"""SEC selection scorer guards split, numeric dependencies and preservation."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.test_sec_excel_web_train_oracle_v1 import workbook
from tools import sec_excel_web_selection_oracle_v1 as oracle
from tools.office_web_excel_selection_worker_v1 import SelectionOracleSubprocess


class SecSelectionOracleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sec-selection-oracle-')
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.seed = root / 'seed.xlsx'
        self.reference = root / 'reference.xlsx'
        self.seed.write_bytes(workbook())
        self.reference.write_bytes(workbook(formula='A1*3'))
        self.cases = root / 'cases.json'
        self.case = {'case_id': 'sec-selection-case',
                     'split': 'selection_candidate',
                     'source_package': {
                         'schema': 'sec-integrated-source-package-v1'}}
        self.cases.write_text(json.dumps([self.case]))

    def test_exact_selection_only_and_one_case(self):
        self.assertEqual(oracle.one_selection_case(
            self.cases, 'sec-selection-case'), self.case)
        for split in ('train_candidate', 'final_candidate'):
            self.cases.write_text(json.dumps([{**self.case,
                                               'split': split}]))
            with self.assertRaisesRegex(ValueError,
                                        'not_exact_original_selection_candidate'):
                oracle.one_selection_case(
                    self.cases, 'sec-selection-case')
        self.cases.write_text(json.dumps([self.case, self.case]))
        with self.assertRaisesRegex(ValueError,
                                    'not_exact_original_selection_candidate'):
            oracle.one_selection_case(self.cases, 'sec-selection-case')

    def test_calibration_requires_33_target_positive_and_two_profiles(self):
        def verify(candidate, _seed, _case):
            return ({'pass': True, 'checked_targets': 33,
                     'counterfactual_profiles': 2, 'errors': []}
                    if candidate == self.reference else
                    {'pass': False, 'checked_targets': 33,
                     'counterfactual_profiles': 0,
                     'errors': ['target_formula_missing:Audit!B6']})
        with patch.object(oracle.train_oracle, 'sec_verify', verify):
            receipt = oracle.calibrate(
                self.seed, self.reference, self.case)
        self.assertTrue(receipt['positive_reference_passed'])
        self.assertEqual(receipt['checked_formula_targets'], 33)
        with patch.object(oracle.train_oracle, 'sec_verify',
                          lambda *_: {'pass': True,
                                      'checked_targets': 29,
                                      'counterfactual_profiles': 2,
                                      'errors': []}):
            with self.assertRaisesRegex(ValueError,
                                        'positive_negative_calibration_failed'):
                oracle.calibrate(self.seed, self.reference, self.case)

    def test_saved_regression_scores_zero_and_setup_failure_is_invalid(self):
        with patch.object(oracle.train_oracle, 'sec_verify',
                          lambda *_: {'pass': False,
                                      'checked_targets': 33,
                                      'counterfactual_profiles': 2,
                                      'errors': [
                                          'non_target_cell_changed:SEC Inputs!A1']}):
            score = oracle.score(self.reference, self.seed, self.case)
        self.assertEqual(score['status'], 'scored')
        self.assertEqual(score['score'], 0)
        self.assertFalse(score['preservation_pass'])
        self.assertEqual(score['non_target_or_structure_error_count'], 1)
        with patch.object(oracle.train_oracle, 'sec_verify',
                          lambda *_: {'pass': False,
                                      'checked_targets': 0,
                                      'counterfactual_profiles': 0,
                                      'errors': [
                                          'oracle_setup:ValueError:source_changed']}):
            invalid = oracle.score(self.reference, self.seed,
                                   self.case)
        self.assertEqual(invalid['status'], 'invalid_source_or_verifier')
        self.assertIsNone(invalid['score'])

    def test_neutral_subprocess_checks_formula_and_literal_cells(self):
        result = SelectionOracleSubprocess().neutral(self.seed, self.seed)
        self.assertEqual(result['schema'], oracle.NEUTRAL_SCHEMA)
        self.assertTrue(result['equivalent'])
        changed = self.seed.parent / 'changed.xlsx'
        changed.write_bytes(workbook(number='101'))
        result = SelectionOracleSubprocess().neutral(self.seed, changed)
        self.assertFalse(result['equivalent'])
        self.assertEqual(result['changed_cell_count'], 1)


if __name__ == '__main__':
    unittest.main()
