"""Disposable-copy adversarial audit of one frozen TRAIN native-save proposal.

The input workbooks/review/source bytes are never written. Output is restricted
to hashes, counts, refusal codes and limitations; local/private identifiers,
source values, cell addresses, formulas and answers are not serialized.
"""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

from tools import sec_excel_train_native_save_proposal_v1 as proposal
from sec_excel_factory.verify_train_next_four import verify as historical_verify

POSITIVE_SHA256 = "7a27251707fb05e19a650923c3a514521b8f4964af1959c711ceea6dc31313dc"
REOPENED_SHA256 = "a12d49983353e3af48b6e47e5287f9e4e8bc2d0acc264e73724d820f8d0944ad"
FRESH_RESET_SHA256 = "0109d5e5f747c7837688371a84325b6cfe6f76e0183ef1060eaee438f418ce8d"


def write_package(path: Path, parts: dict[str, bytes]) -> None:
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        for name, raw in parts.items():
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100600 << 16
            archive.writestr(info, raw)
    os.chmod(path, 0o600)


def edit_xml(parts: dict, name: str, action) -> None:
    root = proposal.xml(parts[name])
    action(root)
    parts[name] = proposal.serialize_xml(root)


def edit_cell(parts: dict, sheet: str, address: str, action) -> None:
    part = proposal.sheet_parts(parts)[sheet][1]

    def update(root):
        matches = [cell for cell in root.findall("m:sheetData/m:row/m:c", proposal.NS)
                   if cell.attrib["r"] == address]
        proposal.require(len(matches) == 1, "audit_cell_not_unique")
        action(matches[0])

    edit_xml(parts, part, update)


def refresh_caches(path: Path) -> None:
    cells, *_ = proposal.load_xlsx(path)
    evaluator = proposal.Evaluator(cells)
    parts = proposal.package(path)
    for sheet, (_, part) in proposal.sheet_parts(parts).items():
        root = proposal.xml(parts[part])
        for cell in root.findall("m:sheetData/m:row/m:c", proposal.NS):
            if cell.find("m:f", proposal.NS) is None:
                continue
            cache = cell.find("m:v", proposal.NS)
            if cache is None:
                cache = ET.SubElement(cell, f"{{{proposal.M}}}v")
            cache.text = format(evaluator.cell(sheet, cell.attrib["r"]), ".17g")
        parts[part] = proposal.serialize_xml(root)
    write_package(path, parts)


def audit(input_directory: Path) -> dict:
    seed = input_directory / "seed.xlsx"
    baseline = input_directory / "untouched-web-baseline.xlsx"
    positive = input_directory / "positive-web.xlsx"
    reopened = input_directory / "positive-reopened-web.xlsx"
    fresh_reset = input_directory / "fresh-reset-web.xlsx"
    private_review = input_directory / "review.private.json"
    inputs = [seed, baseline, positive, reopened, fresh_reset, private_review]
    hashes_before = {path.name: proposal.digest(path) for path in inputs}
    proposal.require(hashes_before["positive-web.xlsx"] == POSITIVE_SHA256 and
                     hashes_before["positive-reopened-web.xlsx"] == REOPENED_SHA256 and
                     hashes_before["fresh-reset-web.xlsx"] == FRESH_RESET_SHA256,
                     "frozen_positive_artifact_binding_changed")
    _, case = proposal.load_review(private_review)
    saved_result = proposal.verify(positive, seed, baseline, private_review)
    reopened_result = proposal.verify(reopened, seed, baseline, private_review)
    proposal.require(saved_result["train_derived_proposal_pass"] and
                     reopened_result["train_derived_proposal_pass"],
                     "proposal_saved_or_reopened_positive_control_failed")
    reset_cells = proposal.qualify_native_cells(seed, fresh_reset, case)
    reset_package = proposal.compare_packages(fresh_reset, baseline, targets=set())
    reset_result = proposal.verify(fresh_reset, seed, baseline, private_review)
    proposal.require(not reset_result["train_derived_proposal_pass"],
                     "fresh_native_reset_wrongly_accepted_as_solved")
    strict_results = [historical_verify(path, seed, case) for path in (positive, reopened)]
    proposal.require(all(result["pass"] is False for result in strict_results),
                     "historical_strict_failure_not_retained")
    base_parts = proposal.package(positive)
    baseline_cells, *_ = proposal.load_xlsx(baseline)
    positive_cells, *_ = proposal.load_xlsx(positive)
    negatives, equivalent_saves = [], []
    categories = Counter()
    with tempfile.TemporaryDirectory(prefix="excel-train-native-audit-") as temporary:
        controls = Path(temporary)
        os.chmod(controls, 0o700)

        def check(label: str, category: str, action, *, refresh=False, expect=False):
            parts = dict(base_parts)
            action(parts)
            path = controls / f"control-{len(negatives) + len(equivalent_saves):03d}.xlsx"
            write_package(path, parts)
            if refresh:
                refresh_caches(path)
            result = proposal.verify(path, seed, baseline, private_review)
            proposal.require(result["train_derived_proposal_pass"] is expect,
                             "audit_control_expectation_failed_" + label)
            record = {"control": label, "category": category,
                      "artifact_sha256": result["candidate_sha256"],
                      "proposal_pass": result["train_derived_proposal_pass"],
                      "reason_codes": result["reason_codes"]}
            (equivalent_saves if expect else negatives).append(record)
            if not expect:
                categories[category] += 1

        def formula(parts, sheet, address, text):
            edit_cell(parts, sheet, address, lambda cell:
                      cell.find("m:f", proposal.NS).__setattr__("text", text))

        # Each target is challenged separately. Numeric formulas retain the
        # correct current display and chain membership but fail dependency replays.
        for serial, (sheet, address) in enumerate(sorted(proposal.BANK_TARGETS)):
            old_formula = baseline_cells[sheet][address].formula
            current_value = positive_cells[sheet][address].value
            check(f"one_target_short_{serial:02d}", "one_target_short",
                  lambda parts, s=sheet, a=address, f=old_formula:
                  formula(parts, s, a, f), refresh=True)
            check(f"numeric_formula_hardcode_{serial:02d}", "numeric_formula_hardcode",
                  lambda parts, s=sheet, a=address, v=current_value:
                  formula(parts, s, a, v), refresh=True)

        check("wrong_formula_current_cache_refreshed", "wrong_formula",
              lambda parts: formula(parts, "Interest build", "C7", "C5+C6"),
              refresh=True)

        def constant_target(parts):
            def change(cell):
                cell.remove(cell.find("m:f", proposal.NS))
            edit_cell(parts, "Interest summary", "B8", change)
        check("target_replaced_by_constant", "plain_hardcode", constant_target)

        def stale(parts):
            edit_cell(parts, "Interest summary", "B8", lambda cell:
                      cell.find("m:v", proposal.NS).__setattr__("text", "-987654321"))
        check("stale_target_cache", "stale_cache", stale)
        check("missing_target_cache", "missing_cache", lambda parts:
              edit_cell(parts, "Interest summary", "B8", lambda cell:
                        cell.remove(cell.find("m:v", proposal.NS))))
        check("missing_collateral_formula_cache", "missing_cache", lambda parts:
              edit_cell(parts, "Interest summary", "B5", lambda cell:
                        cell.remove(cell.find("m:v", proposal.NS))))
        check("nonfinite_numeric_formula_cache", "invalid_cache", lambda parts:
              edit_cell(parts, "Interest summary", "B8", lambda cell:
                        cell.find("m:v", proposal.NS).__setattr__("text", "NaN")))
        check("source_constant_modified_current_caches_refreshed", "source_tamper",
              lambda parts: edit_cell(parts, "Source facts", "C5", lambda cell:
              cell.find("m:v", proposal.NS).__setattr__(
                  "text", str(float(positive_cells["Source facts"]["C5"].value) + 1))),
              refresh=True)
        check("collateral_formula_modified_current_caches_refreshed", "collateral_formula",
              lambda parts: formula(parts, "Interest summary", "B5", "'Interest build'!C5+1"),
              refresh=True)
        check("target_cell_style_changed", "style", lambda parts:
              edit_cell(parts, "Interest summary", "B8", lambda cell: cell.set("s", "0")))
        check("protected_style_part_changed", "style", lambda parts:
              edit_xml(parts, "xl/styles.xml", lambda root: root.set("newFlag", "1")))

        def namespace_only_rebound(parts):
            name = "xl/styles.xml"
            root = proposal.xml(parts[name])
            bindings = proposal.XML_NAMESPACES[root]
            referenced = root.attrib.get(f"{{{proposal.MC}}}Ignorable", "").split()
            used = {key.split("}", 1)[0][1:] for node in root.iter()
                    for key in [node.tag, *node.attrib]
                    if isinstance(key, str) and key.startswith("{")}
            only_qname = [token for token in referenced if bindings[token] not in used]
            proposal.require(bool(only_qname), "audit_qname_only_binding_missing")
            token = only_qname[0]
            declaration = ('xmlns:' + token + '="' + bindings[token] + '"').encode()
            proposal.require(parts[name].count(declaration) == 1,
                             "audit_namespace_declaration_not_unique")
            parts[name] = parts[name].replace(declaration, (
                'xmlns:' + token + '="urn:synthetic-adversarial-rebinding"').encode())
        check("qname_only_namespace_binding_rebound", "xml_namespace", namespace_only_rebound)

        def table_added(parts):
            parts["xl/tables/table1.xml"] = (
                f'<table xmlns="{proposal.M}" id="1" name="AddedTable" '
                'displayName="AddedTable" ref="A1:B2" totalsRowShown="0">'
                '<autoFilter ref="A1:B2"/><tableColumns count="2">'
                '<tableColumn id="1" name="Column1"/><tableColumn id="2" name="Column2"/>'
                '</tableColumns></table>').encode()
        check("table_part_added", "table", table_added)
        check("worksheet_table_structure_added", "table", lambda parts:
              edit_xml(parts, "xl/worksheets/sheet1.xml", lambda root:
                       root.append(ET.Element(f"{{{proposal.M}}}tableParts", {"count": "1"}))))

        def validation_added(parts):
            def change(root):
                group = ET.SubElement(root, f"{{{proposal.M}}}dataValidations", {"count": "1"})
                ET.SubElement(group, f"{{{proposal.M}}}dataValidation",
                              {"type": "whole", "sqref": "B8"})
            edit_xml(parts, "xl/worksheets/sheet1.xml", change)
        check("worksheet_validation_added", "validation", validation_added)
        check("external_link_part_added", "external_link", lambda parts:
              parts.__setitem__("xl/externalLinks/externalLink1.xml",
                                f'<externalLink xmlns="{proposal.M}"/>'.encode()))

        def external_relationship(parts):
            def change(root):
                ET.SubElement(root, f"{{{proposal.P}}}Relationship", {
                    "Id": "rIdExternal", "Type": proposal.R + "/externalLink",
                    "Target": "https://example.invalid/workbook.xlsx", "TargetMode": "External"})
            edit_xml(parts, "xl/_rels/workbook.xml.rels", change)
        check("external_link_relationship_added", "external_link", external_relationship)
        check("macro_part_added", "macro", lambda parts:
              parts.__setitem__("xl/vbaProject.bin", b"synthetic-not-a-macro"))

        def creator_changed(parts):
            def change(root):
                node = root.find("{http://purl.org/dc/elements/1.1/}creator")
                node.text = "Synthetic adversarial author"
            edit_xml(parts, "docProps/core.xml", change)
        check("protected_creator_changed", "metadata", creator_changed)
        check("unobserved_core_metadata_node_added", "metadata", lambda parts:
              edit_xml(parts, "docProps/core.xml", lambda root:
                       root.append(ET.Element("unobserved"))))
        check("invalid_save_timestamp", "metadata", lambda parts:
              edit_xml(parts, "docProps/core.xml", lambda root:
                       root.find(f"{{{proposal.DCT}}}modified").__setattr__(
                           "text", "2026-02-30T00:00:00Z")))
        check("malformed_session_document_id", "metadata", lambda parts:
              edit_xml(parts, "xl/workbook.xml", lambda root:
                       root.find(f"{{{proposal.REV}}}revisionPtr").set("documentId", "invalid")))
        check("calculation_settings_changed", "calculation_settings", lambda parts:
              edit_xml(parts, "xl/workbook.xml", lambda root:
                       root.find("m:calcPr", proposal.NS).set("calcOnSave", "1")))

        def chain_edit(parts, action):
            edit_xml(parts, "xl/calcChain.xml", action)
        check("calculation_chain_member_dropped", "chain_membership", lambda parts:
              chain_edit(parts, lambda root: root.remove(root[0])))
        check("calculation_chain_member_duplicated", "chain_membership", lambda parts:
              chain_edit(parts, lambda root: root.append(ET.fromstring(ET.tostring(root[0])))))
        check("calculation_chain_sheet_identity_changed", "chain_membership", lambda parts:
              chain_edit(parts, lambda root: root[0].set("i", "999")))
        check("calculation_chain_unknown_attribute", "chain_shape", lambda parts:
              chain_edit(parts, lambda root: root[0].set("a", "1")))
        check("calculation_chain_invalid_flag", "chain_shape", lambda parts:
              chain_edit(parts, lambda root: root[0].set("l", "2")))

        def selection_edit(parts, action):
            edit_xml(parts, "xl/worksheets/sheet1.xml", lambda root:
                     action(root.find("m:sheetViews/m:sheetView/m:selection", proposal.NS)))
        check("selection_out_of_bounds", "selection", lambda parts:
              selection_edit(parts, lambda node: node.attrib.update(
                  activeCell="XFE1", sqref="XFE1")))
        check("selection_pane_modified", "selection", lambda parts:
              selection_edit(parts, lambda node: node.set("pane", "topRight")))
        check("selection_unobserved_attribute", "selection", lambda parts:
              selection_edit(parts, lambda node: node.set("activeCellId", "0")))
        check("protected_part_removed", "package_membership", lambda parts:
              parts.pop("xl/styles.xml"))

        # Positive equivalence controls prove the masks are actually exercised.
        def valid_times(parts):
            def change(root):
                root.find(f"{{{proposal.DCT}}}created").text = "2026-09-30T02:00:00Z"
                root.find(f"{{{proposal.DCT}}}modified").text = "2026-09-30T02:00:01Z"
            edit_xml(parts, "docProps/core.xml", change)
        check("equivalent_valid_utc_save_times", "equivalent_save", valid_times, expect=True)

        def valid_session(parts):
            def change(root):
                node = root.find(f"{{{proposal.REV}}}revisionPtr")
                prefix = proposal.SESSION.fullmatch(node.attrib["documentId"])[1]
                node.set("documentId", prefix + "_{11111111-2222-3333-4444-555555555555}")
            edit_xml(parts, "xl/workbook.xml", change)
        check("equivalent_valid_session_uuid", "equivalent_save", valid_session, expect=True)
        check("equivalent_bounded_selection_focus", "equivalent_save", lambda parts:
              selection_edit(parts, lambda node: node.attrib.update(activeCell="A1", sqref="A1")),
              expect=True)

        def valid_chain(parts):
            def change(root):
                root[:] = list(reversed(root))
                for cell in root:
                    cell.set("l", "0")
                    cell.set("s", "1")
            chain_edit(parts, change)
        check("equivalent_chain_order_and_boolean_flags", "equivalent_save", valid_chain,
              expect=True)
        seed_result = proposal.verify(seed, seed, baseline, private_review)
        baseline_result = proposal.verify(baseline, seed, baseline, private_review)
        proposal.require(not seed_result["train_derived_proposal_pass"] and
                         not baseline_result["train_derived_proposal_pass"],
                         "unsolved_seed_or_native_baseline_accepted")
    hashes_after = {path.name: proposal.digest(path) for path in inputs}
    proposal.require(hashes_before == hashes_after, "immutable_input_bytes_changed")
    return {
        "schema": "envloop.sec_excel_train_native_save_proposal_audit.public.v1",
        "status": "TRAIN_derived_normalization_proposal_controls_passed",
        "scope": "one_frozen_bank_TRAIN_source_case",
        "saved_positive": saved_result,
        "reopened_positive": reopened_result,
        "historical_strict_saved_rejected": strict_results[0]["pass"] is False,
        "historical_strict_reopened_rejected": strict_results[1]["pass"] is False,
        "historical_strict_error_counts": [len(row["errors"]) for row in strict_results],
        "raw_unsolved_seed_rejected": not seed_result["train_derived_proposal_pass"],
        "native_unsolved_baseline_rejected": not baseline_result["train_derived_proposal_pass"],
        "fresh_native_reset": {
            "artifact_sha256": hashes_before["fresh-reset-web.xlsx"],
            "source_and_formula_semantic_cells_unchanged":
                reset_cells["raw_to_native_semantic_cells_unchanged"],
            "semantic_cell_count": reset_cells["raw_to_native_semantic_cell_count"],
            "normalization_equivalent_to_pre_edit_native_baseline": True,
            "protected_native_parts": reset_package["part_count"],
            "formula_chain_members": reset_package["formula_chain_members"],
            "rejected_as_unsolved": not reset_result["train_derived_proposal_pass"],
            "reason_codes": reset_result["reason_codes"],
            "offline_reset_artifact_comparison_only": True,
        },
        "adversarial_controls_rejected": len(negatives),
        "adversarial_categories": dict(sorted(categories.items())),
        "adversarial_controls": negatives,
        "equivalent_save_controls_passed": len(equivalent_saves),
        "equivalent_save_controls": equivalent_saves,
        "immutable_input_hashes_before": hashes_before,
        "immutable_input_hashes_after": hashes_after,
        "immutable_inputs_unchanged": True,
        "controls_created_in_private_disposable_directory": True,
        "controls_deleted_after_audit": True,
        "source_code_sha256": {
            "normalization_proposal": proposal.digest(Path(proposal.__file__)),
            "adversarial_audit": proposal.digest(Path(__file__)),
            "historical_train_scorer": proposal.digest(proposal.ROOT / "sec_excel_factory/verify_train_next_four.py"),
            "independent_arithmetic_and_counterfactuals": proposal.digest(proposal.ROOT / "sec_excel_factory/verify_train_next_four.py"),
            "generic_ooxml_parser_and_evaluator": proposal.digest(proposal.ROOT / "sec_excel_factory/verify_ooxml.py"),
        },
        "model_calls": 0, "selection_runs": 0, "final_runs": 0,
        "excel_web_admissions": 0, "official_final_admissions": 0,
        "limitations": [
            "A TRAIN-derived, one-case source proposal; no task admission or model-effect claim.",
            "The pre-edit native baseline chronology is supplied collection evidence, not independently established by this offline audit.",
            "Raw-to-native semantic cells match; broad Office package/style/theme rewriting and visual preservation remain unqualified.",
            "Numeric cache consistency is independently checked; native recalculation provenance remains unverified by this offline audit.",
            "Independent second-person source review, GUI reset and cross-worker isolation are outside this audit.",
            "The observed native package contains no tables or binary parts; table addition is audited here, while existing-table edits and protected-binary equality use synthetic unit controls.",
            "The source-plan hash is reviewed and pinned; this audit directly verifies source-case bytes and five raw source files, but does not reread the source-plan file.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-input-directory", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = audit(args.private_input_directory)
        raw = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
        # Only the explicitly requested new evidence output is written.
        with args.public_out.open("xb") as destination:
            destination.write(raw)
        print(json.dumps({"status": result["status"],
                          "adversarial_controls_rejected": result["adversarial_controls_rejected"],
                          "equivalent_save_controls_passed": result["equivalent_save_controls_passed"],
                          "public_evidence_sha256": sha256(raw).hexdigest(),
                          "model_calls": 0, "final_runs": 0, "official_final_admissions": 0},
                         sort_keys=True))
    except proposal.ProposalError as exc:
        print(json.dumps({"status": "refused", "reason_code": str(exc)}))
        raise SystemExit(2) from None
    except Exception as exc:
        print(json.dumps({"status": "refused", "reason_code":
                          "unhandled_audit_" + type(exc).__name__}))
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
