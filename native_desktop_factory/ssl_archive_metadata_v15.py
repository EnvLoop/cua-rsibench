"""Bounded metadata-only SSL archive inspection; never extract or execute."""
import hashlib
import io
import json
import pathlib
import tarfile

ARCHIVE = '/usr/local/share/e2b/ssl-certs.tar'
MAX_ARCHIVE_BYTES = 4 * 1024 * 1024
MAX_MEMBERS = 2048
MAX_MEMBER_BYTES = 2 * 1024 * 1024
MAX_TOTAL_PAYLOAD = 8 * 1024 * 1024
CERT_ROOTS = ('/etc/ssl/certs', '/usr/share/ca-certificates', '/usr/local/share/ca-certificates')
KNOWN_GUEST_CA = ('/etc/ssl/certs/ca-certificates.crt', '/usr/local/share/ca-certificates/e2b-ca.crt')
PRIVATE_PEM_MARKERS = tuple(b'-----BEGIN ' + kind + b' PRIVATE KEY-----' for kind in
                           (b'RSA', b'EC', b'DSA', b'OPENSSH', b'ENCRYPTED')) + (b'-----BEGIN PRIVATE KEY-----',)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def cert_index(live_root):
    live_root = live_root.resolve()
    rows = {}; total = 0; seen = 0
    allowed = tuple((live_root / prefix.lstrip('/')).resolve() for prefix in CERT_ROOTS)
    for directory in allowed:
        if not directory.is_dir():continue
        for path in sorted(directory.rglob('*')):
            if not path.is_file() or not any(path.resolve().is_relative_to(root) for root in allowed):continue
            seen += 1
            if seen > 5000 or path.stat().st_size > MAX_MEMBER_BYTES:raise ValueError('Live certificate scan exceeds bound')
            raw = path.read_bytes(); total += len(raw)
            if total > 32 * 1024 * 1024:raise ValueError('Live certificate bytes exceed bound')
            absolute = '/' + str(path.relative_to(live_root))
            rows.setdefault(sha(raw), set()).add(absolute)
    return rows, seen, total


def inspect(path=pathlib.Path(ARCHIVE), live_root=pathlib.Path('/')):
    if path.stat().st_size > MAX_ARCHIVE_BYTES:raise ValueError('Archive exceeds byte bound')
    raw = path.read_bytes(); live, files, live_bytes = cert_index(live_root)
    records = []; payload_bytes = 0
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        for member in archive:
            if len(records) >= MAX_MEMBERS or len(member.name) > 1024 or member.size > MAX_MEMBER_BYTES or member.sparse:
                raise ValueError('Archive member exceeds inspection bound')
            item = {'name': member.name, 'type': member.type.decode('ascii', errors='backslashreplace'),
                    'mode': member.mode, 'uid': member.uid, 'gid': member.gid, 'size': member.size,
                    'mtime': member.mtime, 'linkname': member.linkname,
                    'pax_header_names': sorted(member.pax_headers),
                    'is_regular_file': member.isfile(),
                    'payload_sha256': None, 'contains_private_key_pem': False, 'certificate_pem_blocks': 0,
                    'matching_live_certificate_paths': [], 'matches_known_per_guest_ca': []}
            if member.isfile():
                stream = archive.extractfile(member)  # Reads archive bytes only; never writes/extracts a path.
                payload = stream.read(MAX_MEMBER_BYTES + 1)
                if len(payload) != member.size:raise ValueError('Archive payload length changed')
                payload_bytes += len(payload)
                if payload_bytes > MAX_TOTAL_PAYLOAD:raise ValueError('Archive total payload exceeds bound')
                checksum = sha(payload)
                matches = sorted(live.get(checksum, set()))
                item.update(payload_sha256=checksum,
                    contains_private_key_pem=any(marker in payload for marker in PRIVATE_PEM_MARKERS),
                    certificate_pem_blocks=payload.count(b'-----BEGIN CERTIFICATE-----'),
                    matching_live_certificate_paths=matches,
                    matches_known_per_guest_ca=[p for p in matches if p in KNOWN_GUEST_CA])
            records.append(item)
    return {'schema': 'cua-native-ssl-archive-metadata-v15', 'archive_path': ARCHIVE,
            'archive_bytes': len(raw), 'archive_sha256': sha(raw), 'member_count': len(records),
            'total_payload_bytes': payload_bytes, 'live_certificate_files_checked': files,
            'live_certificate_bytes_checked': live_bytes,
            'members_with_private_key_pem': sum(r['contains_private_key_pem'] for r in records),
            'regular_members_without_live_certificate_match': sum(r['is_regular_file'] and not r['matching_live_certificate_paths'] for r in records),
            'members': records, 'raw_payloads_persisted': False, 'archive_extracted': False,
            'archive_executed': False, 'tls_configuration_changed': False}


if __name__ == '__main__':
    print(json.dumps(inspect(), sort_keys=True))
