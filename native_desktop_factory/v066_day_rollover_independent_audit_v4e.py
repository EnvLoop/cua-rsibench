"""Read-only saved-state and intent audit for Desktop v4e evaluator controls.

This auditor imports no controller and creates no provider resources. It
reopens the original eight GUI trios, the stopped v4c precreate intent, each
new positive/near-negative/cold-reset saved artifact, raw A/B/A/B frames,
distinct guests, durable child output, and the five-root full-lease ledger.
"""

from __future__ import annotations

import argparse
from decimal import Decimal
import json
from pathlib import Path
from unittest.mock import patch

from . import qwen_v066_adapter_v4_strict as strict
from . import v066_day_rollover_attrition_audit_v4 as v4_frames
from . import v066_day_rollover_precreate_freeze_v4d as v4d
from . import v066_scoped_profile_final_audit as profile_audit
from .v066_caret_full100_preflight import _read_only_storage, _tree_digest
from .v066_day_rollover_durable_child_v4e import _old_paths
from .v066_day_rollover_five_root_v4e import five_root_budget
from .reconcile_interrupted_sweep import active_hashes
from .v066_day_rollover_continuation_v3 import _write_new
from .v066_day_rollover_reference import validate as validate_reference
from .v066_final_control_audit import _validate_trio
from .v066_final_freeze import LEASE_SECONDS, digest, intent_budget
from .v066_scoped_profile_final_controller import _final_rows


ATTEMPTS = ("positive", "near-miss", "cold-reset")
FREEZE_SCHEMA = "cua-native-wdi-v066-five-root-freeze-private-v4e"
RUN_SCHEMA = "cua-native-wdi-v066-v4e-bounded-run-private-v1"
CHILD_SOURCE = "native_desktop_factory/v066_day_rollover_durable_child_v4e.py"


def _private(path: Path) -> bytes:
    if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o077:
        raise ValueError("Private Desktop audit evidence absent or unsafe")
    return path.read_bytes()


def _checked_attempt(*, root: Path, row: dict, attempt: str,
                     frozen: dict, freeze_sha: str,
                     seen_budget_totals: set[int]) -> None:
    task_id = row["task_id"]
    directory = root / task_id / attempt
    budget_raw = _private(directory / "budget.json")
    intent_raw = _private(directory / "intent.json")
    child_started_raw = _private(directory / "child-started.json")
    output_raw = _private(directory / "child-output.json")
    stdout_raw = _private(directory / "child.stdout")
    stderr_raw = _private(directory / "child.stderr")
    receipt_raw = _private(directory / "receipt.json")
    budget = json.loads(budget_raw)
    intent = json.loads(intent_raw)
    child_started = json.loads(child_started_raw)
    output = json.loads(output_raw)
    receipt = json.loads(receipt_raw)
    five = budget.get("five_root_budget", {})
    total = five.get("combined_full_lease_intents")
    if (type(total) is not int or total in seen_budget_totals or
            not 57 <= total <= 323 or
            five.get("schema") !=
                "cua-native-wdi-v066-five-root-lease-budget-v4e" or
            five.get("historical_four_root_intents") != 56 or
            five.get("new_root_existing_intents") != total - 57 or
            five.get("new_root_proposed_intents") != 1 or
            Decimal(five["combined_conservative_reserved_usd"]) !=
                Decimal(total * LEASE_SECONDS) / Decimal(3600) or
            budget.get("schema") !=
                "cua-native-wdi-v066-precreate-budget-private-v3" or
            budget.get("status") != "fsynced_before_provider_create" or
            budget.get("task_id") != task_id or
            budget.get("attempt") != attempt or
            budget.get("provider_active_before_intent") != 0 or
            budget.get("storage_dispatch_ready") is not True or
            budget.get("credential_present") is not True or
            budget.get("power", {}).get("source") not in
                ("AC Power", "Battery Power") or
            budget.get("fresh_lane_budget", {}).get("combined_intents") !=
                total - 56 or
            intent.get("schema") !=
                "cua-native-wdi-v066-final-control-intent-v1" or
            intent.get("status") != "recorded_before_provider_create" or
            intent.get("task_id") != task_id or
            intent.get("attempt") != attempt or
            intent.get("package_sha256") != row["package_sha256"] or
            intent.get("lease_seconds") != LEASE_SECONDS or
            intent.get("precreate_budget_sha256") != digest(budget_raw) or
            intent.get("durable_child_wrapper_sha256") !=
                frozen["source_sha256s"][CHILD_SOURCE] or
            intent.get("v4e_freeze_sha256") != freeze_sha or
            intent.get("same_intent_replay_authorized") is not False or
            child_started.get("schema") !=
                "cua-native-wdi-v066-v4e-child-started-private-v1" or
            child_started.get("status") !=
                "consumed_before_original_evaluator" or
            child_started.get("task_id") != task_id or
            child_started.get("attempt") != attempt or
            child_started.get("intent_sha256") != digest(intent_raw) or
            child_started.get("freeze_sha256") != freeze_sha or
            child_started.get("permit_sha256") !=
                intent.get("v4e_permit_sha256") or
            output.get("schema") !=
                "cua-native-wdi-v066-v4d-private-child-output-v1" or
            output.get("status") !=
                "terminal_output_fsynced_before_classification" or
            output.get("exit_code") != 0 or
            output.get("timed_out") is not False or
            output.get("stdout_sha256") != digest(stdout_raw) or
            output.get("stderr_sha256") != digest(stderr_raw) or
            receipt.get("native_adapter_sha256") != frozen["source_sha256s"][
                "native_desktop_factory/qwen_v066_adapter_v4_strict.py"] or
            receipt.get("is_running_after_kill") is not False):
        raise ValueError("v4e durable attempt, budget, child, or adapter changed")
    seen_budget_totals.add(total)


def audit(*, freeze: Path, active_run_dir: Path | None = None) -> dict:
    freeze_raw = _private(freeze)
    frozen = json.loads(freeze_raw)
    repo = Path(__file__).resolve().parents[1]
    source = frozen.get("source_sha256s", {})
    if (frozen.get("schema") != FREEZE_SCHEMA or
            frozen.get("status") != "frozen_without_dispatch_authority" or
            frozen.get("dispatch_authorized") is not False or
            frozen.get("same_intent_replay_authorized") is not False or
            frozen.get("official_final_admissions") != 0 or
            len(source) != 6 or
            any(digest((repo / name).read_bytes()) != expected
                for name, expected in source.items())):
        raise ValueError("v4e auditor or source-only freeze changed")
    published = json.loads(Path(frozen["public_path"]).read_bytes())
    if (published.get("schema") !=
            "cua-native-wdi-v066-five-root-freeze-public-v4e" or
            published.get("private_freeze_sha256") != digest(freeze_raw) or
            published.get("source_sha256s") != source or
            published.get("dispatch_authorized") is not False):
        raise ValueError("Published v4e source freeze changed")
    old_raw = _private(Path(frozen["v4d_freeze_path"]))
    old = json.loads(old_raw)
    old_v4c = json.loads(_private(Path(old["v4c_freeze_path"])))
    old_v3 = json.loads(_private(Path(old_v4c["v3_freeze_path"])))
    old_v2 = json.loads(_private(Path(old_v3["base_freeze_path"])))
    historical = old_v2.get("frozen_full100_source_sha256s", {})
    if (digest(old_raw) != frozen["v4d_freeze_sha256"] or
            old.get("dispatch_authorized") is not False or
            old.get("current_four_root_full_lease_intents") != 56 or
            digest(Path(old["public_path"]).read_bytes()) !=
                frozen["v4d_public_sha256"] or
            old.get("new_attempts_root") != frozen["new_attempts_root"] or
            digest(Path(old["public_path"]).read_bytes()) !=
                "f06958825c1d2b5283a4e3ba33c14ee6fcb20e896055d66f31c4dd5f064b6485" or
            len(historical) != 35 or
            any(digest((repo / name).read_bytes()) != expected
                for name, expected in historical.items())):
        raise ValueError("v4d retained precreate source binding changed")
    paths = _old_paths(frozen)
    inventory_raw, rows = _final_rows(paths["candidate_root"])
    roster = [row["task_id"] for row in rows]
    roster_sha = digest((json.dumps(roster, separators=(",", ":")) + "\n").encode())
    if (len(rows) != 100 or
            digest(inventory_raw) != frozen["candidate_inventory_sha256"] or
            roster_sha != frozen["sorted_final_roster_sha256"] or
            digest(_private(paths["bridge_path"])) !=
                frozen["old_bridge_sha256"]):
        raise ValueError("v4e frozen source roster or original bridge changed")
    for index in range(11):
        tree, _ = _tree_digest(paths["attempts_root"] / roster[index])
        if tree != frozen["historical_first_eleven_task_tree_sha256s"][str(index)]:
            raise ValueError("Retained first-eleven Desktop attempt tree changed")
    stopped = paths["attempts_root"] / roster[11] / "positive"
    old_budget_raw = _private(stopped / "budget.json")
    old_intent_raw = _private(stopped / "intent.json")
    if (digest(old_budget_raw) !=
            frozen["old_precreate_budget_sha256"] or
            digest(old_intent_raw) !=
            frozen["old_precreate_intent_sha256"] or
            (stopped / "receipt.json").exists() or
            (stopped.parent / "near-miss").exists() or
            (stopped.parent / "cold-reset").exists()):
        raise ValueError("Stopped v4c precreate intent was replayed or changed")
    terminal_raw = _private(Path(old["v4c_terminal_batch_path"]))
    public_audit_raw = Path(old["v4c_public_terminal_audit_path"]).read_bytes()
    stderr_raw = _private(Path(old["private_forensic_root"]) /
                          "replayed-main.stderr")
    forensic_raw = _private(Path(old["private_forensic_root"]) /
                            "v4c-terminal-audit.private.json")
    if (digest(terminal_raw) != old["terminal_batch_sha256"] or
            digest(public_audit_raw) != old["public_terminal_audit_sha256"] or
            digest(stderr_raw) != old["replayed_stderr_sha256"] or
            digest(forensic_raw) != old["private_forensic_audit_sha256"]):
        raise ValueError("v4c precreate no-create forensic bundle changed")
    v4d._prove_precreate(
        v4c=old_v4c, terminal=json.loads(terminal_raw),
        stderr=stderr_raw, budget_raw=old_budget_raw,
        intent_raw=old_intent_raw,
        public_audit=json.loads(public_audit_raw), repo=repo)
    for row in rows[12:]:
        if (paths["attempts_root"] / row["task_id"]).exists():
            raise ValueError("A never-intended ID appeared in the old root")
    reference, reference_sha = validate_reference(
        path=paths["reference_path"],
        private_audit=paths["private_day_audit"],
        public_audit=paths["public_day_audit"])
    salt = json.loads(_private(paths["private_map"]))["variant_salt"]
    common = {
        "profile_sha": digest(_private(paths["profile_private"])),
        "guest_sha": digest(paths["guest_public"].read_bytes()),
        "private_salt": salt,
        "ratification_sha": digest(_private(paths["action_ratification"])),
        "reservation_sha": digest(_private(paths["reservation"])),
    }
    guest_ids: set[str] = set()
    for index in list(range(7)) + [9]:
        row = rows[index]
        fair = _validate_trio(paths["candidate_root"], paths["attempts_root"],
                              row, **common)
        ids = profile_audit._profile_receipt(
            candidate_root=paths["candidate_root"],
            attempts_root=paths["attempts_root"],
            task_id=row["task_id"], workflow=row["workflow"],
            reference=reference, reference_sha=reference_sha,
            runtime_sha=digest(_private(paths["runtime_freeze"])),
            bridge_sha=digest(_private(paths["bridge_path"])))
        if (fair.get("prospective_controls_passed") is not True or
                len(ids) != 3 or any(item in guest_ids for item in ids)):
            raise ValueError("Original eight saved/profile controls changed")
        guest_ids.update(ids)
    root = Path(frozen["new_attempts_root"])
    complete = []
    if root.exists():
        if root.is_symlink() or not root.is_dir() or root.stat().st_mode & 0o077:
            raise ValueError("Fifth private root changed")
        expected_names = set(roster[11:])
        if any(path.is_symlink() or
               (path.is_dir() and path.name not in expected_names)
               for path in root.iterdir()):
            raise ValueError("Unexpected fifth-root task directory")
        present = [index for index in range(11, 100)
                   if (root / roster[index]).exists()]
        has_clone = 11 in present
        untouched = [index for index in present if index >= 12]
        if (untouched != list(range(12, 12 + len(untouched))) or
                present != ([11] if has_clone else []) + untouched):
            raise ValueError("v4e fifth-root roster has a gap")
        complete = present
    seen_totals: set[int] = set()
    caret_witnesses = 0
    for index in complete:
        row = rows[index]
        task_root = root / row["task_id"]
        if set(path.name for path in task_root.iterdir()) != set(ATTEMPTS):
            raise ValueError("v4e task lacks a complete three-attempt trio")
        for attempt in ATTEMPTS:
            _checked_attempt(
                root=root, row=row, attempt=attempt, frozen=frozen,
                freeze_sha=digest(freeze_raw), seen_budget_totals=seen_totals)
        fair = _validate_trio(paths["candidate_root"], root, row, **common)
        with patch.object(profile_audit, "qwen_v066_adapter", strict):
            ids = profile_audit._profile_receipt(
                candidate_root=paths["candidate_root"], attempts_root=root,
                task_id=row["task_id"], workflow=row["workflow"],
                reference=reference, reference_sha=reference_sha,
                runtime_sha=digest(_private(paths["runtime_freeze"])),
                bridge_sha=digest(_private(paths["bridge_path"])))
        if (fair.get("prospective_controls_passed") is not True or
                len(ids) != 3 or any(item in guest_ids for item in ids)):
            raise ValueError("New v4e saved/profile controls failed")
        guest_ids.update(ids)
        for attempt in ATTEMPTS[:2]:
            receipt = json.loads(_private(task_root / attempt / "receipt.json"))
            caret_witnesses += v4_frames._guard_frames(root, receipt)
    if seen_totals != set(range(57, 57 + 3 * len(complete))):
        raise ValueError("Five-root paid intent order or count changed")
    budget = five_root_budget(
        original_root=paths["old_original_root"],
        failed_root=paths["old_caret_root"],
        failed_scoped_root=paths["old_failed_scoped_root"],
        date_amended_root=paths["attempts_root"], new_root=root)
    if (budget["new_root_existing_intents"] != 3 * len(complete) or
            intent_budget(paths["attempts_root"])["existing_intents"] != 30):
        raise ValueError("v4e full-lease ledger changed")
    if root.exists():
        _read_only_storage(root)
    run_parent = root.parent / "v066-v4e-root-owned-runs"
    run_entries = sorted(run_parent.iterdir()) if run_parent.exists() else []
    accounted = []
    for number, entry in enumerate(run_entries, 1):
        if (entry.name != f"batch-{number:04d}" or not entry.is_dir() or
                entry.is_symlink()):
            raise ValueError("v4e run journal sequence changed")
        receipt = json.loads(_private(entry / "run-receipt.json"))
        active = entry == active_run_dir and receipt.get("status") == "started"
        selected = receipt.get("selected_private_task_ids", [])
        outcomes = receipt.get("task_outcomes", [])
        permit_path_value = receipt.get("permit_path")
        if (type(permit_path_value) is not str or
                not Path(permit_path_value).is_absolute()):
            raise ValueError("v4e run lacks its private review permit")
        permit_raw = _private(Path(permit_path_value))
        permit = json.loads(permit_raw)
        review_path_value = permit.get("independent_review_path")
        if (type(review_path_value) is not str or
                not Path(review_path_value).is_absolute()):
            raise ValueError("v4e independent review path absent")
        review_raw = _private(Path(review_path_value))
        review = json.loads(review_raw)
        selected_sha = digest((json.dumps(selected, separators=(",", ":")) +
                               "\n").encode())
        if (receipt.get("schema") != RUN_SCHEMA or
                receipt.get("freeze_sha256") != digest(freeze_raw) or
                receipt.get("batch_number") != number or
                receipt.get("permit_sha256") != digest(permit_raw) or
                permit.get("schema") !=
                    "cua-native-wdi-v066-v4e-reviewed-dispatch-permit-private-v1" or
                permit.get("status") != "independently_reviewed_one_batch" or
                permit.get("dispatch_authorized") is not True or
                permit.get("freeze_sha256") != digest(freeze_raw) or
                permit.get("source_sha256s") != source or
                permit.get("mode") != receipt.get("mode") or
                permit.get("batch_number") != number or
                permit.get("maximum_new_ids") != len(selected) or
                permit.get("selected_private_task_ids_sha256") != selected_sha or
                permit.get("independent_review_sha256") != digest(review_raw) or
                review.get("schema") !=
                    "cua-native-wdi-v066-v4e-independent-preflight-review-private-v1" or
                review.get("status") != "accepted_for_exact_one_batch" or
                review.get("freeze_sha256") != digest(freeze_raw) or
                review.get("selected_private_task_ids_sha256") != selected_sha or
                review.get("provider_active_at_review") != 0 or
                receipt.get("official_final_admissions") != 0 or
                receipt.get("official_final_model_attempts") != 0 or
                receipt.get("status") !=
                    ("started" if active else "bounded_completed_and_audited") or
                not 1 <= len(selected) <= 2 or
                (receipt.get("mode") == "clone" and
                 selected != [roster[11]]) or
                (receipt.get("mode") == "untouched" and
                 any(task not in roster[12:] for task in selected)) or
                (not active and len(outcomes) != len(selected)) or
                (active and len(outcomes) > len(selected)) or
                any(row.get("private_task_id") != selected[offset] or
                    row.get("status") != "provisional_trio_complete"
                    for offset, row in enumerate(outcomes))):
            raise ValueError("v4e run journal incomplete or changed")
        for row in outcomes:
            task_id = row["private_task_id"]
            attempts = row.get("attempts", [])
            if len(attempts) != 3:
                raise ValueError("v4e run lacks three durable attempt outcomes")
            for attempt_name, outcome in zip(ATTEMPTS, attempts):
                directory = root / task_id / attempt_name
                saved_receipt = json.loads(_private(directory / "receipt.json"))
                if (outcome.get("attempt") != attempt_name or
                        outcome.get("exit_code") != 0 or
                        outcome.get("status") !=
                            ("cold_reset_observed" if attempt_name == "cold-reset"
                             else "control_passed") or
                        outcome.get("budget_sha256") != digest(_private(
                            directory / "budget.json")) or
                        outcome.get("intent_sha256") != digest(_private(
                            directory / "intent.json")) or
                        outcome.get("child_output_sha256") != digest(_private(
                            directory / "child-output.json")) or
                        outcome.get("child_stdout_sha256") != digest(_private(
                            directory / "child.stdout")) or
                        outcome.get("child_stderr_sha256") != digest(_private(
                            directory / "child.stderr")) or
                        outcome.get("receipt_sha256") != digest(_private(
                            directory / "receipt.json")) or
                        outcome.get("sandbox_id_observed") is not True or
                        outcome.get("cleanup_verified") is not True or
                        outcome.get("child_process_exited") is not True or
                        saved_receipt.get("sandbox_id_sha256") is None or
                        json.loads(_private(directory / "intent.json")).get(
                            "v4e_permit_sha256") != digest(permit_raw)):
                    raise ValueError("v4e run outcome differs from durable evidence")
        accounted.extend(row["private_task_id"] for row in outcomes)
    if (len(accounted) != len(complete) or
            set(accounted) != {roster[index] for index in complete} or
            [task for task in accounted if task != roster[11]] !=
                [roster[index] for index in complete if index >= 12]):
        raise ValueError("v4e run journals disagree with saved-state trios")
    return {
        "schema": "cua-native-wdi-v066-five-root-independent-audit-v4e",
        "status": "provisional_evaluator_controls_only",
        "historical_complete_trios": 8,
        "historical_partial_logical_ids": 4,
        "untouched_complete_prefix": len([i for i in complete if i >= 12]),
        "clone_complete": 11 in complete,
        "remaining_untouched_ids": 88 - len([i for i in complete if i >= 12]),
        "five_root_full_lease_intents_charged":
            budget["combined_full_lease_intents"],
        "distinct_accepted_sandboxes": len(guest_ids),
        "cross_observation_caret_witnesses": caret_witnesses,
        "same_intent_replay_authorized": False,
        "official_final_admissions": 0,
        "official_final_model_attempts": 0,
    }


def review_one_batch(*, freeze: Path, mode: str, max_new_ids: int,
                     review_out: Path, permit_out: Path,
                     active_probe=active_hashes) -> dict:
    """Issue one exclusive private permit after independent read-only checks.

    This does not create a sandbox. The permit is bound to one exact next batch,
    and the controller/child re-open this review before any provider create.
    """
    if review_out.exists() or permit_out.exists() or review_out == permit_out:
        raise ValueError("Exclusive review and permit paths required")
    frozen_raw = _private(freeze)
    frozen = json.loads(frozen_raw)
    current = audit(freeze=freeze)
    paths = _old_paths(frozen)
    _raw, rows = _final_rows(paths["candidate_root"])
    if mode == "untouched" and 1 <= max_new_ids <= 2:
        selected = rows[12 + current["untouched_complete_prefix"]:
                        12 + current["untouched_complete_prefix"] + max_new_ids]
    elif mode == "clone" and max_new_ids == 1 and not current["clone_complete"]:
        selected = [rows[11]]
    else:
        raise ValueError("One/two untouched IDs or one separately eligible clone")
    if not selected:
        raise ValueError("No remaining task in requested v4e lane")
    root = Path(frozen["new_attempts_root"])
    run_parent = root.parent / "v066-v4e-root-owned-runs"
    entries = sorted(run_parent.iterdir()) if run_parent.exists() else []
    number = len(entries) + 1
    if any(entry.name != f"batch-{index:04d}" for index, entry in enumerate(entries, 1)):
        raise ValueError("Previous root-owned batch sequence changed")
    active, count = active_probe()
    if active or count:
        raise ValueError("Provider active before v4e independent batch review")
    selected_ids = [row["task_id"] for row in selected]
    selected_sha = digest((json.dumps(selected_ids, separators=(",", ":")) +
                           "\n").encode())
    review = {
        "schema": "cua-native-wdi-v066-v4e-independent-preflight-review-private-v1",
        "status": "accepted_for_exact_one_batch",
        "freeze_sha256": digest(frozen_raw),
        "source_sha256s": frozen["source_sha256s"],
        "mode": mode, "batch_number": number,
        "maximum_new_ids": len(selected),
        "selected_private_task_ids_sha256": selected_sha,
        "current_independent_audit": current,
        "provider_active_at_review": 0,
        "same_intent_replay_authorized": False,
        "official_final_admissions": 0,
    }
    review_sha = _write_new(review_out, review)
    permit = {
        "schema": "cua-native-wdi-v066-v4e-reviewed-dispatch-permit-private-v1",
        "status": "independently_reviewed_one_batch",
        "freeze_sha256": digest(frozen_raw),
        "source_sha256s": frozen["source_sha256s"],
        "mode": mode, "batch_number": number,
        "maximum_new_ids": len(selected),
        "selected_private_task_ids_sha256": selected_sha,
        "new_attempts_root": frozen["new_attempts_root"],
        "independent_review_path": str(review_out.resolve()),
        "independent_review_sha256": review_sha,
        "same_intent_replay_authorized": False,
        "dispatch_authorized": True,
        "official_final_admissions": 0,
    }
    _write_new(permit_out, permit)
    return {
        "status": "one_batch_permit_written_without_provider_create",
        "mode": mode,
        "batch_number": number,
        "maximum_new_ids": len(selected),
        "projected_five_root_full_lease_intents":
            56 + 3 * (current["untouched_complete_prefix"] +
                      int(current["clone_complete"]) + len(selected)),
        "official_final_admissions": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--review-out", type=Path)
    parser.add_argument("--permit-out", type=Path)
    parser.add_argument("--lane", choices=("untouched", "clone"),
                        default="untouched")
    parser.add_argument("--max-new-ids", type=int, default=1)
    args = parser.parse_args()
    if (args.review_out is None) != (args.permit_out is None):
        raise ValueError("Both private review and permit output paths required")
    result = (review_one_batch(
        freeze=args.freeze, mode=args.lane,
        max_new_ids=args.max_new_ids, review_out=args.review_out,
        permit_out=args.permit_out) if args.review_out else
        audit(freeze=args.freeze))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
