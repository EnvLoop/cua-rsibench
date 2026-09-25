"""Saved-state score rejects partial and collateral Magento catalog edits."""

from __future__ import annotations

import copy
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from magento_catalog_factory import seed, verify
from tools import audit_magento_original_fresh_reset_v1 as reset_audit


CASE = {
    'task_id': 'magento-catalog-0123456789abcdef',
    'package_sha256': 'f' * 64,
    'parent_id': 126,
    'parent_sku': 'PARENT-126',
    'quote_page_title': 'Supplier cost review 0123456789abcdef',
    'quote_page_body': '<p>Private source</p>',
    'quote_page_body_sha256': hashlib.sha256(b'<p>Private source</p>').hexdigest(),
    'target_variants': [
        {'entity_id': 111, 'sku': 'A', 'initial_price': '52.00',
         'target_price': '47.05'},
        {'entity_id': 114, 'sku': 'B', 'initial_price': '52.00',
         'target_price': '48.10'},
    ],
    'untouched_comparators': [{'entity_id': 112, 'sku': 'C', 'price': '52.00'}],
}


def baseline():
    return {'schema': 'envloop-magento-catalog-saved-state-v1',
            'task_id': CASE['task_id'], 'page_id': 8,
            'database': {
                'prices': {str(row['entity_id']):
                           {'sku': row['sku'], 'parent_id': 126,
                            'price': row.get('initial_price', row.get('price'))}
                           for row in CASE['target_variants'] +
                           CASE['untouched_comparators']},
                'quote': {'title': CASE['quote_page_title'],
                          'identifier': 'envloop-quote-0123456789abcdef',
                          'is_active': 1, 'store_id': 0,
                          'content_sha256': CASE['quote_page_body_sha256']},
                'hashes': {'other_catalog': {'catalog_product_entity': 'a'},
                           'target_nonprice': {'catalog_product_entity': 'b'},
                           'business': {'sales_order': 'c'},
                           'full': {'catalog_product_entity': 'd'}}},
            'search': {'document_count': 181, 'full_sha256': 'e',
                       'other_documents_sha256': 'f',
                       'parent_document_sha256': 'g'}}


def positive():
    state = copy.deepcopy(baseline())
    for row in CASE['target_variants']:
        state['database']['prices'][str(row['entity_id'])]['price'] = row['target_price']
    state['database']['hashes']['full']['catalog_product_entity'] = 'changed'
    state['search']['full_sha256'] = 'changed'
    state['search']['parent_document_sha256'] = 'changed'
    return state


class MagentoCatalogSavedStateTests(unittest.TestCase):
    def test_positive_requires_all_prices_and_preservation(self):
        before = baseline()
        after = positive()
        self.assertEqual(verify.score_saved_state(CASE, before, after)['score'], 1.0)
        after['database']['prices']['114']['price'] = '52.00'
        self.assertEqual(verify.score_saved_state(CASE, before, after)['failure_codes'],
                         ['target_price_or_identity_mismatch'])

    def test_wrong_variant_quote_change_and_business_side_effect_fail(self):
        before = baseline()
        after = positive()
        after['database']['prices']['112']['price'] = '47.05'
        after['database']['hashes']['other_catalog']['catalog_product_entity'] = 'x'
        after['database']['hashes']['business']['sales_order'] = 'x'
        after['database']['quote']['content_sha256'] = 'x'
        after['search']['other_documents_sha256'] = 'x'
        failed = verify.score_saved_state(CASE, before, after)
        self.assertEqual(failed['score'], 0.0)
        self.assertEqual(set(failed['failure_codes']), {
            'source_quote_changed', 'untouched_variant_changed',
            'other_catalog_changed', 'business_changed',
            'unrelated_search_documents_changed'})

    def test_starting_price_drift_and_reset_require_exact_identity(self):
        before = baseline()
        before['database']['prices']['111']['price'] = '46.00'
        with self.assertRaisesRegex(ValueError, 'baseline variant'):
            verify.score_saved_state(CASE, before, positive())
        original = baseline()
        verify.check_exact_reset(original, copy.deepcopy(original))
        changed = copy.deepcopy(original)
        changed['search']['full_sha256'] = 'not reset'
        with self.assertRaisesRegex(ValueError, 'exact reset'):
            verify.check_exact_reset(original, changed)

    def test_quote_seed_keeps_source_out_of_process_arguments(self):
        fake = SimpleNamespace(returncode=0, stdout=json.dumps({
            'page_id': 8, 'variant_count': 3,
            'quote_page_body_sha256': CASE['quote_page_body_sha256']}))
        with patch.object(seed, 'check_clone', return_value={'image_sha256': seed.IMAGE}), \
             patch.object(seed.subprocess, 'run', return_value=fake) as run:
            receipt = seed.seed(CASE, 'envloop-magento-original-control', 7794, 7795)
        args, kwargs = run.call_args
        self.assertEqual(receipt['status'], 'trusted_fixture_seeded_not_gui_admitted')
        self.assertIn(CASE['quote_page_body'], kwargs['input'])
        self.assertNotIn(CASE['quote_page_body'], ' '.join(args[0]))
        self.assertEqual(kwargs['timeout'], 120)

    def test_native_sidecar_requires_pinned_image_and_shared_network(self):
        app = {'State': {'Running': True},
               'NetworkSettings': {'Networks': {verify.NATIVE_SEARCH_NETWORK: {}}}}
        search = {'State': {'Running': True},
                  'Image': verify.NATIVE_SEARCH_IMAGE, 'Mounts': [],
                  'NetworkSettings': {'Networks': {verify.NATIVE_SEARCH_NETWORK: {}}}}
        response = SimpleNamespace(stdout=json.dumps([app, search]))
        with patch.object(verify.subprocess, 'run', return_value=response):
            verify.check_native_search_sidecar('envloop-magento-original-control')
        search['Image'] = 'sha256:' + '0' * 64
        response = SimpleNamespace(stdout=json.dumps([app, search]))
        with patch.object(verify.subprocess, 'run', return_value=response):
            with self.assertRaisesRegex(ValueError, 'sidecar/image/network'):
                verify.check_native_search_sidecar('envloop-magento-original-control')

    def test_fresh_reset_requires_distinct_clone_and_identical_state(self):
        first = baseline()
        second = copy.deepcopy(first)
        seed_one = {'status': 'trusted_fixture_seeded_not_gui_admitted',
                    'task_id': CASE['task_id'],
                    'package_sha256': CASE['package_sha256'],
                    'quote_page_body_sha256': CASE['quote_page_body_sha256'],
                    'page_id': 8,
                    'clone': {'image_sha256': seed.IMAGE, 'mount_count': 0,
                              'container_id_sha256': '1' * 64,
                              'loopback_ports': [7794, 7795]}}
        seed_two = copy.deepcopy(seed_one)
        seed_two['clone']['container_id_sha256'] = '2' * 64
        def bound(seed_receipt, state, sidecar_id):
            digest = reset_audit.snapshot_sha256(state)
            runtime = {'schema': 'envloop-magento-native-sidecar-runtime-private-v1',
                       'app': seed_receipt['clone'],
                       'sidecar_image_sha256': verify.NATIVE_SEARCH_IMAGE,
                       'sidecar_id_sha256': sidecar_id,
                       'network': verify.NATIVE_SEARCH_NETWORK,
                       'baseline_sha256': digest}
            finalization = {'status': 'normalized_baseline_frozen_not_gui_admitted',
                            'task_id': CASE['task_id'],
                            'package_sha256': CASE['package_sha256'],
                            'clone': seed_receipt['clone'],
                            'search_backend': verify.NATIVE_SEARCH_HOST,
                            'normalized_baseline_sha256': digest}
            return runtime, finalization
        first_runtime, first_finalization = bound(seed_one, first, '3' * 64)
        second_runtime, second_finalization = bound(seed_two, second, '4' * 64)
        self.assertTrue(reset_audit.audit(CASE, first, second,
                                          seed_one, seed_two,
                                          first_runtime, second_runtime,
                                          first_finalization,
                                          second_finalization)['fresh_clone_reset_passed'])
        seed_two['clone']['container_id_sha256'] = '1' * 64
        with self.assertRaisesRegex(ValueError, 'same container'):
            reset_audit.audit(CASE, first, second, seed_one, seed_two,
                              first_runtime, second_runtime,
                              first_finalization, second_finalization)
        seed_two['clone']['container_id_sha256'] = '2' * 64
        second_runtime['sidecar_id_sha256'] = '3' * 64
        with self.assertRaisesRegex(ValueError, 'same search container'):
            reset_audit.audit(CASE, first, second, seed_one, seed_two,
                              first_runtime, second_runtime,
                              first_finalization, second_finalization)


if __name__ == '__main__':
    unittest.main()
