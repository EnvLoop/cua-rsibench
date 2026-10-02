"""Aggregate-only audit of two retained Writer search-focus failures."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
from pathlib import Path

if __package__:
    from . import admit
else:
    import admit


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def summarize(candidate_root: Path, attempts_root: Path, private_map: Path,
              archives: list[Path], final_retry: Path, health_probe: Path) -> dict:
    if len(archives) != 2:
        raise ValueError("Expected both preserved failed Writer near-misses")
    records = []
    ids = set()
    for path in archives:
        raw = path.read_bytes()
        item = json.loads(raw)
        if item.get("schema") != "cua-native-writer-find-focus-recovery-v1" or item.get("status") != "failed_gui_control_archived_pending_one_corrected_retry":
            raise ValueError("Writer failure archive not verified")
        ids.add(item["private_task_id"])
        original = attempts_root / item["archive_relative"]
        if digest((original / "receipt.json").read_bytes()) != item["original_receipt_sha256"] or digest((original / "saved.docx").read_bytes()) != item["original_saved_sha256"]:
            raise ValueError("Original Writer failed bytes changed")
        records.append({"archive_ledger_sha256": digest(raw),
                        "failed_receipt_sha256": item["original_receipt_sha256"],
                        "failed_saved_docx_sha256": item["original_saved_sha256"]})
    if len(ids) != 1:
        raise ValueError("Writer archives belong to different private tasks")
    task_id = next(iter(ids))
    retry_raw = final_retry.read_bytes()
    run = json.loads(retry_raw)
    if run.get("schema") != "cua-native-wdi-final-gui-sweep-v1" or run.get("status") != "gui_gate_complete":
        raise ValueError("Final Writer retry did not complete the GUI gate")
    results = [row for row in run["results"] if row["task_id"] == task_id]
    if len(results) != 1 or results[0]["status"] != "gui_controls_passed":
        raise ValueError("Fresh Writer near-miss did not pass")
    health_raw = health_probe.read_bytes()
    health = json.loads(health_raw)
    if health.get("ready_to_resume_paid_gui_dispatch") is not True or run.get("health_probe_sha256") != digest(health_raw):
        raise ValueError("Retry did not bind a fresh healthy Desktop")
    row = json.loads((candidate_root / "final_candidate" / task_id / "package.json").read_bytes())
    accepted = admit.admit_one(candidate_root, attempts_root, row)
    mapping = json.loads(private_map.read_bytes())
    key = bytes.fromhex(mapping["variant_salt"])
    return {"schema": "cua-native-writer-find-focus-public-recovery-v1",
            "checked_date": "2026-09-27",
            "opaque_task_ref": hmac.new(key, task_id.encode(), hashlib.sha256).hexdigest(),
            "preserved_failed_near_miss_count": len(records),
            "preserved_failures": sorted(records, key=lambda item: item["archive_ledger_sha256"]),
            "separate_health_probe_sha256": digest(health_raw),
            "fresh_retry_run_receipt_sha256": digest(retry_raw),
            "fresh_near_miss_receipt_sha256": accepted["attempt_receipt_sha256"]["near-miss"],
            "fresh_near_miss_result": "exactly_one_target_error_no_collateral_change",
            "classification": "evaluator_native_GUI_focus_failures_not_model_failures",
            "official_full_study_admitted_final_count": 0,
            "official_model_result_count": 0,
            "note": "Two prior Ctrl+F/Ctrl+H GUI scripts altered non-target content and remain independently rejected; each was archived before one fresh guarded per-statement Find-and-Replace control completed the GUI gate."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--attempts-root", type=Path, required=True)
    parser.add_argument("--private-map", type=Path, required=True)
    parser.add_argument("--archive", type=Path, action="append", required=True)
    parser.add_argument("--final-retry", type=Path, required=True)
    parser.add_argument("--health-probe", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Refusing to overwrite Writer public recovery audit")
    result = summarize(args.candidate_root, args.attempts_root,
                       args.private_map, args.archive, args.final_retry,
                       args.health_probe)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"classification": result["classification"],
                      "preserved_failures": result["preserved_failed_near_miss_count"],
                      "receipt_sha256": digest(args.out.read_bytes())}, sort_keys=True))


if __name__ == "__main__":
    main()
