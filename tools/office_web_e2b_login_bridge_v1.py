"""Start or stop a bounded train-only E2B desktop for manual Office web login.

No Microsoft credentials, cookies, task gold, or final task URLs are accepted.
The remote desktop is not a qualified benchmark environment until a separate
train-only native-GUI and saved-artifact pilot passes.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlparse


SCHEMA = 'envloop-office-web-e2b-login-bridge-private-v1'
OFFICE_URL = 'https://powerpoint.cloud.microsoft/'
EXPECTED_TEMPLATE_ID = 'k0wmnzir0zuzye6dndlw'


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_new(path: Path, value: dict) -> str:
    raw = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return sha(raw)


def validate_stream(url: str, auth_key: str) -> None:
    parsed = urlparse(url)
    require(parsed.scheme == 'https' and parsed.hostname is not None and
            parsed.hostname.endswith('.e2b.app') and
            parsed.path.endswith('/vnc.html') and
            isinstance(auth_key, str) and
            re.fullmatch(r'[A-Za-z0-9_-]{12,100}', auth_key) is not None,
            'password-protected E2B desktop stream missing or unexpected')


def start(out: Path, lease_seconds: int, expected_template_id: str,
          sandbox_factory) -> dict:
    private = (Path.cwd() / 'work').resolve()
    out = out.resolve()
    require(out.is_relative_to(private) and not out.exists() and
            300 <= lease_seconds <= 3600 and
            re.fullmatch(r'[a-z0-9]{20}', expected_template_id) is not None,
            'fresh private output, bounded lease and pinned template required')
    require(bool(os.environ.get('E2B_API_KEY')),
            'E2B_API_KEY must be available only in the host environment')
    out.mkdir(parents=True, mode=0o700)
    intent = {'schema': SCHEMA, 'status': 'start_intent',
              'lease_seconds': lease_seconds,
              'expected_template_id': expected_template_id,
              'office_url': OFFICE_URL, 'account_login': 'manual_only',
              'credential_or_cookie_injection': False,
              'task_split': 'train_only',
              'model_calls': 0, 'official_final_admitted': 0,
              'created_at_unix': int(time.time()),
              'launcher_sha256': sha(Path(__file__).read_bytes())}
    write_new(out / 'intent.private.json', intent)
    sandbox = None
    try:
        sandbox = sandbox_factory.create(
            template='desktop', resolution=(1280, 800),
            timeout=lease_seconds, allow_internet_access=True,
            secure=True, envs={})
        info = sandbox.get_info(request_timeout=12)
        require(info.template_id == expected_template_id,
                'E2B Desktop template changed before Office login')
        sandbox.stream.start(require_auth=True)
        url = sandbox.stream.get_url(auto_connect=False, view_only=False)
        auth_key = sandbox.stream.get_auth_key()
        validate_stream(url, auth_key)
        sandbox.launch('google-chrome', uri=OFFICE_URL)
        session = {'schema': SCHEMA, 'status': 'awaiting_manual_login',
                   'sandbox_id': sandbox.sandbox_id,
                   'stream_url': url,
                   'stream_auth_key': auth_key,
                   'lease_seconds': lease_seconds,
                   'lease_started_at_unix': int(time.time()),
                   'expected_template_id': expected_template_id,
                   'observed_template_id': info.template_id,
                   'observed_envd_version': info.envd_version,
                   'sdk_version': importlib.metadata.version('e2b-desktop'),
                   'office_url': OFFICE_URL,
                   'account_login': 'manual_only',
                   'credential_or_cookie_injection': False,
                   'credential_snapshot_or_export': False,
                   'task_split': 'train_only',
                   'provider_billed_usd': None,
                   'model_calls': 0, 'official_final_admitted': 0}
        digest = write_new(out / 'session.private.json', session)
        return {'status': session['status'],
                'private_session_path': str(out / 'session.private.json'),
                'private_session_sha256': digest,
                'lease_seconds': lease_seconds,
                'provider_billed_usd': None,
                'model_calls': 0, 'official_final_admitted': 0}
    except BaseException as error:
        cleanup = 'not_created'
        if sandbox is not None:
            try:
                cleanup = 'killed' if sandbox.kill() else 'kill_unconfirmed'
            except Exception:
                cleanup = 'kill_unconfirmed'
        write_new(out / 'failure.private.json',
                  {'schema': SCHEMA, 'status': 'setup_failed',
                   'error_type': type(error).__name__,
                   'sandbox_cleanup': cleanup,
                   'model_calls': 0, 'official_final_admitted': 0})
        raise


def stop(session_path: Path, sandbox_factory) -> dict:
    private = (Path.cwd() / 'work').resolve()
    session_path = session_path.resolve()
    require(session_path.is_relative_to(private) and
            session_path.name == 'session.private.json' and
            not (session_path.parent / 'stop.private.json').exists(),
            'private unstopped login session required')
    session = json.loads(session_path.read_bytes())
    require(session['schema'] == SCHEMA and
            session['status'] == 'awaiting_manual_login' and
            session['task_split'] == 'train_only',
            'login bridge session changed')
    sandbox = sandbox_factory.connect(session['sandbox_id'])
    try:
        killed = sandbox.kill()
    except Exception:
        killed = False
    receipt = {'schema': SCHEMA, 'status':
               'killed' if killed else 'termination_unconfirmed',
               'sandbox_id_sha256': sha(session['sandbox_id'].encode()),
               'session_sha256': sha(session_path.read_bytes()),
               'terminated_at_unix': int(time.time()),
               'model_calls': 0, 'official_final_admitted': 0}
    digest = write_new(session_path.parent / 'stop.private.json', receipt)
    return {'status': receipt['status'],
            'private_stop_receipt_sha256': digest,
            'official_final_admitted': 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true')
    mode.add_argument('--start', action='store_true')
    mode.add_argument('--stop', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--lease-seconds', type=int, default=900)
    parser.add_argument('--expected-template-id', default=EXPECTED_TEMPLATE_ID)
    args = parser.parse_args()
    if args.dry_run:
        require(300 <= args.lease_seconds <= 3600,
                'bounded train-only lease required')
        print(json.dumps({'status': 'dry_run_no_provider_call',
                          'office_url': OFFICE_URL,
                          'credential_or_cookie_injection': False,
                          'lease_seconds': args.lease_seconds,
                          'template_id': args.expected_template_id,
                          'official_final_admitted': 0}, sort_keys=True))
        return
    from e2b_desktop import Sandbox
    if args.start:
        require(args.out is not None, '--out required for start')
        result = start(args.out, args.lease_seconds,
                       args.expected_template_id, Sandbox)
    else:
        result = stop(args.stop, Sandbox)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
