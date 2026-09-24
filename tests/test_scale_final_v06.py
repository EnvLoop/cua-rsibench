"""Manifest-defined v0.6 final preparation, with no provider clients."""

import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from cursibench import scale_final_v06 as final  # noqa: E402


def sha(data):
    return hashlib.sha256(data).hexdigest()


class ScaleFinalPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root / 'prepared' / 'excel-astra'
        self.manifest_path = self.root / 'cell-final.json'
        self.manifest = self.make_manifest()
        self.save_manifest()

    def ref(self, name, content):
        data = content if isinstance(content, bytes) else final.json_bytes(content)
        (self.root / name).parent.mkdir(parents=True, exist_ok=True)
        (self.root / name).write_bytes(data)
        return {'path': name, 'sha256': sha(data)}

    @staticmethod
    def row(prefix, index):
        identity = f'{prefix}-{index:03d}'
        return {'task_id': identity, 'package_sha256': sha(identity.encode()),
                'source_groups': [f'{identity}-original-workbook'],
                'template_group': f'{identity}-template',
                'instance_group': f'{identity}-instance'}

    def make_manifest(self):
        source = self.ref('source-snapshot.json', {'source_commit': 'pinned'})
        runtime = self.ref('runtime.json', {'runtime': 'pinned'})
        action = self.ref('action-contract.json', {'action_schema': 'pinned'})
        verifier = self.ref('verifier.json', {'verifier': 'pinned'})
        checkpoint_hash = sha(b'checkpoint-object')
        freeze = self.ref('selection-freeze.json', {
            'schema': final.FREEZE_SCHEMA, 'cell_id': 'microsoft-excel',
            'researcher_id': 'astra', 'role': 'selected',
            'checkpoint_sha256': checkpoint_hash, 'selection_frozen': True})
        official = [self.row('official', i) for i in range(100)]
        qualified_rows = []
        for row in official:
            task_id, package_hash = row['task_id'], row['package_sha256']
            initial = sha(('initial-' + task_id).encode())
            reset_proof = self.ref(f'proofs/{task_id}-reset.json', {
                'schema': 'cua-task-reset-proof-v0.6', 'task_id': task_id,
                'package_sha256': package_hash, 'initial_state_sha256': initial,
                'mutated_state_sha256': sha(('mutated-' + task_id).encode()),
                'restored_state_sha256': initial, 'fresh_environment': True, 'passed': True})
            verifier_proof = self.ref(f'proofs/{task_id}-verifier.json', {
                'schema': 'cua-task-verifier-proof-v0.6', 'task_id': task_id,
                'package_sha256': package_hash, 'evaluator_isolated': True,
                'positive_accepted': True, 'negative_rejected': True,
                'unrelated_changes_rejected': True, 'passed': True})
            qualified_rows.append({
                'task_id': task_id, 'package_sha256': package_hash,
                'build_passed': True, 'gui_roundtrip_passed': True,
                'reset': {'passed': True, 'evidence': reset_proof},
                'independent_verifier': {'separate_evaluator': True,
                                         'positive_passed': True, 'negative_rejected': True,
                                         'no_regression_checked': True,
                                         'evidence': verifier_proof}})
        gates = {}
        for gate in ('application_access', 'software_entitlement',
                     'student_observation_and_sampling'):
            proof_ref = self.ref(f'proofs/cell-{gate}.json', {
                'schema': 'cua-cell-gate-proof-v0.6', 'cell_id': 'microsoft-excel',
                'gate': gate, 'passed': True})
            gates[gate] = {'passed': True, 'evidence': proof_ref}
        qualification = {
            'schema': final.EVIDENCE_SCHEMA, 'cell_id': 'microsoft-excel',
            'status': 'qualified',
            'bindings': {key + '_sha256': ref['sha256'] for key, ref in (
                ('source_snapshot', source), ('runtime', runtime),
                ('action_contract', action), ('verifier', verifier))},
            'cell_gates': gates, 'official_tasks': qualified_rows}
        qualification_ref = self.ref('qualification.json', qualification)
        return {
            'schema': final.MANIFEST_SCHEMA, 'cell_id': 'microsoft-excel',
            'researcher_id': 'astra', 'role': 'selected', 'qualification_status': 'qualified',
            'task_sets': {'train': [self.row('train', 0)],
                          'selection': [self.row('selection', 0)], 'official': official},
            'qualification_evidence': qualification_ref,
            'bindings': {'checkpoint': {'model': 'Qwen/Qwen3.8-27B',
                                        'sha256': checkpoint_hash, 'freeze_receipt': freeze},
                         'source_snapshot': source, 'runtime': runtime,
                         'action_contract': action, 'verifier': verifier},
            'sampling': {'seed': 23, 'temperature': '0', 'max_output_tokens': 512},
            'execution': {'tasks_per_chunk': 3, 'max_actions_per_task': 90,
                          'max_wall_seconds_per_task': 1500, 'max_active_chunks': 3},
            'cost': {'currency': 'USD',
                     'basis': 'all_in_including_provider_compute_inference_storage_and_licenses',
                     'task_usd_upper_bound': '1.25', 'chunk_usd_upper_bound': '0.50',
                     'authorized_ceiling_usd': '150', 'available_balance_usd': '150',
                     'spending_authorized_by_user': True}}

    def save_manifest(self):
        self.manifest_path.write_bytes(final.json_bytes(self.manifest))

    def refresh_qualification_hash(self):
        self.manifest['qualification_evidence']['sha256'] = sha((self.root / 'qualification.json').read_bytes())
        self.save_manifest()

    def test_one_hundred_tasks_and_one_task_tail_are_bound(self):
        result = final.prepare(self.manifest_path, self.out)
        plan = json.loads((self.out / 'chunk-plan.json').read_text())
        intent = json.loads((self.out / 'intent.json').read_text())
        self.assertEqual((result['official_task_count'], result['chunk_count'], result['tail_task_count']),
                         (100, 34, 1))
        self.assertEqual([chunk['task_count'] for chunk in plan['chunks']], [3] * 33 + [1])
        self.assertEqual([task['task_id'] for chunk in plan['chunks'] for task in chunk['tasks']],
                         [row['task_id'] for row in self.manifest['task_sets']['official']])
        self.assertEqual(plan['declared_all_in_cost_upper_bound_usd'], '142.00')
        self.assertEqual(intent['plan_sha256'], sha((self.out / 'chunk-plan.json').read_bytes()))
        self.assertEqual(len(set(chunk['request_id'] for chunk in plan['chunks'])), 34)
        self.assertFalse(plan['provider_dispatch_enabled'])
        self.assertFalse(plan['scores_present'])
        self.assertEqual(result['provider_calls'], 0)

    def test_resume_preserves_intent_and_completes_missing_plan(self):
        first = final.prepare(self.manifest_path, self.out)
        saved_intent = (self.out / 'intent.json').read_bytes()
        saved_plan = (self.out / 'chunk-plan.json').read_bytes()
        self.assertEqual(final.prepare(self.manifest_path, self.out), first)
        self.assertEqual((self.out / 'intent.json').read_bytes(), saved_intent)
        self.assertEqual((self.out / 'chunk-plan.json').read_bytes(), saved_plan)
        (self.out / 'chunk-plan.json').unlink()
        self.assertEqual(final.prepare(self.manifest_path, self.out), first)
        self.assertEqual((self.out / 'intent.json').read_bytes(), saved_intent)
        self.assertEqual((self.out / 'chunk-plan.json').read_bytes(), saved_plan)

    def test_tampered_manifest_plan_intent_and_bound_bytes_are_rejected(self):
        final.prepare(self.manifest_path, self.out)
        original_manifest = self.manifest_path.read_bytes()
        original_plan = (self.out / 'chunk-plan.json').read_bytes()
        original_intent = (self.out / 'intent.json').read_bytes()
        self.manifest['sampling']['seed'] = 24
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, 'intent differs'):
            final.prepare(self.manifest_path, self.out)
        self.manifest_path.write_bytes(original_manifest)
        (self.out / 'chunk-plan.json').write_bytes(original_plan + b' ')
        with self.assertRaisesRegex(ValueError, 'chunk plan changed'):
            final.prepare(self.manifest_path, self.out)
        (self.out / 'chunk-plan.json').write_bytes(original_plan)
        (self.out / 'intent.json').write_bytes(original_intent + b' ')
        # Even cosmetically changed intent bytes are not canonical evidence.
        with self.assertRaisesRegex(ValueError, 'intent.*invalid|intent differs'):
            final.prepare(self.manifest_path, self.out)
        (self.out / 'intent.json').write_bytes(original_intent)
        (self.root / 'runtime.json').write_bytes(b'changed runtime')
        with self.assertRaisesRegex(ValueError, 'runtime binding: evidence bytes changed'):
            final.prepare(self.manifest_path, self.out)

    def test_unqualified_missing_proof_leakage_and_unknown_cost_rejected(self):
        bad = copy.deepcopy(self.manifest)
        bad['qualification_status'] = 'candidate'
        self.save_bad_and_reject(bad, 'cell is not qualified')
        qualification = json.loads((self.root / 'qualification.json').read_text())
        qualification['cell_gates']['application_access']['passed'] = False
        (self.root / 'qualification.json').write_bytes(final.json_bytes(qualification))
        self.refresh_qualification_hash()
        with self.assertRaisesRegex(ValueError, 'application_access: cell is not qualified'):
            final.prepare(self.manifest_path, self.out)
        qualification['cell_gates']['application_access']['passed'] = True
        (self.root / 'qualification.json').write_bytes(final.json_bytes(qualification))
        self.refresh_qualification_hash()
        bad = copy.deepcopy(self.manifest)
        bad['task_sets']['official'][1]['instance_group'] = bad['task_sets']['official'][0]['instance_group']
        self.save_bad_and_reject(bad, 'official instances must be distinct')
        bad = copy.deepcopy(self.manifest)
        bad['task_sets']['official'][1]['template_group'] = bad['task_sets']['selection'][0]['template_group']
        self.save_bad_and_reject(bad, 'template group leaked across splits')
        bad = copy.deepcopy(self.manifest)
        bad['cost']['available_balance_usd'] = None
        self.save_bad_and_reject(bad, 'decimal string required')
        bad = copy.deepcopy(self.manifest)
        bad['cost']['authorized_ceiling_usd'] = '100'
        self.save_bad_and_reject(bad, 'cost bound exceeds')
        qualification = json.loads((self.root / 'qualification.json').read_text())
        qualification['official_tasks'][0]['reset']['passed'] = False
        (self.root / 'qualification.json').write_bytes(final.json_bytes(qualification))
        self.refresh_qualification_hash()
        with self.assertRaisesRegex(ValueError, 'lacks reset proof'):
            final.prepare(self.manifest_path, self.out)
        qualification['official_tasks'][0]['reset']['passed'] = True
        qualification['official_tasks'][0]['independent_verifier']['negative_rejected'] = False
        (self.root / 'qualification.json').write_bytes(final.json_bytes(qualification))
        self.refresh_qualification_hash()
        with self.assertRaisesRegex(ValueError, 'lacks independent'):
            final.prepare(self.manifest_path, self.out)

    def test_missing_or_tampered_per_task_proof_is_rejected(self):
        qualification = json.loads((self.root / 'qualification.json').read_text())
        reset_ref = qualification['official_tasks'][17]['reset']['evidence']
        proof_path = self.root / reset_ref['path']
        proof = proof_path.read_bytes()
        proof_path.unlink()
        with self.assertRaisesRegex(ValueError, 'missing or unsafe evidence file'):
            final.prepare(self.manifest_path, self.out)
        proof_path.write_bytes(proof)
        proof_path.write_bytes(proof + b' ')
        with self.assertRaisesRegex(ValueError, 'evidence bytes changed'):
            final.prepare(self.manifest_path, self.out)

    def test_official_count_and_source_leakage_guard(self):
        bad = copy.deepcopy(self.manifest)
        bad['task_sets']['official'].pop()
        self.save_bad_and_reject(bad, 'exactly 100 official tasks')
        bad = copy.deepcopy(self.manifest)
        bad['task_sets']['official'][0]['source_groups'] = \
            bad['task_sets']['selection'][0]['source_groups']
        self.save_bad_and_reject(bad, 'source group leaked across splits')

    def test_repeated_source_families_within_official_are_counted_not_misrepresented(self):
        self.manifest['task_sets']['official'][1]['source_groups'] = \
            self.manifest['task_sets']['official'][0]['source_groups']
        self.manifest['task_sets']['official'][1]['template_group'] = \
            self.manifest['task_sets']['official'][0]['template_group']
        self.save_manifest()
        final.prepare(self.manifest_path, self.out)
        plan = json.loads((self.out / 'chunk-plan.json').read_text())
        self.assertEqual(plan['official_task_count'], 100)
        self.assertEqual(plan['official_cluster_counts'], {
            'source_groups': 99, 'template_groups': 99, 'instance_groups': 100})
        self.assertFalse(plan['one_hundred_independent_source_families_claimed'])

    def test_upstream_task_ids_with_spaces_are_valid_json_identities(self):
        row = self.row('official', 0)
        row['task_id'] = 'HSC Careers and Expo FINAL COM MOD-038'
        self.assertEqual(final.task_identity(row, 'example')['task_id'], row['task_id'])

    def save_bad_and_reject(self, bad, message):
        self.manifest_path.write_bytes(final.json_bytes(bad))
        with self.assertRaisesRegex(ValueError, message):
            final.prepare(self.manifest_path, self.out)
        self.save_manifest()


if __name__ == '__main__':
    unittest.main()
