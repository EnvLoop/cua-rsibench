"""Offline boundaries plus the exact upstream deterministic task-157 evaluator."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('magento_smoke', ROOT / 'tools/qualify_magento_navigation_v1.py')
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)
SOURCE = ROOT / 'work/scale-v06/sources/webarena-verified'


def event(path, status=200):
    return {'request': {'url': smoke.BASE + path, 'method': 'GET',
                        'headers': [{'name': 'Accept', 'value': 'text/html'}]},
            'response': {'status': status, 'headers': [], 'redirectURL': '', 'content': {}}}


class MagentoBoundaryTests(unittest.TestCase):
    def test_measurement_allows_only_local_reads_while_setup_allows_local_login(self):
        self.assertTrue(smoke.permitted_request(smoke.BASE, 'GET'))
        self.assertTrue(smoke.permitted_request(smoke.BASE, 'POST', setup=True))
        self.assertFalse(smoke.permitted_request(smoke.BASE, 'POST'))
        self.assertFalse(smoke.permitted_request('https://example.com/admin', 'GET'))
        self.assertFalse(smoke.permitted_request('http://localhost:8080/admin', 'GET'))
        self.assertFalse(smoke.permitted_request('http://person:secret@localhost:7780/admin', 'GET'))
        with self.assertRaises(ValueError):
            smoke.local_url('https://example.com/admin')

    def test_redaction_preserves_actual_navigation_method_and_status(self):
        row = event('/customer/index/?form_key=sensitive&namespace=customer_listing')
        row['request']['headers'].extend([{'name': 'Cookie', 'value': 'admin_session=secret'},
                                         {'name': 'Authorization', 'value': 'Bearer secret'}])
        row['request']['postData'] = {'text': 'password=secret'}
        row['response']['cookies'] = [{'name': 'auth', 'value': 'secret'}]
        row['response']['content'] = {'text': 'private body'}
        raw = {'log': {'entries': [row]}}
        before = copy.deepcopy(raw)
        clean = smoke.sanitize_har(raw)
        self.assertEqual(raw, before)
        serialized = json.dumps(clean)
        for value in ['sensitive', 'Bearer secret', 'admin_session=secret', 'password=secret', 'private body']:
            self.assertNotIn(value, serialized)
        actual = clean['log']['entries'][0]
        self.assertEqual(actual['request']['method'], 'GET')
        self.assertEqual(actual['response']['status'], 200)
        self.assertIn('/admin/customer/index/', actual['request']['url'])
        self.assertIn('namespace=customer_listing', actual['request']['url'])
        self.assertEqual(len(clean['log']['entries']), 1)

    def test_failure_or_changed_data_cannot_be_claimed_as_smoke_pass(self):
        cases = [{'positive': positive, 'baseline': {'heading': 'Dashboard'},
                  'published_evaluator': {'score': 1 if positive else 0, 'status': 'success' if positive else 'failure'},
                  'final_gui': {'grid_loaded': True, 'visible_data_rows': 70},
                  'raw_and_sanitized_evaluator_equal': True} for positive in [True, False, True]]
        snapshots = [{'sha256': 'same'} for _ in range(4)]
        smoke.validate_outcomes(cases, snapshots)
        bad = copy.deepcopy(cases);bad[1]['published_evaluator']['status'] = 'error'
        with self.assertRaisesRegex(ValueError, 'infrastructure error'):
            smoke.validate_outcomes(bad, snapshots)
        bad = copy.deepcopy(snapshots);bad[-1]['sha256'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'changed customer'):
            smoke.validate_outcomes(cases, bad)
        bad = copy.deepcopy(cases);bad[-1]['baseline']['heading'] = 'Orders'
        with self.assertRaisesRegex(ValueError, 'baseline differs'):
            smoke.validate_outcomes(bad, snapshots)
        bad = copy.deepcopy(cases);bad[-1]['final_gui']['visible_data_rows'] = 1
        with self.assertRaisesRegex(ValueError, 'placeholder'):
            smoke.validate_outcomes(bad, snapshots)


@unittest.skipUnless(SOURCE.exists() and importlib.util.find_spec('webarena_verified'), 'pinned local upstream dependencies required')
class PublishedEvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.task, cls.proof = smoke.source_proof(SOURCE)
        cls.wa = smoke.evaluator(SOURCE)

    def test_exact_published_task_and_source_are_bound(self):
        self.assertEqual(self.proof['git_commit'], smoke.COMMIT)
        smoke.verify_task(self.task)
        changed = copy.deepcopy(self.task)
        changed['eval'][1]['expected']['url'] = '__SHOPPING_ADMIN__/sales/order/'
        with self.assertRaisesRegex(ValueError, 'evaluator contract changed'):
            smoke.verify_task(changed)

    def test_unmodified_evaluator_accepts_customer_navigation_and_rejects_orders(self):
        positive = smoke.evaluate(self.wa, [event('/customer/index/')])
        negative = smoke.evaluate(self.wa, [event('/sales/order/')])
        failed_http = smoke.evaluate(self.wa, [event('/customer/index/', status=500)])
        self.assertEqual((positive['status'], positive['score']), ('success', 1.0))
        self.assertEqual((negative['status'], negative['score']), ('failure', 0.0))
        self.assertEqual((failed_http['status'], failed_http['score']), ('failure', 0.0))
        self.assertEqual([x['name'] for x in positive['evaluators']], ['AgentResponseEvaluator', 'NetworkEventEvaluator'])
        self.assertEqual(positive['evaluator_checksum'], negative['evaluator_checksum'])

    def test_sanitized_har_scores_like_original_without_auth_material(self):
        row = event('/customer/index/')
        row['request']['headers'].append({'name': 'Cookie', 'value': 'private-session-token'})
        raw = {'log': {'entries': [row]}}
        with tempfile.TemporaryDirectory() as temp:
            original, clean = Path(temp) / 'raw.har', Path(temp) / 'clean.har'
            original.write_text(json.dumps(raw));clean.write_text(json.dumps(smoke.sanitize_har(raw)))
            self.assertEqual(smoke.evaluate(self.wa, original), smoke.evaluate(self.wa, clean))
            self.assertNotIn('private-session-token', clean.read_text())


if __name__ == '__main__':
    unittest.main()
