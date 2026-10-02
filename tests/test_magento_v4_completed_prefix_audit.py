"""Synthetic boundary tests and opt-in saved-evidence replay for v4 prefixes."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import tempfile
import unittest

from tests.test_magento_v4_twenty_two_prefix_audit_20260930 import (
    twenty_two_fixture,
)
from tools import audit_magento_v4_completed_prefix as current
from tools import audit_magento_v4_partial_batch_20260929 as first
from tools import magento_clean_100_v4 as v4


FREEZE_SHA = 'd' * 64


def add_chunk(rows: list[dict], cases: list[dict], freeze: dict,
              target: int, *, retry_first: bool = False,
              final_capacity: int = 5) -> None:
    start = len([row for row in rows if row.get('event') == 'case_completed'])
    assert target == min(start + 5, 100)
    dispatch = len(rows)
    rows.append({
        'event': 'dispatch_started', 'sequence': dispatch,
        'max_cases': final_capacity if target == 100 else 5,
        'completed_before_dispatch': start,
        'freeze_v4_sha256': FREEZE_SHA,
        'parent_v3_freeze_sha256': freeze['parent_v3_freeze_sha256'],
        'model_calls': 0, 'official_final_admitted': 0,
    })
    for index in range(start, target):
        if retry_first and index == start:
            rows.extend((
                {'event': 'case_attempt_started', 'index': index,
                 'attempt': 0, 'task_id': cases[index]['task_id'],
                 'package_sha256': cases[index]['package_sha256'],
                 'model_calls': 0, 'official_final_admitted': 0},
                {'event': 'step_intent', 'index': index, 'attempt': 0,
                 'step': 'positive-prepare'},
                {'event': 'attempt_stopped', 'index': index, 'attempt': 0,
                 'model_calls': 0, 'official_final_admitted': 0},
                {'event': 'reconciliation_cleanup_intent', 'index': index,
                 'attempt': 0, 'official_final_admitted': 0},
                {'event': 'attempt_reconciled', 'index': index, 'attempt': 0,
                 'model_calls': 0, 'official_final_admitted': 0},
            ))
        attempt = 1 if retry_first and index == start else 0
        rows.append({
            'event': 'case_attempt_started', 'index': index,
            'attempt': attempt, 'task_id': cases[index]['task_id'],
            'package_sha256': cases[index]['package_sha256'],
            'model_calls': 0, 'official_final_admitted': 0,
        })
        for step in first.ORIGINAL_STEPS:
            rows.extend((
                {'event': 'step_intent', 'index': index, 'attempt': attempt,
                 'step': step},
                {'event': 'step_finished', 'index': index, 'attempt': attempt,
                 'step': step, 'exit_code': 0},
            ))
            if step == 'positive-gui':
                rows.append({'event': 'pair_cleanup_verified', 'index': index,
                             'attempt': attempt, 'pair': 'positive'})
            elif step == 'negative-gui':
                rows.append({'event': 'pair_cleanup_verified', 'index': index,
                             'attempt': attempt, 'pair': 'negative'})
        rows.extend((
            {'event': 'task_gui_calibrated', 'index': index,
             'attempt': attempt},
            {'event': 'case_completed', 'index': index, 'attempt': attempt,
             'calibration_sha256': f'{index + 1:064x}',
             'model_calls': 0, 'official_final_admitted': 0},
        ))
    completed = [row['calibration_sha256'] for row in rows if row.get('event') ==
                 'case_completed']
    boundary = {
        'event': 'run_completed' if target == 100 else 'chunk_completed',
        'max_cases': rows[dispatch]['max_cases'],
        'dispatch_sequence': dispatch, 'freeze_v4_sha256': FREEZE_SHA,
        'parent_v3_freeze_sha256': freeze['parent_v3_freeze_sha256'],
        'completed_distinct_cases': target,
        'newly_completed_this_dispatch': target - start,
        'ordered_completed_task_identity_sha256':
            v4.case_identity_digest(cases[:target]),
        'completed_calibration_receipts_sha256':
            first.sha(('\n'.join(completed) + '\n').encode()),
        'journal_prefix_sha256':
            first.sha(b''.join(first.canonical(row) for row in rows)),
        'infrastructure_retries': sum(row.get('event') == 'attempt_reconciled'
                                      for row in rows),
        'model_calls': 0, 'official_final_admitted': 0,
    }
    if target == 100:
        boundary['distinct_cases'] = 100
    rows.append(boundary)


def serialized(rows: list[dict]) -> bytes:
    previous = '0' * 64
    lines = []
    for sequence, row in enumerate(rows):
        value = {**row, 'schema': v4.JOURNAL_SCHEMA,
                 'sequence': sequence, 'previous_line_sha256': previous}
        line = first.canonical(value)
        lines.append(line)
        previous = first.sha(line)
    return b''.join(lines)


class CompletedPrefixTests(unittest.TestCase):
    def test_twenty_seven_and_retry_shape(self):
        rows, cases, freeze = twenty_two_fixture()
        add_chunk(rows, cases, freeze, 27, retry_first=True)
        result = current.check_completed_chunks(
            rows, cases, freeze, FREEZE_SHA, 27)
        self.assertEqual(len(result['completed']), 27)
        self.assertEqual(len(result['chunks']), 6)
        self.assertEqual(result['chunks'][-1]['infrastructure_retries'], 2)

    def test_changed_boundary_order_step_and_model_fail_closed(self):
        rows, cases, freeze = twenty_two_fixture()
        add_chunk(rows, cases, freeze, 27)
        mutations = (
            (-1, 'journal_prefix_sha256', '0' * 64),
            (-1, 'newly_completed_this_dispatch', 4),
            (current.BASE_ROWS, 'max_cases', 6),
            (current.BASE_ROWS + 1, 'index', 27),
            (current.BASE_ROWS + 2, 'step', 'negative-gui'),
            (current.BASE_ROWS + 1, 'model_calls', 1),
        )
        for index, key, value in mutations:
            with self.subTest(index=index, key=key):
                changed = copy.deepcopy(rows)
                changed[index][key] = value
                with self.assertRaises(current.AUDIT_ERROR):
                    current.check_completed_chunks(
                        changed, cases, freeze, FREEZE_SHA, 27)

    def test_reader_stops_at_completed_boundary_during_later_append(self):
        rows, _, _ = twenty_two_fixture()
        baseline = serialized(rows)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'journal.private.jsonl'
            path.write_bytes(baseline + b'{"live":"unfinished"')
            self.assertEqual(current.read_completed_prefix(path, 22)[1],
                             baseline)
            with self.assertRaises(current.AUDIT_ERROR):
                current.read_completed_prefix(path, 27)
            truncated = baseline[:-1]
            path.write_bytes(truncated)
            with self.assertRaises(current.AUDIT_ERROR):
                current.read_completed_prefix(path, 22)

    def test_final_three_case_receipt_and_no_terminal_append(self):
        rows, cases, freeze = twenty_two_fixture()
        for target in (*range(27, 100, 5), 100):
            add_chunk(rows, cases, freeze, target,
                      final_capacity=3 if target == 100 else 5)
        result = current.check_completed_chunks(
            rows, cases, freeze, FREEZE_SHA, 100)
        self.assertEqual(len(result['completed']), 100)
        self.assertEqual(result['chunks'][-1]['newly_completed_this_dispatch'], 3)
        raw = serialized(rows)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'journal.private.jsonl'
            path.write_bytes(raw)
            self.assertEqual(current.read_completed_prefix(path, 100)[1], raw)
            path.write_bytes(raw + b'{"later":"forbidden"}\n')
            with self.assertRaises(current.AUDIT_ERROR):
                current.read_completed_prefix(path, 100)
        rows, cases, freeze = twenty_two_fixture()
        for target in (*range(27, 100, 5), 100):
            add_chunk(rows, cases, freeze, target)
        self.assertEqual(current.check_completed_chunks(
            rows, cases, freeze, FREEZE_SHA, 100)['chunks'][-1]['max_cases'], 5)

    def test_attempt_inventory_rejects_replay_within_prefix(self):
        rows, _, _ = twenty_two_fixture()
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            attempts = run / 'attempts'
            attempts.mkdir()
            for row in rows:
                if row.get('event') == 'case_attempt_started':
                    (attempts / f"case-{row['index']:03d}-attempt-{row['attempt']}").mkdir()
            current._scoped_attempt_inventory(run, rows, 22)
            (attempts / 'case-022-attempt-0').mkdir()
            current._scoped_attempt_inventory(run, rows, 22)
            (attempts / 'case-021-attempt-2').mkdir()
            with self.assertRaises(current.AUDIT_ERROR):
                current._scoped_attempt_inventory(run, rows, 22)

    def test_retried_case_requires_bound_invalid_attempt_and_cleanup(self):
        index = 22
        case = {'task_id': 'synthetic-case', 'package_sha256': 'a' * 64}
        freeze = {'plan_sha256': 'b' * 64,
                  'study_wide_infrastructure_retry_cap': 20}
        rows = [
            {'event': 'case_attempt_started', 'index': index, 'attempt': 0},
            {'event': 'step_intent', 'index': index, 'attempt': 0,
             'step': 'positive-prepare'},
            {'event': 'attempt_stopped', 'index': index, 'attempt': 0},
        ]
        prefix_sha = first.sha(b''.join(first.canonical(row) for row in rows))
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            previous = v4.attempt_dir(run, index, 0)
            previous.mkdir(parents=True)

            def write(name, value):
                raw = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
                (previous / name).write_bytes(raw)
                return first.sha(raw)

            audit = {
                'schema': 'envloop-magento-clean-attempt-audit-private-v4',
                'status': 'invalid_infrastructure_attempt_before_gui_mutation',
                'case_index': index, 'attempt': 0,
                'task_id': case['task_id'],
                'package_sha256': case['package_sha256'],
                'plan_sha256': freeze['plan_sha256'],
                'freeze_v4_sha256': FREEZE_SHA,
                'journal_sha256_before_audit': prefix_sha,
                'classification':
                    'host_or_step_timeout_pre_gui_no_process_failure',
                'active_pair': None, 'material_witness': None,
                'model_calls': 0, 'official_final_admitted': 0,
            }
            audit_sha = write('reconciliation-audit.private.json', audit)
            intent = {
                'schema': 'envloop-magento-clean-cleanup-intent-private-v4',
                'case_index': index, 'attempt': 0,
                'task_id': case['task_id'], 'audit_sha256': audit_sha,
                'journal_sha256_before_cleanup': prefix_sha,
                'active_pair': None, 'material_witness': None,
                'model_calls': 0, 'official_final_admitted': 0,
            }
            intent_sha = write('reconciliation-intent.private.json', intent)
            cleanup = {
                'schema': 'envloop-magento-clean-cleanup-private-v4',
                'status': 'exact_pair_retired_for_one_whole_case_retry',
                'case_index': index, 'attempt': 0,
                'task_id': case['task_id'],
                'package_sha256': case['package_sha256'],
                'plan_sha256': freeze['plan_sha256'],
                'freeze_v4_sha256': FREEZE_SHA,
                'audit_sha256': audit_sha,
                'cleanup_intent_sha256': intent_sha,
                'active_pair': None, 'material_witness': None,
                'both_containers_absent': True,
                'whole_case_retry_cap_per_id': 1,
                'study_wide_retry_cap': 20,
                'model_calls': 0, 'official_final_admitted': 0,
            }
            cleanup_sha = write('reconciliation.private.json', cleanup)
            rows.extend((
                {'event': 'reconciliation_cleanup_intent', 'index': index,
                 'attempt': 0, 'intent_sha256': intent_sha,
                 'audit_sha256': audit_sha},
                {'event': 'attempt_reconciled', 'index': index, 'attempt': 0,
                 'classification': audit['classification'],
                 'reconciliation_sha256': cleanup_sha,
                 'audit_sha256': audit_sha,
                 'both_containers_absent': True},
            ))
            self.assertEqual(current._check_retry(
                run, rows, index, case, freeze, FREEZE_SHA, {}),
                audit['classification'])
            cleanup['both_containers_absent'] = False
            rows[-1]['reconciliation_sha256'] = write(
                'reconciliation.private.json', cleanup)
            with self.assertRaises(current.AUDIT_ERROR):
                current._check_retry(run, rows, index, case, freeze,
                                     FREEZE_SHA, {})

    def test_public_fields_exclude_private_task_material(self):
        self.assertFalse({'task_id', 'sku', 'quote', 'email', 'credential'} &
                         current.PUBLIC_FIELDS)
        report = {key: 0 for key in current.PUBLIC_FIELDS}
        report['completed_distinct_candidate_controls'] = 27
        report['new_candidate_controls_independently_audited'] = 5
        self.assertIn('0 official final tasks admitted',
                      current.render_markdown(report))
        report['task_id'] = 'private'
        with self.assertRaises(current.AUDIT_ERROR):
            current.render_markdown(report)

    @unittest.skipUnless(os.getenv('MAGENTO_V4_PRIVATE_REPO_ROOT'),
                         'private 22-case saved-evidence replay is opt-in')
    def test_replay_published_twenty_two_only(self):
        root = Path(os.environ['MAGENTO_V4_PRIVATE_REPO_ROOT'])
        report = current.audit_completed_prefix(root, root / first.RUN_REL, 22)
        self.assertEqual(report['completed_distinct_candidate_controls'], 22)
        self.assertEqual(report['successful_step_process_receipts_reopened'],
                         22 * len(first.ORIGINAL_STEPS))
        self.assertEqual(report['model_calls'], 0)


if __name__ == '__main__':
    unittest.main()
