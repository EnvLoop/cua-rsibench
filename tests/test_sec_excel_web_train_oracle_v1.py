"""Train-only SEC scorer boundary and neutral workbook state tests."""

from __future__ import annotations

import json
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools import sec_excel_web_train_oracle_v1 as oracle
from tools.office_web_excel_teacher_worker_v1 import SecOracleSubprocess


def workbook(number='100', formula='A1*2') -> bytes:
    values = {
        '[Content_Types].xml': '<Types/>',
        'xl/workbook.xml': '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="SEC Inputs" sheetId="1" r:id="rId1"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>',
        'xl/worksheets/sheet1.xml': '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1"><v>' + number + '</v></c><c r="B1"><f>' + formula + '</f><v>200</v></c></row></sheetData></worksheet>',
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        for name, value in values.items():
            archive.writestr(name, value)
    return output.getvalue()


class SecExcelTrainOracleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sec-excel-oracle-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.seed = self.root / 'actor.xlsx'
        self.reference = self.root / 'reference.xlsx'
        self.seed.write_bytes(workbook())
        self.reference.write_bytes(workbook())
        self.cases = self.root / 'cases.json'
        self.case = {'case_id': 'train-case-1',
                     'split': 'train_candidate',
                     'source_package': {
                         'schema': 'sec-integrated-source-package-v1'}}
        self.cases.write_text(json.dumps([self.case]))

    def test_neutral_state_compares_all_formula_and_numeric_cells(self):
        first = oracle.neutral(self.seed, self.reference)
        self.assertTrue(first['equivalent'])
        changed = self.root / 'changed.xlsx'
        changed.write_bytes(workbook(number='101'))
        result = oracle.neutral(self.seed, changed)
        self.assertFalse(result['equivalent'])
        self.assertEqual(result['changed_cell_count'], 1)
        formula = self.root / 'formula.xlsx'
        formula.write_bytes(workbook(formula='A1*3'))
        self.assertFalse(oracle.neutral(self.seed, formula)['equivalent'])

    def test_case_manifest_excludes_selection_and_final(self):
        self.assertEqual(oracle.one_train_case(
            self.cases, 'train-case-1')['split'], 'train_candidate')
        wrong = dict(self.case, split='final_candidate')
        self.cases.write_text(json.dumps([wrong]))
        with self.assertRaisesRegex(ValueError, 'not_exact_original_train_candidate'):
            oracle.one_train_case(self.cases, 'train-case-1')

    def test_calibration_requires_unsolved_seed_and_counterfactual_positive(self):
        def fake_verify(candidate, seed, case):
            if candidate == self.reference:
                return {'pass': True, 'checked_targets': 25,
                        'counterfactual_profiles': 2, 'errors': []}
            return {'pass': False, 'checked_targets': 25,
                    'counterfactual_profiles': 0,
                    'errors': ['target_formula_missing']}
        with patch.object(oracle, 'sec_verify', fake_verify):
            result = oracle.calibrate(self.seed, self.reference, self.case)
        self.assertTrue(result['positive_reference_passed'])
        self.assertEqual(result['checked_formula_targets'], 25)
        with patch.object(oracle, 'sec_verify', lambda *_: {
            'pass': True, 'checked_targets': 25,
            'counterfactual_profiles': 2, 'errors': []}):
            with self.assertRaisesRegex(ValueError, 'positive_negative_calibration_failed'):
                oracle.calibrate(self.seed, self.reference, self.case)

    def test_neutral_runs_in_separate_evaluator_process(self):
        result = SecOracleSubprocess().neutral(self.seed, self.reference)
        self.assertEqual(result['schema'],
                         'cua-sec-integrated-train-neutral-v1')
        self.assertTrue(result['equivalent'])


if __name__ == '__main__':
    unittest.main()
