"""Fresh neutral Odoo TRAIN prerequisite and full 20/100 GUI controls.

``prepare`` reads an explicitly supplied roster-metadata projection and source
files only. ``run --execute`` is a separate live operation. It uses the same
neutral adapter as teacher/Qwen, existing GUI recipes and independent exact
SQL/filestore/checkpoint/lease verifier, and no old positive credit. There is
no resume, automatic replay, model sampling, or official task admission.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import re
import secrets

from enterprise_fallback.odoo18 import native_material_workers_v1 as workers


ROSTER_SCHEMA = "envloop-odoo-v066-native-material-roster-metadata-v1"
PLAN_SCHEMA = "envloop-odoo-v066-native-material-qualification-plan-v1"
PUBLIC_PLAN_SCHEMA = "envloop-odoo-v066-native-material-qualification-plan-public-v1"
BATCH_SCHEMA = "envloop-odoo-v066-native-material-qualification-batch-v1"
AUDIT_SCHEMA = "envloop-odoo-v066-native-material-gui-case-audit-v1"
TRAIN_CANDIDATE_SCHEMA = "envloop-odoo-v066-native-material-train-control-candidate-v1"
TRAIN_CANDIDATE_STATUS = "fresh_native_material_train_flow_pending_independent_source_review"
SOURCE_REVIEW_SCHEMA = "envloop-odoo-v066-native-material-source-frame-review-v1"
SOURCE_REVIEW_STATUS = "independent_native_source_frame_review_verified"
SPLITS = {"train": (20, 5), "selection": (20, 5), "official_hidden": (100, 25)}
FAMILIES = ("purchase", "inventory", "sales", "crm")
TASK_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
ROW_FIELDS = {"task_id", "package_sha256", "family", "task_binding_sha256",
              "source_asset_sha256", "visible_instruction_sha256", "source_label"}
CHECKPOINT_FILES = {
    "db_sha256": "baseline.pgcustom",
    "filestore_sha256": "baseline-filestore.tgz",
    "baseline_snapshot_sha256": "baseline_snapshot.json",
    "baseline_filestore_manifest_sha256": "baseline-filestore-manifest.json",
}
PLAN_FIELDS = {
    "schema", "status", "split", "cell", "task_count", "tasks", "checkpoint",
    "roster_metadata_sha256", "native_worker_binding", "native_worker_binding_sha256",
    "native_adapter_binding_sha256", "physical_dispatch_profile", "run_nonce_hex",
    "run_nonce_sha256", "fresh_run_directory_name", "source_freeze_sha256",
    "current_candidate_private_sha256", "historical_ratification_sha256", "old_positive_credit",
    "automatic_replay_authorized", "fresh_native_gui_controls", "official_final_tasks_admitted",
    "model_attempts",
}
require = workers.require
canonical = workers.canonical
digest = workers.digest


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _private_directory(path: Path) -> None:
    require(path.is_dir() and not path.is_symlink() and
            path.stat().st_mode & 0o077 == 0,
            "native_private_directory_unsafe")


def _write_new(path: Path, value: object, *, private: bool = True) -> str:
    if private:
        _private_directory(path.parent)
    require(not path.exists() and not path.is_symlink(),
            "native_qualification_refuses_overwrite")
    raw = canonical(value)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                         0o600 if private else 0o644)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return digest(raw)


def validate_roster_metadata(value: object) -> dict:
    """Allow identities and hashes; reject prompts, case values, and oracles."""
    require(type(value) is dict and set(value) == {
        "schema", "split", "tasks", "checkpoint"} and
        value.get("schema") == ROSTER_SCHEMA and type(value.get("split")) is str and
        value["split"] in SPLITS,
        "native_roster_metadata_shape_invalid")
    count, per_family = SPLITS[value["split"]]
    rows, checkpoint = value["tasks"], value["checkpoint"]
    require(type(rows) is list and len(rows) == count and
            type(checkpoint) is dict and set(checkpoint) == set(CHECKPOINT_FILES) and
            all(workers.HEX64.fullmatch(str(checkpoint[name])) is not None
                for name in CHECKPOINT_FILES),
            "native_roster_count_or_checkpoint_invalid")
    seen = set()
    for row in rows:
        require(type(row) is dict and set(row) == ROW_FIELDS and
                type(row["task_id"]) is str and TASK_ID.fullmatch(row["task_id"]) is not None and
                row["task_id"] not in seen and row["family"] in FAMILIES and
                all(type(row[key]) is str and workers.HEX64.fullmatch(row[key]) is not None
                    for key in ("package_sha256", "task_binding_sha256", "source_asset_sha256",
                                "visible_instruction_sha256")) and
                type(row["source_label"]) is str and 0 < len(row["source_label"].encode()) <= 256,
                "native_roster_identity_or_nonmetadata_field_invalid")
        seen.add(row["task_id"])
    require(Counter(row["family"] for row in rows) ==
            Counter({family: per_family for family in FAMILIES}),
            "native_roster_family_coverage_invalid")
    return value


def project_legacy_metadata(value: object, split: str) -> dict:
    """Project an existing frozen metadata plan, never reconstruct case data.

    The original full plan retains all 20 TRAIN identities. Its later
    remaining-TRAIN split plan has 19 and intentionally fails this projection.
    ``task_set_manifest.json`` lacks source/instruction/checkpoint bindings.
    """
    require(type(split) is str and split in SPLITS and type(value) is dict,
            "native_legacy_metadata_plan_invalid")
    if value.get("schema") == "envloop-odoo-v066-prospective-gui-requalification-plan-v1":
        tasks = value.get("tasks")
        checkpoints = value.get("checkpoints")
        require(type(tasks) is dict and type(checkpoints) is dict and
                split in tasks and split in checkpoints,
                "native_full_metadata_split_or_checkpoint_missing")
        rows, checkpoint = tasks[split], checkpoints[split]
    elif value.get("schema") == "envloop-odoo-v066-split-gui-control-plan-v1":
        require(value.get("split") == split, "native_legacy_metadata_split_changed")
        rows, checkpoint = value.get("tasks"), value.get("checkpoint")
    else:
        raise workers.NativeMaterialWorkerError("native_existing_frozen_metadata_plan_required")
    allowed = ROW_FIELDS | {"ratification_sha256", "action_profile", "split", "checkpoint",
                            "odoo_adapter_sha256", "fresh_v066_gui_proof_status"}
    require(type(rows) is list and type(checkpoint) is dict and
            all(type(row) is dict and ROW_FIELDS <= set(row) <= allowed and
                row.get("split", split) == split and
                row.get("checkpoint", checkpoint) == checkpoint for row in rows),
            "native_legacy_rows_missing_metadata_or_contain_task_body")
    require(set(CHECKPOINT_FILES) <= set(checkpoint), "native_legacy_checkpoint_metadata_missing")
    return validate_roster_metadata({
        "schema": ROSTER_SCHEMA, "split": split,
        "checkpoint": {key: checkpoint[key] for key in CHECKPOINT_FILES},
        "tasks": [{key: row[key] for key in ROW_FIELDS} for row in rows],
    })


def prepare(roster_metadata: dict) -> tuple[dict, dict]:
    """Build a fresh plan without reading any worker, task body, or oracle."""
    roster = validate_roster_metadata(roster_metadata)
    binding = workers.public_binding()
    nonce = secrets.token_hex(16)
    plan = {
        "schema": PLAN_SCHEMA,
        "status": "prepared_source_and_roster_metadata_only_no_native_attempts",
        "split": roster["split"], "cell": "odoo-community",
        "task_count": len(roster["tasks"]),
        "tasks": roster["tasks"], "checkpoint": roster["checkpoint"],
        "roster_metadata_sha256": digest(canonical(roster)),
        "native_worker_binding": binding,
        "native_worker_binding_sha256": binding["binding_sha256"],
        "native_adapter_binding_sha256": binding["native_adapter_binding"]["binding_sha256"],
        "physical_dispatch_profile": binding["profile"],
        "run_nonce_hex": nonce, "run_nonce_sha256": digest(nonce.encode()),
        "fresh_run_directory_name": "native-" + nonce,
        # These compatibility fields bind the retained evaluator's raw receipt.
        # They do not accept any prior GUI outcome or promotion authority.
        "source_freeze_sha256": binding["binding_sha256"],
        "current_candidate_private_sha256": digest(canonical(roster)),
        "historical_ratification_sha256": "49f6a047313c4b1c30fbe357677dbf33cb692614d7e273fe57b088e435c46359",
        "old_positive_credit": 0,
        "automatic_replay_authorized": False,
        "fresh_native_gui_controls": 0,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }
    public = {
        "schema": PUBLIC_PLAN_SCHEMA, "status": plan["status"],
        "split": plan["split"], "candidate_count": plan["task_count"],
        "family_counts": dict(Counter(row["family"] for row in roster["tasks"])),
        "private_plan_sha256": digest(canonical(plan)),
        "native_worker_binding_sha256": binding["binding_sha256"],
        "native_adapter_binding_sha256": plan["native_adapter_binding_sha256"],
        "run_nonce_sha256": plan["run_nonce_sha256"],
        "fresh_native_gui_controls": 0, "old_positive_credit": 0,
        "official_final_tasks_admitted": 0, "model_attempts": 0,
    }
    return plan, public


def validate_plan(value: object) -> dict:
    require(type(value) is dict and set(value) == PLAN_FIELDS and value.get("schema") == PLAN_SCHEMA,
            "native_qualification_plan_invalid")
    roster = validate_roster_metadata({
        "schema": ROSTER_SCHEMA, "split": value.get("split"),
        "tasks": value.get("tasks"), "checkpoint": value.get("checkpoint"),
    })
    workers.validate_binding(value.get("native_worker_binding"),
                             value.get("native_worker_binding_sha256"))
    binding = value["native_worker_binding"]
    require(value.get("status") == "prepared_source_and_roster_metadata_only_no_native_attempts" and
            value.get("cell") == "odoo-community" and
            type(value.get("task_count")) is int and value["task_count"] == len(roster["tasks"]) and
            value.get("roster_metadata_sha256") == digest(canonical(roster)) and
            value.get("current_candidate_private_sha256") == digest(canonical(roster)) and
            value.get("source_freeze_sha256") == binding["binding_sha256"] and
            value.get("native_worker_binding_sha256") == binding["binding_sha256"] and
            value.get("native_adapter_binding_sha256") == binding["native_adapter_binding"]["binding_sha256"] and
            value.get("physical_dispatch_profile") == binding["profile"] and
            type(value.get("run_nonce_hex")) is str and
            workers.NONCE.fullmatch(str(value.get("run_nonce_hex"))) is not None and
            value.get("run_nonce_sha256") == digest(value["run_nonce_hex"].encode()) and
            value.get("fresh_run_directory_name") == "native-" + value["run_nonce_hex"] and
            value.get("automatic_replay_authorized") is False and
            all(type(value.get(key)) is int and value[key] == 0 for key in (
                "old_positive_credit", "fresh_native_gui_controls", "official_final_tasks_admitted", "model_attempts")),
            "native_qualification_plan_binding_changed")
    return value


def audit_native_trace(attempt: Path, trace: dict, row: dict) -> dict:
    """Audit the native guard PNGs in addition to the old durable action chain."""
    samples = trace.get("exact_return_guard_samples")
    require(type(samples) is list and samples,
            "native_qualification_guard_samples_missing")
    for index, sample in enumerate(samples):
        require(type(sample) is dict and type(sample.get("step")) is int and
                sample.get("stage") in ("parse", "dispatch") and
                type(sample.get("sample")) is int and sample["sample"] in range(3) and
                sample.get("sampled_frame_ref", {}).get("path") == f"frames/guard-{index:04d}.png",
                "native_guard_trace_order_or_path_invalid")
        raw = workers.private_ref_bytes(attempt, sample["sampled_frame_ref"])
        require(digest(raw) == sample.get("raw_frame_sha256"),
                "native_guard_trace_raw_digest_changed")
    verified = 0
    accepted_paths = set()
    for step, item in enumerate(trace["actions"]):
        candidates = sorted((attempt / "actions").glob(f"step-{step:03d}*-intent.private.json"))
        require(len(candidates) == 1, "native_guard_trace_intent_ambiguous")
        intent = workers.private_json(candidates[0])
        action = intent["normalized_action"]
        contract = item["contract_receipt"]
        observed = workers.private_ref_bytes(attempt, item["frame"])
        result = workers.audit_native_contract(contract, action, observed, step, row, attempt)
        verified += result["guard_pngs_reopened"]
        rows = []
        for stage in ("parse", "dispatch"):
            guard = contract["native_material_" + stage + "_guard"]
            controls = intent.get("observation_controls")
            require(type(controls) is list and guard.get("observed_control_refs") == sorted(
                item["ref"] for item in controls if item["visible"] is True and item["enabled"] is True),
                "native_guard_observed_controls_not_bound_to_durable_intent")
            require(guard["observed_url"] == intent.get("observed_url") and
                    guard["observed_frame_id_sha256"] == digest(intent["frame_id"].encode()),
                    "native_guard_durable_intent_context_changed")
            rows.extend(guard["sampled_frames"])
        indexes = []
        for sample in rows:
            matches = [index for index, retained in enumerate(samples) if retained == sample]
            require(len(matches) == 1 and sample["sampled_frame_ref"]["path"] not in accepted_paths,
                    "native_success_guard_missing_duplicate_or_reused")
            accepted_paths.add(sample["sampled_frame_ref"]["path"])
            indexes.append(matches[0])
        require(indexes == list(range(indexes[0], indexes[0] + 6)),
                "native_guard_parse_dispatch_not_contiguous")
    require(len(samples) == verified and trace.get("pre_intent_rejections") == [],
            "native_successful_case_has_stale_samples_or_resampling")
    return {"native_guard_pngs_reopened": verified,
            "native_guard_samples_retained": len(samples),
            "native_guard_action_count": len(trace["actions"])}


def audit_case(*, plan: dict, row: dict, attempt: Path,
               worker_private: Path) -> dict:
    binding = workers.validate_binding(plan["native_worker_binding"])
    auditor = workers.semantic_auditor_module(binding)
    independent = importlib.import_module("tools.odoo_v066_scale_audit_v1")

    def checked_action_chain(directory, trace, task, **_flags):
        result = independent._action_chain(directory, trace, task,
                                          require_exact_return_guard=False,
                                          require_pinned_profile=True)
        audit_native_trace(directory, trace, task)
        return result

    auditor._action_chain = checked_action_chain
    result = auditor.audit_current_case(plan=plan, row=row, attempt=attempt,
                                       worker_private=worker_private)
    receipt = workers.private_json(attempt / "attempt.private.json")
    trace = workers.private_json(attempt / receipt["refs"]["gui_trace"]["path"])
    guards = audit_native_trace(attempt, trace, row)
    readiness = workers.audit_readiness_receipt(attempt / "db-readiness.private.json", binding,
                                               worker_private.parent)
    return {**result, **guards, **readiness, "schema": AUDIT_SCHEMA,
            "status": "native_material_saved_state_and_guard_semantics_verified_source_visual_review_pending",
            "native_adapter_binding_sha256": plan["native_adapter_binding_sha256"],
            "native_worker_binding_sha256": plan["native_worker_binding_sha256"],
            "run_nonce_sha256": plan["run_nonce_sha256"],
            "source_attachment_gui_frame_retained": True,
            "source_attachment_readback": False,
            "source_visual_review_verified": False,
            "original_services_restored": receipt["service_state_restored_receipt"],
            "old_positive_credit": 0}


def _case_row(plan: dict, metadata: dict, prerequisite_sha: str | None) -> dict:
    binding = plan["native_worker_binding"]
    return {**metadata, "split": plan["split"],
            "physical_dispatch_profile": plan["physical_dispatch_profile"],
            "source_freeze_sha256": binding["binding_sha256"],
            "epoch_source_freeze_sha256": binding["binding_sha256"],
            "current_candidate_private_sha256": plan["current_candidate_private_sha256"],
            "historical_ratification_sha256": plan["historical_ratification_sha256"],
            "no_gui_gate_sha256": digest(canonical({"plan_sha256": digest(canonical(plan)),
                                                   "fresh_train_control_sha256": prerequisite_sha})),
            "run_nonce_sha256": plan["run_nonce_sha256"],
            "cell_plan_sha256": digest(canonical(plan))}


def finalize_train_control(*, plan_path: Path, worker_dir: Path, run_dir: Path,
                           source_review_path: Path, source_review_sha256: str) -> dict:
    """Saved-evidence only; a pending GUI run cannot approve its own source."""
    plan = validate_plan(workers.private_json(plan_path))
    require(plan["split"] == "train" and digest(plan_path.read_bytes()) == digest(canonical(plan)),
            "native_finalize_requires_canonical_train_plan")
    worker = Path(worker_dir).resolve()
    private = worker / "private"
    run_dir = Path(run_dir)
    require(worker.name == "train" and
            run_dir.parent.resolve() == (private / "v066_native_material_controls").resolve() and
            run_dir.name == plan["fresh_run_directory_name"],
            "native_finalize_train_run_binding_changed")
    _private_directory(private)
    _private_directory(run_dir)
    candidate = workers.private_json(run_dir / "train-control-candidate.private.json")
    attempt = run_dir / "attempt-000"
    receipt_path = attempt / "attempt.private.json"
    receipt = workers.private_json(receipt_path)
    audit_path = attempt / "independent-audit.private.json"
    retained_audit = workers.private_json(audit_path)
    metadata = [row for row in plan["tasks"] if row["task_id"] == receipt.get("task_id")]
    require(len(metadata) == 1 and metadata[0]["family"] == "purchase" and
            candidate.get("schema") == TRAIN_CANDIDATE_SCHEMA and
            candidate.get("status") == TRAIN_CANDIDATE_STATUS and
            candidate.get("source_visual_review_pending") is True and
            candidate.get("source_visual_review_verified") is False and
            candidate.get("attempt_sha256") == digest(receipt_path.read_bytes()) and
            candidate.get("audit_sha256") == digest(audit_path.read_bytes()) and
            candidate.get("run_nonce_sha256") == plan["run_nonce_sha256"] and
            candidate.get("native_worker_binding_sha256") == plan["native_worker_binding_sha256"] and
            candidate.get("native_adapter_binding_sha256") == plan["native_adapter_binding_sha256"] and
            candidate.get("plan_sha256") == digest(canonical(plan)),
            "native_pending_train_candidate_evidence_changed")
    row = _case_row(plan, metadata[0], None)
    rederived = audit_case(plan=plan, row=row, attempt=attempt, worker_private=private)
    require(rederived == retained_audit, "native_train_saved_audit_rederivation_changed")
    frame = receipt["refs"]["source_frame"]
    workers.private_ref_bytes(attempt, frame)
    review = workers.private_json(source_review_path, source_review_sha256)
    expected = {
        "schema": SOURCE_REVIEW_SCHEMA, "status": SOURCE_REVIEW_STATUS,
        "task_id": row["task_id"], "package_sha256": row["package_sha256"],
        "source_asset_sha256": row["source_asset_sha256"], "source_frame_sha256": frame["sha256"],
        "attempt_sha256": candidate["attempt_sha256"], "audit_sha256": candidate["audit_sha256"],
        "native_worker_binding_sha256": plan["native_worker_binding_sha256"],
        "native_adapter_binding_sha256": plan["native_adapter_binding_sha256"],
        "run_nonce_sha256": plan["run_nonce_sha256"],
        "reviewer_independent_of_actor": True, "source_attachment_readable": True,
        "source_matches_package": True,
    }
    require(set(review) == set(expected) | {"reviewed_at_utc"} and
            all(type(review.get(key)) is type(value) and review[key] == value
                for key, value in expected.items()),
            "native_independent_source_review_missing_or_not_fresh")
    try:
        stamp = datetime.fromisoformat(review["reviewed_at_utc"])
    except (TypeError, ValueError):
        raise workers.NativeMaterialWorkerError("native_source_review_timestamp_invalid") from None
    require(stamp.tzinfo is not None and stamp >= datetime.fromisoformat(receipt["finished_at_utc"]),
            "native_source_review_predates_fresh_attempt")
    proof = {**candidate, "schema": workers.TRAIN_CONTROL_SCHEMA,
             "status": workers.TRAIN_CONTROL_STATUS, "source_visual_review_pending": False,
             "source_visual_review_verified": True, "source_attachment_readback": True,
             "source_review_sha256": source_review_sha256,
             "source_frame_sha256": frame["sha256"], "source_asset_sha256": row["source_asset_sha256"]}
    workers.validate_train_control(proof, plan["native_worker_binding"])
    sha = _write_new(run_dir / "train-control.private.json", proof)
    return {"schema": workers.TRAIN_CONTROL_SCHEMA, "status": workers.TRAIN_CONTROL_STATUS,
            "train_control_sha256": sha, "source_review_sha256": source_review_sha256,
            "fresh_native_gui_controls": 1, "old_positive_credit": 0,
            "model_attempts": 0, "official_final_tasks_admitted": 0}


def _live_preflight(plan: dict, worker: Path) -> tuple[dict, Path]:
    """Run only behind --execute; never used by metadata preparation."""
    split = plan["split"]
    require(worker.name == split and
            os.environ.get("ENVLOOP_ODOO_WORKER_DIR") == str(worker),
            "native_original_split_worker_not_selected")
    private = worker / "private"
    _private_directory(private)
    for name, filename in CHECKPOINT_FILES.items():
        path = private / filename
        require(path.is_file() and not path.is_symlink() and path.stat().st_mode & 0o077 == 0 and
                digest(path.read_bytes()) == plan["checkpoint"][name],
                "native_frozen_checkpoint_or_baseline_changed")
    world = workers.private_json(private / "partition_cases.json")
    require(world.get("split") == split and type(world.get("cases")) is dict,
            "native_original_partition_changed")
    from enterprise_fallback.odoo18.partition_factory import source_asset
    by_id = {}
    for family in FAMILIES:
        cases = world["cases"].get(family)
        require(type(cases) is list and len(cases) == SPLITS[split][1],
                "native_partition_family_count_changed")
        for case in cases:
            require(case["id"] not in by_id, "native_partition_duplicate_task")
            by_id[case["id"]] = (family, case)
    require(set(by_id) == {row["task_id"] for row in plan["tasks"]},
            "native_roster_partition_identity_changed")
    for row in plan["tasks"]:
        family, case = by_id[row["task_id"]]
        asset = source_asset(case, world)
        require(family == row["family"] and
                digest(json.dumps(case, sort_keys=True).encode() + b"\n" + asset) == row["package_sha256"] and
                digest(asset) == row["source_asset_sha256"] and
                digest(case["prompt"].encode()) == row["visible_instruction_sha256"],
                "native_roster_source_or_instruction_hash_changed")
    return world, private


def run(*, plan_path: Path, worker_dir: Path, run_dir: Path,
        execute: bool = False, train_task_id: str | None = None,
        train_control_path: Path | None = None,
        train_control_sha256: str | None = None) -> dict:
    require(execute is True, "native_qualification_explicit_execute_required")
    plan = validate_plan(workers.private_json(plan_path))
    require(digest(plan_path.read_bytes()) == digest(canonical(plan)),
            "native_qualification_plan_must_be_canonical")
    binding = plan["native_worker_binding"]
    split = plan["split"]
    if split == "train":
        require(train_control_path is None and train_control_sha256 is None,
                "native_train_control_refuses_old_positive_credit")
        choices = [row for row in plan["tasks"] if row["family"] == "purchase" and
                   (train_task_id is None or row["task_id"] == train_task_id)]
        require(bool(choices), "native_train_first_control_purchase_task_required")
        rows = choices[:1]
        prerequisite_sha = None
    else:
        require(train_task_id is None and train_control_path is not None and
                type(train_control_sha256) is str and
                workers.HEX64.fullmatch(train_control_sha256) is not None,
                "native_full_split_requires_hash_bound_fresh_train_control")
        control = workers.validate_train_control(workers.private_json(
            train_control_path, train_control_sha256), binding)
        require(control["run_nonce_sha256"] != plan["run_nonce_sha256"],
                "native_train_and_qualification_nonce_must_differ")
        rows = plan["tasks"]
        prerequisite_sha = train_control_sha256
    worker = Path(worker_dir).resolve()
    run_dir = Path(run_dir)
    require(run_dir.parent.resolve() == (worker / "private" / "v066_native_material_controls").resolve() and
            run_dir.name == plan["fresh_run_directory_name"] and
            not run_dir.exists() and not run_dir.is_symlink(),
            "native_fresh_nonce_directory_required_no_resume_or_replay")
    world, private = _live_preflight(plan, worker)
    from tools import odoo_v066_scale_controller_v1 as controller
    modules = controller._modules(worker)
    lease = modules[-1]
    root = run_dir.parent
    if not root.exists():
        root.mkdir(mode=0o700)
    _private_directory(root)
    with controller._run_lock(root):
        workers.validate_binding(binding)
        run_dir.mkdir(mode=0o700)
        _write_new(run_dir / "batch-intent.private.json", {
            "schema": BATCH_SCHEMA, "status": "durable_before_first_original_odoo_service_call",
            "split": split, "plan_sha256": digest(plan_path.read_bytes()),
            "native_worker_binding_sha256": binding["binding_sha256"],
            "native_adapter_binding_sha256": plan["native_adapter_binding_sha256"],
            "run_nonce_hex": plan["run_nonce_hex"], "run_nonce_sha256": plan["run_nonce_sha256"],
            "expected_case_count": len(rows), "fresh_train_control_sha256": prerequisite_sha,
            "old_positive_credit": 0, "automatic_replay_authorized": False,
            "model_attempts": 0, "official_final_tasks_admitted": 0,
        })
        runner = workers.evaluator_module(binding)
        audits = []
        by_id = {case["id"]: (family, case) for family in FAMILIES for case in world["cases"][family]}
        for ordinal, metadata in enumerate(rows):
            workers.validate_binding(binding)
            row = _case_row(plan, metadata, prerequisite_sha)
            family, case = by_id[row["task_id"]]
            wrong = next(candidate for candidate in world["cases"][family] if candidate["id"] != case["id"])
            try:
                with lease.exclusive_worker_operation(controller.LEASE_OPERATION):
                    runner.execute_case(run_dir=run_dir, ordinal=ordinal, row=row,
                                        case=case, wrong=wrong, family=family, modules=modules)
                attempt = run_dir / f"attempt-{ordinal:03d}"
                audit = audit_case(plan=plan, row=row, attempt=attempt, worker_private=private)
                audit_sha = _write_new(attempt / "independent-audit.private.json", audit)
                audits.append({"task_id": row["task_id"], "family": family,
                               "attempt_sha256": digest((attempt / "attempt.private.json").read_bytes()),
                               "audit_sha256": audit_sha, "audit": audit})
            except BaseException as error:
                _write_new(run_dir / "failed.private.json", {
                    "schema": BATCH_SCHEMA, "status": "failed_preserve_attempt_no_automatic_replay",
                    "ordinal": ordinal, "error_type": type(error).__name__,
                    "run_nonce_sha256": plan["run_nonce_sha256"],
                    "completed_audits": len(audits), "old_positive_credit": 0,
                    "model_attempts": 0, "official_final_tasks_admitted": 0,
                })
                raise
        result = {
            "schema": BATCH_SCHEMA,
            "status": "full_native_material_gui_control_semantics_verified_source_visual_review_pending",
            "split": split, "fresh_native_gui_controls": len(audits),
            "expected_case_count": len(rows), "task_roster_sha256": digest(canonical(rows)),
            "native_worker_binding_sha256": binding["binding_sha256"],
            "native_adapter_binding_sha256": plan["native_adapter_binding_sha256"],
            "run_nonce_sha256": plan["run_nonce_sha256"],
            "plan_sha256": digest(canonical(plan)),
            "audits": audits, "source_visual_review_pending": True,
            "old_positive_credit": 0, "model_attempts": 0, "official_final_tasks_admitted": 0,
        }
        _write_new(run_dir / "result.private.json", result)
        if split == "train":
            one = audits[0]
            candidate = {**one["audit"], "schema": TRAIN_CANDIDATE_SCHEMA,
                     "status": TRAIN_CANDIDATE_STATUS, "split": "train", "family": "purchase",
                     "run_nonce_hex": plan["run_nonce_hex"],
                     "plan_sha256": result["plan_sha256"],
                     "attempt_sha256": one["attempt_sha256"], "audit_sha256": one["audit_sha256"]}
            candidate_sha = _write_new(run_dir / "train-control-candidate.private.json", candidate)
            return {"schema": BATCH_SCHEMA, "split": "train", "status": TRAIN_CANDIDATE_STATUS,
                    "fresh_native_gui_controls": 1, "train_candidate_sha256": candidate_sha,
                    "old_positive_credit": 0, "model_attempts": 0, "official_final_tasks_admitted": 0}
        return {key: value for key, value in result.items() if key != "audits"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    metadata_source = prep.add_mutually_exclusive_group(required=True)
    metadata_source.add_argument("--roster-metadata", type=Path)
    metadata_source.add_argument("--legacy-metadata-plan", type=Path)
    prep.add_argument("--split", choices=tuple(SPLITS))
    prep.add_argument("--metadata-plan-sha256")
    prep.add_argument("--private-plan", type=Path, required=True)
    prep.add_argument("--public-plan", type=Path, required=True)
    prep.add_argument("--native-binding", type=Path, required=True)
    live = sub.add_parser("run")
    live.add_argument("--plan", type=Path, required=True)
    live.add_argument("--worker-dir", type=Path, required=True)
    live.add_argument("--run-dir", type=Path, required=True)
    live.add_argument("--execute", action="store_true")
    live.add_argument("--train-task-id")
    live.add_argument("--train-control", type=Path)
    live.add_argument("--train-control-sha256")
    finalize = sub.add_parser("finalize-train-control")
    finalize.add_argument("--plan", type=Path, required=True)
    finalize.add_argument("--worker-dir", type=Path, required=True)
    finalize.add_argument("--run-dir", type=Path, required=True)
    finalize.add_argument("--source-review", type=Path, required=True)
    finalize.add_argument("--source-review-sha256", required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        if args.legacy_metadata_plan is not None:
            require(args.split is not None, "native_metadata_projection_requires_split")
            metadata = project_legacy_metadata(workers.private_json(
                args.legacy_metadata_plan, args.metadata_plan_sha256), args.split)
        else:
            require(args.split is None and args.metadata_plan_sha256 is None,
                    "native_dedicated_metadata_refuses_legacy_projection_flags")
            metadata = workers.private_json(args.roster_metadata)
        plan, public = prepare(metadata)
        _write_new(args.private_plan, plan)
        _write_new(args.native_binding, plan["native_worker_binding"])
        _write_new(args.public_plan, public, private=False)
        print(json.dumps(public, sort_keys=True))
    elif args.command == "run":
        result = run(plan_path=args.plan, worker_dir=args.worker_dir, run_dir=args.run_dir,
                     execute=args.execute, train_task_id=args.train_task_id,
                     train_control_path=args.train_control,
                     train_control_sha256=args.train_control_sha256)
        print(json.dumps(result, sort_keys=True))
    else:
        result = finalize_train_control(plan_path=args.plan, worker_dir=args.worker_dir,
                                        run_dir=args.run_dir, source_review_path=args.source_review,
                                        source_review_sha256=args.source_review_sha256)
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
