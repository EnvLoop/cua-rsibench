"""Offline receipt for the tax-provision and cash-tax development workflow."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from verify_tax_candidate import Evaluator, expected_values, load_xlsx, replay, verify


def sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def semantic_hash(path: Path) -> str:
    cells, order, tables, structure = load_xlsx(path)
    payload = {"order": order, "tables": tables, "structure": structure,
               "cells": {sheet: {addr: asdict(c) for addr, c in sorted(rows.items())}
                         for sheet, rows in sorted(cells.items())}}
    return sha(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())


def each_fault_detected(case: dict, seed: Path, reference: Path, faults: list[str]) -> bool:
    s, _, _, _ = load_xlsx(seed)
    g, _, _, _ = load_xlsx(reference)
    for key in faults:
        sheet, addr = key.split("!", 1)
        isolated = {name: dict(rows) for name, rows in g.items()}
        isolated[sheet][addr] = s[sheet][addr]
        profiles = [(Evaluator(isolated), expected_values(case))]
        for index in (1, 2):
            overrides, sd, sc = replay(case, isolated, index)
            profiles.append((Evaluator(isolated, overrides),
                             expected_values(case, source_deltas=sd, scenario_deltas=sc)))
        if not any(abs(calc.cell(sheet, addr) - expected[(sheet, addr)])
                   > max(1e-8, abs(expected[(sheet, addr)]) * 1e-8)
                   for calc, expected in profiles):
            return False
    return True


def audit(cases_path: Path, workbooks: Path) -> dict:
    cases = json.loads(cases_path.read_text())
    if len(cases) != 3 or len({c["cik"] for c in cases}) != 3:
        raise ValueError("expected_three_issuer_distinct_cases")
    rows = []
    for case in cases:
        directory = workbooks / case["case_id"]
        seed, reference, oracle, task = (directory / name for name in
                                         ("actor.xlsx", "reference.xlsx", "private-oracle.json", "task.md"))
        if any(not p.is_file() or not p.stat().st_size for p in (seed, reference, oracle, task)):
            raise ValueError(f"tax_artifact_missing:{case['case_id']}")
        result = verify(reference, seed, case)
        if not result["pass"] or result["checked_targets"] != 46 or result["counterfactual_profiles"] != 2:
            raise ValueError(f"tax_reference_failed:{case['case_id']}:{result['errors'][:2]}")
        if verify(seed, seed, case)["pass"]:
            raise ValueError(f"tax_unsolved_passed:{case['case_id']}")
        faults = json.loads(oracle.read_text())["faulted"]
        if len(faults) != 9 or not each_fault_detected(case, seed, reference, faults):
            raise ValueError(f"tax_fault_control_failed:{case['case_id']}")
        rows.append((case["case_id"], semantic_hash(seed), semantic_hash(reference),
                     sha(oracle.read_bytes()), sha(task.read_bytes())))
    return {"schema": "sec-tax-offline-audit-v1", "date": "2026-09-25",
            "status": "public development workflow only; zero hidden or Excel-web admission",
            "workflows": 1, "cases": 3, "distinct_issuer_families": 3,
            "distinct_original_10k_accessions": 3,
            "issuers": sorted(c["ticker"] for c in cases),
            "sheets_per_case": 9, "formula_targets_per_case": 46,
            "unmarked_faults_per_case": 9, "positive_reference_passes": 3,
            "unsolved_seed_rejections": 3,
            "every_fault_detected_in_isolation_under_baseline_or_two_replays": True,
            "source_raw_status": "exact prior direct-SEC companyfacts SHA-256 per issuer",
            "semantic_artifact_commitment_sha256": sha(json.dumps(sorted(rows),
                                                             separators=(",", ":")).encode()),
            "official_final_admission": 0, "model_scored_final": 0,
            "limits": ["Cash paid, accrual provision, and deferred-tax-asset movement have different accounting bases.",
                       "The synthetic rate/income stress is not SEC guidance or tax advice.",
                       "No Microsoft Excel for the web save/download/readback or reset on these cases."]}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cases", type=Path, required=True)
    p.add_argument("--workbooks", type=Path, required=True)
    p.add_argument("--public-out", type=Path, required=True)
    args = p.parse_args()
    result = audit(args.cases, args.workbooks)
    args.public_out.parent.mkdir(parents=True, exist_ok=True)
    args.public_out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"cases": result["cases"], "positive_reference_passes": result["positive_reference_passes"]}))


if __name__ == "__main__":
    main()
