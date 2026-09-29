"""Source-bound, privacy and retry checks for the SEC TRAIN raw pool."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import sec_excel_train_22_raw_capture_v1 as lane
from tools import audit_sec_excel_train_22_raw_capture_v1 as independent


class SECTrainRawCaptureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cards = {"cards": [{"final_graph_reservation": f"graph-{i}",
                                 "skill_signature_sha256": f"signature-{i}",
                                 "independent_skill_review": True}
                                for i in range(13)]}
        self.registry = {"slots": [
            {"split": "train" if i < 20 else "selection" if i < 40 else "final",
             "issuer_cik": i + 1,
             "original_filing_accession": f"{i+1:010d}-25-000001",
             "semantic_template_reservation": f"heldout-template-{i}"}
            for i in range(140)]}
        self.pilot = {"records": [
            {"final_graph_reservation": f"graph-{i // 2}",
             "issuer_cik": 150 + i, "accession": f"{150+i:010d}-25-000001",
             "template_family": f"pilot-template-{i // 2}"}
            for i in range(4)]}
        self.paths = {}
        for name, value in (("cards", self.cards), ("registry", self.registry),
                            ("pilot", self.pilot)):
            path = self.root / f"{name}.json"
            path.write_text(json.dumps(value))
            self.paths[name] = path
        salt = self.root / "salt"
        salt.write_bytes(b"s" * 32)
        self.paths["salt"] = salt
        rows = []
        for graph in range(2, 13):
            for lane_index in range(2):
                cik = 200 + graph * 2 + lane_index
                rows.append({"final_graph_reservation": f"graph-{graph}",
                             "issuer_cik": cik,
                             "accession": f"{cik:010d}-25-000001",
                             "primary_document": f"issuer{cik}.htm",
                             "index_extension": ".htm",
                             "filing_date": "2025-02-20",
                             "report_period": "2024-12-31", "form": "10-K",
                             "template_family": f"train-template-{graph}",
                             "skill_signature_sha256": f"signature-{graph}"})
        self.plan = {"schema": lane.PLAN_SCHEMA,
                     "registry_sha256": sha256(self.paths["registry"].read_bytes()).hexdigest(),
                     "cards_sha256": sha256(self.paths["cards"].read_bytes()).hexdigest(),
                     "prior_pilot_sha256": sha256(self.paths["pilot"].read_bytes()).hexdigest(),
                     "records": rows}
        plan_path = self.root / "plan.json"
        plan_path.write_text(json.dumps(self.plan))
        self.paths["plan"] = plan_path

    def args(self) -> dict:
        return {"plan_path": self.paths["plan"],
                "registry_path": self.paths["registry"],
                "cards_path": self.paths["cards"],
                "pilot_path": self.paths["pilot"],
                "salt_path": self.paths["salt"],
                "out_dir": self.root / "raw",
                "public_out": self.root / "public.json",
                "user_agent": "EnvLoop Research contact@example.org"}

    def test_plan_checks_all_140_and_two_per_new_graph(self) -> None:
        plan, salt = lane._load_inputs(
            self.paths["plan"], self.paths["registry"], self.paths["cards"],
            self.paths["pilot"], self.paths["salt"])
        self.assertEqual(len(plan["records"]), 22)
        self.assertEqual(len(salt), 32)
        bad = json.loads(json.dumps(self.plan))
        bad["records"][0]["issuer_cik"] = 1
        self.paths["plan"].write_text(json.dumps(bad))
        with self.assertRaisesRegex(ValueError, "issuer_collision"):
            lane._load_inputs(self.paths["plan"], self.paths["registry"],
                              self.paths["cards"], self.paths["pilot"],
                              self.paths["salt"])

    def test_source_identity_rejects_wrong_form(self) -> None:
        row = self.plan["records"][0]
        raw = self._raw(row)
        self.assertGreater(lane._source_identity(row, raw)["companyfacts_accession_fact_count"], 0)
        bad = json.loads(raw["submissions"])
        bad["filings"]["recent"]["form"] = ["10-Q"]
        raw["submissions"] = json.dumps(bad).encode()
        with self.assertRaisesRegex(ValueError, "submission_identity_mismatch"):
            lane._source_identity(row, raw)

    def test_incorporated_filing_document_requires_same_index(self) -> None:
        row = dict(self.plan["records"][0])
        row["supporting_document"] = "annual-exhibit-13.htm"
        raw = self._raw(row)
        raw["support"] = b"<html>source facts</html>" * 60
        with self.assertRaisesRegex(ValueError, "supporting_exhibit_13_not_in"):
            lane._source_identity(row, raw)
        raw["index"] = raw["index"].replace(
            b"<td>10-K</td>",
            b"<td>10-K</td><tr><td>EX-13</td><td>annual-exhibit-13.htm</td></tr>")
        self.assertTrue(lane._source_identity(row, raw)["index_form_match"])

    def _raw(self, row: dict) -> dict[str, bytes]:
        return {
            "submissions": json.dumps({"cik": f'{row["issuer_cik"]:010d}',
                "filings": {"recent": {
                    "accessionNumber": [row["accession"]],
                    "form": ["10-K"],
                    "primaryDocument": [row["primary_document"]],
                    "filingDate": [row["filing_date"]],
                    "reportDate": [row["report_period"]]}}}).encode(),
            "index": (f"<html>{row['accession']} {row['primary_document']} "
                      f"{row['filing_date']} {row['report_period']}"
                      "<td>10-K</td></html>").encode(),
            "10k": b"<html>FORM 10-K annual report</html>",
            "companyfacts": json.dumps({"cik": row["issuer_cik"],
                "facts": {"us-gaap": {"Assets": {"units": {"USD": [
                    {"accn": row["accession"], "form": "10-K", "val": 1}]}}}}}).encode(),
        }

    def test_partial_capture_resume_and_public_privacy(self) -> None:
        url_data = {}
        for row in self.plan["records"][:2]:
            for kind, url in lane._urls(row).items():
                url_data[url] = self._raw(row)[kind]

        def fake_fetch(url: str, *, ip: str, user_agent: str, out: Path) -> dict:
            raw = url_data[url]
            out.write_bytes(raw)
            return {"status": 200, "tls_verify_result": 0,
                    "remote_ip": ip, "url": url, "bytes": len(raw),
                    "sha256": sha256(raw).hexdigest()}

        with patch.object(lane, "_global_ip", return_value="8.8.8.8"), \
             patch.object(lane, "_fetch", side_effect=fake_fetch), \
             patch.object(lane.time, "sleep"):
            first = lane.capture(**self.args(), max_new=2)
        self.assertEqual(first["original_sec_10k_source_bundles_captured"], 2)
        self.assertEqual(first["new_excel_web_admitted_train_cases"], 0)
        public_raw = self.paths["plan"].read_text()
        receipt_raw = self.args()["public_out"].read_text()
        self.assertNotEqual(public_raw, receipt_raw)
        for row in self.plan["records"]:
            self.assertNotIn(row["accession"], receipt_raw)
            self.assertNotIn(f'"issuer_cik": {row["issuer_cik"]}', receipt_raw)
        second = lane.capture(**self.args(), max_new=0)
        self.assertEqual(second["original_sec_10k_source_bundles_captured"], 2)
        audit = independent.audit(
            plan_path=self.paths["plan"], registry_path=self.paths["registry"],
            cards_path=self.paths["cards"], pilot_path=self.paths["pilot"],
            salt_path=self.paths["salt"], raw_root=self.args()["out_dir"],
            public_capture_path=self.args()["public_out"])
        self.assertEqual(audit["source_bundles_reopened"], 2)
        one = self.args()["out_dir"] / "source-00" / "10k.html"
        one.write_bytes(one.read_bytes() + b"tamper")
        with self.assertRaisesRegex(ValueError, "saved_source_hash_changed"):
            lane.capture(**self.args(), max_new=0)
        with self.assertRaisesRegex(ValueError, "saved_raw_response_hash"):
            independent.audit(
                plan_path=self.paths["plan"], registry_path=self.paths["registry"],
                cards_path=self.paths["cards"], pilot_path=self.paths["pilot"],
                salt_path=self.paths["salt"], raw_root=self.args()["out_dir"],
                public_capture_path=self.args()["public_out"])


if __name__ == "__main__":
    unittest.main()
