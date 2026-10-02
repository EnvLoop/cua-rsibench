"""A real Magento catalog has enough disjoint parents; a source count is not GUI admission."""

from __future__ import annotations

import json
from unittest.mock import patch
import unittest

from magento_catalog_factory import plan as factory


def inventory():
    parents = []
    for parent_id in range(1, 147):
        price = str(20 + parent_id % 35)
        parents.append({
            'parent_id': parent_id, 'parent_sku': f'CONFIG-{parent_id:03d}',
            'children': [{'entity_id': parent_id * 1000 + index,
                          'sku': f'CONFIG-{parent_id:03d}-V{index:02d}',
                          'price': price} for index in range(10)],
        })
    return {'schema': factory.INVENTORY_SCHEMA,
            'docker_image_sha256': 'sha256:' + 'a' * 64,
            'quarantined_parent_ids': [1],
            'parents': parents}


class MagentoCatalogFactoryTests(unittest.TestCase):
    def setUp(self):
        self.inventory = inventory()
        self.raw_hash = factory.digest(self.inventory)
        self.seed = 'test-private-seed-with-at-least-thirty-two-characters'

    def build(self, seed=None):
        with patch.object(factory, 'INVENTORY_SHA256', self.raw_hash):
            return factory.build(self.inventory, self.raw_hash, seed or self.seed)

    def test_genuinely_different_causal_templates_and_parent_source_splits(self):
        result = self.build()
        self.assertEqual(result['split_counts'], {
            'train': 20, 'selection': 20, 'official_candidate': 100})
        self.assertEqual(result['final_source_family_count'], 100)
        self.assertEqual(set(result['final_template_counts'].values()), {25})
        self.assertEqual(result['official_final_admitted_count'], 0)
        self.assertFalse(result['model_scores_present'])
        parent_sets = [{row['parent_id'] for row in result['cases'][split]}
                       for split in factory.SPLITS]
        self.assertEqual(len(set.union(*parent_sets)), 140)
        self.assertTrue(all(left.isdisjoint(right) for i, left in enumerate(parent_sets)
                            for right in parent_sets[i+1:]))
        self.assertTrue(all(1 not in parents for parents in parent_sets))
        self.assertTrue(set(result['train_template_groups']).isdisjoint(
            result['final_template_groups']))
        self.assertTrue(set(result['selection_template_groups']).isdisjoint(
            result['final_template_groups']))
        for case in result['cases']['official_candidate']:
            self.assertEqual(len(case['target_variants']), 5)
            self.assertIn('Content > Pages', case['instruction'])
            self.assertIn('<table>', case['quote_page_body'])
            self.assertTrue(all(row['initial_price'] != row['target_price']
                                for row in case['target_variants']))
            self.assertEqual(case['package_sha256'], factory.digest({
                key: value for key, value in case.items()
                if key != 'package_sha256'}))
            self.assertFalse(case['official_final_admitted'])

    def test_rebuild_deterministic_and_seed_change_repartitions(self):
        first = self.build()
        second = self.build()
        self.assertEqual(factory.digest(first), factory.digest(second))
        changed = self.build(self.seed + '-different')
        self.assertNotEqual(first['private_seed_sha256'], changed['private_seed_sha256'])
        self.assertNotEqual(first['cases']['official_candidate'][0]['parent_id'],
                            changed['cases']['official_candidate'][0]['parent_id'])

    def test_short_seed_and_insufficient_parent_pool_fail_closed(self):
        with patch.object(factory, 'INVENTORY_SHA256', self.raw_hash):
            with self.assertRaisesRegex(ValueError, 'private seed mismatch'):
                factory.build(self.inventory, self.raw_hash, 'short')
        reduced = inventory()
        reduced['parents'] = reduced['parents'][:120]
        changed_hash = factory.digest(reduced)
        with patch.object(factory, 'INVENTORY_SHA256', changed_hash):
            with self.assertRaisesRegex(ValueError, 'insufficient disjoint'):
                factory.build(reduced, changed_hash, self.seed)


if __name__ == '__main__':
    unittest.main()
