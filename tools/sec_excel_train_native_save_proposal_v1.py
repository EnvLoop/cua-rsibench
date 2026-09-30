"""Hash-bound, TRAIN-only native Excel save-normalization proposal.

This deliberately remains separate from historical strict scorers. It reuses
only independent reviewed-source arithmetic and the OOXML evaluator. It never
imports a workbook builder, calls a model, controls Office, or grants admission.
Public results contain hashes/counts/reason codes, never workbook answers.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from hashlib import sha256
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import sys
from weakref import WeakKeyDictionary
from xml.etree import ElementTree as ET
from xml.sax.saxutils import quoteattr
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sec_excel_factory"))
from verify_ooxml import Evaluator, load_xlsx, unchanged_cell  # noqa: E402
from verify_train_next_four import (  # noqa: E402
    BANK_TARGETS, SHEETS, _close, _counterfactuals, _source_cells_match,
    _target_values, expected_values,
)

M = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
P = "http://schemas.openxmlformats.org/package/2006/relationships"
DCT = "http://purl.org/dc/terms/"
REV = "http://schemas.microsoft.com/office/spreadsheetml/2014/revision"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
NS = {"m": M}
XML_NAMESPACES = WeakKeyDictionary()
SCHEMA = "envloop.sec_excel_train_native_save_proposal.v1"
REVIEW_SHA256 = "b8eb2d73511ff19f7b68aa2fae67e309e21d51d2ee4e317ad974f48d500fdf72"
SEED_SHA256 = "e279e2b24695208282db024210d1c3e46c3bd3cd38f002c7d49b64df96912a40"
BASELINE_SHA256 = "a7923d89481ec66062da23d31a2dfddea2d328d9827a3a6cf8601363a90af122"
SOURCE_PLAN_SHA256 = "d975e9a31259b6a5bf5474b3b2b57b140fc55a5da03e3357bf2cca78de3e13aa"
CASE_INDEX = 4
MAX_PARTS = 256
MAX_PACKAGE_BYTES = 100_000_000
CELL = re.compile(r"([A-Z]{1,3})([1-9][0-9]{0,6})\Z")
UTC = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")
SESSION = re.compile(r"([0-9])_\{[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}\}\Z")


class ProposalError(ValueError):
    """A field-limited refusal code; it must never contain private input text."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ProposalError(code)


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def xml(raw: bytes) -> ET.Element:
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ProposalError("unobserved_xml_encoding") from None
    require("\x00" not in decoded, "unobserved_xml_encoding")
    require("<!DOCTYPE" not in decoded.upper() and "<!ENTITY" not in decoded.upper(),
            "xml_entities_forbidden")
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True,
                                               insert_pis=True))
    # Namespace declarations can also be referenced inside QName-valued
    # attributes (xsi:type and markup compatibility), not just element tags.
    scopes, pending = [], []
    iterator = ET.iterparse(io.BytesIO(raw), parser=parser,
                            events=("start", "end", "start-ns"))
    for event, item in iterator:
        if event == "start-ns":
            pending.append(item)
        elif event == "start":
            current = dict(scopes[-1]) if scopes else {"xml": "http://www.w3.org/XML/1998/namespace"}
            current.update(pending)
            pending.clear()
            scopes.append(current)
            XML_NAMESPACES[item] = current
        else:
            scopes.pop()
    return iterator.root


def attribute_semantics(node: ET.Element, name: str, value: str):
    bindings = XML_NAMESPACES.get(node, {})

    def prefix(prefix_name):
        require(prefix_name in bindings, "unbound_xml_semantic_prefix")
        return bindings[prefix_name]

    def qname(token):
        pieces = token.split(":")
        require(len(pieces) in (1, 2) and all(pieces), "invalid_xml_semantic_qname")
        return (prefix(pieces[0]), pieces[1]) if len(pieces) == 2 else (
            bindings.get("", ""), pieces[0])

    if name == f"{{{XSI}}}type":
        return ("qname", qname(value))
    if name in {f"{{{MC}}}Ignorable", f"{{{MC}}}MustUnderstand"} or (
            node.tag == f"{{{MC}}}Choice" and name == "Requires"):
        return ("prefix_list", tuple(prefix(token) for token in value.split()))
    if name in {f"{{{MC}}}ProcessContent", f"{{{MC}}}PreserveElements",
                f"{{{MC}}}PreserveAttributes"}:
        return ("qname_list", tuple(qname(token) for token in value.split()))
    return value


def serialize_xml(root: ET.Element) -> bytes:
    """Preserve root namespace bindings when making disposable audit copies.

    ElementTree otherwise drops bindings used only inside QName attributes.
    This helper never writes an input artifact.
    """
    bindings = XML_NAMESPACES.get(root, {})
    for prefix_name, uri in bindings.items():
        if prefix_name != "xml" and not re.fullmatch(r"ns[0-9]+", prefix_name):
            ET.register_namespace(prefix_name, uri)
    raw = ET.tostring(root, encoding="utf-8")
    split = raw.index(b">")
    header, suffix = raw[:split], raw[split:]
    additions = []
    for prefix_name, uri in bindings.items():
        if prefix_name == "xml":
            continue
        attr = ("xmlns:" + prefix_name) if prefix_name else "xmlns"
        if re.search(rb"\s" + re.escape(attr.encode()) + rb"=", header) is None:
            additions.append((" " + attr + "=" + quoteattr(uri)).encode())
    if header.endswith(b"/"):
        return header[:-1] + b"".join(additions) + b"/" + suffix
    return header + b"".join(additions) + suffix


def semantic(node: ET.Element) -> tuple:
    """Namespace-aware equality; attribute spelling/order is not significant.

    Text, tails, node multiplicity and child order remain protected. Including
    comments/PIs prevents an unobserved node from disappearing in the parser.
    """
    tag = node.tag if isinstance(node.tag, str) else str(node.tag)
    return (tag, tuple((name, attribute_semantics(node, name, value))
                       for name, value in sorted(node.attrib.items())), node.text, node.tail,
            tuple(semantic(child) for child in node))


def bounded_cell(address: str) -> bool:
    match = CELL.fullmatch(address)
    if match is None:
        return False
    col = 0
    for letter in match[1]:
        col = col * 26 + ord(letter) - ord("A") + 1
    return col <= 16_384 and int(match[2]) <= 1_048_576


def package(path: Path) -> dict[str, bytes]:
    with ZipFile(path) as archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        require(0 < len(names) <= MAX_PARTS and len(names) == len(set(names)),
                "duplicate_or_excess_package_parts")
        require(sum(item.file_size for item in infos) <= MAX_PACKAGE_BYTES,
                "oversized_package")
        require(all(not PurePosixPath(name).is_absolute() and
                    ".." not in PurePosixPath(name).parts and
                    "\\" not in name and not name.endswith("/")
                    for name in names), "unsafe_package_part")
        require(not any(name.startswith("xl/externalLinks/") or
                        name.lower().endswith("vbaproject.bin")
                        for name in names), "external_link_or_macro_forbidden")
        result = {name: archive.read(name) for name in names}
    for name, raw in result.items():
        if name.endswith((".xml", ".rels")):
            root = xml(raw)
            if name.endswith(".rels"):
                require(not any(child.attrib.get("TargetMode") == "External" and
                                "externalLink" in child.attrib.get("Type", "")
                                for child in root), "external_link_or_macro_forbidden")
    return result


def sheet_parts(parts: dict[str, bytes]) -> dict[str, tuple[str, str]]:
    book = xml(parts["xl/workbook.xml"])
    relationships = xml(parts["xl/_rels/workbook.xml.rels"])
    by_id = {}
    for rel in relationships:
        require(rel.tag == f"{{{P}}}Relationship" and
                rel.attrib.get("Id") not in by_id, "invalid_workbook_relationship")
        by_id[rel.attrib.get("Id")] = rel
    result = {}
    ids = set()
    for sheet in book.findall("m:sheets/m:sheet", NS):
        name, sid = sheet.attrib["name"], sheet.attrib["sheetId"]
        require(name not in result and sid not in ids and
                re.fullmatch(r"[1-9][0-9]*", sid) is not None,
                "duplicate_or_invalid_sheet_identity")
        ids.add(sid)
        rel = by_id[sheet.attrib[f"{{{R}}}id"]]
        require(rel.attrib.get("TargetMode") != "External",
                "external_sheet_relationship")
        target = rel.attrib["Target"]
        part = target.lstrip("/") if target.startswith("/") else "xl/" + target
        require(part in parts and part.startswith("xl/worksheets/"),
                "invalid_sheet_part")
        result[name] = (sid, part)
    require(len({part for _, part in result.values()}) == len(result),
            "duplicate_sheet_part")
    return result


def formula_members(parts: dict[str, bytes], sheets: dict) -> set[tuple[str, str]]:
    members = set()
    for sid, part in sheets.values():
        seen = set()
        root = xml(parts[part])
        for cell in root.findall("m:sheetData/m:row/m:c", NS):
            address = cell.attrib.get("r", "")
            require(bounded_cell(address) and address not in seen,
                    "duplicate_or_invalid_cell_address")
            seen.add(address)
            forms = cell.findall("m:f", NS)
            require(len(forms) <= 1 and len(cell.findall("m:v", NS)) <= 1,
                    "duplicate_formula_or_cache_node")
            if forms:
                require(bool(forms[0].text) and not list(forms[0]),
                        "invalid_formula_node")
                members.add((sid, address))
    return members


def normalize_core(root: ET.Element) -> None:
    times = []
    for tag in ("created", "modified"):
        nodes = root.findall(f"{{{DCT}}}{tag}")
        require(len(nodes) == 1 and not list(nodes[0]) and
                bool(UTC.fullmatch(nodes[0].text or "")),
                "invalid_save_timestamp")
        try:
            times.append(datetime.strptime(nodes[0].text, "%Y-%m-%dT%H:%M:%SZ"))
        except ValueError:
            raise ProposalError("invalid_save_timestamp") from None
        nodes[0].text = "VALIDATED_UTC_SAVE_TIMESTAMP"
    require(times[0] <= times[1], "invalid_save_timestamp_order")


def normalize_workbook(root: ET.Element) -> None:
    nodes = root.findall(f"{{{REV}}}revisionPtr")
    require(len(nodes) == 1, "revision_pointer_count_changed")
    match = SESSION.fullmatch(nodes[0].attrib.get("documentId", ""))
    require(match is not None, "invalid_session_document_id")
    # The observed prefix remains protected; only the valid session UUID moves.
    nodes[0].attrib["documentId"] = match[1] + "_{VALID_SESSION_UUID}"


def normalize_sheet(root: ET.Element, targets: set[str]) -> None:
    for selection in root.findall("m:sheetViews/m:sheetView/m:selection", NS):
        active, sqref = (selection.attrib.get("activeCell"),
                         selection.attrib.get("sqref"))
        require((active is None and sqref is None) or
                (active is not None and sqref == active and bounded_cell(active)),
                "invalid_or_unobserved_selection_focus")
        selection.attrib.pop("activeCell", None)
        selection.attrib.pop("sqref", None)
    for cell in root.findall("m:sheetData/m:row/m:c", NS):
        formula = cell.find("m:f", NS)
        if cell.attrib["r"] in targets and formula is not None:
            formula.text = "INDEPENDENTLY_CHECKED_TARGET_FORMULA"
        if formula is not None:
            cached = cell.find("m:v", NS)
            if cached is not None:
                cached.text = "INDEPENDENTLY_CHECKED_NUMERIC_CACHE"


def normalized_chain(root: ET.Element, members: set[tuple[str, str]]) -> tuple:
    require(root.tag == f"{{{M}}}calcChain", "invalid_calculation_chain_root")
    found = []
    for cell in root:
        require(cell.tag == f"{{{M}}}c" and
                set(cell.attrib) <= {"r", "i", "l", "s"} and
                {"r", "i"} <= set(cell.attrib) and not list(cell) and
                cell.text in (None, "") and cell.tail in (None, ""),
                "unobserved_calculation_chain_node")
        require(all(cell.attrib.get(flag, "0") in {"0", "1"}
                    for flag in ("l", "s")), "invalid_calculation_chain_flag")
        require(bounded_cell(cell.attrib["r"]) and
                re.fullmatch(r"[1-9][0-9]*", cell.attrib["i"]) is not None,
                "invalid_calculation_chain_member")
        found.append((cell.attrib["i"], cell.attrib["r"]))
    require(len(found) == len(set(found)) and set(found) == members,
            "calculation_chain_membership_changed")
    # Root metadata stays protected. l/s and ordering are the only discarded data.
    return (root.tag, tuple(sorted(root.attrib.items())), root.text, root.tail,
            tuple(sorted(found)))


def compare_packages(candidate: Path, baseline: Path,
                     targets: set[tuple[str, str]] = BANK_TARGETS) -> dict:
    before, after = package(baseline), package(candidate)
    require(set(before) == set(after), "native_baseline_part_set_changed")
    old_sheets, new_sheets = sheet_parts(before), sheet_parts(after)
    require(old_sheets == new_sheets, "native_sheet_identity_changed")
    old_members = formula_members(before, old_sheets)
    new_members = formula_members(after, new_sheets)
    require(old_members == new_members, "formula_cell_membership_changed")
    require("xl/calcChain.xml" in before, "native_calculation_chain_required")
    by_part = {part: {a for s, a in targets if s == name}
               for name, (_, part) in old_sheets.items()}
    changed = []
    for name in sorted(before):
        if before[name] != after[name]:
            changed.append(name)
        if not name.endswith((".xml", ".rels")):
            require(before[name] == after[name], "protected_binary_part_changed")
            continue
        left, right = xml(before[name]), xml(after[name])
        if name == "xl/calcChain.xml":
            require(normalized_chain(left, old_members) ==
                    normalized_chain(right, new_members),
                    "protected_calculation_chain_metadata_changed")
            continue
        if name == "docProps/core.xml":
            normalize_core(left)
            normalize_core(right)
        elif name == "xl/workbook.xml":
            normalize_workbook(left)
            normalize_workbook(right)
        elif name in by_part:
            normalize_sheet(left, by_part[name])
            normalize_sheet(right, by_part[name])
        require(semantic(left) == semantic(right), "protected_xml_part_changed")
    return {"part_count": len(before), "changed_part_count": len(changed),
            "formula_chain_members": len(old_members)}


def load_review(path: Path) -> tuple[dict, dict]:
    require(digest(path) == REVIEW_SHA256, "private_review_binding_changed")
    review = json.loads(path.read_bytes())
    require(review.get("schema") ==
            "envloop.sec_excel_train_next_four_review.private.v1" and
            review.get("scope") ==
            "four TRAIN-only source bundles; no selection/final artifact" and
            review.get("source_plan_sha256") == SOURCE_PLAN_SHA256,
            "wrong_train_review_scope")
    cases = [row for row in review["cases"] if row.get("case_index") == CASE_INDEX]
    require(len(cases) == 1, "train_case_not_unique")
    case = cases[0]
    require(case.get("profile") == "bank" and case.get("review_status") ==
            "source_field_review_pass; independent_audit_pending" and
            case.get("excel_web_admitted") is False and
            case.get("official_final_admitted") is False,
            "wrong_train_case_scope")
    return review, case


def source_byte_bindings(review: dict, case: dict) -> dict:
    directory = Path(review["raw_source_root"]) / f"source-{CASE_INDEX:02d}"
    expected = case["source"]["raw_sha256"]
    files = {"10k": "10k.html", "companyfacts": "companyfacts.json",
             "index": "index.html", "submissions": "submissions.json",
             "support": "support.html"}
    require(set(expected) == set(files), "raw_source_file_set_changed")
    for label, name in files.items():
        require(digest(directory / name) == expected[label],
                "raw_source_bytes_changed")
    source_case_sha = digest(directory / "source-case.private.json")
    require(source_case_sha == case["source"]["source_case_sha256"],
            "raw_source_case_changed")
    return {"raw_source_sha256": dict(sorted(expected.items())),
            "source_case_sha256": source_case_sha,
            "source_plan_sha256": review["source_plan_sha256"],
            "raw_source_files_verified": len(files)}


def qualify_native_cells(raw_seed: Path, baseline: Path, case: dict) -> dict:
    raw, order, tables, structures = load_xlsx(raw_seed)
    native, native_order, native_tables, native_structures = load_xlsx(baseline)
    require(order == native_order == SHEETS["bank"] and tables == native_tables and
            structures == native_structures, "raw_to_native_sheet_structure_changed")
    require(_source_cells_match(case, raw) and _source_cells_match(case, native),
            "raw_or_native_source_not_reviewed")
    count = 0
    for sheet in order:
        for address in set(raw[sheet]) | set(native[sheet]):
            count += 1
            left, right = raw[sheet].get(address), native[sheet].get(address)
            require(left is not None and right is not None and
                    unchanged_cell(left, right), "raw_to_native_semantic_cell_changed")
    return {"raw_to_native_semantic_cells_unchanged": True,
            "raw_to_native_semantic_cell_count": count,
            "raw_to_native_package_qualified": False,
            "raw_to_native_visual_qualified": False}


def arithmetic_checks(candidate_path: Path, baseline_path: Path, case: dict) -> dict:
    candidate, order, tables, structures = load_xlsx(candidate_path)
    baseline, old_order, old_tables, old_structures = load_xlsx(baseline_path)
    require(order == old_order == SHEETS["bank"] and tables == old_tables and
            structures == old_structures, "candidate_sheet_structure_changed")
    require(_source_cells_match(case, candidate), "candidate_source_not_reviewed")
    non_targets = 0
    for sheet in order:
        for address in set(baseline[sheet]) | set(candidate[sheet]):
            if (sheet, address) in BANK_TARGETS:
                continue
            non_targets += 1
            left, right = baseline[sheet].get(address), candidate[sheet].get(address)
            require(left is not None and right is not None and
                    left.formula == right.formula and
                    (left.formula is not None or unchanged_cell(left, right)),
                    "non_target_semantic_cell_changed")
    evaluator = Evaluator(candidate)
    caches = 0
    for sheet, cells in candidate.items():
        for address, cell in cells.items():
            if cell.formula is None:
                continue
            require(cell.value is not None and cell.type in (None, "n"),
                    "missing_or_non_numeric_formula_cache")
            try:
                value = float(cell.value)
                actual = evaluator.cell(sheet, address)
            except (TypeError, ValueError, ArithmeticError):
                raise ProposalError("invalid_formula_or_numeric_cache") from None
            require(math.isfinite(value) and _close(value, actual),
                    "stale_saved_formula_cache")
            caches += 1
    require(not _target_values(candidate, case, source_changes={}, driver_changes={}),
            "wrong_target_formula_result")
    baseline_values = expected_values(case)
    witnessed = set()
    replays = _counterfactuals(case)
    require(len(BANK_TARGETS) == 12 and len(replays) == 10,
            "independent_train_contract_changed")
    for sources, drivers in replays:
        values = expected_values(case, source_changes=sources, driver_changes=drivers)
        witnessed.update(key for key in BANK_TARGETS
                         if not _close(values[key], baseline_values[key]))
        require(not _target_values(candidate, case, source_changes=sources,
                                   driver_changes=drivers),
                "target_counterfactual_dependency_failed")
    require(witnessed == BANK_TARGETS, "target_dependency_coverage_incomplete")
    require(all(_close(evaluator.cell("Checks", f"B{row}"), 0) for row in (5, 6)),
            "reconciliation_formula_failed")
    return {"checked_formula_targets": 12, "source_driver_replays": 10,
            "counterfactual_target_coverage": len(witnessed),
            "checked_formula_caches": caches, "unchanged_non_target_cells": non_targets,
            "sheet_count": len(order), "table_count": len(tables)}


def verify(candidate: Path, raw_seed: Path, baseline: Path, review_path: Path) -> dict:
    result = {"schema": SCHEMA, "scope": "one_frozen_bank_TRAIN_source_case",
              "train_derived_proposal_pass": False, "reason_codes": [],
              "model_calls": 0, "selection_runs": 0, "final_runs": 0,
              "excel_web_admissions": 0, "official_final_admissions": 0,
              "native_recalculation_provenance_verified": False,
              "raw_to_native_package_qualified": False,
              "raw_to_native_visual_qualified": False,
              "independent_source_review_complete": False}
    try:
        result.update({"candidate_sha256": digest(candidate),
                       "raw_seed_sha256": digest(raw_seed),
                       "native_baseline_sha256": digest(baseline),
                       "private_review_sha256": digest(review_path)})
        require(result["raw_seed_sha256"] == SEED_SHA256 and
                result["native_baseline_sha256"] == BASELINE_SHA256,
                "frozen_seed_or_native_baseline_binding_changed")
        review, case = load_review(review_path)
        result["reviewed_case_sha256"] = sha256(json.dumps(
            case, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        result.update(source_byte_bindings(review, case))
        result.update(qualify_native_cells(raw_seed, baseline, case))
        result.update(compare_packages(candidate, baseline))
        result.update(arithmetic_checks(candidate, baseline, case))
        result["train_derived_proposal_pass"] = True
    except ProposalError as exc:
        result["reason_codes"] = [str(exc)]
    except Exception as exc:
        # Class only: parser/formula exceptions can contain source values/paths.
        result["reason_codes"] = ["unhandled_verification_" + type(exc).__name__]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--raw-seed", type=Path, required=True)
    parser.add_argument("--native-baseline", type=Path, required=True)
    parser.add_argument("--private-review", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.candidate, args.raw_seed, args.native_baseline,
                    args.private_review)
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result["train_derived_proposal_pass"] else 1)


if __name__ == "__main__":
    main()
