import unittest

from tools.reconcile_magento_cellwide_halt_v1 import valid_halt


class CellwideHaltTest(unittest.TestCase):
    def setUp(self):
        self.rows = [*({'event': 'task_gui_calibrated', 'index': i}
                       for i in (32, 33, 34)),
                     {'event': 'step_finished', 'index': 35,
                      'step': 'positive-prepare', 'exit_code': 1},
                     {'event': 'sweep_stopped', 'passed': 3}]

    def test_exact_halt(self):
        valid_halt(self.rows)

    def test_seed_refused(self):
        rows = self.rows[:-1] + [
            {'event': 'step_intent', 'index': 35, 'step': 'positive-seed'},
            self.rows[-1],
        ]
        with self.assertRaisesRegex(ValueError, 'second drift'):
            valid_halt(rows)


if __name__ == '__main__':
    unittest.main()
