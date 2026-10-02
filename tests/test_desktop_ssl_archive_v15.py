import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import tarfile
import unittest
from unittest.mock import patch

from native_desktop_factory import ssl_archive_metadata_v15 as inspection
from tools import probe_desktop_ssl_archive_v15 as runner


def archive(path, rows):
    with tarfile.open(path, 'w') as output:
        for name, payload in rows:
            item = tarfile.TarInfo(name); item.size = len(payload); item.mode = 0o644
            output.addfile(item, io.BytesIO(payload))


class SSLTests(unittest.TestCase):
    def test_live_certificate_and_known_guest_ca_match_are_hash_only(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); cert = root / 'usr/local/share/ca-certificates/e2b-ca.crt'
            cert.parent.mkdir(parents=True); payload = b'-----BEGIN CERTIFICATE-----\nfixture\n-----END CERTIFICATE-----'
            cert.write_bytes(payload); tar = root / 'archive.tar'; archive(tar, [('usr/local/share/ca-certificates/e2b-ca.crt', payload)])
            result = inspection.inspect(tar, root)
            self.assertEqual(result['members'][0]['matches_known_per_guest_ca'], ['/usr/local/share/ca-certificates/e2b-ca.crt'])
            self.assertEqual(result['members'][0]['certificate_pem_blocks'], 1)
            self.assertNotIn('fixture', json.dumps(result))
            self.assertFalse(result['archive_extracted']); self.assertFalse(result['tls_configuration_changed'])

    def test_private_key_marker_is_detected_without_persisting_payload(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); tar = root / 'archive.tar'; secret = b'-----BEGIN RSA PRIVATE KEY-----\nDO_NOT_EXPORT_RAW_KEY\n-----END RSA PRIVATE KEY-----'
            archive(tar, [('private.key', secret)])
            result = inspection.inspect(tar, root)
            self.assertEqual(result['members_with_private_key_pem'], 1)
            self.assertNotIn('DO_NOT_EXPORT_RAW_KEY', json.dumps(result))
            self.assertFalse(result['raw_payloads_persisted'])

    def test_traversal_member_is_not_written_or_used_as_live_read_path(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); tar = root / 'archive.tar'
            archive(tar, [('../untrusted.txt', b'contents')])
            result = inspection.inspect(tar, root)
            self.assertEqual(result['members'][0]['matching_live_certificate_paths'], [])
            self.assertFalse((root.parent / 'untrusted.txt').exists())

    def test_member_size_and_archive_bytes_are_bounded(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); tar = root / 'archive.tar'; archive(tar, [('too-large.crt', b'0123456789')])
            with patch.object(inspection, 'MAX_MEMBER_BYTES', 5):
                with self.assertRaises(ValueError):inspection.inspect(tar, root)
            with patch.object(inspection, 'MAX_ARCHIVE_BYTES', 5):
                with self.assertRaises(ValueError):inspection.inspect(tar, root)

    def test_paid_flag_precedes_all_private_reads(self):
        with patch.object(runner.parent, 'validate', side_effect=AssertionError('Private read')):
            with self.assertRaisesRegex(ValueError, 'disabled'):runner.run(Path('/absent'), Path('/absent'))

    def test_source_binding_is_additive_and_restores_parent_references(self):
        old = runner.parent.sources
        with runner.binding():
            sources = runner.parent.sources()
            self.assertIn('native_desktop_factory/ssl_archive_metadata_v15.py', sources)
            self.assertEqual(runner.parent.SCHEMA, runner.SCHEMA)
        self.assertIs(runner.parent.sources, old)


if __name__ == '__main__':unittest.main()
