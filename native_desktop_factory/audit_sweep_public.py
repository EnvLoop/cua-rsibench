"""Audit every private desktop GUI receipt and publish aggregate-only evidence."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

if __package__:
    from . import admit
    from .source import EXPECTED_SHA256, CATALOG_URL, LICENSE_URL
else:
    import admit
    from source import EXPECTED_SHA256, CATALOG_URL, LICENSE_URL


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _normalization_index(root: Path) -> dict[str, dict]:
    index = {}
    for path in root.rglob("receipt.json"):
        raw = path.read_bytes()
        try:
            receipt = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if receipt.get("schema") != "cua-native-impress-trusted-normalization-v1":
            continue
        index[digest(raw)] = receipt
    return index


def summarize(candidate_root: Path, attempts_root: Path,
              normalization_root: Path, run_receipts: list[Path]) -> dict:
    inventory_raw = (candidate_root / "candidate-inventory.json").read_bytes()
    inventory = json.loads(inventory_raw)
    if inventory.get("design_revision") != "v2-distinct-structures" or inventory.get("source_sha256") != EXPECTED_SHA256:
        raise ValueError("Wrong candidate source/design")
    gate = admit.audit(candidate_root, attempts_root)
    final = [row for row in inventory["tasks"] if row["split"] == "final_candidate"]
    if len(final) != 100:
        raise ValueError("Final candidate denominator changed")
    index = _normalization_index(normalization_root)
    normalized = [row for row in final if row["workflow"] == "impress-deck" and "normalization" in row]
    for row in normalized:
        ref = row["normalization"]
        receipt = index.get(ref["receipt_sha256"])
        if receipt is None or receipt.get("status") != "neutral_save_observed":
            raise ValueError("Impress normalization receipt missing")
        if receipt.get("is_running_after_kill") is not False or receipt.get("kill_returned") is not True:
            raise ValueError("Impress normalization sandbox cleanup unverified")
        if receipt.get("original_sha256") != ref["original_sha256"] or receipt.get("normalized_sha256") != row["input_sha256"]:
            raise ValueError("Impress normalized bytes differ from candidate")
    if len(normalized) != 25:
        raise ValueError("Not all final Impress candidates normalized")
    run_summaries = []
    for path in run_receipts:
        raw = path.read_bytes()
        record = json.loads(raw)
        if record.get("schema") != "cua-native-wdi-final-gui-sweep-v1" or record.get("dry_run") is not False:
            raise ValueError("Non-actual GUI sweep receipt")
        if record.get("status") not in ("finished_incomplete", "gui_gate_complete"):
            raise ValueError("Sweep receipt still active or uncertain")
        if record.get("candidate_inventory_sha256") != digest(inventory_raw):
            raise ValueError("Sweep used a different candidate inventory")
        run_summaries.append({"receipt_sha256": digest(raw),
                              "planned_task_count": record["planned_task_count"],
                              "planned_new_sandboxes": record["planned_new_sandboxes"],
                              "actual_started_attempts": record["actual_started_attempts"],
                              "lease_seconds": record["caps"]["lease_seconds"],
                              "usd_per_hour_upper": record["caps"]["usd_per_hour_upper"],
                              "reserved_usd_upper": record["actual_reserve_usd_upper"],
                              "task_status_counts": dict(sorted(Counter(row["status"] for row in record["results"]).items()))})
    admissible = {row["task_id"]: row for row in final}
    app_counts = Counter("Calc" if admissible[row["task_id"]]["workflow"].startswith("calc-") else
                         "Impress" if admissible[row["task_id"]]["workflow"].startswith("impress-") else "Writer"
                         for row in gate["admitted"])
    families = {tuple(row["source_groups"]) for row in gate["admitted"]}
    runtime_probes = {row["runtime_probe"] for row in gate["admitted"]}
    if len(runtime_probes) > 1:
        raise ValueError("LibreOffice runtime changed across calibrated tasks")
    sandbox_ids = set()
    resource_shapes = set()
    for row in gate["admitted"]:
        for attempt in admit.ATTEMPTS:
            receipt = json.loads((attempts_root / row["task_id"] / attempt / "receipt.json").read_bytes())
            sandbox_ids.add(receipt["sandbox_id_sha256"])
            if "resource_probe" in receipt:
                probe = receipt["resource_probe"]
                resource_shapes.add((probe["vcpu_visible"], probe["memory_kib_visible"]))
    if len(sandbox_ids) != gate["qualified_final_count"] * 3:
        raise ValueError("A calibrated task reused another task's sandbox")
    if any(cpu > 8 or mem > 8 * 1024 * 1024 for cpu, mem in resource_shapes):
        raise ValueError("Observed Desktop resource shape exceeds priced cap")
    template_counts = dict(sorted(Counter(row["template_group"] for row in final).items()))
    invalid_types = dict(sorted(Counter(row["error_type"] for row in gate["invalid"]).items()))
    return {
        "schema": "cua-native-wdi-private-gui-sweep-aggregate-v1",
        "checked_date": "2026-09-25", "candidate_inventory_sha256": digest(inventory_raw),
        "source_snapshot_sha256": EXPECTED_SHA256,
        "source_catalog_url": CATALOG_URL, "source_license_url": LICENSE_URL,
        "source_license": "CC BY 4.0",
        "candidate_counts": inventory["counts"],
        "final_template_counts": template_counts,
        "final_impress_normalized_count": len(normalized),
        "final_gui_control_passed_count": gate["qualified_final_count"],
        "final_gui_control_missing_count": gate["missing_receipt_count"],
        "final_gui_control_invalid_count": gate["invalid_receipt_count"],
        "invalid_receipt_error_types": invalid_types,
        "calibrated_source_family_count": len(families),
        "calibrated_application_counts": dict(sorted(app_counts.items())),
        "distinct_calibrated_actor_sandboxes": len(sandbox_ids),
        "observed_resource_shapes": [{"vcpu": cpu, "memory_kib": mem} for cpu, mem in sorted(resource_shapes)],
        "libreoffice_runtime_probe": next(iter(runtime_probes)) if runtime_probes else None,
        "sweep_runs": run_summaries,
        "published_8vcpu_8gib_marginal_compute_usd_per_hour": 0.5328,
        "actual_billed_usd": None,
        "billing_note": "Provider invoices and any credits, discounts, or plan fees were not exposed by the SDK receipts; USD values above are reservation estimates, not billed usage.",
        "official_full_study_admitted_final_count": 0,
        "official_model_result_count": 0,
        "status": ("gui_controls_complete_official_gates_pending" if gate["qualified_final_count"] == 100 and gate["invalid_receipt_count"] == 0
                   else "gui_controls_incomplete_official_gates_pending"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--attempts-root", type=Path, required=True)
    parser.add_argument("--normalization-root", type=Path, required=True)
    parser.add_argument("--run-receipt", type=Path, action="append", default=[])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.candidate_root, args.attempts_root,
                       args.normalization_root, args.run_receipt)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"],
                      "gui_passed": result["final_gui_control_passed_count"],
                      "gui_missing": result["final_gui_control_missing_count"],
                      "gui_invalid": result["final_gui_control_invalid_count"],
                      "official_admitted": 0, "receipt_sha256": digest(args.out.read_bytes())}, sort_keys=True))


if __name__ == "__main__":
    main()
