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
    # Reserve one development-exposed family and one train-source family.
    for row in rows[:4]:
        row['intent_template_id'] = 240
    rows[0]['task_id'] = 538
    rows[0]['instantiation_dict'] = {'order_id': '299'}
    for row in rows[4:8]:
        row['intent_template_id'] = 275
        row['eval'] = [{'evaluator': 'AgentResponseEvaluator',
                        'expected': {'task_type': 'mutate', 'status': 'SUCCESS'}},
                       {'evaluator': 'NetworkEventEvaluator',
                        'expected': {'url': '/cms/page/save/back/edit'}}]
    rows[4]['task_id'] = 486
    rows[4]['eval'][1]['expected']['post_data'] = {'page_id': '1'}
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
        self.assertEqual(record['source_entity_hints'], ['order_id:299'])

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
        for row, task_id in zip(rows[8:11], (423, 491, 790)):
            row['task_id'] = task_id
        result = plan.manifest(rows, set())
        all_ids = {row['task_id'] for name in ('selection', 'provisional_final')
                   for row in result['task_sets'][name]}
        self.assertFalse({423, 491, 790} & all_ids)
        self.assertEqual(result['counts']['quarantined_task_ids'], 17)

    def test_train_reserved_template_and_explicit_entity_are_absent_from_both_splits(self):
        rows = fake_rows()
        rows[12]['eval'][1]['expected']['post_data'] = {'page_id': '1'}
        result = plan.manifest(rows, set())
        selected = result['task_sets']['selection'] + result['task_sets']['provisional_final']
        self.assertFalse(any(row['template_group'] == 'shopping_admin:240' for row in selected))
        self.assertFalse(any(row['template_group'] == 'shopping_admin:275' for row in selected))
        self.assertFalse(any('page_id:1' in row['source_entity_hints'] for row in selected))
        self.assertEqual(result['counts']['train_reserved_entity_overlap_excluded_tasks'], 1)

    def test_training_page_id_is_extracted_from_network_form_only(self):
        train = fake_rows()[4]
        self.assertNotIn('page_id', train['instantiation_dict'])
        self.assertEqual(plan.entity_hints(train), ['order_id:1004', 'page_id:1'])

    def test_non_success_retrieval_cannot_refill_success_final_queue(self):
        rows = fake_rows()
        rows[16]['eval'][0]['expected']['status'] = 'NOT_FOUND_ERROR'
        result = plan.manifest(rows, set())
        chosen = result['task_sets']['selection'] + result['task_sets']['provisional_final']
        self.assertFalse(any(item['task_id'] == rows[16]['task_id'] for item in chosen))
        self.assertEqual(result['counts']['source_non_success_outcomes_excluded'],
                         {'NOT_FOUND_ERROR': 1})


if __name__ == '__main__':
    unittest.main()
