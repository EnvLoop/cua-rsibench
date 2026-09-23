import unittest
from cursibench.training_contract import schedule

class TrainingContractTests(unittest.TestCase):
    def test_factory_schedule_covers_every_submitted_row(self):
        config,batches=schedule(35,32,'factory-v1')
        self.assertEqual({x for b in batches for x in b},set(range(35)))
        self.assertEqual(len(batches),32)
        self.assertEqual(config['scheduled_tokens'],262144)
        with self.assertRaisesRegex(ValueError,'omit 3'):schedule(35,16,'factory-v1')
    def test_legacy_limit_remains_explicit(self):
        schedule(26,16,'pilot-v1')
        with self.assertRaises(ValueError):schedule(35,16,'pilot-v1')
        with self.assertRaises(ValueError):schedule(35,129,'factory-v1')
