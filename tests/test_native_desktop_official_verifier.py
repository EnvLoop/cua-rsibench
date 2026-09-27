"""Fair target semantics must not weaken saved-artifact no-regression guards."""

from __future__ import annotations

import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from native_desktop_factory.official_saved_verifier import verify_official
from native_desktop_factory.verify import S, verify as legacy_verify
from tests.test_native_desktop_factory import rewrite_member


ROOT = Path(__file__).resolve().parents[1] / "native_desktop_factory" / "dev-fixtures"
SALT = "evaluator-private-test-salt-0123456789"


def fixture(workflow: str, ext: str):
    path = ROOT / f"wdi-native-mex-{workflow}"
    return (path / f"wdi-native-mex-{workflow}.{ext}").read_bytes(), json.loads((path / "oracle.json").read_bytes())


class OfficialSemanticVerifierTests(unittest.TestCase):
    def test_algebraic_calc_equivalence_without_a_constant_shortcut(self):
        baseline, oracle = fixture("calc-growth", "xlsx")
        alternate = "('WDI facts'!B9-'WDI facts'!B8)/'WDI facts'!B8*100"

        def set_formula(raw: bytes) -> bytes:
            root = ET.fromstring(raw)
            ns = {"s": S}
            cell = root.find(".//s:sheetData/s:row/s:c[@r='B4']", ns)
            cell.find("s:f", ns).text = alternate
            value = cell.find("s:v", ns)
            value.text = str(oracle["targets"]["Review!B4"]["expected_value"])
            return ET.tostring(root)

        saved = rewrite_member(baseline, "xl/worksheets/sheet2.xml", set_formula)
        self.assertFalse(legacy_verify(baseline, saved, oracle)["passed"])
        self.assertTrue(verify_official(baseline, saved, oracle, private_salt=SALT)["passed"])
        with self.assertRaisesRegex(ValueError, "private"):
            verify_official(baseline, saved, oracle, private_salt="short")

    def test_numeric_impress_paraphrase_preserves_other_shapes(self):
        baseline, oracle = fixture("impress-deck", "pptx")
        old = next(iter(oracle["targets"]))
        saved = rewrite_member(baseline, "ppt/slides/slide3.xml",
                               lambda raw: raw.replace(old.encode(), b"2024 GDP grew 2.01%"))
        self.assertFalse(legacy_verify(baseline, saved, oracle)["passed"])
        self.assertTrue(verify_official(baseline, saved, oracle, private_salt=SALT)["passed"])

    def test_writer_paraphrase_passes_but_table_corruption_fails(self):
        baseline, oracle = fixture("writer-brief", "docx")
        old = next(iter(oracle["targets"]))
        saved = rewrite_member(baseline, "word/document.xml",
                               lambda raw: raw.replace(old.encode(), b"GDP increased 2.01% in 2024 from 2023."))
        self.assertFalse(legacy_verify(baseline, saved, oracle)["passed"])
        self.assertTrue(verify_official(baseline, saved, oracle, private_salt=SALT)["passed"])
        collateral = rewrite_member(saved, "word/document.xml",
                                    lambda raw: raw.replace(b"1,304.1", b"9,999.9"))
        result = verify_official(baseline, collateral, oracle, private_salt=SALT)
        self.assertFalse(result["passed"])
        self.assertIn("source_table_changed", result["errors"])


if __name__ == "__main__":
    unittest.main()
