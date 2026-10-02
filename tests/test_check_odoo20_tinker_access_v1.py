import unittest
from unittest.mock import patch
from pathlib import Path
from hashlib import sha256
import json
import tempfile
from tools import check_odoo20_tinker_access_v1 as checker
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

    def _fake_run(self, close_error=False):
        events = []
        class Response:
            def model_dump(self, mode):
                return {'supported_models': [{'model_name': MODEL}]}
        class CloseFuture:
            def result(self, timeout):
                events.append('close_awaited')
                if close_error:
                    raise TimeoutError('synthetic close timeout')
        class Service:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
            def get_server_capabilities(self):
                events.append('capabilities_read')
                return Response()
            def close(self, status):
                events.append('close_submitted')
                return CloseFuture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            terminal = root/'terminal.private.json'
            terminal.write_text(json.dumps({'exit_code': 1, 'automatic_restarts': 0, 'ended_at': 1}))
            terminal.chmod(0o600)
            with patch.object(checker, 'ROOT', root), patch(
                'enterprise_fallback.odoo18.twenty_task_trial_training_v1.no_retry_service_class',
                return_value=Service):
                value, _ = checker.run(terminal_path=terminal,
                    terminal_sha=sha256(terminal.read_bytes()).hexdigest(),
                    output_root=root/'work/synthetic-access.private')
        return value, events

    def test_access_waits_for_actual_close_future_before_ready(self):
        value, events = self._fake_run()
        self.assertEqual(events, ['capabilities_read', 'close_submitted', 'close_awaited'])
        self.assertEqual(value['status'], 'ready')
        self.assertTrue(value['owned_close_awaited'])
        self.assertEqual(value['checker_source_sha256'], sha256(Path(checker.__file__).read_bytes()).hexdigest())

    def test_submitted_but_unsettled_close_does_not_authorize_ready(self):
        value, events = self._fake_run(close_error=True)
        self.assertEqual(value['status'], 'not_ready')
        self.assertFalse(value['owned_close_awaited'])
        self.assertIn('close_awaited', events)


if __name__ == '__main__':
    unittest.main()
