"""The Magento admission backlog must isolate templates and fail closed."""

from __future__ import annotations

import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import plan_magento_final_candidates_v06 as plan  # noqa: E402


def fake_rows() -> list[dict]:
    rows = []
    next_id = 1000
    for template in range(40):
        kind = ('mutate', 'retrieve', 'navigate')[template % 3]
        for _ in range(4):
            rows.append({'sites': ['shopping_admin'], 'task_id': next_id,
                         'intent_template_id': template,
                         'instantiation_dict': {'order_id': str(next_id)},
                         'eval': [{'evaluator': 'AgentResponseEvaluator',
                                   'expected': {'task_type': kind, 'status': 'SUCCESS'}},
                                  *([{'evaluator': 'NetworkEventEvaluator',
                                      'expected': {'url': '/target'}}]
                                    if kind != 'retrieve' else [])]})
            next_id += 1
    for _ in range(6):
        rows.append({'sites': ['shopping_admin'], 'task_id': next_id,
                     'intent_template_id': 742,
                     'instantiation_dict': {},
                     'eval': [{'evaluator': 'AgentResponseEvaluator',
                               'expected': {'task_type': 'mutate', 'status': 'SUCCESS'}},
                              {'evaluator': 'NetworkEventEvaluator',
                               'expected': {'url': '/product/save'}}]})
        next_id += 1
    for _ in range(16):
        rows.append({'sites': ['shopping_admin'], 'task_id': next_id,
                     'intent_template_id': 999,
                     'instantiation_dict': {},
                     'eval': [{'evaluator': 'AgentResponseEvaluator',
                               'expected': {'task_type': 'retrieve', 'status': 'SUCCESS'}}]})
        next_id += 1
    assert len(rows) == 182
    return rows


class MagentoBacklogTests(unittest.TestCase):
    def test_one_hundred_template_disjoint_candidates_and_quarantine(self):
        rows = fake_rows()
        hard = {row['task_id'] for row in rows if row['task_id'] % 2 == 0}
        result = plan.manifest(rows, hard)
        selection = result['task_sets']['selection']
        final = result['task_sets']['provisional_final']
        self.assertEqual((len(selection), len(final)), (20, 100))
        self.assertFalse({row['template_group'] for row in selection} &
                         {row['template_group'] for row in final})
        self.assertFalse(any(row['template_group'] == 'shopping_admin:742'
                             for row in selection + final))
        self.assertEqual(result['counts']['provisional_final_officially_admitted'], 0)
        self.assertEqual(result, plan.manifest(rows, hard))
        self.assertEqual({row['task_type'] for row in selection},
                         {'mutate', 'retrieve', 'navigate'})

    def test_network_event_does_not_claim_persisted_mutation(self):
        row = fake_rows()[0]
        record = plan.task_record(row, {row['task_id']})
        self.assertEqual(record['task_type'], 'mutate')
        self.assertTrue(record['network_only_for_mutation'])
        self.assertTrue(record['requires_saved_state_oracle'])
        self.assertFalse(record['requires_no_state_change_oracle'])
        self.assertEqual(record['expected_status'], 'SUCCESS')
        self.assertTrue(record['official_hard_subset'])
        self.assertEqual(record['source_entity_hints'], ['order_id:1000'])

    def test_unexpected_evaluator_or_insufficient_pool_fails(self):
        row = fake_rows()[0]
        bad = copy.deepcopy(row)
        bad['eval'].append({'evaluator': 'UnknownEvaluator'})
        with self.assertRaisesRegex(ValueError, 'unexpected extra evaluator'):
            plan.evaluation_shape(bad)
        with self.assertRaisesRegex(ValueError, 'fewer than 100 final candidates'):
            plan.choose(fake_rows(), set(), final_count=200)

    def test_source_hash_drift_is_rejected_before_parsing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, hard = root / 'source.json', root / 'hard.json'
            source.write_text('[]')
            hard.write_text('{"task_ids":[]}')
            with self.assertRaisesRegex(ValueError, 'differ from pinned'):
                plan.source_rows(source, hard)

    def test_policy_denial_is_not_counted_as_a_saved_mutation(self):
        row = fake_rows()[0]
        row['eval'] = [{'evaluator': 'AgentResponseEvaluator',
                        'expected': {'task_type': 'mutate',
                                     'status': 'ACTION_NOT_ALLOWED_ERROR'}}]
        shape = plan.evaluation_shape(row)
        self.assertFalse(shape['successful_mutation_expected'])
        self.assertFalse(shape['requires_saved_state_oracle'])
        self.assertTrue(shape['requires_no_state_change_oracle'])
        self.assertFalse(shape['network_only_for_mutation'])

    def test_pinned_problem_ids_are_excluded_but_other_family_members_remain(self):
        rows = fake_rows()
        for row, task_id in zip(rows[:3], (423, 491, 790)):
            row['task_id'] = task_id
        result = plan.manifest(rows, set())
        all_ids = {row['task_id'] for name in ('selection', 'provisional_final')
                   for row in result['task_sets'][name]}
        self.assertFalse({423, 491, 790} & all_ids)
        self.assertEqual(result['counts']['quarantined_task_ids'], 9)


if __name__ == '__main__':
    unittest.main()
