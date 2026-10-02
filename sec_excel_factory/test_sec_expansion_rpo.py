"""Source-integrity and adversarial checks for the distinct RPO workflow."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from prepare_rpo_cases import TICKERS, make_case
from test_integrated_candidates import change_cell
from verify_rpo_candidate import expected_values, load_xlsx, verify


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPORT = ROOT / "docs/evidence/sec-source-expansion-16-2026-09-25.json"


class SourceExpansionTest(unittest.TestCase):
    def test_all_sixteen_excerpts_are_pinned_and_filing_distinct(self) -> None:
        report = json.loads(REPORT.read_text())
        self.assertEqual(report["new_issuer_families"], 16)
        self.assertEqual(report["distinct_original_10k_accessions_with_2024_period_end"], 16)
        self.assertEqual(report["total_pinned_fact_rows"], 589)
        self.assertEqual(report["prior_direct_sec_sha256_checks_passed"], 16)
        seen = set()
        for row in report["sources"]:
            source = HERE / "sources/expansion" / f"{row['ticker'].lower()}-end2024-10k.json"
            self.assertEqual(sha256(source.read_bytes()).hexdigest(), row["excerpt_sha256"])
            parsed = json.loads(source.read_text())
            self.assertEqual(parsed["source_raw_json_sha256"], row["raw_sec_json_sha256"])
            self.assertEqual(parsed["filing_accession"], row["filing_accession"])
            self.assertEqual(len(parsed["records"]), row["fact_rows"])
            self.assertEqual({r["accession"] for r in parsed["records"]},
                             {row["filing_accession"]})
            seen.add(row["filing_accession"])
        self.assertEqual(len(seen), 16)
        hd = next(r for r in report["sources"] if r["ticker"] == "HD")
        self.assertEqual(hd["filing_accession"], "0000354950-24-000062")
        self.assertEqual(hd["filing_fiscal_year"], 2023)
        self.assertEqual(hd["filing_filed"], "2024-03-13")

    def test_four_rpo_cases_have_distinct_source_lineage_and_missing_tag_paths(self) -> None:
        report = json.loads(REPORT.read_text())
        cases = [make_case(ticker, report) for ticker in TICKERS]
        self.assertEqual(len({c["cik"] for c in cases}), 4)
        self.assertEqual(len({c["filing_accession"] for c in cases}), 4)
        by_ticker = {c["ticker"]: c for c in cases}
        self.assertIsNone(by_ticker["GOOGL"]["canonical"]["noncurrent"])
        self.assertIsNone(by_ticker["DIS"]["canonical"]["total"])
        self.assertIsNotNone(by_ticker["ORCL"]["canonical"]["noncurrent"])
        self.assertIsNotNone(by_ticker["NVDA"]["canonical"]["total"])


@unittest.skipUnless(shutil.which("node") and (ROOT / "node_modules/@oai/artifact-tool").exists(),
                     "bundled artifact-tool runtime unavailable")
class RpoWorkbookTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory(prefix="sec-rpo-test-")
        cls.path = Path(cls.tmp.name)
        report = json.loads(REPORT.read_text())
        cls.cases = [make_case(ticker, report) for ticker in TICKERS]
        cls.manifest = cls.path / "cases.json"
        cls.manifest.write_text(json.dumps(cls.cases, separators=(",", ":")))
        subprocess.run(["node", str(HERE / "build_rpo_workbooks.mjs"),
                        str(cls.manifest), str(cls.path / "workbooks")],
                       check=True, capture_output=True, text=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def file(self, case: dict, name: str) -> Path:
        return self.path / "workbooks" / case["case_id"] / name

    def test_all_four_reference_positive_and_unrepaired_negative(self) -> None:
        for case in self.cases:
            with self.subTest(case=case["case_id"]):
                seed, gold = self.file(case, "actor.xlsx"), self.file(case, "reference.xlsx")
                result = verify(gold, seed, case)
                self.assertTrue(result["pass"], result)
                self.assertEqual(result["checked_targets"], 43)
                self.assertEqual(result["counterfactual_profiles"], 2)
                self.assertFalse(verify(seed, seed, case)["pass"])
                private = json.loads(self.file(case, "private-oracle.json").read_text())
                self.assertEqual(len(private["faulted"]), 9)

    def test_hardcode_rejected_by_source_replay(self) -> None:
        case = self.cases[0]
        expected = expected_values(case)[("Filing Selection", "B13")]
        changed = self.path / "hardcoded-rpo.xlsx"
        change_cell(self.file(case, "reference.xlsx"), changed, 2, "B13",
                    formula=str(expected))
        result = verify(changed, self.file(case, "actor.xlsx"), case)
        self.assertFalse(result["pass"])
        self.assertIn("numeric_or_dependency_error_p1:Filing Selection!B13", result["errors"])

    def test_source_and_scenario_tampering_rejected(self) -> None:
        case = self.cases[0]
        gold, seed = self.file(case, "reference.xlsx"), self.file(case, "actor.xlsx")
        source_cells, order, _, _ = load_xlsx(gold)
        raw = source_cells["Source 10-K"]
        source_address = next(addr for addr in raw if addr.startswith("H") and addr[1:].isdigit()
                              and int(addr[1:]) >= 5)
        changed = self.path / "raw-edited.xlsx"
        change_cell(gold, changed, order.index("Source 10-K") + 1, source_address, value="123")
        result = verify(changed, seed, case)
        self.assertFalse(result["pass"])
        self.assertTrue(any(e.startswith("non_target_cell_changed:Source 10-K!") for e in result["errors"]))
        changed2 = self.path / "scenario-edited.xlsx"
        change_cell(gold, changed2, order.index("RPO Scenario") + 1, "B5", value="0.99")
        result = verify(changed2, seed, case)
        self.assertFalse(result["pass"])
        self.assertIn("non_target_cell_changed:RPO Scenario!B5", result["errors"])


if __name__ == "__main__":
    unittest.main()
