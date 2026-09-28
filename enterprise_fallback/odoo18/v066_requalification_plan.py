"""Prospective 20/20/100 Odoo v0.6.6 GUI control plan, with no live actions.

The plan binds private candidate identities to the post-caret six-cell source
ratification. It grants no campaign, model, or official-final authority. A
separate evaluator must later produce fresh per-ID GUI/SQL/filestore receipts.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat

from . import offline_evidence_audit_v1 as historical


ROOT = Path(__file__).resolve().parents[2]
RATIFICATION_SHA256 = "49f6a047313c4b1c30fbe357677dbf33cb692614d7e273fe57b088e435c46359"
PROFILE = "scale-action-profile-v0.6.6"
PRIVATE_SCHEMA = "envloop-odoo-v066-prospective-gui-requalification-plan-v1"
PUBLIC_SCHEMA = "envloop-odoo-v066-prospective-gui-requalification-public-v1"
HEX = re.compile(r"[0-9a-f]{64}\Z")
COMMON_FILES = {
    "full_action_validator_v06": "src/cursibench/scale_action_contract.py",
    "full_action_extension_v066": "src/cursibench/scale_action_contract_v066.py",
    "minimal_output_v065_dependency": "src/cursibench/scale_action_output_v065.py",
    "minimal_output_v066": "src/cursibench/scale_action_output_v066.py",
    "qwen_vision_proxy": "src/cursibench/scale_vision_proxy.py",
}
ODOO_FILES = (
    "enterprise_fallback/odoo18/odoo_v066_train_adapter.py",
    "enterprise_fallback/odoo18/odoo_native_adapter.py",
    "enterprise_fallback/odoo18/verify.py",
    "enterprise_fallback/odoo18/reset.py",
    "enterprise_fallback/odoo18/gui_controls.py",
    "enterprise_fallback/odoo18/worker_lease.py",
    "enterprise_fallback/odoo18/compose.yaml",
    "enterprise_fallback/odoo18/partition_factory.py",
    "enterprise_fallback/odoo18/hidden_factory.py",
)


class RequalificationPlanError(ValueError):
    pass


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise RequalificationPlanError(reason)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode()


def _private_json(path: Path) -> dict:
    require(path.is_file() and not path.is_symlink() and
            stat.S_IMODE(path.stat().st_mode) & 0o077 == 0 and
            stat.S_IMODE(path.parent.stat().st_mode) & 0o077 == 0,
            "private_ratification_or_world_missing_or_permissive")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RequalificationPlanError("private_json_invalid") from None
    require(type(value) is dict, "private_json_invalid")
    return value


def _ratification(private_path: Path, public_path: Path,
                   expected_sha: str) -> tuple[dict, str]:
    require(type(expected_sha) is str and HEX.fullmatch(expected_sha) is not None,
            "ratification_expected_sha_invalid")
    private = _private_json(private_path)
    raw = private_path.read_bytes()
    require(sha(raw) == expected_sha and
            private.get("schema") == "cua-six-cell-action-profile-v066-ratification-v1" and
            private.get("status") == "ratified_pre_result" and
            private.get("action_profile") == PROFILE and
            private.get("hidden_final_model_attempts_before_ratification") == 0 and
            private.get("base_and_selected_identical") is True,
            "new_six_cell_ratification_invalid")
    public = json.loads(public_path.read_bytes())
    require(type(public) is dict and
            public.get("schema") ==
            "cua-six-cell-v066-caret-code-only-ratification-public-v1" and
            public.get("private_ratification_sha256") == expected_sha and
            public.get("status") == "new_source_bytes_frozen_for_evaluator_controls_only" and
            public.get("qualified_final_tasks") == 0 and
            public.get("official_final_model_results") == 0,
            "new_public_ratification_invalid")
    profiles = private.get("cell_profiles")
    require(type(profiles) is dict and
            set(profiles) == {"powerpoint-web", "excel-web", "desktop-native",
                              "odoo-community", "gitlab", "magento-admin"} and
            public.get("cell_adapter_sha256s") ==
            {cell: profile.get("adapter_sha256") for cell, profile in profiles.items()},
            "six_cell_adapter_roster_changed")
    common = {name: sha((ROOT / relative).read_bytes())
              for name, relative in COMMON_FILES.items()}
    require(private.get("common_source_sha256s") == common and
            public.get("common_source_sha256s") == common and
            all(profile.get("common_source_sha256s") == common
                for profile in profiles.values()),
            "common_v066_action_source_changed")
    adapter_sha = sha((ROOT / ODOO_FILES[0]).read_bytes())
    require(profiles["odoo-community"].get("adapter_sha256") == adapter_sha,
            "odoo_v066_adapter_changed")
    return public, adapter_sha


def build(*, workers_root: Path, public_evidence_dir: Path,
          ratification_private: Path, ratification_public: Path,
          expected_ratification_sha256: str = RATIFICATION_SHA256,
          historical_audit=historical.audit) -> tuple[dict, dict]:
    rat_public, adapter_sha = _ratification(
        ratification_private, ratification_public,
        expected_ratification_sha256)
    _private_historical, public_historical = historical_audit(
        Path(workers_root), Path(public_evidence_dir))
    require(public_historical.get("historical_source_assets_and_packages_rebuilt") == 140 and
            public_historical.get("private_evidence_owner_only_permissions") is True and
            public_historical.get("official_final_tasks_admitted") == 0,
            "historical_world_or_privacy_gate_missing")
    world_root = Path(workers_root)
    baseline_taskset = None
    tasks = {}
    checkpoints = {}
    for split, (manifest_split, per_family) in historical.SPLITS.items():
        private = world_root / split / "private"
        world = _private_json(private / "partition_cases.json")
        manifest = _private_json(private / "task_set_manifest.json")
        checkpoint = _private_json(private / "checkpoint_receipt.json")
        sources = _private_json(private / "source_hashes.json")
        baseline = private / "baseline_snapshot.json"
        require(baseline.is_file() and not baseline.is_symlink() and
                sha(baseline.read_bytes()) == historical.file_digest(baseline),
                "baseline_snapshot_unavailable")
        require(world.get("split") == split and
                len(manifest.get(manifest_split, [])) == 4 * per_family and
                set(sources) == {case["id"] for rows in world["cases"].values()
                                 for case in rows},
                "partition_world_changed")
        if baseline_taskset is None:
            baseline_taskset = manifest
        else:
            require(manifest == baseline_taskset,
                    "three_world_taskset_changed")
        checkpoint_ref = {
            "db_sha256": checkpoint["db_sha256"],
            "filestore_sha256": checkpoint["filestore_sha256"],
            "baseline_snapshot_sha256": sha(baseline.read_bytes()),
            "baseline_filestore_manifest_sha256": historical.file_digest(
                private / "baseline-filestore-manifest.json"),
        }
        checkpoints[split] = checkpoint_ref
        by_id = {case["id"]: case for rows in world["cases"].values()
                 for case in rows}
        records = []
        for row in manifest[manifest_split]:
            case = by_id[row["task_id"]]
            binding = {
                "ratification_sha256": expected_ratification_sha256,
                "action_profile": PROFILE,
                "split": split,
                "task_id": row["task_id"],
                "package_sha256": row["package_sha256"],
                "source_asset_sha256": sources[row["task_id"]],
                "visible_instruction_sha256": sha(case["prompt"].encode()),
                "checkpoint": checkpoint_ref,
                "odoo_adapter_sha256": adapter_sha,
            }
            source_label = (f"Purchase planning note for {case['sku']}"
                            if case["family"] == "inventory" else
                            f"{row['task_id']}-source.pdf")
            records.append({**binding, "family": case["family"],
                            "source_label": source_label,
                            "task_binding_sha256": sha(canonical(binding)),
                            "fresh_v066_gui_proof_status": "pending"})
        require(len(records) == 4 * per_family and
                len({row["task_id"] for row in records}) == len(records),
                "partition_plan_identity_invalid")
        tasks[split] = records
    source_hashes = {path: sha((ROOT / path).read_bytes()) for path in ODOO_FILES}
    pilot = next(row for row in tasks["train"] if row["family"] == "purchase")
    private_plan = {
        "schema": PRIVATE_SCHEMA,
        "status": "planned_no_current_v066_gui_proofs",
        "ratification_sha256": expected_ratification_sha256,
        "ratification_public_sha256": sha(ratification_public.read_bytes()),
        "historical_recomputed_world_audit_sha256":
            sha(canonical(_private_historical)),
        "task_set_manifest_sha256": historical.canonical_digest(baseline_taskset),
        "action_profile": PROFILE,
        "odoo_source_sha256s": source_hashes,
        "pilot_auditor_source_sha256": sha(
            Path(__file__).with_name("v066_requalification_pilot.py").read_bytes()),
        "common_action_source_sha256s": rat_public["common_source_sha256s"],
        "checkpoints": checkpoints,
        "tasks": tasks,
        "pilot": {"split": "train", "task_id": pilot["task_id"],
                  "task_binding_sha256": pilot["task_binding_sha256"]},
        "retry_policy": "manual_new_attempt_only_retain_original_receipts",
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }
    raw = canonical(private_plan)
    public_plan = {
        "schema": PUBLIC_SCHEMA,
        "status": "source_bound_plan_only_no_current_gui_proofs",
        "action_profile": PROFILE,
        "new_six_cell_ratification_sha256": expected_ratification_sha256,
        "private_plan_sha256": sha(raw),
        "task_set_manifest_sha256": private_plan["task_set_manifest_sha256"],
        "candidate_counts": {split: len(rows) for split, rows in tasks.items()},
        "pilot_split": "train",
        "pilot_receipt_present": False,
        "fresh_v066_per_id_gui_controls_qualified": 0,
        "saved_state_reset_no_regression_proofs_qualified": 0,
        "official_final_tasks_admitted": 0,
        "researcher_campaigns": 0,
        "model_attempts": 0,
        "full_six_cell_pre_campaign_witness_present": False,
        "planner_source_sha256": sha(Path(__file__).read_bytes()),
        "pilot_auditor_source_sha256": private_plan["pilot_auditor_source_sha256"],
    }
    return private_plan, public_plan


def write_new(path: Path, value: dict, *, private: bool) -> None:
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True, mode=0o700 if private else 0o755)
    if private:
        require(not parent.is_symlink() and
                stat.S_IMODE(parent.stat().st_mode) & 0o077 == 0,
                "private_plan_parent_permissive")
    raw = canonical(value)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                 0o600 if private else 0o644)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers-root", type=Path, required=True)
    parser.add_argument("--public-evidence-dir", type=Path, required=True)
    parser.add_argument("--ratification-private", type=Path, required=True)
    parser.add_argument("--ratification-public", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    private_result, public_result = build(
        workers_root=args.workers_root,
        public_evidence_dir=args.public_evidence_dir,
        ratification_private=args.ratification_private,
        ratification_public=args.ratification_public)
    write_new(args.private_out, private_result, private=True)
    write_new(args.public_out, public_result, private=False)
    print(json.dumps(public_result, sort_keys=True))
