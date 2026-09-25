"""Publish only aggregate, answer-free candidate-source evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .plan import canonical, public_receipt, sha


def summarize(private: Path, aligned_map: Path | None = None) -> dict:
    plan_path = private / "candidate-plan.private.json"
    build_path = private / "build-receipt.private.json"
    plan = json.loads(plan_path.read_bytes())
    build = json.loads(build_path.read_bytes())
    expected = [r for split in ("train", "selection", "final_candidate") for r in plan["sets"][split]]
    if build["plan_sha256"] != sha(plan_path.read_bytes()) or len(build["rows"]) != len(expected):
        raise ValueError("Build receipt does not cover all candidates")
    if len(expected) != 140:
        raise ValueError("Expected 140 candidate tasks")
    if plan["country_partition_alignment"] == "shared_wdi_desktop_private_partition":
        if aligned_map is None:
            raise ValueError("Shared WDI partition must be verified against its private map")
        partition = json.loads(aligned_map.read_bytes())
        if partition.get("schema") != "cua-native-wdi-private-map-v1":
            raise ValueError("Wrong aligned partition schema")
        for split in ("train", "selection", "final_candidate"):
            if {row["source_group"] for row in plan["sets"][split]} != set(partition[split]):
                raise ValueError("PPT country split differs from desktop WDI map")
    calibration_counts = {}
    calibration_hashes = []
    for split in ("train", "selection", "final_candidate"):
        passed = 0
        for row in plan["sets"][split]:
            package = private / "packages" / split / row["task_id"]
            deck = package / "source.pptx"
            draft = package / "draft.pptx"
            spec = package / "task.private.json"
            receipt = package / "calibration.private.json"
            validation = private / "packages" / split / "validation" / (row["task_id"] + "-source.pptx.json")
            if not (deck.is_file() and draft.is_file() and spec.is_file()
                    and receipt.is_file() and validation.is_file()):
                raise ValueError("Candidate package or calibration missing")
            record = next((r for r in build["rows"] if r["task_id"] == row["task_id"]), None)
            if (record is None or record["deck_sha256"] != sha(deck.read_bytes())
                    or record["draft_sha256"] != sha(draft.read_bytes())
                    or record["finalizer_receipt_sha256"] != sha(validation.read_bytes())
                    or record["task_sha256"] != sha(spec.read_bytes())
                    or json.loads(spec.read_bytes()) != row):
                raise ValueError("Candidate file differs from frozen build receipt")
            check = json.loads(receipt.read_bytes())
            calibration_hashes.append(sha(receipt.read_bytes()))
            if (check["task_id"] != row["task_id"] or check["source_sha256"] != record["deck_sha256"]
                    or check["offline_controls_pass"] is not True):
                raise ValueError("Offline control not passed for a candidate")
            passed += 1
        calibration_counts[split] = passed
    run_path = private / "calibration-run.private.json"
    run = json.loads(run_path.read_bytes())
    verifier_path = Path(__file__).with_name("verify.py")
    if (run["plan_sha256"] != sha(plan_path.read_bytes())
            or run["verifier_sha256"] != sha(verifier_path.read_bytes())
            or run["calibration_receipts_commitment_sha256"] != sha(canonical(calibration_hashes))
            or run["candidate_count"] != 140 or run["offline_passed"] != 140):
        raise ValueError("Full calibration run is unbound or incomplete")
    result = public_receipt(plan, sha(plan_path.read_bytes()))
    result["build_receipt_sha256"] = sha(build_path.read_bytes())
    result["builder_sha256"] = build["builder_sha256"]
    result["finalizer_sha256"] = build["finalizer_sha256"]
    result["verifier_sha256"] = run["verifier_sha256"]
    result["calibration_run_sha256"] = sha(run_path.read_bytes())
    result["runtime_bundle_version"] = build["runtime_bundle_version"]
    result["country_partition_alignment_verified"] = bool(aligned_map is not None)
    result["offline_controls"] = {
        "candidate_decks_built": len(expected),
        "seven_slide_native_table_chart_sources": len(expected),
        "embedded_chart_workbooks_finalized": len(expected),
        "positive_partial_collateral_chart_cases_passed": calibration_counts,
        "evidence_class": "direct OOXML fixtures, not visible GUI or PowerPoint-web save/readback",
    }
    qa_path = private / "qa-aggregate.private.json"
    if qa_path.is_file():
        qa = json.loads(qa_path.read_bytes())
        if qa != {"candidate_decks": 140, "package_integrity_pass": 140,
                   "layout_geometry_pass": 140, "chart_workbook_contract_pass": 140}:
            raise ValueError("Structural/layout QA is incomplete")
        result["offline_package_qa"] = qa
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--public-receipt", type=Path, required=True)
    parser.add_argument("--align-country-map", type=Path)
    args = parser.parse_args()
    public = summarize(args.private_root.resolve(), args.align_country_map)
    args.public_receipt.parent.mkdir(parents=True, exist_ok=True)
    args.public_receipt.write_bytes(json.dumps(public, sort_keys=True, indent=2).encode() + b"\n")
    print(json.dumps({"built_candidates": public["offline_controls"]["candidate_decks_built"],
                      "offline_controls": public["offline_controls"]["positive_partial_collateral_chart_cases_passed"],
                      "official_final_credit": 0}))


if __name__ == "__main__":
    main()
