"""Structural and opt-in private replay tests for the seventeen-case prefix."""

from __future__ import annotations

import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tests.test_magento_v4_twelve_prefix_audit_20260929 import twelve_fixture
from tools import audit_magento_v4_partial_batch_20260929 as first
from tools import audit_magento_v4_seventeen_prefix_20260929 as seventeen
from tools import magento_clean_100_v4 as v4


def seventeen_fixture() -> tuple[list[dict], list[dict], dict]:
    rows, cases, freeze = twelve_fixture()
    freeze['study_wide_infrastructure_retry_cap'] = 20
    rows.append({
        'event': 'dispatch_started', 'sequence': seventeen.THIRD_BOUNDARY,
        'max_cases': 5, 'completed_before_dispatch': 12,
        'freeze_v4_sha256': 'd' * 64,
        'parent_v3_freeze_sha256': freeze['parent_v3_freeze_sha256'],
        'model_calls': 0, 'official_final_admitted': 0,
    })
    for index in range(12, 17):
        rows.append({
            'event': 'case_attempt_started', 'index': index, 'attempt': 0,
            'task_id': cases[index]['task_id'],
            'package_sha256': cases[index]['package_sha256'],
            'model_calls': 0, 'official_final_admitted': 0,
        })
        rows.extend({'event': 'step_intent', 'index': index, 'attempt': 0}
                    for _ in range(29))
        rows.append({
            'event': 'case_completed', 'index': index, 'attempt': 0,
            'calibration_sha256': f'{index + 1:064x}',
            'model_calls': 0, 'official_final_admitted': 0,
        })
    assert len(rows) == seventeen.PREFIX_ROWS - 1
    receipts = [r['calibration_sha256'] for r in rows
                if r.get('event') == 'case_completed']
    rows.append({
        'event': 'chunk_completed', 'max_cases': 5,
        'dispatch_sequence': seventeen.THIRD_BOUNDARY,
        'freeze_v4_sha256': 'd' * 64,
        'parent_v3_freeze_sha256': freeze['parent_v3_freeze_sha256'],
        'completed_distinct_cases': 17,
        'newly_completed_this_dispatch': 5,
        'ordered_completed_task_identity_sha256':
            v4.case_identity_digest(cases[:17]),
        'completed_calibration_receipts_sha256':
            first.sha(('\n'.join(receipts) + '\n').encode()),
        'journal_prefix_sha256':
            first.sha(b''.join(first.canonical(row) for row in rows)),
        'infrastructure_retries': 1,
        'model_calls': 0, 'official_final_admitted': 0,
    })
    return rows, cases, freeze


class SeventeenPrefixAuditTest(unittest.TestCase):
    def test_four_chunk_receipts_and_order_pass(self):
        rows, cases, freeze = seventeen_fixture()
        result = seventeen.check_seventeen_chunks(rows, cases, freeze, 'd' * 64)
        self.assertEqual(len(result['completed']), 17)
        self.assertEqual(len(result['chunks']), 4)

    def test_fourth_chunk_tampering_rejected(self):
        rows, cases, freeze = seventeen_fixture()
        for index, key, value in (
                (-1, 'completed_distinct_cases', 18),
                (-1, 'journal_prefix_sha256', '0' * 64),
                (-1, 'completed_calibration_receipts_sha256', '0' * 64),
                (-1, 'infrastructure_retries', 21),
                (seventeen.THIRD_BOUNDARY, 'max_cases', 6),
                (seventeen.THIRD_BOUNDARY + 1, 'index', 17),
                (seventeen.THIRD_BOUNDARY + 1, 'model_calls', 1)):
            with self.subTest(index=index, key=key):
                altered = copy.deepcopy(rows)
                altered[index][key] = value
                with self.assertRaises(seventeen.AUDIT_ERROR):
                    seventeen.check_seventeen_chunks(altered, cases, freeze,
                                                    'd' * 64)

    def test_append_only_prefix_survives_later_journal_appends(self):
        rows, _, _ = seventeen_fixture()
        previous = '0' * 64
        lines = []
        for sequence, value in enumerate(rows):
            row = {**value, 'schema': v4.JOURNAL_SCHEMA,
                   'sequence': sequence, 'previous_line_sha256': previous}
            line = first.canonical(row)
            lines.append(line)
            previous = first.sha(line)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'journal.private.jsonl'
            raw = b''.join(lines)
            path.write_bytes(raw)
            self.assertEqual(seventeen.read_seventeen_prefix(path)[1], raw)
            path.write_bytes(raw + b'{"later":"outside prefix"}\n')
            self.assertEqual(seventeen.read_seventeen_prefix(path)[1], raw)
            altered = lines.copy()
            altered[450] = altered[450].replace(b'step_intent', b'step_changed')
            path.write_bytes(b''.join(altered))
            with self.assertRaises(seventeen.AUDIT_ERROR):
                seventeen.read_seventeen_prefix(path)

    def test_public_fields_exclude_private_task_material(self):
        self.assertFalse({'task_id', 'quote', 'sku', 'email', 'credential'} &
                         seventeen.PUBLIC_FIELDS)
        report = {name: 0 for name in seventeen.PUBLIC_FIELDS}
        self.assertIn('0 official final tasks admitted',
                      seventeen.render_markdown(report))
        report['task_id'] = 'private'
        with self.assertRaises(seventeen.AUDIT_ERROR):
            seventeen.render_markdown(report)

    @unittest.skipUnless(os.getenv('MAGENTO_V4_PRIVATE_REPO_ROOT'),
                         'private original-source replay is opt-in')
    def test_private_seventeen_replays_and_process_tamper_fails(self):
        root = Path(os.environ['MAGENTO_V4_PRIVATE_REPO_ROOT'])
        run = root / first.RUN_REL
        report = seventeen.audit_seventeen(root, run)
        self.assertEqual(report['completed_distinct_candidate_controls'], 17)
        self.assertEqual(report['successful_step_process_receipts_reopened'], 221)
        original = first.read_json

        def altered(path):
            value, digest = original(path)
            if path.name == 'positive-prepare-process.private.json' and \
                    'case-016-attempt-0' in str(path):
                value = {**value, 'exit_code': 1}
            return value, digest

        with mock.patch.object(first, 'read_json', side_effect=altered):
            with self.assertRaises(seventeen.AUDIT_ERROR):
                seventeen.audit_seventeen(root, run)


if __name__ == '__main__':
    unittest.main()
