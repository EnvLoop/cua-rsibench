from copy import deepcopy
import gzip
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from native_desktop_factory import structural_guest_attestation_v16 as common
from native_desktop_factory import selection_control_structural_worker_v16 as worker
from native_desktop_factory import selection_control_structural_epoch_v16 as epoch
from native_desktop_factory.factory import digest
from tools import probe_desktop_projected_identity_v16 as neutral
from tools.audit_desktop_ssl_archive_evidence_v16 import canonical_members


def fixture():
    member = {'name': './ca-certificates.crt', 'type': '0', 'mode': 420, 'uid': 0, 'gid': 0, 'size': 182140,
              'linkname': '', 'pax_header_names': [], 'is_regular_file': True, 'payload_sha256': 'a' * 64,
              'contains_private_key_pem': False, 'certificate_pem_blocks': 121, 'mtime': 100}
    metadata = {'members': [member], 'members_with_private_key_pem': 0, 'raw_payloads_persisted': False,
                'archive_extracted': False, 'archive_executed': False, 'tls_configuration_changed': False,
                'archive_sha256': 'b' * 64, 'archive_bytes': 522240}
    canonical = canonical_members(metadata); canonical_sha = digest(json.dumps(canonical, sort_keys=True, separators=(',', ':')).encode())
    rows = [['/usr/bin/application', 'regular_file', 493, 0, 0, [1, 'c' * 64]],
            [common.ARCHIVE, 'regular_file', 420, 0, 0, [522240, 'b' * 64]]]
    raw = gzip.compress(b''.join((json.dumps(row, sort_keys=True, separators=(',', ':')) + '\n').encode() for row in rows))
    projected, raw_sha = common.projected_manifest(raw, canonical_sha)
    reference = {'schema': 'cua-native-desktop-structural-runtime-reference-v16', 'identity_kind': common.IDENTITY,
         'ssl_archive_exact_canonical_members': canonical, 'ssl_archive_canonical_sha256': canonical_sha,
         'static_content_sha256': projected, 'raw_legacy_content_tree_sha256': 'd' * 64,
         'static_content_counts': {'regular_file': 2}, 'kernel_identity': {'release': 'fixed'}, 'static_content_excluded_paths': ['fixed']}
    observed = {'schema': 'native-guest-content-projected-v16', 'identity_kind': common.IDENTITY, 'ssl_archive_metadata': metadata,
         'ssl_archive_canonical_sha256': canonical_sha, 'content_tree_sha256': projected, 'raw_content_tree_sha256': raw_sha,
         'counts': {'regular_file': 2}, 'kernel': {'release': 'fixed'}, 'excluded_paths': ['fixed']}
    return observed, raw, reference, rows


class RuntimeTests(unittest.TestCase):
    def test_truthful_projection_preserves_raw_hash_without_legacy_match(self):
        observed, raw, reference, _rows = fixture(); result = common.verify(observed, raw, reference)
        self.assertEqual(result['status'], 'projected_identity_verified')
        self.assertNotEqual(result['projected_tree_sha256'], result['raw_tree_sha256'])
        self.assertFalse(result['raw_tree_equals_legacy_reference'])

    def test_timestamp_only_archive_change_is_observed_not_rejected(self):
        observed, raw, reference, _rows = fixture(); observed['ssl_archive_metadata']['members'][0]['mtime'] = 200
        result = common.verify(observed, raw, reference)
        self.assertEqual(result['archive_mtimes_observed'], [200])

    def test_other_file_mutation_and_certificate_payload_change_are_refused(self):
        observed, raw, reference, rows = fixture(); changed = deepcopy(rows); changed[0][5][1] = 'e' * 64
        mutated = gzip.compress(b''.join((json.dumps(row, sort_keys=True, separators=(',', ':')) + '\n').encode() for row in changed))
        projected, raw_sha = common.projected_manifest(mutated, reference['ssl_archive_canonical_sha256'])
        observed.update(content_tree_sha256=projected, raw_content_tree_sha256=raw_sha)
        with self.assertRaises(ValueError):common.verify(observed, mutated, reference)
        observed, raw, reference, _rows = fixture(); observed['ssl_archive_metadata']['members'][0]['payload_sha256'] = 'f' * 64
        with self.assertRaises(ValueError):common.verify(observed, raw, reference)

    def test_generated_probe_retains_both_identity_names_and_compiles(self):
        generated = common.script(); compile(generated, 'generated-guest-v16', 'exec')
        self.assertIn('raw_content_tree_sha256', generated); self.assertIn('projected.hexdigest()', generated)
        self.assertIn('manifest.write(encoded)', generated)

    def test_disabled_control_and_neutral_entries_precede_private_reads(self):
        with patch.object(worker.epoch, 'validate', side_effect=AssertionError('Private read')):
            with self.assertRaisesRegex(ValueError, 'disabled'):worker.run_trio(freeze_path=Path('/absent'), permit_path=Path('/absent'))
        with patch.object(neutral, 'validate', side_effect=AssertionError('Private read')):
            with self.assertRaisesRegex(ValueError, 'disabled'):neutral.run(Path('/absent'), Path('/absent'))

    def test_ancestor_manifest_and_lease_projection_survive_new_inflight_intent(self):
        from tempfile import TemporaryDirectory
        from native_desktop_factory import selection_control_accounting_epoch_v13 as parent
        from tests.test_desktop_ancestor_accounting_v13 import intent
        with TemporaryDirectory() as tmp:
            broad=Path(tmp);past=broad/'past';closed=broad/'closed-v13';own=broad/'current-v16'
            intent(past,600)
            old_manifest=parent.metadata_manifest([broad],exclude=closed)
            old_ledger=parent.ORIGINAL_ACCOUNTING([broad],exclude=closed)
            intent(closed);intent(own)
            with epoch.parent_history(own):
                self.assertEqual(parent.metadata_manifest([broad],exclude=closed),old_manifest)
                self.assertEqual(parent.ORIGINAL_ACCOUNTING([broad],exclude=closed),old_ledger)
                with parent.ancestor_history((closed,)):
                    self.assertEqual(parent.accounting.lease_accounting([broad]),old_ledger)
            self.assertEqual(epoch.ORIGINAL_ACCOUNTING([broad],exclude=own)['past_full_lease_intents'],2)


if __name__ == '__main__':unittest.main()
