"""Offline real inherited entry, immutable ancestry and bounded SDK streams."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from native_desktop_factory import bounded_guest_transport_v17 as transfer
from native_desktop_factory import selection_control_bounded_epoch_v17 as epoch
from native_desktop_factory import selection_control_bounded_worker_v17 as worker
from native_desktop_factory import selection_control_structural_epoch_v16 as v16
from native_desktop_factory import selection_control_accounting_epoch_v13 as history
from native_desktop_factory import v066_post_enter_control_attempt_v9 as core
from native_desktop_factory import model_transport_integration_v11 as integration
from native_desktop_factory import uniform_model_transport_v11 as model
from native_desktop_factory.factory import digest
from tests.test_structural_guest_attestation_v16 import fixture
from tests.test_desktop_ancestor_accounting_v13 import intent
from tests.test_native_desktop_selection_worker_v066 import source_case


class Stream:
    def __init__(self, chunks=(), error=None):
        self.chunks = chunks; self.error = error; self.closed = 0; self.iterations = 0
    def __enter__(self):return self
    def __exit__(self, *args):self.closed += 1
    def __iter__(self):
        self.iterations += 1
        yield from self.chunks
        if self.error:raise self.error


class TransferTests(unittest.TestCase):
    def test_one_stream_exact_bytes_and_every_other_file_call_forwarded(self):
        stream = Stream([b'a', b'b']); raw = Mock(); raw.read.return_value = stream
        files = transfer.BoundedFiles(raw)
        self.assertEqual(files.read(transfer.MANIFEST_PATH, format='bytes'), bytearray(b'ab'))
        raw.read.assert_called_once_with(transfer.MANIFEST_PATH, format='stream', request_timeout=180.0)
        self.assertEqual(stream.closed, 1)
        for path, args, kwargs in [('/home/user/file.xlsx', ('bytes', 'fixture'), {'request_timeout': 12}),
                                  (transfer.MANIFEST_PATH, (), {'format': 'stream', 'gzip': True}),
                                  (transfer.MANIFEST_PATH, (), {})]:
            raw.read.reset_mock(); sentinel = object(); raw.read.return_value = sentinel
            self.assertIs(files.read(path, *args, **kwargs), sentinel)
            raw.read.assert_called_once_with(path, *args, **kwargs)
        files.write('/tmp/script.py', b'original'); raw.write.assert_called_once_with('/tmp/script.py', b'original')

    def test_positional_stream_override_preserves_user_and_gzip(self):
        raw = Mock(); stream = Stream([b'ok']); raw.read.return_value = stream
        self.assertEqual(transfer.BoundedFiles(raw).read(transfer.MANIFEST_PATH, 'bytes', 'user', 12, True), b'ok')
        raw.read.assert_called_once_with(transfer.MANIFEST_PATH, 'stream', 'user', 180.0, True)
        self.assertEqual(stream.closed, 1)

    def test_overflow_closes_once_with_one_request_and_no_retry(self):
        raw = Mock(); stream = Stream([b'a' * transfer.MAX_COMPRESSED_BYTES, b'b']); raw.read.return_value = stream
        with self.assertRaisesRegex(ValueError, 'compressed_manifest_bound'):
            transfer.BoundedFiles(raw).read(transfer.MANIFEST_PATH, format='bytes')
        self.assertEqual(raw.read.call_count, 1); self.assertEqual(stream.closed, 1)

    def test_acquisition_and_iteration_monotonic_expiration_close(self):
        for times in ([0, 180], [0, 1, 180], [0, 1, 2, 180]):
            raw = Mock(); stream = Stream([b'a']); raw.read.return_value = stream
            with patch.object(transfer.time, 'monotonic', side_effect=times):
                with self.assertRaisesRegex(TimeoutError, 'wall_bound'):
                    transfer.BoundedFiles(raw).read(transfer.MANIFEST_PATH, format='bytes')
            self.assertEqual(raw.read.call_count, 1); self.assertEqual(stream.closed, 1)

    def test_stream_error_or_invalid_chunk_close_without_replay(self):
        for stream, error in [(Stream([b'a'], error=OSError()), OSError), (Stream(['bad']), TypeError)]:
            raw = Mock(); raw.read.return_value = stream
            with self.assertRaises(error):transfer.BoundedFiles(raw).read(transfer.MANIFEST_PATH, format='bytes')
            self.assertEqual(raw.read.call_count, 1); self.assertEqual(stream.closed, 1)
        raw = Mock(); raw.read.side_effect = TimeoutError()
        with self.assertRaises(TimeoutError):transfer.BoundedFiles(raw).read(transfer.MANIFEST_PATH, format='bytes')
        self.assertEqual(raw.read.call_count, 1)

    def test_all_five_actual_model_guest_creates_share_recipe_and_source_binding(self):
        creates = []; reads = []
        class FakeSandbox:
            @staticmethod
            def create(**kwargs):
                creates.append(kwargs)
                files = Mock(); files.read.side_effect = lambda *a, **kw: (reads.append((a, kw)) or Stream([b'fixture']))
                return SimpleNamespace(files=files, commands=Mock(), get_info=Mock(return_value='shape'),
                                       is_running=Mock(return_value=False), kill=Mock(return_value=True))
        with TemporaryDirectory() as tmp, patch.dict('sys.modules', {'e2b_desktop': SimpleNamespace(Sandbox=FakeSandbox)}):
            for slot in ['shared-base', *integration.matrix.RESEARCHERS]:
                out = Path(tmp) / slot / 'actor'; out.mkdir(parents=True)
                guest = model.create_guest(root=Path(tmp), out=out, filename='fixture.xlsx')
                self.assertEqual(guest.sandbox.files.read(transfer.MANIFEST_PATH, format='bytes'), b'fixture')
                self.assertEqual(guest.sandbox.get_info(request_timeout=12), 'shape')
                self.assertFalse(guest.sandbox.is_running(request_timeout=12))
                guest.sandbox.raw.get_info.assert_called_once_with(request_timeout=30.0)
                guest.sandbox.raw.is_running.assert_called_once_with(request_timeout=30.0)
        self.assertEqual(len(creates), 5); self.assertTrue(all(c['timeout'] == 1200 for c in creates))
        self.assertTrue(all(kw == {'format': 'stream', 'request_timeout': 180.0} for _a, kw in reads))
        proposal = integration.proposal()
        self.assertEqual(proposal['bounded_guest_transport_recipe'], transfer.RECIPE)
        self.assertEqual(proposal['bounded_guest_transport_source_sha256'], digest(Path(transfer.__file__).read_bytes()))
        self.assertEqual(proposal['configuration_owners'], ['shared-base', *integration.matrix.RESEARCHERS])
        self.assertEqual(proposal['max_actor_wall_seconds'], 720)

    def test_uncertain_model_cleanup_consumes_one_kill_and_status_for_every_slot(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for slot in ['shared-base', *integration.matrix.RESEARCHERS]:
                out = root / slot / 'actor'; out.mkdir(parents=True)
                raw = SimpleNamespace(files=Mock(), commands=Mock(), kill=Mock(return_value=True),
                                      is_running=Mock(side_effect=TimeoutError()))
                guest = model.ModelGuest(transfer.BoundedSandbox(raw), root=root, out=out, filename='fixture.xlsx')
                self.assertFalse(guest.close()); self.assertFalse(guest.close())
                raw.kill.assert_called_once_with(); raw.is_running.assert_called_once_with(request_timeout=30.0)
                self.assertEqual(guest.receipt['kill_error_type'], 'TimeoutError')
                self.assertTrue(guest.close_attempted)

    def test_nested_parent_projection_excludes_only_new_root_and_retains_v16_lease(self):
        with TemporaryDirectory() as tmp:
            broad = Path(tmp); past = broad / 'past'; closed13 = broad / 'v13'; closed16 = broad / 'v16'; own = broad / 'v17'
            intent(past, 600); intent(closed13)
            old16_manifest = history.metadata_manifest([broad], exclude=closed16)
            old16_ledger = history.ORIGINAL_ACCOUNTING([broad], exclude=closed16)
            old13_manifest = history.metadata_manifest([broad], exclude=closed13)
            old13_ledger = history.ORIGINAL_ACCOUNTING([broad], exclude=closed13)
            prior = intent(closed16); prior_bytes = prior.read_bytes(); intent(own)
            with epoch.parent_history(own):
                self.assertEqual(v16.ORIGINAL_ACCOUNTING([broad], exclude=closed16), old16_ledger)
                self.assertEqual(v16.ORIGINAL_MANIFEST([broad], exclude=closed16), old16_manifest)
                with v16.parent_history(closed16):
                    self.assertEqual(history.ORIGINAL_ACCOUNTING([broad], exclude=closed13), old13_ledger)
                    self.assertEqual(history.metadata_manifest([broad], exclude=closed13), old13_manifest)
            current = epoch.ORIGINAL_ACCOUNTING([broad], exclude=own)
            self.assertEqual(current['past_full_lease_intents'], 3); self.assertEqual(current['past_full_lease_seconds'], 3000)
            manifest = epoch.ORIGINAL_MANIFEST([broad], exclude=own)
            self.assertEqual(manifest[str(prior.resolve())], digest(prior_bytes))
            prior.write_bytes(prior_bytes + b' ')
            self.assertNotEqual(epoch.ORIGINAL_MANIFEST([broad], exclude=own), manifest)

    def test_disabled_entry_precedes_private_reads(self):
        with patch.object(epoch, 'validate', side_effect=AssertionError('No private read')):
            with self.assertRaisesRegex(ValueError, 'disabled'):
                worker.run_trio(freeze_path=Path('/absent'), permit_path=Path('/absent'))

    def test_real_inherited_entry_creates_once_and_v16_capture_sees_bounded_inner_files(self):
        with TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp); broad = root / 'native'; broad.mkdir(); past = broad / 'past'; closed = broad / 'v16'; own = broad / 'v17'
            intent(past, 600)
            ancestor_ledger = epoch.ORIGINAL_ACCOUNTING([broad], exclude=closed)
            ancestor_manifest = epoch.ORIGINAL_MANIFEST([broad], exclude=closed)
            source, _neutral, _positive, oracle, extension = source_case('calc-growth')
            package = root / 'package'; package.mkdir(); (package / ('fixture' + extension)).write_bytes(source)
            (package / 'actor_task.txt').write_text('Offline public TRAIN fixture.')
            candidate = root / 'cohort'; candidate.mkdir()
            row = {'task_id': 'fixture', 'package_sha256': 'a' * 64, 'split': 'selection', 'workflow': 'calc-growth'}
            epoch.accounting._write_new(candidate / 'candidate-inventory.json', {'tasks': [row]})
            private_map = root / 'map.private.json'; epoch.accounting._write_new(private_map, {'variant_salt': 'fixture-' * 8})
            observed, compressed, reference, _ = fixture()
            reference.update(provider_template_id='fixture', provider_envd_version='fixture', provider_shape={'vcpu': 2, 'memory_mb': 4096})
            guest = root / 'guest.json'; guest.write_text(json.dumps(reference))
            scoped = root / 'scoped.json'; scoped.write_text('{}'); ratification = root / 'ratification.json'; ratification.write_text('{}')
            stage = root / 'stage'; stage.mkdir(mode=0o700); parent_freeze = stage / 'source-freeze.private.json'
            epoch.accounting._write_new(parent_freeze, {'attempts_root': str(closed)})
            old_value = {'_freeze_sha256': digest(parent_freeze.read_bytes()), 'attempts_root': str(closed),
                'source_sha256s': v16.source_hashes(), 'roster': [row], 'accounting_roots': [str(broad)],
                'candidate_root': str(candidate), 'private_map': str(private_map), 'guest_public': str(guest),
                'scoped_reference': str(scoped), 'ratification': str(ratification), 'structural_reference_sha256': digest(guest.read_bytes()),
                'cohort_counts': {'train': 20, 'selection': 20, 'final_candidate': 100},
                'source_family_counts': {'train': 5, 'selection': 5, 'final_candidate': 25},
                'maximum_new_full_lease_intents': 360, 'lease_seconds_each': 1200,
                'max_actor_actions': 90, 'max_actor_wall_seconds': 720, 'same_intent_replay_authorized': False}
            closed_out = closed / 'fixture/positive'
            epoch.accounting._write_new(closed_out / 'intent.json', {'schema': 'cua-native-v16-test-intent', 'source_freeze_sha256': old_value['_freeze_sha256'],
                'attempt': 'positive', 'lease_seconds': 1200, 'same_intent_replay_authorized': False})
            epoch.accounting._write_new(closed_out / 'receipt.json', {'schema': 'cua-native-v16-test-receipt', 'sandbox_timeout_seconds': 1200, 'source_freeze_sha256': old_value['_freeze_sha256'],
                'stage': 'guest_content_attestation', 'error_type': 'ReadTimeout', 'actor_steps': [], 'status': 'cleanup_unverified',
                'kill_returned': True, 'is_running_after_kill': None})
            epoch.accounting._write_new(closed_out / 'guest-probe-command-v16.private.json', {'exit_code': 0, 'stdout': json.dumps(observed), 'stderr': ''})
            reconciliation = stage / 'provider-reconciliation.private.json'
            epoch.accounting._write_new(reconciliation, {'schema': 'cua-native-v16-terminal-provider-cleanup-reconciliation-v1',
                'account_running_count': 0, 'known_guest_still_active': False, 'provider_list_error_type': None,
                'new_creates': 0, 'model_calls': 0, 'original_kill_returned': True, 'original_running_confirmation': None,
                'raw_failed_receipt_sha256': digest((closed_out / 'receipt.json').read_bytes()),
                'raw_status_preserved': 'cleanup_unverified', 'same_intent_replay_authorized': False})
            closed_bytes = epoch.file_manifest(closed)
            def ancestor_validate(_path):
                epoch.require(v16.ORIGINAL_ACCOUNTING([broad], exclude=closed) == ancestor_ledger, 'v16_ancestor_lease_changed')
                epoch.require(v16.ORIGINAL_MANIFEST([broad], exclude=closed) == ancestor_manifest, 'v16_ancestor_bytes_changed')
                return old_value
            stack.enter_context(patch.object(v16, 'validate', side_effect=ancestor_validate))
            freeze = root / 'v17.private.json'; public = root / 'v17.public.json'
            epoch.prepare(parent_freeze=parent_freeze, reconciliation=reconciliation, attempts_root=own, freeze_path=freeze, public_path=public)
            frozen = epoch.validate(freeze)
            permit = root / 'permit.private.json'
            epoch.accounting._write_new(permit, {'schema': epoch.PERMIT_SCHEMA, 'freeze_sha256': frozen['_freeze_sha256'],
                'source_sha256s': frozen['source_sha256s'], 'bounded_transport_recipe': transfer.RECIPE, **{k: row[k] for k in ('task_id', 'package_sha256', 'split')},
                'attempts': ['positive', 'near-miss', 'cold-reset'], 'maximum_new_intents': 3,
                'provider_active_zero_at_review': True, 'same_intent_replay_authorized': False})
            calls = []; reads = []; streams = []; statuses = []
            class StopAfterTransfer(Exception):pass
            class Files:
                def write(self, *args, **kwargs):pass
                def read(self, path, **kwargs):
                    reads.append((path, kwargs)); stream = Stream([compressed[:10], compressed[10:]]); streams.append(stream); return stream
            class Commands:
                def run(self, command, *args, **kwargs):
                    if command == 'sudo -n python3 /tmp/native-guest-content-probe-v066.py':
                        assert kwargs == {'timeout': 450, 'request_timeout': 480}
                        return SimpleNamespace(exit_code=0, stdout=json.dumps(observed), stderr='')
                    raise StopAfterTransfer()
            class Guest:
                sandbox_id = 'offline-fixture'
                files = Files(); commands = Commands()
                def get_info(self, **kwargs):
                    statuses.append(kwargs); return SimpleNamespace(template_id='fixture', envd_version='fixture', cpu_count=2, memory_mb=4096)
                def kill(self):return True
                def is_running(self, **kwargs):statuses.append(kwargs); return False
            class Sandbox:
                @staticmethod
                def create(**kwargs):
                    assert (own / 'fixture/positive/intent.json').is_file()
                    assert (own / 'fixture/positive/child-started.json').is_file()
                    epoch.validate(freeze); calls.append(kwargs); return Guest()
            stack.enter_context(patch.dict('sys.modules', {'e2b_desktop': SimpleNamespace(Sandbox=Sandbox)}))
            stack.enter_context(patch.dict(os.environ, {'E2B_API_KEY': 'fixture-only'}))
            stack.enter_context(patch.object(core.admit, '_package', return_value=(package, source, oracle)))
            stack.enter_context(patch.object(core, 'validate_reference', return_value=({'applications': {'calc': 'b' * 64}}, 'b' * 64)))
            stack.enter_context(patch.object(core, 'storage_audit', return_value={'dispatch_storage_ready': True}))
            stack.enter_context(patch.object(core.importlib.metadata, 'version', side_effect=lambda name:
                {'e2b-desktop': '2.2.0', 'e2b': '2.51.0', 'Pillow': '11.3.0'}[name]))
            stack.enter_context(patch('native_desktop_factory.reconcile_interrupted_sweep.active_hashes', return_value=([], 0)))
            with self.assertRaisesRegex(ValueError, 'no subsequent create or replay'):
                worker.run_trio(freeze_path=freeze, permit_path=permit, enable_paid_controls=True)
            out = own / 'fixture/positive'; receipt = json.loads((out / 'receipt.json').read_bytes())
            self.assertEqual(receipt['error_type'], 'StopAfterTransfer'); self.assertEqual(len(calls), 1)
            self.assertEqual(reads, [(transfer.MANIFEST_PATH, {'format': 'stream', 'request_timeout': 180.0})])
            self.assertEqual([s.closed for s in streams], [1]); self.assertEqual(statuses, [{'request_timeout': 30.0}] * 2)
            self.assertEqual((out / 'guest-content-files-v16.jsonl.gz').read_bytes(), compressed)
            self.assertEqual(epoch.file_manifest(closed), closed_bytes)
            self.assertEqual(epoch.validate(freeze)['historical_full_lease_accounting']['past_full_lease_seconds'], 1800)
            with self.assertRaises(ValueError):worker.run_trio(freeze_path=freeze, permit_path=permit, enable_paid_controls=True)
            self.assertEqual(len(calls), 1)
            reconciliation.write_bytes(reconciliation.read_bytes() + b' ')
            with self.assertRaises(ValueError):epoch.validate(freeze)


if __name__ == '__main__':unittest.main()
