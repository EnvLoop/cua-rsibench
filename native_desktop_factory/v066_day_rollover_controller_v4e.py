"""Bounded, source-bound Desktop evaluator continuation after v4d precreate stop.

The immutable v4d freeze has no dispatch authority. A separately reviewed,
one-batch private permit is required for this controller and its child. Every
new attempt is charged before E2B create, stdout/stderr are fsynced, and an
uncertain outcome stops the batch without replay. These are evaluator controls,
not official final admissions or model outcomes.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import sys

from . import v066_day_rollover_continuation_v2 as v2
from . import v066_day_rollover_continuation_v3 as v3
from . import v066_day_rollover_durable_output_v4d as durable_output
from . import v066_day_rollover_precreate_freeze_v4d as v4d
from .reconcile_interrupted_sweep import active_hashes
from .v066_day_rollover_durable_child_v4e import _old_paths
from .v066_day_rollover_five_root_v4e import five_root_budget
from .v066_final_freeze import LEASE_SECONDS, digest, intent_budget
from .v066_scoped_profile_final_controller import _final_rows
from .v066_storage_budget import audit as storage_audit


SCHEMA = "cua-native-wdi-v066-five-root-freeze-private-v4e"
PUBLIC_SCHEMA = "cua-native-wdi-v066-five-root-freeze-public-v4e"
RUN_SCHEMA = "cua-native-wdi-v066-v4e-bounded-run-private-v1"
PERMIT_SCHEMA = "cua-native-wdi-v066-v4e-reviewed-dispatch-permit-private-v1"
CHILD = "native_desktop_factory.v066_day_rollover_durable_child_v4e"
MAIN_V4D_PUBLIC_SHA256 = (
    "f06958825c1d2b5283a4e3ba33c14ee6fcb20e896055d66f31c4dd5f064b6485"
)
SOURCE_NAMES = (
    "native_desktop_factory/qwen_v066_adapter_v4_strict.py",
    "native_desktop_factory/v066_day_rollover_durable_child_v4e.py",
    "native_desktop_factory/v066_day_rollover_controller_v4e.py",
    "native_desktop_factory/v066_day_rollover_five_root_v4e.py",
    "native_desktop_factory/v066_day_rollover_independent_audit_v4e.py",
    "native_desktop_factory/v066_day_rollover_durable_output_v4d.py",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _private(path: Path) -> bytes:
    if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o077:
        raise ValueError("Private v4e source or run evidence is absent or unsafe")
    return path.read_bytes()


def _sources() -> dict[str, str]:
    repo = Path(__file__).resolve().parents[1]
    return {name: digest((repo / name).read_bytes()) for name in SOURCE_NAMES}


def _v4d_lineage(v4d_freeze: Path) -> tuple[dict, bytes, dict, list[dict]]:
    raw = _private(v4d_freeze)
    frozen = json.loads(raw)
    repo = Path(__file__).resolve().parents[1]
    if (frozen.get("schema") != v4d.SCHEMA or
            frozen.get("status") != "frozen_before_new_v4d_create" or
            frozen.get("dispatch_authorized") is not False or
            frozen.get("same_intent_replay_authorized") is not False or
            frozen.get("current_four_root_full_lease_intents") != 56 or
            frozen.get("never_intended_ids") != 88 or
            frozen.get("official_final_admissions") != 0 or
            frozen.get("source_sha256s") !=
                v4d._source_hashes(repo, v4d.V4D_SOURCE_NAMES)):
        raise ValueError("Main v4d source-only freeze changed")
    public_raw = Path(frozen["public_path"]).read_bytes()
    public = json.loads(public_raw)
    if (public.get("schema") != v4d.PUBLIC_SCHEMA or
            public.get("private_freeze_sha256") != digest(raw) or
            public.get("dispatch_authorized") is not False or
            digest(public_raw) != MAIN_V4D_PUBLIC_SHA256):
        raise ValueError("Main v4d public source binding changed")
    old_v4c = json.loads(_private(Path(frozen["v4c_freeze_path"])))
    old_v3 = json.loads(_private(Path(old_v4c["v3_freeze_path"])))
    old_v2 = json.loads(_private(Path(old_v3["base_freeze_path"])))
    historical = old_v2["frozen_full100_source_sha256s"]
    if (len(historical) != 35 or
            any(digest((repo / name).read_bytes()) != expected
                for name, expected in historical.items())):
        raise ValueError("Original 35-file Desktop evaluator source changed")
    paths = _old_paths({"v4d_freeze_path": str(v4d_freeze)})
    inventory_raw, rows = _final_rows(paths["candidate_root"])
    roster = [row["task_id"] for row in rows]
    roster_sha = digest((json.dumps(roster, separators=(",", ":")) + "\n").encode())
    if (len(rows) != 100 or
            digest(inventory_raw) != frozen["candidate_inventory_sha256"] or
            roster_sha != frozen["sorted_final_roster_sha256"]):
        raise ValueError("v4d frozen sorted 100-task roster changed")
    return frozen, raw, paths, rows


def prepare(*, v4d_freeze: Path, freeze: Path, public: Path,
            active_probe=active_hashes) -> dict:
    if freeze.exists() or public.exists():
        raise ValueError("Exclusive private/public v4e freeze paths required")
    old, old_raw, paths, rows = _v4d_lineage(v4d_freeze)
    new_root = Path(old["new_attempts_root"])
    if new_root.exists():
        raise ValueError("v4e fifth root must be unused at source freeze")
    # Reopen v4c no-create proof and all eight saved GUI/profile trios before
    # freezing the fifth root. Its stopped intent remains part of old 56.
    inspected = v4d.inspect(
        v4c_freeze=Path(old["v4c_freeze_path"]),
        terminal_path=Path(old["v4c_terminal_batch_path"]),
        public_audit_path=Path(old["v4c_public_terminal_audit_path"]),
        forensic_root=Path(old["private_forensic_root"]),
        new_attempts_root=new_root, query_provider=False)
    if (inspected["old_v4c_freeze_sha256"] !=
            old["old_v4c_freeze_sha256"] or
            inspected["precreate_intent_sha256"] !=
            old["precreate_intent_sha256"]):
        raise ValueError("v4d no-create provenance changed")
    budget = five_root_budget(
        original_root=paths["old_original_root"],
        failed_root=paths["old_caret_root"],
        failed_scoped_root=paths["old_failed_scoped_root"],
        date_amended_root=paths["attempts_root"], new_root=new_root,
        proposed_new_intents=267)
    if budget["combined_full_lease_intents"] != 323:
        raise ValueError("Five-root 88-trio plus clone reservation changed")
    active, active_count = active_probe()
    if active or active_count:
        raise ValueError("Provider must be active-zero before v4e freeze")
    value = {
        "schema": SCHEMA,
        "status": "frozen_without_dispatch_authority",
        "recorded_utc": _now(),
        "v4d_freeze_path": str(v4d_freeze.resolve()),
        "v4d_freeze_sha256": digest(old_raw),
        "v4d_public_sha256": digest(Path(old["public_path"]).read_bytes()),
        "public_path": str(public.resolve()),
        "new_attempts_root": str(new_root.resolve()),
        "candidate_inventory_sha256": old["candidate_inventory_sha256"],
        "sorted_final_roster_sha256": old["sorted_final_roster_sha256"],
        "historical_first_eleven_task_tree_sha256s":
            json.loads(_private(Path(old["v4c_freeze_path"])))[
                "first_eleven_task_tree_sha256s"],
        "old_precreate_budget_sha256": old["precreate_budget_sha256"],
        "old_precreate_intent_sha256": old["precreate_intent_sha256"],
        "old_bridge_sha256": digest(_private(paths["bridge_path"])),
        "source_sha256s": _sources(),
        "untouched_roster_start_index": 12,
        "untouched_task_count": 88,
        "clone_roster_index": 11,
        "maximum_new_full_trios_for_clone": 1,
        "projected_five_root_full_lease_intents": 323,
        "projected_five_root_reserved_usd_upper":
            budget["combined_conservative_reserved_usd"],
        "one_or_two_ids_per_root_batch": True,
        "same_intent_replay_authorized": False,
        "automatic_clone_retry_authorized": False,
        "dispatch_authorized": False,
        "official_final_admissions": 0,
        "official_final_model_attempts": 0,
    }
    private_sha = v3._write_new(freeze, value)
    published = {
        "schema": PUBLIC_SCHEMA,
        "status": "source_frozen_pending_independent_dispatch_review",
        "private_freeze_sha256": private_sha,
        "v4d_main_freeze_sha256": value["v4d_freeze_sha256"],
        "v4d_main_public_sha256": value["v4d_public_sha256"],
        "candidate_inventory_sha256": value["candidate_inventory_sha256"],
        "sorted_final_roster_sha256": value["sorted_final_roster_sha256"],
        "source_sha256s": value["source_sha256s"],
        "historical_complete_trios": 8,
        "historical_partial_logical_ids": 4,
        "untouched_task_count": 88,
        "retained_four_root_full_lease_intents": 56,
        "projected_five_root_full_lease_intents": 323,
        "projected_five_root_reserved_usd_upper":
            value["projected_five_root_reserved_usd_upper"],
        "same_intent_replay_authorized": False,
        "automatic_clone_retry_authorized": False,
        "dispatch_authorized": False,
        "official_final_admissions": 0,
        "official_final_model_attempts": 0,
    }
    v3._write_new(public, published, public=True)
    return published


def validate_source(*, freeze: Path, include_attempt_audit: bool = True
                    ) -> tuple[dict, dict, list[dict], dict | None]:
    raw = _private(freeze)
    frozen = json.loads(raw)
    if (frozen.get("schema") != SCHEMA or
            frozen.get("status") != "frozen_without_dispatch_authority" or
            frozen.get("dispatch_authorized") is not False or
            frozen.get("automatic_clone_retry_authorized") is not False or
            frozen.get("same_intent_replay_authorized") is not False or
            frozen.get("official_final_admissions") != 0 or
            frozen.get("source_sha256s") != _sources()):
        raise ValueError("v4e source freeze or no-dispatch boundary changed")
    public = json.loads(Path(frozen["public_path"]).read_bytes())
    if (public.get("schema") != PUBLIC_SCHEMA or
            public.get("private_freeze_sha256") != digest(raw) or
            public.get("source_sha256s") != frozen["source_sha256s"]):
        raise ValueError("Published v4e source binding changed")
    old, old_raw, paths, rows = _v4d_lineage(Path(frozen["v4d_freeze_path"]))
    if (digest(old_raw) != frozen["v4d_freeze_sha256"] or
            digest(Path(old["public_path"]).read_bytes()) !=
                frozen["v4d_public_sha256"] or
            old["new_attempts_root"] != frozen["new_attempts_root"] or
            digest(_private(paths["bridge_path"])) !=
                frozen["old_bridge_sha256"]):
        raise ValueError("v4e old four-root or v4d lineage changed")
    five_root_budget(
        original_root=paths["old_original_root"],
        failed_root=paths["old_caret_root"],
        failed_scoped_root=paths["old_failed_scoped_root"],
        date_amended_root=paths["attempts_root"],
        new_root=Path(frozen["new_attempts_root"]))
    audit = None
    if include_attempt_audit:
        from .v066_day_rollover_independent_audit_v4e import audit as readback
        audit = readback(freeze=freeze)
    return frozen, paths, rows, audit


def _select(*, frozen: dict, rows: list[dict], audit: dict,
            mode: str, max_new_ids: int) -> list[dict]:
    if not 1 <= max_new_ids <= 2 or mode not in ("untouched", "clone"):
        raise ValueError("v4e batch must be one or two IDs in one mode")
    if mode == "clone":
        if max_new_ids != 1 or audit["clone_complete"]:
            raise ValueError("Clone is separately eligible for one full trio")
        return [rows[11]]
    start = 12 + audit["untouched_complete_prefix"]
    return rows[start:start + max_new_ids]


def plan(*, freeze: Path, mode: str = "untouched",
         max_new_ids: int = 1) -> dict:
    frozen, paths, rows, audited = validate_source(freeze=freeze)
    selected = _select(frozen=frozen, rows=rows, audit=audited,
                       mode=mode, max_new_ids=max_new_ids)
    budget = five_root_budget(
        original_root=paths["old_original_root"],
        failed_root=paths["old_caret_root"],
        failed_scoped_root=paths["old_failed_scoped_root"],
        date_amended_root=paths["attempts_root"],
        new_root=Path(frozen["new_attempts_root"]),
        proposed_new_intents=3 * len(selected))
    return {
        "status": "offline_v4e_bounded_plan",
        "mode": mode,
        "new_ids_selected": len(selected),
        "historical_complete_trios": 8,
        "new_untouched_complete_trios": audited["untouched_complete_prefix"],
        "clone_complete": audited["clone_complete"],
        "projected_five_root_full_lease_intents":
            budget["combined_full_lease_intents"],
        "projected_five_root_reserved_usd_upper":
            budget["combined_conservative_reserved_usd"],
        "dispatch_authorized": False,
        "official_final_admissions": 0,
    }


def _checked_permit(*, freeze: Path, frozen: dict, permit_path: Path,
                    mode: str, selected: list[dict], batch_number: int,
                    current_audit: dict | None = None) -> bytes:
    raw = _private(permit_path)
    permit = json.loads(raw)
    selected_ids = [row["task_id"] for row in selected]
    selected_sha = digest((json.dumps(selected_ids, separators=(",", ":")) +
                           "\n").encode())
    review_path_value = permit.get("independent_review_path")
    if type(review_path_value) is not str or not Path(review_path_value).is_absolute():
        raise ValueError("Independent v4e review path missing")
    review_raw = _private(Path(review_path_value))
    review = json.loads(review_raw)
    if (permit.get("schema") != PERMIT_SCHEMA or
            permit.get("status") != "independently_reviewed_one_batch" or
            permit.get("dispatch_authorized") is not True or
            permit.get("freeze_sha256") != digest(_private(freeze)) or
            permit.get("source_sha256s") != frozen["source_sha256s"] or
            permit.get("mode") != mode or
            permit.get("batch_number") != batch_number or
            permit.get("maximum_new_ids") != len(selected) or
            permit.get("selected_private_task_ids_sha256") != selected_sha or
            permit.get("same_intent_replay_authorized") is not False or
            permit.get("new_attempts_root") != frozen["new_attempts_root"] or
            permit.get("independent_review_sha256") != digest(review_raw) or
            review.get("schema") !=
                "cua-native-wdi-v066-v4e-independent-preflight-review-private-v1" or
            review.get("status") != "accepted_for_exact_one_batch" or
            review.get("freeze_sha256") != digest(_private(freeze)) or
            review.get("source_sha256s") != frozen["source_sha256s"] or
            review.get("mode") != mode or
            review.get("batch_number") != batch_number or
            review.get("selected_private_task_ids_sha256") != selected_sha or
            review.get("maximum_new_ids") != len(selected) or
            review.get("provider_active_at_review") != 0 or
            review.get("current_independent_audit", {}).get(
                "official_final_admissions") != 0 or
            (current_audit is not None and
             review.get("current_independent_audit") != current_audit)):
        raise ValueError("Separate one-batch v4e review permit absent")
    return raw


def _task(*, row: dict, frozen: dict, paths: dict, freeze: Path,
          permit: Path, run_dir: Path) -> dict:
    root = Path(frozen["new_attempts_root"])
    result = {"private_task_id": row["task_id"], "attempts": []}
    for attempt in v3.ATTEMPTS:
        v3._sdk_and_credential()
        power = v3._power_snapshot()
        active, count = active_hashes()
        if active or count:
            result["status"] = "stopped_for_provider_cleanup_audit"
            return result
        budget = five_root_budget(
            original_root=paths["old_original_root"],
            failed_root=paths["old_caret_root"],
            failed_scoped_root=paths["old_failed_scoped_root"],
            date_amended_root=paths["attempts_root"], new_root=root,
            proposed_new_intents=1)
        storage = storage_audit(root)
        if storage["dispatch_storage_ready"] is not True:
            result["status"] = "storage_budget_exhausted"
            return result
        attempt_dir = root / row["task_id"] / attempt
        if attempt_dir.exists() or attempt_dir.is_symlink():
            result["status"] = "existing_attempt_refused"
            return result
        attempt_dir.mkdir(parents=True, mode=0o700)
        attempt_dir.parent.chmod(0o700)
        attempt_dir.chmod(0o700)
        v3._sync_dir(attempt_dir.parent)
        v3._sync_dir(root)
        budget_receipt = {
            "schema": "cua-native-wdi-v066-precreate-budget-private-v3",
            "status": "fsynced_before_provider_create", "created_utc": _now(),
            "task_id": row["task_id"], "attempt": attempt,
            "five_root_budget": budget,
            "fresh_lane_budget": intent_budget(root, proposed_new=1),
            "storage_dispatch_ready": True,
            "sdk_versions": v3.SDK_VERSIONS,
            "credential_present": True,
            "power": power,
            "provider_active_before_intent": 0,
            "actual_provider_billed_usd": None,
        }
        budget_sha = v3._write_new(attempt_dir / "budget.json", budget_receipt)
        intent = {
            "schema": "cua-native-wdi-v066-final-control-intent-v1",
            "status": "recorded_before_provider_create", "created_utc": _now(),
            "task_id": row["task_id"], "attempt": attempt,
            "package_sha256": row["package_sha256"],
            "lease_seconds": LEASE_SECONDS,
            "ratification_sha256": digest(_private(paths["action_ratification"])),
            "reservation_sha256": digest(_private(paths["reservation"])),
            "scoped_reference_sha256": digest(_private(paths["reference_path"])),
            "scoped_runtime_freeze_sha256": digest(_private(paths["runtime_freeze"])),
            "three_root_bridge_sha256": digest(_private(paths["bridge_path"])),
            "precreate_budget_sha256": budget_sha,
            "durable_child_wrapper_sha256": frozen["source_sha256s"][
                "native_desktop_factory/v066_day_rollover_durable_child_v4e.py"],
            "v4e_freeze_sha256": digest(_private(freeze)),
            "v4e_permit_sha256": digest(_private(permit)),
            "same_intent_replay_authorized": False,
            "actual_provider_billed_usd": None,
        }
        intent_sha = v3._write_new(attempt_dir / "intent.json", intent)
        command = [
            sys.executable, "-m", CHILD,
            "--candidate-root", str(paths["candidate_root"]),
            "--attempts-root", str(root),
            "--task-id", row["task_id"], "--attempt", attempt,
            "--private-map", str(paths["private_map"]),
            "--profile-private", str(paths["profile_private"]),
            "--guest-public", str(paths["guest_public"]),
            "--fair-public", str(paths["fair_public"]),
            "--ratification", str(paths["action_ratification"]),
            "--reservation", str(paths["reservation"]),
            "--scoped-reference", str(paths["reference_path"]),
            "--runtime-freeze", str(paths["runtime_freeze"]),
            "--three-root-bridge", str(paths["bridge_path"]),
            "--original-root", str(paths["old_original_root"]),
            "--failed-root", str(paths["old_caret_root"]),
            "--public-calibration", str(paths["public_day_audit"]),
            "--private-calibration-audit", str(paths["private_day_audit"]),
            "--failed-private-stop", str(paths["failed_private_stop"]),
            "--failed-public-interruption",
                str(paths["failed_public_interruption"]),
            "--enable-paid-scoped-final",
        ]
        # The durable helper writes raw child bytes and a terminal receipt before
        # returning any status. A second invocation on this intent is refused.
        previous_freeze = os.environ.get("ENVLOOP_DESKTOP_V4E_FREEZE")
        previous_permit = os.environ.get("ENVLOOP_DESKTOP_V4E_PERMIT")
        previous_run = os.environ.get("ENVLOOP_DESKTOP_V4E_RUN_DIR")
        os.environ.update({
            "ENVLOOP_DESKTOP_V4E_FREEZE": str(freeze.resolve()),
            "ENVLOOP_DESKTOP_V4E_PERMIT": str(permit.resolve()),
            "ENVLOOP_DESKTOP_V4E_RUN_DIR": str(run_dir.resolve()),
        })
        try:
            code, _stdout, _stderr, timed_out = durable_output._invoke_to_files(
                command, attempt_dir, LEASE_SECONDS + 120)
        finally:
            for key, previous in (
                ("ENVLOOP_DESKTOP_V4E_FREEZE", previous_freeze),
                ("ENVLOOP_DESKTOP_V4E_PERMIT", previous_permit),
                ("ENVLOOP_DESKTOP_V4E_RUN_DIR", previous_run),
            ):
                if previous is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = previous
        output_raw = _private(attempt_dir / "child-output.json")
        output = json.loads(output_raw)
        receipt_path = attempt_dir / "receipt.json"
        receipt_raw = _private(receipt_path) if receipt_path.exists() else None
        try:
            receipt = json.loads(receipt_raw) if receipt_raw is not None else {}
        except (TypeError, ValueError):
            receipt = {}
        outcome = {
            "attempt": attempt, "exit_code": code,
            "budget_sha256": budget_sha,
            "intent_sha256": intent_sha,
            "child_output_sha256": digest(output_raw),
            "child_stdout_sha256": digest(_private(attempt_dir / "child.stdout")),
            "child_stderr_sha256": digest(_private(attempt_dir / "child.stderr")),
            "receipt_sha256": digest(receipt_raw) if receipt_raw else None,
            "status": "timeout_uncertain" if timed_out else
                receipt.get("status", "missing_or_invalid_receipt"),
            "sandbox_id_observed": bool(receipt.get("sandbox_id_sha256")),
            "cleanup_verified": receipt.get("is_running_after_kill") is False,
            "child_process_exited": True,
        }
        result["attempts"].append(outcome)
        expected = ("cold_reset_observed" if attempt == "cold-reset"
                    else "control_passed")
        if (output.get("stdout_sha256") != outcome["child_stdout_sha256"] or
                output.get("stderr_sha256") != outcome["child_stderr_sha256"] or
                outcome["status"] != expected or code != 0 or
                not outcome["sandbox_id_observed"] or
                not outcome["cleanup_verified"]):
            result["status"] = "stopped_after_invalid_or_uncertain_attempt"
            return result
    result["status"] = "provisional_trio_complete"
    return result


def run(*, freeze: Path, permit: Path, run_dir: Path,
        mode: str = "untouched", max_new_ids: int = 1) -> dict:
    frozen, paths, rows, audited = validate_source(freeze=freeze)
    selected = _select(frozen=frozen, rows=rows, audit=audited,
                       mode=mode, max_new_ids=max_new_ids)
    if not selected:
        return {"status": "all_88_untouched_ids_audited",
                "new_ids_selected": 0, "official_final_admissions": 0}
    root = Path(frozen["new_attempts_root"])
    if any((root / row["task_id"]).exists() for row in selected):
        raise ValueError("v4e selected ID already has an attempt")
    expected_parent = root.parent / "v066-v4e-root-owned-runs"
    entries = sorted(expected_parent.iterdir()) if expected_parent.exists() else []
    number = len(entries) + 1
    if (any(entry.name != f"batch-{index:04d}" or
            not entry.is_dir() for index, entry in enumerate(entries, 1)) or
            run_dir.exists() or run_dir.parent != expected_parent or
            run_dir.name != f"batch-{number:04d}"):
        raise ValueError("Exclusive sequential v4e root-owned batch required")
    permit_raw = _checked_permit(
        freeze=freeze, frozen=frozen, permit_path=permit, mode=mode,
        selected=selected, batch_number=number, current_audit=audited)
    v3._sdk_and_credential()
    v3._power_snapshot()
    active, count = active_hashes()
    if active or count:
        raise ValueError("Provider must be active-zero before v4e bounded run")
    if not root.exists():
        root.mkdir(parents=True, mode=0o700)
        root.chmod(0o700)
        v3._sync_dir(root.parent)
    run_dir.mkdir(parents=True, mode=0o700)
    run_dir.chmod(0o700)
    v3._sync_dir(run_dir.parent)
    journal = {
        "schema": RUN_SCHEMA, "status": "started",
        "created_utc": _now(),
        "freeze_sha256": digest(_private(freeze)),
        "permit_sha256": digest(permit_raw),
        "permit_path": str(permit.resolve()),
        "batch_number": number, "mode": mode,
        "selected_private_task_ids": [row["task_id"] for row in selected],
        "task_outcomes": [],
        "official_final_model_attempts": 0,
        "official_final_admissions": 0,
    }
    journal_path = run_dir / "run-receipt.json"
    v3._write_new(journal_path, journal)
    old_term = signal.getsignal(signal.SIGTERM)

    def interrupted(_signum, _frame):
        raise InterruptedError("v4e root-owned batch interrupted")

    signal.signal(signal.SIGTERM, interrupted)
    try:
        for row in selected:
            outcome = _task(row=row, frozen=frozen, paths=paths,
                            freeze=freeze, permit=permit, run_dir=run_dir)
            journal["task_outcomes"].append(outcome)
            v2._persist(journal_path, journal)
            if outcome["status"] != "provisional_trio_complete":
                journal["status"] = "stopped_for_reconciliation"
                break
            active, count = active_hashes()
            if active or count:
                journal["status"] = "stopped_for_provider_cleanup_audit"
                break
            try:
                from .v066_day_rollover_independent_audit_v4e import audit
                current = audit(freeze=freeze, active_run_dir=run_dir)
                if (current["untouched_complete_prefix"] +
                        int(current["clone_complete"]) !=
                        audited["untouched_complete_prefix"] +
                        int(audited["clone_complete"]) +
                        len(journal["task_outcomes"])):
                    raise ValueError("New trio not independently accepted")
            except Exception as exc:
                journal["status"] = "stopped_after_independent_audit_failure"
                journal["audit_error_type"] = type(exc).__name__
                break
        else:
            journal["status"] = "bounded_completed_and_audited"
    except BaseException as exc:
        journal["status"] = "stopped_after_root_interruption"
        journal["interruption_type"] = type(exc).__name__
        journal["completed_utc"] = _now()
        v2._persist(journal_path, journal)
        raise
    finally:
        signal.signal(signal.SIGTERM, old_term)
    journal["completed_utc"] = _now()
    v2._persist(journal_path, journal)
    return {
        "status": journal["status"],
        "new_ids_selected": len(selected),
        "new_complete_trios": sum(
            item["status"] == "provisional_trio_complete"
            for item in journal["task_outcomes"]),
        "official_final_admissions": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "plan", "run"))
    parser.add_argument("--v4d-freeze", type=Path)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--public", type=Path)
    parser.add_argument("--permit", type=Path)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--lane", choices=("untouched", "clone"),
                        default="untouched")
    parser.add_argument("--max-new-ids", type=int, default=1)
    args = parser.parse_args()
    if args.mode == "prepare":
        if args.v4d_freeze is None or args.public is None:
            raise ValueError("v4d lineage and public freeze path required")
        result = prepare(v4d_freeze=args.v4d_freeze,
                         freeze=args.freeze, public=args.public)
    elif args.mode == "plan":
        result = plan(freeze=args.freeze, mode=args.lane,
                      max_new_ids=args.max_new_ids)
    else:
        if args.permit is None or args.run_dir is None:
            raise ValueError("Separate reviewed permit and new run dir required")
        result = run(freeze=args.freeze, permit=args.permit,
                     run_dir=args.run_dir, mode=args.lane,
                     max_new_ids=args.max_new_ids)
    print(json.dumps(result, sort_keys=True))
    if result.get("status", "").startswith("stopped_"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
