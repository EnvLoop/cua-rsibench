"""No-Docker v4 bounded-dispatch, immutable-prefix and interruption checks."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools import magento_clean_100_v4 as v4

REAL_VALIDATE_FREEZE = v4.validate_freeze


def _cases():
    return [{'task_id': f'candidate-{i:03d}',
             'package_sha256': f'{i + 1:064x}'} for i in range(100)]


class ChunkedMagentoV4Tests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / 'work/magento-original'
        self.work.mkdir(parents=True)
        self.run_dir = self.work / 'clean-v4-100-20260929'
        self.cases = _cases()
        self.frozen = {
            'parent_v3_freeze_sha256': 'v' * 64,
            'parent_cron_freeze_sha256': 'p' * 64,
            'plan_sha256': 'a' * 64,
            'ordered_task_identity_sha256': v4.case_identity_digest(self.cases),
            'source_commit': 'source',
            'parent_runtime_fingerprint_sha256': 'r' * 64,
            'pinned_python_runtime_sha256': 'y' * 64,
            'train_only_release_guard_pilot_sha256': 't' * 64,
            'v2_retirement_public_sha256': 'h' * 64,
        }
        self.old = {'runtime_fingerprint_sha256': 'r' * 64}
        self.task_ids = []

        def fake_task(index, case, plan, plan_sha, source, target,
                      journal, *, cellwide_freeze, journal_append):
            self.task_ids.append(index)
            journal_append(journal, {
                'event': 'task_gui_calibrated', 'index': index,
                'task_id': case['task_id'], 'receipt_sha256': f'{index + 1:064x}'})

        def fake_verify(run_dir, events, index, number, case, fingerprint):
            self.assertEqual(fingerprint, 'r' * 64)
            self.assertEqual(case, self.cases[index])
            self.assertTrue(v4.attempt_dir(run_dir, index, number).is_dir())
            return f'{index + 1:064x}'

        patches = (
            patch.object(v4, 'ROOT', self.root),
            patch.object(v4, 'V4_RUN', self.run_dir),
            patch.object(v4, 'validate_freeze', return_value=(
                self.frozen, self.old, 'f' * 64)),
            patch.object(v4, 'validate_plan', return_value=self.cases),
            patch.object(v4, '_lock', return_value=1),
            patch.object(v4, '_unlock'),
            patch.object(v4, '_check_single_dispatch'),
            patch.object(v4.sweep_v3, 'assert_absent'),
            patch.object(v4.sweep_v3, 'task', side_effect=fake_task),
            patch.object(v4, 'verify_finished_attempt', side_effect=fake_verify),
        )
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def _run(self, *, resume=False, max_cases=2):
        return v4.run_campaign(
            self.work / 'plan.json', 'a' * 64,
            self.work / 'source', self.work / 'old-freeze.json',
            self.work / 'v4-freeze.json', self.run_dir,
            resume=resume, max_cases=max_cases)

    def test_two_chunks_are_exact_and_do_not_replay(self):
        first = self._run()
        self.assertEqual(first['completed_distinct_cases'], 2)
        self.assertEqual(first['next_case_index'], 2)
        self.assertEqual(self.task_ids, [0, 1])
        second = self._run(resume=True)
        self.assertEqual(second['completed_distinct_cases'], 4)
        self.assertEqual(self.task_ids, [0, 1, 2, 3])
        journal = v4.read_journal(self.run_dir / 'journal.private.jsonl')
        v4.validate_chunk_boundaries(journal, self.cases, self.frozen,
                                     'f' * 64)
        self.assertEqual(len([e for e in journal if e['event'] ==
                              'chunk_completed']), 2)
        self.assertEqual(len([e for e in journal if e['event'] ==
                              'dispatch_started']), 2)

    def test_invalid_cap_stops_before_directory_creation(self):
        for cap in (0, 6, -1):
            with self.assertRaisesRegex(ValueError, 'bounded 1-to-5'):
                self._run(max_cases=cap)
        self.assertFalse(self.run_dir.exists())

    def test_changed_completed_receipt_stops_before_new_task(self):
        self._run()
        events = v4.read_journal(self.run_dir / 'journal.private.jsonl')
        with patch.object(v4, 'verify_finished_attempt', return_value='z' * 64):
            with self.assertRaisesRegex(ValueError, 'previously completed'):
                self._run(resume=True)
        self.assertEqual(self.task_ids, [0, 1])
        self.assertEqual(v4.read_journal(self.run_dir / 'journal.private.jsonl'),
                         events)

    def test_unjournaled_attempt_directory_stops_before_new_task(self):
        self._run()
        (self.run_dir / 'attempts/case-002-attempt-0').mkdir()
        with self.assertRaisesRegex(ValueError, 'unjournaled or missing'):
            self._run(resume=True)
        self.assertEqual(self.task_ids, [0, 1])

    def test_open_dispatch_closes_at_completed_case_without_replay(self):
        self._run()
        journal = self.run_dir / 'journal.private.jsonl'
        rows = v4.read_journal(journal)
        journal.write_bytes(b''.join(v4.encode(row) for row in rows[:-1]))
        result = self._run(resume=True)
        self.assertEqual(result['completed_distinct_cases'], 2)
        self.assertEqual(self.task_ids, [0, 1])
        self.assertEqual(v4.read_journal(journal)[-1]['event'],
                         'chunk_completed')

    def test_open_dispatch_cannot_change_cap(self):
        self._run()
        journal = self.run_dir / 'journal.private.jsonl'
        rows = v4.read_journal(journal)
        journal.write_bytes(b''.join(v4.encode(row) for row in rows[:-1]))
        with self.assertRaisesRegex(ValueError, 'open dispatch cap'):
            self._run(resume=True, max_cases=3)
        self.assertEqual(self.task_ids, [0, 1])

    def test_changed_chunk_boundary_blocks_next_dispatch(self):
        self._run()
        journal = self.run_dir / 'journal.private.jsonl'
        rows = v4.read_journal(journal)
        bad = dict(rows[-1], completed_distinct_cases=3)
        del bad['sequence']
        del bad['previous_line_sha256']
        del bad['schema']
        del bad['time']
        journal.write_bytes(b''.join(v4.encode(row) for row in rows[:-1]))
        v4.append_event(journal, bad)
        with self.assertRaisesRegex(ValueError, 'case-boundary receipt'):
            self._run(resume=True)
        self.assertEqual(self.task_ids, [0, 1])

    def test_parent_v3_freeze_binding_is_explicit(self):
        with patch.object(v4, 'V3_FREEZE', self.work / 'old-v3-freeze'), \
                patch.object(v4.parent_v3, 'V3_RUN', self.work / 'old-v3-run'), \
                patch.object(v4.parent_v3, 'validate_freeze', return_value=(
                {'ordered_case_count': 100,
                 'whole_case_retry_cap_per_id': 1,
                 'study_wide_infrastructure_retry_cap': 20,
                 'model_calls': 0, 'official_final_admitted': 0}, {},
                'v' * 64)), patch.object(v4, 'CODE_FILES', ()):
            value = v4.build_freeze(self.root, self.work / 'old',
                                    self.work / 'plan', 'a' * 64,
                                    self.work / 'source')
        self.assertEqual(value['parent_v3_freeze_sha256'], 'v' * 64)
        self.assertEqual(value['historical_v3_controls_reused'], 0)
        self.assertEqual(value['max_cases_per_dispatch'], 5)

    def test_changed_parent_freeze_fails_v4_validation(self):
        old_digest = ['v' * 64]
        prior = {
            'ordered_case_count': 100,
            'whole_case_retry_cap_per_id': 1,
            'study_wide_infrastructure_retry_cap': 20,
            'model_calls': 0, 'official_final_admitted': 0,
            'parent_cron_freeze_sha256': 'p' * 64,
            'parent_runtime_fingerprint_sha256': 'r' * 64,
            'plan_sha256': 'a' * 64,
            'ordered_task_identity_sha256': v4.case_identity_digest(self.cases),
            'pinned_python_runtime_sha256': 'y' * 64,
            'train_only_release_guard_pilot_sha256': 't' * 64,
            'v2_retirement_public_sha256': 'h' * 64,
        }
        def fake_parent(*_args, **_kwargs):
            return prior, {}, old_digest[0]
        private_path = self.work / 'v4-freeze.json'
        public_path = self.root / 'docs/evidence/v4-freeze.json'
        with patch.object(v4, 'V3_FREEZE', self.work / 'old-v3-freeze'), \
                patch.object(v4, 'PUBLIC_FREEZE', public_path), \
                patch.object(v4, 'PROBE_DIR', self.work / 'probe'), \
                patch.object(v4, 'TRAIN_DIR', self.work / 'train'), \
                patch.object(v4.parent_v3, 'V3_RUN', self.work / 'old-v3-run'), \
                patch.object(v4.parent_v3, 'validate_freeze', side_effect=fake_parent), \
                patch.object(v4.old_contract, 'validate_freeze',
                             return_value=({}, 'p' * 64)), \
                patch.object(v4, 'CODE_FILES', ()):
            frozen = v4.build_freeze(self.root, self.work / 'old',
                                     self.work / 'plan', 'a' * 64,
                                     self.work / 'source')
            freeze_sha = v4.private_new(private_path, frozen)
            public_path.parent.mkdir(parents=True)
            public_path.write_text(json.dumps({
                'schema': 'envloop-magento-clean-100-freeze-public-v4',
                'private_freeze_sha256': freeze_sha,
                'parent_v3_freeze_sha256': old_digest[0],
                'max_cases_per_dispatch': 5,
                'parent_cron_freeze_sha256': 'p' * 64,
                'runtime_fingerprint_sha256': 'r' * 64,
                'plan_sha256': 'a' * 64,
                'ordered_task_identity_sha256':
                v4.case_identity_digest(self.cases),
                'pinned_python_runtime_sha256': 'y' * 64,
                'train_only_release_guard_pilot_sha256': 't' * 64,
                'v2_retirement_public_sha256': 'h' * 64,
                'historical_v2_controls_reused': 0,
                'historical_v3_controls_reused': 0,
                'study_wide_infrastructure_retry_cap': 20,
                'model_calls': 0, 'official_final_admitted': 0,
            }))
            self.assertEqual(REAL_VALIDATE_FREEZE(
                private_path, self.work / 'old', self.work / 'plan',
                'a' * 64, self.work / 'source', root=self.root)[2], freeze_sha)
            old_digest[0] = 'z' * 64
            with self.assertRaisesRegex(ValueError, 'v4 pre-result freeze'):
                REAL_VALIDATE_FREEZE(private_path, self.work / 'old',
                                     self.work / 'plan', 'a' * 64,
                                     self.work / 'source', root=self.root)

    def test_one_failure_stops_mid_case_and_refuses_unreconciled_replay(self):
        def fail(*_args, **_kwargs):
            raise RuntimeError('deliberate child interruption')
        with patch.object(v4.sweep_v3, 'task', side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, 'deliberate child'):
                self._run(max_cases=3)
        events = v4.read_journal(self.run_dir / 'journal.private.jsonl')
        self.assertEqual(len([row for row in events if row['event'] ==
                              'case_attempt_started']), 1)
        self.assertEqual(len([row for row in events if row['event'] ==
                              'case_completed']), 0)
        with self.assertRaisesRegex(ValueError, 'incomplete attempt needs'):
            self._run(resume=True, max_cases=3)

    def test_100_cases_finish_in_exact_twenty_five_case_chunks(self):
        for chunk in range(20):
            result = self._run(resume=chunk > 0, max_cases=5)
            self.assertEqual(result['completed_distinct_cases'], (chunk + 1) * 5)
            self.assertEqual(result['official_final_admitted'], 0)
        self.assertEqual(self.task_ids, list(range(100)))
        events = v4.read_journal(self.run_dir / 'journal.private.jsonl')
        self.assertEqual(events[-1]['event'], 'run_completed')
        self.assertEqual(len([row for row in events if row['event'] ==
                              'chunk_completed']), 19)
        self.assertEqual(len([row for row in events if row['event'] ==
                              'dispatch_started']), 20)
        with self.assertRaisesRegex(ValueError, 'already completed'):
            self._run(resume=True, max_cases=1)


if __name__ == '__main__':
    unittest.main()
