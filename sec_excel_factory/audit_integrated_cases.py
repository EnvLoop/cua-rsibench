"""Fail-closed offline audit of the filing-pinned Excel candidate pool."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from verify_integrated_candidate import (Evaluator, expected_values, load_xlsx,
                                         override_inputs, verify)


def sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def semantic_hash(path: Path) -> str:
    cells, order, tables, structure = load_xlsx(path)
    value = {
        "order": order, "tables": tables, "structure": structure,
        "cells": {sheet: {addr: asdict(cell) for addr, cell in sorted(rows.items())}
                  for sheet, rows in sorted(cells.items())},
    }
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def fault_detectability(case: dict, seed_path: Path, reference_path: Path, faults: list[str]) -> bool:
    seed, _, _, _ = load_xlsx(seed_path)
    reference, _, _, _ = load_xlsx(reference_path)
    baseline = expected_values(case)
    for key in faults:
        sheet, addr = key.split("!", 1)
        # Isolate one injected fault. Interacting mistakes can coincidentally
        # cancel in the broken seed, hiding an individually substantive fault.
        cells = {name: dict(rows) for name, rows in reference.items()}
        cells[sheet][addr] = seed[sheet][addr]
        profiles = [(Evaluator(cells), baseline)]
        for i in (1, 2):
            overrides, sd, sc = override_inputs(case, cells, i)
            profiles.append((Evaluator(cells, overrides),
                             expected_values(case, source_delta=sd, scenario_delta=sc)))
        if not any(abs(evaluator.cell(sheet, addr) - expected[(sheet, addr)])
                   > max(1e-8, abs(expected[(sheet, addr)]) * 1e-8)
                   for evaluator, expected in profiles):
            return False
    return True


def audit(cases_path: Path, workbooks: Path) -> dict:
    cases = json.loads(cases_path.read_text())
    if len(cases) != 140 or len({c["case_id"] for c in cases}) != 140:
        raise ValueError("incomplete_or_duplicate_case_manifest")
    counts = Counter()
    source_groups = {}
    entity_groups = {}
    template_groups = {}
    fault_signatures = {}
    target_counts = {}
    raw_counts = {}
    actor_semantic_hashes = set()
    artifact_hashes = []
    for case in cases:
        split, case_id = case["split"], case["case_id"]
        root = workbooks / split / case_id
        actor, reference, oracle, task = (root / name for name in
                                           ("actor.xlsx", "reference.xlsx", "private-oracle.json", "task.md"))
        for p in (actor, reference, oracle, task):
            if not p.is_file() or not p.stat().st_size:
                raise ValueError(f"candidate_artifact_missing:{case_id}:{p.name}")
        private = json.loads(oracle.read_text())
        faults = private["faulted"]
        if private["case_id"] != case_id or not 6 <= len(faults) <= 9:
            raise ValueError(f"fault_manifest_invalid:{case_id}")
        if not fault_detectability(case, actor, reference, faults):
            raise ValueError(f"undetectable_injected_fault:{case_id}")
        positive = verify(reference, actor, case)
        unsolved = verify(actor, actor, case)
        if not positive["pass"] or unsolved["pass"]:
            raise ValueError(f"positive_or_unsolved_oracle_failed:{case_id}:{positive['errors'][:2]}")
        if positive["counterfactual_profiles"] != 2:
            raise ValueError(f"counterfactual_profiles_missing:{case_id}")
        counts[split] += 1
        source_groups.setdefault(split, set()).add(case["source_group"])
        entity_groups.setdefault(split, set()).add(case["entity_group"])
        template_groups.setdefault(split, set()).add(case["template_group"])
        fault_signatures.setdefault(split, set()).add(tuple(faults))
        target_counts.setdefault(split, set()).add(positive["checked_targets"])
        raw_counts.setdefault(split, []).append((len(case["source_package"]["annual_rows"]),
                                                  len(case["source_package"]["q3_rows"])))
        actor_hash = semantic_hash(actor)
        if actor_hash in actor_semantic_hashes:
            raise ValueError(f"duplicate_actor_workbook_semantics:{case_id}")
        actor_semantic_hashes.add(actor_hash)
        artifact_hashes.append((case_id, actor_hash, semantic_hash(reference), sha(oracle), sha(task)))
    expected_counts = {"train_candidate": 20, "selection_candidate": 20, "final_candidate": 100}
    if dict(counts) != expected_counts:
        raise ValueError(f"candidate_split_counts:{dict(counts)}")
    accession_owner = {}
    for case in cases:
        for accession in (case["source_package"]["annual_accession"],
                          case["source_package"]["q3_accession"]):
            old = accession_owner.setdefault(accession, case["split"])
            if old != case["split"]:
                raise ValueError("source_filing_leakage_across_splits")
    report = {
        "schema": "sec-integrated-offline-audit-v1",
        "date": "2026-09-25",
        "status": "offline_candidate_only; no official final task or Excel-web admission",
        "source_snapshot_sha256": {
            "AAPL": "73a86c6aedc31f77cac2ea4df5f80f0b3bd7e6eb58bb4e01444fbedf3afb9c43",
            "MSFT": "f8aae2965b20ad0df44bdf7ccbedf797d275b6b8dc030154a7a311361bb7246f",
        },
        "counts": {split: {
            "actor_reference_pairs_built": counts[split],
            "reference_oracle_passes": counts[split],
            "unsolved_actor_rejections": counts[split],
            "injected_faults_each": "6-9",
            "every_injected_fault_detectable_under_baseline_or_two_replays": True,
            "formula_targets_per_workbook": sorted(target_counts[split]),
            "distinct_source_filing_pairs": len(source_groups[split]),
            "distinct_issuer_entities": len(entity_groups[split]),
            "distinct_template_groups": len(template_groups[split]),
            "distinct_fault_sets": len(fault_signatures[split]),
            "annual_source_rows_range": [min(a for a, _ in raw_counts[split]),
                                         max(a for a, _ in raw_counts[split])],
            "q3_source_rows_range": [min(q for _, q in raw_counts[split]),
                                     max(q for _, q in raw_counts[split])],
        } for split in expected_counts},
        "source_filing_accession_split_overlap": 0,
        "actor_workbook_semantic_duplicates": 0,
        "semantic_artifact_integrity_commitment_sha256": sha256(json.dumps(sorted(artifact_hashes),
                                                                     separators=(",", ":")).encode()).hexdigest(),
        "integrity_commitment_is_secrecy": False,
        "individually_excel_web_gui_admitted_final": 0,
        "sealed_hidden_final": 0,
        "model_scored_final": 0,
        "limits": [
            "The final candidate set repeats seven filing pairs from two issuers and one calculation template.",
            "The same issuer identities recur in all splits, and comparative filing facts can repeat values.",
            "The public builder and earlier prototypes expose related source facts and fault shapes.",
            "No fresh Excel-web saved/downloaded readback or reset control was performed for these 140 files.",
        ],
    }
    return report


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cases", type=Path, required=True)
    p.add_argument("--workbooks", type=Path, required=True)
    p.add_argument("--public-out", type=Path, required=True)
    args = p.parse_args()
    result = audit(args.cases, args.workbooks)
    args.public_out.parent.mkdir(parents=True, exist_ok=True)
    args.public_out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "counts": {
        k: v["actor_reference_pairs_built"] for k, v in result["counts"].items()}}, sort_keys=True))


if __name__ == "__main__":
    main()
