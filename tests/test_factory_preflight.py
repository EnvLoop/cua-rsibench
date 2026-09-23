import unittest
from cursibench.factory_preflight import inspect_rows


class CountingTokenizer:
    eos_token_id = 0
    def apply_chat_template(self, messages, **kwargs):
        return messages[-1]['content']
    def encode(self, text, **kwargs):
        return [1] * int(text)


def row(prefix, target):
    return {'record_id': 'episode:1:history', 'messages': [
        {'role': 'user', 'content': str(prefix)},
        {'role': 'assistant', 'content': str(target)}]}


class PreflightTests(unittest.TestCase):
    def test_sequence_boundary_counts_eos_before_training_shift(self):
        report = inspect_rows([row(16000, 383)], CountingTokenizer(), steps=1)
        self.assertTrue(report['accepted'])
        self.assertEqual(report['max_sequence'], 16384)
        self.assertEqual(report['scheduled_tokens'], 2 * 16383)
        report = inspect_rows([row(16000, 384)], CountingTokenizer(), steps=1)
        self.assertFalse(report['accepted'])
        self.assertEqual(report['record_violations'][0]['record_id'], 'episode:1:history')

    def test_total_exposure_and_output_capacity_are_independent_limits(self):
        self.assertFalse(inspect_rows([row(4500, 100)], CountingTokenizer())['accepted'])
        report = inspect_rows([row(100, 512)], CountingTokenizer(), steps=1)
        self.assertFalse(report['accepted'])
        self.assertEqual(report['max_target'], 513)
