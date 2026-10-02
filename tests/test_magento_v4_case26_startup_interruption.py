"""Safety checks for the additive case-26 preconfiguration interruption."""

from copy import deepcopy
import fcntl
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
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
                   'observed_at': 1700000005.0,
                   'model_calls': 0, 'official_final_admitted': 0,
                   'containers': [
                       {'name': recovery.sweep.APP, 'image_sha256': recovery.v4.IMAGE, 'mount_count': 0,
                        'container_id_sha256': recovery.prior.sha(b'review-app-id'),
                        'created': '2023-11-14T22:13:21+00:00'},
                       {'name': recovery.sweep.SEARCH, 'image_sha256': recovery.v4.NATIVE_SEARCH_IMAGE, 'mount_count': 0,
                        'container_id_sha256': recovery.prior.sha(b'review-search-id'),
                        'created': '2023-11-14T22:13:21+00:00'}]}
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

    def test_missing_duplicate_or_bad_container_identity_is_rejected(self):
        for alter in ('missing', 'invalid', 'duplicate', 'late', 'early'):
            w, p, b, s = self.fixture()
            if alter == 'missing': del w['containers'][0]['container_id_sha256']
            if alter == 'invalid': w['containers'][0]['container_id_sha256'] = 'unbound'
            if alter == 'duplicate': w['containers'][1]['container_id_sha256'] = w['containers'][0]['container_id_sha256']
            if alter == 'late': w['containers'][0]['created'] = '2023-11-15T22:13:21+00:00'
            if alter == 'early': w['containers'][0]['created'] = '2023-11-13T22:13:21+00:00'
            with patch.object(recovery.prior, '_reference', return_value=(b, s)), \
                 self.subTest(alter=alter), self.assertRaises(ValueError):
                recovery.verify_witness({'root': Path('/tmp')}, w, p, start_time=1700000000.0)


class Case26V2ProtocolTests(unittest.TestCase):
    """Real temporary-file protocols, with Docker replaced by an in-memory pair."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.p = recovery.paths(self.root)
        self.p['attempt'].mkdir(mode=0o700, parents=True)
        self.p['v1_public'].parent.mkdir(parents=True)
        self.witness, self.parent, self.baseline, self.startup = Case26InterruptionTests().fixture()
        self.cases = [{'task_id': f'review-case-{i}', 'package_sha256': f'review-package-{i}'}
                      for i in range(100)]
        for event in ({'event': 'case_attempt_started', 'index': 26, 'attempt': 0,
                       **self.cases[26], 'model_calls': 0, 'official_final_admitted': 0},
                      {'event': 'step_intent', 'index': 26, 'attempt': 0,
                       'step': 'positive-prepare', 'official_final_admitted': 0}):
            recovery.v4.append_event(self.p['journal'], event)
        self.prefix = recovery.v4.read_journal(self.p['journal'])
        self.context = {'parent': self.parent, 'cases': self.cases,
                        'rows': self.prefix, 'start_time': 1700000000.0}
        self.prefix_raw = self.p['journal'].read_bytes()
        self.sources = {'isolated-review-source.py': 'f' * 64}
        old_freeze = {'schema': 'envloop-magento-case26-startup-freeze-private-v1',
                      'journal_sha256': recovery.prior.sha(self.prefix_raw),
                      'classification': recovery.CLASSIFICATION, 'case_index': 26,
                      'initial_witness': self.witness, 'source_sha256s': self.sources,
                      'model_calls': 0, 'official_final_admitted': 0}
        old_sha = recovery.v4.private_new(self.p['v1_freeze'], old_freeze)
        self.p['v1_public'].write_text(json.dumps({'private_freeze_sha256': old_sha}))
        old_audit = {'schema': 'envloop-magento-clean-attempt-audit-private-v4',
                     'status': 'invalid_infrastructure_attempt_before_gui_mutation',
                     'case_index': 26, 'attempt': 0, **self.cases[26],
                     'plan_sha256': recovery.prior.PLAN_SHA,
                     'freeze_v4_sha256': recovery.prior.FREEZE_SHA,
                     'startup_interruption_amendment_freeze_sha256': old_sha,
                     'journal_sha256_before_audit': recovery.prior.sha(self.prefix_raw),
                     'classification': recovery.CLASSIFICATION, 'active_pair': 'positive',
                     'material_witness': self.witness, 'model_calls': 0, 'official_final_admitted': 0}
        audit_sha = recovery.v4.private_new(self.p['audit'], old_audit)
        self.original_audit_bytes = self.p['audit'].read_bytes()
        self.original_freeze_bytes = self.p['v1_freeze'].read_bytes()
        self.original_public_bytes = self.p['v1_public'].read_bytes()
        self.infos = {
            recovery.sweep.APP: {'Id': 'review-app-id', 'Image': recovery.v4.IMAGE,
                                 'Mounts': [], 'State': {'Running': True}},
            recovery.sweep.SEARCH: {'Id': 'review-search-id', 'Image': recovery.v4.NATIVE_SEARCH_IMAGE,
                                    'Mounts': [], 'State': {'Running': True}}}
        self.dispatches = []
        self.patches = [
            patch.object(recovery, 'V1_FREEZE_SHA', old_sha),
            patch.object(recovery, 'V1_PUBLIC_SHA', recovery.prior.sha(self.original_public_bytes)),
            patch.object(recovery, 'V1_AUDIT_SHA', audit_sha),
            patch.object(recovery, 'ORIGINAL_JOURNAL_SHA', recovery.prior.sha(self.prefix_raw)),
            patch.object(recovery, 'ORIGINAL_JOURNAL_BYTES', len(self.prefix_raw)),
            patch.object(recovery, 'ORIGINAL_JOURNAL_ROWS', len(self.prefix)),
            patch.object(recovery, '_context', return_value=self.context),
            patch.object(recovery, '_sources', return_value=self.sources),
            patch.object(recovery, '_mutation_root'),
            patch.object(recovery, 'inspect', return_value=self.witness),
            patch.object(recovery, '_workers_absent', return_value={'matching_original_workers': 0}),
            patch.object(recovery.prior, '_reference', return_value=(self.baseline, self.startup)),
            patch.object(recovery.v4, '_lock', side_effect=self.lock),
            patch.object(recovery.v4, '_docker_inspect', side_effect=lambda name: self.infos.get(name)),
            patch.object(recovery.v4.subprocess, 'run', side_effect=self.docker),
            patch.object(recovery.v4, 'validate_case_sequence'),
            patch.object(recovery.sweep, 'assert_absent', side_effect=self.absent),
        ]
        for item in self.patches: item.start()
        self.addCleanup(lambda: [item.stop() for item in reversed(self.patches)])

    def lock(self):
        fd = os.open(self.root / '.isolated-test.lock', os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd

    def docker(self, argv, **kwargs):
        action, name = argv[-2:]
        self.assertIn(action, ('stop', 'rm'))
        self.dispatches.append((name, action))
        if action == 'stop': self.infos[name]['State']['Running'] = False
        else: del self.infos[name]
        return SimpleNamespace(returncode=0, stdout=b'review-only-result', stderr=b'')

    def absent(self):
        self.assertEqual(self.infos, {})

    def prepare_audit(self):
        recovery.prepare(self.p)
        recovery.audit(self.p)

    def assert_history(self):
        self.assertEqual(self.p['historical_audit'].read_bytes(), self.original_audit_bytes)
        self.assertEqual(self.p['v1_freeze'].read_bytes(), self.original_freeze_bytes)
        self.assertEqual(self.p['v1_public'].read_bytes(), self.original_public_bytes)
        self.assertEqual(self.p['historical_audit'].stat().st_mode & 0o777, 0o600)

    def test_v2_prepare_does_not_supersede_original_audit(self):
        result = recovery.prepare(self.p)
        self.assertEqual(result['schema'], 'envloop-magento-case26-startup-freeze-public-v2')
        self.assertEqual(self.p['audit'].read_bytes(), self.original_audit_bytes)
        self.assertFalse(self.p['historical_audit'].exists())
        self.assertFalse(self.p['intent'].exists())
        self.assertEqual(self.dispatches, [])

    def test_explicit_audit_supersession_retains_original_bytes_and_journal(self):
        self.prepare_audit()
        self.assert_history()
        self.assertNotEqual(self.p['audit'].read_bytes(), self.original_audit_bytes)
        self.assertEqual(self.p['journal'].read_bytes(), self.prefix_raw)
        self.assertEqual(self.dispatches, [])
        new_bytes = self.p['audit'].read_bytes()
        recovery.audit(self.p)
        self.assertEqual(self.p['audit'].read_bytes(), new_bytes)
        self.assert_history()

    def test_supersession_recovers_after_replace_before_completion_receipt(self):
        recovery.prepare(self.p)
        original = recovery.v4.private_new
        def interrupted(path, value):
            if path == self.p['supersession_receipt']: raise RuntimeError('review interruption')
            return original(path, value)
        with patch.object(recovery.v4, 'private_new', side_effect=interrupted), self.assertRaises(RuntimeError):
            recovery.audit(self.p)
        self.assert_history()
        self.assertNotEqual(self.p['audit'].read_bytes(), self.original_audit_bytes)
        self.assertFalse(self.p['supersession_receipt'].exists())
        recovery.audit(self.p)
        self.assertTrue(self.p['supersession_receipt'].exists())
        self.assertEqual(self.p['journal'].read_bytes(), self.prefix_raw)
        self.assertEqual(self.dispatches, [])

    def test_supersession_failure_before_archive_preserves_standard_audit(self):
        recovery.prepare(self.p)
        with patch.object(recovery, '_atomic_bytes', side_effect=RuntimeError('review interruption')), \
             self.assertRaises(RuntimeError):
            recovery.audit(self.p)
        self.assertEqual(self.p['audit'].read_bytes(), self.original_audit_bytes)
        self.assertFalse(self.p['supersession_intent'].exists())
        recovery.audit(self.p)
        self.assert_history()

    def test_cleanup_intent_file_without_event_is_recoverable(self):
        self.prepare_audit()
        append = recovery.v4.append_event
        def interrupted(path, event):
            if event['event'] == 'reconciliation_cleanup_intent':
                raise RuntimeError('review interruption')
            append(path, event)
        with patch.object(recovery.v4, 'append_event', side_effect=interrupted), self.assertRaises(RuntimeError):
            recovery.cleanup(self.p)
        self.assertTrue(self.p['intent'].exists())
        self.assertEqual(self.p['journal'].read_bytes(), self.prefix_raw)
        self.assertEqual(self.dispatches, [])
        result = recovery.cleanup(self.p)
        self.assertEqual(result['cleanup_finish_event_count'], 4)
        self.assertEqual(len(self.dispatches), 4)
        recovery.cleanup(self.p)
        self.assertEqual(len(self.dispatches), 4)
        self.assert_history()

    def _interrupted_effect(self, action):
        self.prepare_audit()
        append = recovery.v4.append_event
        def interrupted(path, event):
            if event['event'] == 'cleanup_step_finished' and \
               event['name'] == recovery.sweep.APP and event['action'] == action:
                raise RuntimeError('review interruption')
            append(path, event)
        with patch.object(recovery.v4, 'append_event', side_effect=interrupted), self.assertRaises(RuntimeError):
            recovery.cleanup(self.p)
        result = recovery.cleanup(self.p)
        self.assertEqual(result['cleanup_finish_event_count'], 3)
        self.assertFalse(result['original_cleanup_command_results_reconstructed'])
        self.assertEqual(len(self.dispatches), 4)
        receipt, _ = recovery._private(self.p['receipt'])
        self.assertEqual(len(receipt['cleanup_actions_with_unrecorded_command_results']), 1)
        self.assert_history()

    def test_stop_effect_without_original_finish_event_is_not_replayed(self):
        self._interrupted_effect('stop')

    def test_remove_effect_without_original_finish_event_is_not_replayed(self):
        self._interrupted_effect('rm')

    def test_generic_auditor_reopens_effect_only_retirement(self):
        from tools import audit_magento_v4_completed_prefix as generic
        self._interrupted_effect('stop')
        rows = recovery.v4.read_journal(self.p['journal'])
        result = generic._check_retry(
            self.p['run'], rows, 26, self.cases[26],
            {'plan_sha256': recovery.prior.PLAN_SHA,
             'study_wide_infrastructure_retry_cap': recovery.v4.RETRY_CAP},
            recovery.prior.FREEZE_SHA, self.parent)
        self.assertEqual(result, recovery.CLASSIFICATION)

    def test_generic_auditor_checks_metadata_before_case26_delegate(self):
        from tools import audit_magento_v4_completed_prefix as generic
        self.prepare_audit()
        recovery.cleanup(self.p)
        audit, _ = recovery._private(self.p['audit'])
        audit['model_calls'] = 9
        self.p['audit'].write_bytes(recovery.v4.encode(audit))
        with patch.object(recovery, 'verify_saved_retry') as delegate, \
             self.assertRaises(ValueError):
            generic._check_retry(
                self.p['run'], recovery.v4.read_journal(self.p['journal']), 26,
                self.cases[26], {'plan_sha256': recovery.prior.PLAN_SHA,
                'study_wide_infrastructure_retry_cap': recovery.v4.RETRY_CAP},
                recovery.prior.FREEZE_SHA, self.parent)
        delegate.assert_not_called()

    def test_active_worker_blocks_cleanup_on_reentry(self):
        self.prepare_audit()
        append = recovery.v4.append_event
        def interrupted(path, event):
            if event['event'] == 'cleanup_step_finished':
                raise RuntimeError('review interruption')
            append(path, event)
        with patch.object(recovery.v4, 'append_event', side_effect=interrupted), self.assertRaises(RuntimeError):
            recovery.cleanup(self.p)
        with patch.object(recovery, '_workers_absent', side_effect=ValueError('worker active')), \
             self.assertRaises(ValueError):
            recovery.cleanup(self.p)
        self.assertEqual(len(self.dispatches), 1)

    def test_full_metadata_guard_rejects_schema_identity_caps_and_work(self):
        for field, value in (('schema', 'wrong'), ('task_id', 'other-review-case'),
                             ('attempt', 1), ('active_pair', 'negative'),
                             ('whole_case_retry_cap_per_id', 2), ('model_calls', 9),
                             ('official_final_admitted', 9)):
            record = {**recovery._identity(self.context, 'review-freeze'), 'schema': 'review-schema'}
            record[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                recovery._check_record(record, self.context, 'review-freeze', 'review-schema')

    def test_invalid_finish_hash_or_extra_activity_is_rejected(self):
        self.prepare_audit()
        recovery.cleanup(self.p)
        rows = recovery.v4.read_journal(self.p['journal'])
        for corrupt in ('bad_hash', 'duplicate_finish', 'extra_gui'):
            altered = deepcopy(rows)
            finish = next(r for r in altered if r['event'] == 'cleanup_step_finished')
            if corrupt == 'bad_hash': finish['stdout_sha256'] = 'unrecorded'
            if corrupt == 'duplicate_finish': altered.append(deepcopy(finish))
            if corrupt == 'extra_gui': altered.append({'event': 'step_intent', 'index': 26,
                'attempt': 0, 'step': 'positive-gui', 'official_final_admitted': 0})
            with self.subTest(corrupt=corrupt), self.assertRaises(ValueError):
                recovery._cleanup_events(altered, self.witness, complete=True)


if __name__ == '__main__': unittest.main()
