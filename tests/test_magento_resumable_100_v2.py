"""Fail-closed offline tests for the pre-result Magento v2 campaign ledger."""

from __future__ import annotations

import json
from datetime import datetime, timezone
import stat
import subprocess
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
import unittest

from tools import magento_resumable_100_v2 as v2


def cases() -> list[dict]:
    return [{'task_id': f'opaque-{index:03d}',
             'package_sha256': f'{index + 1:064x}'} for index in range(100)]


class MagentoResumable100Tests(unittest.TestCase):
    def test_v2_freeze_refuses_missing_or_changed_public_pre_result_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            private = root / 'work'
            private.mkdir()
            path = private / 'freeze.private.json'
            frozen = {'schema': v2.SCHEMA, 'model_calls': 0,
                      'official_final_admitted': 0,
                      'parent_cron_freeze_sha256': 'p',
                      'parent_runtime_fingerprint_sha256': 'r',
                      'ordered_task_identity_sha256': 'i'}
            digest = v2.private_new(path, frozen)
            public_path = root / v2.PUBLIC_FREEZE.relative_to(v2.ROOT)
            with (patch.object(v2, 'build_freeze', return_value=frozen),
                  patch.object(v2.old_contract, 'validate_freeze',
                               return_value=({}, 'p'))):
                with self.assertRaises(FileNotFoundError):
                    v2.validate_freeze(path, path, path, 'q', path,
                                       root=root)
                public_path.parent.mkdir(parents=True)
                v2.private_new(public_path, {
                    'schema': 'envloop-magento-resumable-100-freeze-public-v2',
                    'private_freeze_sha256': digest,
                    'parent_cron_freeze_sha256': 'p',
                    'runtime_fingerprint_sha256': 'r',
                    'plan_sha256': 'q',
                    'ordered_task_identity_sha256': 'i',
                    'study_wide_infrastructure_retry_cap': v2.RETRY_CAP,
                    'model_calls': 0, 'official_final_admitted': 0})
                self.assertEqual(v2.validate_freeze(path, path, path, 'q',
                                                    path, root=root)[2], digest)
                public = json.loads(public_path.read_text())
                public['private_freeze_sha256'] = 'changed'
                public_path.write_text(json.dumps(public))
                with self.assertRaisesRegex(ValueError, 'published'):
                    v2.validate_freeze(path, path, path, 'q', path,
                                       root=root)

    def test_chained_journal_is_append_only_and_detects_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            journal = Path(temporary) / 'events.private.jsonl'
            v2.append_event(journal, {'event': 'run_started'})
            v2.append_event(journal, {'event': 'case_attempt_started',
                                      'index': 0, 'attempt': 0})
            self.assertEqual([row['sequence'] for row in
                              v2.read_journal(journal)], [0, 1])
            self.assertEqual(stat.S_IMODE(journal.stat().st_mode), 0o600)
            raw = journal.read_bytes().replace(b'run_started', b'run_stopped')
            journal.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, 'chain'):
                v2.read_journal(journal)

    def test_exact_order_and_retry_limits_reject_extra_or_skipped_cases(self):
        source = cases()
        header = [{'event': 'run_started'}]
        for index in range(100):
            header += [{'event': 'case_attempt_started', 'index': index,
                        'attempt': 0, **source[index]},
                       {'event': 'case_completed', 'index': index,
                        'attempt': 0}]
        v2.validate_case_sequence(header, source)
        duplicate = header + [{'event': 'case_attempt_started', 'index': 99,
                               'attempt': 1, **source[99]}]
        with self.assertRaisesRegex(ValueError, 'completion|attempt|later'):
            v2.validate_case_sequence(duplicate, source)
        swapped = header.copy()
        swapped[3] = {**swapped[3], 'index': 2}
        with self.assertRaises(ValueError):
            v2.validate_case_sequence(swapped, source)
        retries = header + [{'event': 'attempt_reconciled', 'index': index,
                             'attempt': 0} for index in range(21)]
        with self.assertRaisesRegex(ValueError, 'retry cap'):
            v2.validate_case_sequence(retries, source)

    def test_only_incomplete_non_gui_step_or_host_gap_can_retry(self):
        start = {'event': 'case_attempt_started', 'index': 0, 'attempt': 0}
        safe = [start,
                {'event': 'step_intent', 'step': 'positive-prepare'},
                {'event': 'step_timeout_uncertain',
                 'step': 'positive-prepare'},
                {'event': 'attempt_stopped'}]
        v2._retryable_interruption(safe)
        with self.assertRaisesRegex(ValueError, 'deterministic failure'):
            v2._retryable_interruption(safe + [
                {'event': 'step_finished', 'step': 'positive-prepare',
                 'exit_code': 1}])
        with self.assertRaisesRegex(ValueError, 'interrupted GUI'):
            v2._retryable_interruption([start,
                {'event': 'step_intent', 'step': 'positive-gui'}])
        with self.assertRaisesRegex(ValueError, 'not host loss'):
            v2._retryable_interruption([start,
                {'event': 'step_intent', 'step': 'positive-gui'},
                {'event': 'step_finished', 'step': 'positive-gui',
                 'exit_code': 0}, {'event': 'attempt_stopped'}])
        v2._retryable_interruption([start])

    def test_only_exact_native_cms_menu_timeout_is_exception_to_nonzero_rule(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            pair = base / 'case-000/negative'
            (pair / 'neutral').mkdir(parents=True)
            (pair / 'neutral/private-before.json').write_text('{}')
            stderr = (b'Locator.click: Timeout 60000ms exceeded\n'
                      b'element is not visible\n'
                      b'data-action="item-edit"')
            (pair / 'negative-neutral-stderr.private.bin').write_bytes(stderr)
            (pair / 'negative-neutral-process.private.json').write_text(
                json.dumps({'exit_code': 1,
                            'stderr_sha256': v2.sha(stderr)}))
            events = [{'event': 'case_attempt_started'},
                      {'event': 'step_intent', 'step': 'negative-neutral'},
                      {'event': 'step_finished', 'step': 'negative-neutral',
                       'exit_code': 1, 'stderr_sha256': v2.sha(stderr)},
                      {'event': 'attempt_stopped'}]
            self.assertEqual(v2._known_neutral_timeout(base, 0, events),
                             'known_neutral_cms_menu_timeout_before_edit')
            v2._retryable_interruption(events, known_neutral_timeout=True)
            with self.assertRaisesRegex(ValueError, 'deterministic failure'):
                v2._retryable_interruption(events)
            (pair / 'neutral/private-after.json').write_text('{}')
            self.assertIsNone(v2._known_neutral_timeout(base, 0, events))
            (pair / 'neutral/private-after.json').unlink()
            page_title = (b'Locator.wait_for: Timeout 120000ms exceeded\n'
                          b'waiting for locator("h1.page-title")')
            (pair / 'negative-neutral-stderr.private.bin').write_bytes(page_title)
            (pair / 'negative-neutral-process.private.json').write_text(
                json.dumps({'exit_code': 1,
                            'stderr_sha256': v2.sha(page_title)}))
            events[2]['stderr_sha256'] = v2.sha(page_title)
            self.assertEqual(v2._known_neutral_timeout(base, 0, events),
                             'known_neutral_page_title_timeout_before_edit')

    def test_abandoned_gui_requires_terminal_driver_and_exact_material_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            pair = base / 'case-000/positive'
            pair.mkdir(parents=True)
            v2.private_new(pair / 'prepare.private.json',
                           {'train_probe_cron': {'config_sha256': 'c'}})
            v2.private_new(pair / 'seed.private.json',
                           {'task_id': 'opaque', 'page_id': 7})
            baseline = {'task_id': 'opaque', 'database': {}, 'search': {}}
            v2.private_new(pair / 'normalized-baseline.private.json', baseline)
            intents = [{'event': 'step_intent', 'step': 'positive-gui'}]
            self.assertEqual(v2._pending_gui_step(base, 0, intents),
                             'positive-gui')
            with self.assertRaisesRegex(ValueError, 'interrupted GUI'):
                v2._retryable_interruption(intents)
            v2._retryable_interruption(intents,
                                       abandoned_gui_terminal=True)
            price = {'price_rows': 8156, 'price_changed_rows': 0,
                     'price_key_sets_equal': True,
                     'live_price_sha256': 'p',
                     'replica_price_sha256': 'p'}
            with (patch.object(v2, '_live_pair', return_value=[]),
                  patch.object(v2, 'read_snapshot',
                               side_effect=[baseline, baseline]),
                  patch.object(v2, 'check_baseline'),
                  patch.object(v2.clone, 'verify_cron_never_autostarted',
                               return_value={'config_sha256': 'c'}),
                  patch.object(v2.clone, 'read_price_index_shape',
                               return_value=price),
                  patch.object(v2.time, 'sleep')):
                witness = v2._material_witness(
                    {'task_id': 'opaque'}, pair, intents,
                    exact_pre_gui=True)
            self.assertTrue(witness['material_equal_exact'])
            self.assertEqual(witness['allowed_volatile_fields'], [])
            with (patch.object(v2, '_live_pair', return_value=[]),
                  patch.object(v2, 'read_snapshot', return_value={
                      **baseline, 'changed': True}),
                  patch.object(v2, 'check_baseline')):
                with self.assertRaisesRegex(ValueError, 'exact normalized baseline'):
                    v2._material_witness({'task_id': 'opaque'}, pair, intents,
                                         exact_pre_gui=True)

    def test_live_unreceipted_preseed_can_be_audited_but_exited_pair_fails(self):
        now = time.time()
        created = datetime.fromtimestamp(now, timezone.utc).isoformat()
        app = {'Name': '/' + v2.old_sweep.APP, 'Id': 'app-id',
               'Created': created, 'Image': v2.IMAGE, 'Mounts': [],
               'State': {'Running': True}}
        search = {'Name': '/' + v2.old_sweep.SEARCH, 'Id': 'search-id',
                  'Created': created, 'Image': v2.NATIVE_SEARCH_IMAGE,
                  'Mounts': [], 'State': {'Running': True}}
        events = [{'event': 'step_intent', 'step': 'positive-prepare',
                   'time': now - 1},
                  {'event': 'step_finished', 'step': 'positive-prepare',
                   'exit_code': 1},
                  {'event': 'attempt_stopped', 'time': now + 1}]
        app_sha, search_sha = v2.sha(b'app-id'), v2.sha(b'search-id')
        catalog = {'application_clone': {'container_id_sha256': app_sha},
                   'search_sidecar_id_sha256': search_sha,
                   'search_documents_sha256': v2.old_sweep.SEARCH_SHA,
                   'search_document_count': 181}
        price = {'price_rows': 8156, 'price_key_sets_equal': True,
                 'price_changed_rows': 0, 'live_price_sha256': 'p',
                 'replica_price_sha256': 'p'}
        with (patch.object(v2, '_docker_inspect', side_effect=[app, search]),
              patch.object(v2.subprocess, 'run', return_value=
                           subprocess.CompletedProcess(['docker'], 0,
                                                       b'logs', b'')),
              patch.object(v2.clone, 'audit_existing', return_value=catalog),
              patch.object(v2.clone, 'verify_cron_never_autostarted',
                           return_value={'config_sha256': 'c'}),
              patch.object(v2.clone, 'read_price_index_shape',
                           return_value=price)):
            witness = v2._unreceipted_preseed_witness(
                'positive', events, {'runtime': {'cron_config_sha256': 'c'}})
        self.assertEqual(witness['state'],
                         'unreceipted_live_preseed_equivalent')
        self.assertEqual(len(witness['containers']), 2)
        search['State']['Running'] = False
        with patch.object(v2, '_docker_inspect', side_effect=[app, search]):
            with self.assertRaisesRegex(ValueError, 'exited/unreceipted'):
                v2._unreceipted_preseed_witness(
                    'positive', events, {'runtime': {'cron_config_sha256': 'c'}})

    def test_exact_cleanup_can_resume_after_removal_intent(self):
        with tempfile.TemporaryDirectory() as temporary:
            journal = Path(temporary) / 'journal.private.jsonl'
            row = {'name': v2.old_sweep.APP,
                   'container_id_sha256': 'a' * 64,
                   'image_sha256': 'sha256:image'}
            v2.append_event(journal, {'event': 'cleanup_step_intent',
                                      'index': 0, 'attempt': 0,
                                      'name': row['name'], 'action': 'rm',
                                      'container_id_sha256': 'a' * 64})
            with patch.object(v2, '_docker_inspect', return_value=None):
                v2._cleanup_step(journal, 0, row, 'stop')
                v2._cleanup_step(journal, 0, row, 'rm')
            self.assertEqual(len(v2.read_journal(journal)), 1)
            with self.assertRaisesRegex(ValueError, 'exact removal intent'):
                v2._cleanup_step(Path(temporary) / 'empty.private.jsonl',
                                 0, row, 'rm')

    def test_incomplete_campaign_cannot_emit_public_100_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            journal = root / 'journal.private.jsonl'
            frozen = {'parent_cron_freeze_sha256': 'p',
                      'plan_sha256': 'q',
                      'ordered_task_identity_sha256': 'r',
                      'source_commit': 's',
                      'parent_runtime_fingerprint_sha256': 't'}
            v2.append_event(journal, {'event': 'run_started',
                                      'freeze_v2_sha256': 'f',
                                      'parent_cron_freeze_sha256': 'p',
                                      'plan_sha256': 'q',
                                      'ordered_task_identity_sha256': 'r',
                                      'source_commit': 's',
                                      'runtime_fingerprint_sha256': 't',
                                      'model_calls': 0,
                                      'official_final_admitted': 0})
            with (patch.object(v2, 'validate_freeze', return_value=(
                    frozen, {'runtime_fingerprint_sha256': 't'}, 'f')),
                  patch.object(v2, 'validate_plan', return_value=cases())):
                with self.assertRaisesRegex(ValueError, '100 distinct'):
                    v2.audit_campaign(root, 'q', root, root, root, root)

    def test_resume_skips_99_completed_cases_and_runs_only_original_last_id(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            private = root / 'work'
            private.mkdir()
            run = private / 'campaign'
            run.mkdir()
            journal = run / 'journal.private.jsonl'
            frozen = {
                'parent_cron_freeze_sha256': 'p',
                'plan_sha256': 'q',
                'ordered_task_identity_sha256': 'r',
                'source_commit': 's',
                'parent_runtime_fingerprint_sha256': 't',
            }
            v2.append_event(journal, {'event': 'run_started',
                                      'freeze_v2_sha256': 'f',
                                      'parent_cron_freeze_sha256': 'p',
                                      'plan_sha256': 'q',
                                      'ordered_task_identity_sha256': 'r',
                                      'source_commit': 's',
                                      'runtime_fingerprint_sha256': 't',
                                      'model_calls': 0,
                                      'official_final_admitted': 0})
            for index, case in enumerate(cases()[:99]):
                v2.append_event(journal, {'event': 'case_attempt_started',
                                          'index': index, 'attempt': 0, **case})
                v2.append_event(journal, {'event': 'case_completed',
                                          'index': index, 'attempt': 0,
                                          'calibration_sha256': 'd'})
            called = []

            def fake_task(index, case, *args, **kwargs):
                called.append((index, case['task_id']))
                v2.old_sweep.append_event(journal, {
                    'event': 'pair_cleanup_verified', 'index': index,
                    'pair': 'positive'})
                v2.old_sweep.append_event(journal, {
                    'event': 'pair_cleanup_verified', 'index': index,
                    'pair': 'negative'})
                v2.old_sweep.append_event(journal, {
                    'event': 'task_gui_calibrated', 'index': index,
                    'task_id': case['task_id'], 'receipt_sha256': 'd'})

            with (patch.object(v2, 'ROOT', root),
                  patch.object(v2, 'validate_freeze', return_value=(
                      frozen, {'runtime_fingerprint_sha256': 't'}, 'f')),
                  patch.object(v2, 'validate_plan', return_value=cases()),
                  patch.object(v2, 'verify_finished_attempt',
                               return_value='d'),
                  patch.object(v2, '_lock', return_value=1),
                  patch.object(v2, '_unlock'),
                  patch.object(v2, '_check_single_dispatch'),
                  patch.object(v2.old_sweep, 'assert_absent'),
                  patch.object(v2.old_sweep, 'task', side_effect=fake_task)):
                outcome = v2.run_campaign(private, 'q', private, private,
                                          private, run, resume=True)
            self.assertEqual(called, [(99, 'opaque-099')])
            self.assertEqual(outcome['official_final_admitted'], 0)
            self.assertEqual(v2.read_journal(journal)[-1]['event'],
                             'run_completed')

    def test_cleanup_receipt_can_recover_missing_last_journal_event(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / 'campaign'
            run.mkdir()
            journal = run / 'journal.private.jsonl'
            frozen = {'parent_cron_freeze_sha256': 'p',
                      'plan_sha256': 'q',
                      'ordered_task_identity_sha256': 'r',
                      'source_commit': 's',
                      'parent_runtime_fingerprint_sha256': 't'}
            v2.append_event(journal, {'event': 'run_started',
                                      'freeze_v2_sha256': 'f',
                                      'parent_cron_freeze_sha256': 'p',
                                      'plan_sha256': 'q',
                                      'ordered_task_identity_sha256': 'r',
                                      'source_commit': 's',
                                      'runtime_fingerprint_sha256': 't',
                                      'model_calls': 0,
                                      'official_final_admitted': 0})
            v2.append_event(journal, {'event': 'case_attempt_started',
                                      'index': 0, 'attempt': 0, **cases()[0]})
            attempt = v2.attempt_dir(run, 0, 0)
            witness = {'active_pair': None}
            audit = {'classification':
                     'host_or_step_timeout_pre_gui_no_process_failure',
                     'material_witness': witness}
            audit_sha = v2.private_new(attempt / 'reconciliation-audit.private.json',
                                       audit)
            intent_sha = v2.private_new(attempt / 'reconciliation-intent.private.json',
                                        {'material_witness': witness})
            v2.private_new(attempt / 'reconciliation.private.json', {
                'schema': 'envloop-magento-resumable-cleanup-private-v2',
                'case_index': 0, 'task_id': cases()[0]['task_id'],
                'package_sha256': cases()[0]['package_sha256'],
                'plan_sha256': 'q', 'freeze_v2_sha256': 'f',
                'audit_sha256': audit_sha,
                'cleanup_intent_sha256': intent_sha,
                'material_witness': witness,
                'both_containers_absent': True,
                'model_calls': 0, 'official_final_admitted': 0})
            with (patch.object(v2, 'validate_freeze', return_value=(
                    frozen, {}, 'f')),
                  patch.object(v2, 'validate_plan', return_value=cases()),
                  patch.object(v2, '_lock', return_value=1),
                  patch.object(v2, '_unlock'),
                  patch.object(v2.old_sweep, 'assert_absent')):
                response = v2.reconcile_attempt(root, 'q', root, root, root,
                                                run, mode='cleanup')
            self.assertEqual(response['official_final_admitted'], 0)
            self.assertEqual(v2.read_journal(journal)[-1]['event'],
                             'attempt_reconciled')


if __name__ == '__main__':
    unittest.main()
