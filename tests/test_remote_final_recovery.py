import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import prepare_remote_final_recovery as prepare
from remote_cloud_worker import read_archive, sha


class FinalEligibilityTests(unittest.TestCase):
    def evidence(self, error='ConnectError'):
        summary = {'status': 'infrastructure_error', 'score': None,
                   'tasks': [{'task': 'a', 'score': 1.0, 'error_type': None},
                             {'task': 'b', 'score': None, 'error_type': error}]}
        raw = {'a': {'exception_info': None, 'verifier_result': {'rewards': {'reward': 1.0}},
                     'verifier_environment_mode': 'separate'},
               'b': {'exception_info': {'exception_type': error, 'exception_traceback': 'e2b connectrpc transport stack'},
                     'agent_setup': {'started': True}, 'agent_execution': None}}
        return summary, raw

    def test_recorded_transport_fault_is_eligible_without_reusing_successes(self):
        summary, raw = self.evidence()
        before = copy.deepcopy(summary)
        faults = prepare.eligible_faults(summary, raw, ['a', 'b'])
        self.assertEqual(faults[0]['task'], 'b')
        self.assertEqual(summary, before)

    def test_scored_original_and_valid_astra_slot_are_never_admitted(self):
        summary, raw = self.evidence()
        summary.update(status='scored', score=.5)
        with self.assertRaisesRegex(ValueError, 'scored or unfinished'):
            prepare.eligible_faults(summary, raw, ['a', 'b'])
        with self.assertRaisesRegex(ValueError, 'only the four'):
            prepare.inspect_slot(Path('/unused'), {'label': 'astra-selected-repeat-1'})

    def test_agent_timeouts_model_budgets_and_unknown_errors_are_rejected(self):
        for error in ('AgentTimeout', 'AgentTimeoutError', 'ModelBudgetExceeded', 'CommandExitCodeError'):
            summary, raw = self.evidence(error)
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, 'not an allowed'):
                prepare.eligible_faults(summary, raw, ['a', 'b'])
        summary, raw = self.evidence('TimeoutException')
        raw['b']['exception_info']['exception_traceback'] = 'e2b transport; AgentTimeoutError'
        with self.assertRaisesRegex(ValueError, 'model-budget'):
            prepare.eligible_faults(summary, raw, ['a', 'b'])

    def test_error_needs_raw_provider_traceback_and_exact_task_set(self):
        summary, raw = self.evidence()
        raw['b']['exception_info']['exception_traceback'] = 'ordinary application error'
        with self.assertRaisesRegex(ValueError, 'provider/transport traceback'):
            prepare.eligible_faults(summary, raw, ['a', 'b'])
        summary, raw = self.evidence()
        with self.assertRaisesRegex(ValueError, 'identities'):
            prepare.eligible_faults(summary, raw, ['a', 'b', 'c'])
        raw['a']['verifier_environment_mode'] = 'shared'
        with self.assertRaisesRegex(ValueError, 'separate verifier'):
            prepare.eligible_faults(summary, raw, ['a', 'b'])


class ControllerReadinessTests(unittest.TestCase):
    def test_alias_presence_does_not_substitute_for_ready_build(self):
        runtime = {'packages': {}, 'package_sources': {}, 'python_required': '3.12', 'platform_destination': 'Linux x86_64'}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'runtime-lock.txt').write_text('frozen==1\n')
            plan = {'operational_version': prepare.VERSION, 'template': 'known-ready',
                    'requirements_sha256': prepare.file_sha(root / 'runtime-lock.txt'), 'runtime': runtime}
            (root / 'plan.json').write_text(json.dumps(plan))
            (root / 'build-result.json').write_text(json.dumps({'state': 'alias_present', 'template': 'known-ready'}))
            with self.assertRaisesRegex(ValueError, 'READY'):
                prepare.ready_controller(root, runtime)
            (root / 'build-result.json').write_text(json.dumps({'state': 'built_ready', 'template': 'known-ready'}))
            self.assertEqual(prepare.ready_controller(root, runtime)['template'], 'known-ready')
            (root / 'runtime-lock.txt').write_text('changed==2\n')
            with self.assertRaisesRegex(ValueError, 'lock changed'):
                prepare.ready_controller(root, runtime)


class PayloadTests(unittest.TestCase):
    def fixture(self, root):
        (root / 'tools').mkdir()
        (root / 'tools/run_cloud_chain.py').write_text('# frozen local launcher fixture\n')
        (root / 'tools/remote_cloud_worker.py').write_bytes(Path(prepare.__file__).with_name('remote_cloud_worker.py').read_bytes())
        package = root / 'src/cursibench'
        package.mkdir(parents=True)
        source = package / 'factory_harbor.py'
        source.write_text('# frozen actor fixture\n')
        study = root / 'study'
        for name in ('a', 'b', 'c'):
            task = study / 'sealed-final/chunk-0' / name
            task.mkdir(parents=True)
            (task / 'task.toml').write_text('fixture = true\n')
        slot = {'label': 'astra-base-repeat-1', 'execution': {'researcher': 'astra'},
                'plan': {'chunks': {'chunk-0': ['a', 'b', 'c']},
                         'binding': {'candidate': 'base', 'training_manifest': None}},
                'selected': {'model': 'Qwen/Qwen3.5-4B', 'inference_kind': 'base'},
                'proof': {'protocol_hash': 'protocol', 'checkpoint_sha256': 'checkpoint-digest',
                          'original_wrapper_hashes': {'chunk-0': 'original-wrapper'},
                          'original_plan_sha256': 'original-plan', 'original_summary_sha256': 'original-summary',
                          'task_package_hashes': {'a': 'a-hash', 'b': 'b-hash', 'c': 'c-hash'}}}
        return source, study, slot

    def test_remote_payload_preserves_full_chunk_and_explicit_non_independent_scope(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, study, slot = self.fixture(root)
            with patch.object(prepare, 'ROOT', root), patch.object(prepare, 'source_closure', return_value=[source]):
                plan = prepare.prepare_chunk(study, slot, 'chunk-0', root / 'prepared', {}, {'template': 'ready'}, 'amendment')
            data = (root / 'prepared/payload.tar.gz').read_bytes()
            manifest = json.loads(read_archive(data)['manifest.json'])
            self.assertEqual(plan['payload_sha256'], sha(data))
            self.assertEqual(manifest['task_names'], ['a', 'b', 'c'])
            self.assertEqual(manifest['fixed'], prepare.FIXED)
            self.assertEqual(manifest['final_recovery']['policy_kind'], 'full_suite_replay')
            self.assertFalse(manifest['final_recovery']['original_rows_reused'])
            self.assertFalse(manifest['final_recovery']['new_independent_repetition'])
            self.assertFalse(manifest['final_recovery']['new_research_seed'])
            self.assertFalse(plan['cloud_execution_authorized_by_this_preparation'])
            self.assertEqual(manifest['worker_sha256'], sha((root / 'prepared/worker.py').read_bytes()))

    def test_credentials_are_rejected_before_creating_payload_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, study, slot = self.fixture(root)
            source.write_text('sk-' + 'a' * 24)
            with patch.object(prepare, 'ROOT', root), patch.object(prepare, 'source_closure', return_value=[source]), self.assertRaisesRegex(ValueError, 'credential'):
                prepare.prepare_chunk(study, slot, 'chunk-0', root / 'prepared', {}, {'template': 'ready'}, 'amendment')
            self.assertFalse((root / 'prepared').exists())


if __name__ == '__main__':
    unittest.main()
