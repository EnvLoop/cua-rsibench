"""Adversarial checks for the offline SEC Excel task and OOXML verifier."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
import warnings
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from verify_ooxml import Cell, load_xlsx, unchanged_cell, verify


HERE = Path(__file__).resolve().parent
NODE = os.environ.get(
    "NODE_BIN",
    "/Users/xiaoyong/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node",
)
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def mutate_cell(src: Path, dest: Path, sheet_number: int, address: str, *, formula: str | None = None, value: str | None = None) -> None:
    target = f"xl/worksheets/sheet{sheet_number}.xml"
    with ZipFile(src) as zin, ZipFile(dest, "w", ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == target:
                root = ET.fromstring(data)
                cell = root.find(f'.//{{{NS}}}c[@r="{address}"]')
                assert cell is not None
                f = cell.find(f"{{{NS}}}f")
                v = cell.find(f"{{{NS}}}v")
                if formula is not None:
                    if f is None:
                        f = ET.Element(f"{{{NS}}}f")
                        cell.insert(0, f)
                    f.text = formula.removeprefix("=")
                elif f is not None:
                    cell.remove(f)
                if value is not None:
                    if v is None:
                        v = ET.SubElement(cell, f"{{{NS}}}v")
                    v.text = value
                data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            zout.writestr(item, data)


class FactoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory(prefix="sec-excel-test-")
        cls.base = Path(cls.temp.name) / "base"
        cls.holdout = Path(cls.temp.name) / "holdout"
        for path, variant in ((cls.base, "base"), (cls.holdout, "holdout")):
            subprocess.run([NODE, str(HERE / "build_workbooks.mjs"), str(path), variant], check=True, stdout=subprocess.DEVNULL)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_positive_and_hidden_scenario(self) -> None:
        a = verify(self.base / "private/positive.xlsx", self.base / "actor/task.xlsx")
        b = verify(self.holdout / "private/positive.xlsx", self.holdout / "actor/task.xlsx")
        self.assertTrue(a["pass"], a)
        self.assertTrue(b["pass"], b)
        self.assertEqual(a["checked_targets"], 84)
        self.assertFalse(verify(self.base / "private/positive.xlsx", self.holdout / "actor/task.xlsx")["pass"])

    def test_source_tampering_rejected(self) -> None:
        source = self.base / "private/positive.xlsx"
        modified = self.base / "tampered.xlsx"
        mutate_cell(source, modified, 5, "O5", value="352584000000")
        result = verify(modified, self.base / "actor/task.xlsx")
        self.assertFalse(result["pass"])
        self.assertTrue(any("non_target_cell_changed:Raw SEC!O5" in x for x in result["errors"]), result)

    def test_excel_double_roundtrip_spelling_is_not_source_tampering(self) -> None:
        source = self.base / "private/positive.xlsx"
        modified = self.base / "same-double-different-spelling.xlsx"
        sheets, _, _, _ = load_xlsx(source)
        self.assertEqual(sheets["Raw SEC"]["O23"].value, "2.18")
        mutate_cell(source, modified, 5, "O23", value="2.1800000000000002")
        result = verify(modified, self.base / "actor/task.xlsx")
        self.assertTrue(result["pass"], result)

    def test_excel_string_and_numeric_storage_encodings_are_semantically_compared(self) -> None:
        self.assertTrue(unchanged_cell(Cell("Apple", None, "str"), Cell("Apple", None, "s")))
        self.assertTrue(unchanged_cell(Cell("2.18", None, "n"), Cell("2.1800000000000002", None, None)))
        self.assertFalse(unchanged_cell(Cell("Apple", None, "str"), Cell("Microsoft", None, "s")))

    def test_duplicate_ooxml_member_is_rejected(self) -> None:
        source = self.base / "private/positive.xlsx"
        modified = self.base / "duplicate-member.xlsx"
        with ZipFile(source) as zin, ZipFile(modified, "w", ZIP_DEFLATED) as zout:
            workbook_xml = zin.read("xl/workbook.xml")
            for item in zin.infolist():
                zout.writestr(item, zin.read(item.filename))
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                zout.writestr("xl/workbook.xml", workbook_xml)
        result = verify(modified, self.base / "actor/task.xlsx")
        self.assertFalse(result["pass"])
        self.assertTrue(any("duplicate_or_oversized_ooxml_package" in x for x in result["errors"]), result)

    def test_hardcode_rejected_after_private_perturbation(self) -> None:
        source = self.base / "private/positive.xlsx"
        modified = self.base / "hardcode.xlsx"
        mutate_cell(source, modified, 2, "D6", formula="391035", value="391035")
        result = verify(modified, self.base / "actor/task.xlsx")
        self.assertFalse(result["pass"])
        self.assertTrue(any("dependency_failure:FY Selection!D6" in x for x in result["errors"]), result)

    def test_equal_value_wrong_filing_rejected(self) -> None:
        source = self.base / "private/positive.xlsx"
        sheets, _, _, _ = load_xlsx(source)
        current_formula = sheets["FY Selection"]["D6"].formula or ""
        canonical_row = int(re.search(r"O(\d+)", current_formula).group(1))
        canonical_value = sheets["Raw SEC"][f"O{canonical_row}"].value
        raw_row_numbers = sorted(int(addr[1:]) for addr in sheets["Raw SEC"] if addr.startswith("A") and addr[1:].isdigit() and int(addr[1:]) >= 5)
        wrong_rows = [
            row for row in raw_row_numbers
            if row != canonical_row
            and sheets["Raw SEC"].get(f"B{row}")
            and sheets["Raw SEC"][f"B{row}"].value == "Apple"
            and sheets["Raw SEC"][f"D{row}"].value == "Revenue"
            and sheets["Raw SEC"][f"G{row}"].value == "2024-09-28"
            and sheets["Raw SEC"][f"O{row}"].value == canonical_value
        ]
        self.assertTrue(wrong_rows, "Frozen SEC excerpt should contain a same-value comparative distractor")
        modified = self.base / "wrong-filing.xlsx"
        mutate_cell(source, modified, 2, "D6", formula=f"'Raw SEC'!O{wrong_rows[0]}/1000000", value="391035")
        result = verify(modified, self.base / "actor/task.xlsx")
        self.assertFalse(result["pass"])
        self.assertTrue(any("dependency_failure:FY Selection!D6" in x for x in result["errors"]), result)


if __name__ == "__main__":
    unittest.main()
