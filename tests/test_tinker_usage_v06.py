"""Offline billing reconciliation tests; no provider calls or private IDs."""
import copy
import unittest

from tools.reconcile_tinker_usage_v06 import reconcile


START = '2026-09-24T00:00:00Z'
END = '2026-09-24T02:00:00Z'
PRICE = [{'tinker_id': 'Qwen/Qwen3.8-27B', 'type': 'Hybrid + Vision',
          'prefill': '$1.86', 'cached_prefill': '$0.372',
          'sample': '$5.595', 'train': '$4.103'}]


def event(kind, count=None, *, session='private-session-alpha', cached=None, model='Qwen/Qwen3.8-27B'):
    info = {'type': kind}
    if count is not None:
        info['token_count'] = count
    if cached is not None:
        info['cached'] = cached
    if kind == 'storage':
        info['gigabyte_hours'] = 4.0
    return {'bucket_start': START, 'bucket_end': '2026-09-24T01:00:00Z',
            'base_model': model, 'session_id': session, 'event_info': info}


def fixture():
    return {'sessions': {
        'private-session-alpha': {'user_metadata': {'purpose': 'scale-vision-proxy-v1',
                                                     'campaign_id': 'magento-sol6-seed23'}},
        'private-session-beta': {'user_metadata': {'purpose': 'scale-vision-proxy-v1',
                                                    'campaign_id': 'excel-astra-seed23'}},
        'private-training-session': {'user_metadata': {'purpose': 'cua-v06-training',
                                                        'campaign_id': 'magento-sol6-seed23'}},
    }, 'data': [
        event('training', 1_000_000, session='private-training-session'),
        event('sampling_prefill', 1_000_000, cached=False),
        event('sampling_prefill', 1_000_000, cached=True),
        event('sampling_sample', 1_000_000),
        event('storage'),
        event('sampling_sample', 9_000_000, session='private-session-beta'),
    ]}


class TinkerUsageTests(unittest.TestCase):
    def calculate(self, usage=None, pricing=None):
        return reconcile(usage or fixture(), pricing or PRICE,
                         campaign_id='magento-sol6-seed23',
                         window_start=START, window_end=END)

    def test_attributed_cached_uncached_train_sample_and_unpriced_storage(self):
        result = self.calculate()
        self.assertEqual(result['matched_event_count'], 5)
        self.assertEqual(result['unpriced_campaign_event_count'], 1)
        self.assertEqual(result['billed_tokens_by_type'], {
            'training': 1_000_000, 'sampling_prefill_uncached': 1_000_000,
            'sampling_prefill_cached': 1_000_000, 'sampling_sample': 1_000_000})
        self.assertEqual(result['nominal_token_rate_subtotal_usd'], '11.930')
        self.assertIsNone(result['all_in_cost_usd'])
        self.assertNotIn('private-session-alpha', str(result))
        self.assertNotIn('private-session-beta', str(result))
        self.assertNotIn('private-training-session', str(result))

    def test_missing_session_is_unattributed_and_never_assigned_to_campaign(self):
        usage = fixture()
        usage['data'].append(event('sampling_sample', 4_000_000, session='unknown'))
        result = self.calculate(usage=usage)
        self.assertEqual(result['unattributed_org_event_count'], 1)
        self.assertEqual(result['nominal_token_rate_subtotal_usd'], '11.930')

    def test_wrong_model_and_invalid_billable_event_fail_closed(self):
        usage = fixture()
        usage['data'].append(event('sampling_sample', 200, model='other/model'))
        self.assertEqual(self.calculate(usage=usage)['unpriced_campaign_event_count'], 2)
        for change in (lambda u: u['data'][0]['event_info'].update(token_count=True),
                       lambda u: u['data'][1]['event_info'].pop('cached'),
                       lambda u: u['data'][0].update(bucket_start='2026-09-25T00:00:00Z')):
            bad = copy.deepcopy(fixture())
            change(bad)
            with self.assertRaises(ValueError):
                self.calculate(usage=bad)

    def test_price_and_window_identity_are_exact(self):
        with self.assertRaisesRegex(ValueError, 'exact Qwen'):
            self.calculate(pricing=[PRICE[0] | {'tinker_id': 'other/model'}])
        with self.assertRaisesRegex(ValueError, 'UTC hour boundary'):
            reconcile(fixture(), PRICE, campaign_id='magento-sol6-seed23',
                      window_start='2026-09-24T00:30:00Z', window_end=END)
        with self.assertRaisesRegex(ValueError, 'invalid campaign'):
            reconcile(fixture(), PRICE, campaign_id='../wrong',
                      window_start=START, window_end=END)


if __name__ == '__main__':
    unittest.main()
