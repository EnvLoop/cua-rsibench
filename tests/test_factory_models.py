"""Model-generation identity remains explicit across routing and saved runs."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cursibench.agentrouter import (
    MODEL_CHOICES, RESEARCHER_MODELS, ProviderFailure,
    response_receipt, resolve_researcher_model,
)
from cursibench.factory_research import run


class ResearcherModelTests(unittest.TestCase):
    def test_aliases_do_not_relabel_the_historical_sol_campaign(self):
        self.assertEqual(resolve_researcher_model('sol'), 'gpt-5.6-sol')
        self.assertEqual(resolve_researcher_model('sol6'), 'gpt-6-sol')
        self.assertEqual(resolve_researcher_model('luna6'), 'gpt-6-luna')
        for model in MODEL_CHOICES:
            self.assertEqual(resolve_researcher_model(model), model)
        with self.assertRaises(ValueError):
            resolve_researcher_model('sol-latest')

    def test_transport_keeps_requested_and_reported_identities_distinct(self):
        body = {'id': 'mock-response', 'model': 'provider-reported-model',
                'status': 'completed', 'output': [{'type': 'message', 'content': [
                    {'type': 'output_text', 'text': 'mock-result'}]}]}
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'unit-test-key'}):
            for model in MODEL_CHOICES:
                with self.subTest(model=model), patch('cursibench.agentrouter.post_json', return_value=body) as post:
                    output, receipt = response_receipt('unit-test prompt', model)
                    self.assertEqual(post.call_args.args[1]['model'], model)
                    self.assertEqual(post.call_args.args[1]['reasoning'], {'effort': 'low'})
                    self.assertNotIn('temperature', post.call_args.args[1])
                    self.assertEqual(output, 'mock-result')
                    self.assertEqual(receipt['requested_model'], model)
                    self.assertEqual(receipt['reported_model'], 'provider-reported-model')
                    self.assertNotIn('unit-test-key', json.dumps(receipt))

    def test_explicit_frozen_reasoning_settings_reach_responses(self):
        body = {'id': 'mock', 'model': 'gpt-6-astra', 'status': 'completed',
                'output': [{'type': 'message', 'content': [
                    {'type': 'output_text', 'text': 'ok'}]}]}
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'unit-test-key'}), \
                patch('cursibench.agentrouter.post_json', return_value=body) as post:
            _, receipt = response_receipt('test', 'gpt-6-astra',
                                          reasoning_effort='high',
                                          reasoning_mode='pro')
        self.assertEqual(post.call_args.args[1]['reasoning'],
                         {'effort': 'high', 'mode': 'pro'})
        self.assertEqual(receipt['requested_reasoning_effort'], 'high')
        self.assertEqual(receipt['requested_reasoning_mode'], 'pro')
        with self.assertRaisesRegex(ValueError, 'unsupported frozen reasoning'):
            response_receipt('test', 'gpt-6-astra', reasoning_effort='none')

    def test_transport_failure_retains_exact_requested_model(self):
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'unit-test-key'}), \
                patch('cursibench.agentrouter.post_json', side_effect=ValueError('private provider content')):
            with self.assertRaises(ProviderFailure) as raised:
                response_receipt('unit-test prompt', 'gpt-6-luna')
        self.assertEqual(raised.exception.receipt['requested_model'], 'gpt-6-luna')
        self.assertNotIn('private provider content', json.dumps(raised.exception.receipt))

    def test_factory_records_canonical_researcher_and_keeps_teacher_fixed(self):
        # No cloud service is called: one read action exercises the controller's
        # model argument, receipt persistence, and immutable run specification.
        for alias, model in RESEARCHER_MODELS.items():
            with self.subTest(alias=alias), tempfile.TemporaryDirectory() as tmp, \
                    patch('cursibench.factory_research.FactoryWorkspace') as workspace, \
                    patch('cursibench.factory_research.response_receipt') as respond, \
                    contextlib.redirect_stdout(io.StringIO()):
                workspace.return_value.sandbox = None
                workspace.return_value.read.return_value = {'content': 'test contract'}
                respond.return_value = (
                    json.dumps({'action': {'type': 'read', 'path': 'inputs/contract.md'}}),
                    {'requested_model': model, 'reported_model': 'provider-id'},
                )
                out = Path(tmp) / alias
                result = run(out, researcher=alias, max_turns=1)
                self.assertEqual(respond.call_args.args[1], model)
                self.assertEqual(result['spec']['researcher'], model)
                self.assertEqual(result['spec']['teacher'], 'gpt-5.6-sol')
                receipt = json.loads((out / 'controller/researcher-receipt-0.json').read_text())
                self.assertEqual(receipt['requested_model'], model)
                self.assertEqual(receipt['reported_model'], 'provider-id')


if __name__ == '__main__':
    unittest.main()
