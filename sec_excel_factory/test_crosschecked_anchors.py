"""Keep the ten SEC-view-supported source anchors narrow and reproducible."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from freeze_crosschecked_anchors import freeze


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPORT = ROOT / "docs/evidence/sec-ten-official-crosschecked-anchors-2026-09-25.json"
CROSSCHECKS = HERE / "new_issuer_official_crosschecks.json"
RAW = ROOT / "work/sec-expansion/new-ten"


class OfficialAnchorTest(unittest.TestCase):
    def test_published_tier_has_only_twenty_verified_facts(self) -> None:
        report = json.loads(REPORT.read_text())
        self.assertEqual(report["new_issuer_families_with_two_verified_anchors"], 10)
        self.assertEqual(report["anchor_facts_verified"], 20)
        self.assertEqual(report["total_issuer_identities_with_at_least_two_official_anchors"], 28)
        self.assertEqual(report["full_raw_direct_hash_pinned_issuers_after_expansion"], 18)
        self.assertEqual(report["hidden_final_source_families_admitted"], 0)
        self.assertEqual(len({r["accession"] for r in report["sources"]}), 10)
        for entry in report["sources"]:
            path = HERE / "sources/anchors" / f"{entry['ticker'].lower()}-end2024-two-anchors.json"
            self.assertEqual(sha256(path.read_bytes()).hexdigest(), entry["two_fact_excerpt_sha256"])
            source = json.loads(path.read_text())
            self.assertEqual(len(source["facts"]), 2)
            self.assertEqual({f["accession"] for f in source["facts"]}, {entry["accession"]})
            self.assertEqual(source["filing_fiscal_year"], entry["fiscal_year"])
            self.assertEqual(source["filing_period_end"], entry["period_end"])
            self.assertEqual({f["concept"] for f in source["facts"]} & {"Assets"}, {"Assets"})
            self.assertTrue(all(f["unit"] == "USD" for f in source["facts"]))
        low = next(r for r in report["sources"] if r["ticker"] == "LOW")
        self.assertEqual(low["fiscal_year"], 2023)
        self.assertEqual(low["accession"], "0000060667-24-000033")

    @unittest.skipUnless(RAW.is_dir(), "captured proxy candidates are intentionally not committed")
    def test_reextract_and_reject_false_official_value(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sec-anchors-test-") as tmp:
            out = Path(tmp)
            report = freeze(RAW, CROSSCHECKS, out / "good")
            self.assertEqual(report["anchor_facts_verified"], 20)
            published = json.loads(REPORT.read_text())
            self.assertEqual(report["sources"], published["sources"])
            altered = json.loads(CROSSCHECKS.read_text())
            altered["records"][0]["revenue_usd_m"] += 1
            wrong = out / "wrong-crosschecks.json"
            wrong.write_text(json.dumps(altered))
            with self.assertRaisesRegex(ValueError, "official_revenue_value_not_found"):
                freeze(RAW, wrong, out / "bad")


if __name__ == "__main__":
    unittest.main()
