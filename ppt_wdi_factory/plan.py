"""Plan original PowerPoint-web candidates from the pinned WDI source.

All task identities, instructions, exact answers, and artifacts stay in ignored
private storage until the held-out evaluation closes. This is an offline source
factory, not an Office-web admission or model result.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import secrets
from collections import Counter
from pathlib import Path

from native_desktop_factory.source import COUNTRIES, EXPECTED_SHA256, YEARS, country_facts, load

SCHEMA = "ppt-wdi-original-candidates-v1"
COUNTS = {"train": 20, "selection": 20, "final_candidate": 100}
WORKFLOWS = (
    "nominal_output_growth",
    "per_capita_growth",
    "inflation_acceleration",
    "labor_rate_change",
    "population_growth",
    "output_per_person_divergence",
    "price_labor_spread",
    "dual_threshold_review",
)
INDICATORS = {
    "gdp": "NY.GDP.MKTP.CD", "gdp_pc": "NY.GDP.PCAP.CD",
    "inflation": "FP.CPI.TOTL.ZG", "population": "SP.POP.TOTL",
    "unemployment": "SL.UEM.TOTL.ZS",
}


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def keyed(seed: bytes, message: str) -> bytes:
    return hmac.new(seed, message.encode(), hashlib.sha256).digest()


def source_split(seed: bytes, aligned_partition: dict | None = None) -> dict[str, list[str]]:
    if aligned_partition is not None:
        if aligned_partition.get("schema") != "cua-native-wdi-private-map-v1":
            raise ValueError("Only the pinned desktop WDI partition schema may be aligned")
        result = {name: list(aligned_partition[name]) for name in COUNTS}
        combined = [country for rows in result.values() for country in rows]
        if ([len(result[name]) for name in COUNTS] != [5, 5, 25]
                or len(combined) != len(set(combined)) or set(combined) != set(COUNTRIES)):
            raise ValueError("Aligned country map overlaps, is incomplete, or has wrong counts")
        return result
    countries = sorted(COUNTRIES, key=lambda iso: keyed(seed, "country:" + iso))
    return {"train": countries[:5], "selection": countries[5:10],
            "final_candidate": countries[10:]}


def workflow_for(split: str, country_index: int, slot: int) -> str:
    if split == "train":
        return WORKFLOWS[slot]
    if split == "selection":
        return WORKFLOWS[(country_index + slot) % 8]
    return WORKFLOWS[(country_index * 3 + slot * 2) % 8]


def compute(facts: dict, workflow: str) -> dict:
    """Derive from the exact rounded WDI values visible in the source table."""
    v = {year: {
        INDICATORS["gdp"]: round(row[INDICATORS["gdp"]] / 1e9, 1),
        INDICATORS["gdp_pc"]: round(row[INDICATORS["gdp_pc"]], 0),
        INDICATORS["inflation"]: round(row[INDICATORS["inflation"]], 2),
        INDICATORS["population"]: round(row[INDICATORS["population"]] / 1e6, 2),
        INDICATORS["unemployment"]: round(row[INDICATORS["unemployment"]], 2),
    } for year, row in facts["years"].items()}
    y19, y23, y24 = v["2019"], v["2023"], v["2024"]
    gdp_growth = (y24[INDICATORS["gdp"]] / y23[INDICATORS["gdp"]] - 1) * 100
    pc_growth = (y24[INDICATORS["gdp_pc"]] / y23[INDICATORS["gdp_pc"]] - 1) * 100
    inflation_delta = y24[INDICATORS["inflation"]] - y23[INDICATORS["inflation"]]
    labor_delta = y24[INDICATORS["unemployment"]] - y19[INDICATORS["unemployment"]]
    pop_growth = (y24[INDICATORS["population"]] / y19[INDICATORS["population"]] - 1) * 100
    spread = y24[INDICATORS["inflation"]] - y24[INDICATORS["unemployment"]]
    gdp_wrong = (y24[INDICATORS["gdp"]] / v["2022"][INDICATORS["gdp"]] - 1) * 100
    labor_wrong = y24[INDICATORS["unemployment"]] - y23[INDICATORS["unemployment"]]
    reference = {
        "nominal_output_growth": (
            gdp_growth, gdp_wrong, "%", "2024 GDP / 2023 GDP - 1", "2024 GDP / 2022 GDP - 1",
            "GDP (current USD)", "2023–2024", "growth", 3.0,
            "The denominator for an annual GDP change is the immediately preceding year."),
        "per_capita_growth": (
            pc_growth, gdp_growth, "%", "2024 GDP per capita / 2023 GDP per capita - 1",
            "2024 total GDP / 2023 total GDP - 1", "GDP per capita (current USD)", "2023–2024",
            "growth", 3.0, "Use the per-person series, not the total-output series."),
        "inflation_acceleration": (
            inflation_delta, y24[INDICATORS["inflation"]] - v["2022"][INDICATORS["inflation"]],
            "percentage points", "2024 CPI inflation - 2023 CPI inflation",
            "2024 CPI inflation - 2022 CPI inflation", "CPI inflation (annual %)", "2023–2024",
            "delta", 1.0, "Compare the current annual inflation rate to the preceding annual rate."),
        "labor_rate_change": (
            labor_delta, labor_wrong, "percentage points", "2024 unemployment - 2019 unemployment",
            "2024 unemployment - 2023 unemployment", "Unemployment (% of labor force)",
            "2019–2024", "delta", 1.0, "The labor comparison spans 2019 to 2024, in percentage points."),
        "population_growth": (
            pop_growth, (y24[INDICATORS["population"]] / v["2020"][INDICATORS["population"]] - 1) * 100,
            "%", "2024 population / 2019 population - 1", "2024 population / 2020 population - 1",
            "Population (people)", "2019–2024", "growth", 2.0,
            "For the five-year population comparison, 2019 is the base year."),
        "output_per_person_divergence": (
            gdp_growth - pc_growth, gdp_growth - pop_growth,
            "percentage points", "2024 GDP growth - 2024 GDP-per-capita growth",
            "2024 GDP growth - 2019–2024 population growth", "GDP and GDP per capita (current USD)",
            "2023–2024", "gap", 0.5,
            "Subtract the per-person growth rate from the total-output growth rate."),
        "price_labor_spread": (
            spread, y24[INDICATORS["inflation"]] - y23[INDICATORS["unemployment"]],
            "percentage points", "2024 CPI inflation - 2024 unemployment",
            "2024 CPI inflation - 2023 unemployment", "CPI inflation and unemployment (%)",
            "2024", "spread", 2.0, "Both rates in the price–labor spread must refer to 2024."),
        "dual_threshold_review": (
            max(y24[INDICATORS["inflation"]] - 5.0, y24[INDICATORS["unemployment"]] - 6.0),
            min(y24[INDICATORS["inflation"]] - 5.0, y24[INDICATORS["unemployment"]] - 6.0),
            "percentage points", "max(2024 CPI inflation - 5%, 2024 unemployment - 6%)",
            "min(2024 CPI inflation - 5%, 2024 unemployment - 6%)",
            "CPI inflation and unemployment (%)", "2024", "threshold", 0.0,
            "Escalate when either simulated watch threshold is exceeded; use the larger excess."),
    }
    if workflow not in reference:
        raise ValueError("Unknown workflow")
    value, wrong_value, unit, formula, wrong_formula, series, window, kind, threshold, rule = reference[workflow]
    if abs(round(value, 2) - round(wrong_value, 2)) < 0.1:
        stale_labor_year = max(("2019", "2020", "2021", "2022"),
                               key=lambda year: abs(y24[INDICATORS["unemployment"]]
                                                    - v[year][INDICATORS["unemployment"]]))
        fallbacks = {
            "nominal_output_growth": ((y24[INDICATORS["gdp"]] / y19[INDICATORS["gdp"]] - 1) * 100,
                                      "2024 GDP / 2019 GDP - 1"),
            "per_capita_growth": ((y24[INDICATORS["gdp_pc"]] / v["2022"][INDICATORS["gdp_pc"]] - 1) * 100,
                                  "2024 GDP per capita / 2022 GDP per capita - 1"),
            "inflation_acceleration": (y24[INDICATORS["inflation"]] - v["2021"][INDICATORS["inflation"]],
                                       "2024 CPI inflation - 2021 CPI inflation"),
            "labor_rate_change": (y24[INDICATORS["unemployment"]] - v["2021"][INDICATORS["unemployment"]],
                                  "2024 unemployment - 2021 unemployment"),
            "population_growth": ((y24[INDICATORS["population"]] / v["2021"][INDICATORS["population"]] - 1) * 100,
                                  "2024 population / 2021 population - 1"),
            "output_per_person_divergence": (((y24[INDICATORS["gdp"]] /
                                                 y19[INDICATORS["gdp"]] - 1) * 100) - pc_growth,
                                             "2019–2024 GDP growth - 2024 GDP-per-capita growth"),
            "price_labor_spread": (y24[INDICATORS["inflation"]]
                                   - v[stale_labor_year][INDICATORS["unemployment"]],
                                   f"2024 CPI inflation - {stale_labor_year} unemployment"),
            "dual_threshold_review": (max(y23[INDICATORS["inflation"]] - 5.0,
                                          y23[INDICATORS["unemployment"]] - 6.0),
                                      "max(2023 CPI inflation - 5%, 2023 unemployment - 6%)"),
        }
        wrong_value, wrong_formula = fallbacks[workflow]
    if abs(round(value, 2) - round(wrong_value, 2)) < 0.1:
        wrong_value = value + 0.5
        wrong_formula += " (plus a 0.5-point transcription error)"
    if kind == "threshold":
        decision = "Escalate for committee review" if value > 0 else "Routine quarterly monitoring"
        incorrect = "Routine quarterly monitoring" if value > 0 else "Escalate for committee review"
    else:
        decision = "Escalate for committee review" if value >= threshold else "Routine quarterly monitoring"
        incorrect = "Routine quarterly monitoring" if value >= threshold else "Escalate for committee review"
    return {
        "value": round(value, 2), "wrong_value": round(wrong_value, 2),
        "unit": unit, "formula": formula, "wrong_formula": wrong_formula, "rule": rule,
        "series": series,
        "window": window, "decision": decision, "incorrect_decision": incorrect,
        "simulated_threshold": threshold, "workflow_kind": kind,
    }


def chart_series(facts: dict, workflow: str) -> dict:
    if workflow in ("nominal_output_growth",):
        chosen = ("gdp",)
        divisor, precision, unit = 1e9, 1, "USD billions"
    elif workflow in ("per_capita_growth", "output_per_person_divergence"):
        chosen = ("gdp_pc",)
        divisor, precision, unit = 1, 0, "current USD"
    elif workflow == "population_growth":
        chosen = ("population",)
        divisor, precision, unit = 1e6, 2, "millions of people"
    elif workflow in ("price_labor_spread", "dual_threshold_review"):
        chosen = ("inflation", "unemployment")
        divisor, precision, unit = 1, 2, "%"
    elif workflow == "labor_rate_change":
        chosen = ("unemployment",)
        divisor, precision, unit = 1, 2, "%"
    else:
        chosen = ("inflation",)
        divisor, precision, unit = 1, 2, "%"
    names = {"gdp": "GDP", "gdp_pc": "GDP per capita", "population": "Population",
             "inflation": "CPI inflation", "unemployment": "Unemployment"}
    return {"categories": list(YEARS), "unit": unit,
            "series": [{"name": names[key], "values": [round(facts["years"][year][INDICATORS[key]] / divisor, precision)
                                                        for year in YEARS]} for key in chosen]}


def task(seed: bytes, split: str, iso: str, country_index: int, slot: int,
         facts: dict) -> dict:
    workflow = workflow_for(split, country_index, slot)
    calc = compute(facts, workflow)
    task_id = "ppt-wdi-" + keyed(seed, f"task:{split}:{iso}:{slot}").hex()[:16]
    display = f"{calc['value']:+.2f} {calc['unit']}"
    wrong_display = f"{calc['wrong_value']:+.2f} {calc['unit']}"
    heading = f"{facts['name']} | {calc['series']} | {calc['window']}"
    correct = {
        "summary": f"Verified change: {display}",
        "ledger": display,
        "interpretation": f"Use {calc['formula']} for the {calc['window']} review; result {display}.",
        "decision": f"Simulated committee rule: {calc['decision']} ({calc['workflow_kind']} threshold {calc['simulated_threshold']:.1f}).",
    }
    draft = {
        "summary": f"Verified change: {wrong_display}",
        "ledger": wrong_display,
        "interpretation": f"Use {calc['wrong_formula']} for the {calc['window']} review; result {wrong_display}.",
        "decision": f"Simulated committee rule: {calc['incorrect_decision']} ({calc['workflow_kind']} threshold {calc['simulated_threshold']:.1f}).",
    }
    target_keys = (["summary"] if split == "train" else
                   ["summary", "ledger", "interpretation"] if split == "selection" else
                   ["summary", "ledger", "interpretation", "decision"])
    for key in correct:
        if key not in target_keys:
            draft[key] = correct[key]
    actor = (f"In the {facts['name']} monitoring brief, reconcile the flagged {workflow.replace('_', ' ')} "
             f"statements with the WDI evidence table and chart. Correct the marked "
             f"{', '.join(target_keys)} field{'s' if len(target_keys)>1 else ''}; "
             "use the displayed simulated committee rule where applicable. Preserve the other slides, "
             "data, chart, source note, and layout. Save the same deck.")
    return {
        "schema": SCHEMA, "task_id": task_id, "split": split, "source_group": iso,
        "template_group": f"{split}-{workflow}-v1", "entity_group": iso,
        "instance_group": task_id, "workflow": workflow, "country_name": facts["name"],
        "heading": heading, "facts": facts["years"], "chart": chart_series(facts, workflow),
        "calculation": calc, "target_keys": target_keys, "correct": correct, "draft": draft,
        "actor_task": actor, "source_snapshot_sha256": EXPECTED_SHA256,
        "source_license": "World Development Indicators CC BY 4.0; authored analyst simulation",
        "official_final_credit": 0,
    }


def build(seed: bytes, aligned_partition: dict | None = None) -> dict:
    if len(seed) != 32:
        raise ValueError("Seed must be exactly 32 private random bytes")
    source = load()
    split = source_split(seed, aligned_partition)
    sets = {}
    for name, countries in split.items():
        sets[name] = [task(seed, name, iso, i, slot, country_facts(source, iso))
                      for i, iso in enumerate(countries) for slot in range(4)]
    if {name: len(rows) for name, rows in sets.items()} != COUNTS:
        raise ValueError("Unexpected split task counts")
    for i, left in enumerate(COUNTS):
        for right in list(COUNTS)[i + 1:]:
            for field in ("source_group", "template_group", "entity_group", "instance_group"):
                if {row[field] for row in sets[left]} & {row[field] for row in sets[right]}:
                    raise ValueError(f"{field} leaked between {left} and {right}")
    all_ids = [row["task_id"] for rows in sets.values() for row in rows]
    if len(all_ids) != len(set(all_ids)):
        raise ValueError("Duplicate task ID")
    return {"schema": SCHEMA, "source_sha256": EXPECTED_SHA256,
            "seed_commitment_sha256": sha(seed),
            "country_partition_alignment": ("shared_wdi_desktop_private_partition"
                                            if aligned_partition is not None else "independent_private_partition"),
            "sets": sets}


def public_receipt(plan: dict, manifest_sha256: str) -> dict:
    return {"schema": "ppt-wdi-original-offline-inventory-v1",
            "candidate_manifest_sha256": manifest_sha256,
            "source_sha256": plan["source_sha256"],
            "country_partition_alignment": plan["country_partition_alignment"],
            "source_license": "World Development Indicators CC BY 4.0",
            "authored_content": "simulated analyst briefs, mistakes, and committee rules",
            "dependent_target_edits_per_task": {"train": 1, "selection": 3,
                                                "final_candidate": 4},
            "counts": {name: {"candidate_tasks": len(rows),
                               "source_country_families": len({r["source_group"] for r in rows}),
                               "workflow_counts": dict(sorted(Counter(r["workflow"] for r in rows).items()))}
                       for name, rows in plan["sets"].items()},
            "admission": {"office_web_gui_admitted": 0, "official_final_tasks": 0,
                          "model_runs": 0},
            "limitations": ["No task-specific visible-GUI save/download/reset controls yet",
                            "No PowerPoint-web chart/table edit compatibility established",
                            "Country-level source clustering required in final analysis"]}


def write_private(path: Path, data: bytes) -> None:
    if path.exists():
        raise ValueError("Refusing to overwrite private frozen material")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.chmod(0o600)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--public-receipt", type=Path)
    parser.add_argument("--align-country-map", type=Path,
                        help="Private WDI desktop map; align entity splits across cells")
    args = parser.parse_args()
    private = args.private_root.resolve()
    seed_path = private / "seed.private"
    manifest_path = private / "candidate-plan.private.json"
    if seed_path.exists():
        seed = bytes.fromhex(seed_path.read_text().strip())
    else:
        seed = secrets.token_bytes(32)
        write_private(seed_path, (seed.hex() + "\n").encode())
    aligned = json.loads(args.align_country_map.read_bytes()) if args.align_country_map else None
    plan = build(seed, aligned)
    manifest = canonical(plan)
    if manifest_path.exists() and manifest_path.read_bytes() != manifest:
        raise ValueError("Existing private candidate manifest differs")
    if not manifest_path.exists():
        write_private(manifest_path, manifest)
    receipt = public_receipt(plan, sha(manifest))
    if args.public_receipt:
        args.public_receipt.parent.mkdir(parents=True, exist_ok=True)
        args.public_receipt.write_bytes(json.dumps(receipt, sort_keys=True, indent=2).encode() + b"\n")
    print(json.dumps({"candidate_counts": {k: len(v) for k, v in plan["sets"].items()},
                      "candidate_manifest_sha256": sha(manifest), "official_final_credit": 0}))


if __name__ == "__main__":
    main()
