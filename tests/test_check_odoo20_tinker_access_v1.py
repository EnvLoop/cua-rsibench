import unittest
from tools.check_odoo20_tinker_access_v1 import MODEL, result_receipt


def receipt(**changes):
    values = dict(terminal_ref={'path': 'private', 'sha256': 'a'*64},
        terminal={'exit_code': 1, 'automatic_restarts': 0, 'ended_at': 10},
        started_at=11, ended_at=12,
        capabilities={'supported_models': [{'model_name': MODEL, 'trainable': True, 'sampleable': True}]},
        status_code=200, error_type=None, close_returned=True)
    values.update(changes)
    return result_receipt(**values)


class AccessReceiptTests(unittest.TestCase):
    def test_real_success_can_authorize_readonly_continuation(self):
        value = receipt()
        self.assertEqual(value['status'], 'ready')
        self.assertEqual(value['training_calls'], value['model_sampling_calls'])
        self.assertEqual(value['training_calls'], 0)
        self.assertIsNone(value['actual_cost_usd'])


    def test_billing_denial_does_not_authorize_continuation(self):
        value = receipt(capabilities=None, status_code=402, error_type='BillingError')
        self.assertEqual(value['status'], 'not_ready')
        self.assertEqual(value['provider_http_status'], 402)


    def test_stale_check_missing_model_and_incomplete_close_fail_closed(self):
        self.assertEqual(receipt(started_at=9)['status'], 'not_ready')
        self.assertEqual(receipt(capabilities={'supported_models': []})['status'], 'not_ready')
        self.assertEqual(receipt(close_returned=False)['status'], 'not_ready')
        self.assertEqual(receipt(capabilities={'supported_models': [
            {'model_name': MODEL, 'sampleable': False}]})['status'], 'not_ready')


if __name__ == '__main__':
    unittest.main()
