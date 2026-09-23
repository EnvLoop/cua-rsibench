import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from build_factory_report import validate_study


class RecoveryPublicationTests(unittest.TestCase):
    def study(self):
        names = [f'task-{n}' for n in range(6)]
        evaluation = {'status': 'scored', 'score': 0, 'expected_tasks': names,
                      'tasks': [{'task': name, 'score': 0, 'error_type': None} for name in names]}
        original = copy.deepcopy(evaluation)
        original.update(status='infrastructure_error', score=None)
        original['tasks'][0].update(score=1)
        original['tasks'][1].update(score=None, error_type='ConnectError')
        recovery = {'policy_kind': 'full_suite_replay', 'original_rows_reused': False,
                    'new_independent_repetition': False, 'new_research_seed': False,
                    'logical_comparison_slot': 'base-1', 'retried_tasks': names,
                    'amendment_sha256': 'bound', 'chunk_plan_sha256': {'chunk-0': 'bound'}}
        return {'audit_pass': True, 'search_finished': True, 'all_final_executions_finished': True,
                'all_final_recoveries_finished': True, 'teacher': 'gpt-5.6-sol', 'student': 'Qwen/Qwen3.5-4B',
                'selection_tasks': 3, 'final_tasks': 6,
                'training': {'profile': 'factory-v1', 'steps': 32, 'batch_size': 2, 'rank': 8,
                             'learning_rate': .0001, 'seed': 23, 'token_cap_per_run': 262144},
                'sampling': {'max_tokens': 512, 'temperature': 0, 'seed': 23},
                'campaigns': [{'name': 'researcher', 'researcher': 'exact-model', 'selection_frozen': True,
                               'pending_training': 0, 'attempts': [{}], 'selection_score': 0,
                               'training_token_budget': 1048576, 'max_attempts': 5}],
                'final_comparison': {'bindings': {'base': ['base-1'], 'researcher': ['base-1']},
                                     'repetitions': 1, 'executions': [{'label': 'base-1'}]},
                'final_executions': [{'label': 'base-1', 'selection_precedes_test': True,
                                      'evaluation': original, 'recovered_evaluation': evaluation, 'recovery': recovery}]}

    def test_whole_suite_replay_can_have_different_fresh_outcomes_without_mutating_original(self):
        data = self.study()
        original = copy.deepcopy(data['final_executions'][0]['evaluation'])
        validate_study(data, {'exact-model'})
        self.assertEqual(data['final_executions'][0]['evaluation'], original)

    def test_replay_cannot_claim_a_new_sample_or_reuse_original_rows(self):
        for field in ('new_independent_repetition', 'new_research_seed', 'original_rows_reused'):
            data = self.study()
            data['final_executions'][0]['recovery'][field] = True
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_study(data, {'exact-model'})

    def test_scored_original_cannot_be_replayed(self):
        data = self.study()
        run = data['final_executions'][0]
        run['evaluation'] = copy.deepcopy(run['recovered_evaluation'])
        with self.assertRaisesRegex(ValueError, 'scored original'):
            validate_study(data, {'exact-model'})

    def test_partial_retry_policy_cannot_change_an_originally_scored_task(self):
        data = self.study()
        data['final_executions'][0]['recovery']['policy_kind'] = 'build_only'
        with self.assertRaisesRegex(ValueError, 'originally scored'):
            validate_study(data, {'exact-model'})


if __name__ == '__main__':
    unittest.main()
