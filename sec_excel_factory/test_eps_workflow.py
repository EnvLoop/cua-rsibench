"""Mixed-unit source and adversarial OOXML checks for EPS development cases."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from audit_eps_workflows import audit
from prepare_eps_cases import TICKERS, make_case
from test_integrated_candidates import change_cell
from verify_eps_candidate import expected_values, load_xlsx, verify


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPORT = ROOT / "docs/evidence/sec-eps-sources-2026-09-25.json"


class EpsSourceTest(unittest.TestCase):
    def test_four_mixed_unit_filing_excerpts_are_exactly_pinned(self) -> None:
        report = json.loads(REPORT.read_text())
        self.assertEqual(report["issuers"], 4)
        self.assertEqual(report["total_fact_rows"], 84)
        self.assertEqual(report["units"], ["USD", "USD/shares", "shares"])
        self.assertEqual(report["original_accessions"], 4)
        for row in report["sources"]:
            path = HERE / "sources/eps" / f"{row['ticker'].lower()}-end2024-eps.json"
            self.assertEqual(sha256(path.read_bytes()).hexdigest(), row["excerpt_sha256"])
            source = json.loads(path.read_text())
            self.assertEqual({r["accession"] for r in source["records"]},
                             {row["original_accession"]})
            self.assertEqual({r["unit"] for r in source["records"]},
                             {"USD", "shares", "USD/shares"})
        cases = [make_case(ticker, report) for ticker in TICKERS]
        self.assertEqual(len({c["cik"] for c in cases}), 4)
        self.assertTrue(all(len(c["canonical"]) == 14 for c in cases))
        self.assertTrue(all(len(expected_values(c)) == 50 for c in cases))


@unittest.skipUnless(shutil.which("node") and (ROOT / "node_modules/@oai/artifact-tool").exists(),
                     "bundled artifact-tool runtime unavailable")
class EpsWorkbookTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory(prefix="sec-eps-test-")
        cls.path = Path(cls.tmp.name)
        report = json.loads(REPORT.read_text())
        cls.cases = [make_case(ticker, report) for ticker in TICKERS]
        cls.manifest = cls.path / "cases.json"
        cls.manifest.write_text(json.dumps(cls.cases, separators=(",", ":")))
        subprocess.run(["node", str(HERE / "build_eps_workbooks.mjs"),
                        str(cls.manifest), str(cls.path / "workbooks")],
                       check=True, capture_output=True, text=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def file(self, case: dict, name: str) -> Path:
        return self.path / "workbooks" / case["case_id"] / name

    def test_all_four_positive_negative_and_isolated_faults(self) -> None:
        for case in self.cases:
            with self.subTest(case=case["case_id"]):
                seed, ref = self.file(case, "actor.xlsx"), self.file(case, "reference.xlsx")
                result = verify(ref, seed, case)
                self.assertTrue(result["pass"], result)
                self.assertEqual(result["checked_targets"], 50)
                self.assertEqual(result["counterfactual_profiles"], 2)
                self.assertFalse(verify(seed, seed, case)["pass"])
        receipt = audit(self.manifest, self.path / "workbooks")
        self.assertEqual(receipt["positive_reference_passes"], 4)
        self.assertTrue(receipt["every_fault_detected_in_isolation_under_baseline_or_two_replays"])

    def test_hardcoded_eps_and_collateral_edit_rejected(self) -> None:
        case = self.cases[0]
        seed, ref = self.file(case, "actor.xlsx"), self.file(case, "reference.xlsx")
        expected = expected_values(case)[("Filing Selection", "C9")]
        changed = self.path / "hardcoded-eps.xlsx"
        change_cell(ref, changed, 2, "C9", formula=str(expected))
        result = verify(changed, seed, case)
        self.assertFalse(result["pass"])
        self.assertIn("numeric_or_dependency_error_p1:Filing Selection!C9", result["errors"])
        cells, order, _, _ = load_xlsx(ref)
        raw = cells["Source 10-K"]
        address = next(a for a in raw if a.startswith("H") and a[1:].isdigit()
                       and int(a[1:]) >= 5)
        changed2 = self.path / "edited-source.xlsx"
        change_cell(ref, changed2, order.index("Source 10-K") + 1, address, value="123")
        result = verify(changed2, seed, case)
        self.assertFalse(result["pass"])
        self.assertTrue(any(e.startswith("non_target_cell_changed:Source 10-K!") for e in result["errors"]))


if __name__ == "__main__":
    unittest.main()
