"""Synthetic fail-closed checks for the field-limited SEC source screen."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from tools.sec_excel_transfer_source_availability_v1 import audit


def _record(issuer: int, accession: str, graph: str, lane: str,
            profile: str, signature: str) -> dict:
    document = f"filing-{issuer}.htm"
    base = (f"https://www.sec.gov/Archives/edgar/data/{issuer}/"
            f"{accession.replace('-', '')}/")
    if profile == "cash":
        periods = [
            dict(period_end="2025-12-31", operating=10, investing=-4,
                 financing=-2, fx=1, net_change=5, beginning=20, ending=25,
                 cash=20, restricted=5),
            dict(period_end="2024-12-31", operating=9, investing=-3,
                 financing=-2, fx=0, net_change=4, beginning=16, ending=20,
                 cash=16, restricted=4),
        ]
    else:
        periods = [
            dict(period_end="2025-12-31", operating_income=100,
                 interest_expense_abs=20, cash_from_operations=80,
                 debt_principal_components=[50, 50], debt_principal_total=100),
            dict(period_end="2024-12-31", operating_income=90,
                 interest_expense_abs=18, cash_from_operations=70,
                 debt_principal_components=[40, 50], debt_principal_total=90),
        ]
    return dict(final_graph_reservation=graph, analogue_lane=lane,
                issuer_cik=issuer, accession=accession,
                primary_document=document, primary_document_type_checked="10-K",
                template_family=f"train-{graph}", skill_signature_sha256=signature,
                sec_filing_index_url=base + accession + "-index.htm",
                sec_original_10k_url=base + document, periods=periods,
                raw_source_bytes_captured=False,
                companyfacts_snapshot_captured=False,
                independent_fact_review_completed=False)


class SourceAvailabilityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        slots = []
        for split, count in (("train", 20), ("selection", 20), ("final", 100)):
            for _ in range(count):
                idx = len(slots)
                slots.append(dict(split=split, issuer_cik=10000 + idx,
                                  original_filing_accession=f"0000000001-24-{idx:06d}",
                                  semantic_template_reservation=f"original-{idx}"))
        cards = [dict(final_graph_reservation=f"g{i}",
                      skill_signature_sha256=f"{i + 1:064x}",
                      independent_skill_review=True) for i in range(13)]
        self.registry = self.root / "registry.json"
        self.cards = self.root / "cards.json"
        self.registry.write_text(json.dumps(dict(slots=slots)))
        self.cards.write_text(json.dumps(dict(cards=cards)))
        self.salt = self.root / "salt"
        self.salt.write_bytes(b"s" * 32)
        records = []
        for i, (graph, profile, lane) in enumerate((
                ("g0", "cash", "A"), ("g0", "cash", "B"),
                ("g1", "interest", "A"), ("g1", "interest", "B"))):
            records.append(_record(20000 + i, f"0000000002-25-{i:06d}",
                                   graph, lane, profile,
                                   cards[int(graph[1:])]["skill_signature_sha256"]))
        self.pilot = dict(schema="envloop-sec-excel-two-graph-source-availability-private-v1",
                          original_140_registry_sha256=sha256(self.registry.read_bytes()).hexdigest(),
                          reviewed_cards_sha256=sha256(self.cards.read_bytes()).hexdigest(),
                          records=records)
        self.pilot_path = self.root / "pilot.json"

    def screen(self) -> dict:
        self.pilot_path.write_text(json.dumps(self.pilot))
        return audit(registry_path=self.registry, cards_path=self.cards,
                     pilot_path=self.pilot_path, salt_path=self.salt)

    def test_four_source_pilot_exports_no_private_identity(self) -> None:
        result = self.screen()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["two_period_fact_profiles_arithmetic_checked"], 4)
        self.assertEqual(result["admitted_train_analogues"], 0)
        public = json.dumps(result)
        self.assertNotIn("20000", public)
        self.assertNotIn("0000000002-25-000000", public)

    def test_cash_flow_tamper_fails(self) -> None:
        self.pilot["records"][0]["periods"][0]["operating"] += 1
        self.assertIn("cash_flow_bridge_mismatch", self.screen()["errors"])

    def test_debt_component_tamper_fails(self) -> None:
        self.pilot["records"][2]["periods"][0]["debt_principal_components"][0] += 1
        self.assertIn("debt_components_mismatch", self.screen()["errors"])

    def test_original_issuer_overlap_fails_and_is_counted(self) -> None:
        row = self.pilot["records"][0]
        row["issuer_cik"] = 10000
        row["sec_filing_index_url"] = row["sec_filing_index_url"].replace(
            "/20000/", "/10000/")
        row["sec_original_10k_url"] = row["sec_original_10k_url"].replace(
            "/20000/", "/10000/")
        result = self.screen()
        self.assertIn("original_or_pilot_source_overlap", result["errors"])
        self.assertEqual(result["source_issuer_overlap_count"], 1)

    def test_raw_capture_claim_without_evidence_fails(self) -> None:
        self.pilot["records"][0]["raw_source_bytes_captured"] = True
        self.assertIn("unsupported_source_admission_claim", self.screen()["errors"])

    def test_non_sec_source_url_fails(self) -> None:
        self.pilot["records"][0]["sec_original_10k_url"] = (
            "https://example.com/not-an-original-10k.htm")
        self.assertIn("original_sec_filing_identity_mismatch", self.screen()["errors"])


if __name__ == "__main__":
    unittest.main()
