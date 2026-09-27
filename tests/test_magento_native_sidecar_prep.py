"""A nonzero local indexer is reconciled by saved state, never blindly retried."""

from __future__ import annotations

import subprocess
from unittest.mock import patch
import unittest

from tools import start_magento_native_sidecar_clone_v1 as prep


class NativeSidecarPreparationTests(unittest.TestCase):
    def test_nonzero_indexer_accepts_only_matching_read_only_catalog(self):
        outcome = subprocess.CompletedProcess(['indexer'], 1, b'', b'error')
        with patch.object(prep, 'audit_existing', return_value={
                'status': 'clone_and_sidecar_prepared_no_task_seeded'}) as audit:
            receipt = prep.reconcile_indexer_result('a' * 64, outcome)
        audit.assert_called_once_with('a' * 64,
            'read_only_state_reconciled_after_indexer_process_error')
        self.assertEqual(receipt['indexer_process']['exit_code'], 1)
        self.assertFalse(receipt['indexer_process']['reported_success'])
        with patch.object(prep, 'audit_existing', side_effect=ValueError(
                'native-sidecar catalog differs from frozen source index')):
            with self.assertRaisesRegex(ValueError, 'differs from frozen'):
                prep.reconcile_indexer_result('a' * 64, outcome,
                                              settle_seconds=0)

    def test_eventually_visible_index_is_audited_without_reindex_retry(self):
        outcome = subprocess.CompletedProcess(['indexer'], 0,
            b'Catalog Search index has been rebuilt successfully', b'')
        with patch.object(prep, 'audit_existing', side_effect=[
                ValueError('native-sidecar catalog differs from frozen source index'),
                {'status': 'clone_and_sidecar_prepared_no_task_seeded'}]) as audit, \
             patch.object(prep.time, 'sleep'):
            receipt = prep.reconcile_indexer_result('c' * 64, outcome,
                                                    settle_seconds=30)
        self.assertEqual(audit.call_count, 2)
        self.assertEqual(receipt['indexer_process']['read_only_audit_attempts'], 2)

    def test_normal_indexer_keeps_new_clone_mode(self):
        outcome = subprocess.CompletedProcess(['indexer'], 0,
            b'Catalog Search index has been rebuilt successfully', b'')
        with patch.object(prep, 'audit_existing', return_value={}) as audit:
            receipt = prep.reconcile_indexer_result('b' * 64, outcome)
        audit.assert_called_once_with('b' * 64, 'new_clone')
        self.assertTrue(receipt['indexer_process']['reported_success'])


if __name__ == '__main__':
    unittest.main()
