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
        return {'cell_id': cell_id, 'base_manifest': manifests.pop('shared-base'),
                'selected_manifests': manifests}

    @classmethod
    def build_fixture(cls) -> dict:
        cells = [cls.build_cell(cell_id) for cell_id in matrix.CELLS]
        return {
            'schema': matrix.SCHEMA, 'study_id': 'full-computer-use-v1',
            'student_model': matrix.STUDENT, 'teacher_model': matrix.TEACHER,
            'researchers': matrix.RESEARCHERS, 'cells': cells,
            'budget': {'campaign_hours': 16,
                       'tinker_usd_per_campaign': '500',
                       'global_all_in_ceiling_usd': '3000',
                       'available_all_in_usd': '3000',
                       'spending_authorized_by_user': True},
        }

    def write_matrix(self, value: dict, name='changed.json') -> Path:
        path = self.root / name
        path.write_bytes(cell_final.json_bytes(value))
        return path

    def test_matched_six_cell_matrix_has_24_campaigns_and_3000_final_trials(self):
        out = self.root / 'prepared'
        result = matrix.prepare(self.manifest_path, out)
        plan = json.loads((out / 'matrix-plan.json').read_text())
        self.assertEqual((result['campaign_count'], result['distinct_official_task_identities'],
                          result['initial_total_final_trials']), (24, 600, 3000))
        self.assertEqual((plan['initial_base_final_trials'],
                          plan['initial_selected_final_trials']), (600, 2400))
        self.assertEqual(plan['declared_all_in_cost_upper_bound_usd'], '3000')
        self.assertFalse(plan['provider_dispatch_enabled'])
        self.assertFalse(plan['scores_present'])
        self.assertEqual(result['provider_calls'], 0)
        self.assertEqual(len(plan['cells']), 6)
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
