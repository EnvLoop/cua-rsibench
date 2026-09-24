"""Fail-closed publication gate for account-backed benchmark evidence.

Raw browser traces, authentication state, screenshots and private provider
artifacts are never release inputs. This checks the explicit text inventory;
reviewed binaries require an independently recorded SHA-256 allowlist.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re


TEXT_SUFFIXES = frozenset({'.json', '.jsonl', '.md', '.txt', '.csv', '.tsv', '.html', '.css', '.js', '.mjs', '.py', '.svg', '.sha256'})
TEXT_NAMES = frozenset({'.gitignore'})
PRIVATE_NAMES = frozenset({'.env', 'storage_state.json', 'auth_state.json', 'cookies.json', 'secrets.json', 'credentials.json'})
PRIVATE_SUFFIXES = frozenset({'.har', '.sqlite', '.sqlite3', '.db', '.key', '.pem', '.p12', '.pfx'})
SECRET_PATTERNS = (
    ('provider credential', re.compile(r'(?:tml-|e2b_|sk-)[A-Za-z0-9_-]{20,}')),
    ('bearer credential', re.compile(r'(?i)\bBearer\s+[A-Za-z0-9._~+/-]{16,}')),
    ('Microsoft sharing link', re.compile(r'(?i)https?://(?:1drv\.ms|[^/\s]*\.sharepoint\.com|onedrive\.live\.com)/[^\s<>"\']+')),
    ('account email', re.compile(r'(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b')),
    ('OAuth token field', re.compile(r'(?i)"(?:access_token|refresh_token|id_token|client_secret|session_cookie)"\s*:')),
)
MARKER_ENV_NAMES = ('BENCH_ACCOUNT_EMAIL', 'BENCH_MS_CLIENT_ID', 'BENCH_MS_TENANT_ID',
                    'BENCH_TEST_ACCOUNT_PASSWORD', 'OPENAI_API_KEY', 'TINKER_API_KEY', 'E2B_API_KEY')


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def private_markers(environment=None):
    environment = os.environ if environment is None else environment
    # Never echo markers, even when a release is rejected.
    return tuple(value for name in MARKER_ENV_NAMES if (value := environment.get(name)) and len(value) >= 6)


def scan_public_tree(root, *, markers=(), approved_binary_hashes=None):
    root = Path(root).resolve()
    if not root.is_dir() or root.is_symlink():
        raise ValueError('public inventory root must be a regular directory')
    approved = set(approved_binary_hashes or ())
    files = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('public inventory contains a symlink')
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if any(part.lower() in PRIVATE_NAMES for part in path.relative_to(root).parts) or path.suffix.lower() in PRIVATE_SUFFIXES:
            raise ValueError('public inventory contains an authentication or raw-state file')
        data = path.read_bytes()
        digest = sha256(data)
        is_text = path.suffix.lower() in TEXT_SUFFIXES or path.name.lower() in TEXT_NAMES
        if is_text:
            try:
                content = data.decode('utf-8')
            except UnicodeDecodeError:
                raise ValueError('claimed public text is not UTF-8') from None
            if any(marker.encode() in data for marker in markers if marker):
                raise ValueError('private account or provider marker found in public text')
            for label, pattern in SECRET_PATTERNS:
                if pattern.search(content):
                    raise ValueError(label + ' found in public text')
        elif digest not in approved:
            raise ValueError('unreviewed binary file in public inventory')
        files[relative] = {'sha256': digest, 'bytes': len(data),
                           'reviewed_binary': not is_text}
    if not files:
        raise ValueError('empty public inventory')
    return {'schema': 'scale-publication-boundary-v1', 'status': 'text-and-inventory-pass',
            'files': files, 'raw_ui_trace_reviewed': False,
            'screenshot_content_reviewed': False,
            'interpretation': 'This gate checks bytes and paths. It cannot OCR an approved screenshot or attest to external account permissions.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-root', type=Path, required=True)
    parser.add_argument('--approved-binary-hashes', type=Path,
                        help='JSON list of SHA-256 digests for separately reviewed binaries')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    approved = json.loads(args.approved_binary_hashes.read_text()) if args.approved_binary_hashes else []
    result = scan_public_tree(args.public_root, markers=private_markers(), approved_binary_hashes=approved)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'file_count': len(result['files'])}))


if __name__ == '__main__':
    main()
