"""Offline source freeze and split-local 19/20/100 Odoo v0.6.6 control plans.

No provider, Docker, browser or model call. Public plans contain counts/hashes
only; split-local private plans contain exactly one remaining-train, selection, or final roster.
"""

from __future__ import annotations

from hashlib import sha256
from importlib import metadata
import json
import os
from pathlib import Path
import stat
import sys


ROOT = Path(__file__).resolve().parents[1]
RATIFICATION_SHA = "49f6a047313c4b1c30fbe357677dbf33cb692614d7e273fe57b088e435c46359"
SOURCE_FREEZE_SCHEMA = "envloop-odoo-v066-scale-gui-source-freeze-v1"
OLD_LEASE_FREEZE_SHA256 = "f32a309bffddc411e8c317e23b322a7707bedc27e64f20b14c5be2fefbc8179c"
EXACT_RETURN_AMENDMENT = "exact-frame-return-2026-09-28"
PRIVATE_PLAN_SCHEMA = "envloop-odoo-v066-split-gui-control-plan-v1"
PUBLIC_PLAN_SCHEMA = "envloop-odoo-v066-split-gui-control-plan-public-v1"
CASE_SCHEMA = "envloop-odoo-v066-split-gui-case-control-v1"
BATCH_SCHEMA = "envloop-odoo-v066-split-gui-batch-v1"
SPLITS = {"train": ("train", 19, 5, 20),
          "selection": ("selection", 20, 5, 20),
          "official_hidden": ("official", 100, 25, 100)}
FAMILIES = ("purchase", "inventory", "sales", "crm")
SOURCE_FILES = (
    "tools/odoo_v066_scale_protocol_v1.py",
    "tools/odoo_v066_scale_recipes_v1.py",
    "tools/odoo_v066_scale_controller_v1.py",
    "tools/odoo_v066_scale_audit_v1.py",
    "tools/audit_odoo_v066_selection_flicker_v1.py",
    "tools/audit_odoo_v066_inline_lease_incident_v1.py",
    "tools/prepare_odoo_v066_lease_timing_adoption_v1.py",
    "tools/record_odoo_v066_train_gui_v1.py",
    "enterprise_fallback/odoo18/odoo_v066_train_adapter.py",
    "enterprise_fallback/odoo18/odoo_v066_scale_exact_return_adapter.py",
    "enterprise_fallback/odoo18/odoo_native_adapter.py",
    "enterprise_fallback/odoo18/verify.py",
    "enterprise_fallback/odoo18/reset.py",
    "enterprise_fallback/odoo18/gui_controls.py",
    "enterprise_fallback/odoo18/worker_lease.py",
    "enterprise_fallback/odoo18/compose.yaml",
    "enterprise_fallback/odoo18/partition_factory.py",
    "enterprise_fallback/odoo18/hidden_factory.py",
    "src/cursibench/scale_action_contract.py",
    "src/cursibench/scale_action_contract_v066.py",
    "src/cursibench/scale_action_output_v066.py",
    "src/cursibench/scale_vision_proxy.py",
)


class ScaleProtocolError(ValueError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ScaleProtocolError(code)


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode()


def _private(path: Path, *, directory: bool = False) -> None:
    require(not path.is_symlink() and
            (path.is_dir() if directory else path.is_file()) and
            stat.S_IMODE(path.stat().st_mode) & 0o077 == 0,
            "private_scale_path_missing_or_permissive")


def private_json(path: Path) -> dict:
    _private(path)
    require(path.stat().st_size <= 16_000_000, "private_scale_json_oversized")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ScaleProtocolError("private_scale_json_invalid") from None
    require(type(value) is dict, "private_scale_json_invalid")
    return value


def public_json(path: Path) -> dict:
    require(path.is_file() and not path.is_symlink(),
            "public_scale_reference_missing")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ScaleProtocolError("public_scale_json_invalid") from None
    require(type(value) is dict, "public_scale_json_invalid")
    return value


def current_source_hashes() -> dict[str, str]:
    return {relative: digest((ROOT / relative).read_bytes())
            for relative in SOURCE_FILES}


def host_runtime() -> dict[str, str]:
    return {"python": ".".join(map(str, sys.version_info[:3])),
            "playwright": metadata.version("playwright"),
            "Pillow": metadata.version("Pillow")}


def validate_source_freeze(path: Path) -> tuple[dict, str]:
    value = public_json(path)
    raw = path.read_bytes()
    require(value.get("schema") == SOURCE_FREEZE_SCHEMA and
            value.get("ratification_sha256") == RATIFICATION_SHA and
            value.get("official_final_tasks_admitted") == 0 and
            value.get("model_attempts") == 0,
            "scale_source_freeze_changed_or_nonzero")
    if value.get("status") == "frozen_after_pre_result_lease_audit_timing_amendment":
        # Historical batches are read-only auditable under their immutable
        # source freeze. This branch must never authorize a current dispatch.
        require(digest(raw) == OLD_LEASE_FREEZE_SHA256 and
                value.get("train_raw_complete_before_new_freeze") == 1 and
                value.get("train_case_reclassified_before_new_freeze") is False and
                value.get("selection_gui_controls_before_freeze") == 0 and
                value.get("final_gui_controls_before_freeze") == 0,
                "scale_historical_source_freeze_changed")
    else:
        require(value.get("status") ==
                "frozen_after_selection_exact_frame_return_amendment" and
                value.get("frame_guard_amendment") == EXACT_RETURN_AMENDMENT and
                value.get("old_source_freeze_sha256") ==
                OLD_LEASE_FREEZE_SHA256 and
                value.get("selection_failure_public_sha256") == digest((
                    ROOT / "docs/evidence/odoo-v066-selection-first-exact-frame-flicker-incident-2026-09-28.json"
                ).read_bytes()) and
                value.get("source_sha256s") == current_source_hashes() and
                value.get("host_runtime") == host_runtime() and
                value.get("accepted_train_pilot_count") == 1 and
                value.get("retained_selection_failed_controls_before_freeze") == 1 and
                value.get("official_final_gui_controls_before_freeze") == 0,
                "scale_exact_return_source_freeze_changed_or_nonzero")
    return value, digest(raw)


def _worker_split(worker_dir: Path, split: str) -> Path:
    worker = Path(worker_dir).resolve()
    require(split in SPLITS and worker.name == split and
            not worker.is_symlink(), "wrong_original_odoo_worker_split")
    private = worker / "private"
    _private(private, directory=True)
    env = worker / ".env"
    _private(env)
    safe_fields = dict(line.split("=", 1) for line in env.read_text().splitlines()
                       if line.startswith("ODOO_PARTITION="))
    require(safe_fields.get("ODOO_PARTITION") == split,
            "odoo_worker_partition_config_changed")
    return private


def build_split_plan(*, split: str, worker_dir: Path,
                     full_private_plan: Path, full_public_plan: Path,
                     source_freeze_path: Path,
                     train_pilot_public_path: Path) -> tuple[dict, dict]:
    source_freeze, source_freeze_sha = validate_source_freeze(source_freeze_path)
    require(split in SPLITS, "unknown_odoo_scale_split")
    key, count, per_family, world_count = SPLITS[split]
    private = _worker_split(worker_dir, split)
    full = private_json(full_private_plan)
    full_public = public_json(full_public_plan)
    train_pilot = public_json(train_pilot_public_path)
    require(full.get("schema") ==
            "envloop-odoo-v066-prospective-gui-requalification-plan-v1" and
            full.get("ratification_sha256") == RATIFICATION_SHA and
            full_public.get("private_plan_sha256") ==
            digest(full_private_plan.read_bytes()) and
            full_public.get("candidate_counts") ==
            {"train": 20, "selection": 20, "official_hidden": 100} and
            train_pilot.get("schema") ==
            "envloop-odoo-v066-gui-control-pilot-audit-v1" and
            train_pilot.get("fresh_train_candidate_controls_qualified") == 1 and
            train_pilot.get("official_final_tasks_admitted") == 0 and
            source_freeze.get("train_pilot_public_sha256") ==
            digest(train_pilot_public_path.read_bytes()),
            "scale_plan_train_provenance_unbound")
    source = private_json(private / "source_hashes.json")
    world = private_json(private / "partition_cases.json")
    checkpoint = private_json(private / "checkpoint_receipt.json")
    require(digest((private / "baseline.pgcustom").read_bytes()) ==
            checkpoint.get("db_sha256") and
            digest((private / "baseline-filestore.tgz").read_bytes()) ==
            checkpoint.get("filestore_sha256"),
            "scale_task_source_or_checkpoint_changed")
    original_rows = full.get("tasks", {}).get(split, [])
    if split == "train":
        require(len(original_rows) == 20 and
                full.get("pilot", {}).get("split") == "train",
                "remaining_train_pilot_exclusion_missing")
        original_rows = [row for row in original_rows
                         if row["task_id"] != full["pilot"]["task_id"]]
    require(world.get("split") == split and
            len(original_rows) == count and
            len(source) == world_count,
            "scale_private_world_count_changed")
    from enterprise_fallback.odoo18.partition_factory import source_asset
    by_id = {case["id"]: case for family in FAMILIES
             for case in world["cases"][family]}
    require(len(by_id) == world_count and
            {family: len(world["cases"][family]) for family in FAMILIES} ==
            {family: per_family for family in FAMILIES},
            "scale_world_family_count_changed")
    rows = []
    for row in original_rows:
        case = by_id.get(row["task_id"])
        require(case is not None and case["family"] == row["family"],
                "scale_case_family_binding_changed")
        asset = source_asset(case, world)
        package_sha = digest(json.dumps(case, sort_keys=True).encode() +
                             b"\n" + asset)
        require(package_sha == row["package_sha256"] and
                digest(asset) == row["source_asset_sha256"] ==
                source[row["task_id"]] and
                digest(case["prompt"].encode()) ==
                row["visible_instruction_sha256"] and
                row["checkpoint"]["db_sha256"] ==
                checkpoint["db_sha256"] and
                row["checkpoint"]["filestore_sha256"] ==
                checkpoint["filestore_sha256"],
                "scale_task_source_or_checkpoint_changed")
        rows.append(row)
    require(len({row["task_id"] for row in rows}) == count,
            "scale_task_identity_duplicate")
    plan = {
        "schema": PRIVATE_PLAN_SCHEMA,
        "status": "planned_no_new_split_gui_controls",
        "split": split,
        "cell": "odoo-community",
        "ratification_sha256": RATIFICATION_SHA,
        "source_freeze_sha256": source_freeze_sha,
        "full_private_plan_sha256": digest(full_private_plan.read_bytes()),
        "full_public_plan_sha256": digest(full_public_plan.read_bytes()),
        "train_pilot_public_sha256": digest(train_pilot_public_path.read_bytes()),
        "task_set_manifest_sha256": full["task_set_manifest_sha256"],
        "checkpoint": full["checkpoints"][split],
        "source_sha256s": source_freeze["source_sha256s"],
        "frame_guard_amendment": source_freeze.get("frame_guard_amendment"),
        "task_count": count,
        "world_case_count": world_count,
        "accepted_train_pilot_excluded": split == "train",
        "tasks": rows,
        "retry_policy": "manual_reconcile_partial_before_new_attempt",
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }
    public = {
        "schema": PUBLIC_PLAN_SCHEMA,
        "status": "split_source_bound_plan_only_no_gui_dispatch",
        "split": split,
        "cell": "odoo-community",
        "ratification_sha256": RATIFICATION_SHA,
        "source_freeze_sha256": source_freeze_sha,
        "private_plan_sha256": digest(canonical(plan)),
        "candidate_count": count,
        "family_candidate_counts": {family: sum(
            row["family"] == family for row in rows) for family in FAMILIES},
        "fresh_current_profile_gui_controls": 0,
        "official_final_tasks_admitted": 0,
        "researcher_campaigns": 0,
        "model_attempts": 0,
    }
    return plan, public


def validate_split_plan(*, split: str, private_path: Path,
                        public_path: Path, source_freeze_path: Path) -> dict:
    source_freeze, freeze_sha = validate_source_freeze(source_freeze_path)
    private = private_json(private_path)
    public = public_json(public_path)
    count = SPLITS[split][1]
    require(private.get("schema") == PRIVATE_PLAN_SCHEMA and
            private.get("status") == "planned_no_new_split_gui_controls" and
            private.get("split") == split and
            private.get("ratification_sha256") == RATIFICATION_SHA and
            private.get("source_freeze_sha256") == freeze_sha and
            private.get("source_sha256s") == source_freeze["source_sha256s"] and
            private.get("frame_guard_amendment") ==
            source_freeze.get("frame_guard_amendment") and
            private.get("task_count") == count and
            private.get("world_case_count") == SPLITS[split][3] and
            private.get("accepted_train_pilot_excluded") is (split == "train") and
            len(private.get("tasks", [])) == count and
            len({row["task_id"] for row in private["tasks"]}) == count and
            public.get("schema") == PUBLIC_PLAN_SCHEMA and
            public.get("split") == split and
            public.get("private_plan_sha256") == digest(private_path.read_bytes()) and
            public.get("candidate_count") == count and
            public.get("fresh_current_profile_gui_controls") == 0 and
            public.get("official_final_tasks_admitted") == 0 and
            private.get("official_final_tasks_admitted") == 0,
            "scale_split_plan_or_source_drift")
    return private


def write_new(path: Path, value: dict, *, private: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True,
                      mode=0o700 if private else 0o755)
    if private:
        _private(path.parent, directory=True)
    raw = canonical(value)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                         0o600 if private else 0o644)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=tuple(SPLITS), required=True)
    parser.add_argument("--worker-dir", type=Path, required=True)
    parser.add_argument("--full-private-plan", type=Path, required=True)
    parser.add_argument("--full-public-plan", type=Path, required=True)
    parser.add_argument("--source-freeze", type=Path, required=True)
    parser.add_argument("--train-pilot-public", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    try:
        private, public = build_split_plan(
            split=args.split, worker_dir=args.worker_dir,
            full_private_plan=args.full_private_plan,
            full_public_plan=args.full_public_plan,
            source_freeze_path=args.source_freeze,
            train_pilot_public_path=args.train_pilot_public)
        write_new(args.private_out, private=True, value=private)
        write_new(args.public_out, private=False, value=public)
    except Exception as error:
        print(json.dumps({"schema": PUBLIC_PLAN_SCHEMA,
                          "status": "source_bound_plan_refused",
                          "error_type": type(error).__name__,
                          "official_final_tasks_admitted": 0,
                          "model_attempts": 0}, sort_keys=True))
        raise SystemExit(2) from None
    print(json.dumps(public, sort_keys=True))
