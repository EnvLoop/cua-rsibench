"""Independent OOXML and frozen-SEC oracle for the blind Q4 bridge audit.

The builder is not imported. A private reference workbook is used solely to
identify which seed formulas may be repaired, never as a scoring-value oracle.
"""

from __future__ import annotations

import argparse
import json
from functools import lru_cache
from pathlib import Path

from extract_sec import ISSUERS, METRICS, read_source
from verify_ooxml import Cell, Evaluator, close, load_xlsx, unchanged_cell


SHEETS = ["Board Review", "Historical", "Q4 Bridge", "Drivers", "Forecast", "Raw SEC"]
FLOW_METRICS = ("Revenue", "Operating income", "Operating cash flow", "Capital expenditures")
ALL_METRICS = (*FLOW_METRICS, "Assets", "Liabilities", "Equity")
FY_START = {("Apple", "2023"): "2022-09-25", ("Apple", "2024"): "2023-10-01",
            ("Microsoft", "2023"): "2022-07-01", ("Microsoft", "2024"): "2023-07-01"}
NINE = {"Apple": ("2023-10-01", "2024-06-29", "0000320193-24-000081"),
        "Microsoft": ("2023-07-01", "2024-03-31", "0000950170-24-048288")}
TARGETS = {
    *(("Historical", f"{col}{row}") for row in range(5, 9) for col in "DEFGHIJK"),
    *(("Q4 Bridge", f"{col}{row}") for row in (*range(5, 13), 14, 15) for col in "CDE"),
    *(("Drivers", f"{col}{row}") for row in (5, 6) for col in "BCDE"),
    *(("Forecast", f"{col}{row}") for row in range(5, 9) for col in "CDEFGHI"),
    *(("Board Review", f"{col}{row}") for row in (5, 6) for col in "BCDEFGHI"),
}


@lru_cache(maxsize=None)
def _source_fact(issuer: str, metric: str, *, year: str | None = None, nine: bool = False) -> float:
    spec = ISSUERS[issuer]
    data = read_source(spec)
    if nine:
        start, end, accession = NINE[issuer]
        form = "10-Q"
    else:
        if year is None:
            raise ValueError("annual_year_required")
        start = FY_START[(issuer, year)] if metric in FLOW_METRICS else None
        end, accession, form = spec["periods"][year], spec["filing"], "10-K"
    candidates = [fact for fact in data["facts"]["us-gaap"][METRICS[metric]]["units"]["USD"]
                  if fact.get("start") == start and fact["end"] == end and fact["accn"] == accession
                  and fact["form"] == form]
    if len(candidates) != 1:
        raise ValueError(f"canonical_source_ambiguity:{issuer}:{metric}:{year}:{nine}:{len(candidates)}")
    return float(candidates[0]["val"]) / 1_000_000


def _multiplier(seed: dict[str, dict[str, Cell]], issuer: str, delta: float = 0) -> float:
    address = "F5" if issuer == "Apple" else "F6"
    value = seed["Drivers"].get(address)
    if value is None or value.value is None or value.formula is not None:
        raise ValueError(f"scenario_input_missing:{address}")
    return float(value.value) + (delta if issuer == "Apple" else 0)


def expected_values(seed: dict[str, dict[str, Cell]], *, source_deltas_m: dict[tuple[str, str, str], float] | None = None,
                    scenario_deltas: dict[str, float] | None = None) -> dict[tuple[str, str], float]:
    """Recompute every target without reading the builder or reference values."""
    source_deltas_m = source_deltas_m or {}
    scenario_deltas = scenario_deltas or {}
    out: dict[tuple[str, str], float] = {}
    actuals: dict[tuple[str, str], dict[str, float]] = {}
    for issuer, year, row in (("Apple", "2023", 5), ("Apple", "2024", 6),
                              ("Microsoft", "2023", 7), ("Microsoft", "2024", 8)):
        values = {metric: _source_fact(issuer, metric, year=year) + source_deltas_m.get((issuer, year, metric), 0)
                  for metric in ALL_METRICS}
        actuals[(issuer, year)] = values
        for col, metric in zip("DEFGHIJ", ("Revenue", "Operating income", "Operating cash flow", "Capital expenditures", "Assets", "Liabilities", "Equity")):
            out[("Historical", f"{col}{row}")] = values[metric]
        out[("Historical", f"K{row}")] = values["Assets"] - values["Liabilities"] - values["Equity"]

    q4: dict[str, dict[str, float]] = {}
    for issuer, first, fcf_row in (("Apple", 5, 14), ("Microsoft", 9, 15)):
        annual = actuals[(issuer, "2024")]
        q4[issuer] = {}
        nine_values: dict[str, float] = {}
        for offset, metric in enumerate(("Revenue", "Operating cash flow", "Capital expenditures", "Operating income")):
            nine = _source_fact(issuer, metric, nine=True) + source_deltas_m.get((issuer, "nine", metric), 0)
            nine_values[metric] = nine
            row = first + offset
            out[("Q4 Bridge", f"C{row}")] = nine
            out[("Q4 Bridge", f"D{row}")] = annual[metric]
            out[("Q4 Bridge", f"E{row}")] = annual[metric] - nine
            q4[issuer][metric] = annual[metric] - nine
        for col, value in (("C", nine_values["Operating cash flow"] - nine_values["Capital expenditures"]),
                           ("D", annual["Operating cash flow"] - annual["Capital expenditures"]),
                           ("E", q4[issuer]["Operating cash flow"] - q4[issuer]["Capital expenditures"])):
            out[("Q4 Bridge", f"{col}{fcf_row}")] = value
        q4[issuer]["FCF"] = out[("Q4 Bridge", f"E{fcf_row}")]

    for issuer, driver_row, forecast_25, forecast_26, board_row, historical_row in (
        ("Apple", 5, 5, 6, 5, 6), ("Microsoft", 6, 7, 8, 6, 8)
    ):
        prior, current = actuals[(issuer, "2023")], actuals[(issuer, "2024")]
        growth = current["Revenue"] / prior["Revenue"] - 1
        ocf_ratio = current["Operating cash flow"] / current["Revenue"]
        capex_ratio = current["Capital expenditures"] / current["Revenue"]
        next_growth = growth / 2
        for col, value in zip("BCDE", (growth, ocf_ratio, capex_ratio, next_growth)):
            out[("Drivers", f"{col}{driver_row}")] = value
        multiplier = _multiplier(seed, issuer, scenario_deltas.get(issuer, 0))
        forecast: dict[int, dict[str, float]] = {}
        revenue = current["Revenue"]
        for row, rate in ((forecast_25, growth), (forecast_26, next_growth)):
            prior_revenue = revenue
            revenue = prior_revenue * (1 + rate)
            ocf = revenue * ocf_ratio
            capex = revenue * capex_ratio * multiplier
            fcf = ocf - capex
            op_income = revenue * current["Operating income"] / current["Revenue"]
            for col, value in zip("CDEFGHI", (prior_revenue, revenue, ocf, capex, fcf, op_income, fcf / revenue)):
                out[("Forecast", f"{col}{row}")] = value
            forecast[row] = {"Revenue": revenue, "FCF": fcf}
        board_values = (current["Revenue"], current["Operating cash flow"] - current["Capital expenditures"],
                        q4[issuer]["Revenue"], q4[issuer]["FCF"], q4[issuer]["FCF"] / q4[issuer]["Revenue"],
                        forecast[forecast_26]["Revenue"], forecast[forecast_26]["FCF"],
                        out[("Historical", f"K{historical_row}")])
        for col, value in zip("BCDEFGHI", board_values):
            out[("Board Review", f"{col}{board_row}")] = value
    if set(out) != TARGETS:
        raise ValueError(f"oracle_target_coverage:{len(out)}:{len(TARGETS)}")
    return out


def _raw_reference(sheets: dict[str, dict[str, Cell]], issuer: str, metric: str, start: str, end: str, accession: str) -> tuple[str, str]:
    raw = sheets["Raw SEC"]
    rows = sorted(int(a[1:]) for a in raw if a.startswith("A") and a[1:].isdigit() and int(a[1:]) >= 5)
    matching = []
    for row in rows:
        def text(col: str) -> str | None:
            cell = raw.get(f"{col}{row}")
            return (cell.value or "") if cell else ""
        if (text("B"), text("D"), text("F"), text("G"), text("J"), text("N")) == (issuer, metric, start, end, accession, "USD"):
            matching.append(row)
    if len(matching) != 1:
        raise ValueError(f"raw_reference_ambiguity:{issuer}:{metric}:{len(matching)}")
    return ("Raw SEC", f"O{matching[0]}")


def perturbation_profiles() -> list[tuple[dict[tuple[str, str, str], float], dict[str, float]]]:
    """Two distinct sealed replay vectors cover every canonical input lineage."""
    keys = [(issuer, year, metric) for issuer in ISSUERS for year in ("2023", "2024") for metric in ALL_METRICS]
    keys += [(issuer, "nine", metric) for issuer in ISSUERS for metric in FLOW_METRICS]
    first = {key: float((index + 1) * 17) for index, key in enumerate(keys)}
    second = {key: float(((-1) ** index) * (index * 23 + 41)) for index, key in enumerate(keys)}
    return [(first, {"Apple": 0.05, "Microsoft": 0.07}),
            (second, {"Apple": -0.031, "Microsoft": 0.043})]


def _source_overrides(sheets: dict[str, dict[str, Cell]], seed: dict[str, dict[str, Cell]],
                      deltas_m: dict[tuple[str, str, str], float], scenarios: dict[str, float]) -> dict[tuple[str, str], float]:
    overrides = {}
    for (issuer, period, metric), delta_m in deltas_m.items():
        if period == "nine":
            start, end, accession = NINE[issuer]
        else:
            start = FY_START[(issuer, period)] if metric in FLOW_METRICS else ""
            end, accession = ISSUERS[issuer]["periods"][period], ISSUERS[issuer]["filing"]
        ref = _raw_reference(sheets, issuer, metric, start, end, accession)
        overrides[ref] = float(sheets[ref[0]][ref[1]].value) + delta_m * 1_000_000
    for issuer, delta in scenarios.items():
        overrides[("Drivers", "F5" if issuer == "Apple" else "F6")] = _multiplier(seed, issuer, delta)
    return overrides


def verify(candidate_path: Path, seed_path: Path, reference_path: Path) -> dict:
    errors: list[str] = []
    try:
        candidate, order, tables, structure = load_xlsx(candidate_path)
        seed, seed_order, seed_tables, seed_structure = load_xlsx(seed_path)
        reference, reference_order, reference_tables, reference_structure = load_xlsx(reference_path)
    except Exception as exc:
        return {"pass": False, "errors": [f"invalid_xlsx:{exc}"]}
    if order != SHEETS or seed_order != SHEETS or reference_order != SHEETS:
        errors.append("sheet_order_or_identity_changed")
    if tables != seed_tables or tables != reference_tables or structure != seed_structure or structure != reference_structure:
        errors.append("table_or_sheet_structure_changed")
    allowed_repairs = {key for key in TARGETS if seed.get(key[0], {}).get(key[1], Cell(None, None, None)).formula
                       != reference.get(key[0], {}).get(key[1], Cell(None, None, None)).formula}
    if len(allowed_repairs) != 9:
        errors.append("private_repair_manifest_invalid")
    for sheet in seed_order:
        for addr in set(seed[sheet]) | set(candidate.get(sheet, {})):
            key = (sheet, addr)
            old, new = seed[sheet].get(addr), candidate.get(sheet, {}).get(addr)
            if key in TARGETS:
                if new is None or not new.formula:
                    errors.append(f"missing_formula:{sheet}!{addr}")
                elif key not in allowed_repairs and (old is None or old.formula != new.formula):
                    errors.append(f"previously_correct_formula_changed:{sheet}!{addr}")
                continue
            if old is None or new is None or not unchanged_cell(old, new):
                errors.append(f"non_target_cell_changed:{sheet}!{addr}")
    if errors:
        return {"pass": False, "errors": errors[:30], "checked_targets": len(TARGETS),
                "allowed_repairs": len(allowed_repairs), "repaired_faults": 0, "repair_score": 0.0}
    try:
        cases = [(expected_values(seed), {})]
        for deltas_m, scenarios in perturbation_profiles():
            cases.append((expected_values(seed, source_deltas_m=deltas_m, scenario_deltas=scenarios),
                          _source_overrides(candidate, seed, deltas_m, scenarios)))
        for case_index, (expected, overrides) in enumerate(cases):
            calculator = Evaluator(candidate, overrides)
            for sheet, addr in sorted(TARGETS):
                try:
                    actual = calculator.cell(sheet, addr)
                    if not close(actual, expected[(sheet, addr)]):
                        prefix = "wrong_result" if case_index == 0 else f"dependency_failure_p{case_index}"
                        errors.append(f"{prefix}:{sheet}!{addr}")
                    if case_index == 0:
                        cached = candidate[sheet][addr].value
                        if cached is not None and not close(float(cached), actual):
                            errors.append(f"stale_cache:{sheet}!{addr}")
                except Exception as exc:
                    errors.append(f"evaluation_error_p{case_index}:{sheet}!{addr}:{exc}")
        # Local repair credit isolates each fault from other still-broken cells.
        # The public development task can expose this score; official feedback
        # must remain evaluator-only to avoid an adaptive answer oracle.
        repaired = 0
        for key in allowed_repairs:
            if candidate[key[0]][key[1]].formula == seed[key[0]][key[1]].formula:
                continue
            local_ok = True
            for expected, overrides in cases:
                isolated = dict(overrides)
                isolated.update({other: value for other, value in expected.items() if other != key})
                try:
                    if not close(Evaluator(candidate, isolated).cell(*key), expected[key]):
                        local_ok = False
                        break
                except Exception:
                    local_ok = False
                    break
            repaired += int(local_ok)
    except Exception as exc:
        errors.append(f"verification_error:{exc}")
        repaired = 0
    return {"pass": not errors and repaired == len(allowed_repairs), "errors": errors[:30],
            "checked_targets": len(TARGETS), "allowed_repairs": len(allowed_repairs),
            "repaired_faults": repaired, "repair_score": repaired / len(allowed_repairs) if allowed_repairs else 0.0,
            "private_replay_profiles": len(cases) - 1 if "cases" in locals() else 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    parser.add_argument("seed", type=Path)
    parser.add_argument("reference", type=Path)
    args = parser.parse_args()
    result = verify(args.candidate, args.seed, args.reference)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["pass"] else 1)
