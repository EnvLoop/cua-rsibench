import unittest

from tools.reconcile_magento_interrupted_preseed_v1 import validate_events


class InterruptedPreseedTest(unittest.TestCase):
    def setUp(self):
        self.events = [
            {'event': 'sweep_started', 'start_index': 32,
             'official_final_admitted': False, 'model_calls': 0},
            {'event': 'step_intent', 'index': 32, 'step': 'positive-prepare',
             'command_sha256': '0' * 64, 'time': 1.0},
        ]

    def test_exact_intent_is_eligible(self):
        self.assertEqual(validate_events(self.events)['index'], 32)

    def test_seed_or_later_event_refused(self):
        for extra in ({'event': 'step_intent', 'index': 32, 'step': 'positive-seed'},
                      {'event': 'step_finished', 'index': 32,
                       'step': 'positive-prepare', 'exit_code': 0}):
            with self.subTest(extra=extra):
                with self.assertRaisesRegex(ValueError, 'pre-seed'):
                    validate_events(self.events + [extra])


if __name__ == '__main__':
    unittest.main()
