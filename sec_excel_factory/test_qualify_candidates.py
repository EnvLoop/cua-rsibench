"""Mutation checks for admission from frozen real SEC companyfacts data."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from extract_sec import ISSUERS, METRICS
from qualify_candidates import HERE, audit, qualify_snapshot, read_snapshot


class QualifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.candidates = {row["ticker"]: row for row in json.loads(
            (HERE / "candidate_issuers.json").read_text())["candidates"]}
        cls.apple, cls.apple_hash, _ = read_snapshot(HERE / "sources/raw/apple-companyfacts.json.gz")
        cls.microsoft, cls.microsoft_hash, _ = read_snapshot(HERE / "sources/raw/microsoft-companyfacts.json.gz")

    def apple_result(self, data: dict) -> dict:
        return qualify_snapshot(data, self.candidates["AAPL"], self.apple_hash)

    def edit_fact(self, data: dict, tag: str, year: int) -> dict:
        rows = data["facts"]["us-gaap"][tag]["units"]["USD"]
        return next(row for row in rows if row.get("accn") == ISSUERS["Apple"]["filing"]
                    and row.get("end", "").startswith(f"{year}-")
                    and row.get("form") == "10-K")

    def test_two_public_snapshots_qualify_with_exact_source_hashes(self) -> None:
        for ticker, data, digest, issuer in (
            ("AAPL", self.apple, self.apple_hash, "Apple"),
            ("MSFT", self.microsoft, self.microsoft_hash, "Microsoft"),
        ):
            with self.subTest(ticker=ticker):
                self.assertEqual(digest, ISSUERS[issuer]["sha256"])
                result = qualify_snapshot(data, self.candidates[ticker], digest)
                self.assertEqual(result["status"], "eligible_source")
                self.assertEqual(result["accession"], ISSUERS[issuer]["filing"])
                self.assertEqual(len(result["selected_facts"]), 14)
                self.assertEqual(result["balance_gaps_usd"], {"2023": 0, "2024": 0})

    def test_offline_manifest_distinguishes_pending_from_rejected(self) -> None:
        result = audit(HERE / "candidate_issuers.json", HERE / "sources/raw")
        self.assertEqual(result["counts"], {
            "candidates": 18, "snapshots_audited": 2, "eligible_sources": 2,
            "rejected_sources": 0, "pending_snapshots": 16, "fetch_errors": 0,
        })

    def test_rejects_mismatched_cik(self) -> None:
        data = copy.deepcopy(self.apple)
        data["cik"] = 999999
        self.assertIn("cik_mismatch", self.apple_result(data)["reason_codes"])

    def test_rejects_missing_concept_and_wrong_units(self) -> None:
        data = copy.deepcopy(self.apple)
        tag = METRICS["Capital expenditures"]
        del data["facts"]["us-gaap"][tag]
        self.assertIn(f"missing_usd_concept:{tag}", self.apple_result(data)["reason_codes"])

        data = copy.deepcopy(self.apple)
        data["facts"]["us-gaap"][tag]["units"]["USD/shares"] = data["facts"]["us-gaap"][tag]["units"].pop("USD")
        self.assertIn(f"missing_usd_concept:{tag}", self.apple_result(data)["reason_codes"])

    def test_rejects_accession_gap_and_conflicting_duplicate(self) -> None:
        data = copy.deepcopy(self.apple)
        tag = METRICS["Equity"]
        rows = data["facts"]["us-gaap"][tag]["units"]["USD"]
        rows[:] = [r for r in rows if not (
            r.get("accn") == ISSUERS["Apple"]["filing"] and r.get("end") == "2024-09-28")]
        self.assertIn(f"non_unique_annual_fact:2024:{tag}", self.apple_result(data)["reason_codes"])

        data = copy.deepcopy(self.apple)
        tag = METRICS["Revenue"]
        item = self.edit_fact(data, tag, 2024)
        conflict = dict(item, val=item["val"] + 1_000_000_000)
        data["facts"]["us-gaap"][tag]["units"]["USD"].append(conflict)
        self.assertIn(f"non_unique_annual_fact:2024:{tag}", self.apple_result(data)["reason_codes"])

    def test_rejects_start_date_and_balance_inconsistency(self) -> None:
        data = copy.deepcopy(self.apple)
        item = self.edit_fact(data, METRICS["Operating cash flow"], 2024)
        item["start"] = "2023-10-02"
        self.assertIn("flow_start_mismatch:2024", self.apple_result(data)["reason_codes"])

        data = copy.deepcopy(self.apple)
        item = self.edit_fact(data, METRICS["Equity"], 2024)
        item["val"] += 1_000_000_000
        self.assertIn("balance_sheet_gap:2024", self.apple_result(data)["reason_codes"])

    def test_fetch_requires_declared_contact_before_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "SEC_USER_AGENT"):
                audit(HERE / "candidate_issuers.json", Path(tmp), fetch=True, user_agent="")


if __name__ == "__main__":
    unittest.main()
