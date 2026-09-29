"""Independent saved-OOXML scorer for four TRAIN-only SEC analogues.

The scorer imports only the generic OOXML parser/formula evaluator from the
existing SEC factory. It never imports the workbook builder or its formulas.
Expected business values are recomputed from evaluator-private reviewed source
packages; model selection/final workbooks and browser state are out of scope.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import sys
from xml.etree import ElementTree as ET
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_ooxml import Evaluator, load_xlsx, unchanged_cell  # noqa: E402


NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CASH = "cash_train_profile"
INTEREST = "interest_train_profile"
CASH_SHEETS = ["Cash summary", "Cash scenario", "Flow build", "Source facts",
               "Source lineage", "Checks"]
INTEREST_SHEETS = ["Interest summary", "Rate scenario", "Interest build",
                   "Source facts", "Source lineage", "Checks"]
CASH_SOURCE_ROWS = {"operating": 5, "investing": 6, "financing": 7, "fx": 8,
                    "net_change": 9, "beginning": 10, "ending": 11,
                    "cash": 12, "restricted": 13}
INTEREST_SOURCE_ROWS = {"operating_income": 5, "interest_expense_abs": 6,
                        "cash_from_operations": 7, "debt_component_1": 8,
                        "debt_component_2": 9, "debt_component_3": 10,
                        "debt_component_4": 11, "debt_principal_direct": 12,
                        "debt_carrying": 13, "unamortized_cost": 14}
CASH_LABELS = {
    "operating": "Operating cash flow", "investing": "Investing cash flow",
    "financing": "Financing cash flow", "fx": "Foreign-exchange effect",
    "net_change": "Reported net change in cash and restricted cash",
    "beginning": "Beginning cash and restricted cash",
    "ending": "Ending cash and restricted cash",
    "cash": "Ending cash and cash equivalents",
    "restricted": "Ending restricted cash and cash equivalents",
}
INTEREST_LABELS = {
    "operating_income": "Operating income",
    "interest_expense_abs": "Reported interest expense magnitude",
    "cash_from_operations": "Operating cash flow",
    **{f"debt_component_{i}": f"Tracked debt principal component {i}"
       for i in range(1, 5)},
    "debt_principal_direct": "Direct reported gross principal, if available",
    "debt_carrying": "Reported debt carrying value, if applicable",
    "unamortized_cost": "Reported unamortized issuance cost, if applicable",
}
CASH_TARGETS = {
    ("Flow build", "B5"), ("Flow build", "C5"), ("Flow build", "C6"),
    ("Flow build", "C9"), ("Flow build", "C11"), ("Flow build", "C13"),
    ("Flow build", "C17"), ("Flow build", "C19"),
    ("Cash scenario", "C5"), ("Cash scenario", "C9"),
    ("Cash scenario", "C10"), ("Cash summary", "B9"),
}
INTEREST_TARGETS = {
    ("Interest build", "B5"), ("Interest build", "C5"),
    ("Interest build", "C6"), ("Interest build", "C8"),
    ("Interest build", "C9"), ("Interest build", "C11"),
    ("Interest build", "C12"), ("Rate scenario", "C5"),
    ("Rate scenario", "C6"), ("Rate scenario", "C7"),
    ("Rate scenario", "C10"), ("Interest summary", "B8"),
}


def _close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-6)


def _num(cell) -> float:
    if cell is None or cell.value is None or cell.formula is not None:
        raise ValueError("reviewed_input_missing_or_replaced_with_formula")
    return float(cell.value)


def _same_saved_number(cell, expected: int | float) -> bool:
    try:
        return math.isfinite(_num(cell)) and _num(cell).hex() == float(expected).hex()
    except (ValueError, TypeError):
        return False


def _text(cell) -> str:
    return cell.value if cell is not None and cell.value is not None else ""


def _raw_number(case: dict, period: int, key: str,
                changes: dict[tuple[int, str], float]) -> float:
    item = case["periods"][period]["facts"].get(key)
    if item is None or not isinstance(item.get("value"), (int, float)):
        raise ValueError("missing_reviewed_original_fact")
    return changes.get((period, key), float(item["value"]))


def expected_values(case: dict, *, source_changes: dict[tuple[int, str], float] | None = None,
                    driver_changes: dict[str, float] | None = None) -> dict[tuple[str, str], float]:
    """Recompute the two selected graph profiles without builder formulas."""
    source_changes = source_changes or {}
    scenario = {**case["scenario"], **(driver_changes or {})}
    out: dict[tuple[str, str], float] = {}
    if case["profile"] == CASH:
        prior = {k: _raw_number(case, 0, k, source_changes) for k in CASH_SOURCE_ROWS}
        now = {k: _raw_number(case, 1, k, source_changes) for k in CASH_SOURCE_ROWS}
        signed_flow = now["operating"] + now["investing"] + now["financing"] + now["fx"]
        modeled_op = now["operating"] * (1 + scenario["operating_change"])
        modeled_investing = now["investing"] - now["operating"] * scenario["extra_investing_share"]
        modeled_fx = now["fx"] + now["operating"] * scenario["fx_share_change"]
        modeled_change = modeled_op + modeled_investing + now["financing"] + modeled_fx
        modeled_ending = now["beginning"] + modeled_change
        out.update({
            ("Flow build", "B5"): prior["operating"],
            ("Flow build", "C5"): now["operating"],
            ("Flow build", "C6"): now["investing"],
            ("Flow build", "C9"): signed_flow,
            ("Flow build", "C11"): signed_flow - now["net_change"],
            ("Flow build", "C13"): now["beginning"] + signed_flow,
            ("Flow build", "C17"): now["ending"] - now["cash"] - now["restricted"],
            ("Flow build", "C19"): now["operating"] / now["net_change"],
            ("Cash scenario", "C5"): modeled_op,
            ("Cash scenario", "C9"): modeled_change,
            ("Cash scenario", "C10"): modeled_ending,
            ("Cash summary", "B9"): modeled_ending,
        })
        if set(out) != CASH_TARGETS:
            raise ValueError("cash_target_contract_mismatch")
    elif case["profile"] == INTEREST:
        prior = {k: _raw_number(case, 0, k, source_changes)
                 for k in INTEREST_SOURCE_ROWS if k in case["periods"][0]["facts"]}
        now = {k: _raw_number(case, 1, k, source_changes)
               for k in INTEREST_SOURCE_ROWS if k in case["periods"][1]["facts"]}
        n = case["periods"][1]["component_count"]
        gross = sum(now[f"debt_component_{i}"] for i in range(1, n + 1))
        control = (now["debt_principal_direct"]
                   if case["source"]["debt_control_kind"] == "direct_principal"
                   else now["debt_carrying"] + now["unamortized_cost"])
        added_interest = gross * scenario["rate_change"]
        modeled_interest = now["interest_expense_abs"] + added_interest
        modeled_income = now["operating_income"] * (1 + scenario["income_change"])
        modeled_coverage = modeled_income / modeled_interest
        out.update({
            ("Interest build", "B5"): prior["operating_income"],
            ("Interest build", "C5"): now["operating_income"],
            ("Interest build", "C6"): now["interest_expense_abs"],
            ("Interest build", "C8"): gross,
            ("Interest build", "C9"): control,
            ("Interest build", "C11"): now["operating_income"] / now["interest_expense_abs"],
            ("Interest build", "C12"): now["cash_from_operations"] / now["interest_expense_abs"],
            ("Rate scenario", "C5"): gross,
            ("Rate scenario", "C6"): added_interest,
            ("Rate scenario", "C7"): modeled_interest,
            ("Rate scenario", "C10"): modeled_coverage,
            ("Interest summary", "B8"): modeled_coverage,
        })
        if set(out) != INTEREST_TARGETS:
            raise ValueError("interest_target_contract_mismatch")
    else:
        raise ValueError("unsupported_train_profile")
    return out


def _sheet_paths(z: ZipFile) -> dict[str, str]:
    book = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    ids = {item.attrib["Id"]: item.attrib["Target"]
           for item in rels.findall(f"{{{PKG_REL_NS}}}Relationship")}
    found = {}
    for item in book.findall("m:sheets/m:sheet", NS):
        target = ids[item.attrib[f"{{{NS['r']}}}id"]]
        found[item.attrib["name"]] = target.lstrip("/") if target.startswith("/") else "xl/" + target
    return found


def _normalized_sheet(raw: bytes, targets: set[str]) -> bytes:
    tree = ET.fromstring(raw)
    for cell in tree.findall(".//m:sheetData/m:row/m:c", NS):
        addr = cell.attrib["r"]
        if addr in targets:
            for child in list(cell):
                if child.tag in (f"{{{NS['m']}}}f", f"{{{NS['m']}}}v"):
                    cell.remove(child)
        else:
            form = cell.find("m:f", NS)
            if form is not None:
                cached = cell.find("m:v", NS)
                if cached is not None:
                    cached.text = None
    return ET.tostring(tree, encoding="utf-8")


def _normalized_rels(raw: bytes) -> tuple:
    tree = ET.fromstring(raw)
    return tuple(sorted((e.attrib.get("Type"), e.attrib.get("Target"),
                         e.attrib.get("TargetMode")) for e in tree))


def _normalized_workbook(raw: bytes) -> bytes:
    tree = ET.fromstring(raw)
    for sheet in tree.findall("m:sheets/m:sheet", NS):
        sheet.attrib.pop(f"{{{NS['r']}}}id", None)
    return ET.tostring(tree, encoding="utf-8")


def _package_structure_unchanged(candidate: Path, seed: Path,
                                 targets: set[tuple[str, str]]) -> bool:
    with ZipFile(candidate) as current, ZipFile(seed) as original:
        names = set(current.namelist())
        if names != set(original.namelist()):
            return False
        current_sheet = _sheet_paths(current)
        original_sheet = _sheet_paths(original)
        if set(current_sheet) != set(original_sheet):
            return False
        current_sheet_parts = set(current_sheet.values())
        original_sheet_parts = set(original_sheet.values())
        if current_sheet_parts != original_sheet_parts:
            return False
        for name in sorted(names - current_sheet_parts):
            a, b = current.read(name), original.read(name)
            if name.endswith(".rels"):
                if _normalized_rels(a) != _normalized_rels(b):
                    return False
            elif name == "xl/workbook.xml":
                if _normalized_workbook(a) != _normalized_workbook(b):
                    return False
            elif a != b:
                return False
        for sheet in current_sheet:
            addresses = {cell for owner, cell in targets if owner == sheet}
            if _normalized_sheet(current.read(current_sheet[sheet]), addresses) != \
                    _normalized_sheet(original.read(original_sheet[sheet]), addresses):
                return False
    return True


def _source_facts_match(case: dict, seed_sheets: dict) -> bool:
    mapping = CASH_SOURCE_ROWS if case["profile"] == CASH else INTEREST_SOURCE_ROWS
    facts = seed_sheets["Source facts"]
    if (facts.get("A2") is None or facts["A2"].value !=
            "Original filing: " + case["source"]["original_10k_url"]):
        return False
    for period, col in ((0, "B"), (1, "C")):
        for key, row in mapping.items():
            source = case["periods"][period]["facts"].get(key)
            cell = facts.get(f"{col}{row}")
            if source is None:
                if cell is None or cell.value != "n.a." or cell.formula is not None:
                    return False
            elif not _same_saved_number(cell, source["value"]):
                return False
    driver_sheet = "Cash scenario" if case["profile"] == CASH else "Rate scenario"
    driver_keys = (["operating_change", "extra_investing_share", "fx_share_change"]
                   if case["profile"] == CASH else
                   ["rate_change", "income_change", "cash_flow_change"])
    for row, key in enumerate(driver_keys, 5):
        if not _same_saved_number(seed_sheets[driver_sheet].get(f"B{row}"),
                                  case["scenario"][key]):
            return False
    lineage = seed_sheets["Source lineage"]
    accession = case["source"]["accession"]
    labels = CASH_LABELS if case["profile"] == CASH else INTEREST_LABELS
    next_row = 5
    for period in (0, 1):
        for key in mapping:
            item = case["periods"][period]["facts"].get(key)
            if item is None:
                continue
            expected = [
                labels[key], case["periods"][period]["period_end"],
                item["evidence_class"], item.get("tag") or item.get("note_label") or "",
                item.get("ix_id") or "",
                " / ".join(x for x in (item.get("context_ref"), item.get("row_sha256")) if x),
                case["source"]["original_10k_url"], accession,
            ]
            if [_text(lineage.get(f"{col}{next_row}")) for col in "ABCDEFGH"] != expected:
                return False
            next_row += 1
    lineage_rows = [addr for addr in lineage if addr.startswith("H") and addr[1:].isdigit()
                    and int(addr[1:]) >= 5]
    if len(lineage_rows) != next_row - 5:
        return False
    return True


def _check_target_values(candidate: dict, case: dict,
                         source_changes: dict[tuple[int, str], float] | None = None,
                         driver_changes: dict[str, float] | None = None,
                         *, check_cache: bool = False) -> list[str]:
    errors = []
    expected = expected_values(case, source_changes=source_changes,
                               driver_changes=driver_changes)
    override: dict[tuple[str, str], float] = {}
    source_changes = source_changes or {}
    source_rows = CASH_SOURCE_ROWS if case["profile"] == CASH else INTEREST_SOURCE_ROWS
    for (period, metric), value in source_changes.items():
        override[("Source facts", f"{'B' if period == 0 else 'C'}{source_rows[metric]}")] = value
    driver_changes = driver_changes or {}
    driver_sheet = "Cash scenario" if case["profile"] == CASH else "Rate scenario"
    driver_keys = (["operating_change", "extra_investing_share", "fx_share_change"]
                   if case["profile"] == CASH else
                   ["rate_change", "income_change", "cash_flow_change"])
    for row, key in enumerate(driver_keys, 5):
        if key in driver_changes:
            override[(driver_sheet, f"B{row}")] = driver_changes[key]
    evaluator = Evaluator(candidate, override)
    for sheet, addr in sorted(expected):
        cell = candidate.get(sheet, {}).get(addr)
        if cell is None or not cell.formula:
            errors.append(f"missing_target_formula:{sheet}!{addr}")
            continue
        try:
            observed = evaluator.cell(sheet, addr)
            if not _close(observed, expected[(sheet, addr)]):
                errors.append(f"wrong_target_result:{sheet}!{addr}")
            if check_cache and cell.value is not None and not _close(float(cell.value), observed):
                errors.append(f"stale_target_cache:{sheet}!{addr}")
        except Exception as error:
            errors.append(f"target_evaluation_error:{sheet}!{addr}:{type(error).__name__}")
    return errors


def _counterfactuals(case: dict) -> list[tuple[dict, dict]]:
    if case["profile"] == CASH:
        prior_operating = case["periods"][0]["facts"]["operating"]["value"]
        current_operating = case["periods"][1]["facts"]["operating"]["value"]
        current_investing = case["periods"][1]["facts"]["investing"]["value"]
        current_ending = case["periods"][1]["facts"]["ending"]["value"]
        current_restricted = case["periods"][1]["facts"]["restricted"]["value"]
        return [
            ({(0, "operating"): prior_operating + 17.0}, {}),
            ({(1, "operating"): current_operating + 17.0}, {}),
            ({(1, "investing"): current_investing - 11.0}, {}),
            ({(1, "ending"): current_ending + 7.0}, {}),
            ({(1, "restricted"): current_restricted + 4.0}, {}),
            ({}, {"operating_change": case["scenario"]["operating_change"] + 0.035}),
            ({}, {"extra_investing_share": case["scenario"]["extra_investing_share"] + 0.021}),
            ({}, {"fx_share_change": case["scenario"]["fx_share_change"] - 0.011}),
        ]
    gross_first = case["periods"][1]["facts"]["debt_component_1"]["value"]
    income = case["periods"][1]["facts"]["operating_income"]["value"]
    prior_income = case["periods"][0]["facts"]["operating_income"]["value"]
    interest = case["periods"][1]["facts"]["interest_expense_abs"]["value"]
    operating_cash = case["periods"][1]["facts"]["cash_from_operations"]["value"]
    control_key = ("debt_principal_direct" if case["source"]["debt_control_kind"] == "direct_principal"
                   else "debt_carrying")
    control = case["periods"][1]["facts"][control_key]["value"]
    return [
        ({(0, "operating_income"): prior_income + 13.0}, {}),
        ({(1, "operating_income"): income + 21.0}, {}),
        ({(1, "interest_expense_abs"): interest + 5.0}, {}),
        ({(1, "cash_from_operations"): operating_cash + 9.0}, {}),
        ({(1, "debt_component_1"): gross_first + 13.0}, {}),
        ({(1, control_key): control + 7.0}, {}),
        ({}, {"rate_change": case["scenario"]["rate_change"] + 0.003}),
        ({}, {"income_change": case["scenario"]["income_change"] + 0.025}),
        ({}, {"cash_flow_change": case["scenario"]["cash_flow_change"] + 0.03}),
    ]


def verify(candidate_path: Path, seed_path: Path, case_path: Path) -> dict:
    errors: list[str] = []
    case = json.loads(case_path.read_bytes())
    if case.get("schema") != "envloop.sec_four_train_analogue_case.private.v1":
        return {"pass": False, "errors": ["wrong_private_case_schema"]}
    targets = CASH_TARGETS if case["profile"] == CASH else INTEREST_TARGETS
    expected_sheets = CASH_SHEETS if case["profile"] == CASH else INTEREST_SHEETS
    try:
        candidate, candidate_names, candidate_tables, candidate_structure = load_xlsx(candidate_path)
        seed, seed_names, seed_tables, seed_structure = load_xlsx(seed_path)
        if candidate_names != expected_sheets or seed_names != expected_sheets:
            errors.append("sheet_order_or_names_changed")
        if candidate_tables != seed_tables or candidate_structure != seed_structure:
            errors.append("sheet_table_or_structure_changed")
        if not _package_structure_unchanged(candidate_path, seed_path, targets):
            errors.append("workbook_non_target_or_style_structure_changed")
        if not _source_facts_match(case, seed):
            errors.append("seed_facts_or_drivers_not_reviewed_source")
        for sheet in seed_names:
            for addr in set(seed[sheet]) | set(candidate.get(sheet, {})):
                if (sheet, addr) in targets:
                    continue
                old, new = seed[sheet].get(addr), candidate.get(sheet, {}).get(addr)
                if old is None or new is None or old.formula != new.formula:
                    errors.append(f"non_target_cell_changed:{sheet}!{addr}")
                elif old.formula is None and not unchanged_cell(old, new):
                    errors.append(f"non_target_cell_changed:{sheet}!{addr}")
        saved_evaluator = Evaluator(candidate)
        for sheet, cells in candidate.items():
            for addr, cell in cells.items():
                if cell.formula and cell.value is not None:
                    try:
                        if not _close(float(cell.value), saved_evaluator.cell(sheet, addr)):
                            errors.append(f"stale_saved_display_cache:{sheet}!{addr}")
                    except (ValueError, ZeroDivisionError):
                        errors.append(f"invalid_saved_display_formula_or_cache:{sheet}!{addr}")
        if errors:
            return {"pass": False, "errors": errors[:30], "checked_targets": 0}
        errors.extend(_check_target_values(candidate, case, check_cache=True))
        counterfactuals = _counterfactuals(case)
        baseline_expected = expected_values(case)
        witnesses: set[tuple[str, str]] = set()
        for source_change, driver_change in counterfactuals:
            changed_expected = expected_values(case, source_changes=source_change,
                                               driver_changes=driver_change)
            witnesses.update(key for key in targets
                             if not _close(changed_expected[key], baseline_expected[key]))
            errors.extend(_check_target_values(candidate, case,
                source_changes=source_change, driver_changes=driver_change))
        if witnesses != targets:
            errors.append("counterfactual_target_dependency_coverage_incomplete")
        if not errors:
            evaluator = Evaluator(candidate)
            check_last = 8 if case["profile"] == CASH else 7
            for row in range(5, check_last + 1):
                if not _close(evaluator.cell("Checks", f"B{row}"), 0.0):
                    errors.append(f"historical_or_scenario_reconciliation_failed:{row}")
    except Exception as error:
        errors.append(f"verification_error:{type(error).__name__}:{error}")
    return {"pass": not errors, "errors": errors[:30],
            "checked_targets": len(targets),
            "counterfactual_replays": len(_counterfactuals(case)),
            "source_only_offline_train": True,
            "official_excel_web_admission": 0}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate", type=Path)
    ap.add_argument("seed", type=Path)
    ap.add_argument("case", type=Path)
    args = ap.parse_args()
    result = verify(args.candidate, args.seed, args.case)
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
