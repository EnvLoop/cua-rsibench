"""Meaningful source, artifact-verifier, and deterministic-package controls."""

from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile


ROOT = Path(__file__).resolve().parents[1]
from native_desktop_factory import source, verify, factory, admit  # noqa: E402


def rewrite_member(raw: bytes, member: str, transform) -> bytes:
    result = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as source_zip, zipfile.ZipFile(result, "w") as out:
        for item in source_zip.infolist():
            value = source_zip.read(item.filename)
            if item.filename == member:
                value = transform(value)
            out.writestr(item, value)
    return result.getvalue()


class NativeSourceTests(unittest.TestCase):
    def test_pinned_real_observation_cube(self):
        rows = source.load()
        self.assertEqual(len(rows["observations"]), 1050)
        self.assertEqual(len(rows["names"]), 35)
        self.assertEqual(rows["source_sha256"], source.EXPECTED_SHA256)
        facts = source.country_facts(rows, "MEX")
        self.assertGreater(facts["years"]["2024"]["NY.GDP.MKTP.CD"], 0)

    def test_private_country_family_split_rejects_leakage(self):
        countries = list(source.COUNTRIES)
        mapping = {"schema": "cua-native-wdi-private-map-v1", "train": countries[:5],
                   "selection": countries[5:10], "final_candidate": countries[10:],
                   "variant_salt": "a" * 64}
        factory.validate_private_map(mapping)
        mapping["selection"][0] = mapping["train"][0]
        with self.assertRaisesRegex(ValueError, "overlap"):
            factory.validate_private_map(mapping)


class NativeVerifierTests(unittest.TestCase):
    @staticmethod
    def fixture(workflow: str, ext: str):
        path = ROOT / "native_desktop_factory" / "dev-fixtures" / f"wdi-native-mex-{workflow}"
        return (path / f"wdi-native-mex-{workflow}.{ext}").read_bytes(), json.loads((path / "oracle.json").read_bytes())

    def test_calc_positive_wrong_formula_and_non_target_mutation(self):
        baseline, oracle = self.fixture("calc-growth", "xlsx")

        def make(value: bytes, *, wrong: bool = False, corrupt_source: bool = False) -> bytes:
            root = ET.fromstring(value)
            ns = {"s": verify.S}
            cell = root.find(".//s:sheetData/s:row/s:c[@r='B4']", ns)
            cell.find("s:f", ns).text = (
                "('WDI facts'!B9/'WDI facts'!B7-1)*100" if wrong else
                oracle["targets"]["Review!B4"]["formula"].lstrip("=")
            )
            value = cell.find("s:v", ns)
            if value is None:
                value = ET.SubElement(cell, f"{{{verify.S}}}v")
            value.text = str(oracle["targets"]["Review!B4"]["expected_value"])
            return ET.tostring(root)

        good = rewrite_member(baseline, "xl/worksheets/sheet2.xml", make)
        self.assertTrue(verify.verify(baseline, good, oracle)["passed"])
        wrong = rewrite_member(baseline, "xl/worksheets/sheet2.xml", lambda value: make(value, wrong=True))
        self.assertFalse(verify.verify(baseline, wrong, oracle)["passed"])

        def mutate_source(value: bytes) -> bytes:
            root = ET.fromstring(value)
            cell = root.find(f".//{{{verify.S}}}sheetData/{{{verify.S}}}row/{{{verify.S}}}c[@r='B9']")
            cell.find(f"{{{verify.S}}}v").text = "999999999999"
            return ET.tostring(root)

        corrupted = rewrite_member(good, "xl/worksheets/sheet1.xml", mutate_source)
        self.assertIn("non_target_changed:WDI facts!B9", verify.verify(baseline, corrupted, oracle)["errors"])

    def test_impress_positive_wrong_signal_and_collateral_edit(self):
        baseline, oracle = self.fixture("impress-deck", "pptx")
        old, expected = next(iter(oracle["targets"].items()))
        good = rewrite_member(baseline, "ppt/slides/slide3.xml", lambda value: value.replace(old.encode(), expected.encode()))
        self.assertTrue(verify.verify(baseline, good, oracle)["passed"])
        wrong = rewrite_member(baseline, "ppt/slides/slide3.xml", lambda value: value.replace(old.encode(), b"2024 nominal GDP growth: 3.01%"))
        self.assertFalse(verify.verify(baseline, wrong, oracle)["passed"])
        collateral = rewrite_member(good, "ppt/slides/slide3.xml", lambda value: value.replace(b"2024 inflation:", b"2025 inflation:"))
        self.assertTrue(any("non_target_text_changed" in x for x in verify.verify(baseline, collateral, oracle)["errors"]))

        def reorder(value: bytes) -> bytes:
            root = ET.fromstring(value)
            parent = root.find(f"{{{verify.P}}}sldIdLst")
            children = list(parent)
            parent[:] = list(reversed(children))
            return ET.tostring(root)

        reordered = rewrite_member(good, "ppt/presentation.xml", reorder)
        self.assertFalse(verify.verify(baseline, reordered, oracle)["passed"])

    def test_writer_positive_wrong_finding_and_table_corruption(self):
        baseline, oracle = self.fixture("writer-brief", "docx")
        old, expected = next(iter(oracle["targets"].items()))
        good = rewrite_member(baseline, "word/document.xml", lambda value: value.replace(old.encode(), expected.encode()))
        self.assertTrue(verify.verify(baseline, good, oracle)["passed"])
        wrong = rewrite_member(baseline, "word/document.xml", lambda value: value.replace(old.encode(), b"FINDING 1: Nominal GDP grew 3.01% from 2023 to 2024."))
        self.assertFalse(verify.verify(baseline, wrong, oracle)["passed"])
        collateral = rewrite_member(good, "word/document.xml", lambda value: value.replace(b"1,304.1", b"9,999.9"))
        self.assertIn("source_table_changed", verify.verify(baseline, collateral, oracle)["errors"])

    def test_unchanged_baselines_never_pass(self):
        for workflow, ext in (("calc-growth", "xlsx"), ("impress-deck", "pptx"), ("writer-brief", "docx")):
            baseline, oracle = self.fixture(workflow, ext)
            with self.subTest(workflow=workflow):
                self.assertFalse(verify.verify(baseline, baseline, oracle)["passed"])

    def test_actual_e2b_saved_dev_artifacts_discriminate(self):
        """These bytes came from the GUI controls, not a fixture mutator."""
        for task, workflow, ext in (("wdi-native-mex-calc-growth", "calc-growth", "xlsx"),
                                    ("wdi-native-mex-impress-deck-normalized", "impress-deck", "pptx"),
                                    ("wdi-native-mex-writer-brief", "writer-brief", "docx")):
            directory = ROOT / "native_desktop_factory" / "dev-fixtures" / task
            baseline = (directory / f"{task}.{ext}").read_bytes()
            oracle = json.loads((directory / "oracle.json").read_bytes())
            controls = directory / "controls"
            with self.subTest(task=task):
                self.assertTrue(verify.verify(baseline, (controls / f"positive.{ext}").read_bytes(), oracle)["passed"])
                self.assertFalse(verify.verify(baseline, (controls / f"near-miss.{ext}").read_bytes(), oracle)["passed"])

    def test_unnormalized_impress_gui_save_fails_geometry_guard(self):
        baseline, oracle = self.fixture("impress-deck", "pptx")
        saved = ROOT / "native_desktop_factory" / "dev-fixtures" / "wdi-native-mex-impress-deck" / "controls" / "positive.pptx"
        result = verify.verify(baseline, saved.read_bytes(), oracle)
        self.assertFalse(result["passed"])
        self.assertTrue("slide_canvas_changed" in result["errors"] or
                        any(error.startswith("shape_geometry_changed:") for error in result["errors"]))


class CandidateGenerationTests(unittest.TestCase):
    @unittest.skipUnless(all(__import__("importlib").util.find_spec(name) is not None
                             for name in ("openpyxl", "pptx", "docx")),
                         "Office file-generation dependencies unavailable")
    def test_140_candidate_packages_regenerate_byte_identically(self):
        countries = list(source.COUNTRIES)
        mapping = {"schema": "cua-native-wdi-private-map-v1", "train": countries[:5],
                   "selection": countries[5:10], "final_candidate": countries[10:],
                   "variant_salt": "b" * 64}
        with tempfile.TemporaryDirectory() as temporary:
            first = factory.generate(Path(temporary) / "one", mapping)
            second = factory.generate(Path(temporary) / "two", mapping)
            self.assertEqual(first, second)
            self.assertEqual(first["counts"], factory.EXPECTED_COUNTS)
            self.assertEqual({row["workflow"] for row in first["tasks"]}, set(factory.WORKFLOWS))
            with self.assertRaisesRegex(ValueError, "group leaked"):
                admit.audit(Path(temporary) / "one", Path(temporary) / "absent-final-gui")


if __name__ == "__main__":
    unittest.main()
