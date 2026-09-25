"""Offline aggregate audit of the separate contract-obligations workflow."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from verify_rpo_candidate import Evaluator, expected_values, load_xlsx, replay, verify


def sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def semantic_hash(path: Path) -> str:
    cells, order, tables, structure = load_xlsx(path)
    payload = {"order": order, "tables": tables, "structure": structure,
               "cells": {sheet: {addr: asdict(c) for addr, c in sorted(rows.items())}
                         for sheet, rows in sorted(cells.items())}}
    return sha(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())


def individually_detectable(case: dict, seed: Path, reference: Path, faults: list[str]) -> bool:
    s, _, _, _ = load_xlsx(seed)
    g, _, _, _ = load_xlsx(reference)
    for key in faults:
        sheet, addr = key.split("!", 1)
        isolated = {name: dict(rows) for name, rows in g.items()}
        isolated[sheet][addr] = s[sheet][addr]
        prof = [(Evaluator(isolated), expected_values(case))]
        for index in (1, 2):
            overrides, sd, sc = replay(case, isolated, index)
            prof.append((Evaluator(isolated, overrides),
                         expected_values(case, source_deltas=sd, scenario_deltas=sc)))
        if not any(abs(calc.cell(sheet, addr) - expected[(sheet, addr)])
                   > max(1e-8, abs(expected[(sheet, addr)]) * 1e-8)
                   for calc, expected in prof):
            return False
    return True


def audit(cases_path: Path, workbooks: Path) -> dict:
    cases = json.loads(cases_path.read_text())
    if len(cases) != 4 or len({c["cik"] for c in cases}) != 4:
        raise ValueError("expected_four_issuer_distinct_cases")
    targets = Counter()
    digest_rows = []
    source_accessions = set()
    for case in cases:
        directory = workbooks / case["case_id"]
        seed, reference, oracle, task = (directory / name for name in
                                         ("actor.xlsx", "reference.xlsx", "private-oracle.json", "task.md"))
        if any(not p.is_file() or not p.stat().st_size for p in (seed, reference, oracle, task)):
            raise ValueError(f"rpo_artifact_missing:{case['case_id']}")
        result = verify(reference, seed, case)
        if not result["pass"] or result["checked_targets"] != 43 or result["counterfactual_profiles"] != 2:
            raise ValueError(f"rpo_reference_failed:{case['case_id']}:{result['errors'][:2]}")
        if verify(seed, seed, case)["pass"]:
            raise ValueError(f"rpo_unsolved_passed:{case['case_id']}")
        private = json.loads(oracle.read_text())
        faults = private["faulted"]
        if len(faults) != 9 or not individually_detectable(case, seed, reference, faults):
            raise ValueError(f"rpo_fault_control_failed:{case['case_id']}")
        targets[case["ticker"]] += 1
        source_accessions.add(case["filing_accession"])
        digest_rows.append((case["case_id"], semantic_hash(seed), semantic_hash(reference),
                            sha(oracle.read_bytes()), sha(task.read_bytes())))
    return {"schema": "sec-rpo-offline-audit-v1", "date": "2026-09-25",
            "status": "public development workflow only; zero hidden or Excel-web admission",
            "workflows": 1, "cases": len(cases), "issuer_families": len(targets),
            "distinct_original_10k_accessions": len(source_accessions),
            "issuers": sorted(targets), "sheets_per_case": 8, "formula_targets_per_case": 43,
            "unmarked_faults_per_case": 9, "positive_reference_passes": 4,
            "unsolved_seed_rejections": 4,
            "each_fault_isolated_detectable_under_baseline_or_two_replays": True,
            "source_snapshot_transport": "read-only SEC proxy with exact prior direct-SEC raw-hash match",
            "semantic_artifact_commitment_sha256": sha(json.dumps(sorted(digest_rows),
                                                             separators=(",", ":")).encode()),
            "official_final_admission": 0, "model_scored_final": 0,
            "limits": ["Only four public source-filing development cases.",
                       "No Microsoft Excel for the web saved/downloaded readback or reset on these cases.",
                       "The scenario parameters are synthetic, not SEC guidance or a cash forecast."]}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cases", type=Path, required=True)
    p.add_argument("--workbooks", type=Path, required=True)
    p.add_argument("--public-out", type=Path, required=True)
    args = p.parse_args()
    result = audit(args.cases, args.workbooks)
    args.public_out.parent.mkdir(parents=True, exist_ok=True)
    args.public_out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"cases": result["cases"], "issuer_families": result["issuer_families"],
                      "positive_reference_passes": result["positive_reference_passes"]}))


if __name__ == "__main__":
    main()
