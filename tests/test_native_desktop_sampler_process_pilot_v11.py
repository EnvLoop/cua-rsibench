"""Offline uncertainty and TRAIN scope checks; no service or guest is opened."""
import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from native_desktop_factory import qwen_sampler_process_v11 as rpc
from native_desktop_factory import train_weak_base_pilot_v11 as pilot
from native_desktop_factory import model_transport_integration_v11 as integration
from native_desktop_factory import uniform_model_transport_v11 as transport
from native_desktop_factory.factory import digest


class Child:
    def __init__(self):
        self.stdin = io.StringIO(); self.stdout = io.StringIO(); self.pid = 123456
        self.returncode = None; self.terminated = False

    def poll(self):return self.returncode
    def terminate(self):self.terminated = True; self.returncode = -15
    def kill(self):self.returncode = -9
    def wait(self, timeout):return self.returncode


class FakeCleanSampler:
    def __init__(self):self.closed = []
    def start(self, **kwargs):return {'status': 'ready', 'sampling_kind': 'base'}
    def sample_rendered(self, **kwargs):return {'status': 'completed', 'new_dispatch': True, 'reused': False}
    def close(self, success):self.closed.append(success)


class ProcessPilotTests(unittest.TestCase):
    def tearDown(self):
        rpc.ACTIVE_PROCESS = None

    def test_missing_explicit_runtime_refuses_before_process_launch(self):
        with patch.object(rpc.subprocess, 'Popen', side_effect=AssertionError('Must not launch')):
            with self.assertRaises(ValueError):
                transport.ModelSampler()

    def test_timeout_consumes_private_request_and_cannot_resubmit(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); binary = root / 'work/qwen38-training-runtime/.venv/bin/python'
            binary.parent.mkdir(parents=True); binary.write_bytes(b'not executed')
            journal = root / 'sampler'; child = Child()
            with patch.object(rpc.subprocess, 'Popen', return_value=child) as launch, \
                 patch.object(rpc.select, 'select', return_value=([], [], [])):
                with patch.dict(os.environ, {'E2B_API_KEY': 'fixture-native', 'TINKER_API_KEY': 'fixture-tinker'}):
                    process = rpc.SamplerProcess(repo_root=root, journal_root=journal, plan_sha256='a' * 64)
                env = launch.call_args.kwargs['env']
                self.assertNotIn('E2B_API_KEY', env)
                self.assertEqual(env['TINKER_API_KEY'], 'fixture-tinker')
                with self.assertRaises(TimeoutError):process.call('sample', {}, timeout=.001)
                first = child.stdin.getvalue()
                with self.assertRaisesRegex(ValueError, 'uncertain'):process.call('sample', {})
                self.assertEqual(child.stdin.getvalue(), first)
                self.assertEqual(len(list(journal.glob('*.request.private.json'))), 1)
                process.close(False)
                self.assertTrue(child.terminated)
                terminal = json.loads((journal / 'child-terminal.private.json').read_bytes())
                self.assertTrue(terminal['request_acknowledgement_uncertain'])
                self.assertEqual(terminal['automatic_restarts'], 0)

    def test_provider_gate_requires_exact_live_process_root_and_plan(self):
        with self.assertRaises(ValueError):rpc.delegated_pre_dispatch(repo_root=Path('/absent'), study_plan_sha256='a' * 64)
        process = SimpleNamespace(root=Path('/fixture'), plan='a' * 64, call=Mock(return_value={'provider_calls': 0}))
        rpc.ACTIVE_PROCESS = process
        with self.assertRaises(ValueError):rpc.delegated_pre_dispatch(repo_root=Path('/fixture'), study_plan_sha256='b' * 64)
        self.assertEqual(rpc.delegated_pre_dispatch(repo_root=Path('/fixture'), study_plan_sha256='a' * 64), {'provider_calls': 0})

    def test_child_setup_failure_is_retained_and_later_command_is_not_processed(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); journal = root / 'sampler'; journal.mkdir(mode=0o700)
            requests = []
            for number, kind in enumerate(['setup', 'sample']):
                name = f'{number:03d}.request.private.json'
                checksum = rpc.write_new(journal / name, {'schema': 'cua-clean-sampler-command-v11',
                        'ordinal': number, 'kind': kind, 'plan_sha256': 'a' * 64, 'arguments': {},
                        'same_request_replay_authorized': False})
                requests.append(json.dumps({'request': name, 'sha256': checksum}) + '\n')
            fake = FakeCleanSampler(); fake.start = Mock(side_effect=TimeoutError())
            stdout = io.StringIO()
            with patch.object(transport, 'CleanRuntimeSampler', return_value=fake), \
                 patch('cursibench.full_study_qwen_runtime_gate_v1.pre_dispatch', return_value={}), \
                 patch.object(rpc.sys, 'stdin', io.StringIO(''.join(requests))), patch.object(rpc.sys, 'stdout', stdout):
                rpc.serve(root, journal, 'a' * 64)
            self.assertEqual(fake.start.call_count, 1)
            self.assertEqual(len(stdout.getvalue().splitlines()), 1)
            self.assertFalse((journal / '001.result.private.json').exists())
            failure = json.loads((journal / '000.result.private.json').read_bytes())
            self.assertEqual(failure['status'], 'failed')
            self.assertFalse(failure['same_request_replay_authorized'])

    def test_train_pilot_paid_flag_precedes_all_private_or_provider_reads(self):
        with patch.object(pilot, 'validate', side_effect=AssertionError('Private read')):
            with self.assertRaisesRegex(ValueError, 'disabled'):
                pilot.run(freeze_path=Path('/absent'), permit_path=Path('/absent'))

    def test_train_preparation_refuses_selection_before_opening_gold(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); inventory = root / 'candidate-inventory.json'
            inventory.write_text(json.dumps({'tasks': [{'task_id': 'fixture', 'split': 'selection'}]})); inventory.chmod(0o600)
            with patch.object(integration.controls, 'validate', return_value={'candidate_root': str(root)}), \
                 patch.object(pilot.admit, '_package', side_effect=AssertionError('Selection gold opened')):
                with self.assertRaisesRegex(ValueError, 'TRAIN only'):
                    pilot.prepare(control_freeze=root / 'unused', task_id='fixture', output_root=root / 'new', freeze_path=root / 'freeze')

    def test_paid_pilot_timeout_retains_intent_and_never_calls_provider_twice(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); sampler = SimpleNamespace(process=SimpleNamespace(call=Mock(return_value={})))
            freeze = {'source_sha256s': integration.proposal()['source_sha256s']}
            paid = pilot.PilotPaidCalls(freeze, root / 'paid', sampler)
            provider = Mock(side_effect=TimeoutError())
            with self.assertRaises(TimeoutError):
                paid.invoke(suffix='sample-0', category='tinker', request={}, provider=provider)
            with self.assertRaisesRegex(ValueError, 'consumed'):
                paid.invoke(suffix='sample-0', category='tinker', request={}, provider=provider)
            self.assertEqual(provider.call_count, 1)
            self.assertEqual(len(list((root / 'paid').glob('*.intent.private.json'))), 1)
            self.assertEqual(paid.calls, [])


if __name__ == '__main__':
    unittest.main()
