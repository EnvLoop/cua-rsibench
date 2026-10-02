"""Regression reaches inherited execute after a durable new intent is written."""
import json
import os
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from native_desktop_factory import selection_control_accounting_epoch_v13 as epoch
from native_desktop_factory import selection_control_accounting_worker_v13 as worker
from native_desktop_factory import v066_post_enter_control_attempt_v9 as core_worker
from native_desktop_factory.factory import digest
from tests.test_native_desktop_selection_worker_v066 import source_case


def intent(root, lease=1200):
    path = root / 'fixture/positive/intent.json'
    epoch.accounting._write_new(path, {'schema': 'cua-native-test-intent', 'lease_seconds': lease, 'source_epoch': root.name})
    return path


class AccountingTests(unittest.TestCase):
    def test_projection_preserves_ancestor_totals_and_counts_closed_child_in_current_history(self):
        with TemporaryDirectory() as tmp:
            broad = Path(tmp); past = broad / 'past'; old = broad / 'v10'; closed = broad / 'v12'; own = broad / 'v13'
            intent(past, 600)
            old_expected = epoch.ORIGINAL_ACCOUNTING([broad], exclude=old)
            intent(old)
            parent_expected = epoch.ORIGINAL_ACCOUNTING([broad], exclude=closed)
            intent(closed); intent(own)
            self.assertNotEqual(epoch.ORIGINAL_ACCOUNTING([broad], exclude=old), old_expected)
            with epoch.ancestor_history((closed, own)):
                self.assertEqual(epoch.accounting.lease_accounting([broad], exclude=old), old_expected)
                self.assertEqual(epoch.accounting.lease_accounting([broad], exclude=closed), parent_expected)
            current = epoch.ORIGINAL_ACCOUNTING([broad], exclude=own)
            self.assertEqual(current['past_full_lease_intents'], 3)
            self.assertEqual(current['past_full_lease_seconds'], 3000)
            before = epoch.metadata_manifest([broad], exclude=own)
            intent(broad / 'v13-unrelated', 600)
            self.assertNotEqual(epoch.metadata_manifest([broad], exclude=own), before)

    def test_excluded_current_metadata_does_not_hide_a_historical_mutation(self):
        with TemporaryDirectory() as tmp:
            broad = Path(tmp); past = broad / 'past'; closed = broad / 'v12'; own = broad / 'v13'
            old = intent(past, 600); expected = epoch.ORIGINAL_ACCOUNTING([broad], exclude=own)
            intent(closed); intent(own)
            with epoch.ancestor_history((closed, own)):
                self.assertEqual(epoch.accounting.lease_accounting([broad]), expected)
                old.write_text(json.dumps({'schema': 'cua-native-test-intent', 'lease_seconds': 1200}))
                self.assertNotEqual(epoch.accounting.lease_accounting([broad]), expected)

    def test_disabled_entry_never_reads_private_source(self):
        with patch.object(epoch, 'validate', side_effect=AssertionError('private read')):
            with self.assertRaisesRegex(ValueError, 'disabled'):
                worker.run_trio(freeze_path=Path('/absent'), permit_path=Path('/absent'))

    def test_real_inherited_worker_appends_intent_then_validates_before_fake_e2b_boundary(self):
        with TemporaryDirectory() as tmp, ExitStack() as stack:
            broad = Path(tmp) / 'native-desktop'; broad.mkdir()
            past = broad / 'past'; old = broad / 'v10'; closed = broad / 'v12'; own = broad / 'v13'
            intent(past, 600); v10_ledger = epoch.ORIGINAL_ACCOUNTING([broad], exclude=old)
            intent(old); v12_ledger = epoch.ORIGINAL_ACCOUNTING([broad], exclude=closed); intent(closed)
            source, _neutral, _positive, oracle, extension = source_case('calc-growth')
            package = Path(tmp) / 'package'; package.mkdir(); (package / ('fixture' + extension)).write_bytes(source)
            (package / 'actor_task.txt').write_text('Offline public TRAIN fixture.')
            candidate = Path(tmp) / 'cohort'; candidate.mkdir()
            row = {'task_id': 'fixture', 'package_sha256': 'a' * 64, 'split': 'selection', 'workflow': 'calc-growth'}
            epoch.accounting._write_new(candidate / 'candidate-inventory.json', {'tasks': [row]})
            private_map = Path(tmp) / 'map.private.json'; epoch.accounting._write_new(private_map, {'variant_salt': 'fixture-' * 8})
            guest = Path(tmp) / 'guest.json'; guest.write_text('{}')
            reference = Path(tmp) / 'reference.json'; reference.write_text('{}')
            ratification = Path(tmp) / 'ratification.json'; ratification.write_text('{}')
            parent_freeze = Path(tmp) / 'parent.private.json'
            epoch.accounting._write_new(parent_freeze, {'attempts_root': str(closed)})
            old_value = {'_freeze_sha256': digest(parent_freeze.read_bytes()), 'attempts_root': str(closed),
                'source_sha256s': epoch.parent.source_hashes(), 'roster': [row], 'accounting_roots': [str(broad)],
                'candidate_root': str(candidate), 'private_map': str(private_map), 'guest_public': str(guest),
                'scoped_reference': str(reference), 'ratification': str(ratification),
                'cohort_counts': {'train': 20, 'selection': 20, 'final_candidate': 100},
                'source_family_counts': {'train': 5, 'selection': 5, 'final_candidate': 25},
                'maximum_new_full_lease_intents': 360, 'lease_seconds_each': 1200,
                'max_actor_actions': 90, 'max_actor_wall_seconds': 720, 'same_intent_replay_authorized': False}

            def ancestor_validate(_path):
                epoch.require(epoch.accounting.lease_accounting([broad], exclude=old) == v10_ledger, 'v10_historical_intents_or_lease_metadata_changed')
                epoch.require(epoch.accounting.lease_accounting([broad], exclude=closed) == v12_ledger, 'v12_history_changed')
                return old_value

            stack.enter_context(patch.object(epoch.parent, 'validate', side_effect=ancestor_validate))
            stack.enter_context(patch.object(epoch, 'terminal_forensic', return_value={'offline_fixture': True}))
            freeze = Path(tmp) / 'v13.private.json'; public = Path(tmp) / 'v13.public.json'
            epoch.prepare(parent_freeze=parent_freeze, dispatch_root=Path(tmp), attempts_root=own, freeze_path=freeze, public_path=public)
            frozen = epoch.validate(freeze)
            permit = Path(tmp) / 'permit.private.json'
            epoch.accounting._write_new(permit, {'schema': epoch.PERMIT_SCHEMA, 'freeze_sha256': frozen['_freeze_sha256'],
                'source_sha256s': frozen['source_sha256s'], **{k: row[k] for k in ('task_id', 'package_sha256', 'split')},
                'attempts': ['positive', 'near-miss', 'cold-reset'], 'maximum_new_intents': 3,
                'provider_active_zero_at_review': True, 'same_intent_replay_authorized': False})
            provider_calls = []
            class FakeProviderBoundary(Exception):pass
            class FakeSandbox:
                @staticmethod
                def create(**kwargs):
                    self.assertTrue((own / 'fixture/positive/intent.json').is_file())
                    self.assertTrue((own / 'fixture/positive/child-started.json').is_file())
                    epoch.validate(freeze)  # Real v13 validator after inherited execute has appended metadata.
                    provider_calls.append(kwargs)
                    raise FakeProviderBoundary()
            stack.enter_context(patch.dict(os.environ, {'E2B_API_KEY': 'fixture-only'}))
            stack.enter_context(patch.dict('sys.modules', {'e2b_desktop': SimpleNamespace(Sandbox=FakeSandbox)}))
            stack.enter_context(patch.object(core_worker.admit, '_package', return_value=(package, source, oracle)))
            stack.enter_context(patch.object(core_worker, 'validate_reference', return_value=({'applications': {'calc': 'b' * 64}}, 'b' * 64)))
            stack.enter_context(patch.object(core_worker, 'storage_audit', return_value={'dispatch_storage_ready': True}))
            stack.enter_context(patch.object(core_worker.importlib.metadata, 'version', side_effect=lambda name:
                        {'e2b-desktop': '2.2.0', 'e2b': '2.51.0', 'Pillow': '11.3.0'}[name]))
            stack.enter_context(patch('native_desktop_factory.reconcile_interrupted_sweep.active_hashes', return_value=([], 0)))
            with self.assertRaisesRegex(ValueError, 'no subsequent create or replay'):
                worker.run_trio(freeze_path=freeze, permit_path=permit, enable_paid_controls=True)
            receipt = json.loads((own / 'fixture/positive/receipt.json').read_bytes())
            self.assertEqual(receipt['error_type'], 'FakeProviderBoundary')
            self.assertEqual(len(provider_calls), 1)
            self.assertEqual(len(list(own.glob('*/*/intent.json'))), 1)
            self.assertEqual(epoch.validate(freeze)['historical_full_lease_accounting']['past_full_lease_intents'], 3)
            previous = next(iter(frozen['historical_metadata_sha256s']))
            Path(previous).write_bytes(Path(previous).read_bytes() + b' ')
            with self.assertRaises(ValueError):epoch.validate(freeze)


if __name__ == '__main__':unittest.main()
