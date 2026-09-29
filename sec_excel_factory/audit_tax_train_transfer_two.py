"""Adversarial saved-OOXML controls for TRAIN-only tax workbooks.

The reference must pass. The faulty seed, every one-target-short variant, every
target hardcode, semantic negatives, source/style/cache changes and reset copy
must receive the expected independent verifier verdict.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from sec_excel_factory.verify_tax_train_transfer_two import TARGETS, verify
from sec_excel_factory.verify_train_transfer_four import _sheet_paths
from tools.sec_tax_train_prepare_v1 import (
    CARD_SIGNATURE, GRAPH, REVIEW_SHA256, REVIEWED_CARD_SHA256,
    SOURCE_PLAN_SHA256, _make_case,
)
from verify_ooxml import Evaluator, load_xlsx


NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _private(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    raw = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(raw)


def _require_frozen_case_exact(case: dict, reconstructed: dict) -> None:
    """Require every normalized reviewed fact, absence and locator to match."""
    if case != reconstructed:
        raise ValueError("private_case_fields_differ_from_frozen_semantic_review")


def mutate(source: Path, destination: Path, sheet: str, address: str,
           *, formula: str | None = None, value: str | None = None,
           style_change: bool = False, remove_cache: bool = False,
           refresh_cache: bool = False) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with ZipFile(source) as original:
        part = _sheet_paths(original)[sheet]
        with ZipFile(destination, "w") as changed:
            for info in original.infolist():
                raw = original.read(info.filename)
                if info.filename == part:
                    tree = ET.fromstring(raw)
                    matches = [cell for cell in tree.findall(
                        f".//{{{NS}}}sheetData/{{{NS}}}row/{{{NS}}}c")
                        if cell.attrib.get("r") == address]
                    if len(matches) != 1:
                        raise ValueError("mutation_target_cell_not_unique")
                    cell = matches[0]
                    if style_change:
                        cell.set("s", str(int(cell.attrib.get("s", "0")) + 1))
                    if formula is not None:
                        f = cell.find(f"{{{NS}}}f")
                        if f is None:
                            f = ET.Element(f"{{{NS}}}f")
                            cell.insert(0, f)
                        f.text = formula.lstrip("=")
                    if value is not None:
                        v = cell.find(f"{{{NS}}}v")
                        if v is None:
                            v = ET.SubElement(cell, f"{{{NS}}}v")
                        v.text = value
                    if remove_cache:
                        v = cell.find(f"{{{NS}}}v")
                        if v is not None:
                            cell.remove(v)
                    raw = ET.tostring(tree, encoding="utf-8", xml_declaration=True)
                changed.writestr(info, raw)
    os.chmod(destination, 0o600)
    if refresh_cache:
        _refresh_all_formula_caches(destination)


def _refresh_all_formula_caches(path: Path) -> None:
    """Remove stale-display rejection as the reason for a semantic negative."""
    sheets, *_ = load_xlsx(path)
    evaluator = Evaluator(sheets)
    values = {(sheet, address): evaluator.cell(sheet, address)
              for sheet, cells in sheets.items() for address, cell in cells.items()
              if cell.formula}
    temporary = path.with_suffix(".recomputed.xlsx")
    with ZipFile(path) as original:
        parts = _sheet_paths(original)
        owners = {part: owner for owner, part in parts.items()}
        with ZipFile(temporary, "w") as changed:
            for info in original.infolist():
                raw = original.read(info.filename)
                if info.filename in owners:
                    sheet = owners[info.filename]
                    tree = ET.fromstring(raw)
                    for cell in tree.findall(
                        f".//{{{NS}}}sheetData/{{{NS}}}row/{{{NS}}}c"):
                        address = cell.attrib["r"]
                        if (sheet, address) not in values:
                            continue
                        v = cell.find(f"{{{NS}}}v")
                        if v is None:
                            v = ET.SubElement(cell, f"{{{NS}}}v")
                        v.text = format(values[(sheet, address)], ".15g")
                    raw = ET.tostring(tree, encoding="utf-8", xml_declaration=True)
                changed.writestr(info, raw)
    os.replace(temporary, path)
    os.chmod(path, 0o600)


def audit_one(index: int, root: Path, controls: Path) -> dict:
    name = f"case-{index:02d}"
    case_path = root / "cases" / f"{name}.private.json"
    seed = root / "workbooks" / name / "seed.xlsx"
    positive = root / "workbooks" / name / "positive.xlsx"
    base = verify(seed, seed, case_path)
    good = verify(positive, seed, case_path)
    if base["pass"] or not good["pass"] or good["checked_targets"] != 12:
        raise ValueError("positive_or_unrepaired_seed_control_failed")
    old, *_ = load_xlsx(seed)
    fixed, *_ = load_xlsx(positive)
    control_dir = controls / name
    control_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    one_short = 0
    hardcode = 0
    for serial, (sheet, address) in enumerate(sorted(TARGETS)):
        bad_formula = old[sheet][address].formula
        if not bad_formula:
            raise ValueError("seed_target_without_faulty_formula")
        near = control_dir / f"one-target-short-{serial:02d}.xlsx"
        mutate(positive, near, sheet, address, formula=bad_formula,
               refresh_cache=True)
        near_result = verify(near, seed, case_path)
        if near_result["pass"] or not any("wrong_target_result:" in e
                                           for e in near_result["errors"]):
            raise ValueError("one_target_short_accepted")
        one_short += 1
        saved = fixed[sheet][address].value
        if saved is None:
            raise ValueError("reference_target_without_saved_value")
        static = control_dir / f"hardcoded-target-{serial:02d}.xlsx"
        mutate(positive, static, sheet, address, formula=saved, value=saved,
               refresh_cache=True)
        static_result = verify(static, seed, case_path)
        if static_result["pass"] or not any("wrong_target_result:" in e
                                             for e in static_result["errors"]):
            raise ValueError("hardcoded_target_accepted")
        hardcode += 1
    semantic = (
        ("wrong_period", "Gross bridge", "C5", "'Source facts'!B5"),
        ("wrong_reduction_sign", "Gross bridge", "C8", "-'Source facts'!C8"),
        ("omit_settlements", "Gross bridge", "C13", "C6+C7+C8+C10+C11+C12"),
        ("mix_interest_into_gross", "Gross bridge", "C14",
         "C5+C13+'Interest scope'!C5"),
        ("ignore_scenario", "Tax summary", "B8", "'Interest scope'!C8"),
    )
    semantic_rejected = 0
    for label, sheet, address, wrong in semantic:
        variant = control_dir / f"semantic-{label}.xlsx"
        mutate(positive, variant, sheet, address, formula=wrong,
               refresh_cache=True)
        result = verify(variant, seed, case_path)
        if result["pass"] or not any("wrong_target_result:" in e
                                     for e in result["errors"]):
            raise ValueError("semantic_negative_accepted")
        semantic_rejected += 1
    collateral = control_dir / "collateral-source-edit.xlsx"
    filed = fixed["Source facts"]["C6"].value
    mutate(positive, collateral, "Source facts", "C6", value=str(float(filed) + 1),
           refresh_cache=True)
    if verify(collateral, seed, case_path)["pass"]:
        raise ValueError("collateral_filed_fact_edit_accepted")
    style = control_dir / "style-change.xlsx"
    mutate(positive, style, "Tax summary", "B8", style_change=True)
    if verify(style, seed, case_path)["pass"]:
        raise ValueError("style_change_accepted")
    stale = control_dir / "stale-display-cache.xlsx"
    value = fixed["Tax summary"]["B5"].value
    mutate(positive, stale, "Tax summary", "B5", value=str(float(value) + 100))
    if verify(stale, seed, case_path)["pass"]:
        raise ValueError("stale_non_target_cache_accepted")
    missing_cache = control_dir / "missing-target-cache.xlsx"
    mutate(positive, missing_cache, "Tax summary", "B8", remove_cache=True)
    missing_result = verify(missing_cache, seed, case_path)
    if missing_result["pass"] or not any("missing_saved_numeric_formula_cache:" in e
                                        for e in missing_result["errors"]):
        raise ValueError("missing_saved_display_cache_accepted")
    reset = control_dir / "fresh-reset-seed.xlsx"
    shutil.copyfile(seed, reset)
    os.chmod(reset, 0o600)
    if _sha(reset) != _sha(seed) or verify(reset, seed, case_path)["pass"]:
        raise ValueError("fresh_reset_not_byte_exact_seed")
    return {"case_index": index, "case_sha256": _sha(case_path),
            "seed_sha256": _sha(seed), "positive_sha256": _sha(positive),
            "positive_pass": True, "unrepaired_seed_rejected": True,
            "target_count": 12, "one_target_short_rejected": one_short,
            "individual_hardcodes_rejected": hardcode,
            "semantic_negatives_rejected": semantic_rejected,
            "collateral_filed_fact_rejected": True,
            "style_change_rejected": True,
            "stale_display_cache_rejected": True,
            "missing_target_cache_rejected": True,
            "fresh_reset_byte_exact": True,
            "positive_counterfactual_replays": good["counterfactual_replays"],
            "official_excel_web_admitted": 0}


def audit(root: Path, output: Path, *, source_plan: Path,
          semantic_review: Path, raw_root: Path, card_root: Path) -> dict:
    manifest_path = root / "cases-manifest.private.json"
    manifest = json.loads(manifest_path.read_bytes())
    if (manifest.get("schema") != "envloop.sec_tax_train_case_manifest.private.v1" or
            manifest.get("case_count") != 2 or
            manifest.get("official_excel_web_admitted") != 0):
        raise ValueError("private_train_case_manifest_missing")
    plan_raw = source_plan.read_bytes()
    review_raw = semantic_review.read_bytes()
    if (_sha(source_plan) != SOURCE_PLAN_SHA256 or
            _sha(semantic_review) != REVIEW_SHA256 or
            manifest.get("source_plan_sha256") != SOURCE_PLAN_SHA256 or
            manifest.get("semantic_review_sha256") != REVIEW_SHA256):
        raise ValueError("source_plan_or_semantic_review_freeze_changed")
    plan, review = json.loads(plan_raw), json.loads(review_raw)
    if review.get("source_plan_sha256") != SOURCE_PLAN_SHA256:
        raise ValueError("source_review_plan_binding_changed")
    card_path = card_root / "skill-cards-reviewed.private.json"
    if (_sha(card_path) != REVIEWED_CARD_SHA256 or
            manifest.get("signed_card_sha256") != REVIEWED_CARD_SHA256):
        raise ValueError("reviewed_skill_card_freeze_changed")
    cards = json.loads(card_path.read_bytes())
    matches = [row for row in cards["cards"]
               if row.get("skill_signature_sha256") == CARD_SIGNATURE and
               row.get("final_graph_reservation") == GRAPH and
               row.get("independent_skill_review") is True]
    if len(matches) != 1:
        raise ValueError("signed_reviewed_tax_skill_card_missing")
    card = matches[0]
    for i in range(2):
        case_path = root / "cases" / f"case-{i:02d}.private.json"
        if _sha(case_path) != manifest["case_sha256"][i]:
            raise ValueError("private_case_package_changed")
        case = json.loads(case_path.read_bytes())
        selected = plan["records"][i]
        reviewed = review["source_reviews"][i]
        if (case["source"]["issuer_cik"] != selected["issuer_cik"] or
                case["source"]["accession"] != selected["accession"] or
                case["source"]["raw_sha256"] != reviewed["raw_sha256"] or
                case["source"]["semantic_review_sha256"] != REVIEW_SHA256):
            raise ValueError("private_case_source_provenance_changed")
        for filename, digest in reviewed["raw_sha256"].items():
            if _sha(raw_root / f"source-{i:02d}" / filename) != digest:
                raise ValueError("frozen_original_sec_raw_bytes_changed")
        expected_case = _make_case(i, reviewed, selected, raw_root,
                                   REVIEW_SHA256, card)
        _require_frozen_case_exact(case, expected_case)
    controls = root / "offline-controls"
    if controls.exists():
        raise ValueError("offline_control_directory_must_be_fresh")
    controls.mkdir(mode=0o700)
    rows = [audit_one(i, root, controls) for i in range(2)]
    private = {"schema": "envloop.sec_tax_train_offline_audit.private.v1",
               "status": "two_train_only_tax_saved_ooxml_controls_passed",
               "source_manifest_sha256": _sha(manifest_path),
               "frozen_source_case_reconstructions_exact": 2,
               "cases": rows, "model_calls": 0,
               "original_excel_web_gui_uses": 0, "official_final_admissions": 0}
    _private(output, private)
    return {"status": private["status"], "cases": 2,
            "positive_saved_ooxml_pass": 2, "seed_rejected": 2,
            "frozen_source_case_reconstructions_exact": 2,
            "one_target_short_rejected": sum(r["one_target_short_rejected"] for r in rows),
            "individual_hardcodes_rejected": sum(r["individual_hardcodes_rejected"] for r in rows),
            "semantic_negatives_rejected": sum(r["semantic_negatives_rejected"] for r in rows),
            "collateral_rejected": 2, "style_rejected": 2,
            "stale_cache_rejected": 2, "missing_cache_rejected": 2,
            "fresh_reset_exact": 2,
            "positive_counterfactual_replays": sum(r["positive_counterfactual_replays"] for r in rows),
            "official_excel_web_admissions": 0,
            "private_audit_sha256": _sha(output)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--private-root", type=Path, required=True)
    ap.add_argument("--private-out", type=Path, required=True)
    ap.add_argument("--source-plan", type=Path, required=True)
    ap.add_argument("--semantic-review", type=Path, required=True)
    ap.add_argument("--raw-root", type=Path, required=True)
    ap.add_argument("--card-private-root", type=Path, required=True)
    args = ap.parse_args()
    print(json.dumps(audit(args.private_root, args.private_out,
                           source_plan=args.source_plan,
                           semantic_review=args.semantic_review,
                           raw_root=args.raw_root,
                           card_root=args.card_private_root), sort_keys=True))


if __name__ == "__main__":
    main()
