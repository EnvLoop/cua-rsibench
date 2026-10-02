"""Tamper tests for the read-only, two-case Magento v4 audit."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from tools import audit_magento_v4_partial_batch_20260929 as audit
from tools import magento_clean_100_v4 as v4


def fixture() -> tuple[list[dict], list[dict], dict]:
    cases = [{'task_id': f'private-task-{n}',
              'package_sha256': f'{n + 1:064x}'} for n in range(100)]
    freeze = {'plan_sha256': 'a' * 64,
              'parent_v3_freeze_sha256': 'b' * 64,
              'ordered_task_identity_sha256': v4.case_identity_digest(cases),
              'source_commit': 'c' * 40}
    rows = [{'event': 'step_intent'} for _ in range(79)]
    rows[0] = {'event': 'run_started', 'freeze_v4_sha256': 'd' * 64,
               'plan_sha256': freeze['plan_sha256'],
               'ordered_task_identity_sha256':
               freeze['ordered_task_identity_sha256'],
               'source_commit': freeze['source_commit'],
               'model_calls': 0, 'official_final_admitted': 0}
    rows[1] = {'event': 'dispatch_started', 'max_cases': 2,
               'completed_before_dispatch': 0,
               'freeze_v4_sha256': 'd' * 64, 'model_calls': 0,
               'official_final_admitted': 0, 'sequence': 1}
    for number, (index, attempt) in ((2, (0, 0)), (16, (0, 1)),
                                     (47, (1, 0))):
        rows[number] = {'event': 'case_attempt_started', 'index': index,
                        'attempt': attempt, 'task_id': cases[index]['task_id'],
                        'package_sha256': cases[index]['package_sha256'],
                        'model_calls': 0, 'official_final_admitted': 0}
    rows[5] = {'event': 'attempt_stopped', 'index': 0, 'attempt': 0,
               'model_calls': 0, 'official_final_admitted': 0}
    rows[15] = {'event': 'attempt_reconciled', 'index': 0, 'attempt': 0,
                'model_calls': 0, 'official_final_admitted': 0}
    for number, (index, attempt, receipt) in ((46, (0, 1, 'e' * 64)),
                                               (77, (1, 0, 'f' * 64))):
        rows[number] = {'event': 'case_completed', 'index': index,
                        'attempt': attempt, 'calibration_sha256': receipt,
                        'model_calls': 0, 'official_final_admitted': 0}
    completed_receipts = ['e' * 64, 'f' * 64]
    rows[78] = {
        'event': 'chunk_completed', 'max_cases': 2, 'dispatch_sequence': 1,
        'freeze_v4_sha256': 'd' * 64,
        'parent_v3_freeze_sha256': freeze['parent_v3_freeze_sha256'],
        'completed_distinct_cases': 2, 'newly_completed_this_dispatch': 2,
        'ordered_completed_task_identity_sha256':
            v4.case_identity_digest(cases[:2]),
        'completed_calibration_receipts_sha256':
            audit.sha(('\n'.join(completed_receipts) + '\n').encode()),
        'journal_prefix_sha256':
            audit.sha(b''.join(audit.canonical(row) for row in rows[:78])),
        'infrastructure_retries': 1,
        'model_calls': 0, 'official_final_admitted': 0,
    }
    return rows, cases, freeze


def journal_bytes(rows: list[dict]) -> bytes:
    prior = '0' * 64
    raw = b''
    for number, item in enumerate(rows):
        item = {**item, 'schema': v4.JOURNAL_SCHEMA,
                'sequence': number, 'previous_line_sha256': prior}
        line = audit.canonical(item)
        raw += line
        prior = audit.sha(line)
    return raw


class MagentoV4PartialAuditTest(unittest.TestCase):
    def test_exact_two_case_receipt_passes(self):
        rows, cases, freeze = fixture()
        result = audit.check_chunk(rows, cases, freeze, 'd' * 64)
        self.assertEqual(len(result['completed']), 2)
        self.assertEqual(len(result['reconciled']), 1)

    def test_chunk_count_and_hash_tampering_rejected(self):
        rows, cases, freeze = fixture()
        for key, value in (('completed_distinct_cases', 3),
                           ('journal_prefix_sha256', '0' * 64),
                           ('infrastructure_retries', 0),
                           ('completed_calibration_receipts_sha256', '0' * 64)):
            with self.subTest(key=key):
                altered = copy.deepcopy(rows)
                altered[-1][key] = value
                with self.assertRaises(audit.AuditError):
                    audit.check_chunk(altered, cases, freeze, 'd' * 64)

    def test_attempt_reordering_and_model_call_tampering_rejected(self):
        rows, cases, freeze = fixture()
        altered = copy.deepcopy(rows)
        altered[16]['attempt'] = 0
        with self.assertRaises(audit.AuditError):
            audit.check_chunk(altered, cases, freeze, 'd' * 64)
        altered = copy.deepcopy(rows)
        altered[46]['model_calls'] = 1
        with self.assertRaises(audit.AuditError):
            audit.check_chunk(altered, cases, freeze, 'd' * 64)

    def test_append_only_chain_detects_mutation_or_truncation(self):
        rows, _, _ = fixture()
        raw = journal_bytes(rows)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'journal.private.jsonl'
            path.write_bytes(raw)
            self.assertEqual(len(audit.read_journal_prefix(path)[0]), 79)
            lines = raw.splitlines(keepends=True)
            lines[5] = lines[5].replace(b'attempt_stopped', b'attempt_started')
            path.write_bytes(b''.join(lines))
            with self.assertRaises(audit.AuditError):
                audit.read_journal_prefix(path)
            path.write_bytes(raw[:-1])
            with self.assertRaises(audit.AuditError):
                audit.read_journal_prefix(path)

    def test_docker_absence_is_read_only_and_fails_closed(self):
        seen = []

        def missing(argv, **kwargs):
            seen.append(argv)
            return subprocess.CompletedProcess(
                argv, 1, '[]\n',
                f'Error response from daemon: No such container: {argv[-1]}\n')

        with mock.patch.object(audit.subprocess, 'run', side_effect=missing):
            self.assertTrue(audit.assert_disposable_pair_absent())
        self.assertEqual(len(seen), 2)
        self.assertTrue(all(command[3:5] == ['container', 'inspect']
                            for command in seen))
        with mock.patch.object(audit.subprocess, 'run', return_value=
                               subprocess.CompletedProcess([], 0, '[{}]', '')):
            with self.assertRaises(audit.AuditError):
                audit.assert_disposable_pair_absent()
        with mock.patch.object(audit.subprocess, 'run', return_value=
                               subprocess.CompletedProcess([], 1, '',
                                                           'daemon unavailable')):
            with self.assertRaises(audit.AuditError):
                audit.assert_disposable_pair_absent()

    def test_public_field_allowlist_has_no_private_task_or_quote(self):
        self.assertFalse({'task_id', 'quote', 'sku', 'email', 'credential'} &
                         audit.PUBLIC_FIELDS)
        report = {name: 0 for name in audit.PUBLIC_FIELDS}
        markdown = audit.render_markdown(report)
        self.assertIn('0 official final tasks admitted', markdown)
        report['task_id'] = 'leak'
        with self.assertRaises(audit.AuditError):
            audit.render_markdown(report)

    @unittest.skipUnless(os.getenv('MAGENTO_V4_PRIVATE_REPO_ROOT'),
                         'private source-bound first chunk opt-in')
    def test_private_run_replays_and_saved_snapshot_tamper_fails(self):
        root = Path(os.environ['MAGENTO_V4_PRIVATE_REPO_ROOT'])
        run = root / audit.RUN_REL
        result = audit.audit_partial(root, run)
        self.assertEqual(result['completed_distinct_candidate_controls'], 2)
        original = audit.read_json

        def altered(path):
            value, digest = original(path)
            if (path.name == 'private-after.json' and
                    path.parent.name == 'gui-positive' and
                    'case-000-attempt-1' in str(path)):
                value = copy.deepcopy(value)
                value['database']['quote']['content_sha256'] = '0' * 64
            return value, digest

        with mock.patch.object(audit, 'read_json', side_effect=altered):
            with self.assertRaises(audit.AuditError):
                audit.audit_partial(root, run)


if __name__ == '__main__':
    unittest.main()
