"""Source, split, workbook, and adversarial oracle checks for SEC candidates."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from prepare_integrated_cases import allocate_cases, packages
from verify_integrated_candidate import expected_values, verify
from verify_ooxml import load_xlsx


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def change_cell(source: Path, output: Path, sheet_number: int, address: str,
                *, formula: str | None = None, value: str | None = None) -> None:
    member = f"xl/worksheets/sheet{sheet_number}.xml"
    with ZipFile(source) as zin, ZipFile(output, "w", ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename == member:
                root = ET.fromstring(data)
                cell = root.find(f'.//{{{MAIN}}}c[@r="{address}"]')
                if cell is None:
                    raise ValueError(f"missing test cell {member}!{address}")
                if formula is not None:
                    element = cell.find(f"{{{MAIN}}}f")
                    if element is None:
                        element = ET.Element(f"{{{MAIN}}}f")
                        cell.insert(0, element)
                    element.text = formula.removeprefix("=")
                    old_cache = cell.find(f"{{{MAIN}}}v")
                    if old_cache is not None:
                        cell.remove(old_cache)
                if value is not None:
                    element = cell.find(f"{{{MAIN}}}v")
                    if element is None:
                        element = ET.SubElement(cell, f"{{{MAIN}}}v")
                    element.text = value
                data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            zout.writestr(info, data)


class IntegratedSourceTest(unittest.TestCase):
    def test_exact_source_and_filing_split(self) -> None:
        source_packages = packages()
        cases = allocate_cases(source_packages)
        self.assertEqual(len(source_packages), 15)
        self.assertEqual(Counter(c["split"] for c in cases), {
            "train_candidate": 20, "selection_candidate": 20, "final_candidate": 100})
        accession_owner = {}
        for case in cases:
            source = case["source_package"]
            for accession in (source["annual_accession"], source["q3_accession"]):
                if accession in accession_owner:
                    self.assertEqual(accession_owner[accession], case["split"])
                accession_owner[accession] = case["split"]
            self.assertEqual(len(source["canonical"]), 16)
            self.assertGreaterEqual(len(source["annual_rows"]), 28)
            self.assertGreaterEqual(len(source["q3_rows"]), 30)
        self.assertEqual(len(set(accession_owner.values())), 3)
        self.assertEqual(len({c["source_group"] for c in cases if c["split"] == "final_candidate"}), 7)


@unittest.skipUnless(shutil.which("node") and (ROOT / "node_modules/@oai/artifact-tool").exists(),
                     "bundled artifact-tool runtime unavailable")
class IntegratedWorkbookTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory(prefix="sec-integrated-test-")
        cls.path = Path(cls.tmp.name)
        all_cases = allocate_cases(packages())
        cls.cases = [all_cases[0], all_cases[20], all_cases[40]]
        manifest = cls.path / "cases.json"
        manifest.write_text(json.dumps(cls.cases, separators=(",", ":")))
        subprocess.run(["node", str(HERE / "build_integrated_workbooks.mjs"),
                        str(manifest), str(cls.path / "workbooks"), "3"],
                       check=True, capture_output=True, text=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def workbook(self, case: dict, filename: str) -> Path:
        return self.path / "workbooks" / case["split"] / case["case_id"] / filename

    def test_reference_passes_and_unsolved_fails(self) -> None:
        for case, target_count in zip(self.cases, (25, 33, 48)):
            with self.subTest(case=case["case_id"]):
                seed = self.workbook(case, "actor.xlsx")
                gold = self.workbook(case, "reference.xlsx")
                result = verify(gold, seed, case)
                self.assertTrue(result["pass"], result)
                self.assertEqual(result["checked_targets"], target_count)
                self.assertEqual(result["counterfactual_profiles"], 2)
                self.assertFalse(verify(seed, seed, case)["pass"])
                private = json.loads(self.workbook(case, "private-oracle.json").read_text())
                self.assertGreaterEqual(len(private["faulted"]), 6)
                self.assertLessEqual(len(private["faulted"]), 9)

    def test_fault_locations_not_color_signaled(self) -> None:
        case = self.cases[2]
        seed = self.workbook(case, "actor.xlsx")
        private = json.loads(self.workbook(case, "private-oracle.json").read_text())
        faulted = {tuple(key.split("!")) for key in private["faulted"]}
        # A formula fault is not distinguished by special cell formatting.
        with ZipFile(seed) as z, ZipFile(self.workbook(case, "reference.xlsx")) as ref_z:
            for sheet_name, sheet_index in (("FY Selection", 2), ("Q3 Selection", 3),
                                            ("Working Capital", 5), ("Scenario", 6)):
                root = ET.fromstring(z.read(f"xl/worksheets/sheet{sheet_index}.xml"))
                reference_root = ET.fromstring(ref_z.read(f"xl/worksheets/sheet{sheet_index}.xml"))
                for cell in root.findall(f".//{{{MAIN}}}sheetData/{{{MAIN}}}row/{{{MAIN}}}c"):
                    if (sheet_name, cell.get("r")) in faulted:
                        reference_cell = reference_root.find(f'.//{{{MAIN}}}c[@r="{cell.get("r")}"]')
                        self.assertIsNotNone(reference_cell)
                        self.assertEqual(cell.get("s"), reference_cell.get("s"),
                                         (sheet_name, cell.get("r")))

    def test_hardcode_rejected_by_counterfactual(self) -> None:
        case = self.cases[2]
        base = expected_values(case)
        modified = self.path / "hardcode.xlsx"
        change_cell(self.workbook(case, "reference.xlsx"), modified, 2, "B5",
                    formula=str(base[("FY Selection", "B5")]))
        result = verify(modified, self.workbook(case, "actor.xlsx"), case)
        self.assertFalse(result["pass"])
        self.assertTrue(any("numeric_or_dependency_error_p1:FY Selection!B5" in e
                            for e in result["errors"]), result)

    def test_source_and_unrelated_formula_regressions_rejected(self) -> None:
        case = self.cases[2]
        gold = self.workbook(case, "reference.xlsx")
        seed = self.workbook(case, "actor.xlsx")
        altered = self.path / "source-edit.xlsx"
        # Annual raw source is sheet 8 in the ten-tab final workbook.
        source_cells, order, _, _ = load_xlsx(gold)
        raw = source_cells["Annual 10-K"]
        address = next(a for a in raw if a.startswith("N") and a[1:].isdigit() and int(a[1:]) >= 5)
        change_cell(gold, altered, order.index("Annual 10-K") + 1, address, value="123")
        result = verify(altered, seed, case)
        self.assertFalse(result["pass"])
        self.assertTrue(any(e.startswith("non_target_cell_changed:Annual 10-K!") for e in result["errors"]), result)
        altered2 = self.path / "unrelated-edit.xlsx"
        change_cell(gold, altered2, order.index("Scenario") + 1, "B5", value="12345")
        result = verify(altered2, seed, case)
        self.assertFalse(result["pass"])

    def test_build_is_semantically_deterministic(self) -> None:
        case = self.cases[2]
        manifest = self.path / "one-case.json"
        manifest.write_text(json.dumps([case], separators=(",", ":")))
        other = self.path / "rebuilt"
        subprocess.run(["node", str(HERE / "build_integrated_workbooks.mjs"),
                        str(manifest), str(other), "1"], check=True,
                       capture_output=True, text=True)
        for file in ("actor.xlsx", "reference.xlsx"):
            original = self.workbook(case, file)
            duplicate = other / case["split"] / case["case_id"] / file
            self.assertEqual(load_xlsx(original), load_xlsx(duplicate))


if __name__ == "__main__":
    unittest.main()
