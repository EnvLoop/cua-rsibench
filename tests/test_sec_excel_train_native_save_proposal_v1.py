"""Synthetic package attacks for the deliberately narrow TRAIN proposal."""

from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

from tools import sec_excel_train_native_save_proposal_v1 as proposal


def fixture() -> dict[str, bytes]:
    m, r, p = proposal.M, proposal.R, proposal.P
    rows = {
        "[Content_Types].xml": '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        "xl/workbook.xml": f'<workbook xmlns="{m}" xmlns:r="{r}" xmlns:rev="{proposal.REV}"><rev:revisionPtr documentId="8_{{11111111-1111-1111-1111-111111111111}}"/><sheets><sheet name="Synthetic" sheetId="1" r:id="rId1"/></sheets><calcPr calcId="1" calcOnSave="0"/></workbook>',
        "xl/_rels/workbook.xml.rels": f'<Relationships xmlns="{p}"><Relationship Id="rId1" Type="{r}/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        "xl/worksheets/sheet1.xml": f'<worksheet xmlns="{m}"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1"/><selection pane="bottomLeft"/></sheetView></sheetViews><sheetData><row r="1"><c r="A1" s="1"><v>2</v></c><c r="B1" s="1"><f>A1*2</f><v>4</v></c><c r="C1"><f>B1+1</f><v>5</v></c></row></sheetData><dataValidations count="1"><dataValidation type="whole" sqref="A1"><formula1>0</formula1></dataValidation></dataValidations><tableParts count="1"/></worksheet>',
        "xl/calcChain.xml": f'<calcChain xmlns="{m}"><c r="B1" i="1" l="1"/><c r="C1" i="1" s="1"/></calcChain>',
        "docProps/core.xml": f'<coreProperties xmlns="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dcterms="{proposal.DCT}" xmlns:dtype="{proposal.DCT}" xmlns:xsi="{proposal.XSI}"><creator>Synthetic author</creator><dcterms:created xsi:type="dtype:W3CDTF">2026-09-30T00:00:00Z</dcterms:created><dcterms:modified xsi:type="dtype:W3CDTF">2026-09-30T00:00:00Z</dcterms:modified></coreProperties>',
        "xl/styles.xml": f'<styleSheet xmlns="{m}" xmlns:mc="{proposal.MC}" xmlns:ext="urn:synthetic-ignored" mc:Ignorable="ext"><cellXfs count="1"><xf numFmtId="0"/></cellXfs></styleSheet>',
        "xl/tables/table1.xml": f'<table xmlns="{m}" name="SyntheticTable" ref="A1:C2"/>',
        "xl/media/protected.bin": b"synthetic-protected-binary",
    }
    return {name: raw.encode() if isinstance(raw, str) else raw
            for name, raw in rows.items()}


def write_package(path: Path, parts: dict[str, bytes]) -> None:
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        for name, raw in parts.items():
            archive.writestr(name, raw)


class NativeSaveProposalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="native-save-proposal-test-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.baseline = self.directory / "baseline.xlsx"
        write_package(self.baseline, fixture())
        self.candidate = self.directory / "candidate.xlsx"

    def compare(self, parts: dict[str, bytes]):
        write_package(self.candidate, parts)
        return proposal.compare_packages(self.candidate, self.baseline,
                                         {("Synthetic", "B1")})

    def edit(self, name: str, action):
        parts = fixture()
        root = proposal.xml(parts[name])
        action(root)
        parts[name] = proposal.serialize_xml(root)
        return parts

    def test_only_observed_package_masks_accept_valid_save_changes(self):
        parts = fixture()
        core = proposal.xml(parts["docProps/core.xml"])
        for node in core:
            if node.tag.startswith("{" + proposal.DCT + "}"):
                node.text = "2026-09-30T01:00:00Z"
        parts["docProps/core.xml"] = proposal.serialize_xml(core)
        book = proposal.xml(parts["xl/workbook.xml"])
        book.find(f"{{{proposal.REV}}}revisionPtr").set(
            "documentId", "8_{22222222-2222-2222-2222-222222222222}")
        parts["xl/workbook.xml"] = proposal.serialize_xml(book)
        sheet = proposal.xml(parts["xl/worksheets/sheet1.xml"])
        selection = sheet.find("m:sheetViews/m:sheetView/m:selection", proposal.NS)
        selection.set("activeCell", "XFD1048576")
        selection.set("sqref", "XFD1048576")
        cells = {cell.attrib["r"]: cell for cell in sheet.findall(
            "m:sheetData/m:row/m:c", proposal.NS)}
        cells["B1"].find("m:f", proposal.NS).text = "A1+A1"
        cells["B1"].find("m:v", proposal.NS).text = "4.0"
        cells["C1"].find("m:v", proposal.NS).text = "5.0"
        parts["xl/worksheets/sheet1.xml"] = proposal.serialize_xml(sheet)
        chain = proposal.xml(parts["xl/calcChain.xml"])
        chain[:] = list(reversed(chain))
        for cell in chain:
            cell.set("l", "0")
            cell.set("s", "1")
        parts["xl/calcChain.xml"] = proposal.serialize_xml(chain)
        self.assertEqual(self.compare(parts)["formula_chain_members"], 2)

    def test_invalid_timestamp_and_other_metadata_are_rejected(self):
        for value in ("2026-02-30T00:00:00Z", "2026-09-30T00:00:00+00:00",
                      "2026-09-30", "2026-09-30T00:00:00.1Z"):
            with self.subTest(value=value):
                parts = self.edit("docProps/core.xml", lambda root:
                                  root.find(f"{{{proposal.DCT}}}created").__setattr__(
                                      "text", value))
                with self.assertRaisesRegex(proposal.ProposalError,
                                            "invalid_save_timestamp"):
                    self.compare(parts)
        parts = self.edit("docProps/core.xml", lambda root:
                          root[0].__setattr__("text", "Changed author"))
        with self.assertRaisesRegex(proposal.ProposalError, "protected_xml"):
            self.compare(parts)

    def test_session_shape_prefix_and_other_revision_attributes_are_protected(self):
        for value, code in (("private-arbitrary-string", "invalid_session"),
                            ("7_{22222222-2222-2222-2222-222222222222}", "protected_xml")):
            parts = self.edit("xl/workbook.xml", lambda root:
                              root[0].set("documentId", value))
            with self.assertRaisesRegex(proposal.ProposalError, code):
                self.compare(parts)
        parts = self.edit("xl/workbook.xml", lambda root: root[0].set("newFlag", "1"))
        with self.assertRaisesRegex(proposal.ProposalError, "protected_xml"):
            self.compare(parts)

    def test_selection_bounds_pair_pane_count_and_unknown_attrs_are_protected(self):
        def selection(root):
            return root.find("m:sheetViews/m:sheetView/m:selection", proposal.NS)
        attacks = [
            (lambda root: selection(root).set("activeCell", "B1"), "selection_focus"),
            (lambda root: selection(root).attrib.update(activeCell="XFE1", sqref="XFE1"), "selection_focus"),
            (lambda root: selection(root).attrib.update(activeCell="A1048577", sqref="A1048577"), "selection_focus"),
            (lambda root: selection(root).attrib.update(activeCell="B1", sqref="B1:C2"), "selection_focus"),
            (lambda root: selection(root).set("pane", "topRight"), "protected_xml"),
            (lambda root: selection(root).set("activeCellId", "0"), "protected_xml"),
            (lambda root: root.find("m:sheetViews/m:sheetView", proposal.NS).append(
                ET.Element(f"{{{proposal.M}}}selection", {"pane": "bottomLeft"})), "protected_xml"),
        ]
        for attack, code in attacks:
            with self.subTest(code=code):
                with self.assertRaisesRegex(proposal.ProposalError, code):
                    self.compare(self.edit("xl/worksheets/sheet1.xml", attack))

    def test_calc_chain_must_exactly_cover_unique_actual_formula_cells(self):
        attacks = [
            (lambda root: root.remove(root[0]), "membership_changed"),
            (lambda root: root.append(ET.fromstring(ET.tostring(root[0]))), "membership_changed"),
            (lambda root: root[0].set("r", "A1"), "membership_changed"),
            (lambda root: root[0].set("i", "2"), "membership_changed"),
            (lambda root: root[0].set("l", "2"), "chain_flag"),
            (lambda root: root[0].set("a", "1"), "chain_node"),
            (lambda root: root[0].attrib.pop("i"), "chain_node"),
            (lambda root: root[0].append(ET.Element("extra")), "chain_node"),
            (lambda root: root[0].__setattr__("tail", "unobserved text"), "chain_node"),
        ]
        for attack, code in attacks:
            with self.subTest(code=code):
                with self.assertRaisesRegex(proposal.ProposalError, code):
                    self.compare(self.edit("xl/calcChain.xml", attack))

    def test_styles_tables_validations_constants_and_collateral_formulas_are_protected(self):
        attacks = [
            ("xl/styles.xml", lambda root: root[0][0].set("numFmtId", "9")),
            ("xl/tables/table1.xml", lambda root: root.set("ref", "A1:C3")),
            ("xl/worksheets/sheet1.xml", lambda root: root.find("m:dataValidations/m:dataValidation", proposal.NS).set("type", "decimal")),
            ("xl/worksheets/sheet1.xml", lambda root: root.find("m:sheetData/m:row/m:c/m:v", proposal.NS).__setattr__("text", "3")),
            ("xl/worksheets/sheet1.xml", lambda root: root.find("m:sheetData/m:row/m:c[@r='C1']/m:f", proposal.NS).__setattr__("text", "B1+2")),
            ("xl/workbook.xml", lambda root: root.find("m:calcPr", proposal.NS).set("calcOnSave", "1")),
            ("xl/worksheets/sheet1.xml", lambda root: root.find("m:sheetData/m:row/m:c[@r='B1']", proposal.NS).set("s", "2")),
        ]
        for name, attack in attacks:
            with self.subTest(part=name):
                with self.assertRaisesRegex(proposal.ProposalError, "protected_xml"):
                    self.compare(self.edit(name, attack))

    def test_part_set_binaries_duplicate_members_xml_entities_and_unknown_nodes_are_protected(self):
        parts = fixture()
        parts["xl/media/protected.bin"] += b"changed"
        with self.assertRaisesRegex(proposal.ProposalError, "protected_binary"):
            self.compare(parts)
        for extra in ("xl/externalLinks/externalLink1.xml", "xl/vbaProject.bin"):
            parts = fixture()
            parts[extra] = b"<extra/>"
            with self.assertRaisesRegex(proposal.ProposalError, "external_link_or_macro"):
                self.compare(parts)
        parts = fixture()
        del parts["xl/styles.xml"]
        with self.assertRaisesRegex(proposal.ProposalError, "part_set_changed"):
            self.compare(parts)
        parts = self.edit("docProps/core.xml", lambda root: root.append(ET.Element("extra")))
        with self.assertRaisesRegex(proposal.ProposalError, "protected_xml"):
            self.compare(parts)
        parts = fixture()
        parts["xl/styles.xml"] = b'<!DOCTYPE x [<!ENTITY a "x">]><x/>'
        with self.assertRaisesRegex(proposal.ProposalError, "xml_entities"):
            self.compare(parts)
        parts = fixture()
        parts["xl/styles.xml"] = '<!DOCTYPE x [<!ENTITY a "x">]><x/>'.encode("utf-16")
        with self.assertRaisesRegex(proposal.ProposalError, "unobserved_xml_encoding"):
            self.compare(parts)
        stream = io.BytesIO()
        with ZipFile(stream, "w") as archive:
            archive.writestr("duplicate.xml", "<x/>")
            with self.assertWarnsRegex(UserWarning, "Duplicate name"):
                archive.writestr("duplicate.xml", "<x/>")
        self.candidate.write_bytes(stream.getvalue())
        with self.assertRaisesRegex(proposal.ProposalError, "duplicate_or_excess"):
            proposal.package(self.candidate)

    def test_private_review_hash_refuses_any_other_split_or_review(self):
        path = self.directory / "different-review.json"
        path.write_text('{"split":"final_candidate"}')
        with self.assertRaisesRegex(proposal.ProposalError, "review_binding_changed"):
            proposal.load_review(path)

    def test_qname_and_markup_namespace_rebinding_is_not_hidden_by_xml_parsing(self):
        parts = fixture()
        parts["xl/styles.xml"] = parts["xl/styles.xml"].replace(
            b'xmlns:ext="urn:synthetic-ignored"', b'xmlns:ext="urn:changed-semantics"')
        with self.assertRaisesRegex(proposal.ProposalError, "protected_xml"):
            self.compare(parts)
        parts = fixture()
        parts["xl/styles.xml"] = parts["xl/styles.xml"].replace(
            b'xmlns:ext="urn:synthetic-ignored"', b'')
        with self.assertRaisesRegex(proposal.ProposalError, "unbound_xml_semantic_prefix"):
            self.compare(parts)
        parts = fixture()
        parts["docProps/core.xml"] = parts["docProps/core.xml"].replace(
            ('xmlns:dtype="' + proposal.DCT + '"').encode(),
            b'xmlns:dtype="urn:changed-type"')
        with self.assertRaisesRegex(proposal.ProposalError, "protected_xml"):
            self.compare(parts)
        # Prefix spelling may change if its resolved namespace stays identical.
        parts = fixture()
        parts["xl/styles.xml"] = parts["xl/styles.xml"].replace(
            b'xmlns:ext=', b'xmlns:alias=').replace(b'mc:Ignorable="ext"', b'mc:Ignorable="alias"')
        self.assertEqual(self.compare(parts)["part_count"], len(parts))

    def test_failed_verification_does_not_export_private_exception_paths(self):
        private = self.directory / "private-secret-answer.xlsx"
        result = proposal.verify(private, private, private, private)
        self.assertFalse(result["train_derived_proposal_pass"])
        self.assertEqual(result["reason_codes"],
                         ["unhandled_verification_FileNotFoundError"])
        self.assertNotIn("private-secret-answer", json.dumps(result))
        self.assertNotIn(str(self.directory), json.dumps(result))


if __name__ == "__main__":
    unittest.main()
