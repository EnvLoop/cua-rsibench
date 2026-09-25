"""Filing, counterfactual, and non-target checks for debt-capacity cases."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from audit_debt_workflows import audit
from prepare_debt_cases import TICKERS, make_case
from test_integrated_candidates import change_cell
from verify_debt_candidate import expected_values, load_xlsx, verify


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPORT = ROOT / "docs/evidence/sec-source-expansion-16-2026-09-25.json"


class DebtSourceTest(unittest.TestCase):
    def test_five_distinct_original_filing_sources(self) -> None:
        source_report = json.loads(REPORT.read_text())
        cases = [make_case(ticker, source_report) for ticker in TICKERS]
        self.assertEqual(len({c["cik"] for c in cases}), 5)
        self.assertEqual(len({c["filing_accession"] for c in cases}), 5)
        self.assertEqual(len({c["source_raw_json_sha256"] for c in cases}), 5)
        for case in cases:
            self.assertTrue(case["annual_start"] < case["annual_end"])
            self.assertEqual(len(case["canonical"]), 7)
            self.assertEqual(len(expected_values(case)), 33)


@unittest.skipUnless(shutil.which("node") and (ROOT / "node_modules/@oai/artifact-tool").exists(),
                     "bundled artifact-tool runtime unavailable")
class DebtWorkbookTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory(prefix="sec-debt-test-")
        cls.path = Path(cls.tmp.name)
        source_report = json.loads(REPORT.read_text())
        cls.cases = [make_case(ticker, source_report) for ticker in TICKERS]
        manifest = cls.path / "cases.json"
        manifest.write_text(json.dumps(cls.cases, separators=(",", ":")))
        subprocess.run(["node", str(HERE / "build_debt_workbooks.mjs"),
                        str(manifest), str(cls.path / "workbooks")],
                       check=True, capture_output=True, text=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def file(self, case: dict, filename: str) -> Path:
        return self.path / "workbooks" / case["case_id"] / filename

    def test_positive_negative_and_full_offline_audit(self) -> None:
        for case in self.cases:
            with self.subTest(case=case["case_id"]):
                seed, ref = self.file(case, "actor.xlsx"), self.file(case, "reference.xlsx")
                result = verify(ref, seed, case)
                self.assertTrue(result["pass"], result)
                self.assertEqual(result["checked_targets"], 33)
                self.assertEqual(result["counterfactual_profiles"], 2)
                self.assertFalse(verify(seed, seed, case)["pass"])
        manifest = self.path / "case-for-audit.json"
        manifest.write_text(json.dumps(self.cases))
        receipt = audit(manifest, self.path / "workbooks")
        self.assertEqual(receipt["positive_reference_passes"], 5)
        self.assertTrue(receipt["every_fault_detected_in_isolation_under_baseline_or_two_replays"])

    def test_hardcode_and_source_tamper_are_rejected(self) -> None:
        case = self.cases[0]
        seed, ref = self.file(case, "actor.xlsx"), self.file(case, "reference.xlsx")
        value = expected_values(case)[("Filing Selection", "B5")]
        static = self.path / "hardcoded-debt.xlsx"
        change_cell(ref, static, 2, "B5", formula=str(value))
        result = verify(static, seed, case)
        self.assertFalse(result["pass"])
        self.assertIn("numeric_or_dependency_error_p1:Filing Selection!B5", result["errors"])
        cells, order, _, _ = load_xlsx(ref)
        raw = cells["Source 10-K"]
        addr = next(a for a in raw if a.startswith("H") and a[1:].isdigit() and int(a[1:]) >= 5)
        edited = self.path / "edited-source.xlsx"
        change_cell(ref, edited, order.index("Source 10-K") + 1, addr, value="123")
        result = verify(edited, seed, case)
        self.assertFalse(result["pass"])
        self.assertTrue(any(e.startswith("non_target_cell_changed:Source 10-K!") for e in result["errors"]))


if __name__ == "__main__":
    unittest.main()
