"""Independently inspect fresh PowerPoint-web artifact controls.

The Office UI, cloud-item identity, and download origin are outside this
offline verifier. Its private, pre-actor oracle is frozen before downloads are
bound to the companion fresh-copy controller. Even a passing artifact audit
never confers GUI admission or official final-task credit by itself.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

try:
    from tools import pptx_title_size_guard as guard
    from tools import stage_office_web_fresh_attempt as controller
except ModuleNotFoundError:  # direct `python tools/...py` invocation
    import pptx_title_size_guard as guard
    import stage_office_web_fresh_attempt as controller

SCHEMA = "office-web-fresh-ppt-artifact-audit-v1"
ORACLE_NAME = "ppt_artifact_oracle.json"
RECEIPT_NAME = "ppt_artifact_audit.json"


def _read_controller(root: Path) -> dict:
    controller.verify_staged(root)
    manifest = json.loads((root / "controller.json").read_text())
    if manifest["cell_id"] != "powerpoint-web":
        raise ValueError("artifact audit only supports the PowerPoint web cell")
    return manifest


def _source(root: Path, manifest: dict) -> Path:
    return controller._slot_path(root, manifest["source_snapshot_path"])


def freeze(root: Path, *, slide_part: str, shape_id: str,
           target_size_pt: float, expected_collateral_part: str) -> dict:
    """Freeze a private task oracle before any candidate artifact is bound."""
    manifest = _read_controller(root)
    oracle_path = root / ORACLE_NAME
    if oracle_path.exists() or manifest.get("downloads") or manifest.get("ppt_artifact_oracle_sha256"):
        raise ValueError("freeze must precede all downloads and may run only once")
    source = _source(root, manifest)
    contract = guard.freeze_contract(source, slide_part, shape_id, target_size_pt,
                                     office_web_normalized=True)
    baseline_check = guard.verify(source, source, contract)
    if baseline_check["status"] != "scored" or baseline_check["target_correct"]:
        raise ValueError("frozen baseline is unreadable or already satisfies the target")
    _, source_parts = guard.package(source)
    if expected_collateral_part not in source_parts:
        raise ValueError("expected collateral package part is absent from the baseline")
    now = datetime.now(timezone.utc).isoformat()
    oracle = {
        "schema": SCHEMA, "frozen_at_utc": now,
        "cell_id": manifest["cell_id"], "task_id": manifest["task_id"],
        "source_sha256": manifest["source_sha256"],
        "target_contract": contract,
        "expected_collateral_part": expected_collateral_part,
        "control_slots": list(controller.SLOTS),
        "boundary": "private artifact oracle, not a cloud provenance or GUI attestation",
    }
    controller.write_private_json(oracle_path, oracle)
    manifest["ppt_artifact_oracle_sha256"] = controller.digest(oracle_path)
    try:
        controller.write_private_json(root / "controller.json", manifest)
    except BaseException:
        oracle_path.unlink(missing_ok=True)
        raise
    return {"status": "frozen_before_download", "source_sha256": manifest["source_sha256"],
            "oracle_sha256": manifest["ppt_artifact_oracle_sha256"],
            "official_final_credit": 0}


def compare_semantic_unchanged(source: Path, artifact: Path) -> dict:
    """Require the complete OOXML package to match except narrow save metadata."""
    try:
        _, before = guard.package(source)
        _, after = guard.package(artifact)
        unexpected = set(before) ^ set(after)
        for name in set(before) & set(after):
            if before[name] == after[name]:
                continue
            if name in guard.OFFICE_DERIVED_PARTS:
                equal = guard.office_derived_part_equal(name, before[name], after[name])
            elif name.endswith((".xml", ".rels")):
                equal = guard.canonical(guard.xml(before[name])) == guard.canonical(guard.xml(after[name]))
            else:
                equal = False
            if not equal:
                unexpected.add(name)
        return {"status": "checked", "semantic_match": not unexpected,
                "unexpected_parts": sorted(unexpected)}
    except (guard.ArtifactUnavailable, OSError, ValueError, TypeError) as error:
        return {"status": "infrastructure_error", "semantic_match": None,
                "error_type": type(error).__name__}


def _oracle(root: Path, manifest: dict) -> dict:
    path = root / ORACLE_NAME
    if not path.is_file() or controller.digest(path) != manifest.get("ppt_artifact_oracle_sha256"):
        raise ValueError("private pre-actor oracle is missing or changed")
    oracle = json.loads(path.read_text())
    if (oracle.get("schema") != SCHEMA or oracle.get("source_sha256") != manifest["source_sha256"]
            or oracle.get("task_id") != manifest["task_id"]
            or oracle.get("target_contract", {}).get("original_sha256") != manifest["source_sha256"]):
        raise ValueError("private oracle does not bind this frozen task and source")
    return oracle


def audit(root: Path) -> dict:
    """Audit all five bound local artifacts, without claiming GUI provenance."""
    manifest = _read_controller(root)
    oracle = _oracle(root, manifest)
    missing = sorted(set(controller.SLOTS) - set(manifest["downloads"]))
    if missing:
        return {"schema": SCHEMA, "status": "incomplete_downloads",
                "missing_slots": missing, "artifact_controls_pass": None,
                "gui_admitted": False, "official_final_credit": 0}
    freeze_time = datetime.fromisoformat(oracle["frozen_at_utc"])
    for slot, record in manifest["downloads"].items():
        if datetime.fromisoformat(record["bound_at_utc"]) <= freeze_time:
            raise ValueError("download was bound before the private oracle was frozen: " + slot)
    source = _source(root, manifest)
    downloads = {slot: controller._slot_path(root, manifest["downloads"][slot]["path"])
                 for slot in controller.SLOTS}
    unchanged = compare_semantic_unchanged(source, downloads["untouched"])
    reset = compare_semantic_unchanged(source, downloads["fresh_reset"])
    contract = oracle["target_contract"]
    positive = guard.verify(source, downloads["positive"], contract)
    partial = guard.verify(source, downloads["partial_negative"], contract)
    collateral = guard.verify(source, downloads["collateral_negative"], contract)
    if (unchanged["status"] != "checked" or reset["status"] != "checked"
            or any(case["status"] != "scored" for case in (positive, partial, collateral))):
        status, passed = "infrastructure_error", None
    else:
        target_pt = contract["target_size_pt"]
        partial_sizes = partial["observed_title_sizes_pt"]
        mixed_partial = any(size is not None and abs(size - target_pt) <= .5 for size in partial_sizes) and any(
            size is None or abs(size - target_pt) > .5 for size in partial_sizes)
        passed = bool(
            unchanged["semantic_match"] and reset["semantic_match"]
            and positive["target_correct"] and positive["preservation_pass"]
            and not partial["target_correct"] and partial["preservation_pass"] and mixed_partial
            and collateral["target_correct"] and not collateral["preservation_pass"]
            and oracle["expected_collateral_part"] in collateral["unexpected_parts"]
        )
        status = "checked"
    result = {
        "schema": SCHEMA, "status": status, "cell_id": manifest["cell_id"],
        "task_id": manifest["task_id"], "source_sha256": manifest["source_sha256"],
        "oracle_sha256": manifest["ppt_artifact_oracle_sha256"],
        "download_sha256": {slot: manifest["downloads"][slot]["sha256"] for slot in controller.SLOTS},
        "controls": {"untouched": unchanged, "positive": positive,
                     "partial_negative": partial, "collateral_negative": collateral,
                     "fresh_reset": reset},
        "artifact_controls_pass": passed,
        "gui_provenance": "unverified_external_browser_trace_required",
        "cloud_item_isolation": "unverified_distinct_item_id_required",
        "gui_admitted": False, "official_final_credit": 0,
    }
    return result


def write_audit(root: Path) -> dict:
    result = audit(root)
    if result["status"] == "incomplete_downloads":
        return result
    destination = root / RECEIPT_NAME
    if destination.exists():
        raise ValueError("artifact audit receipt already exists; never overwrite it")
    controller.write_private_json(destination, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    frozen = actions.add_parser("freeze")
    frozen.add_argument("--root", type=Path, required=True)
    frozen.add_argument("--slide-part", required=True)
    frozen.add_argument("--shape-id", required=True)
    frozen.add_argument("--target-size-pt", type=float, required=True)
    frozen.add_argument("--expected-collateral-part", required=True)
    checked = actions.add_parser("audit")
    checked.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "freeze":
        result = freeze(args.root, slide_part=args.slide_part, shape_id=args.shape_id,
                        target_size_pt=args.target_size_pt,
                        expected_collateral_part=args.expected_collateral_part)
    else:
        result = write_audit(args.root)
    # Full private artifact details remain under the evaluator's ignored work/.
    print(json.dumps({key: result[key] for key in ("status", "official_final_credit")}
                     | {"artifact_controls_pass": result.get("artifact_controls_pass")}))


if __name__ == "__main__":
    main()
