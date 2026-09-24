"""Positive, negative and evaluator-side development replay checks."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from build_retail_working_capital import build
from extract_retail_sec import HERE
from verify_ooxml import load_xlsx
from verify_retail_working_capital import (SHEETS, TARGETS, expected_values,
                                           perturbation_profiles, verify)


MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def change_cell(source: Path, output: Path, sheet: str, address: str,
                *, formula: str | None = None, value: str | None = None) -> None:
    member = f"xl/worksheets/sheet{SHEETS.index(sheet) + 1}.xml"
    with ZipFile(source) as zin, ZipFile(output, "w", ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename == member:
                root = ET.fromstring(data)
                cell = root.find(f'.//{{{MAIN}}}c[@r="{address}"]')
                if cell is None:
                    raise ValueError(f"missing_cell:{sheet}!{address}")
                if formula is not None:
                    f = cell.find(f"{{{MAIN}}}f")
                    if f is None:
                        f = ET.Element(f"{{{MAIN}}}f")
                        cell.insert(0, f)
                    f.text = formula.removeprefix("=")
                    cached = cell.find(f"{{{MAIN}}}v")
                    if cached is not None:
                        cell.remove(cached)
                if value is not None:
                    v = cell.find(f"{{{MAIN}}}v")
                    if v is None:
                        v = ET.SubElement(cell, f"{{{MAIN}}}v")
                    v.text = value
                data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            zout.writestr(info, data)


class RetailWorkingCapitalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory(prefix="sec-retail-working-capital-test-")
        cls.root = Path(cls.temp.name)
        cls.manifest = build(cls.root)
        cls.seed = cls.root / "actor/task.xlsx"
        cls.reference = cls.root / "private/reference.xlsx"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_substantive_source_and_positive_oracle(self) -> None:
        self.assertEqual(self.manifest["source_rows"], 112)
        self.assertEqual(self.manifest["formula_cells"], 92)
        self.assertEqual(self.manifest["injected_faults"], 9)
        result = verify(self.reference, self.seed, self.reference)
        self.assertTrue(result["pass"], result)
        self.assertEqual(result["repaired_faults"], 9)
        self.assertEqual(result["private_replay_profiles"], 2)

    def test_fetched_audit_has_source_provenance_without_claiming_workbook_admission(self) -> None:
        audit = json.loads((HERE / "candidate_audit_fetched_2026-09-24.json").read_text())
        excerpt = json.loads((HERE / "sources/retail_excerpt.json").read_text())
        self.assertEqual(audit["counts"], {
            "candidates": 18, "snapshots_audited": 18, "eligible_sources": 6,
            "rejected_sources": 12, "pending_snapshots": 0, "fetch_errors": 0,
        })
        by_ticker = {row["ticker"]: row for row in audit["results"]}
        for source in excerpt["source_meta"]:
            self.assertEqual(source["sha256_raw_json"], by_ticker[source["ticker"]]["sha256_raw_json"])
        self.assertEqual(by_ticker["COST"]["status"], "eligible_source")
        self.assertEqual(by_ticker["WMT"]["status"], "rejected")

    def test_deterministic_rebuild(self) -> None:
        another = self.root / "another"
        build(another)
        for relative in ("actor/task.xlsx", "private/reference.xlsx"):
            self.assertEqual(hashlib.sha256((self.root / relative).read_bytes()).hexdigest(),
                             hashlib.sha256((another / relative).read_bytes()).hexdigest())

    def test_unrepaired_seed_and_one_repair(self) -> None:
        result = verify(self.seed, self.seed, self.reference)
        self.assertFalse(result["pass"])
        self.assertEqual(result["repair_score"], 0)
        ref, _, _, _ = load_xlsx(self.reference)
        repaired = self.root / "one-repair.xlsx"
        change_cell(self.seed, repaired, "Year Delta", "F5", formula=ref["Year Delta"]["F5"].formula)
        result = verify(repaired, self.seed, self.reference)
        self.assertFalse(result["pass"])
        self.assertEqual(result["repaired_faults"], 1)
        self.assertAlmostEqual(result["repair_score"], 1 / 9)

    def test_same_value_wrong_filing_fails_development_replay(self) -> None:
        seed, _, _, _ = load_xlsx(self.seed)
        ref, _, _, _ = load_xlsx(self.reference)
        self.assertNotEqual(seed["History"]["G5"].formula, ref["History"]["G5"].formula)
        altered = self.root / "wrong-filing.xlsx"
        change_cell(self.reference, altered, "History", "G5", formula=seed["History"]["G5"].formula)
        result = verify(altered, self.seed, self.reference)
        self.assertFalse(result["pass"])
        self.assertIn("dependency_failure_p1:History!G5", result["errors"])
        self.assertEqual(result["repaired_faults"], 8)

    def test_static_hardcode_fails_development_replay(self) -> None:
        altered = self.root / "hardcoded.xlsx"
        change_cell(self.reference, altered, "History", "G5", formula="16651")
        result = verify(altered, self.seed, self.reference)
        self.assertFalse(result["pass"])
        self.assertIn("dependency_failure_p1:History!G5", result["errors"])

    def test_source_and_correct_formula_regressions_rejected(self) -> None:
        modified_source = self.root / "source-tamper.xlsx"
        change_cell(self.reference, modified_source, "Raw SEC", "N5", value="999999999")
        result = verify(modified_source, self.seed, self.reference)
        self.assertFalse(result["pass"])
        self.assertIn("non_target_cell_changed:Raw SEC!N5", result["errors"])
        modified_formula = self.root / "correct-formula-change.xlsx"
        change_cell(self.reference, modified_formula, "History", "J5", formula="(F5+G5)*0.5")
        result = verify(modified_formula, self.seed, self.reference)
        self.assertFalse(result["pass"])
        self.assertIn("previously_correct_formula_changed:History!J5", result["errors"])

    def test_replay_changes_all_targets(self) -> None:
        seed, _, _, _ = load_xlsx(self.seed)
        baseline = expected_values(seed)
        changed = set()
        for source, scenario in perturbation_profiles():
            replay = expected_values(seed, source_deltas_m=source, scenario_deltas_m=scenario)
            changed.update(key for key in TARGETS if abs(replay[key] - baseline[key]) > 1e-9)
        self.assertEqual(changed, TARGETS)


if __name__ == "__main__":
    unittest.main()
