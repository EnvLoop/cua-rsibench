"""Independent offline pilot gate for future raw Odoo v0.6.6 GUI controls.

The gate derives positive/no-regression, wrong-object negative and reset from
saved SELECT-only snapshots and physical filestore references. It does not
create a task proof, call Odoo/Docker, or admit an official final task.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
import stat

from cursibench.scale_vision_proxy import Limits, image_from_bytes
from . import v066_requalification_plan as plan
from . import verify
from .offline_evidence_audit_v1 import NEGATIVE_CODES


ATTEMPT_SCHEMA = "envloop-odoo-v066-gui-control-attempt-v1"
GUI_SCHEMA = "envloop-odoo-v066-gui-control-trace-v1"
REVIEW_SCHEMA = "envloop-odoo-v066-independent-source-frame-review-v1"
PILOT_AUDIT_SCHEMA = "envloop-odoo-v066-gui-control-pilot-audit-v1"
LEASE_OPERATION = "v066_gui_requalify"
REFS = frozenset({
    "pre_restore", "baseline_sql", "source_frame", "source_review",
    "gui_trace", "positive_reload_frame", "positive_sql",
    "positive_filestore", "positive_store_paths", "negative_reload_frame",
    "negative_sql", "negative_filestore", "negative_store_paths",
    "post_restore", "restored_sql", "restored_filestore",
})
STAGES = ("pre_restore", "source_observed", "positive_reload",
          "positive_sql", "negative_reload", "negative_sql", "post_restore")
GUI_ACTIONS = {"click", "double_click", "type", "key", "scroll", "drag",
               "wait", "finish"}
HEX = re.compile(r"[0-9a-f]{64}\Z")


class PilotEvidenceError(ValueError):
    pass


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise PilotEvidenceError(reason)


def _stamp(value: object) -> datetime:
    require(type(value) is str, "pilot_timestamp_invalid")
    try:
        result = datetime.fromisoformat(value)
    except ValueError:
        raise PilotEvidenceError("pilot_timestamp_invalid") from None
    require(result.tzinfo is not None, "pilot_timestamp_invalid")
    return result


def _private(path: Path, *, directory: bool = False) -> None:
    require(not path.is_symlink() and
            (path.is_dir() if directory else path.is_file()) and
            stat.S_IMODE(path.stat().st_mode) & 0o077 == 0,
            "pilot_private_evidence_missing_or_permissive")


def _json(path: Path) -> dict:
    _private(path)
    require(path.stat().st_size <= 8_000_000, "pilot_json_too_large")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PilotEvidenceError("pilot_json_invalid") from None
    require(type(value) is dict, "pilot_json_invalid")
    return value


def _ref(directory: Path, raw: object, *, image: bool = False) -> tuple[Path, bytes]:
    require(type(raw) is dict and set(raw) == {"path", "sha256"} and
            type(raw["path"]) is str and
            type(raw["sha256"]) is str and
            HEX.fullmatch(raw["sha256"]) is not None,
            "pilot_artifact_reference_invalid")
    relative = Path(raw["path"])
    require(not relative.is_absolute() and relative.parts and
            all(part not in (".", "..") for part in relative.parts) and
            len(relative.parts) <= 2,
            "pilot_artifact_path_unsafe")
    path = directory / relative
    require(path.resolve().is_relative_to(directory.resolve()),
            "pilot_artifact_path_unsafe")
    _private(path)
    if path.parent != directory:
        _private(path.parent, directory=True)
    data = path.read_bytes()
    require(plan.sha(data) == raw["sha256"], "pilot_artifact_bytes_changed")
    if image:
        try:
            _, metadata = image_from_bytes(data, Limits())
        except Exception:
            raise PilotEvidenceError("pilot_frame_invalid") from None
        require(metadata["format"] == "png" and
                (metadata["width"], metadata["height"]) == (1440, 1000),
                "pilot_frame_viewport_changed")
    return path, data


def _artifact_json(directory: Path, raw: object) -> dict:
    _path, data = _ref(directory, raw)
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PilotEvidenceError("pilot_artifact_json_invalid") from None
    require(type(value) is dict, "pilot_artifact_json_invalid")
    return value


def _lease(events_path: Path, pid: int, start: datetime,
           finish: datetime) -> bool:
    _private(events_path)
    events = [json.loads(line) for line in events_path.read_text().splitlines()]
    for index, event in enumerate(events):
        if (event.get("operation") != LEASE_OPERATION or
                event.get("event") != "acquired" or
                event.get("pid") != pid or
                _stamp(event.get("at_utc")) > start):
            continue
        release = next((later for later in events[index + 1:]
                        if later.get("operation") == LEASE_OPERATION and
                        later.get("event") == "released" and
                        later.get("pid") == pid), None)
        if release is None or _stamp(release.get("at_utc")) < finish:
            continue
        if any(start <= _stamp(other.get("at_utc")) <= finish and
               (other.get("pid") != pid or
                other.get("operation") != LEASE_OPERATION)
               for other in events):
            return False
        return True
    return False


def _pure_score(family: str, task_id: str, gold: dict,
                baseline: dict, observed: dict, frozen_files: dict,
                actual_files: dict, actual_paths: dict) -> dict:
    functions = {"purchase": verify.evaluate,
                 "inventory": verify.evaluate_replenishment,
                 "sales": verify.evaluate_sales,
                 "crm": verify.evaluate_crm}
    require(family in functions, "pilot_family_unknown")
    try:
        score = functions[family](task_id, gold, baseline, observed)
        extra = verify.protected_source_file_differences(
            baseline, frozen_files, actual_files)
        extra += verify.protected_source_store_path_differences(
            baseline, actual_paths)
    except (KeyError, TypeError, ValueError, RuntimeError):
        raise PilotEvidenceError("pilot_saved_state_unverifiable") from None
    differences = sorted(set(score["difference_codes"] + extra))
    return {"reward": 0.0 if differences else 1.0,
            "difference_codes": differences,
            "protected_source_files_checked":
                len({row["checksum"] for row in baseline["attachments"]})}


def _gui_trace(directory: Path, receipt: dict, row: dict,
               artifacts: dict, finish: datetime) -> tuple[int, int]:
    gui = artifacts["gui_trace"]
    require(gui.get("schema") == GUI_SCHEMA and
            gui.get("task_binding_sha256") == row["task_binding_sha256"] and
            type(gui.get("actions")) is list and
            2 <= len(gui["actions"]) <= 90,
            "pilot_gui_trace_invalid")
    source_sha = receipt["refs"]["source_frame"]["sha256"]
    positive_reload = receipt["refs"]["positive_reload_frame"]["sha256"]
    negative_reload = receipt["refs"]["negative_reload_frame"]["sha256"]
    review = artifacts["source_review"]
    require(review.get("schema") == REVIEW_SCHEMA and
            review.get("decision") == "source_visible_in_original_odoo_gui" and
            review.get("reviewer_role") == "independent_visual_source_reviewer" and
            type(review.get("reviewer_id_sha256")) is str and
            HEX.fullmatch(review["reviewer_id_sha256"]) is not None and
            review["reviewer_id_sha256"] != receipt["controller_id_sha256"] and
            review.get("source_frame_sha256") == source_sha and
            review.get("source_asset_sha256") == row["source_asset_sha256"] and
            review.get("source_label") == row["source_label"] and
            _stamp(review.get("reviewed_at_utc")) >= finish,
            "pilot_independent_source_frame_review_missing")
    positive = negative = 0
    frame_hashes = set()
    for index, action in enumerate(gui["actions"]):
        require(type(action) is dict and set(action) ==
                {"phase", "step", "frame", "contract_receipt"} and
                action["phase"] in ("positive", "negative") and
                action["step"] == index,
                "pilot_gui_action_sequence_invalid")
        _, raw = _ref(directory, action["frame"], image=True)
        frame_sha = plan.sha(raw)
        frame_hashes.add(frame_sha)
        contract = action["contract_receipt"]
        require(type(contract) is dict and
                contract.get("action_profile") == plan.PROFILE and
                contract.get("task_binding_sha256") == row["package_sha256"] and
                contract.get("task_id_sha256") == plan.sha(row["task_id"].encode()) and
                contract.get("step") == index and
                contract.get("frame_id_sha256") is not None and
                HEX.fullmatch(contract["frame_id_sha256"]) is not None and
                type(contract.get("screenshot")) is dict and
                contract["screenshot"].get("sha256") == frame_sha and
                contract["screenshot"].get("width") == 1440 and
                contract["screenshot"].get("height") == 1000 and
                contract.get("action_type") in GUI_ACTIONS and
                contract.get("error_code") is None,
                "pilot_v066_current_frame_action_binding_invalid")
        if action["phase"] == "positive":
            require(negative == 0, "pilot_gui_phase_order_invalid")
            positive += 1
        else:
            negative += 1
    require(positive > 0 and negative > 0 and
            source_sha in frame_hashes and
            positive_reload != negative_reload,
            "pilot_gui_source_or_dual_phase_missing")
    return positive, negative


def audit_pilot(*, private_plan_path: Path, public_plan_path: Path,
                workers_root: Path, attempt_dir: Path) -> dict:
    private_plan = _json(Path(private_plan_path))
    public_plan = json.loads(Path(public_plan_path).read_bytes())
    require(type(public_plan) is dict and
            public_plan.get("schema") == plan.PUBLIC_SCHEMA and
            public_plan.get("status") == "source_bound_plan_only_no_current_gui_proofs" and
            public_plan.get("private_plan_sha256") ==
            plan.sha(plan.canonical(private_plan)) and
            public_plan.get("new_six_cell_ratification_sha256") ==
            plan.RATIFICATION_SHA256 and
            public_plan.get("candidate_counts") ==
            {"train": 20, "selection": 20, "official_hidden": 100} and
            public_plan.get("task_set_manifest_sha256") ==
            private_plan.get("task_set_manifest_sha256") and
            public_plan.get("pilot_auditor_source_sha256") ==
            plan.sha(Path(__file__).read_bytes()) and
            public_plan.get("planner_source_sha256") ==
            plan.sha(Path(plan.__file__).read_bytes()),
            "pilot_public_plan_source_binding_invalid")
    require(private_plan.get("ratification_sha256") ==
            plan.RATIFICATION_SHA256 and
            private_plan.get("pilot_auditor_source_sha256") ==
            public_plan["pilot_auditor_source_sha256"] and
            private_plan.get("odoo_source_sha256s") ==
            {relative: plan.sha((plan.ROOT / relative).read_bytes())
             for relative in plan.ODOO_FILES} and
            private_plan.get("common_action_source_sha256s") ==
            {name: plan.sha((plan.ROOT / relative).read_bytes())
             for name, relative in plan.COMMON_FILES.items()},
            "pilot_current_source_changed")
    task_sets = private_plan.get("tasks")
    require(type(task_sets) is dict and
            set(task_sets) == {"train", "selection", "official_hidden"} and
            {key: len(value) for key, value in task_sets.items()} ==
            {"train": 20, "selection": 20, "official_hidden": 100} and
            len({row.get("task_id") for rows in task_sets.values()
                 for row in rows}) == 140,
            "pilot_private_plan_task_coverage_invalid")
    require(private_plan.get("schema") == plan.PRIVATE_SCHEMA and            private_plan.get("status") == "planned_no_current_v066_gui_proofs" and
            private_plan.get("official_final_tasks_admitted") == 0,
            "pilot_plan_invalid")
    attempt_dir = Path(attempt_dir)
    _private(attempt_dir, directory=True)
    attempt_path = attempt_dir / "attempt.private.json"
    require(attempt_path.is_file(), "pilot_attempt_missing")
    receipt = _json(attempt_path)
    pilot = private_plan["pilot"]
    rows = private_plan["tasks"]["train"]
    matches = [row for row in rows if row["task_id"] == pilot["task_id"]]
    require(len(matches) == 1 and pilot["split"] == "train", "pilot_plan_identity_invalid")
    row = matches[0]
    binding = {key: row.get(key) for key in (
        "ratification_sha256", "action_profile", "split", "task_id",
        "package_sha256", "source_asset_sha256",
        "visible_instruction_sha256", "checkpoint", "odoo_adapter_sha256")}
    require(row.get("fresh_v066_gui_proof_status") == "pending" and
            row.get("split") == "train" and
            row.get("ratification_sha256") == plan.RATIFICATION_SHA256 and
            row.get("action_profile") == plan.PROFILE and
            row.get("checkpoint") == private_plan["checkpoints"]["train"] and
            row.get("odoo_adapter_sha256") ==
            private_plan["odoo_source_sha256s"][plan.ODOO_FILES[0]] and
            row.get("task_binding_sha256") == plan.sha(plan.canonical(binding)),
            "pilot_task_binding_not_rederived")
    require(type(receipt) is dict and set(receipt) == {
                "schema", "status", "plan_sha256", "ratification_sha256",
                "split", "task_id", "package_sha256", "task_binding_sha256",
                "worker_pid", "controller_id_sha256", "started_at_utc",
                "finished_at_utc", "lease_operation", "stage_timestamps",
                "refs"} and
            receipt["schema"] == ATTEMPT_SCHEMA and
            receipt["status"] == "completed_with_raw_evaluator_evidence" and
            receipt["plan_sha256"] == plan.sha(plan.canonical(private_plan)) and
            receipt["ratification_sha256"] == private_plan["ratification_sha256"] and
            receipt["split"] == "train" and
            receipt["task_id"] == row["task_id"] and
            receipt["package_sha256"] == row["package_sha256"] and
            receipt["task_binding_sha256"] == row["task_binding_sha256"] and
            type(receipt["worker_pid"]) is int and receipt["worker_pid"] > 0 and
            type(receipt["controller_id_sha256"]) is str and
            HEX.fullmatch(receipt["controller_id_sha256"]) is not None and
            receipt["lease_operation"] == LEASE_OPERATION and
            type(receipt["refs"]) is dict and set(receipt["refs"]) == REFS,
            "pilot_attempt_identity_or_artifacts_invalid")
    start = _stamp(receipt["started_at_utc"])
    finish = _stamp(receipt["finished_at_utc"])
    stage_raw = receipt["stage_timestamps"]
    require(type(stage_raw) is dict and set(stage_raw) == set(STAGES),
            "pilot_stage_timestamps_invalid")
    stamps = {name: _stamp(stage_raw[name]) for name in STAGES}
    require(start <= stamps[STAGES[0]] and
            all(stamps[a] <= stamps[b] for a, b in zip(STAGES, STAGES[1:])) and
            stamps[STAGES[-1]] <= finish,
            "pilot_stage_order_invalid")
    worker_private = Path(workers_root) / "train" / "private"
    _private(worker_private, directory=True)
    task_manifest = _json(worker_private / "task_set_manifest.json")
    require(plan.sha(json.dumps(task_manifest, sort_keys=True).encode()) ==
            private_plan["task_set_manifest_sha256"] and
            len([item for item in task_manifest["train"]
                 if item.get("task_id") == row["task_id"] and
                 item.get("package_sha256") == row["package_sha256"]]) == 1,
            "pilot_current_private_taskset_changed")
    source_hashes = _json(worker_private / "source_hashes.json")
    world = _json(worker_private / "partition_cases.json")
    cases = [case for family_cases in world.get("cases", {}).values()
             for case in family_cases if case.get("id") == row["task_id"]]
    require(world.get("split") == "train" and len(cases) == 1 and
            source_hashes.get(row["task_id"]) == row["source_asset_sha256"] and
            plan.sha(cases[0]["prompt"].encode()) ==
            row["visible_instruction_sha256"],
            "pilot_current_private_case_or_source_changed")
    checkpoint_receipt = _json(worker_private / "checkpoint_receipt.json")
    checkpoint = private_plan["checkpoints"]["train"]
    require(checkpoint_receipt.get("db_sha256") == checkpoint["db_sha256"] and
            checkpoint_receipt.get("filestore_sha256") ==
            checkpoint["filestore_sha256"] and
            plan.sha((worker_private / "baseline.pgcustom").read_bytes()) ==
            checkpoint["db_sha256"] and
            plan.sha((worker_private / "baseline-filestore.tgz").read_bytes()) ==
            checkpoint["filestore_sha256"],
            "pilot_current_checkpoint_archives_changed")
    require(attempt_dir.resolve().is_relative_to(worker_private.resolve()),
            "pilot_attempt_not_in_train_private_worker")
    require(_lease(worker_private / "worker-lease-events.jsonl",
                   receipt["worker_pid"], start, finish),
            "pilot_exclusive_worker_lease_missing")
    artifacts = {}
    for name, reference in receipt["refs"].items():
        if name.endswith("frame"):
            _ref(attempt_dir, reference, image=True)
        else:
            artifacts[name] = _artifact_json(attempt_dir, reference)
    positive_actions, negative_actions = _gui_trace(
        attempt_dir, receipt, row, artifacts, finish)
    for key in ("pre_restore", "post_restore"):
        restored = artifacts[key]
        require(restored.get("status") == "restored" and
                restored.get("business_snapshot_equal") is True and
                restored.get("physical_filestore_equal_before_web_restart") is True and
                restored.get("db_sha256") == checkpoint["db_sha256"] and
                restored.get("filestore_sha256") == checkpoint["filestore_sha256"],
                "pilot_physical_reset_not_exact")
    baseline_path = worker_private / "baseline_snapshot.json"
    baseline = _json(baseline_path)
    require(plan.sha(baseline_path.read_bytes()) ==
            checkpoint["baseline_snapshot_sha256"] and
            artifacts["baseline_sql"] == baseline and
            artifacts["restored_sql"] == baseline,
            "pilot_baseline_or_restored_sql_changed")
    frozen_path = worker_private / "baseline-filestore-manifest.json"
    frozen_files = _json(frozen_path)
    require(plan.sha(frozen_path.read_bytes()) ==
            checkpoint["baseline_filestore_manifest_sha256"],
            "pilot_frozen_filestore_manifest_changed")
    try:
        post_web_source_differences = verify.protected_source_file_differences(
            baseline, frozen_files, artifacts["restored_filestore"])
    except (KeyError, TypeError, ValueError, RuntimeError):
        raise PilotEvidenceError("pilot_restored_source_files_unverifiable") from None
    require(post_web_source_differences == [],
            "pilot_restored_protected_source_files_changed")
    gold_filename = {"purchase": "development_gold.json",
                     "inventory": "replenishment_gold.json",
                     "sales": "sales_gold.json", "crm": "crm_gold.json"}[row["family"]]
    gold = _json(worker_private / gold_filename)
    require(row["task_id"] in gold, "pilot_gold_case_missing")
    target = gold[row["task_id"]]
    source_count = 3 * 5 + 1
    require(len({item["checksum"] for item in baseline["attachments"]}) ==
            source_count, "pilot_protected_source_set_changed")
    baseline_paths = {str(item["id"]):
                      f"{item['checksum'][:2]}/{item['checksum']}"
                      for item in baseline["attachments"]}
    baseline_score = _pure_score(row["family"], row["task_id"], target,
                                 baseline, baseline, frozen_files,
                                 frozen_files, baseline_paths)
    positive = _pure_score(row["family"], row["task_id"], target,
                           baseline, artifacts["positive_sql"], frozen_files,
                           artifacts["positive_filestore"],
                           artifacts["positive_store_paths"])
    negative = _pure_score(row["family"], row["task_id"], target,
                           baseline, artifacts["negative_sql"], frozen_files,
                           artifacts["negative_filestore"],
                           artifacts["negative_store_paths"])
    require(baseline_score["reward"] == 0.0 and
            positive["reward"] == 1.0 and
            positive["difference_codes"] == [] and
            negative["reward"] == 0.0 and
            negative["difference_codes"] == [NEGATIVE_CODES[row["family"]]] and
            positive["protected_source_files_checked"] == source_count and
            negative["protected_source_files_checked"] == source_count and
            artifacts["positive_sql"] != baseline and
            artifacts["negative_sql"] != artifacts["positive_sql"],
            "pilot_independent_saved_state_or_negative_control_failed")
    return {
        "schema": PILOT_AUDIT_SCHEMA,
        "status": "fresh_train_candidate_control_derived_from_raw_evidence",
        "split": "train",
        "ratification_sha256": private_plan["ratification_sha256"],
        "private_plan_sha256": plan.sha(plan.canonical(private_plan)),
        "private_attempt_sha256": plan.sha(attempt_path.read_bytes()),
        "positive_gui_actions": positive_actions,
        "negative_gui_actions": negative_actions,
        "independent_baseline_reward": baseline_score["reward"],
        "independent_positive_reward": positive["reward"],
        "independent_negative_reward": negative["reward"],
        "negative_difference_code": NEGATIVE_CODES[row["family"]],
        "protected_source_files_checked": source_count,
        "post_web_restart_protected_source_bytes_equal": True,
        "full_filestore_reset_before_web_restart_exact": True,
        "fresh_train_candidate_controls_qualified": 1,
        "selection_candidate_controls_qualified": 0,
        "hidden_candidate_controls_qualified": 0,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-plan", type=Path, required=True)
    parser.add_argument("--public-plan", type=Path, required=True)
    parser.add_argument("--workers-root", type=Path, required=True)
    parser.add_argument("--attempt-dir", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    result = audit_pilot(
        private_plan_path=args.private_plan,
        public_plan_path=args.public_plan,
        workers_root=args.workers_root,
        attempt_dir=args.attempt_dir)
    plan.write_new(args.public_out, result, private=False)
    print(json.dumps(result, sort_keys=True))
