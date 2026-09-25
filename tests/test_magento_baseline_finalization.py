"""Trusted Magento baseline finalization cannot mask business side effects."""

from __future__ import annotations

import copy
import unittest

from tools import finalize_magento_normalized_baseline_v1 as finish


CASE = {'task_id': 'magento-catalog-0123456789abcdef'}


def state():
    return {'schema': 'envloop-magento-catalog-saved-state-v1',
            'task_id': CASE['task_id'], 'page_id': 8,
            'search': {'full_sha256': 'a'},
            'database': {
                'quote': {'content_sha256': 'b'},
                'prices': {'111': {'price': '52.000000'}},
                'hashes': {'other_catalog': {'catalog_product_entity': 'c'},
                           'target_nonprice': {'catalog_product_entity': 'd'},
                           'business': {'sales_order': 'e'},
                           'full': {'catalog_product_entity': 'before',
                                    'sales_order': 'e'}},
                'target_rows': {
                    'catalog_product_entity': [{'entity_id': 111,
                                                'updated_at': '2026-09-25 02:23:04',
                                                'sku': 'SAMPLE'}],
                    'cataloginventory_stock_item': [{'product_id': 111,
                                                     'manage_stock': 1}],
                }}}


class MagentoBaselineFinalizationTests(unittest.TestCase):
    def test_only_updated_at_may_change(self):
        before = state()
        after = copy.deepcopy(before)
        after['database']['target_rows']['catalog_product_entity'][0][
            'updated_at'] = finish.FROZEN_TIMESTAMP
        after['database']['hashes']['full']['catalog_product_entity'] = 'after'
        finish.validate_only_timestamp_changed(CASE, before, after)
        after['database']['target_rows']['cataloginventory_stock_item'][0][
            'manage_stock'] = 0
        with self.assertRaisesRegex(ValueError, 'non-entity target row'):
            finish.validate_only_timestamp_changed(CASE, before, after)


if __name__ == '__main__':
    unittest.main()
