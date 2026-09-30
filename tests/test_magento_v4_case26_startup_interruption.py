"""Safety checks for the additive case-26 preconfiguration interruption."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import magento_v4_case26_startup_interruption_20260930 as recovery


class Case26InterruptionTests(unittest.TestCase):
    def fixture(self):
        hashes = {key: 'a' * 64 for key in recovery.prior.STABLE_SQL}
        baseline = {'database': {'hashes': {'full': hashes}}}
        startup = {'train_probe_price_stages': {'after_cron_policy_and_http_ready':
                   {'live_price_sha256': 'a' * 64}}}
        parent = {'runtime': {'cron_config_sha256': 'b' * 64}}
        witness = {'state': 'live_unseeded_preconfig_operator_interruption',
                   'sql_hashes': hashes, 'sql_table_count': 14, 'price_rows': 8156,
                   'price_changed_rows': 0, 'price_key_sets_equal': True,
                   'quote_pages': 0, 'native_sidecar_index_count': 0,
                   'task_seeded': False, 'material_equal_exact': True,
                   'config_paths': ['web/unsecure/base_url'],
                   'config_value_sha256': recovery.prior.sha(b'http://localhost:7780/'),
                   'cron_config_sha256': 'b' * 64, 'cron_stopped': True,
                   'embedded_search_stopped': True, 'workers': {'matching_original_workers': 0},
                   'model_calls': 0, 'official_final_admitted': 0,
                   'containers': [
                       {'name': recovery.sweep.APP, 'image_sha256': recovery.v4.IMAGE, 'mount_count': 0},
                       {'name': recovery.sweep.SEARCH, 'image_sha256': recovery.v4.NATIVE_SEARCH_IMAGE, 'mount_count': 0}]}
        return witness, parent, baseline, startup

    def check(self, witness, parent, baseline, startup):
        with patch.object(recovery.prior, '_reference', return_value=(baseline, startup)):
            recovery.verify_witness({'root': Path('/tmp')}, witness, parent)

    def test_original_source_state_is_valid_without_http_readiness(self):
        w, p, b, s = self.fixture()
        w['http_diagnostic'] = {'exit_code': 28, 'status': '000'}
        self.check(w, p, b, s)

    def test_one_sql_or_price_or_seed_change_is_rejected(self):
        for field, value in [('price_changed_rows', 1), ('task_seeded', True),
                             ('quote_pages', 1), ('native_sidecar_index_count', 1)]:
            w, p, b, s = self.fixture(); w[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): self.check(w, p, b, s)
        w, p, b, s = self.fixture(); w = deepcopy(w)
        w['sql_hashes'][recovery.prior.STABLE_SQL[0]] = 'c' * 64
        with self.assertRaises(ValueError): self.check(w, p, b, s)

    def test_mount_or_config_or_live_worker_is_rejected(self):
        for alter in ('mount', 'config', 'worker'):
            w, p, b, s = self.fixture()
            if alter == 'mount': w['containers'][0]['mount_count'] = 1
            if alter == 'config': w['config_paths'].append('catalog/search/engine')
            if alter == 'worker': w['workers']['matching_original_workers'] = 1
            with self.subTest(alter=alter), self.assertRaises(ValueError): self.check(w, p, b, s)

    def test_http_diagnostics_do_not_hide_source_change(self):
        w, _, _, _ = self.fixture(); other = deepcopy(w)
        w['http_diagnostic'] = {'status': '000'}; other['http_diagnostic'] = {'status': '200'}
        self.assertEqual(recovery.stable(w), recovery.stable(other))
        other['price_rows'] = 8155
        self.assertNotEqual(recovery.stable(w), recovery.stable(other))

    def test_live_python_worker_blocks_recovery(self):
        result = SimpleNamespace(stdout='123 /usr/bin/python python -m tools.magento_clean_100_v4 run\n')
        with patch.object(recovery.subprocess, 'run', return_value=result), self.assertRaises(ValueError):
            recovery._workers_absent()


if __name__ == '__main__': unittest.main()
