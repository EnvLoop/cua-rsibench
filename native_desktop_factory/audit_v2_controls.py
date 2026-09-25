"""Create a non-leaking public summary of private v2 final GUI controls."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import hmac
import json
from pathlib import Path

if __package__:
    from . import admit, factory as base
    from .source import EXPECTED_SHA256
else:
    import admit
    import factory as base
    from source import EXPECTED_SHA256


def summarize(candidate_root: Path, attempts_root: Path, private_map_path: Path) -> dict:
    inventory_raw = (candidate_root / "candidate-inventory.json").read_bytes()
    inventory = json.loads(inventory_raw)
    if inventory.get("design_revision") != "v2-distinct-structures" or inventory.get("source_sha256") != EXPECTED_SHA256:
        raise ValueError("Not the pinned v2 native task inventory")
    private_map = json.loads(private_map_path.read_bytes())
    base.validate_private_map(private_map)
    if base.digest(base.json_bytes(private_map)) != inventory["private_map_sha256"]:
        raise ValueError("Private map changed after candidate generation")
    gate = admit.audit(candidate_root, attempts_root)
    if gate["invalid_receipt_count"]:
        raise ValueError("Invalid final GUI receipts must be resolved before reporting")
    key = bytes.fromhex(private_map["variant_salt"])
    rows = {row["task_id"]: row for row in inventory["tasks"]}
    statuses = []
    sandbox_ids = set()
    for evidence in gate["admitted"]:
        task_id = evidence["task_id"]
        row = rows[task_id]
        observations = {}
        for attempt in admit.ATTEMPTS:
            receipt_path = attempts_root / task_id / attempt / "receipt.json"
            raw = receipt_path.read_bytes()
            receipt = json.loads(raw)
            if base.digest(raw) != evidence["attempt_receipt_sha256"][attempt]:
                raise ValueError("GUI receipt changed after admission audit")
            sid = receipt["sandbox_id_sha256"]
            if sid in sandbox_ids:
                raise ValueError("Fresh sandbox identity reused across tasks")
            sandbox_ids.add(sid)
            observations[attempt] = {
                "receipt_sha256": base.digest(raw),
                "saved_sha256": receipt.get("saved_sha256"),
                "independent_verifier_passed": receipt.get("verifier", {}).get("passed"),
                "cold_reset_sha256": receipt.get("restored_state_sha256"),
                "sandbox_stopped": receipt.get("is_running_after_kill") is False,
            }
        statuses.append({
            "opaque_task_ref": hmac.new(key, task_id.encode(), hashlib.sha256).hexdigest(),
            "application": ("Calc" if row["workflow"].startswith("calc-") else
                            "Impress" if row["workflow"].startswith("impress-") else "Writer"),
            "package_sha256": row["package_sha256"],
            "input_sha256": row["input_sha256"],
            "normalization_receipt_sha256": row.get("normalization", {}).get("receipt_sha256"),
            "attempts": observations,
        })
    final = [r for r in inventory["tasks"] if r["split"] == "final_candidate"]
    families = {tuple(row["source_groups"]) for row in final if row["task_id"] in {x["task_id"] for x in gate["admitted"]}}
    normalized = sum("normalization" in row for row in final if row["workflow"] == "impress-deck")
    return {
        "schema": "cua-native-wdi-v2-final-gui-calibration-summary-v1",
        "checked_date": "2026-09-25", "source_snapshot_sha256": EXPECTED_SHA256,
        "candidate_inventory_sha256": base.digest(inventory_raw),
        "private_map_sha256": inventory["private_map_sha256"],
        "candidate_counts": inventory["counts"],
        "final_candidate_applications": {"Calc": 50, "Impress": 25, "Writer": 25},
        "source_family_count_final": 25,
        "final_gui_control_passed_count": gate["qualified_final_count"],
        "final_gui_control_source_family_count": len(families),
        "final_gui_control_application_counts": dict(sorted(Counter(x["application"] for x in statuses).items())),
        "final_gui_control_missing_count": gate["missing_receipt_count"],
        "final_gui_control_invalid_count": gate["invalid_receipt_count"],
        "normalized_final_impress_candidate_count": normalized,
        "distinct_actor_control_sandbox_count": len(sandbox_ids),
        "calibrated_tasks": sorted(statuses, key=lambda x: x["opaque_task_ref"]),
        "official_full_study_admitted_final_count": 0,
        "official_model_result_count": 0,
        "scope": "Private per-ID evaluator calibrations only; no Qwen model attempts, 96 candidate GUI trios absent, full image/profile and study action contract not frozen.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--attempts-root", type=Path, required=True)
    parser.add_argument("--private-map", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.candidate_root, args.attempts_root, args.private_map)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"gui_control_passed": result["final_gui_control_passed_count"],
                      "gui_control_missing": result["final_gui_control_missing_count"],
                      "source_families": result["final_gui_control_source_family_count"],
                      "official_admitted": 0, "receipt_sha256": base.digest(args.out.read_bytes())},
                     sort_keys=True))


if __name__ == "__main__":
    main()
