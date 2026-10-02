"""Publish a field-limited receipt for three real native-GUI development controls."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

if __package__:
    from .source import CATALOG_URL, EXPECTED_SHA256, LICENSE_URL, SOURCE_URL
else:
    from source import CATALOG_URL, EXPECTED_SHA256, LICENSE_URL, SOURCE_URL


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def audit(candidate_inventory: Path, gui_root: Path) -> dict:
    inventory_raw = candidate_inventory.read_bytes()
    inventory = json.loads(inventory_raw)
    if inventory["schema"] != "cua-native-wdi-candidate-inventory-v1" or inventory["counts"] != {
        "train": 20, "selection": 20, "final_candidate": 100
    } or inventory["source_sha256"] != EXPECTED_SHA256:
        raise ValueError("Candidate inventory failed shape/source checks")
    final_rows = [r for r in inventory["tasks"] if r["split"] == "final_candidate"]
    app_counts = {"Calc": sum(r["workflow"].startswith("calc-") for r in final_rows),
                  "Impress": sum(r["workflow"] == "impress-deck" for r in final_rows),
                  "Writer": sum(r["workflow"] == "writer-brief" for r in final_rows)}
    if app_counts != {"Calc": 50, "Impress": 25, "Writer": 25}:
        raise ValueError("Final candidate application mix changed")
    summaries = []
    sandbox_ids = []
    runtime_probes = set()
    for app, workflow in (("Calc", "calc-growth"), ("Impress", "impress-deck"),
                          ("Writer", "writer-brief")):
        trio = {}
        task_id = ("wdi-native-mex-impress-deck-normalized" if app == "Impress"
                   else f"wdi-native-mex-{workflow}")
        prefix = "mex-impress-normalized" if app == "Impress" else f"mex-{app.lower()}"
        for attempt in ("positive", "near-miss", "cold-reset"):
            label = f"{prefix}-{attempt}-" + ("2" if app == "Calc" and attempt == "positive" else "1")
            path = gui_root / label / "receipt.json"
            raw = path.read_bytes()
            receipt = json.loads(raw)
            if receipt["attempt"] != attempt or receipt["task_id"] != task_id:
                raise ValueError("Development task identity or attempt mismatch")
            if receipt.get("kill_returned") is not True or receipt.get("is_running_after_kill") is not False:
                raise ValueError("Desktop termination not verified")
            sandbox_ids.append(receipt["sandbox_id_sha256"])
            runtime_probes.add(receipt["runtime_probe"])
            trio[attempt] = (receipt, raw)
        positive, near, cold = (trio[key][0] for key in ("positive", "near-miss", "cold-reset"))
        if len({positive["input_sha256"], near["input_sha256"], cold["input_sha256"]}) != 1:
            raise ValueError("Development trio inputs differ")
        if positive["status"] != "control_passed" or positive["verifier"]["passed"] is not True:
            raise ValueError("Positive GUI control failed")
        if near["status"] != "control_passed" or near["verifier"]["passed"] is not False:
            raise ValueError("Near-miss GUI control was accepted")
        if near["saved_sha256"] == near["input_sha256"] or positive["saved_sha256"] == positive["input_sha256"]:
            raise ValueError("Actor changes were not saved")
        if cold["status"] != "cold_reset_observed" or cold["restored_state_sha256"] != cold["input_sha256"]:
            raise ValueError("Cold reset did not restore initial bytes")
        summaries.append({
            "application": app, "development_task_id": positive["task_id"],
            "same_input_sha256": positive["input_sha256"],
            "positive_saved_sha256": positive["saved_sha256"],
            "near_miss_saved_sha256": near["saved_sha256"],
            "positive_verifier_passed": True, "near_miss_verifier_passed": False,
            "near_miss_reasons": near["verifier"]["errors"],
            "fresh_cold_reset_sha256": cold["restored_state_sha256"],
            "actor_action_counts": {key: len(trio[key][0]["actor_actions"]) for key in trio},
            "receipt_sha256": {key: digest(trio[key][1]) for key in trio},
            "sandbox_id_sha256": {key: trio[key][0]["sandbox_id_sha256"] for key in trio},
            "screenshots_sha256": {key: {label: val["sha256"] for label, val in trio[key][0]["screenshots"].items()}
                                    for key in trio},
        })
    normalization_raw = (gui_root.parent / "normalized-impress-neutral-3" / "receipt.json").read_bytes()
    normalization = json.loads(normalization_raw)
    if normalization.get("status") != "neutral_save_observed" or normalization.get("is_running_after_kill") is not False:
        raise ValueError("Impress neutral setup was not verified")
    if normalization["normalized_sha256"] != summaries[1]["same_input_sha256"]:
        raise ValueError("Impress development input differs from neutral native save")
    if normalization["sandbox_id_sha256"] in sandbox_ids:
        raise ValueError("Neutral save shared an actor sandbox")
    runtime_probes.add(normalization["runtime_probe"])
    if len(set(sandbox_ids)) != 9 or len(runtime_probes) != 1:
        raise ValueError("Controls did not use nine distinct, version-matched sandboxes")
    return {
        "schema": "cua-native-wdi-original-desktop-development-receipt-v1",
        "checked_date": "2026-09-25", "source": {
            "dataset": "World Development Indicators", "source_url": SOURCE_URL,
            "catalog_url": CATALOG_URL, "license_url": LICENSE_URL,
            "license": "CC BY 4.0", "snapshot_sha256": EXPECTED_SHA256,
            "observation_count": 1050, "country_count": 35,
            "years": "2019–2024", "indicators": 5,
        },
        "candidate_inventory_sha256": digest(inventory_raw),
        "private_split_map_sha256": inventory["private_map_sha256"],
        "candidate_counts": inventory["counts"],
        "final_candidate_application_counts": app_counts,
        "development_controls": summaries,
        "impress_trusted_neutral_save": {
            "original_sha256": normalization["original_sha256"],
            "normalized_sha256": normalization["normalized_sha256"],
            "receipt_sha256": digest(normalization_raw),
            "sandbox_id_sha256": normalization["sandbox_id_sha256"],
        },
        "runtime_probe": next(iter(runtime_probes)),
        "qualified_final_task_count": 0,
        "official_model_attempt_count": 0,
        "scope": "Original WDI-derived LibreOffice content, not OSWorld; three exposed train-only development tasks; candidate generation and controls do not admit any official final identity.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--gui-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.inventory, args.gui_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"candidate_counts": result["candidate_counts"],
                      "dev_controls": len(result["development_controls"]),
                      "qualified_final": 0, "receipt_sha256": digest(args.out.read_bytes())},
                     sort_keys=True))


if __name__ == "__main__":
    main()
