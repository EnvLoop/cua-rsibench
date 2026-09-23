import copy
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import prepare_remote_factory_final as final
from cursibench.factory_campaign import CampaignRegistry, digest
from remote_cloud_worker import read_archive, sha


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2))


class InitialFinalTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.study = self.root / 'study'
        self.study.mkdir()
        write(self.study / 'manifest.json', {'researchers': {'sol6': 'gpt-6-sol', 'luna6': 'gpt-6-luna'}})
        self.tasks = ['a', 'b', 'c', 'd', 'e', 'f']
        self.chunks = {'chunk-0': self.tasks[:3], 'chunk-1': self.tasks[3:]}
        self.package_hashes = {}
        for chunk, names in self.chunks.items():
            for name in names:
                path = self.study / 'sealed-final' / chunk / name
                path.mkdir(parents=True)
                (path / 'task.toml').write_text('fixture = true\n')
                (path / 'instruction.md').write_text('Task ' + name)
                self.package_hashes[name] = digest({p.name: sha(p.read_bytes()) for p in path.iterdir()})
        (self.root / 'tools').mkdir()
        self.launcher = self.root / 'tools/run_cloud_chain.py'
        self.launcher.write_text('# immutable launcher fixture\n')
        (self.root / 'tools/remote_cloud_worker.py').write_bytes(Path(final.__file__).with_name('remote_cloud_worker.py').read_bytes())
        self.source = self.root / 'src/cursibench/factory_harbor.py'
        self.source.parent.mkdir(parents=True)
        self.source.write_text('# immutable actor fixture\n')
        self.runtime_hashes = {'tools/run_cloud_chain.py': sha(self.launcher.read_bytes()),
                               'src/cursibench/factory_harbor.py': sha(self.source.read_bytes())}
        self.extra_source = self.source.with_name('transport_fixture.py')
        self.extra_source.write_text('# source outside frozen actor overlap\n')
        write(self.root / 'docs/evidence/remote-controller-sources-v1.json', {
            'operational_version': final.VERSION,
            'worker_sha256': sha((self.root / 'tools/remote_cloud_worker.py').read_bytes()),
            'files': dict(self.runtime_hashes, **{'src/cursibench/transport_fixture.py': sha(self.extra_source.read_bytes())})})
        protocol = {'selection_tasks': ['s1', 's2', 's3'], 'final_tasks': self.tasks,
                    'max_attempts': 5, 'training_token_budget': 1048576}
        self.registries = {}
        for name in ('sol6', 'luna6'):
            registry = CampaignRegistry(self.study / (name + '-campaign.json'), protocol)
            registry.set_baseline({'status': 'scored', 'score': 0.0,
                                  'tasks': [{'task': task, 'score': 0.0, 'error_type': None} for task in protocol['selection_tasks']]})
            for number in range(1, 6):
                registry.record_submission_rejection('round-' + str(number), None, {'accepted': False})
            registry.freeze_selection('declared round limit reached')
            self.registries[name] = registry
        self.labels = ['sol6-base-repeat-1', 'sol6-base-repeat-2']
        self.comparison = {'created_at': time.time(), 'repetitions': 2,
                           'selection_frozen_at': {name: registry.snapshot()['final_selection']['frozen_at'] for name, registry in self.registries.items()},
                           'bindings': {name: self.labels for name in ('base', 'sol6', 'luna6')},
                           'executions': [{'label': label, 'researcher': 'sol6', 'role': 'base', 'repetition': i,
                                           'checkpoint_sha256': digest('Qwen/Qwen3.5-4B')} for i, label in enumerate(self.labels, 1)]}
        write(self.study / 'final-comparison.json', self.comparison)
        self.controller = {'template': 'reviewed-ready-template', 'state': 'built_ready',
                           'plan_sha256': 'template-plan', 'build_result_sha256': 'ready-result', 'requirements_sha256': 'lock'}
        for target, value in [('ROOT', self.root), ('source_closure', lambda *_: [self.source, self.extra_source]),
                              ('runtime_origin', lambda: {}), ('ready_controller', lambda *_: self.controller),
                              ('make_plan', self.fake_plan)]:
            patcher = patch.object(final, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def fake_plan(self, root, study, state, role, repetition=1):
        return {'runtime_hashes': self.runtime_hashes, 'task_package_hashes': self.package_hashes,
                'chunks': self.chunks, 'final_manifest_sha256': 'sealed-final',
                'binding': {'candidate': 'base', 'model': 'Qwen/Qwen3.5-4B', 'training_manifest': None,
                            'training_manifest_sha256': None, 'checkpoint_sha256': digest('Qwen/Qwen3.5-4B')},
                'selection': state['final_selection'], 'protocol_hash': state['protocol_hash'],
                'role': role, 'repetition': repetition, 'sampling': {'max_tokens': 512, 'temperature': 0, 'seed': 23},
                'repeat_interpretation': 'same-seed fresh-environment stability; not independent research seeds'}

    def prepare(self, labels=None):
        return final.prepare(self.study, self.root / 'template', labels)

    def set_state(self, name, change):
        state = self.registries[name].snapshot()
        change(state)
        write(self.study / (name + '-campaign.json'), state)

    def test_both_campaigns_must_be_frozen_without_reservations(self):
        self.set_state('luna6', lambda state: state.update(final_selection=None))
        with self.assertRaisesRegex(ValueError, 'all campaign selections'):
            self.prepare()
        self.assertFalse((self.study / 'final-executions').exists())

    def test_a_frozen_state_does_not_bypass_declared_stopping_or_pending_training(self):
        self.set_state('luna6', lambda state: state['attempts'].pop())
        with self.assertRaisesRegex(ValueError, 'stopping condition'):
            self.prepare()
        self.set_state('sol6', lambda state: state['reservations'].update({'pending': {'token_bound': 100}}))
        with self.assertRaisesRegex(ValueError, 'pending training'):
            self.prepare()

    def test_unknown_or_modified_comparison_slots_cannot_be_prepared(self):
        with self.assertRaisesRegex(ValueError, 'one frozen comparison'):
            self.prepare(['luna6-selected-repeat-1'])
        altered = copy.deepcopy(self.comparison)
        altered['executions'][0]['checkpoint_sha256'] = 'different'
        write(self.study / 'final-comparison.json', altered)
        with self.assertRaisesRegex(ValueError, 'comparison slots'):
            self.prepare()

    def test_initial_payloads_have_no_fabricated_recovery_history_and_plan_is_exact(self):
        with patch('e2b.Sandbox.create', side_effect=AssertionError('preparation must make no cloud calls')):
            result = self.prepare()
        self.assertEqual(result['labels'], self.labels)
        directory = self.study / 'final-executions' / self.labels[0]
        self.assertEqual(final.read(directory / 'plan.json'), self.fake_plan(self.root, self.study, self.registries['sol6'].snapshot(), 'base'))
        self.assertFalse((directory / 'started.json').exists())
        operation = final.read(directory / 'operational-plan.json')
        self.assertEqual(operation['admission_kind'], 'initial_final')
        for chunk in self.chunks:
            child = directory / chunk
            manifest = json.loads(read_archive((child / 'payload.tar.gz').read_bytes())['manifest.json'])
            self.assertEqual(manifest['admission_kind'], 'initial_final')
            self.assertNotIn('prior_execution_wrapper_sha256', manifest['model'])
            self.assertNotIn('final_recovery', manifest)
            self.assertEqual(set(manifest['initial_final']), {'logical_comparison_slot', 'chunk', 'final_comparison_sha256', 'final_plan_sha256', 'task_package_hashes'})
            self.assertEqual(manifest['task_names'], self.chunks[chunk])

    def test_preparation_resume_preserves_existing_job_ids_and_failure_evidence(self):
        self.prepare([self.labels[0]])
        directory = self.study / 'final-executions' / self.labels[0]
        original = (directory / 'chunk-0/plan.json').read_bytes()
        failure = directory / 'chunk-0/failure-evidence.json'
        failure.write_text('{"error_type":"ConnectError"}')
        (directory / 'operational-plan.json').unlink()  # interrupted publication after both child plans
        self.prepare([self.labels[0]])
        self.assertEqual((directory / 'chunk-0/plan.json').read_bytes(), original)
        self.assertEqual(failure.read_text(), '{"error_type":"ConnectError"}')
        self.prepare([self.labels[0]])
        self.assertEqual((directory / 'chunk-0/plan.json').read_bytes(), original)

    def test_unowned_existing_final_and_changed_runtime_are_rejected(self):
        directory = self.study / 'final-executions' / self.labels[0]
        directory.mkdir(parents=True)
        (directory / 'original-result.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'unowned existing'):
            self.prepare([self.labels[0]])
        self.source.write_text('# changed actor\n')
        with self.assertRaisesRegex(ValueError, 'frozen child runtime'):
            self.prepare([self.labels[1]])

    def test_source_outside_frozen_overlap_must_match_trusted_snapshot(self):
        self.extra_source.write_text('# changed transport outside actor overlap\n')
        with self.assertRaisesRegex(ValueError, 'trusted source inventory or bytes'):
            self.prepare([self.labels[0]])

    def test_extra_source_path_is_rejected(self):
        untrusted = self.source.with_name('untrusted_fixture.py')
        untrusted.write_text('# unexpected source\n')
        with patch.object(final, 'source_closure', lambda *_: [self.source, self.extra_source, untrusted]):
            with self.assertRaisesRegex(ValueError, 'trusted source inventory or bytes'):
                self.prepare([self.labels[0]])

    def test_worker_must_match_trusted_snapshot(self):
        worker = self.root / 'tools/remote_cloud_worker.py'
        worker.write_bytes(worker.read_bytes() + b'\n# changed worker\n')
        with self.assertRaisesRegex(ValueError, 'worker or version differs from trusted'):
            self.prepare([self.labels[0]])

    def collected(self, failure=False, shared_verifier=False):
        self.prepare([self.labels[0]])
        directory = self.study / 'final-executions' / self.labels[0]
        self.started = time.time()
        for chunk, names in self.chunks.items():
            evaluation = directory / chunk / 'evaluation'
            write(evaluation / 'result.json', {'training_checkpoint': 'Qwen/Qwen3.5-4B', 'training_model': 'Qwen/Qwen3.5-4B',
                  'inference_kind': 'base', 'environment': 'journal', 'factory_contract': True, 'concurrency': 3,
                  'harbor_exit': 0, 'proxy_destroyed': True})
            job = evaluation / 'harbor/checkpoint-browser'
            write(job / 'result.json', {'finished_at': '2026-09-23T15:00:00Z'})
            for name in names:
                bad = failure and name == 'a'
                write(job / (name + '__trial') / 'result.json', {'task_name': name,
                      'exception_info': {'exception_type': 'ConnectError'} if bad else None,
                      'verifier_result': None if bad else {'rewards': {'reward': 1.0 if name == 'b' else 0.0}},
                      'verifier_environment_mode': 'shared' if shared_verifier and name == 'b' else 'separate'})
        return directory

    def remote_proof(self, directory, names, checkpoint, final_plan):
        return {'admission_kind': 'initial_final', 'started_at': self.started,
                'archive_sha256': 'archive-' + Path(directory).name,
                'proxy_destroyed': True, 'orchestrator_destroyed': True}

    def test_finalize_is_read_only_until_admitted_and_registers_only_once(self):
        directory = self.collected()
        with patch.object(final, 'audit_remote', side_effect=self.remote_proof):
            proof = final.finalize(self.study, self.labels[0])
            self.assertFalse(proof['registered'])
            self.assertAlmostEqual(proof['evaluation']['score'], 1/6)
            self.assertFalse((directory / 'summary.json').exists())
            self.assertEqual(self.registries['sol6'].snapshot()['final_results'], [])
            final.finalize(self.study, self.labels[0], admit=True)
            first = (directory / 'initial-final-receipt.json').read_bytes()
            final.finalize(self.study, self.labels[0], admit=True)
            self.assertEqual((directory / 'initial-final-receipt.json').read_bytes(), first)
            self.assertEqual(len(self.registries['sol6'].snapshot()['final_results']), 1)

    def test_infrastructure_failure_is_preserved_as_null_without_reexecution(self):
        directory = self.collected(failure=True)
        original = (directory / 'chunk-0/evaluation/harbor/checkpoint-browser/a__trial/result.json').read_bytes()
        with patch.object(final, 'audit_remote', side_effect=self.remote_proof), patch('e2b.Sandbox.create', side_effect=AssertionError('no replay')):
            proof = final.finalize(self.study, self.labels[0], admit=True)
        self.assertEqual(proof['evaluation']['status'], 'infrastructure_error')
        self.assertIsNone(proof['evaluation']['score'])
        self.assertFalse(self.registries['sol6'].snapshot()['final_results'][0]['valid'])
        self.assertEqual((directory / 'chunk-0/evaluation/harbor/checkpoint-browser/a__trial/result.json').read_bytes(), original)

    def test_shared_verifier_or_pre_freeze_execution_cannot_be_admitted(self):
        directory = self.collected(shared_verifier=True)
        with patch.object(final, 'audit_remote', side_effect=self.remote_proof), self.assertRaisesRegex(ValueError, 'separate verification'):
            final.finalize(self.study, self.labels[0], admit=True)
        self.assertEqual(self.registries['sol6'].snapshot()['final_results'], [])
        self.started = 0
        with patch.object(final, 'audit_remote', side_effect=self.remote_proof), self.assertRaisesRegex(ValueError, 'precedes frozen'):
            final.finalize(self.study, self.labels[0], admit=True)


if __name__ == '__main__':
    unittest.main()
