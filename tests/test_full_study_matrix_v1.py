"""A full matrix freezes only matched, individually qualified 100-task cells."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from cursibench import full_study_matrix_v1 as matrix  # noqa: E402
from cursibench import full_study_pre_campaign_v1 as pre_campaign  # noqa: E402
from cursibench import scale_final_v06 as cell_final  # noqa: E402


def sha(value: bytes) -> str:
    return cell_final.digest(value)


class FullStudyMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory(prefix='cua-full-matrix-test-')
        cls.root = Path(cls.temp.name)
        cls.matrix = cls.build_fixture()
        cls.manifest_path = cls.root / 'matrix.json'
        cls.manifest_path.write_bytes(cell_final.json_bytes(cls.matrix))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    @classmethod
    def local_ref(cls, directory: Path, name: str, payload: object) -> dict:
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        data = payload if isinstance(payload, bytes) else cell_final.json_bytes(payload)
        path.write_bytes(data)
        return {'path': name, 'sha256': sha(data)}

    @classmethod
    def matrix_ref(cls, path: Path) -> dict:
        return {'path': path.relative_to(cls.root).as_posix(),
                'sha256': sha(path.read_bytes())}

    @classmethod
    def configuration(cls, name: str, role: str, model: str) -> dict:
        directory = cls.root / 'configs' / name
        directory.mkdir(parents=True)
        assets = {}
        names = ['prompt', 'harness', 'tool_grammar', 'decoding', 'provider_route']
        if role == 'student':
            names.append('training')
        for asset in names:
            assets[asset] = cls.local_ref(directory, asset + '.txt',
                                          (name + ':' + asset).encode())
        settings = ({'renderer': 'qwen3_8_disable_thinking',
                     'image_processor': 'pinned',
                     'temperature': '0', 'max_output_tokens': 512}
                    if role == 'student' else
                    {'reasoning_effort': 'max',
                     'temperature': '0', 'max_output_tokens': 4096})
        path = directory / 'config.json'
        path.write_bytes(cell_final.json_bytes({
            'schema': 'cua-model-configuration-v1',
            'role': role, 'model': model, 'snapshot_id': None,
            'settings': settings, 'assets': assets,
        }))
        return cls.matrix_ref(path)

    @staticmethod
    def task(cell_id: str, split: str, index: int) -> dict:
        identity = f'{cell_id}-{split}-{index:03d}'
        return {'task_id': identity, 'package_sha256': sha(identity.encode()),
                'source_groups': [identity + '-source'],
                'template_group': identity + '-template',
                'instance_group': identity + '-instance'}

    @classmethod
    def build_cell(cls, cell_id: str) -> dict:
        directory = cls.root / cell_id
        directory.mkdir()
        source = cls.local_ref(directory, 'bindings/source.json', {'cell': cell_id})
        runtime = cls.local_ref(directory, 'bindings/runtime.json', {'runtime': cell_id})
        action = cls.local_ref(directory, 'bindings/action.json', {'action': 'visual-v1'})
        verifier = cls.local_ref(directory, 'bindings/verifier.json', {'verifier': cell_id})
        train = [cls.task(cell_id, 'train', 0)]
        selection = [cls.task(cell_id, 'selection', i) for i in range(20)]
        official = [cls.task(cell_id, 'official', i) for i in range(100)]
        gates = {}
        for gate in ('application_access', 'software_entitlement',
                     'student_observation_and_sampling'):
            evidence = cls.local_ref(directory, f'proofs/{gate}.json', {
                'schema': 'cua-cell-gate-proof-v0.6',
                'cell_id': cell_id, 'gate': gate, 'passed': True})
            gates[gate] = {'passed': True, 'evidence': evidence}
        task_proofs = []
        for row in official:
            task_id, package = row['task_id'], row['package_sha256']
            initial = sha(('initial-' + task_id).encode())
            reset = cls.local_ref(directory, f'proofs/{task_id}-reset.json', {
                'schema': 'cua-task-reset-proof-v0.6', 'task_id': task_id,
                'package_sha256': package, 'initial_state_sha256': initial,
                'mutated_state_sha256': sha(('mutated-' + task_id).encode()),
                'restored_state_sha256': initial, 'fresh_environment': True,
                'passed': True})
            independent = cls.local_ref(directory, f'proofs/{task_id}-verifier.json', {
                'schema': 'cua-task-verifier-proof-v0.6', 'task_id': task_id,
                'package_sha256': package, 'evaluator_isolated': True,
                'positive_accepted': True, 'negative_rejected': True,
                'unrelated_changes_rejected': True, 'passed': True})
            task_proofs.append({
                'task_id': task_id, 'package_sha256': package,
                'build_passed': True, 'gui_roundtrip_passed': True,
                'reset': {'passed': True, 'evidence': reset},
                'independent_verifier': {
                    'separate_evaluator': True, 'positive_passed': True,
                    'negative_rejected': True, 'no_regression_checked': True,
                    'evidence': independent},
            })
        cls.local_ref(directory, 'analysis-families.json', {
            'schema': 'cua-cell-analysis-families-v1',
            'cell_id': cell_id,
            'family_by_task': {row['task_id']: row['source_groups'][0]
                               for row in official},
        })
        analysis_families = cls.matrix_ref(directory / 'analysis-families.json')
        qualification = cls.local_ref(directory, 'qualification.json', {
            'schema': cell_final.EVIDENCE_SCHEMA,
            'cell_id': cell_id, 'status': 'qualified',
            'bindings': {key + '_sha256': value['sha256'] for key, value in (
                ('source_snapshot', source), ('runtime', runtime),
                ('action_contract', action), ('verifier', verifier))},
            'cell_gates': gates, 'official_tasks': task_proofs,
        })
        manifests = {}
        for researcher_id, role in [('shared-base', 'base'),
                                    *((key, 'selected') for key in matrix.RESEARCHERS)]:
            checkpoint = sha((cell_id + researcher_id).encode())
            freeze = cls.local_ref(directory, f'proofs/{researcher_id}-freeze.json', {
                'schema': cell_final.FREEZE_SCHEMA, 'cell_id': cell_id,
                'researcher_id': researcher_id, 'role': role,
                'checkpoint_sha256': checkpoint, 'selection_frozen': True})
            slot = {
                'schema': cell_final.MANIFEST_SCHEMA,
                'cell_id': cell_id, 'researcher_id': researcher_id,
                'role': role, 'qualification_status': 'qualified',
                'task_sets': {'train': train, 'selection': selection,
                              'official': official},
                'qualification_evidence': qualification,
                'bindings': {'checkpoint': {
                    'model': matrix.STUDENT, 'sha256': checkpoint,
                    'freeze_receipt': freeze},
                    'source_snapshot': source, 'runtime': runtime,
                    'action_contract': action, 'verifier': verifier},
                'sampling': {'seed': 23, 'temperature': '0',
                             'max_output_tokens': 512},
                'execution': {'tasks_per_chunk': 3, 'max_actions_per_task': 80,
                              'max_wall_seconds_per_task': 1500,
                              'max_active_chunks': 3},
                'cost': {'currency': 'USD',
                         'basis': 'all_in_including_provider_compute_inference_storage_and_licenses',
                         'task_usd_upper_bound': '1', 'chunk_usd_upper_bound': '0',
                         'authorized_ceiling_usd': '100',
                         'available_balance_usd': '100',
                         'spending_authorized_by_user': True},
            }
            path = directory / f'{researcher_id}.json'
            path.write_bytes(cell_final.json_bytes(slot))
            manifests[researcher_id] = cls.matrix_ref(path)
        return {'cell_id': cell_id, 'analysis_families': analysis_families,
                'base_manifest': manifests.pop('shared-base'),
                'selected_manifests': manifests}

    @classmethod
    def build_fixture(cls) -> dict:
        cells = [cls.build_cell(cell_id) for cell_id in matrix.CELLS]
        value = {
            'schema': matrix.SCHEMA, 'study_id': 'full-computer-use-v1',
            'student_model': matrix.STUDENT, 'teacher_model': matrix.TEACHER,
            'researchers': matrix.RESEARCHERS, 'cells': cells,
            'configurations': {
                'student': cls.configuration('student', 'student', matrix.STUDENT),
                'teacher': cls.configuration('teacher', 'teacher', matrix.TEACHER),
                'researchers': {key: cls.configuration(
                    key, 'researcher', model)
                    for key, model in matrix.RESEARCHERS.items()},
            },
            'budget': {'campaign_hours': 16,
                       'tinker_usd_per_campaign': '500',
                       'researcher_inference_usd_per_campaign': '100',
                       'researcher_calls_per_campaign': 1000,
                       'teacher_rollout_usd_per_campaign': '25',
                       'teacher_rollout_tokens_per_campaign': 1000000,
                       'teacher_rollout_calls_per_campaign': 1000,
                       'e2b_sandbox_hours_per_campaign': '20',
                       'e2b_usd_per_campaign': '20',
                       'e2b_peak_concurrency': 3,
                       'storage_application_usd_per_campaign': '5',
                       'candidate_submissions_per_campaign': 25,
                       'selection_evaluations_per_campaign': 25,
                       'per_campaign_all_in_ceiling_usd': '750',
                       'global_all_in_ceiling_usd': '20000',
                       'available_all_in_usd': '20000',
                       'spending_authorized_by_user': True},
        }
        protocol = copy.deepcopy(value)
        protocol['schema'] = pre_campaign.SCHEMA
        for cell in protocol['cells']:
            del cell['selected_manifests']
        protocol_path = cls.root / 'pre-campaign-protocol.json'
        protocol_path.write_bytes(cell_final.json_bytes(protocol))
        frozen = pre_campaign.build(protocol, cls.root,
                                    sha(protocol_path.read_bytes()))
        plan_path = cls.root / 'pre-campaign-plan.json'
        plan_path.write_bytes(cell_final.json_bytes(frozen))
        value['pre_campaign_protocol'] = cls.matrix_ref(protocol_path)
        value['pre_campaign_plan'] = cls.matrix_ref(plan_path)
        return value

    def write_matrix(self, value: dict, name='changed.json') -> Path:
        path = self.root / name
        path.write_bytes(cell_final.json_bytes(value))
        return path

    def pre_campaign_manifest(self) -> dict:
        value = copy.deepcopy(self.matrix)
        value['schema'] = pre_campaign.SCHEMA
        del value['pre_campaign_protocol']
        del value['pre_campaign_plan']
        for cell in value['cells']:
            del cell['selected_manifests']
        return value

    def test_pre_campaign_freeze_requires_six_qualified_bases_before_training(self):
        source = self.write_matrix(self.pre_campaign_manifest(), 'pre-campaign.json')
        out = self.root / 'pre-campaign-prepared'
        result = pre_campaign.prepare(source, out)
        plan = json.loads((out / 'campaign-plan.json').read_text())
        self.assertEqual((result['campaign_count'],
                          result['distinct_official_task_identities']), (24, 600))
        self.assertEqual(plan['declared_shared_base_cost_upper_bound_usd'], '600')
        self.assertEqual(plan['declared_campaign_reservation_usd'], '18000')
        self.assertEqual(plan['declared_all_in_cost_upper_bound_usd'], '18600')
        self.assertEqual(len(plan['campaign_intents']), 24)
        self.assertTrue(all(row['selected_checkpoint_known'] is False and
                            row['provider_dispatch_enabled'] is False
                            for row in plan['campaign_intents']))
        self.assertEqual(pre_campaign.prepare(source, out), result)
        plan_path = out / 'campaign-plan.json'
        original = plan_path.read_bytes()
        try:
            plan_path.write_bytes(original + b' ')
            with self.assertRaisesRegex(ValueError, 'existing pre-campaign plan changed'):
                pre_campaign.prepare(source, out)
        finally:
            plan_path.write_bytes(original)

    def test_pre_campaign_rejects_incomplete_cell_and_underfunded_study(self):
        bad = self.pre_campaign_manifest()
        bad['cells'].pop()
        with self.assertRaisesRegex(ValueError, 'exactly six pre-campaign cells'):
            pre_campaign.prepare(self.write_matrix(bad), self.root / 'pre-missing-cell')
        bad = self.pre_campaign_manifest()
        bad['budget']['available_all_in_usd'] = '3000'
        with self.assertRaisesRegex(ValueError, 'pre-campaign all-in upper bound exceeds'):
            pre_campaign.prepare(self.write_matrix(bad), self.root / 'pre-budget-shortfall')
        bad = self.pre_campaign_manifest()
        bad['budget']['per_campaign_all_in_ceiling_usd'] = '650'
        with self.assertRaisesRegex(ValueError, 'omits selected final-evaluation'):
            pre_campaign.prepare(self.write_matrix(bad), self.root / 'pre-final-omitted')

    def test_pre_campaign_rejects_changed_base_qualification_or_model_asset(self):
        bad = self.pre_campaign_manifest()
        ref = bad['cells'][0]['base_manifest']
        path = self.root / ref['path']
        original = path.read_bytes()
        try:
            value = json.loads(original)
            value['qualification_status'] = 'candidate'
            path.write_bytes(cell_final.json_bytes(value))
            ref['sha256'] = sha(path.read_bytes())
            with self.assertRaisesRegex(ValueError, 'cell is not qualified'):
                pre_campaign.prepare(self.write_matrix(bad), self.root / 'pre-unqualified')
        finally:
            path.write_bytes(original)
        prompt = self.root / 'configs/astra/prompt.txt'
        original = prompt.read_bytes()
        try:
            prompt.write_bytes(original + b' changed')
            with self.assertRaisesRegex(ValueError, 'evidence bytes changed'):
                pre_campaign.prepare(self.write_matrix(self.pre_campaign_manifest()),
                                     self.root / 'pre-prompt-drift')
        finally:
            prompt.write_bytes(original)

    def test_final_matrix_cannot_replace_frozen_pre_campaign_plan(self):
        changed = copy.deepcopy(self.matrix)
        reference = changed['pre_campaign_plan']
        path = self.root / reference['path']
        original = path.read_bytes()
        try:
            plan = json.loads(original)
            plan['campaign_count'] = 23
            path.write_bytes(cell_final.json_bytes(plan))
            reference['sha256'] = sha(path.read_bytes())
            with self.assertRaisesRegex(ValueError,
                                        'differs from frozen pre-campaign protocol'):
                matrix.prepare(self.write_matrix(changed), self.root / 'pre-plan-replaced')
        finally:
            path.write_bytes(original)
        changed = copy.deepcopy(self.matrix)
        changed['budget']['teacher_rollout_calls_per_campaign'] = 999
        with self.assertRaisesRegex(ValueError,
                                    'differs from frozen pre-campaign protocol'):
            matrix.prepare(self.write_matrix(changed), self.root / 'pre-budget-drift')

    def test_matched_six_cell_matrix_has_24_campaigns_and_3000_final_trials(self):
        out = self.root / 'prepared'
        result = matrix.prepare(self.manifest_path, out)
        plan = json.loads((out / 'matrix-plan.json').read_text())
        self.assertEqual((result['campaign_count'], result['distinct_official_task_identities'],
                          result['initial_total_slot_task_results']), (24, 600, 3000))
        self.assertEqual((plan['initial_base_final_trials'],
                          plan['initial_selected_final_trials']), (600, 2400))
        self.assertEqual(result['planned_unique_checkpoint_task_executions'], 3000)
        self.assertTrue(all(cell['unique_checkpoint_count'] == 5 for cell in plan['cells']))
        self.assertEqual(plan['declared_final_slot_cost_upper_bound_usd'], '3000')
        self.assertEqual(plan['declared_shared_base_cost_upper_bound_usd'], '600')
        self.assertEqual(plan['declared_campaign_reservation_usd'], '18000')
        self.assertEqual(plan['declared_all_in_cost_upper_bound_usd'], '18600')
        self.assertEqual(len(plan['configuration_bindings']['researchers']), 4)
        self.assertIn('training', plan['configuration_bindings']['student']['asset_sha256'])
        self.assertEqual(plan['researcher_inference_usd_cap_per_campaign'], '100')
        self.assertEqual(plan['matched_non_tinker_campaign_caps'][
            'teacher_rollout_tokens_per_campaign'], 1000000)
        self.assertFalse(plan['provider_dispatch_enabled'])
        self.assertFalse(plan['scores_present'])
        self.assertEqual(result['provider_calls'], 0)
        self.assertEqual(len(plan['cells']), 6)
        self.assertTrue(all(cell['analysis_family_count'] == 100
                            for cell in plan['cells']))
        self.assertTrue(all(cell['base']['chunk_count'] == 34 for cell in plan['cells']))
        self.assertEqual(matrix.prepare(self.manifest_path, out), result)

    def test_missing_cell_wrong_roster_and_unavailable_budget_fail_closed(self):
        bad = copy.deepcopy(self.matrix)
        bad['cells'].pop()
        with self.assertRaisesRegex(ValueError, 'exactly six cells'):
            matrix.prepare(self.write_matrix(bad), self.root / 'bad-cells')
        bad = copy.deepcopy(self.matrix)
        bad['researchers']['sol6'] = 'gpt-6-luna'
        with self.assertRaisesRegex(ValueError, 'roster changed'):
            matrix.prepare(self.write_matrix(bad), self.root / 'bad-roster')
        bad = copy.deepcopy(self.matrix)
        bad['budget']['available_all_in_usd'] = '2999'
        with self.assertRaisesRegex(ValueError, 'all-in upper bound exceeds'):
            matrix.prepare(self.write_matrix(bad), self.root / 'bad-budget')
        bad = copy.deepcopy(self.matrix)
        bad['budget']['researcher_calls_per_campaign'] = None
        with self.assertRaisesRegex(ValueError, 'positive integer required'):
            matrix.prepare(self.write_matrix(bad), self.root / 'missing-external-cap')
        bad = copy.deepcopy(self.matrix)
        bad['budget']['per_campaign_all_in_ceiling_usd'] = '99'
        with self.assertRaisesRegex(ValueError, 'cannot cover declared service caps'):
            matrix.prepare(self.write_matrix(bad), self.root / 'weak-campaign-cap')
        bad = copy.deepcopy(self.matrix)
        bad['budget']['per_campaign_all_in_ceiling_usd'] = '650'
        with self.assertRaisesRegex(ValueError, 'campaign all-in cap exceeded'):
            matrix.prepare(self.write_matrix(bad), self.root / 'missing-final-in-cap')
        bad = copy.deepcopy(self.matrix)
        bad['budget']['global_all_in_ceiling_usd'] = '3000'
        with self.assertRaisesRegex(ValueError, 'matrix all-in upper bound exceeds'):
            matrix.prepare(self.write_matrix(bad), self.root / 'training-omitted-global')
        bad = copy.deepcopy(self.matrix)
        bad['budget']['teacher_rollout_usd_per_campaign'] = '26'
        with self.assertRaisesRegex(ValueError, 'campaign all-in cap exceeded'):
            matrix.prepare(self.write_matrix(bad), self.root / 'teacher-dollars-omitted')
        bad = copy.deepcopy(self.matrix)
        del bad['budget']['e2b_usd_per_campaign']
        with self.assertRaisesRegex(ValueError, 'matrix budget: wrong fields'):
            matrix.prepare(self.write_matrix(bad), self.root / 'e2b-dollars-missing')

    def test_unqualified_slot_and_cross_researcher_drift_fail_closed(self):
        bad = copy.deepcopy(self.matrix)
        ref = bad['cells'][0]['selected_manifests']['astra']
        slot_path = self.root / ref['path']
        original = slot_path.read_bytes()
        try:
            slot = json.loads(original)
            slot['qualification_status'] = 'candidate'
            slot_path.write_bytes(cell_final.json_bytes(slot))
            ref['sha256'] = sha(slot_path.read_bytes())
            with self.assertRaisesRegex(ValueError, 'cell is not qualified'):
                matrix.prepare(self.write_matrix(bad), self.root / 'bad-slot')
            slot['qualification_status'] = 'qualified'
            slot['sampling']['seed'] = 24
            slot_path.write_bytes(cell_final.json_bytes(slot))
            ref['sha256'] = sha(slot_path.read_bytes())
            with self.assertRaisesRegex(ValueError, 'matched environment or policy differs'):
                matrix.prepare(self.write_matrix(bad), self.root / 'bad-matched')
        finally:
            slot_path.write_bytes(original)

    def test_model_configuration_or_prompt_byte_drift_is_rejected(self):
        bad = copy.deepcopy(self.matrix)
        ref = bad['configurations']['researchers']['astra']
        path = self.root / ref['path']
        original = path.read_bytes()
        try:
            value = json.loads(original)
            value['model'] = 'different-model'
            path.write_bytes(cell_final.json_bytes(value))
            ref['sha256'] = sha(path.read_bytes())
            with self.assertRaisesRegex(ValueError, 'configured model or role changed'):
                matrix.prepare(self.write_matrix(bad), self.root / 'bad-model-config')
        finally:
            path.write_bytes(original)
        asset_path = path.parent / 'prompt.txt'
        original_prompt = asset_path.read_bytes()
        try:
            asset_path.write_bytes(original_prompt + b' changed')
            with self.assertRaisesRegex(ValueError, 'evidence bytes changed'):
                matrix.prepare(self.manifest_path, self.root / 'bad-prompt')
        finally:
            asset_path.write_bytes(original_prompt)

    def test_identical_selected_checkpoint_reuses_frozen_base_evidence(self):
        changed = copy.deepcopy(self.matrix)
        cell = changed['cells'][0]
        base_path = self.root / cell['base_manifest']['path']
        selected_ref = cell['selected_manifests']['luna6']
        selected_path = self.root / selected_ref['path']
        selected_original = selected_path.read_bytes()
        selected = json.loads(selected_original)
        freeze_path = selected_path.parent / selected['bindings']['checkpoint']['freeze_receipt']['path']
        freeze_original = freeze_path.read_bytes()
        try:
            base = json.loads(base_path.read_text())
            base_checkpoint = base['bindings']['checkpoint']['sha256']
            selected['bindings']['checkpoint']['sha256'] = base_checkpoint
            freeze = json.loads(freeze_original)
            freeze['checkpoint_sha256'] = base_checkpoint
            freeze_path.write_bytes(cell_final.json_bytes(freeze))
            selected['bindings']['checkpoint']['freeze_receipt']['sha256'] = sha(
                freeze_path.read_bytes())
            selected_path.write_bytes(cell_final.json_bytes(selected))
            selected_ref['sha256'] = sha(selected_path.read_bytes())
            result = matrix.prepare(self.write_matrix(changed), self.root / 'reused-base')
            plan = json.loads(Path(result['matrix_plan_path']).read_text())
            self.assertEqual(result['initial_total_slot_task_results'], 3000)
            self.assertEqual(result['planned_unique_checkpoint_task_executions'], 2900)
            self.assertEqual(plan['cells'][0]['execution_evidence_owner_by_slot']['luna6'],
                             'shared-base')
        finally:
            selected_path.write_bytes(selected_original)
            freeze_path.write_bytes(freeze_original)

    def test_analysis_family_must_be_prebound_to_a_real_source_group(self):
        changed = copy.deepcopy(self.matrix)
        ref = changed['cells'][0]['analysis_families']
        path = self.root / ref['path']
        original = path.read_bytes()
        try:
            value = json.loads(original)
            task = next(iter(value['family_by_task']))
            value['family_by_task'][task] = 'invented-family'
            path.write_bytes(cell_final.json_bytes(value))
            ref['sha256'] = sha(path.read_bytes())
            with self.assertRaisesRegex(ValueError, 'not a frozen source group'):
                matrix.prepare(self.write_matrix(changed), self.root / 'bad-family')
        finally:
            path.write_bytes(original)

    def test_tampered_intent_or_plan_and_missing_proof_fail_closed(self):
        out = self.root / 'prepared'
        matrix.prepare(self.manifest_path, out)
        plan = out / 'matrix-plan.json'
        original_plan = plan.read_bytes()
        try:
            plan.write_bytes(original_plan + b' ')
            with self.assertRaisesRegex(ValueError, 'existing matrix plan changed'):
                matrix.prepare(self.manifest_path, out)
        finally:
            plan.write_bytes(original_plan)
        reset_path = self.root / matrix.CELLS[-1] / 'proofs' / (
            matrix.CELLS[-1] + '-official-099-reset.json')
        original_reset = reset_path.read_bytes()
        try:
            reset_path.write_bytes(original_reset + b' ')
            with self.assertRaisesRegex(ValueError, 'evidence bytes changed'):
                matrix.prepare(self.manifest_path, out)
        finally:
            reset_path.write_bytes(original_reset)


if __name__ == '__main__':
    unittest.main()
