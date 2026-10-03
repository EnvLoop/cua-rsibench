"""Reference orchestration tests; no application, provider or model is started."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from magento_catalog_factory import native_selection_reference_controls_v1 as m


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(m.workers.final.canonical(value)); path.chmod(0o600)
    return m._sha(path)


def selection():
    return [{'task_id': f'fixture-{i:02d}', 'package_sha256': f'{i+1:064x}'} for i in range(20)]


def inputs_fixture(root):
    binding = m.workers.public_binding(); roster = selection(); loaded = []
    case = {'target_variants': [{'target_price': 1}], 'untouched_comparators': [{'price': 2}]}
    def load(identity, split):
        loaded.append((identity, split)); return case
    plan = root/'plan.private.json'; save(plan, {})
    return SimpleNamespace(binding=binding, roster={'splits': {'selection': roster, 'train': [roster[0]]}},
                           plan_path=plan, plan_sha=m._sha(plan), load=load, runtime=lambda: 'test-runtime',
                           username=lambda: 'test-admin', validate_train_admission=lambda: (_ for _ in ()).throw(
                               AssertionError('unchanged model admission must not be invoked'))), loaded


def native_row(identity, score, binding):
    return {**identity, 'score': score, 'native_source_binding_sha256': binding['binding_sha256'],
            'samples': [{'paid_attempt_id': None}]}


class SelectionReferenceTests(unittest.TestCase):
    def test_exact_existing_facade_loop_sixty_calls_saved_audit_and_no_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); inputs, loaded = inputs_fixture(root); output = root/'selection.private'
            contract = {'source_binding': m.source_binding(), 'output_root': str(output),
                        'selection_tasks': selection(), 'model_lane_admission_claimed': False}
            review = root/'review.private.json'; review_sha = save(review, contract)
            kwargs = {'output': output}
            seen = []
            async def task(**args):
                self.assertEqual(args['paid_attempt_id'], None)
                self.assertEqual(args['task'], selection()[len(seen)//3])
                self.assertIs(args['sampler'].__class__, m.facade.ancestor.ReferenceSampler)
                seen.append(args['sampler'].mode)
                return native_row(args['task'], int(args['sampler'].mode == 'positive'), inputs.binding)
            async_task = AsyncMock(side_effect=task)
            def audited(_folder, row, **args):
                self.assertFalse(args['provider_close_required'])
                return {'score': row['score'], 'actions': [], 'frames': []}
            with patch.object(m, '_prepare', return_value=(inputs, contract)), \
                 patch.object(m.facade._impl, 'run_task', async_task), \
                 patch.object(m.facade._impl, 'audit_episode', side_effect=audited), \
                 patch.object(m.audit, 'audit_episode', side_effect=audited):
                result = m.run(root_review_path=review, root_review_sha256=review_sha, execute=True, **kwargs)
                self.assertEqual(seen, [mode for _ in range(20) for mode, _ in m.MODES])
                self.assertEqual(loaded, [(identity, 'selection') for identity in selection()])
                self.assertEqual(async_task.await_count, 60)
                self.assertFalse(result['source_visual_qualification_complete'])
                self.assertFalse(result['formal_registration_performed'])
                self.assertFalse(result['model_lane_admission_claimed'])
                self.assertEqual(m.saved_audit(root_review_path=review, root_review_sha256=review_sha, **kwargs), result)
                with self.assertRaises(Exception):
                    m.run(root_review_path=review, root_review_sha256=review_sha, execute=True, **kwargs)
                self.assertEqual(async_task.await_count, 60)

    def test_failure_consumes_authority_and_never_calls_next_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); inputs, loaded = inputs_fixture(root); output = root/'selection.private'
            contract = {'source_binding': m.source_binding(), 'output_root': str(output)}
            review = root/'review.private.json'; digest = save(review, contract)
            task = AsyncMock(side_effect=RuntimeError('owned native failure'))
            with patch.object(m, '_prepare', return_value=(inputs, contract)), patch.object(m.facade._impl, 'run_task', task):
                for _ in range(2):
                    with self.assertRaises(Exception):
                        m.run(root_review_path=review, root_review_sha256=digest, execute=True, output=output)
                self.assertEqual(task.await_count, 1)
                self.assertTrue((output/'failure.private.json').exists())
                self.assertEqual(loaded, [(selection()[0], 'selection')])
                with self.assertRaises(Exception):
                    m.saved_audit(root_review_path=review, root_review_sha256=digest, output=output)

    def test_unreviewed_changed_contract_refuses_before_load_or_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); inputs, loaded = inputs_fixture(root)
            contract = {'source_binding': m.source_binding()}; review = root/'review.private.json'
            digest = save(review, {'source_binding': 'different'})
            with patch.object(m, '_prepare', return_value=(inputs, contract)), patch.object(m.facade._impl, 'run_controls') as loop:
                with self.assertRaises(Exception):
                    m.run(root_review_path=review, root_review_sha256=digest, execute=True, output=root/'output')
                loop.assert_not_called(); self.assertEqual(loaded, [])
            with self.assertRaises(Exception): m.run(execute=False)

    def test_reference_wrapper_refuses_final_train_or_changed_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            inputs, loaded = inputs_fixture(Path(temporary)); contract = {'source_binding': m.source_binding()}
            wrapper = m._ReferenceInputs(inputs, contract, {})
            for split in ['train', 'official_candidate']:
                with self.assertRaises(Exception): wrapper.load(selection()[0], split)
            with patch.object(m, 'source_binding', return_value={'changed': True}):
                with self.assertRaises(Exception): wrapper.load(selection()[0], 'selection')
                with self.assertRaises(Exception): wrapper.runtime()
            self.assertEqual(loaded, [])

    def test_reference_gate_reopens_prerequisites_before_original_load(self):
        with tempfile.TemporaryDirectory() as temporary:
            inputs, loaded = inputs_fixture(Path(temporary)); contract = {'source_binding': m.source_binding()}
            wrapper = m._ReferenceInputs(inputs, contract, {'input': 'exact'})
            with patch.object(m, '_prepare', return_value=(inputs, {'changed': True})) as prepare:
                with self.assertRaises(Exception): wrapper.validate_train_admission()
                prepare.assert_called_once_with(input='exact')
                self.assertEqual(loaded, [])

    def test_saved_audit_refuses_reordered_missing_identity_score_or_paid_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); inputs, _ = inputs_fixture(root); tasks = []
            for ordinal, identity in enumerate(selection()):
                trio = {}
                for mode, score in m.MODES:
                    folder = root/f'attempt-{ordinal:03d}'/mode
                    digest = save(folder/'native-row.private.json', native_row(identity, score, inputs.binding))
                    trio[mode] = {'score': score, 'episode_root': str(folder), 'native_row_sha256': digest}
                tasks.append({**identity, 'trio': trio})
            original = {'schema': 'magento-native-surface-control-set-v1', 'source_binding_sha256': inputs.binding['binding_sha256'],
                        'split': 'selection', 'task_count': 20, 'tasks': tasks, 'model_calls': 0,
                        'formal_registration_performed': False, 'old_development_control_credit': 0}
            controls = root/'controls.private.json'
            def audited(_folder, row, **_): return {'score': row['score'], 'actions': [], 'frames': []}
            with patch.object(m.audit, 'audit_episode', side_effect=audited):
                digest = save(controls, original); m._trios(inputs, controls, digest, 'selection', 20)
                variants = []
                bad = copy.deepcopy(original); bad['tasks'].reverse(); variants.append(bad)
                bad = copy.deepcopy(original); del bad['tasks'][0]['trio']['wrong_variant']; variants.append(bad)
                bad = copy.deepcopy(original); bad['tasks'][0]['package_sha256'] = 'f'*64; variants.append(bad)
                bad = copy.deepcopy(original); bad['tasks'][0]['trio']['positive']['score'] = 0; variants.append(bad)
                for bad in variants:
                    digest = save(controls, bad)
                    with self.assertRaises(Exception): m._trios(inputs, controls, digest, 'selection', 20)
                row_path = root/'attempt-000/baseline/native-row.private.json'
                row = m.private(row_path); row['samples'][0]['paid_attempt_id'] = 'unexpected-provider'
                bad = copy.deepcopy(original); bad['tasks'][0]['trio']['baseline']['native_row_sha256'] = save(row_path, row)
                digest = save(controls, bad)
                with self.assertRaises(Exception): m._trios(inputs, controls, digest, 'selection', 20)

    def test_independent_reset_auditor_failure_cannot_be_promoted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); inputs, _ = inputs_fixture(root); identity = selection()[0]; tasks = []
            trio = {}
            for mode, score in m.MODES:
                folder = root/'attempt-000'/mode
                digest = save(folder/'native-row.private.json', native_row(identity, score, inputs.binding))
                trio[mode] = {'score': score, 'episode_root': str(folder), 'native_row_sha256': digest}
            controls = {'schema': 'magento-native-surface-control-set-v1', 'source_binding_sha256': inputs.binding['binding_sha256'],
                        'split': 'train', 'task_count': 1, 'tasks': [{**identity, 'trio': trio}], 'model_calls': 0,
                        'formal_registration_performed': False, 'old_development_control_credit': 0,
                        'reference_binding': m.reference.reference_binding(), 'fresh_three_modes_completed': True,
                        'old_principal_epoch_qualification_credit': 0, 'original_baseline_promoted': False}
            path = root/'controls.private.json'; digest = save(path, controls)
            with patch.object(m.audit, 'audit_episode', side_effect=ValueError('exact reset failed')):
                with self.assertRaises(Exception): m._trios(inputs, path, digest, 'train', 1)

    def test_incomplete_source_reading_review_refuses_without_selection_or_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); inputs, loaded = inputs_fixture(root)
            path = root/'review.private.json'
            bad = {'schema': 'root-magento11-native-source-read-close-reset-audit-v1', 'actual_exec_exit_code': 0,
                   'model_calls': 0, 'tinker_calls': 0, 'native_full_qualification_claimed': False}
            digest = save(path, bad)
            with self.assertRaises(Exception): m._source_reading(inputs, {}, path, digest)
            self.assertEqual(loaded, [])

    def test_frozen_source_gate_uses_current_actual_facade_namespace(self):
        self.assertIs(m.facade._impl.run_task, m.workers.run_task)
        self.assertIs(m.facade._impl.audit_episode, m.audit.audit_episode)
        self.assertIs(m.facade._impl.ReferenceSampler, m.reference.reference.sampler)
        self.assertEqual(m.facade._impl.public_binding(), m.workers.public_binding())


if __name__ == '__main__': unittest.main()
