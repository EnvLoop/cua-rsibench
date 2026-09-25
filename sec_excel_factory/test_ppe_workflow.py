"""PPE source provenance and adversarial OOXML controls."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from audit_ppe_workflows import audit
from prepare_ppe_cases import TICKERS, make_case
from test_integrated_candidates import change_cell
from verify_ppe_candidate import expected_values, load_xlsx, verify


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPORT = ROOT / "docs/evidence/sec-ppe-sources-2026-09-25.json"


class PpeSourceTest(unittest.TestCase):
    def test_five_exact_original_ppe_source_families(self) -> None:
        report = json.loads(REPORT.read_text())
        self.assertEqual(report["issuers"], 5)
        self.assertEqual(report["original_accessions"], 5)
        self.assertEqual(report["total_fact_rows"], 72)
        for row in report["sources"]:
            path = HERE / "sources/ppe" / f"{row['ticker'].lower()}-end2024-ppe.json"
            self.assertEqual(sha256(path.read_bytes()).hexdigest(), row["excerpt_sha256"])
            source = json.loads(path.read_text())
            self.assertEqual({r["accession"] for r in source["records"]}, {row["accession"]})
        cases = [make_case(ticker, report) for ticker in TICKERS]
        self.assertEqual(len({c["cik"] for c in cases}), 5)
        self.assertTrue(all(len(c["canonical"]) == 12 for c in cases))
        self.assertTrue(all(len(expected_values(c)) == 55 for c in cases))


@unittest.skipUnless(shutil.which("node") and (ROOT / "node_modules/@oai/artifact-tool").exists(),
                     "bundled artifact-tool runtime unavailable")
class PpeWorkbookTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory(prefix="sec-ppe-test-")
        cls.path = Path(cls.tmp.name)
        report = json.loads(REPORT.read_text())
        cls.cases = [make_case(ticker, report) for ticker in TICKERS]
        cls.manifest = cls.path / "cases.json"
        cls.manifest.write_text(json.dumps(cls.cases, separators=(",", ":")))
        subprocess.run(["node", str(HERE / "build_ppe_workbooks.mjs"),
                        str(cls.manifest), str(cls.path / "workbooks")],
                       check=True, capture_output=True, text=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def file(self, case: dict, name: str) -> Path:
        return self.path / "workbooks" / case["case_id"] / name

    def test_reference_positive_seed_negative_and_fault_isolation(self) -> None:
        for case in self.cases:
            with self.subTest(case=case["case_id"]):
                seed, ref = self.file(case, "actor.xlsx"), self.file(case, "reference.xlsx")
                result = verify(ref, seed, case)
                self.assertTrue(result["pass"], result)
                self.assertEqual(result["checked_targets"], 55)
                self.assertEqual(result["counterfactual_profiles"], 2)
                self.assertFalse(verify(seed, seed, case)["pass"])
        receipt = audit(self.manifest, self.path / "workbooks")
        self.assertEqual(receipt["positive_reference_passes"], 5)
        self.assertTrue(receipt["every_fault_detected_in_isolation_under_baseline_or_two_replays"])

    def test_hardcode_and_collateral_source_edit_rejected(self) -> None:
        case = self.cases[0]
        seed, ref = self.file(case, "actor.xlsx"), self.file(case, "reference.xlsx")
        expected = expected_values(case)[("Filing Selection", "C5")]
        static = self.path / "hardcoded-ppe.xlsx"
        change_cell(ref, static, 2, "C5", formula=str(expected))
        result = verify(static, seed, case)
        self.assertFalse(result["pass"])
        self.assertIn("numeric_or_dependency_error_p1:Filing Selection!C5", result["errors"])
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
