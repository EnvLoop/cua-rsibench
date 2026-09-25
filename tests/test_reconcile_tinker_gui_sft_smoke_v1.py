"""A provider usage event must be attributed before a nominal cost is stated."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'reconcile_tinker_gui_sft_smoke_v1',
    ROOT / 'tools/reconcile_tinker_gui_sft_smoke_v1.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def fixture():
    pricing = [{'tinker_id': 'Qwen/Qwen3.8-27B', 'type': 'Hybrid + Vision',
                'prefill': '$1.86', 'cached_prefill': '$0.372',
                'sample': '$5.595', 'train': '$4.103'}]
    session = 'private-test-session'
    usage = {
        'schema': 'envloop-price777-private-billing-filter-v1',
        'window_start': '2026-09-25T02:00:00Z',
        'window_end': '2026-09-25T04:00:00Z',
        'sessions': {session: {'user_metadata': {
            'purpose': MODULE.PURPOSE, 'split': 'train',
            'source_task_id': '777'}}},
        'events': [
            {'session_id': session, 'base_model': MODULE.MODEL,
             'bucket_start': '2026-09-25T02:00:00Z',
             'event_info': {'type': 'training', 'token_count': 2299}},
            {'session_id': session, 'base_model': MODULE.MODEL,
             'bucket_start': '2026-09-25T02:00:00Z',
             'event_info': {'type': 'sampling_prefill', 'token_count': 2285,
                            'cached': False}},
            {'session_id': session, 'base_model': MODULE.MODEL,
             'bucket_start': '2026-09-25T02:00:00Z',
             'event_info': {'type': 'sampling_sample', 'token_count': 15}},
        ],
    }
    return usage, pricing


class BillingReconciliationTests(unittest.TestCase):
    def test_provider_token_counts_and_published_rates_remain_distinct_from_invoice(self):
        usage, pricing = fixture()
        result = MODULE.reconcile(usage, pricing, usage_sha256='a'*64,
                                  pricing_sha256='b'*64)
        self.assertEqual(result['provider_reported_billed_tokens_by_type'], {
            'training': 2299, 'sampling_prefill_uncached': 2285,
            'sampling_prefill_cached': 0, 'sampling_sample': 15})
        self.assertEqual(result['published_rate_nominal_token_subtotal_usd'],
                         '0.013766822')
        self.assertIsNone(result['provider_invoice_usd'])
        self.assertEqual(result['official_final_results_added'], 0)

    def test_wrong_session_or_model_cannot_be_attributed_to_smoke(self):
        usage, pricing = fixture()
        bad = copy.deepcopy(usage)
        next(iter(bad['sessions'].values()))['user_metadata']['source_task_id'] = '486'
        with self.assertRaisesRegex(ValueError, 'session metadata'):
            MODULE.reconcile(bad, pricing, usage_sha256='a'*64,
                             pricing_sha256='b'*64)
        bad = copy.deepcopy(usage)
        bad['events'][0]['base_model'] = 'other-model'
        with self.assertRaisesRegex(ValueError, 'billing event identity'):
            MODULE.reconcile(bad, pricing, usage_sha256='a'*64,
                             pricing_sha256='b'*64)

    def test_missing_sample_or_cache_flag_is_not_a_complete_reconciliation(self):
        usage, pricing = fixture()
        bad = copy.deepcopy(usage)
        bad['events'].pop()
        with self.assertRaisesRegex(ValueError, 'one-step training'):
            MODULE.reconcile(bad, pricing, usage_sha256='a'*64,
                             pricing_sha256='b'*64)
        bad = copy.deepcopy(usage)
        del bad['events'][1]['event_info']['cached']
        with self.assertRaisesRegex(ValueError, 'prefill cache flag'):
            MODULE.reconcile(bad, pricing, usage_sha256='a'*64,
                             pricing_sha256='b'*64)


if __name__ == '__main__':
    unittest.main()
