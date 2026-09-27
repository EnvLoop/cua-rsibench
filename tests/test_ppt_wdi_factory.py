"""Meaningful source, split, and independent OOXML control checks."""

from __future__ import annotations

import json
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

from ppt_wdi_factory import plan, qa, verify
from ppt_wdi_factory.build import DEFAULT_MODULES, DEFAULT_NODE, DEFAULT_PYTHON, DEFAULT_SKILL, prepare_builder, run
from native_desktop_factory import source as wdi_source


def finalized_package(private: Path, row: dict) -> Path:
    package = private / "packages" / "final_candidate" / row["task_id"]
    package.mkdir(parents=True)
    spec = package / "task.private.json"
    spec.write_bytes(plan.canonical(row))
    builder = prepare_builder(private, DEFAULT_MODULES)
    environment = {**os.environ, "PRESENTATIONS_SKILL_DIR": str(DEFAULT_SKILL),
                   "RUNTIME_PYTHON": str(DEFAULT_PYTHON), "RUNTIME_NODE": str(DEFAULT_NODE),
                   "RUNTIME_NODE_MODULES": str(DEFAULT_MODULES)}
    subprocess.run([str(DEFAULT_NODE), str(builder), str(spec), str(package / "draft.pptx")],
                   check=True, capture_output=True, env=environment)
    subprocess.run([str(DEFAULT_NODE), str(Path("ppt_wdi_factory/finalize_deck.mjs").resolve()),
                    str(package / "draft.pptx"), str(package / "source.pptx")],
                   check=True, capture_output=True, env=environment)
    return package


class PptWdiFactoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidates = plan.build(bytes.fromhex("f0" * 32))

    def test_embedded_chart_workbook_repack_preserves_cells_not_edits(self):
        sheet = (b'<worksheet xmlns="http://schemas.openxmlformats.org/'
                 b'spreadsheetml/2006/main"><sheetData><row r="1">'
                 b'<c r="A1" t="n"><v>5.62</v></c></row></sheetData></worksheet>')
        members = {'xl/worksheets/sheet1.xml': sheet,
                   'xl/workbook.xml': b'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>'}
        def pack(rows, compressed):
            out = io.BytesIO()
            with ZipFile(out, 'w', compression=compressed) as archive:
                for name, content in rows:
                    archive.writestr(name, content)
            return out.getvalue()
        first = pack(members.items(), ZIP_DEFLATED)
        repacked = pack(reversed(list(members.items())), 0)
        self.assertNotEqual(first, repacked)
        self.assertTrue(verify._masked_workbook_equal(first, repacked, []))
        altered = dict(members)
        altered['xl/worksheets/sheet1.xml'] = sheet.replace(b'5.62', b'6.62')
        self.assertFalse(verify._masked_workbook_equal(
            first, pack(altered.items(), ZIP_DEFLATED), []))

    def test_140_country_disjoint_candidates_with_distinct_causal_workflows(self):
        sets = self.candidates["sets"]
        self.assertEqual({key: len(rows) for key, rows in sets.items()}, plan.COUNTS)
        countries = {key: {r["source_group"] for r in rows} for key, rows in sets.items()}
        self.assertEqual({key: len(value) for key, value in countries.items()},
                         {"train": 5, "selection": 5, "final_candidate": 25})
        self.assertFalse(countries["train"] & countries["selection"])
        self.assertFalse(countries["train"] & countries["final_candidate"])
        self.assertFalse(countries["selection"] & countries["final_candidate"])
        final = sets["final_candidate"]
        self.assertTrue(all(r["target_keys"] == ["summary", "ledger", "interpretation"]
                            for r in sets["selection"]))
        self.assertEqual({r["workflow"] for r in final}, set(plan.WORKFLOWS))
        self.assertEqual({workflow: sum(r["workflow"] == workflow for r in final)
                          for workflow in plan.WORKFLOWS}, {workflow: 10 for workflow in plan.WORKFLOWS})
        self.assertEqual(len({r["task_id"] for r in final}), 100)
        self.assertTrue(all(r["target_keys"] == verify.FINAL_TARGETS.get(
            r["workflow"], verify.DEFAULT_FINAL_TARGETS) for r in final))
        self.assertTrue(all(r["calculation"]["value"] != r["calculation"]["wrong_value"]
                            for r in final))
        self.assertTrue(all(r["calculation"]["formula"] != r["calculation"]["wrong_formula"]
                            for r in final))

    def test_public_receipt_has_no_gold_or_country_map(self):
        receipt = plan.public_receipt(self.candidates, "0" * 64)
        data = json.dumps(receipt)
        self.assertEqual(receipt["admission"]["official_final_tasks"], 0)
        self.assertNotIn("correct", data)
        self.assertNotIn("actor_task", data)
        for country in plan.COUNTRIES:
            self.assertNotIn(f'"{country}"', data)

    def test_existing_wdi_partition_can_be_shared_across_cells(self):
        seed = bytes.fromhex("f0" * 32)
        original = plan.source_split(seed)
        aligned = {"schema": "cua-native-wdi-private-map-v1", **original}
        rerun = plan.build(bytes.fromhex("e1" * 32), aligned)
        for split in plan.COUNTS:
            self.assertEqual({r["source_group"] for r in rerun["sets"][split]},
                             set(original[split]))
        self.assertEqual(rerun["country_partition_alignment"],
                         "shared_wdi_desktop_private_partition")

    def test_private_reserve_requires_exact_pinned_wdi_observation_cube(self):
        # Synthetic parser fixture only; these are not benchmark observations.
        rows = []
        years = list(wdi_source.YEARS)
        for indicator in wdi_source.INDICATORS:
            for offset, year in enumerate(years):
                value = {
                    "NY.GDP.MKTP.CD": 100_000_000_000 + offset * 5_000_000_000,
                    "NY.GDP.PCAP.CD": 20_000 + offset * 500,
                    "FP.CPI.TOTL.ZG": 2.0 + offset * 0.2,
                    "SP.POP.TOTL": 5_000_000 + offset * 30_000,
                    "SL.UEM.TOTL.ZS": 4.0 + offset * 0.1,
                }[indicator]
                rows.append({"countryiso3code": "ZZZ",
                             "country": {"value": "Synthetic Testland"},
                             "indicator": {"id": indicator},
                             "date": year, "value": value})
        raw = json.dumps([{"page": 1, "pages": 1, "total": 30}, rows]).encode()
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary)
            snapshot = package / "source-snapshot.private.json"
            snapshot.write_bytes(raw)
            source_path = package / "source.pptx"
            facts = verify._reserve_country_facts({
                "source_snapshot_sha256": plan.sha(raw),
                "source_snapshot_date": "2026-09-27",
                "source_group": "ZZZ"}, source_path)
            task = plan.task(bytes.fromhex("f0" * 32), "final_candidate",
                             "ZZZ", 0, 0, facts)
            task["source_scope"] = "private_wdi_reserve_v1"
            task["source_snapshot_sha256"] = plan.sha(raw)
            task["source_snapshot_date"] = "2026-09-27"
            verify._validate_task_source(task, source_path)
            snapshot.write_bytes(raw + b" ")
            with self.assertRaisesRegex(ValueError, "hash changed"):
                verify._validate_task_source(task, source_path)

    @unittest.skipUnless(DEFAULT_NODE.is_file() and DEFAULT_MODULES.is_dir(),
                         "bundled presentation runtime is unavailable")
    def test_positive_partial_collateral_and_chart_controls(self):
        with tempfile.TemporaryDirectory() as temporary:
            private = Path(temporary)
            (private / "candidate-plan.private.json").write_bytes(plan.canonical(self.candidates))
            run(private, DEFAULT_NODE, DEFAULT_MODULES, limit=1)
            row = self.candidates["sets"]["train"][0]
            package = private / "packages" / "train" / row["task_id"]
            with ZipFile(package / "source.pptx") as archive:
                self.assertEqual(sum(name.endswith(".xlsx") for name in archive.namelist()), 1)
            self.assertEqual(qa.audit(private, limit=1)["chart_workbook_contract_pass"], 1)
            report = verify.calibrate(package)
            self.assertTrue(report["offline_controls_pass"])
            receipt = json.loads((package / "calibration.private.json").read_text())
            self.assertEqual(receipt["checks"]["positive"]["score"], 1)
            self.assertEqual(receipt["checks"]["near_miss"]["score"], 0)
            self.assertFalse(receipt["checks"]["collateral"]["preservation_pass"])
            self.assertFalse(receipt["checks"]["wrong_chart"]["preservation_pass"])

            # A real PowerPoint web save can drop target-run dirty="0" and
            # regenerate an opaque chart series ID. These narrow masks still
            # reject a changed native chart value.
            with ZipFile(package / "source.pptx") as archive:
                members = {name: archive.read(name) for name in archive.namelist()}
            slide = ET.fromstring(members["ppt/slides/slide1.xml"])
            target = verify._target_node(slide, "target__summary")
            run_properties = next(node for node in target.iter()
                                  if node.tag == verify.A + "rPr")
            run_properties.set("dirty", "0")
            with_dirty = ET.tostring(slide)
            run_properties.attrib.pop("dirty")
            without_dirty = ET.tostring(slide)
            self.assertNotEqual(
                verify._canonical_target_slide(with_dirty, ["target__summary"]),
                verify._canonical_target_slide(without_dirty, ["target__summary"]))
            self.assertEqual(
                verify._canonical_target_slide(with_dirty, ["target__summary"], True),
                verify._canonical_target_slide(without_dirty, ["target__summary"], True))

            chart_part = next(name for name in members if "/charts/chart" in name
                              and name.endswith(".xml"))
            chart = ET.fromstring(members[chart_part])
            series_id = ET.SubElement(chart, verify.OFFICE_CHART + "uniqueId")
            series_id.set("val", "{00000000-1111-2222-3333-444444444444}")
            first = ET.tostring(chart)
            series_id.set("val", "{00000000-AAAA-BBBB-CCCC-DDDDDDDDDDDD}")
            second = ET.tostring(chart)
            self.assertNotEqual(verify._masked_chart(first, []),
                                verify._masked_chart(second, []))
            self.assertEqual(verify._masked_chart(first, [], True),
                             verify._masked_chart(second, [], True))
            value = next(chart.iter(verify.C + "val")).find(".//" + verify.C + "v")
            value.text = str(float(value.text) + 1)
            self.assertNotEqual(verify._masked_chart(first, [], True),
                                verify._masked_chart(ET.tostring(chart), [], True))

    def test_office_target_run_split_preserves_style_but_not_style_damage(self):
        slide = ET.Element(verify.P + "sld")
        shape = ET.SubElement(slide, verify.P + "sp")
        nv = ET.SubElement(shape, verify.P + "nvSpPr")
        ET.SubElement(nv, verify.P + "cNvPr", {"name": "target__summary"})
        body = ET.SubElement(shape, verify.P + "txBody")
        paragraph = ET.SubElement(body, verify.A + "p")
        first_run = ET.SubElement(paragraph, verify.A + "r")
        props = ET.SubElement(first_run, verify.A + "rPr",
                              {"b": "1", "sz": "2400", "lang": "en-US"})
        ET.SubElement(props, verify.A + "latin", {"typeface": "Arial"})
        ET.SubElement(first_run, verify.A + "t").text = "Verified change: +24.79 %"
        ET.SubElement(paragraph, verify.A + "endParaRPr", {"lang": "en-US"})
        original = ET.tostring(slide)
        split = ET.fromstring(original)
        split_paragraph = next(split.iter(verify.A + "p"))
        left = next(child for child in split_paragraph if child.tag == verify.A + "r")
        right = ET.fromstring(ET.tostring(left))
        left.find(verify.A + "t").text = "Verified change: +"
        right.find(verify.A + "t").text = "24.79 %"
        left_props = left.find(verify.A + "rPr")
        left_props.attrib.pop("lang")
        ET.SubElement(left_props, verify.A + "ea", {"typeface": "Arial"})
        split_paragraph.insert(1, right)
        self.assertEqual(
            verify._canonical_target_slide(original, ["target__summary"], True),
            verify._canonical_target_slide(ET.tostring(split), ["target__summary"], True))
        right.find(verify.A + "rPr").set("b", "0")
        with self.assertRaises(ValueError):
            verify._canonical_target_slide(ET.tostring(split), ["target__summary"], True)

    def test_office_table_modid_and_invisible_end_size_are_scoped(self):
        slide = ET.Element(verify.P + "sld")
        ET.SubElement(slide, verify.OFFICE_TABLE_MODID, {"val": "123"})
        table = ET.SubElement(slide, verify.A + "tbl")
        for row_number in range(2):
            row = ET.SubElement(table, verify.A + "tr")
            for column in range(2):
                cell = ET.SubElement(row, verify.A + "tc")
                paragraph = ET.SubElement(cell, verify.A + "p")
                run = ET.SubElement(paragraph, verify.A + "r")
                ET.SubElement(run, verify.A + "rPr", {"sz": "1250"})
                ET.SubElement(run, verify.A + "t").text = f"{row_number}:{column}"
                ET.SubElement(paragraph, verify.A + "endParaRPr", {"sz": "1275"})
        original = ET.tostring(slide)
        after = ET.fromstring(original)
        after.find(verify.OFFICE_TABLE_MODID).set("val", "456")
        target = verify._target_node(after, "table:1:1")
        target.find(".//" + verify.A + "t").text = "changed target"
        target.find(".//" + verify.A + "endParaRPr").set("sz", "1250")
        self.assertEqual(
            verify._canonical_target_slide(original, ["table:1:1"], True),
            verify._canonical_target_slide(ET.tostring(after), ["table:1:1"], True))
        other = verify._target_node(after, "table:0:0")
        other.find(".//" + verify.A + "rPr").set("sz", "1300")
        self.assertNotEqual(
            verify._canonical_target_slide(original, ["table:1:1"], True),
            verify._canonical_target_slide(ET.tostring(after), ["table:1:1"], True))

    def test_office_ascii_target_font_fallback_and_run_split_are_scoped(self):
        slide = ET.Element(verify.P + "sld")
        for name, value in (("target__summary", "Old target"),
                            ("untouched", "Guard text")):
            shape = ET.SubElement(slide, verify.P + "sp")
            identity = ET.SubElement(shape, verify.P + "nvSpPr")
            ET.SubElement(identity, verify.P + "cNvPr", {"name": name})
            paragraph = ET.SubElement(shape, verify.A + "p")
            run = ET.SubElement(paragraph, verify.A + "r")
            props = ET.SubElement(run, verify.A + "rPr",
                                  {"lang": "en-US", "sz": "2400"})
            ET.SubElement(props, verify.A + "latin", {"typeface": "Calibri"})
            ET.SubElement(props, verify.A + "ea", {"typeface": "+mn-lt"})
            ET.SubElement(props, verify.A + "cs", {"typeface": "Arial"})
            ET.SubElement(run, verify.A + "t").text = value
            end = ET.SubElement(paragraph, verify.A + "endParaRPr",
                                {"lang": "en-US"})
            ET.SubElement(end, verify.A + "cs", {"typeface": "Arial"})
        before = ET.tostring(slide)
        edited = ET.fromstring(before)
        target = verify._target_node(edited, "target__summary")
        paragraph = next(target.iter(verify.A + "p"))
        first = next(paragraph.iter(verify.A + "r"))
        first.find(verify.A + "t").text = "New "
        first_props = first.find(verify.A + "rPr")
        first_props.set("dirty", "0")
        first_props.remove(first_props.find(verify.A + "latin"))
        first_props.find(verify.A + "cs").set("typeface", "+mn-lt")
        second = ET.Element(verify.A + "r")
        second_props = ET.SubElement(second, verify.A + "rPr",
                                     {"lang": "en-US", "sz": "2400", "b": "0"})
        ET.SubElement(second_props, verify.A + "ea", {"typeface": "+mn-lt"})
        ET.SubElement(second_props, verify.A + "cs", {"typeface": "+mn-lt"})
        ET.SubElement(second, verify.A + "t").text = "target"
        paragraph.insert(1, second)
        end = paragraph.find(verify.A + "endParaRPr")
        end.set("dirty", "0")
        end.set("sz", "2400")
        end.find(verify.A + "cs").set("typeface", "+mn-lt")
        ET.SubElement(end, verify.A + "ea", {"typeface": "+mn-lt"})
        self.assertEqual(
            verify._canonical_target_slide(before, ["target__summary"], True),
            verify._canonical_target_slide(ET.tostring(edited), ["target__summary"], True))
        changed_other = ET.fromstring(ET.tostring(edited))
        verify._target_node(changed_other, "untouched").find(
            ".//" + verify.A + "t").text = "Changed guard"
        self.assertNotEqual(
            verify._canonical_target_slide(before, ["target__summary"], True),
            verify._canonical_target_slide(ET.tostring(changed_other), ["target__summary"], True))
        first_props.find(verify.A + "cs").set("typeface", "Times New Roman")
        with self.assertRaises(ValueError):
            verify._canonical_target_slide(ET.tostring(edited), ["target__summary"], True)

    @unittest.skipUnless(DEFAULT_NODE.is_file() and DEFAULT_MODULES.is_dir(),
                         "bundled presentation runtime is unavailable")
    def test_final_four_dependent_targets_and_near_miss(self):
        with tempfile.TemporaryDirectory() as temporary:
            private = Path(temporary)
            row = self.candidates["sets"]["final_candidate"][0]
            package = finalized_package(private, row)
            self.assertTrue(verify.calibrate(package)["offline_controls_pass"])
            receipt = json.loads((package / "calibration.private.json").read_text())
            self.assertEqual(len(receipt["checks"]["positive"]["per_target"]), 4)
            near = receipt["checks"]["near_miss"]
            self.assertEqual(sum(x["correct"] for x in near["per_target"].values()), 1)
            self.assertTrue(near["preservation_pass"])
            source = package / "source.pptx"
            destroyed = package / "deleted-target.pptx"
            with ZipFile(source) as archive:
                members = {name: archive.read(name) for name in archive.namelist()}
            root = ET.fromstring(members["ppt/slides/slide1.xml"])
            names = [node for node in root.iter(verify.P + "cNvPr")
                     if node.get("name") == "target__summary"]
            self.assertEqual(len(names), 1)
            names[0].set("name", "deleted-target")
            members["ppt/slides/slide1.xml"] = ET.tostring(root)
            with ZipFile(destroyed, "w", compression=ZIP_DEFLATED) as archive:
                for name, content in members.items():
                    archive.writestr(name, content)
            oracle = json.loads((package / "oracle.private.json").read_text())
            result = verify.verify(source, destroyed, oracle)
            self.assertEqual(result["status"], "scored")
            self.assertEqual(result["score"], 0)
            self.assertFalse(result["preservation_pass"])

    @unittest.skipUnless(DEFAULT_NODE.is_file() and DEFAULT_MODULES.is_dir(),
                         "bundled presentation runtime is unavailable")
    def test_provenance_and_web_editable_chart_caption_workflows(self):
        with tempfile.TemporaryDirectory() as temporary:
            private = Path(temporary)
            for workflow in ("source_year_reconciliation", "chart_caption_reconciliation"):
                row = next(r for r in self.candidates["sets"]["final_candidate"]
                           if r["workflow"] == workflow)
                package = finalized_package(private, row)
                self.assertTrue(verify.calibrate(package)["offline_controls_pass"])
                receipt = json.loads((package / "calibration.private.json").read_text())
                self.assertEqual(len(receipt["checks"]["positive"]["per_target"]), 4)
                if workflow == "source_year_reconciliation":
                    self.assertIn("attribution", row["target_keys"])
                else:
                    self.assertIn("chart_caption", row["target_keys"])
                    self.assertEqual(receipt["checks"]["positive"]["score"], 1)
                    self.assertEqual(receipt["checks"]["near_miss"]["score"], 0)
                    self.assertEqual([r["name"] for r in row["chart"]["series"]],
                                     ["CPI inflation", "Unemployment"])


if __name__ == "__main__":
    unittest.main()
