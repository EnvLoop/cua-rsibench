"""Source-independent checks for the native Calc admission control."""

from __future__ import annotations

import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "qualify_osworld_calc_time_v1", ROOT / "tools/qualify_osworld_calc_time_v1.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def workbook(*, e3: str = "", e4: str = "", b4: str = "0.0625") -> bytes:
    target = (f'<c r="E3"><f>D3*F3*24</f><v>{e3}</v></c>' if e3 else "")
    wrong = (f'<c r="E4"><f>D3*F3*24</f><v>{e4}</v></c>' if e4 else "")
    sheet = (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData><row r="3"><c r="D3"><f>SUM(B3:B7)</f>'
        '<v>0.319444444444444</v></c>' + target +
        '<c r="F3"><v>25</v></c></row><row r="4">'
        f'<c r="B4"><v>{b4}</v></c>' + wrong +
        '</row></sheetData></worksheet>')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    return buffer.getvalue()


class OSWorldCalcTimeControlTests(unittest.TestCase):
    def test_positive_requires_exact_saved_target_and_unrelated_cell_preservation(self):
        baseline = workbook()
        result = MODULE.semantic_check(
            baseline, workbook(e3="191.666666666666"), attempt="positive")
        self.assertEqual(result["changed_cells"], ["E3"])
        self.assertTrue(result["independent_accept"])
        collateral = MODULE.semantic_check(
            baseline, workbook(e3="191.666666666666", b4="0.5"),
            attempt="positive")
        self.assertFalse(collateral["independent_accept"])
        self.assertEqual(collateral["changed_cells"], ["B4", "E3"])

    def test_plausible_wrong_cell_is_rejected_even_when_formula_is_correct(self):
        result = MODULE.semantic_check(workbook(),
                                       workbook(e4="191.666666666666"),
                                       attempt="wrong-cell")
        self.assertEqual(result["changed_cells"], ["E4"])
        self.assertFalse(result["target_passed"])
        self.assertFalse(result["independent_accept"])

    def test_window_readiness_waits_past_splash_screen(self):
        class Result:
            exit_code = 0
            def __init__(self, stdout):
                self.stdout = stdout
        class Commands:
            def __init__(self):
                self.searches = 0
            def run(self, command):
                if "search --name" in command:
                    self.searches += 1
                    return Result("" if self.searches < 3 else "234\n")
                return Result("Multiply_Time_Number.xlsx - LibreOffice Calc\n")
        class Sandbox:
            commands = Commands()
        sandbox = Sandbox()
        with patch.object(MODULE.time, "sleep"):
            title = MODULE.wait_for_workbook(sandbox, seconds=2)
        self.assertEqual(title, "Multiply_Time_Number.xlsx - LibreOffice Calc")
        self.assertEqual(sandbox.commands.searches, 3)

    def test_absent_workbook_window_fails_closed(self):
        class Sandbox:
            class commands:
                @staticmethod
                def run(command):
                    raise AssertionError("should not query after deadline")
        with self.assertRaisesRegex(TimeoutError, "never became visible"):
            MODULE.wait_for_workbook(Sandbox(), seconds=0)


if __name__ == "__main__":
    unittest.main()
