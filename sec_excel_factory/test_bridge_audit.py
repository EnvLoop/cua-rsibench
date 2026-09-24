"""Mutation checks for the independent blind-repair verifier."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from build_bridge_audit import build
from verify_bridge_audit import SHEETS, TARGETS, expected_values, perturbation_profiles, verify
from verify_ooxml import load_xlsx


MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def change_cell(source: Path, output: Path, sheet: str, address: str, *, formula: str | None = None,
                value: str | None = None) -> None:
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


class BridgeAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory(prefix="sec-bridge-audit-test-")
        cls.path = Path(cls.temp.name)
        cls.manifest = build(cls.path)
        cls.seed = cls.path / "actor/task.xlsx"
        cls.gold = cls.path / "private/reference.xlsx"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_built_task_is_substantive_and_positive_passes(self) -> None:
        self.assertEqual(self.manifest["source_rows"], 177)
        self.assertEqual(self.manifest["formula_cells"], 114)
        self.assertEqual(self.manifest["injected_faults"], 9)
        result = verify(self.gold, self.seed, self.gold)
        self.assertTrue(result["pass"], result)
        self.assertEqual(result["checked_targets"], 114)
        self.assertEqual(result["allowed_repairs"], 9)
        self.assertEqual(result["private_replay_profiles"], 2)
        self.assertEqual(result["repaired_faults"], 9)
        self.assertEqual(result["repair_score"], 1.0)

    def test_build_is_byte_reproducible_for_reset_checksums(self) -> None:
        other = self.path / "second-build"
        build(other)
        for relative in ("actor/task.xlsx", "private/reference.xlsx"):
            first_digest = hashlib.sha256((self.path / relative).read_bytes()).hexdigest()
            second_digest = hashlib.sha256((other / relative).read_bytes()).hexdigest()
            self.assertEqual(first_digest, second_digest, relative)

    def test_unrepaired_seed_fails_even_when_wrong_filing_has_same_value(self) -> None:
        result = verify(self.seed, self.seed, self.gold)
        self.assertFalse(result["pass"], result)
        seed, _, _, _ = load_xlsx(self.seed)
        gold, _, _, _ = load_xlsx(self.gold)
        # This fault can be missed by a static workbook-value comparison.
        self.assertNotEqual(seed["Historical"]["D6"].formula, gold["Historical"]["D6"].formula)
        self.assertTrue(any(x.startswith("wrong_result:") for x in result["errors"]), result)
        self.assertEqual(result["repair_score"], 0.0)

    def test_same_value_wrong_filing_rejected_by_private_perturbation(self) -> None:
        seed, _, _, _ = load_xlsx(self.seed)
        modified = self.path / "wrong-filing.xlsx"
        change_cell(self.gold, modified, "Historical", "D6", formula=seed["Historical"]["D6"].formula)
        result = verify(modified, self.seed, self.gold)
        self.assertFalse(result["pass"], result)
        self.assertIn("dependency_failure_p1:Historical!D6", result["errors"])
        self.assertEqual(result["repaired_faults"], 8)

    def test_static_hardcode_rejected_by_private_perturbation(self) -> None:
        modified = self.path / "hardcoded-revenue.xlsx"
        change_cell(self.gold, modified, "Historical", "D6", formula="391035")
        result = verify(modified, self.seed, self.gold)
        self.assertFalse(result["pass"], result)
        self.assertIn("dependency_failure_p1:Historical!D6", result["errors"])
        self.assertEqual(result["repaired_faults"], 8)

    def test_one_repaired_fault_receives_isolated_partial_credit(self) -> None:
        reference, _, _, _ = load_xlsx(self.gold)
        modified = self.path / "one-repair.xlsx"
        change_cell(self.seed, modified, "Q4 Bridge", "E11", formula=reference["Q4 Bridge"]["E11"].formula)
        result = verify(modified, self.seed, self.gold)
        self.assertFalse(result["pass"], result)
        self.assertEqual(result["repaired_faults"], 1)
        self.assertAlmostEqual(result["repair_score"], 1 / 9)

    def test_hidden_replays_change_every_target_at_least_once(self) -> None:
        seed, _, _, _ = load_xlsx(self.seed)
        baseline = expected_values(seed)
        changed = set()
        for source_deltas, scenarios in perturbation_profiles():
            replay = expected_values(seed, source_deltas_m=source_deltas, scenario_deltas=scenarios)
            changed.update(key for key in TARGETS if not abs(replay[key] - baseline[key]) < 1e-9)
        self.assertEqual(changed, TARGETS)

    def test_unrelated_formula_regression_is_rejected(self) -> None:
        modified = self.path / "new-regression.xlsx"
        change_cell(self.gold, modified, "Board Review", "G5", formula="Forecast!D6+0")
        result = verify(modified, self.seed, self.gold)
        self.assertFalse(result["pass"], result)
        self.assertIn("previously_correct_formula_changed:Board Review!G5", result["errors"])

    def test_source_tampering_is_rejected(self) -> None:
        gold, _, _, _ = load_xlsx(self.gold)
        row = next(i for i in range(5, 182) if gold["Raw SEC"].get(f"B{i}")
                   and gold["Raw SEC"][f"B{i}"].value == "Apple"
                   and gold["Raw SEC"].get(f"D{i}")
                   and gold["Raw SEC"][f"D{i}"].value == "Revenue")
        modified = self.path / "source-tampered.xlsx"
        change_cell(self.gold, modified, "Raw SEC", f"O{row}", value="123456789")
        result = verify(modified, self.seed, self.gold)
        self.assertFalse(result["pass"], result)
        self.assertIn(f"non_target_cell_changed:Raw SEC!O{row}", result["errors"])


if __name__ == "__main__":
    unittest.main()
