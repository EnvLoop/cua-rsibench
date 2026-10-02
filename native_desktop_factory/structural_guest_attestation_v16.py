"""Common truthful projected runtime identity for controls and model guests.

The raw manifest/tree hash is retained. Only the provider certificate tar's
content hash is projected to a frozen member descriptor; no TLS state changes.
"""
import gzip
import json
from pathlib import Path

from . import runtime_fingerprint_probe as legacy
from . import ssl_archive_metadata_v15 as ssl
from .factory import digest
from .v066_storage_budget import reserve_and_write
from tools.audit_desktop_ssl_archive_evidence_v16 import canonical_members

IDENTITY = 'projected-ssl-archive-structural-v16'
ARCHIVE = '/usr/local/share/e2b/ssl-certs.tar'
LEGACY_PROBE = legacy.GUEST_CONTENT_PROBE


def projected_manifest(raw, canonical_sha):
    decoded = gzip.decompress(raw)
    if len(decoded) > 128_000_000:raise ValueError('Guest manifest exceeds bound')
    output = []; replaced = 0
    for line in decoded.splitlines():
        row = json.loads(line)
        if row[0] == ARCHIVE:
            if row[1] != 'regular_file' or row[5][0] != 522240:raise ValueError('SSL archive row shape changed')
            row[5] = [row[5][0], canonical_sha]; replaced += 1
        output.append((json.dumps(row, sort_keys=True, separators=(',', ':')) + '\n').encode())
    if replaced != 1:raise ValueError('One exact SSL archive row is required')
    return digest(b''.join(output)), digest(decoded)


def script():
    inspector = Path(ssl.__file__).read_text().rsplit("\nif __name__ == '__main__':", 1)[0]
    fields = tuple(__import__('tools.audit_desktop_ssl_archive_evidence_v16', fromlist=['CANONICAL_FIELDS']).CANONICAL_FIELDS)
    prelude = (inspector + '\nssl_observed=inspect()\nssl_members=[{k:r[k] for k in ' + repr(fields) +
        "} for r in sorted(ssl_observed['members'],key=lambda r:r['name'])]\n" +
        "ssl_canonical_sha=sha(json.dumps(ssl_members,sort_keys=True,separators=(',',':')).encode())\n")
    base = LEGACY_PROBE
    markers = ['summary=hashlib.sha256();counts=', 'summary.update(encoded);manifest.write(encoded)',
               "'content_tree_sha256':summary.hexdigest()", "'schema':'native-guest-content-manifest-v1'"]
    if any(base.count(marker) != 1 for marker in markers):raise ValueError('Immutable legacy probe shape changed')
    base = base.replace(markers[0], 'summary=hashlib.sha256();projected=hashlib.sha256();counts=')
    base = base.replace(markers[1], "summary.update(encoded)\n projected_row=list(row)\n if path=='" + ARCHIVE +
        "':projected_row[5]=[row[5][0],ssl_canonical_sha]\n projected.update(json.dumps(projected_row,sort_keys=True,separators=(',',':')).encode()+b'\\n')\n manifest.write(encoded)")
    base = base.replace(markers[2], "'content_tree_sha256':projected.hexdigest(),'raw_content_tree_sha256':summary.hexdigest()," +
        "'identity_kind':'" + IDENTITY + "','ssl_archive_canonical_sha256':ssl_canonical_sha,'ssl_archive_metadata':ssl_observed")
    base = base.replace(markers[3], "'schema':'native-guest-content-projected-v16'")
    return prelude + base


def build_reference(old_reference, old_manifest, archive_evidence):
    old = json.loads(old_reference.read_bytes()); evidence = json.loads(archive_evidence.read_bytes())
    policy = evidence['structural_proposal']; canonical_sha = policy['canonical_members_sha256']
    raw = old_manifest.read_bytes(); projected_sha, old_raw_sha = projected_manifest(raw, canonical_sha)
    if old_raw_sha != old['static_content_sha256'] or digest(raw) not in old['private_compressed_manifest_sha256s']:
        raise ValueError('Original raw reference manifest changed')
    keys = ('provider_template_id', 'provider_envd_version', 'provider_shape', 'kernel_identity',
            'static_content_counts', 'static_content_excluded_paths')
    return {'schema': 'cua-native-desktop-structural-runtime-reference-v16', 'identity_kind': IDENTITY,
            **{key: old[key] for key in keys}, 'static_content_sha256': projected_sha,
            'raw_legacy_content_tree_sha256': old_raw_sha, 'old_guest_reference_sha256': digest(old_reference.read_bytes()),
            'old_manifest_sha256': digest(raw), 'ssl_evidence_sha256': digest(archive_evidence.read_bytes()),
            'ssl_archive_exact_canonical_members': policy['exact_canonical_members'],
            'ssl_archive_canonical_sha256': canonical_sha, 'guest_content_probe_script_sha256': digest(script().encode()),
            'raw_archive_hash_is_observed_not_projected_identity': True, 'original_reference_rewritten': False,
            'tls_configuration_changed': False, 'task_or_scorer_exception': False,
            'live_projected_identity_verified': False, 'official_model_results': 0}


def verify(observed, raw_manifest, reference):
    if reference['schema'] != 'cua-native-desktop-structural-runtime-reference-v16' or reference['identity_kind'] != IDENTITY:
        raise ValueError('Explicit structural runtime reference required')
    metadata = observed['ssl_archive_metadata']; members = canonical_members(metadata)
    canonical_sha = digest(json.dumps(members, sort_keys=True, separators=(',', ':')).encode())
    projected_sha, raw_sha = projected_manifest(raw_manifest, canonical_sha)
    archive_rows = [json.loads(line) for line in gzip.decompress(raw_manifest).splitlines()
                    if json.loads(line)[0] == ARCHIVE]
    if len(archive_rows) != 1 or archive_rows[0][5] != [metadata['archive_bytes'], metadata['archive_sha256']]:
        raise ValueError('Archive metadata is not bound to its raw filesystem manifest')
    if not (observed.get('schema') == 'native-guest-content-projected-v16' and observed.get('identity_kind') == IDENTITY and
            members == reference['ssl_archive_exact_canonical_members'] and canonical_sha == reference['ssl_archive_canonical_sha256'] == observed['ssl_archive_canonical_sha256'] and
            projected_sha == reference['static_content_sha256'] == observed['content_tree_sha256'] and
            raw_sha == observed['raw_content_tree_sha256'] and
            observed['counts'] == reference['static_content_counts'] and observed['kernel'] == reference['kernel_identity'] and
            observed['excluded_paths'] == reference['static_content_excluded_paths'] and
            metadata['members_with_private_key_pem'] == 0 and metadata['raw_payloads_persisted'] is metadata['archive_extracted'] is metadata['archive_executed'] is metadata['tls_configuration_changed'] is False):
        raise ValueError('Projected identity, immutable rows or exact SSL member descriptor changed')
    return {'schema': 'cua-native-runtime-structural-attestation-v16', 'status': 'projected_identity_verified',
            'identity_kind': IDENTITY, 'projected_tree_sha256': projected_sha, 'raw_tree_sha256': raw_sha,
            'raw_archive_sha256': metadata['archive_sha256'], 'archive_canonical_sha256': canonical_sha,
            'archive_mtimes_observed': [m['mtime'] for m in metadata['members']],
            'raw_tree_equals_legacy_reference': raw_sha == reference['raw_legacy_content_tree_sha256'],
            'tls_configuration_changed': False}


def execute_probe(sandbox, *, root, out, reference):
    sandbox.files.write('/tmp/native-guest-content-probe-v066.py', script().encode())
    try:result = sandbox.commands.run('sudo -n python3 /tmp/native-guest-content-probe-v066.py', timeout=450, request_timeout=480)
    except Exception as exc:
        if not all(hasattr(exc, key) for key in ('exit_code', 'stdout', 'stderr')):raise
        result = exc
    return capture_result(sandbox, result, root=root, out=out, reference=reference)


def capture_result(sandbox, result, *, root, out, reference):
    capture = {'exit_code': result.exit_code, 'stdout': result.stdout, 'stderr': result.stderr}
    reserve_and_write(root, out / 'guest-probe-command-v16.private.json', (json.dumps(capture, sort_keys=True) + '\n').encode())
    raw = bytes(sandbox.files.read('/tmp/native-guest-content-files.jsonl.gz', format='bytes'))
    reserve_and_write(root, out / 'guest-content-files-v16.jsonl.gz', raw)
    if result.exit_code != 0:raise ValueError('Structural content probe failed; raw output retained')
    observed = json.loads(result.stdout); attestation = verify(observed, raw, reference)
    reserve_and_write(root, out / 'structural-attestation-v16.private.json', (json.dumps(attestation, sort_keys=True) + '\n').encode())
    return result, observed, attestation
