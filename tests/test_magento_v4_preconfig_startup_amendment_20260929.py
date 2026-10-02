"""Source-bound fail-closed checks for the v4 pre-configuration incident."""

from __future__ import annotations

from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools import magento_v4_preconfig_startup_amendment_20260929 as amendment


class PreconfigAmendmentTests(unittest.TestCase):
    def _saved_failure(self, *, step: str = 'positive-prepare',
                       include_seed: bool = False) -> None:
        with TemporaryDirectory() as raw:
            base = Path(raw)
            run = base / 'run'
            pair = run / 'attempts/case-000-attempt-0/case-000/positive'
            pair.mkdir(parents=True)
            journal = run / 'journal.private.jsonl'
            journal.write_bytes(b'frozen journal\n')
            stderr = b'Traceback\nTimeoutError: Magento HTTP did not become ready\n'
            (pair / 'positive-prepare-stderr.private.bin').write_bytes(stderr)
            process = {'stderr_sha256': hashlib.sha256(stderr).hexdigest(),
                       'exit_code': 1, 'stdout_bytes': 0}
            (pair / 'positive-prepare-process.private.json').write_text(
                json.dumps(process))
            if include_seed:
                (pair / 'seed.private.json').write_text('{}')
            events = [
                {'event': 'run_started', 'model_calls': 0,
                 'official_final_admitted': 0},
                {'event': 'dispatch_started', 'max_cases': 2,
                 'model_calls': 0, 'official_final_admitted': 0},
                {'event': 'case_attempt_started', 'index': 0, 'attempt': 0,
                 'model_calls': 0, 'official_final_admitted': 0},
                {'event': 'step_intent', 'index': 0, 'attempt': 0,
                 'step': step, 'time': 1.0},
                {'event': 'step_finished', 'index': 0, 'attempt': 0,
                 'step': step, 'exit_code': 1,
                 'stderr_sha256': hashlib.sha256(stderr).hexdigest()},
                {'event': 'attempt_stopped', 'index': 0, 'attempt': 0,
                 'error_type': 'ValueError', 'time': 2.0,
                 'model_calls': 0, 'official_final_admitted': 0},
            ]
            paths = {'run': run, 'attempt': run / 'attempts/case-000-attempt-0',
                     'journal': journal,
                     'process': pair / 'positive-prepare-process.private.json',
                     'stderr': pair / 'positive-prepare-stderr.private.bin'}
            with ExitStack() as stack:
                stack.enter_context(patch.object(amendment, '_frozen_context',
                    return_value=({}, {}, [{}] * 100)))
                stack.enter_context(patch.object(amendment, 'ORIGINAL_JOURNAL_SHA',
                    hashlib.sha256(journal.read_bytes()).hexdigest()))
                stack.enter_context(patch.object(amendment, 'ORIGINAL_JOURNAL_LENGTH',
                    len(journal.read_bytes())))
                stack.enter_context(patch.object(amendment, 'PROCESS_SHA',
                    hashlib.sha256(paths['process'].read_bytes()).hexdigest()))
                stack.enter_context(patch.object(amendment, 'STDERR_SHA',
                    hashlib.sha256(stderr).hexdigest()))
                stack.enter_context(patch.object(amendment.v4, 'read_journal',
                    return_value=events))
                for name in ('validate_run_header', 'validate_case_sequence',
                             'validate_chunk_boundaries', 'validate_attempt_inventory'):
                    stack.enter_context(patch.object(amendment.v4, name))
                if step == 'positive-prepare' and not include_seed:
                    result = amendment.classify_saved_failure(paths)
                    self.assertEqual(result['start_time'], 1.0)
                    self.assertEqual(result['stop_time'], 2.0)
                else:
                    with self.assertRaises(ValueError):
                        amendment.classify_saved_failure(paths)

    def test_exact_saved_preconfig_stop_is_classified(self) -> None:
        self._saved_failure()

    def test_different_step_is_not_classified(self) -> None:
        self._saved_failure(step='positive-seed')

    def test_any_seed_receipt_is_not_classified(self) -> None:
        self._saved_failure(include_seed=True)

    def test_only_http_health_volatility_is_ignored(self) -> None:
        first = {'containers': [{'container_id_sha256': 'a'}],
                 'sql_hashes': {'table': 'b'}, 'quote_pages': 0,
                 'http_status': '302', 'sidecar_health': 'yellow',
                 'audit_observed_time': 1.0,
                 'diagnostic_hashes': {'log': 'x'}}
        second = {**first, 'http_status': '200',
                  'sidecar_health': 'green', 'audit_observed_time': 3.0,
                  'diagnostic_hashes': {'log': 'y'}}
        self.assertEqual(amendment._stable_witness(first),
                         amendment._stable_witness(second))
        second['sql_hashes'] = {'table': 'changed'}
        self.assertNotEqual(amendment._stable_witness(first),
                            amendment._stable_witness(second))

    def test_two_readback_gate_rejects_material_change(self) -> None:
        paths = {'unused': Path('/unused')}
        first = {'containers': [{'container_id_sha256': 'a'}],
                 'sql_hashes': {'table': 'b'}}
        second = {'containers': [{'container_id_sha256': 'changed'}],
                  'sql_hashes': {'table': 'b'}}
        with patch.object(amendment, 'classify_saved_failure', return_value={}), \
             patch.object(amendment, '_live_once', side_effect=[first, second]), \
             patch.object(amendment.time, 'sleep'):
            with self.assertRaises(ValueError):
                amendment.inspect(paths)

    def test_cleanup_protocol_binds_exact_pair_before_retry_without_docker(self) -> None:
        with TemporaryDirectory() as raw:
            root = Path(raw)
            (root / 'work/magento-original').mkdir(parents=True)
            paths = amendment._paths(root)
            paths['attempt'].mkdir(parents=True)
            amendment.v4.append_event(paths['journal'], {'event': 'run_started'})
            amendment.v4.append_event(paths['journal'], {
                'event': 'case_attempt_started', 'index': 0, 'attempt': 0})
            original_prefix = paths['journal'].read_bytes()
            pair = [
                {'name': amendment.sweep.APP, 'container_id_sha256': 'a' * 64,
                 'image_sha256': amendment.IMAGE, 'mount_count': 0},
                {'name': amendment.sweep.SEARCH, 'container_id_sha256': 'b' * 64,
                 'image_sha256': amendment.NATIVE_SEARCH_IMAGE,
                 'mount_count': 0},
            ]
            witness = {'state': 'live_unseeded_preconfig_http_timeout',
                       'containers': pair, 'sql_hashes': {'table': 'c'},
                       'quote_pages': 0}
            audited = {'schema': 'envloop-magento-clean-attempt-audit-private-v4',
                       'case_index': 0, 'attempt': 0,
                       'classification': amendment.CLASSIFICATION,
                       'preconfig_amendment_freeze_sha256': 'f' * 64,
                       'journal_sha256_before_audit':
                           amendment.ORIGINAL_JOURNAL_SHA,
                       'task_id': 'private-case',
                       'package_sha256': 'd' * 64,
                       'material_witness': witness,
                       'model_calls': 0, 'official_final_admitted': 0}
            amendment.v4.private_new(paths['audit'], audited)
            operations = []

            def pretend_cleanup(journal, index, item, action):
                operations.append((index, item['name'], action))
                amendment.v4.append_event(journal, {
                    'event': 'cleanup_step_intent', 'index': index,
                    'name': item['name'], 'action': action,
                    'container_id_sha256': item['container_id_sha256']})
                amendment.v4.append_event(journal, {
                    'event': 'cleanup_step_finished', 'index': index,
                    'name': item['name'], 'action': action,
                    'container_id_sha256': item['container_id_sha256']})

            with patch.object(amendment, '_validate_source_freeze',
                              return_value='f' * 64), \
                 patch.object(amendment, 'inspect', return_value=witness), \
                 patch.object(amendment.v4, '_cleanup_step',
                              side_effect=pretend_cleanup), \
                 patch.object(amendment.sweep, 'assert_absent'):
                result = amendment.cleanup(paths)
            self.assertEqual(result['status'],
                             'exact_preconfig_pair_retired_for_one_same_id_retry')
            self.assertEqual(operations, [
                (0, amendment.sweep.APP, 'stop'),
                (0, amendment.sweep.APP, 'rm'),
                (0, amendment.sweep.SEARCH, 'stop'),
                (0, amendment.sweep.SEARCH, 'rm'),
            ])
            receipt = json.loads(paths['receipt'].read_bytes())
            intent = json.loads(paths['intent'].read_bytes())
            events = amendment.v4.read_journal(paths['journal'])
            self.assertEqual(receipt['material_witness'],
                             intent['material_witness'])
            self.assertEqual(receipt['audit_sha256'], intent['audit_sha256'])
            self.assertTrue(receipt['both_containers_absent'])
            self.assertEqual(events[-1]['classification'],
                             amendment.CLASSIFICATION)
            self.assertEqual(events[-1]['reconciliation_sha256'],
                             amendment.sha(paths['receipt'].read_bytes()))
            with ExitStack() as stack:
                stack.enter_context(patch.object(amendment,
                    '_validate_source_freeze', return_value='f' * 64))
                stack.enter_context(patch.object(amendment,
                    '_frozen_context', return_value=({}, {}, [{}] * 100)))
                stack.enter_context(patch.object(amendment,
                    'ORIGINAL_JOURNAL_LENGTH', len(original_prefix)))
                stack.enter_context(patch.object(amendment,
                    'ORIGINAL_JOURNAL_SHA', amendment.sha(original_prefix)))
                for name in ('validate_run_header', 'validate_case_sequence',
                             'validate_chunk_boundaries', 'validate_attempt_inventory'):
                    stack.enter_context(patch.object(amendment.v4, name))
                stack.enter_context(patch.object(amendment.sweep,
                    'assert_absent'))
                verified = amendment.verify_retired(paths)
            self.assertEqual(verified['status'],
                             'one_same_id_v4_retry_lineage_verified')


if __name__ == '__main__':
    unittest.main()
