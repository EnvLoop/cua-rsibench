"""Exercise positive, isolated-fault, hardcode, collateral, and reset controls.

All mutated OOXML files are evaluator-private disposable controls, not authored
training tasks. The four seed/reference workbooks are made with artifact-tool.
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

from sec_excel_factory.verify_train_transfer_four import (
    CASH, CASH_TARGETS, INTEREST_TARGETS, _sheet_paths, load_xlsx, verify,
)


NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _write_private(path: Path, obj: dict) -> None:
    raw = (json.dumps(obj, sort_keys=True, indent=2) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(raw)


def mutate(source: Path, output: Path, sheet: str, address: str,
           *, formula: str | None = None, value: str | None = None,
           style_change: bool = False) -> None:
    """Change exactly one cell in an OOXML test copy."""
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with ZipFile(source) as original:
        part = _sheet_paths(original)[sheet]
        with ZipFile(output, "w") as changed:
            for info in original.infolist():
                data = original.read(info.filename)
                if info.filename == part:
                    root = ET.fromstring(data)
                    matches = [cell for cell in root.findall(f".//{{{NS}}}sheetData/{{{NS}}}row/{{{NS}}}c")
                               if cell.attrib.get("r") == address]
                    if len(matches) != 1:
                        raise ValueError("target_cell_not_unique")
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
                    data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
                changed.writestr(info, data)
    os.chmod(output, 0o600)


def audit_one(index: int, root: Path, test_root: Path) -> dict:
    name = f"case-{index:02d}"
    case_path = root / "cases" / f"{name}.private.json"
    c = json.loads(case_path.read_bytes())
    case_dir = root / "workbooks" / name
    seed, positive = case_dir / "seed.xlsx", case_dir / "positive.xlsx"
    targets = CASH_TARGETS if c["profile"] == CASH else INTEREST_TARGETS
    seed_sheets, *_ = load_xlsx(seed)
    positive_sheets, *_ = load_xlsx(positive)
    pos = verify(positive, seed, case_path)
    base = verify(seed, seed, case_path)
    if not pos["pass"] or base["pass"]:
        raise ValueError("positive_or_unrepaired_seed_control_failed")
    controls = test_root / name
    controls.mkdir(parents=True, exist_ok=False, mode=0o700)
    individually_rejected = 0
    individual_results = []
    for serial, (sheet, addr) in enumerate(sorted(targets)):
        bad = seed_sheets[sheet][addr]
        if not bad.formula:
            raise ValueError("seed_target_lacks_formula")
        near = controls / f"one-target-short-{serial:02d}.xlsx"
        mutate(positive, near, sheet, addr, formula=bad.formula,
               value=bad.value if bad.value is not None else None)
        result = verify(near, seed, case_path)
        individual_results.append({"ordinal": serial, "rejected": not result["pass"],
                                   "error_classes": sorted({x.split(":")[0] for x in result["errors"]})})
        individually_rejected += int(not result["pass"])
    if individually_rejected != len(targets):
        raise ValueError("isolated_one_target_fault_escaped")

    hardcoded_rejected = 0
    for serial, (sheet, addr) in enumerate(sorted(targets)):
        target_cell = positive_sheets[sheet][addr]
        if target_cell.value is None:
            raise ValueError("positive_target_value_uncached")
        hardcoded = controls / f"hardcoded-target-{serial:02d}.xlsx"
        mutate(positive, hardcoded, sheet, addr,
               formula=target_cell.value, value=target_cell.value)
        hard_result = verify(hardcoded, seed, case_path)
        if hard_result["pass"]:
            raise ValueError("individually_hardcoded_target_accepted")
        hardcoded_rejected += 1

    if c["profile"] == CASH:
        semantic = [
            ("wrong_period", "Flow build", "C5", "'Source facts'!B5"),
            ("investing_sign", "Flow build", "C9", "C5-C6+C7+C8"),
            ("omit_restricted_cash", "Flow build", "C17", "C14-C15"),
        ]
        terminal = ("Cash summary", "B5")
    else:
        semantic = [
            ("wrong_period", "Interest build", "C5", "'Source facts'!B5"),
            ("interest_sign", "Rate scenario", "C7", "'Interest build'!C6-C6"),
            ("wrong_debt_basis", "Rate scenario", "C5", "'Interest build'!C9"),
        ]
        terminal = ("Interest summary", "B5")
    semantic_rejected = 0
    for name, sheet, addr, wrong in semantic:
        bad = controls / f"semantic-{name}.xlsx"
        mutate(positive, bad, sheet, addr, formula=wrong)
        if verify(bad, seed, case_path)["pass"]:
            raise ValueError("semantic_negative_accepted")
        semantic_rejected += 1

    collateral = controls / "collateral-original-fact.xlsx"
    fact = positive_sheets["Source facts"]["C5"]
    mutate(positive, collateral, "Source facts", "C5",
           value=str(float(fact.value) + 1.0))
    collateral_result = verify(collateral, seed, case_path)
    if collateral_result["pass"]:
        raise ValueError("collateral_original_fact_edit_accepted")

    styled = controls / "target-style-changed.xlsx"
    mutate(positive, styled, terminal[0], terminal[1], style_change=True)
    style_result = verify(styled, seed, case_path)
    if style_result["pass"]:
        raise ValueError("target_style_change_accepted")

    cache = controls / "stale-nontarget-display-cache.xlsx"
    display_value = positive_sheets[terminal[0]][terminal[1]].value
    if display_value is None:
        raise ValueError("positive_display_cache_missing")
    mutate(positive, cache, terminal[0], terminal[1],
           value=str(float(display_value) + 100.0))
    cache_result = verify(cache, seed, case_path)
    if cache_result["pass"]:
        raise ValueError("stale_nontarget_display_cache_accepted")

    reset = controls / "fresh-reset-seed.xlsx"
    shutil.copyfile(seed, reset)
    os.chmod(reset, 0o600)
    if _sha(reset) != _sha(seed) or verify(reset, seed, case_path)["pass"]:
        raise ValueError("fresh_source_reset_not_exact_seed")
    return {"case_index": index, "profile": c["profile"],
            "case_sha256": _sha(case_path), "seed_sha256": _sha(seed),
            "positive_sha256": _sha(positive),
            "positive_pass": pos["pass"], "unrepaired_seed_rejected": not base["pass"],
            "target_count": len(targets),
            "one_target_short_rejected": individually_rejected,
            "individual_target_controls": individual_results,
            "positive_counterfactual_replays": pos["counterfactual_replays"],
            "individual_hardcodes_rejected": hardcoded_rejected,
            "semantic_negatives_rejected": semantic_rejected,
            "collateral_original_fact_rejected": not collateral_result["pass"],
            "target_style_change_rejected": not style_result["pass"],
            "stale_nontarget_display_cache_rejected": not cache_result["pass"],
            "fresh_reset_byte_exact": True,
            "official_excel_web_admitted": 0}


def audit(root: Path, out_path: Path) -> dict:
    case_manifest_raw = (root / "cases-manifest.private.json").read_bytes()
    manifest = json.loads(case_manifest_raw)
    if manifest.get("schema") != "envloop.sec_four_train_case_manifest.private.v1":
        raise ValueError("case_manifest_missing")
    for i in range(4):
        p = root / "cases" / f"case-{i:02d}.private.json"
        if _sha(p) != manifest["case_sha256"][i]:
            raise ValueError("private_case_package_changed")
    controls = root / "offline-controls"
    if controls.exists():
        raise ValueError("offline_control_directory_must_be_fresh")
    controls.mkdir(mode=0o700)
    rows = [audit_one(i, root, controls) for i in range(4)]
    private = {"schema": "envloop.sec_four_train_offline_audit.private.v1",
               "status": "four_train_only_offline_saved_ooxml_controls_passed",
               "source_manifest_sha256": _sha(root / "cases-manifest.private.json"),
               "cases": rows, "no_original_excel_web_gui": True,
               "model_calls": 0, "official_final_admissions": 0}
    _write_private(out_path, private)
    return {"status": private["status"], "cases": 4,
            "positive_saved_ooxml_pass": sum(x["positive_pass"] for x in rows),
            "seed_rejected": sum(x["unrepaired_seed_rejected"] for x in rows),
            "one_target_short_rejected": sum(x["one_target_short_rejected"] for x in rows),
            "individual_hardcodes_rejected": sum(x["individual_hardcodes_rejected"] for x in rows),
            "semantic_negatives_rejected": sum(x["semantic_negatives_rejected"] for x in rows),
            "collateral_rejected": sum(x["collateral_original_fact_rejected"] for x in rows),
            "style_rejected": sum(x["target_style_change_rejected"] for x in rows),
            "stale_nontarget_cache_rejected": sum(x["stale_nontarget_display_cache_rejected"] for x in rows),
            "fresh_reset_exact": sum(x["fresh_reset_byte_exact"] for x in rows),
            "positive_counterfactual_replays": sum(x["positive_counterfactual_replays"] for x in rows),
            "official_excel_web_admissions": 0,
            "private_audit_sha256": _sha(out_path)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--private-root", type=Path, required=True)
    ap.add_argument("--private-out", type=Path, required=True)
    args = ap.parse_args()
    print(json.dumps(audit(args.private_root, args.private_out), sort_keys=True))


if __name__ == "__main__":
    main()
