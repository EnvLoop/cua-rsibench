"""Arithmetic and isolation checks for offline scaling; no providers are used."""
import copy
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

FILE = Path(__file__).resolve().parents[1] / 'tools/plan_factory_scale.py'
SPEC = importlib.util.spec_from_file_location('offline_scale_planner', FILE)
planner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(planner)


def task(identity, source=None, template='shared-template', instance=None):
    return {'task_id': identity, 'source_groups': [source or identity], 'template_group': template,
            'instance_group': instance or identity, 'package_sha256': planner.fingerprint(identity)}


class ScalePlannerTests(unittest.TestCase):
    def test_four_by_six_hundred_task_arithmetic_and_tail_batches(self):
        config = planner.default_config()
        plan = planner.plan(config)
        capacity = plan['capacity']
        self.assertEqual(plan['matrix_campaigns'], 24)
        self.assertEqual(len({row['id'] for row in plan['campaigns']}), 24)
        self.assertEqual(plan['inventory']['planned_unique_final_instances'], 600)
        self.assertEqual(capacity['research_round_ceiling'], 120)
        self.assertEqual(capacity['global_training_token_cap'], 24 * 1048576)
        self.assertEqual(capacity['full_candidate_cap_rounds_per_campaign'], 4)
        self.assertEqual(config['final_seeds'], [23])
        self.assertEqual(capacity['final_base_initial_trials'], 600)
        self.assertEqual(capacity['final_selected_initial_trials'], 2400)
        self.assertEqual(capacity['final_total_initial_trials'], 3000)
        self.assertEqual(capacity['final_initial_remote_chunks'], 1020)
        self.assertEqual(capacity['selection_initial_trials'], 2520)
        self.assertEqual(capacity['selection_initial_remote_chunks'], 882)
        self.assertEqual(capacity['student_call_ceiling_with_recovery'], 993600)
        self.assertEqual(capacity['remote_chunk_ceiling_with_recovery'], 3804)
        self.assertEqual(capacity['nominal_wall_time_budget_sec_per_campaign'], 57600)
        self.assertEqual(capacity['aggregate_nominal_campaign_hours'], 384)
        self.assertEqual(capacity['nominal_Tinker_cost_budget_usd_per_campaign'], '500')
        self.assertEqual(capacity['aggregate_nominal_Tinker_budget_usd'], '12000')
        self.assertEqual(capacity['researcher_charged_call_ceiling'], 4800)
        self.assertEqual(capacity['teacher_charged_call_ceiling'], 12000)
        self.assertEqual(capacity['task_sandbox_ceiling_during_remote_only'], 24)
        for cell in plan['cells']:
            chunks = cell['final_chunks']
            self.assertEqual(len(chunks), 34)
            self.assertEqual([c['task_count'] for c in chunks], [3] * 33 + [1])
            slots = [i for chunk in chunks for i in range(chunk['planned_slot_start_inclusive'], chunk['planned_slot_end_exclusive'])]
            self.assertEqual(slots, list(range(100)))
            self.assertEqual(chunks[-1]['proxy_request_capacity'], 256)
            self.assertEqual(chunks[0]['proxy_request_capacity'], 270)

    def test_planning_preserves_user_authorization_without_creating_outcomes_or_dispatch(self):
        config = planner.default_config()
        before = copy.deepcopy(config)
        result = planner.plan(config)
        self.assertEqual(config, before)
        self.assertFalse(result['executed'])
        self.assertFalse(result['executable_now'])
        self.assertIsNone(result['outcomes'])
        self.assertEqual(result['provider_calls'], 0)
        self.assertEqual(result['inventory']['new_task_instances_generated'], 0)
        self.assertEqual(result['inventory']['validated_task_packages'], 0)
        self.assertIsNone(result['cost']['all_in_total_usd'])
        self.assertIsNone(result['cost']['token_cost_estimate_usd'])
        self.assertIsNotNone(result['cost']['known_token_cost_subtotal_usd'])
        self.assertTrue(result['spending_authorized_by_user'])
        self.assertTrue(result['cost']['spending_authorized_by_user'])
        self.assertFalse(result['cost']['dispatch_capability'])
        self.assertTrue(any('missing application' in x for x in result['readiness_blockers']))
        self.assertEqual(result, planner.plan(config))
        config['spending_authorized_by_user'] = False
        unauthorized = planner.plan(config)
        self.assertFalse(unauthorized['spending_authorized_by_user'])
        self.assertTrue(any('not authorized' in x for x in unauthorized['readiness_blockers']))

    def test_recovery_bound_is_separate_and_never_relabels_repeated_tasks(self):
        config = planner.default_config()
        config['execution']['selection_full_suite_replays'] = 0
        config['execution']['final_full_suite_replays'] = 0
        config['final_seeds'] = [23, 23]
        result = planner.plan(config)
        self.assertEqual(result['capacity']['final_total_initial_trials'], 6000)
        self.assertEqual(result['capacity']['final_trial_ceiling_with_recovery'], 6000)
        self.assertEqual(result['capacity']['student_call_ceiling_with_recovery'], (6000 + 2520) * 90)
        self.assertEqual(result['inventory']['planned_unique_final_instances'], 600)
        self.assertFalse(result['recovery_policy']['valid_scores_retried'])
        self.assertFalse(result['recovery_policy']['retry_counts_as_new_independent_repetition'])

    def test_extra_research_seed_multiplies_campaigns_but_does_not_invent_more_tasks(self):
        config = planner.default_config()
        config['research_seeds'] = [23, 42]
        result = planner.plan(config)
        self.assertEqual(result['matrix_campaigns'], 48)
        self.assertEqual(result['capacity']['final_selected_initial_trials'], 4800)
        self.assertEqual(result['capacity']['final_base_initial_trials'], 600)
        self.assertEqual(result['inventory']['planned_unique_final_instances'], 600)

    def test_unknown_input_tokens_remain_unknown_despite_training_sequence_limit(self):
        config = planner.default_config()
        for field in config['pricing_usd_per_million']:
            config['pricing_usd_per_million'][field] = '1.25'
        result = planner.plan(config)
        self.assertIsNone(result['cost']['components']['student_input']['tokens'])
        self.assertIsNone(result['cost']['token_cost_estimate_usd'])
        self.assertIsNotNone(result['cost']['known_token_cost_subtotal_usd'])
        config['input_tokens_per_call_assumption'] = {'student': 1000, 'teacher': 2000, 'researcher': 3000}
        result = planner.plan(config)
        components = result['cost']['components']
        expected = sum(Decimal(row['tokens']) for row in components.values()) * Decimal('1.25') / Decimal(1000000)
        self.assertEqual(Decimal(result['cost']['token_cost_estimate_usd']), expected)
        self.assertIsNone(result['cost']['all_in_total_usd'])
        self.assertTrue(result['cost']['spending_authorized_by_user'])
        self.assertFalse(result['cost']['dispatch_capability'])

    def test_invalid_matrix_resource_and_price_inputs_fail_closed(self):
        changes = [
            lambda c: c['researchers'].pop(),
            lambda c: c['cells'].pop(),
            lambda c: c['researchers'][1].update(model=c['researchers'][0]['model']),
            lambda c: c['cells'][1].update(id=c['cells'][0]['id']),
            lambda c: c['cells'][0].update(final_tasks=True),
            lambda c: c['execution'].update(tasks_per_chunk=4),
            lambda c: c['execution'].update(final_full_suite_replays=2),
            lambda c: c['execution'].update(orchestrator_lease_seconds=3000),
            lambda c: c['budget'].update(training_tokens_per_campaign=1),
            lambda c: c['budget'].update(Tinker_cost_budget_usd=0),
            lambda c: c['budget'].update(wall_time_budget_sec=0),
            lambda c: c.update(research_seeds=[23, 23]),
            lambda c: c['pricing_usd_per_million'].update(student_input='NaN'),
            lambda c: c['pricing_usd_per_million'].update(student_output=-1),
        ]
        for index, change in enumerate(changes):
            with self.subTest(index=index):
                config = planner.default_config()
                change(config)
                with self.assertRaises(ValueError):
                    planner.plan(config)

    def test_split_identity_metadata_is_verified_without_reading_task_contents(self):
        manifest = {'train': [task('train-a')], 'selection': [task('selection-a')],
                    'final': [task('final-a'), task('final-b')]}
        result = planner.validate_splits(manifest, 1, 2, 'shared_allowed')
        self.assertTrue(result['declared_split_identity_checks_pass'])
        self.assertEqual(result['counts']['final']['instance_groups'], 2)
        self.assertFalse(result['package_contents_verified'])
        self.assertFalse(result['access_control_verified'])
        with self.assertRaisesRegex(ValueError, 'template holdout'):
            planner.validate_splits(manifest, 1, 2, 'disjoint_required')
        for split, rows in manifest.items():
            for row in rows: row['template_group'] = split + '-template'
        self.assertTrue(planner.validate_splits(manifest, 1, 2, 'disjoint_required')['declared_split_identity_checks_pass'])

    def test_source_leakage_duplicate_instances_and_hidden_content_rejected(self):
        base = {'train': [task('train-a')], 'selection': [task('selection-a')],
                'final': [task('final-a'), task('final-b')]}
        variations = []
        source_leak = copy.deepcopy(base);source_leak['final'][0]['source_groups'] = ['train-a'];variations.append(source_leak)
        duplicate = copy.deepcopy(base);duplicate['final'][1]['task_id'] = 'final-a';variations.append(duplicate)
        variant = copy.deepcopy(base);variant['final'][1]['instance_group'] = 'final-a';variations.append(variant)
        leaked_answer = copy.deepcopy(base);leaked_answer['final'][0]['answer'] = 'not permitted here';variations.append(leaked_answer)
        copied_package = copy.deepcopy(base);copied_package['final'][0]['package_sha256'] = copied_package['train'][0]['package_sha256'];variations.append(copied_package)
        repeated_package = copy.deepcopy(base);repeated_package['final'][1]['package_sha256'] = repeated_package['final'][0]['package_sha256'];variations.append(repeated_package)
        for index, manifest in enumerate(variations):
            with self.subTest(index=index), self.assertRaises(ValueError):
                planner.validate_splits(manifest, 1, 2, 'shared_allowed')
        with self.assertRaisesRegex(ValueError, 'task counts'):
            planner.validate_splits(base, 1, 100, 'shared_allowed')

    def test_cli_creates_only_requested_new_artifacts_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config, output = root / 'config.json', root / 'plan.json'
            subprocess.run([sys.executable, str(FILE), 'example', '--out', str(config)], check=True, capture_output=True)
            subprocess.run([sys.executable, str(FILE), 'plan', '--config', str(config), '--out', str(output)], check=True, capture_output=True)
            result = json.loads(output.read_text())
            self.assertEqual(result['status'], 'offline_proposal_only')
            before = output.read_bytes()
            rejected = subprocess.run([sys.executable, str(FILE), 'plan', '--out', str(output)], capture_output=True)
            self.assertEqual(rejected.returncode, 2)
            self.assertEqual(output.read_bytes(), before)
            self.assertEqual(sorted(x.name for x in root.iterdir()), ['config.json', 'plan.json'])


if __name__ == '__main__':
    unittest.main()
