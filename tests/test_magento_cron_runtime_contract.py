"""The revised Magento runtime cannot inherit old passes or partial controls."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from magento_catalog_factory.seed import IMAGE
from magento_catalog_factory.verify import NATIVE_SEARCH_IMAGE
from tools import audit_magento_cron_requalification_v1 as auditor
from tools import magento_cron_runtime_contract_v1 as contract


def prepared() -> dict:
    return {
        'schema': 'envloop-magento-native-sidecar-clone-preparation-v1',
        'status': 'clone_and_sidecar_prepared_no_task_seeded',
        'application_clone': {'image_sha256': IMAGE, 'mount_count': 0},
        'search_sidecar_image_sha256': NATIVE_SEARCH_IMAGE,
        'search_document_count': 181,
        'search_documents_sha256': contract.SEARCH_SHA,
        'train_probe_cron': {'policy': contract.POLICY,
                             'config_sha256': 'c' * 64},
        'train_probe_price_stages': {
            stage: {'price_rows': 8156, 'price_key_sets_equal': True,
                    'price_changed_rows': 0, 'live_price_sha256': 'p',
                    'replica_price_sha256': 'p'}
            for stage in contract.STAGES},
        'official_final_tasks_admitted': 0,
    }


class MagentoCronRuntimeContractTests(unittest.TestCase):
    def test_prepared_pair_requires_all_four_zero_drift_stages(self):
        source = prepared()
        contract.validate_prepared(source, config_sha256='c' * 64)
        source['train_probe_price_stages']['after_search_reindex']['price_changed_rows'] = 1
        with self.assertRaisesRegex(ValueError, 'prepared pair differs'):
            contract.validate_prepared(source, config_sha256='c' * 64)
        source = prepared()
        del source['train_probe_price_stages']['after_idle_60_seconds']
        with self.assertRaisesRegex(ValueError, 'prepared pair differs'):
            contract.validate_prepared(source, config_sha256='c' * 64)

    def test_old_final_sweep_refused_before_files_or_docker(self):
        result = subprocess.run([
            sys.executable, 'tools/sweep_magento_original_gui_controls_v1.py',
            '--plan', '/does-not-exist', '--plan-sha256', '0' * 64,
            '--split', 'official_candidate', '--source', '/does-not-exist',
            '--out-dir', '/does-not-exist', '--limit', '100',
        ], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('cell-wide cron freeze required', result.stderr)

    def test_partial_revised_sweep_refused_before_files_or_docker(self):
        result = subprocess.run([
            sys.executable, 'tools/sweep_magento_original_gui_controls_v1.py',
            '--plan', '/does-not-exist', '--plan-sha256', '0' * 64,
            '--split', 'official_candidate', '--source', '/does-not-exist',
            '--out-dir', '/does-not-exist', '--limit', '1',
            '--cellwide-cron-freeze', '/does-not-exist',
        ], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('one fresh 0..99 sweep', result.stderr)

    def test_training_journal_without_complete_trio_cannot_freeze(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'events.private.jsonl').write_text(json.dumps({
                'event': 'sweep_started', 'split': 'train_policy_development',
                'plan_sha256': 'a' * 64, 'start_index': 0, 'limit': 1,
                'recovery_of_private_journal_sha256': None,
                'model_calls': 0, 'official_final_admitted': False,
            }) + '\n')
            with self.assertRaisesRegex(ValueError, 'uninterrupted'):
                contract.validate_train_gui(root, 'c' * 64, 'a' * 64,
                                            'r' * 64)

    def test_requalification_audit_rejects_partial_journal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = root / 'plan.json'
            plan.write_text(json.dumps({'cases': {'official_candidate': [
                {'task_id': str(index), 'package_sha256': f'{index:064x}'}
                for index in range(100)]}}))
            sweep = root / 'sweep'
            sweep.mkdir()
            (sweep / 'events.private.jsonl').write_text(json.dumps({
                'event': 'sweep_started', 'split': 'official_candidate',
                'start_index': 0, 'limit': 100,
                'plan_sha256': contract.sha(plan.read_bytes()),
                'cellwide_cron_freeze_sha256': 'f',
                'runtime_fingerprint_sha256': 'r',
                'recovery_of_private_journal_sha256': None,
                'model_calls': 0, 'official_final_admitted': False,
            }) + '\n')
            frozen = {'final_candidate_plan_sha256': contract.sha(plan.read_bytes()),
                      'runtime_fingerprint_sha256': 'r'}
            with patch.object(contract, 'validate_freeze', return_value=(frozen, 'f')):
                with self.assertRaisesRegex(ValueError, 'one uninterrupted'):
                    auditor.audit(plan, frozen['final_candidate_plan_sha256'], sweep,
                                  root / 'freeze.json')


if __name__ == '__main__':
    unittest.main()
