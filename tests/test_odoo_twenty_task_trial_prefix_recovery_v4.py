"""Recovery gates: actual saved audit, uncertain exclusion and no dispatch."""
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from enterprise_fallback.odoo18 import twenty_task_trial_prefix_recovery_v4 as subject
from enterprise_fallback.odoo18 import twenty_task_trial_selection_v4 as selection
from tools.check_odoo20_tinker_access_v1 import result_receipt


class PrefixRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve(); self.root.chmod(0o700)

    def save(self, name, value):
        path = self.root/name; path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_text(json.dumps(value)); path.chmod(0o600)
        return subject.absolute_ref(path)

    def access(self):
        terminal = {'exit_code': 1, 'automatic_restarts': 0, 'ended_at': 10}
        terminal_ref = self.save('terminal.private.json', terminal)
        raw = {'supported_models': [{'model_name': subject.MODEL, 'trainable': True, 'sampleable': True}]}
        raw_ref = self.save('capabilities.private.json', raw)
        access = result_receipt(terminal_ref=terminal_ref, terminal=terminal, started_at=11, ended_at=12,
            capabilities=raw, status_code=200, error_type=None, close_returned=True, raw_provider_evidence_ref=raw_ref)
        return access, {'original_terminal_ref': terminal_ref, 'original_terminal_ended_at': 10}

    def test_actual_root_capabilities_receipt_is_required_not_ready_boolean(self):
        access, candidate = self.access()
        reference = self.save('access.private.json', access)
        self.assertEqual(subject.checked_access(reference, candidate), access)
        for change in ({'status': 'not_ready', 'provider_http_status': 402}, {'owned_close_returned': False},
                       {'automatic_retries': 1}, {'checked_after_prior_terminal': False}, {'started_at': 9},
                       {'checked_at': 13}, {'supported_model_verified': False}, {'injected_authority': True},
                       {'owned_close_awaited': False}, {'checker_source_sha256': '0'*64}):
            with self.subTest(change=change):
                changed = {**access, **change}; reference = self.save('access.private.json', changed)
                with self.assertRaises(ValueError): subject.checked_access(reference, candidate)

    def test_capabilities_raw_bytes_and_supported_model_cannot_be_swapped(self):
        access, candidate = self.access()
        raw_ref = access['raw_provider_evidence_ref']
        Path(raw_ref['path']).write_text(json.dumps({'supported_models': []}))
        with self.assertRaises(ValueError):
            subject.checked_access(self.save('access.private.json', access), candidate)
        access['raw_provider_evidence_ref'] = subject.absolute_ref(Path(raw_ref['path']))
        with self.assertRaisesRegex(ValueError, 'capabilities_model_list'):
            subject.checked_access(self.save('access.private.json', access), candidate)

    def test_mirror_preserves_all_bytes_original_hashes_and_private_mode(self):
        self.save('episode/frame.private.json', {'frame': 'synthetic test fixture'})
        lock = self.root/'episode/journal.lock'; lock.touch(mode=0o600)
        source = self.root/'episode'; mirror = self.root/'mirror.private'
        items = subject._mirror(source, mirror)
        self.assertEqual(len(items), 2)
        for item in items:
            original = Path(item['original_path']); copied = mirror/item['mirror_relative_path']
            self.assertEqual(original.read_bytes(), copied.read_bytes())
            self.assertEqual(copied.stat().st_mode & 0o077, 0)
        (source/'symlink').symlink_to(source/'frame.private.json')
        with self.assertRaisesRegex(ValueError, 'link_forbidden'):
            subject._mirror(source, self.root/'mirror-2.private')

    def test_journal_is_opened_read_only_and_missing_results_reject(self):
        journal = self.root/'sampling-journal/requests.sqlite3'; journal.parent.mkdir(mode=0o700)
        connection = sqlite3.connect(journal)
        connection.execute('CREATE TABLE requests (id TEXT, state TEXT, result TEXT)')
        connection.execute('INSERT INTO requests VALUES (?,?,?)', ('synthetic-request', 'complete', '{"status":"error"}'))
        connection.commit(); connection.close(); journal.chmod(0o600)
        before = journal.read_bytes()
        self.assertEqual(subject._journal(self.root), [('synthetic-request', 'complete', {'status': 'error'})])
        self.assertEqual(journal.read_bytes(), before)
        journal.with_name(journal.name+'-wal').touch(mode=0o600)
        with self.assertRaisesRegex(ValueError, 'unsettled_sqlite'):
            subject._journal(self.root)

    def test_incomplete_attempt_cannot_be_imported_as_completed_score(self):
        task = {'task_id': 'SYNTHETIC-SEL-3', 'package_sha256': 'a'*64}
        failure = {'schema': 'envloop-odoo20-selection-task-failure-v3', 'task': task,
            'same_request_replay_authorized': False, 'formal_large_study_credit': 0, 'actual_cost_usd': None}
        self.save('selection-task-failure.private.json', failure)
        self.save('saved-state.private.json', {'score': 0})
        with self.assertRaisesRegex(ValueError, 'cannot_have_model_outcome'):
            subject._audit_exclusion(self.root, task)

    def test_source_facade_does_not_mutate_v3_or_native_binding(self):
        original_before = selection.original.source_binding()
        globals_before = selection.original.freeze_checkpoint.__globals__['source_binding']
        current = selection.source_binding()
        self.assertEqual(selection.original.source_binding(), original_before)
        self.assertIs(selection.original.freeze_checkpoint.__globals__['source_binding'], globals_before)
        self.assertEqual(current['original_selection_source_binding'], original_before)
        self.assertEqual(current['evaluator_source_sha256'], original_before['evaluator_source_sha256'])
        self.assertEqual(current['native_binding_sha256'], original_before['native_binding_sha256'])
        self.assertFalse(current['actor_sampler_scorer_reset_changed'])

    def test_checked_orchestration_compiles_without_dispatch_and_keeps_v3_formats(self):
        before = selection.original.source_binding()
        namespace = {**selection._impl.__dict__}
        code = selection.orchestration_source()
        exec(compile(code, 'saved-only-orchestration-test', 'exec'), namespace)
        self.assertTrue(callable(namespace['run']))
        self.assertIn("'envloop-odoo20-selection-complete-v3'", code)
        self.assertIn('if ordinal < _import_count: continue', code)
        self.assertIn("'continuation_authority_ref': _authority_ref", code)
        self.assertEqual(selection.original.source_binding(), before)

    def test_dispatch_requires_explicit_execute_and_base_recovery_authority(self):
        with patch.object(selection._impl, 'run_owned_task', side_effect=AssertionError('Native dispatch forbidden')), \
             patch.object(selection._impl, 'sampler_class', side_effect=AssertionError('Provider setup forbidden')):
            with self.assertRaisesRegex(ValueError, 'explicit_selection_dispatch'):
                selection.run(execute=False)
            with self.assertRaisesRegex(ValueError, 'base_requires_reviewed_prefix'):
                selection.run(execute=True, base_mode=True)
            with self.assertRaisesRegex(ValueError, 'checkpoint_requires_fresh'):
                selection.run(execute=True, base_mode=False, continuation_authority_path='synthetic',
                    continuation_authority_sha='a'*64)

    def test_review_keeps_whole_task_replacement_distinct_from_request_retry(self):
        review = subject.continuation_review({'sha256': 'a'*64})
        self.assertEqual(review['replacement_ordinal'], 3)
        self.assertEqual(review['unattempted_ordinals'], list(range(4, 20)))
        self.assertTrue(review['one_fresh_whole_task_replacement_authorized'])
        for key in ('original_request_replay_authorized', 'original_attempt_resume_authorized',
                    'automatic_retry_authorized', 'formal_admission_authorized'):
            self.assertIs(review[key], False)

    def test_actual_retained_prefix_reaudit_without_provider_or_native_dispatch(self):
        stage = subject.ROOT/'work/odoo-twenty-task-trial-20261001.private'
        supervisor = stage/'selection-base-native14-readback-v3-03-supervision.private'
        launch = supervisor/'launch-intent.private.json'
        if not launch.is_file(): self.skipTest('Actual private baseline fixture unavailable')
        argv = json.loads(launch.read_bytes())['argv']; arg = lambda name: argv[argv.index('--'+name)+1]
        with patch.object(selection._impl, 'run_owned_task', side_effect=AssertionError('Native dispatch forbidden')), \
             patch.object(selection._impl, 'sampler_class', side_effect=AssertionError('Provider setup forbidden')):
            value = subject.inspect_prefix(plan_path=arg('plan-path'), plan_sha=arg('plan-sha'),
                old_output_root=arg('output-root'), old_root_review_path=arg('root-review-path'),
                old_root_review_sha=arg('root-review-sha'), old_terminal_path=str(supervisor/'worker-terminal.private.json'),
                old_terminal_sha=subject.digest((supervisor/'worker-terminal.private.json').read_bytes()),
                first_case_import_path=arg('saved-case-import-path'), first_case_import_sha=arg('saved-case-import-sha'),
                first_case_review_path=arg('saved-case-review-path'), first_case_review_sha=arg('saved-case-review-sha'),
                worker_dir=arg('worker-dir'))
        self.assertEqual(value['completed_ordinals'], [0, 1, 2])
        self.assertEqual([row['score'] for row in value['scores']], [0, 0, 0])
        self.assertEqual(value['infrastructure_exclusion']['completed_sample_calls'], 44)
        self.assertIsNone(value['infrastructure_exclusion']['model_score'])
        self.assertEqual(value['new_model_calls'], 0)
        self.assertFalse(value['continuation_authorized'])


if __name__ == '__main__': unittest.main()
