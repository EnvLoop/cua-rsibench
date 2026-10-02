"""Read-only, source-bound audit of historical Odoo candidate GUI controls.

This audit never opens Odoo, Docker, a browser, or a model provider. It can
reverify the 20/20/100 evaluator control receipts, but it cannot promote them
into official final tasks or establish a live v0.6.6 model-run gate.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from factory import CODE_DIR
from partition_factory import FAMILIES, ROLE_GROUP_XMLIDS, source_asset
from sweep_partition import NEGATIVE_CODES


SCHEMA = "envloop-odoo-offline-candidate-evidence-audit-v1"
SPLITS = {"train": ("train", 5), "selection": ("selection", 5),
          "official_hidden": ("official", 25)}
AUDIT_FILES = {
    "train": "odoo-hidden-study-train-20-gui-audit-2026-09-25.json",
    "selection": "odoo-hidden-study-selection-20-gui-audit-2026-09-25.json",
    "official_hidden": "odoo-official-hidden-100-gui-audit-2026-09-25.json",
}
AGGREGATE_FILE = "odoo-hidden-study-environment-aggregate-2026-09-25.json"
BOUNDARY_FILE = "odoo-hidden-final-boundary-2026-09-25.json"
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")


class EvidenceError(ValueError):
    """A historical candidate receipt or its source binding is inconsistent."""


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise EvidenceError(reason)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_digest(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), "missing_or_symlinked_evidence")
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def load_json(path: Path) -> object:
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 8_000_000,
            "missing_unsafe_or_oversized_json_evidence")
    try:
        return json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise EvidenceError("invalid_json_evidence") from None


def canonical_digest(value: object) -> str:
    return digest(json.dumps(value, sort_keys=True).encode())


def _reward_is(value: object, expected: float) -> bool:
    return type(value) in (int, float) and value == expected


def _mode_owner_only(path: Path) -> bool:
    mode = stat.S_IMODE(path.stat().st_mode)
    return mode & 0o077 == 0


def _interval(raw: object) -> datetime:
    require(type(raw) is str, "invalid_gui_interval")
    try:
        value = datetime.fromisoformat(raw)
    except ValueError:
        raise EvidenceError("invalid_gui_interval") from None
    require(value.tzinfo is not None, "naive_gui_interval")
    return value


def _lease(events_path: Path, pid: int, first: datetime, last: datetime) -> bool:
    require(events_path.is_file() and not events_path.is_symlink(), "lease_log_missing")
    events = []
    for line in events_path.read_text().splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            raise EvidenceError("lease_log_invalid") from None
        require(type(event) is dict and type(event.get("pid")) is int,
                "lease_log_invalid")
        events.append(event)
    for index, event in enumerate(events):
        if (event.get("operation") != "sweep_partition" or
                event.get("event") != "acquired" or event["pid"] != pid or
                _interval(event.get("at_utc")) > first):
            continue
        release = next((later for later in events[index + 1:]
                        if later.get("operation") == "sweep_partition" and
                        later.get("event") == "released" and
                        later.get("pid") == pid), None)
        if release is None or _interval(release.get("at_utc")) < last:
            continue
        if any(first <= _interval(other.get("at_utc")) <= last and
               (other.get("pid") != pid or
                other.get("operation") != "sweep_partition")
               for other in events):
            return False
        return True
    return False


def _public_receipts(public_dir: Path) -> tuple[dict, dict, dict[str, dict]]:
    aggregate = load_json(public_dir / AGGREGATE_FILE)
    boundary = load_json(public_dir / BOUNDARY_FILE)
    require(type(aggregate) is dict and type(boundary) is dict,
            "public_receipt_invalid")
    require(aggregate.get("schema") ==
            "envloop-odoo-hidden-study-environment-aggregate-v1" and
            aggregate.get("official_final_tasks_admitted") == 0 and
            aggregate.get("completed_official_model_attempts") == 0 and
            boundary.get("schema") == "envloop-odoo-hidden-boundary-public-v1" and
            boundary.get("official_final_tasks_admitted") == 0 and
            boundary.get("source_entity_instance_overlap_with_any_compared_pool") == 0,
            "public_receipt_status_changed")
    audits = {}
    for split, filename in AUDIT_FILES.items():
        path = public_dir / filename
        key = "hidden_gui" if split == "official_hidden" else f"{split}_gui"
        require(file_digest(path) == aggregate.get("evidence_sha256", {}).get(key),
                "public_gui_receipt_hash_changed")
        audit = load_json(path)
        require(type(audit) is dict and audit.get("partition") == split and
                audit.get("status") == "candidate_environment_qualified" and
                audit.get("official_final_tasks_admitted") == 0 and
                audit.get("model_attempts") == 0,
                "public_gui_receipt_status_changed")
        audits[split] = audit
    require(file_digest(public_dir / BOUNDARY_FILE) ==
            aggregate.get("evidence_sha256", {}).get("hidden_boundary"),
            "public_boundary_receipt_hash_changed")
    return aggregate, boundary, audits


def audit(workers_root: Path, public_dir: Path, *,
          asset_builder=source_asset) -> tuple[dict, dict]:
    """Return private per-ID and public aggregate reports without writes.

    A permissive private directory or file does not erase historical controls,
    but always closes the pre-campaign gate. The caller must not use this
    report as a v0.6 qualification proof or official model result.
    """
    workers_root = Path(workers_root)
    public_dir = Path(public_dir)
    aggregate, boundary, audits = _public_receipts(public_dir)
    split_rows = {}
    manifests = []
    pinned_codes = []
    permission_counts: Counter[str] = Counter()
    checked_permissions: set[Path] = set()

    def track(path: Path, kind: str) -> None:
        require(path.exists() and not path.is_symlink(), "unsafe_private_evidence_path")
        if path not in checked_permissions:
            checked_permissions.add(path)
            if not _mode_owner_only(path):
                permission_counts[kind] += 1

    for split, (manifest_split, per_family) in SPLITS.items():
        private = workers_root / split / "private"
        track(private, "directories")
        # Include every retained private artifact, not only inputs consumed here.
        # A readable old gold file or descendant directory also closes the gate.
        for artifact in private.rglob("*"):
            track(artifact, "directories" if artifact.is_dir() else "files")
        receipt_path = private / "partition_receipt.json"
        checkpoint_path = private / "checkpoint_receipt.json"
        world_path = private / "partition_cases.json"
        source_path = private / "source_hashes.json"
        manifest_path = private / "task_set_manifest.json"
        snapshot_path = private / "baseline_snapshot.json"
        for path in (receipt_path, checkpoint_path, world_path, source_path,
                     manifest_path, snapshot_path):
            track(path, "files")
        receipt = load_json(receipt_path)
        checkpoint = load_json(checkpoint_path)
        world = load_json(world_path)
        source_hashes = load_json(source_path)
        task_sets = load_json(manifest_path)
        audit_receipt = audits[split]
        require(all(type(item) is dict for item in
                    (receipt, checkpoint, world, source_hashes, task_sets)),
                "private_manifest_invalid")
        require(receipt.get("partition") == split and world.get("split") == split and
                receipt.get("official_final_tasks_admitted") == 0,
                "partition_identity_changed")
        require(canonical_digest(world) == receipt.get("case_manifest_sha256") ==
                audit_receipt.get("world_case_manifest_sha256") and
                canonical_digest(source_hashes) == receipt.get("source_hash_manifest_sha256") ==
                audit_receipt.get("world_source_hash_manifest_sha256") and
                canonical_digest(task_sets) == receipt.get("task_set_manifest_sha256") ==
                audit_receipt.get("task_set_manifest_sha256"),
                "world_or_task_manifest_hash_changed")
        require(set(task_sets) == {"train", "selection", "official"} and
                {key: len(rows) for key, rows in task_sets.items()} ==
                {"train": 20, "selection": 20, "official": 100},
                "study_task_split_counts_changed")
        manifests.append(task_sets)
        code = receipt.get("pinned_code_and_runtime_sha256")
        require(type(code) is dict and code == audit_receipt.get("pinned_code_and_runtime_sha256")
                and len(code) >= 12, "historical_code_binding_changed")
        pinned_codes.append(code)
        for name, sha in code.items():
            require(type(name) is str and Path(name).name == name and
                    type(sha) is str and HEX.fullmatch(sha) is not None and
                    file_digest(CODE_DIR / name) == sha,
                    "historical_source_bytes_changed")
        for archive_name, hash_name in (("baseline.pgcustom", "db_sha256"),
                                        ("baseline-filestore.tgz", "filestore_sha256")):
            archive = private / archive_name
            track(archive, "files")
            require(file_digest(archive) == checkpoint.get(hash_name) ==
                    audit_receipt.get("db_checkpoint_sha256" if hash_name == "db_sha256"
                                      else "filestore_checkpoint_sha256"),
                    "checkpoint_archive_hash_changed")
        expected = {}
        for family in FAMILIES:
            cases = world.get("cases", {}).get(family)
            require(type(cases) is list and len(cases) == per_family,
                    "family_case_count_changed")
            for case in cases:
                require(type(case) is dict and type(case.get("id")) is str and
                        ID.fullmatch(case["id"]) is not None and
                        case.get("family") == family and
                        case.get("partition") == split and
                        case["id"] not in expected,
                        "case_identity_invalid")
                expected[case["id"]] = case
        require(len(expected) == per_family * len(FAMILIES) and
                set(source_hashes) == set(expected), "source_case_coverage_changed")
        packages = {row["task_id"]: row for row in task_sets[manifest_split]}
        require(set(packages) == set(expected) and len(packages) == len(expected),
                "task_package_coverage_changed")
        asset_hashes = set()
        for task_id, case in expected.items():
            asset = asset_builder(case, world)
            require(type(asset) is bytes and asset,
                    "source_asset_rebuild_invalid")
            source_sha = digest(asset)
            package_sha = digest(json.dumps(case, sort_keys=True).encode() + b"\n" + asset)
            package = packages[task_id]
            require(source_hashes[task_id] == source_sha and
                    package.get("package_sha256") == package_sha and
                    package.get("source_groups") == ["odoo-source-" + source_sha] and
                    package.get("template_group") == case.get("template_group") and
                    package.get("instance_group") == case.get("instance_group"),
                    "source_asset_or_package_changed")
            asset_hashes.add(source_sha)
        require(len(asset_hashes) == len(expected), "source_asset_duplicate_within_split")
        run_id = audit_receipt.get("run_id")
        require(type(run_id) is str and ID.fullmatch(run_id) is not None,
                "historical_run_id_invalid")
        runs = private / "admission_runs"
        run = runs / run_id
        track(runs, "directories")
        track(run, "directories")
        summary_path = run / "summary.json"
        track(summary_path, "files")
        summary = load_json(summary_path)
        require(type(summary) is dict and summary.get("run_id") == run_id and
                summary.get("partition") == split and
                summary.get("attempted_this_run") == len(expected) and
                summary.get("qualified_this_run") == len(expected) and
                summary.get("official_final_tasks_admitted") == 0 and
                type(summary.get("cases")) is list and
                len(summary["cases"]) == len(expected),
                "historical_run_summary_changed")
        receipt_paths = {path.stem: path for path in run.glob("*.json")
                         if path.name != "summary.json"}
        require(set(receipt_paths) == set(expected), "per_id_gui_receipt_coverage_changed")
        rows = []
        for task_id, path in receipt_paths.items():
            track(path, "files")
            row = load_json(path)
            require(type(row) is dict and row.get("case_id") == task_id and
                    row.get("family") == expected[task_id]["family"] and
                    row.get("task_package_sha256") == packages[task_id]["package_sha256"] and
                    row.get("baseline_snapshot_sha256") == file_digest(snapshot_path) and
                    row.get("status") == "candidate_environment_gui_qualified" and
                    row.get("official_final_task") is False and
                    row.get("exclusive_worker_lease_held") is True and
                    row.get("cold_reset_before") is True and
                    row.get("cold_reset_after") is True and
                    row.get("source_visible_in_native_gui") is True and
                    _reward_is(row.get("baseline_reward"), 0.0) and
                    _reward_is(row.get("gui_oracle_reward"), 1.0) and
                    row.get("positive_difference_codes") == [] and
                    _reward_is(row.get("wrong_object_reward"), 0.0) and
                    NEGATIVE_CODES[expected[task_id]["family"]] in
                    row.get("wrong_object_difference_codes", []) and
                    _reward_is(row.get("after_reset_reward"), 0.0) and
                    row.get("protected_source_files_checked") == 3 * per_family + 1,
                    "per_id_gui_control_invalid")
            rows.append({"task_id": task_id,
                         "package_sha256": packages[task_id]["package_sha256"],
                         "source_asset_sha256": source_hashes[task_id],
                         "gui_receipt_sha256": file_digest(path),
                         "row": row})
        summary_rows = {row["case_id"]: row for row in summary["cases"]}
        require(len(summary_rows) == len(expected) and
                {row["task_id"]: row["row"] for row in rows} == summary_rows,
                "per_id_receipt_and_summary_disagree")
        ordered = summary["cases"]
        for previous, current in zip(ordered, ordered[1:]):
            require(_interval(previous.get("finished_at_utc")) <=
                    _interval(current.get("started_at_utc")),
                    "gui_control_intervals_overlap")
        starts = [_interval(row.get("started_at_utc")) for row in ordered]
        finishes = [_interval(row.get("finished_at_utc")) for row in ordered]
        require(all(start <= finish for start, finish in zip(starts, finishes)) and
                len({row.get("worker_pid") for row in ordered}) == 1 and
                type(ordered[0].get("worker_pid")) is int,
                "gui_control_worker_or_time_invalid")
        lease_path = private / "worker-lease-events.jsonl"
        track(lease_path, "files")
        require(_lease(lease_path, ordered[0]["worker_pid"], starts[0], finishes[-1]),
                "exclusive_gui_lease_missing_or_overlap")
        require(audit_receipt.get("candidate_cases") == len(expected) and
                audit_receipt.get("cases_with_all_per_id_controls") == len(expected) and
                audit_receipt.get("all_sources_visible_in_native_gui") is True and
                audit_receipt.get("final_database_and_physical_filestore_reset_exact") is True and
                audit_receipt.get("actor_role_scoped_no_admin_group") is True and
                audit_receipt.get("evaluator_select_only_on_scored_tables") is True and
                audit_receipt.get("exclusive_worker_lease_interval_verified") is True and
                audit_receipt.get("protected_attachment_files_per_attempt") ==
                3 * per_family + 1 and
                audit_receipt.get("per_family_qualified") ==
                {family: per_family for family in FAMILIES},
                "historical_public_gui_claim_changed")
        split_rows[split] = {"count": len(rows), "family_counts":
                             dict(Counter(row["row"]["family"] for row in rows)),
                             "rows": rows,
                             "source_hashes": asset_hashes}

    require(all(manifest == manifests[0] for manifest in manifests[1:]) and
            all(code == pinned_codes[0] for code in pinned_codes[1:]) and
            canonical_digest(manifests[0]) ==
            aggregate.get("common_task_set_manifest_sha256") ==
            boundary.get("task_set_manifest_sha256"),
            "three_world_taskset_or_runtime_changed")
    official_private = workers_root / "official_hidden" / "private"
    boundary_private_path = official_private / "hidden_boundary_audit.json"
    track(boundary_private_path, "files")
    boundary_private = load_json(boundary_private_path)
    require(type(boundary_private) is dict and
            file_digest(boundary_private_path) ==
            boundary.get("private_boundary_audit_sha256") and
            boundary_private.get("task_set_manifest_sha256") ==
            canonical_digest(manifests[0]) and
            boundary_private.get("pinned_code_and_runtime_sha256") == pinned_codes[0] and
            boundary_private.get("official_final_tasks_admitted") == 0,
            "private_boundary_receipt_changed")
    all_rows = [row for split in SPLITS for row in split_rows[split]["rows"]]
    require(len(all_rows) == 140 and
            len({row["task_id"] for row in all_rows}) == 140 and
            len({row["package_sha256"] for row in all_rows}) == 140 and
            len({row["source_asset_sha256"] for row in all_rows}) == 140,
            "cross_split_identity_or_source_overlap")
    group_owners = {}
    for split, (manifest_split, _) in SPLITS.items():
        for package in manifests[0][manifest_split]:
            for kind, value in (("template", package["template_group"]),
                                ("instance", package["instance_group"])):
                old = group_owners.setdefault((kind, value), split)
                require(old == split, "cross_split_template_or_instance_overlap")
    require(aggregate.get("candidate_counts") ==
            {"train": 20, "selection": 20, "official_hidden": 100} and
            aggregate.get("source_entity_instance_overlap_with_exposed_development") == 0 and
            aggregate.get("causal_template_overlap_with_exposed_development") == 0 and
            boundary.get("causal_template_overlap_with_exposed_development") == 0 and
            boundary.get("qa_prompts_gold_and_sources_researcher_exposed") is False,
            "historical_boundary_claim_changed")

    private = {
        "schema": SCHEMA,
        "status": "historical_evaluator_controls_reverified_offline",
        "candidate_counts": {split: split_rows[split]["count"] for split in SPLITS},
        "per_id": {split: [{key: row[key] for key in
                            ("task_id", "package_sha256", "source_asset_sha256",
                             "gui_receipt_sha256")}
                           for row in split_rows[split]["rows"]] for split in SPLITS},
        "task_set_manifest_sha256": canonical_digest(manifests[0]),
        "historical_source_hashes": pinned_codes[0],
        "owner_only_permission_violations_by_category": dict(permission_counts),
        "pre_campaign_admission_eligible": False,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }
    public = {
        "schema": SCHEMA,
        "status": ("historical_evaluator_controls_reverified_privacy_hardening_pending"
                   if permission_counts else
                   "historical_evaluator_controls_reverified_offline"),
        "historical_candidate_counts": private["candidate_counts"],
        "historical_source_assets_and_packages_rebuilt": 140,
        "historical_gui_positive_wrong_object_reset_receipts_reverified": 140,
        "cross_split_identity_source_template_instance_overlap": 0,
        "historical_task_set_manifest_sha256": private["task_set_manifest_sha256"],
        "historical_pinned_source_bundle_sha256": canonical_digest(pinned_codes[0]),
        "prior_public_aggregate_sha256": file_digest(public_dir / AGGREGATE_FILE),
        "prior_public_boundary_sha256": file_digest(public_dir / BOUNDARY_FILE),
        "auditor_sha256": file_digest(Path(__file__)),
        "private_per_id_report_sha256": digest((json.dumps(
            private, sort_keys=True, indent=2) + "\n").encode()),
        "private_evidence_owner_only_permissions": not bool(permission_counts),
        "permission_violations_by_category": dict(permission_counts),
        "live_v066_model_action_and_application_retested": False,
        "current_actor_acl_and_sql_privileges_retested": False,
        "pre_campaign_admission_eligible": False,
        "official_final_tasks_admitted": 0,
        "researcher_campaigns": 0,
        "model_attempts": 0,
    }
    return private, public


def write_new(path: Path, value: dict, *, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if mode == 0o600:
        require(not path.parent.is_symlink() and _mode_owner_only(path.parent),
                "private_report_parent_permissions_invalid")
    raw = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers-root", type=Path, required=True)
    parser.add_argument("--public-evidence-dir", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    private_result, public_result = audit(args.workers_root, args.public_evidence_dir)
    write_new(args.private_out, private_result, mode=0o600)
    write_new(args.public_out, public_result, mode=0o644)
    print(json.dumps(public_result, sort_keys=True))
