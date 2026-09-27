"""Re-audit all private GUI-saved artifacts with fair numeric semantics.

This read-only pass does not modify the frozen GUI attempt receipts. It checks
three correct targets in every positive and exactly one semantically wrong
target in every near-miss, using a private counterfactual salt for Calc. The
public output contains only aggregate counts and evidence hashes.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import hmac
import json
from pathlib import Path

if __package__:
    from . import admit
    from .formula_semantics import semantically_equivalent
    from .target_text_semantics import semantically_correct
    from .verify import docx_content, pptx_slide_shapes, xlsx_cells
else:
    import admit
    from formula_semantics import semantically_equivalent
    from target_text_semantics import semantically_correct
    from verify import docx_content, pptx_slide_shapes, xlsx_cells


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _positions(before: list[str], targets: dict[str, str]) -> list[tuple[int, str, str]]:
    positions = [(i, old, targets[old]) for i, old in enumerate(before) if old in targets]
    if len(positions) != 3 or len({old for _, old, _ in positions}) != 3:
        raise ValueError("Three distinct target statements not found")
    return positions


def audit(candidate_root: Path, attempts_root: Path, private_map_path: Path) -> tuple[dict, dict]:
    mapping_raw = private_map_path.read_bytes()
    mapping = json.loads(mapping_raw)
    private_salt = mapping["variant_salt"]
    if not isinstance(private_salt, str) or len(private_salt) < 32:
        raise ValueError("Private semantic perturbation salt missing")
    inventory_raw = (candidate_root / "candidate-inventory.json").read_bytes()
    inventory = json.loads(inventory_raw)
    if (digest(mapping_raw) != inventory.get("private_map_sha256") or
            inventory.get("design_revision") != "v2-distinct-structures"):
        raise ValueError("Candidate inventory/version mismatch")
    gate = admit.audit(candidate_root, attempts_root)
    if (gate["qualified_final_count"], gate["missing_receipt_count"], gate["invalid_receipt_count"]) != (100, 0, 0):
        raise ValueError("All 100 original GUI controls must qualify first")
    rows = [r for r in inventory["tasks"] if r["split"] == "final_candidate"]
    statuses = []
    failures = []
    key = bytes.fromhex(private_salt)
    for row in rows:
        task_id = row["task_id"]
        _, baseline, oracle = admit._package(candidate_root, row)
        attempt_dir = attempts_root / task_id
        ext = ".xlsx" if row["workflow"].startswith("calc-") else ".pptx" if row["workflow"].startswith("impress-") else ".docx"
        positive = (attempt_dir / "positive" / ("saved" + ext)).read_bytes()
        near = (attempt_dir / "near-miss" / ("saved" + ext)).read_bytes()
        if row["workflow"].startswith("calc-"):
            before, good, bad = xlsx_cells(baseline), xlsx_cells(positive), xlsx_cells(near)
            correct = []
            wrong = []
            for address, spec in oracle["targets"].items():
                sheet, cell = address.split("!", 1)
                proposed_good = good[sheet][cell]["formula"]
                proposed_bad = bad[sheet][cell]["formula"]
                if proposed_good is None or proposed_bad is None:
                    raise ValueError("A Calc target lacks a saved live formula")
                correct.append(semantically_equivalent(proposed_good, spec["formula"],
                                                       before, private_salt=private_salt))
                wrong.append(not semantically_equivalent(proposed_bad, spec["formula"],
                                                         before, private_salt=private_salt))
        elif row["workflow"].startswith("impress-"):
            slide = oracle["target_slide"] - 1
            before = pptx_slide_shapes(baseline)[slide]
            good, bad = pptx_slide_shapes(positive)[slide], pptx_slide_shapes(near)[slide]
            positions = _positions(before, oracle["targets"])
            correct = [semantically_correct(good[i], expected) for i, _, expected in positions]
            wrong = [not semantically_correct(bad[i], expected) for i, _, expected in positions]
        else:
            before = docx_content(baseline)["paragraphs"]
            good = docx_content(positive)["paragraphs"]
            bad = docx_content(near)["paragraphs"]
            positions = _positions(before, oracle["targets"])
            correct = [semantically_correct(good[i], expected) for i, _, expected in positions]
            wrong = [not semantically_correct(bad[i], expected) for i, _, expected in positions]
        valid = len(correct) == 3 and all(correct) and sum(wrong) == 1
        if not valid:
            failures.append({"task_id": task_id, "workflow": row["workflow"],
                             "positive_semantic_flags": correct, "near_miss_wrong_flags": wrong})
        statuses.append({"task_id": task_id, "workflow": row["workflow"],
                         "source_groups": row["source_groups"],
                         "opaque_task_ref": hmac.new(key, task_id.encode(), hashlib.sha256).hexdigest(),
                         "input_sha256": digest(baseline),
                         "positive_saved_sha256": digest(positive),
                         "near_miss_saved_sha256": digest(near),
                         "positive_semantic_flags": correct,
                         "near_miss_wrong_flags": wrong,
                         "passed": valid})
    private = {"schema": "cua-native-wdi-saved-semantic-audit-private-v1",
               "candidate_inventory_sha256": digest(inventory_raw),
               "private_map_sha256": digest(mapping_raw),
               "task_count": len(rows), "tasks": statuses, "failures": failures}
    public_rows = sorted(({"opaque_task_ref": r["opaque_task_ref"],
                           "input_sha256": r["input_sha256"],
                           "positive_saved_sha256": r["positive_saved_sha256"],
                           "near_miss_saved_sha256": r["near_miss_saved_sha256"]}
                          for r in statuses), key=lambda item: item["opaque_task_ref"])
    public = {"schema": "cua-native-wdi-saved-semantic-audit-public-v1",
              "checked_date": "2026-09-27",
              "candidate_inventory_sha256": digest(inventory_raw),
              "private_map_sha256": digest(mapping_raw),
              "private_perturbation_salt_sha256": digest(private_salt.encode()),
              "final_task_count": len(rows),
              "application_counts": dict(sorted(Counter("Calc" if r["workflow"].startswith("calc-") else
                                                          "Impress" if r["workflow"].startswith("impress-") else "Writer"
                                                          for r in statuses).items())),
              "source_family_count": len({tuple(r["source_groups"]) for r in statuses}),
              "positive_target_semantics_passed": sum(sum(r["positive_semantic_flags"]) for r in statuses),
              "positive_target_semantics_total": 3 * len(rows),
              "near_miss_exactly_one_semantic_error_task_count": sum(r["passed"] for r in statuses),
              "semantic_failure_task_count": len(failures),
              "saved_artifact_hash_manifest_sha256": digest((json.dumps(public_rows, sort_keys=True) + "\n").encode()),
              "status": "all_private_saved_semantic_checks_passed" if not failures else "semantic_checks_failed",
              "official_full_study_admitted_final_count": 0,
              "official_model_result_count": 0,
              "scope": "Read-only evaluator re-audit of known GUI controls, not a model attempt or campaign result. The semantic guards are not yet frozen in the official scorer."}
    return private, public


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--attempts-root", type=Path, required=True)
    parser.add_argument("--private-map", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.private_out, args.public_out):
        if path.exists():
            raise ValueError("Refusing to overwrite semantic audit evidence")
    private, public = audit(args.candidate_root, args.attempts_root, args.private_map)
    args.private_out.parent.mkdir(parents=True, exist_ok=True)
    args.public_out.parent.mkdir(parents=True, exist_ok=True)
    args.private_out.write_text(json.dumps(private, indent=2, sort_keys=True) + "\n")
    public["private_full_audit_sha256"] = digest(args.private_out.read_bytes())
    args.public_out.write_text(json.dumps(public, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": public["status"],
                      "positive_targets": public["positive_target_semantics_passed"],
                      "near_miss_tasks": public["near_miss_exactly_one_semantic_error_task_count"],
                      "public_receipt_sha256": digest(args.public_out.read_bytes())}, sort_keys=True))
    if private["failures"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
