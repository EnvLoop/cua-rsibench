"""Synthetic public fixtures; the pinned financial model stays private."""

from importlib.util import find_spec
import io
from pathlib import Path
import sys
import unittest
from zipfile import ZipFile
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))

HAS_OPENPYXL = find_spec('openpyxl') is not None
if HAS_OPENPYXL:
    from openpyxl import Workbook
    from hard_excel_v2_ooxml_oracle import calibrate, mutate_cell, self_check, verify
    from excel_web_ooxml import MAIN


def model(*, targets=False, unrelated=100, cache=True):
    book = Workbook()
    sheet = book.active
    sheet.title = 'Model'
    sheet['A1'] = unrelated
    sheet['C1'] = '=A1*2'
    book.create_sheet('Notes')['A1'] = 'Preserve this note'
    if targets:
        sheet['B1'] = '=A1*1.1'
        sheet['B2'] = '=B1*2'
    stream = io.BytesIO()
    book.save(stream)
    raw = stream.getvalue()
    if not targets or not cache:
        return raw
    with ZipFile(io.BytesIO(raw)) as source:
        parts = {item.filename: source.read(item.filename) for item in source.infolist()}
    root = ET.fromstring(parts['xl/worksheets/sheet1.xml'])
    for node in root.iter(MAIN + 'c'):
        if node.get('r') in ('B1', 'B2'):
            node.find(MAIN + 'v').text = {'B1': '110', 'B2': '220'}[node.get('r')]
    parts['xl/worksheets/sheet1.xml'] = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    output = io.BytesIO()
    with ZipFile(output, 'w') as target:
        for name, value in parts.items():
            target.writestr(name, value)
    return output.getvalue()


@unittest.skipUnless(HAS_OPENPYXL, 'install optional excel_v2_oracle dependency')
class HardExcelOracleTests(unittest.TestCase):
    def setUp(self):
        self.source = model()
        self.gold = model(targets=True)
        self.contract = calibrate(self.source, self.gold, "'Model'!B1:B2")

    def test_positive_and_disjoint_negatives(self):
        self.assertTrue(verify(self.contract, self.gold)['artifact_pass'])
        self.assertEqual(self_check(self.contract, self.gold), {
            'gold_positive': True,
            'wrong_target_rejected': True,
            'unrelated_edit_rejected': True})
        self.assertEqual(len(self.contract.targets), 2)

    def test_missing_cache_and_unrelated_formula_change_fail(self):
        missing = verify(self.contract, model(targets=True, cache=False))
        self.assertFalse(missing['artifact_pass'])
        self.assertTrue(any('target_cache_mismatch' in error for error in missing['error_examples']))
        wrong = verify(self.contract, mutate_cell(self.gold, 'Model', 'C1', 'f', 'A1*3'))
        self.assertFalse(wrong['artifact_pass'])
        self.assertIn('unrelated_cell_changed:Model!C1', wrong['error_examples'])

    def test_gold_mutation_outside_answers_rejected_at_calibration(self):
        bad_gold = mutate_cell(self.gold, 'Model', 'A1', 'v', '101')
        with self.assertRaisesRegex(ValueError, 'gold_unrelated_semantic_change'):
            calibrate(self.source, bad_gold, "'Model'!B1:B2")
        with self.assertRaisesRegex(ValueError, 'gold_target_outside_answer_range'):
            calibrate(self.source, self.gold, "'Model'!B1:B1")


if __name__ == '__main__':
    unittest.main()
