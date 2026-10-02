"""Synthetic identity and fail-closed tests for SEC raw-source capture."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from tools.sec_excel_transfer_official_raw_capture_v1 import (
    _check_contents, _fetch, _source_urls,
)


CIK = 20000
ACCESSION = "0000000002-25-000001"
BASE = f"https://www.sec.gov/Archives/edgar/data/{CIK}/{ACCESSION.replace('-', '')}/"


def _record() -> dict:
    return {
        "issuer_cik": CIK, "accession": ACCESSION,
        "primary_document": "filing.htm", "filing_date": "2025-02-01",
        "report_period": "2024-12-31",
        "sec_filing_index_url": BASE + ACCESSION + "-index.htm",
        "sec_original_10k_url": BASE + "filing.htm",
        "periods": [
            {"period_end": "2024-12-31", "operating": 10, "investing": -4,
             "financing": -2, "fx": 1, "net_change": 5, "beginning": 20,
             "ending": 25, "cash": 20, "restricted": 5},
            {"period_end": "2023-12-31", "operating": 9, "investing": -3,
             "financing": -2, "fx": 0, "net_change": 4, "beginning": 16,
             "ending": 20, "cash": 16, "restricted": 4},
        ],
    }


def _raw() -> dict[str, bytes]:
    facts = {"cik": CIK, "facts": {"us-gaap": {"OperatingCashFlow": {
        "units": {"USD": [{"accn": ACCESSION, "form": "10-K", "val": 1234000000}]}}}}}
    return {
        "index": (f"<html>{ACCESSION} 2025-02-01 2024-12-31 "
                  "<table><tr><td>1</td><td>filing.htm</td>"
                  "<td>10-K</td></tr></table></html>").encode(),
        "10k": (b"<html><body>FORM 10-K "
                b"10 (4) (2) 1 5 20 25 9 (3) 0 16</body></html>"),
        "companyfacts": json.dumps(facts).encode(),
    }


class OfficialRawCaptureTest(unittest.TestCase):
    def test_valid_sec_urls_and_filed_values(self) -> None:
        urls = _source_urls(_record())
        self.assertEqual(set(urls), {"index", "10k", "companyfacts"})
        result = _check_contents(_record(), _raw())
        self.assertEqual(result["period_numeric_literals_screened"], 18)
        self.assertEqual(result["derived_debt_total_arithmetic_checks"], 0)
        self.assertEqual(result["companyfacts_accession_10k_fact_count"], 1)
        self.assertFalse(result["semantic_fact_review_completed"])

    def test_non_original_or_wrong_filing_url_rejected(self) -> None:
        row = _record()
        row["sec_original_10k_url"] = "https://example.com/filing.htm"
        with self.assertRaisesRegex(ValueError, "private_sec_source_identity_invalid"):
            _source_urls(row)

    def test_index_and_companyfacts_identity_are_required(self) -> None:
        raw = _raw()
        raw["index"] = raw["index"].replace(ACCESSION.encode(), b"wrong-accession")
        with self.assertRaisesRegex(ValueError, "sec_filing_index_identity_mismatch"):
            _check_contents(_record(), raw)
        raw = _raw()
        facts = json.loads(raw["companyfacts"])
        facts["cik"] += 1
        raw["companyfacts"] = json.dumps(facts).encode()
        with self.assertRaisesRegex(ValueError, "companyfacts_cik_mismatch"):
            _check_contents(_record(), raw)

    def test_missing_source_literal_does_not_pass(self) -> None:
        raw = _raw()
        raw["10k"] = raw["10k"].replace(b"25", b"26")
        with self.assertRaisesRegex(ValueError, "original_filing_numeric_literal_missing"):
            _check_contents(_record(), raw)

    def test_derived_debt_total_is_arithmetic_not_filed_literal(self) -> None:
        row = _record()
        row["periods"] = [
            {"period_end": "2024-12-31", "operating_income": 100,
             "interest_expense_abs": 20, "cash_from_operations": 80,
             "debt_principal_components": [30.0, 40.0],
             "debt_principal_total": 70.0},
            {"period_end": "2023-12-31", "operating_income": 90,
             "interest_expense_abs": 18, "cash_from_operations": 72,
             "debt_principal_components": [25.0, 35.0],
             "debt_principal_total": 60.0},
        ]
        raw = _raw()
        raw["10k"] = (b"<html><body>FORM 10-K 100 20 80 30 40 "
                      b"90 18 72 25 35</body></html>")
        result = _check_contents(row, raw)
        self.assertEqual(result["derived_debt_total_arithmetic_checks"], 2)
        self.assertEqual(result["period_numeric_literals_screened"], 10)

    def test_tls_verification_and_exact_effective_url_required(self) -> None:
        url = BASE + "filing.htm"
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "response"
            out.write_bytes(b"x" * 2000)
            for result in ("200\t1\t23.5.4.249\t" + url + "\ttext/html",
                           "200\t0\t23.5.4.249\thttps://example.com/x\ttext/html"):
                with self.subTest(result=result):
                    with patch("subprocess.run", return_value=Mock(
                            returncode=0, stdout=result)):
                        with self.assertRaisesRegex(ValueError,
                                                    "verified_sec_http_200_required"):
                            _fetch(url, ip="23.5.4.249",
                                   user_agent="EnvLoop Research hello@envloop.ai",
                                   out=out)


if __name__ == "__main__":
    unittest.main()
