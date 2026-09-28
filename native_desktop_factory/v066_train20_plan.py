"""Private 20-ID WDI train source freeze and task-disjoint 15/5 diagnostic plan.

This module is offline. It does not create an E2B guest or expose oracle data
in its public aggregate. A complete source binding is revalidated before each
future provider intent.
"""

from __future__ import annotations

from collections import Counter
import argparse
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path

from . import admit
from .source import EXPECTED_SHA256 as WDI_SOURCE_SHA256
from .v066_final_freeze import validate_ratification
from . import v066_scoped_calc_writer_train_demo as known_demos
from . import v066_scoped_profile_train_control as impress_demo


SCHEMA = "cua-native-wdi-v066-train20-source-plan-private-v1"
PUBLIC_SCHEMA = "cua-native-wdi-v066-train20-source-plan-public-v1"
LEASE_SECONDS = 600
MAX_INTENTS = 20
CONCURRENCY = 1
PLANNING_USD_PER_HOUR_UPPER = Decimal("1.00")
SOURCE_FILES = (
    "native_desktop_factory/v066_train20_plan.py",
    "native_desktop_factory/v066_train20_worker.py",
    "native_desktop_factory/v066_train20_audit.py",
    "native_desktop_factory/v066_scoped_calc_writer_train_demo.py",
    "native_desktop_factory/v066_scoped_profile_train_control.py",
    "native_desktop_factory/v066_scoped_profile_guard.py",
    "native_desktop_factory/v066_scoped_profile_reference.py",
    "native_desktop_factory/v066_profile_scope_analysis.py",
    "native_desktop_factory/qwen_v066_adapter.py",
    "native_desktop_factory/qwen_v064_adapter.py",
    "native_desktop_factory/runtime_fingerprint_probe.py",
    "native_desktop_factory/v066_storage_budget.py",
    "native_desktop_factory/reconcile_interrupted_sweep.py",
    "native_desktop_factory/gui_control_shell.py",
    "native_desktop_factory/v066_final_freeze.py",
    "native_desktop_factory/verify.py",
    "native_desktop_factory/admit.py",
    "native_desktop_factory/source.py",
    "native_desktop_factory/factory.py",
    "src/cursibench/scale_action_contract.py",
    "src/cursibench/scale_action_contract_v066.py",
    "src/cursibench/scale_action_output_v066.py",
)


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def encode(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _write_new(path: Path, raw: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if mode == 0o600:
        path.parent.chmod(0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def source_hashes(repo_root: Path) -> dict[str, str]:
    return {name: digest((repo_root / name).read_bytes()) for name in SOURCE_FILES}


def actions_for_train(row: dict, oracle: dict) -> list[dict]:
    """Reuse only the three already real-GUI-tested single-edit patterns.

    Other country/task instances retain the same source structure but have
    not passed a new v0.6.6 live guest. The first mismatch stops the lane.
    """
    targets = oracle.get("targets")
    if (row.get("split") != "train" or oracle.get("split") != "train"
            or row.get("task_id") != oracle.get("task_id")
            or type(targets) is not dict or len(targets) != 1):
        raise ValueError("A single-edit original training source is required")
    workflow = row["workflow"]
    if workflow in ("calc-growth", "calc-risk"):
        if list(targets) != ["Review!B4"]:
            raise ValueError("Unexpected original Calc training target")
        actions = known_demos.actor_actions("calc", oracle)
    elif workflow == "writer-brief":
        if not next(iter(targets)).startswith("FINDING_1_REVIEW_"):
            raise ValueError("Unexpected original Writer training target")
        actions = known_demos.actor_actions("writer", oracle)
    elif workflow == "impress-deck":
        if (oracle.get("target_slide") != 3 or
                not next(iter(targets)).startswith("SIGNAL_1_REVIEW_")):
            raise ValueError("Unexpected original Impress training target")
        actions = impress_demo._script(next(iter(targets.values())))
    else:
        raise ValueError("Unsupported original train workflow")
    if not 1 <= len(actions) <= 32:
        raise ValueError("Original training GUI action count changed")
    return actions


def _validate_inventory(candidate_root: Path) -> tuple[bytes, list[dict], dict]:
    raw = (candidate_root / "candidate-inventory.json").read_bytes()
    inventory = json.loads(raw)
    if (inventory.get("schema") != "cua-native-wdi-candidate-inventory-v1"
            or inventory.get("design_revision") != "v2-distinct-structures"
            or inventory.get("source_sha256") != WDI_SOURCE_SHA256
            or inventory.get("counts") !=
            {"train": 20, "selection": 20, "final_candidate": 100}):
        raise ValueError("Original WDI 20/20/100 source inventory changed")
    rows = inventory["tasks"]
    if (len(rows) != 140 or len({row["task_id"] for row in rows}) != 140
            or Counter(row["split"] for row in rows) != inventory["counts"]):
        raise ValueError("Original WDI task identities or split counts changed")
    groups: dict[tuple[str, str], str] = {}
    for row in rows:
        admit._package(candidate_root, row)
        for family in ([("source", group) for group in row["source_groups"]]
                       + [("template", row["template_group"]),
                          ("instance", row["instance_group"])]):
            owner = groups.setdefault(family, row["split"])
            if owner != row["split"]:
                raise ValueError("Source/template/instance family leaked across splits")
    train = sorted((row for row in rows if row["split"] == "train"),
                   key=lambda row: row["task_id"])
    if (len({tuple(row["source_groups"]) for row in rows
             if row["split"] == "selection"}) != 5 or
            len({tuple(row["source_groups"]) for row in rows
                 if row["split"] == "final_candidate"}) != 25):
        raise ValueError("Original selection/final source families changed")
    if (Counter(row["workflow"] for row in train) !=
            {"calc-growth": 5, "calc-risk": 5, "impress-deck": 5,
             "writer-brief": 5} or
            any(len(row["source_groups"]) != 1 for row in train) or
            sorted(Counter(row["source_groups"][0] for row in train).values()) !=
            [4, 4, 4, 4, 4]):
        raise ValueError("Original train source-family matrix changed")
    return raw, train, inventory


def assign_roles(source_rows: list[dict], inventory_sha: str) -> tuple[list[dict], list[dict], str]:
    if (len(source_rows) != 20 or
            len({row["task_id"] for row in source_rows}) != 20 or
            len({row["package_sha256"] for row in source_rows}) != 20):
        raise ValueError("Diagnostic assignment needs 20 distinct source packages")
    families = sorted({row["source_group"] for row in source_rows})
    if (len(families) != 5 or
            sorted(Counter(row["source_group"] for row in source_rows).values()) !=
            [4, 4, 4, 4, 4]):
        raise ValueError("Diagnostic assignment needs five four-workflow families")
    country = max(families, key=lambda group:
                  digest((inventory_sha + ":" + group).encode()))
    full = [row for row in source_rows if row["source_group"] == country]
    extra = max((row for row in source_rows if row["source_group"] != country),
                key=lambda row: digest((inventory_sha + ":" +
                                        row["package_sha256"]).encode()))
    holdout = sorted([*full, extra], key=lambda row: row["task_id"])
    holdout_ids = {row["task_id"] for row in holdout}
    sft = sorted((row for row in source_rows if row["task_id"] not in holdout_ids),
                 key=lambda row: row["task_id"])
    if (len(sft) != 15 or len(holdout) != 5 or
            set(row["task_id"] for row in sft) & holdout_ids or
            set(Counter(row["workflow"] for row in holdout)) !=
            {"calc-growth", "calc-risk", "impress-deck", "writer-brief"}):
        raise ValueError("Task-disjoint 15/5 diagnostic assignment invalid")
    return sft, holdout, country


def build_plan(*, repo_root: Path, candidate_root: Path,
               guest_public: Path, scoped_reference: Path,
               ratification: Path) -> tuple[dict, dict]:
    inventory_raw, train, _inventory = _validate_inventory(candidate_root)
    inventory_sha = digest(inventory_raw)
    from .v066_scoped_profile_reference import validate_reference
    reference, reference_sha = validate_reference(scoped_reference)
    if set(reference["applications"]) != {"calc", "impress", "writer"}:
        raise ValueError("Three live-calibrated LibreOffice profiles required")
    guest_raw = guest_public.read_bytes()
    guest = json.loads(guest_raw)
    if (guest.get("schema") !=
            "cua-native-wdi-guest-content-identity-public-v1" or
            guest.get("scoped_guest_content_identity_passed") is not True):
        raise ValueError("Scoped Desktop guest identity is not bound")
    _rat, rat_sha = validate_ratification(ratification)

    source_rows = []
    for row in train:
        directory, baseline, oracle = admit._package(candidate_root, row)
        actions = actions_for_train(row, oracle)
        source_rows.append({
            "task_id": row["task_id"], "workflow": row["workflow"],
            "source_group": row["source_groups"][0],
            "package_sha256": row["package_sha256"],
            "input_sha256": digest(baseline),
            "oracle_sha256": row["oracle_sha256"],
            "instruction_sha256": row["actor_task_sha256"],
            "action_script_sha256": digest(encode(actions)),
            "action_count": len(actions),
            "relative_package_path": str(directory.relative_to(candidate_root)),
        })
    # Freeze one entire source family, then a fifth task from another family.
    # This is deterministic from pre-result source bytes, never from outcomes.
    sft, holdout, country = assign_roles(source_rows, inventory_sha)
    families = sorted({row["source_group"] for row in source_rows})
    holdout_ids = {row["task_id"] for row in holdout}
    private = {
        "schema": SCHEMA, "status": "offline_source_frozen_no_guest_dispatch",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_root": str(candidate_root.resolve()),
        "candidate_inventory_sha256": inventory_sha,
        "source_files_sha256": source_hashes(repo_root),
        "guest_identity_public_sha256": digest(guest_raw),
        "scoped_reference_sha256": reference_sha,
        "action_ratification_sha256": rat_sha,
        "train_rows": source_rows,
        "sft_task_ids": sorted(row["task_id"] for row in sft),
        "holdout_task_ids": sorted(holdout_ids),
        "fully_heldout_source_group": country,
        "lease_seconds_each": LEASE_SECONDS,
        "maximum_total_intents": MAX_INTENTS,
        "concurrency": CONCURRENCY,
        "planning_usd_per_hour_upper": str(PLANNING_USD_PER_HOUR_UPPER),
        "all_20_full_lease_usd_upper": str(
            Decimal(MAX_INTENTS * LEASE_SECONDS) / Decimal(3600) *
            PLANNING_USD_PER_HOUR_UPPER),
        "actual_provider_billed_usd": None,
        "automatic_replay_authorized": False,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    public = {
        "schema": PUBLIC_SCHEMA,
        "status": "offline_plan_no_guest_dispatch_or_model_effect",
        "candidate_inventory_sha256": inventory_sha,
        "original_source_train_selection_final": [20, 20, 100],
        "workflow_counts": dict(sorted(Counter(row["workflow"] for row in source_rows).items())),
        "source_family_count": len(families),
        "sft_candidate_count": 15, "holdout_candidate_count": 5,
        "fully_heldout_source_family_count": 1,
        "mixed_source_family_count": 1,
        "holdout_has_every_workflow": True,
        "lease_seconds_each": LEASE_SECONDS,
        "maximum_total_intents": MAX_INTENTS,
        "concurrency": CONCURRENCY,
        "all_20_full_lease_usd_upper": private["all_20_full_lease_usd_upper"],
        "actual_provider_billed_usd": None,
        "source_files_sha256": private["source_files_sha256"],
        "guest_identity_public_sha256": private["guest_identity_public_sha256"],
        "scoped_reference_sha256": reference_sha,
        "action_ratification_sha256": private["action_ratification_sha256"],
        "real_new_gui_demos": 0,
        "official_final_admissions": 0, "official_model_results": 0,
    }
    return private, public


def write_plan(*, private_out: Path, public_out: Path, private: dict,
               public: dict) -> dict:
    raw = encode(private)
    _write_new(private_out, raw, 0o600)
    public = {**public, "private_plan_sha256": digest(raw)}
    _write_new(public_out, (json.dumps(public, indent=2, sort_keys=True) + "\n").encode(),
               0o644)
    return public


def validate_plan(*, private_path: Path, repo_root: Path,
                  candidate_root: Path, guest_public: Path,
                  scoped_reference: Path, ratification: Path) -> tuple[dict, str]:
    raw = private_path.read_bytes()
    plan = json.loads(raw)
    if (plan.get("schema") != SCHEMA or
            private_path.stat().st_mode & 0o077 or
            plan.get("candidate_root") != str(candidate_root.resolve()) or
            plan.get("source_files_sha256") != source_hashes(repo_root) or
            plan.get("guest_identity_public_sha256") != digest(guest_public.read_bytes()) or
            plan.get("scoped_reference_sha256") != digest(scoped_reference.read_bytes()) or
            plan.get("action_ratification_sha256") != digest(ratification.read_bytes())):
        raise ValueError("Private Desktop train20 source plan changed")
    rebuilt, _ = build_plan(repo_root=repo_root, candidate_root=candidate_root,
                            guest_public=guest_public,
                            scoped_reference=scoped_reference,
                            ratification=ratification)
    rebuilt.pop("created_utc")
    candidate = dict(plan)
    candidate.pop("created_utc")
    if candidate != rebuilt:
        raise ValueError("Desktop train20 source mapping changed")
    return plan, digest(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--guest-public", type=Path, required=True)
    parser.add_argument("--scoped-reference", type=Path, required=True)
    parser.add_argument("--ratification", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    private, public = build_plan(
        repo_root=args.repo_root, candidate_root=args.candidate_root,
        guest_public=args.guest_public,
        scoped_reference=args.scoped_reference, ratification=args.ratification)
    result = write_plan(private_out=args.private_out, public_out=args.public_out,
                        private=private, public=public)
    print(json.dumps({key: result[key] for key in (
        "status", "private_plan_sha256", "sft_candidate_count",
        "holdout_candidate_count", "real_new_gui_demos")}, sort_keys=True))


if __name__ == "__main__":
    main()
