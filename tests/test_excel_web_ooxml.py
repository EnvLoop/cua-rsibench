import io
from pathlib import Path
import sys
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from excel_web_ooxml import package, read_workbook, task_50250, wrong_h2_fixture
from prepare_excel_web_candidates import target_cells


def workbook(h2='', c1='867', additional='', sheets=''):
    values = {
        'xl/workbook.xml': '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Data" sheetId="1" r:id="rId1"/>' + sheets + '</sheets></workbook>',
        'xl/_rels/workbook.xml.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Target="worksheets/sheet2.xml"/></Relationships>',
        'xl/sharedStrings.xml': '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>sela</t></si></sst>',
        'xl/worksheets/sheet1.xml': '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="C1"><v>' + c1 + '</v></c></row><row r="2"><c r="G2" t="s"><v>0</v></c>' + h2 + additional + '</row></sheetData></worksheet>',
        'xl/worksheets/sheet2.xml': '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>',
        'docProps/core.xml': '<unchanged/>',
    }
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        for name, value in values.items():
            archive.writestr(name, value)
    return stream.getvalue()


class IndependentOracleTests(unittest.TestCase):
    def setUp(self):
        self.initial = workbook()
        self.reference = workbook('<c r="H2"><f>SUM(C1:C1)</f><v>867</v></c>')

    def test_reference_pass_is_explicitly_artifact_only(self):
        result = task_50250(self.initial, self.reference)
        self.assertTrue(result['artifact_value_pass'])
        self.assertEqual(result['expected_H2'], '867')
        self.assertFalse(result['gui_execution_verified'])
        self.assertFalse(result['native_recalculation_verified'])

    def test_wrong_result_and_noop_fail(self):
        wrong = task_50250(self.initial, wrong_h2_fixture(self.reference))
        self.assertIn('H2_value_mismatch', wrong['errors'])
        self.assertFalse(task_50250(self.initial, self.initial)['artifact_value_pass'])

    def test_unrelated_value_change_fails(self):
        result = task_50250(self.initial, workbook('<c r="H2"><v>867</v></c>', c1='999'))
        self.assertIn('unrelated_cell_changed:C1', result['errors'])

    def test_unrelated_added_cell_fails(self):
        result = task_50250(self.initial, workbook('<c r="H2"><v>867</v></c>', additional='<c r="Z2"><v>1</v></c>'))
        self.assertIn('unrelated_cell_changed:Z2', result['errors'])

    def test_extra_sheet_fails(self):
        out = workbook('<c r="H2"><v>867</v></c>', sheets='<sheet name="Hidden" sheetId="2" r:id="rId2" state="hidden"/>')
        self.assertIn('worksheet_identity_or_date_system_changed', task_50250(self.initial, out)['errors'])

    def test_numeric_string_is_not_numeric_output(self):
        out = workbook('<c r="H2" t="str"><v>867</v></c>')
        self.assertFalse(task_50250(self.initial, out)['artifact_value_pass'])

    def test_missing_formula_cache_cannot_be_success(self):
        out = workbook('<c r="H2"><f>SUM(C1:C1)</f><v/></c>')
        result = task_50250(self.initial, out)
        self.assertIn('H2_formula_cache_missing', result['errors'])

    def test_cache_freshness_is_not_claimed(self):
        # This deliberately inconsistent cache is observable as867. A real GUI
        # verifier must provide independent native recalculation/provenance.
        out = workbook('<c r="H2"><f>0</f><v>867</v></c>')
        result = task_50250(self.initial, out)
        self.assertTrue(result['artifact_value_pass'])
        self.assertFalse(result['native_recalculation_verified'])

    def test_negative_changes_only_target_worksheet_member(self):
        before, after = package(self.reference), package(wrong_h2_fixture(self.reference))
        self.assertEqual(set(before), set(after))
        self.assertEqual([name for name in before if before[name] != after[name]], ['xl/worksheets/sheet1.xml'])

    def test_target_mapping_honors_answer_sheet(self):
        source = {'sheets': {'WrongFirst': {}, 'Correct': {}}}
        self.assertEqual(target_cells({'answer_sheet': 'Correct', 'answer_position': '$H$2:$H$3'}, source), ('Correct', ['H2', 'H3']))
        self.assertEqual(target_cells({'answer_sheet': 'WrongFirst', 'answer_position': "'Correct'!H2"}, source), ('Correct', ['H2']))

    def test_duplicate_zip_member_rejected(self):
        stream = io.BytesIO(self.initial)
        with zipfile.ZipFile(stream, 'a') as archive:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                archive.writestr('docProps/core.xml', '<changed/>')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            read_workbook(stream.getvalue())

    def test_nonfinite_number_rejected(self):
        with self.assertRaisesRegex(ValueError, 'nonfinite'):
            read_workbook(workbook(c1='NaN'))


if __name__ == '__main__':
    unittest.main()
