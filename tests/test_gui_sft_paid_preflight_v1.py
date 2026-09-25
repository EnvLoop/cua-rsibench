import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'gui_sft_paid_preflight', ROOT / 'tools/build_magento_gui_sft_v1.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class PaidPreflightTests(unittest.TestCase):
    def receipt(self):
        return {
            'episode_sha256': builder.PINNED_ACTION_ONLY_EPISODE_SHA256,
            'train_only': True, 'train_task_id': 777,
            'train_template_id': 742, 'datum_count': 36,
            'paid_provider_calls': 0, 'tinker_sdk_version': '0.30.1',
            'first_supervised_tokens': 2500, 'first_prompt_tokens': 2300,
            'renderer_identity': {
                'processor_config_sha256': builder.PINNED_PROCESSOR_SHA256,
                'tokenizer_vocabulary_sha256': builder.PINNED_TOKENIZER_SHA256,
            },
        }

    def test_exact_dataset_and_renderer_are_required_before_paid_call(self):
        reservation = builder.paid_preflight(self.receipt())
        self.assertLess(float(reservation['max_published_rate_reservation_usd']), 0.25)
        self.assertEqual(reservation['max_sample_tokens'], 96)
        self.assertIsNone(reservation['provider_invoice_usd'])

    def test_drifted_episode_or_processor_is_rejected(self):
        for key, bad in (('episode_sha256', '0' * 64),
                         ('train_template_id', 240),
                         ('datum_count', 35)):
            row = self.receipt()
            row[key] = bad
            with self.assertRaisesRegex(ValueError, 'paid_dataset_or_renderer'):
                builder.paid_preflight(row)
        row = self.receipt()
        row['renderer_identity']['processor_config_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'paid_dataset_or_renderer'):
            builder.paid_preflight(row)

    def test_invalid_or_oversize_tokens_are_rejected(self):
        row = self.receipt()
        row['first_prompt_tokens'] = row['first_supervised_tokens']
        with self.assertRaisesRegex(ValueError, 'paid_token_length'):
            builder.paid_preflight(row)
        row = self.receipt()
        row['first_supervised_tokens'] = 32_769
        with self.assertRaisesRegex(ValueError, 'paid_token_length'):
            builder.paid_preflight(row)


if __name__ == '__main__':
    unittest.main()
