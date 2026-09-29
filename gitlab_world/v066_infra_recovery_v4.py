"""Offline successor plan after the terminal GitLab v0.6.6 startup failure.

This source never starts Docker, replays the failed identity, or dispatches a
task. It binds a new diagnostic ID epoch and a whole-family FIFO replacement
proposal to the immutable terminal record. Live qualification needs a later,
separately frozen runner and independent audit.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import stat

from . import bootstrap, factory, pre_result_recovery as reserve
from . import prospective_final_controls_v066 as lane
from . import v066_requalified_continuation_v1 as terminal
from . import v066_supervised_final_one_v1 as one


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = ROOT / "work/gitlab-full-world"
PRIVATE_DIR = PRIVATE_ROOT / "v066-infra-recovery-v4-20260929"
PRIVATE_PLAN = PRIVATE_DIR / "source-plan.private.json"
PUBLIC_PLAN = ROOT / "docs/evidence/gitlab-v066-infra-recovery-v4-source-plan-2026-09-29.json"
TERMINAL_PUBLIC = ROOT / "docs/evidence/gitlab-v066-requalified-continuation-batch-003-terminal-independent-audit-2026-09-29.json"
TERMINAL_PUBLIC_SHA256 = "48e8041e07b27bd961d75c012c8cb9a6648769bc1d4c86fdb4c98514eadaace3"
QUEUE_PUBLIC = ROOT / "docs/evidence/gitlab-pre-result-recovery-queue-2026-09-28.json"
QUEUE_PUBLIC_SHA256 = "1f0496a84f4f082e478051e130e8639b3d2d7ab4cebbd3054aadbad51a258666"
FAILED_INDEX = 13
RETIRED_INDICES = (10, 11, 12, 13, 14)
DIAGNOSTIC_INDEX = 15
PRIVATE_SCHEMA = "envloop-gitlab-v066-infra-recovery-v4-source-plan-private-v1"
PUBLIC_SCHEMA = "envloop-gitlab-v066-infra-recovery-v4-source-plan-public-v1"
SOURCE_FILES = (
    "gitlab_world/v066_infra_recovery_v4.py",
    "tests/test_gitlab_v066_infra_recovery_v4.py",
    "docs/FULL_STUDY_GITLAB_V066_INFRA_RECOVERY_V4_2026-09-29.md",
    "gitlab_world/pre_result_recovery.py",
    "gitlab_world/factory.py",
)


class RecoveryPlanError(RuntimeError):
    pass


def require(value: bool, code: str) -> None:
    if not value:
        raise RecoveryPlanError(code)


def _source_sha256s() -> dict[str, str]:
    return {name: one.sha((ROOT / name).read_bytes()) for name in SOURCE_FILES}


def _read_private_input(path: Path) -> bytes:
    require(path.is_file() and not path.is_symlink() and
            stat.S_ISREG(path.stat().st_mode) and
            path.stat().st_mode & 0o077 == 0,
            "private_source_input_missing_or_permissive")
    return path.read_bytes()


def replacement_roster(original: list[dict], first_reserve: dict) -> dict:
    """Retire one correlated five-task family, never one task in isolation."""
    require(len(original) == 100 and
            len({row["task_id"] for row in original}) == 100 and
            len({row["package_sha256"] for row in original}) == 100,
            "original_roster_not_one_hundred_distinct_identities")
    failed_family = original[FAILED_INDEX]["source_family_sha256"]
    actual_indices = tuple(index for index, row in enumerate(original)
                           if row["source_family_sha256"] == failed_family)
    require(actual_indices == RETIRED_INDICES and
            original[DIAGNOSTIC_INDEX]["source_family_sha256"] != failed_family,
            "failed_correlated_family_or_distinct_diagnostic_changed")
    tasks = first_reserve.get("tasks")
    require(first_reserve.get("ordinal") == 1 and
            isinstance(tasks, list) and len(tasks) == 5,
            "first_fifo_reserve_family_missing")
    by_workflow = {task["template_group"]: task for task in tasks}
    retired_workflows = [original[index]["template_group"]
                         for index in RETIRED_INDICES]
    require(len(by_workflow) == 5 and
            set(by_workflow) == set(retired_workflows) and
            all(task.get("partition") == "final_candidate_unsealed"
                for task in tasks),
            "fifo_reserve_does_not_replace_complete_workflow_family")
    reserve_rows = []
    for workflow in retired_workflows:
        task = by_workflow[workflow]
        reserve_rows.append({
            "task_id": task["task_id"],
            "source_family_sha256": one.sha(task["source_family"].encode()),
            "template_group": workflow,
            "task_object_sha256": one.sha(one.canonical(task)),
            "package_sha256": None,
            "provenance": "first_precommitted_fifo_reserve_family",
        })
    require(len({row["source_family_sha256"] for row in reserve_rows}) == 1 and
            reserve_rows[0]["source_family_sha256"] not in
            {row["source_family_sha256"] for row in original} and
            not ({row["task_id"] for row in reserve_rows} &
                 {row["task_id"] for row in original}),
            "reserve_source_or_task_identity_overlaps_original_roster")
    candidate = ([{**row, "provenance": "original_roster"}
                  for row in original[:RETIRED_INDICES[0]]] +
                 reserve_rows +
                 [{**row, "provenance": "original_roster"}
                  for row in original[RETIRED_INDICES[-1] + 1:]])
    counts = Counter(row["source_family_sha256"] for row in candidate)
    require(len(candidate) == len({row["task_id"] for row in candidate}) == 100 and
            len(counts) == 20 and set(counts.values()) == {5} and
            not ({row["task_id"] for row in candidate} &
                 {original[index]["task_id"] for index in RETIRED_INDICES}),
            "replacement_denominator_or_whole_family_invariant_failed")
    return {
        "retired_family_original_indices": list(RETIRED_INDICES),
        "retired_completed_controls": 3,
        "retained_historical_passing_controls": 10,
        "candidate_roster": candidate,
        "diagnostic_original_index": DIAGNOSTIC_INDEX,
        "diagnostic_task_id": original[DIAGNOSTIC_INDEX]["task_id"],
        "diagnostic_package_sha256": original[DIAGNOSTIC_INDEX]["package_sha256"],
        "diagnostic_source_family_sha256":
            original[DIAGNOSTIC_INDEX]["source_family_sha256"],
    }


def parent_and_queue(ratification_private: Path) -> tuple[dict, dict, dict]:
    """Reopen the terminal attempt and reconstruct the precommitted queue."""
    require(one.sha(TERMINAL_PUBLIC.read_bytes()) == TERMINAL_PUBLIC_SHA256 and
            one.sha(QUEUE_PUBLIC.read_bytes()) == QUEUE_PUBLIC_SHA256,
            "published_terminal_or_fifo_commitment_changed")
    terminal_public = json.loads(TERMINAL_PUBLIC.read_bytes())
    queue_public = json.loads(QUEUE_PUBLIC.read_bytes())
    audit = terminal.audit(ratification_private)
    require(audit == {
        "status": "terminal_failure_no_replay",
        "completed_current_controls": 13,
        "remaining_original_roster_controls": 87,
        "closed_batch_count": 4,
        "pending_batch": False,
        "pending_id": False,
        "original_terminal_failure_retained": True,
        "v3_requalification_retained": True,
        "all_100_controls_independently_reopened": False,
        "model_calls": 0,
        "official_final_admitted": 0,
    } and
            terminal_public.get("status") ==
            "read_only_terminal_infrastructure_failure_audited_no_replay" and
            terminal_public.get("completed_current_profile_controls") == 13 and
            terminal_public.get("completed_new_controls_in_batch") == 0 and
            terminal_public.get("automatic_same_id_replay") is False and
            terminal_public.get("branch_terminal_failure") is True and
            terminal_public.get("official_final_admitted") == 0,
            "terminal_failure_not_independently_bound")
    _old_freeze, context, audited = terminal.validate_freeze(
        ratification_private)
    require(audited["completed_task_count"] == 13 and
            audited["terminal_failure"] is True and
            audited["pending_intent"] is False and
            one.sha((terminal.BRANCH / "journal.private.jsonl").read_bytes()) ==
            terminal_public["branch_journal_sha256"] and
            one.sha((terminal.BATCHES / "journal.private.jsonl").read_bytes()) ==
            terminal_public["continuation_batch_journal_sha256"] and
            one.sha((terminal.SUPERVISION / "013-result.private.json").read_bytes()) ==
            terminal_public["supervisor_result_private_sha256"] and
            one.sha(one.canonical(terminal.recovery._tree_manifest(
                terminal.BRANCH / "attempts" / "013"))) ==
            terminal_public["failed_attempt_partial_manifest_sha256"] and
            not (terminal.SUPERVISION / "014-intent.private.json").exists() and
            not (terminal.BRANCH / "attempts" / "014").exists(),
            "terminal_branch_changed_or_later_id_dispatched")
    world = json.loads(_read_private_input(bootstrap.WORLD_FILE))
    seed = _read_private_input(bootstrap.SEED_FILE).decode().strip()
    queue = reserve.ordered_queue(seed, world,
                                  reserve.load_catalog(reserve.FULL_CATALOG))
    require(reserve.public_commitment(queue) == queue_public and
            len(queue["ordered_families"]) == 5 and
            queue["status"] == "prospective_unsealed_not_gui_qualified",
            "reconstructed_fifo_reserve_differs_from_pre_result_commitment")
    return context["old"], terminal_public, queue


def private_plan_payload(original: dict, terminal_public: dict,
                         queue: dict, ratification_private_sha: str) -> dict:
    roster = replacement_roster(original["task_roster"],
                                queue["ordered_families"][0])
    source_hashes = _source_sha256s()
    source_bundle = one.sha(one.canonical(source_hashes))
    candidate_sha = one.sha(one.canonical(roster["candidate_roster"]))
    epoch = one.sha(one.canonical({
        "source_bundle_sha256": source_bundle,
        "terminal_batch_journal_sha256":
            terminal_public["continuation_batch_journal_sha256"],
        "fifo_queue_sha256": queue["queue_sha256"],
        "candidate_roster_sha256": candidate_sha,
    }))
    return {
        "schema": PRIVATE_SCHEMA,
        "status": "prospective_new_id_epoch_plan_only_no_dispatch",
        "epoch_sha256": epoch,
        "source_sha256s": source_hashes,
        "source_bundle_sha256": source_bundle,
        "amended_ratification_private_sha256": ratification_private_sha,
        "terminal_public_sha256": TERMINAL_PUBLIC_SHA256,
        "terminal_branch_journal_sha256": terminal_public["branch_journal_sha256"],
        "terminal_batch_journal_sha256":
            terminal_public["continuation_batch_journal_sha256"],
        "fifo_public_commitment_sha256": QUEUE_PUBLIC_SHA256,
        "fifo_queue_sha256": queue["queue_sha256"],
        "original_100_id_plan_sha256":
            one.sha((terminal.BRANCH / "plan.private.json").read_bytes()),
        "failed_original_index": FAILED_INDEX,
        **roster,
        "candidate_roster_sha256": candidate_sha,
        "diagnostic_epoch_intent_written": False,
        "replacement_epoch_intent_written": False,
        "same_identity_replay_authorized": False,
        "boot_only_infrastructure_probe_passed": False,
        "failed_container_raw_logs_retained_for_new_epoch": False,
        "reserve_family_bootstrapped_in_new_world": False,
        "new_baseline_and_acl_frozen": False,
        "one_id_gui_dispatch_authorized": False,
        "official_final_admitted": 0,
        "model_calls": 0,
    }


def public_plan_payload(private: dict, private_sha: str) -> dict:
    return {
        "schema": PUBLIC_SCHEMA,
        "status": "prospective_new_id_epoch_plan_only_no_dispatch",
        "private_plan_sha256": private_sha,
        "epoch_sha256": private["epoch_sha256"],
        "source_bundle_sha256": private["source_bundle_sha256"],
        "terminal_public_sha256": private["terminal_public_sha256"],
        "fifo_public_commitment_sha256":
            private["fifo_public_commitment_sha256"],
        "fifo_queue_sha256": private["fifo_queue_sha256"],
        "failed_original_index": FAILED_INDEX,
        "retired_family_original_indices": list(RETIRED_INDICES),
        "retired_completed_controls": 3,
        "retained_historical_passing_controls": 10,
        "prospective_candidate_count": 100,
        "candidate_roster_sha256": private["candidate_roster_sha256"],
        "prospective_diagnostic_original_index": DIAGNOSTIC_INDEX,
        "diagnostic_result_not_counted_as_final_roster_control": True,
        "same_identity_replay_authorized": False,
        "boot_only_infrastructure_probe_passed": False,
        "failed_container_raw_logs_retained_for_new_epoch": False,
        "reserve_family_bootstrapped_in_new_world": False,
        "new_baseline_and_acl_frozen": False,
        "one_id_gui_dispatch_authorized": False,
        "official_final_admitted": 0,
        "model_calls": 0,
    }


def build(ratification_private: Path) -> tuple[dict, dict]:
    original, terminal_public, queue = parent_and_queue(
        ratification_private)
    private = private_plan_payload(
        original, terminal_public, queue,
        one.sha(_read_private_input(ratification_private)))
    return private, public_plan_payload(
        private, one.sha(one.canonical(private)))


def freeze(ratification_private: Path) -> dict:
    require(not PRIVATE_PLAN.exists() and not PUBLIC_PLAN.exists(),
            "new_epoch_freeze_requires_fresh_private_and_public_paths")
    private, _public = build(ratification_private)
    PRIVATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    require(PRIVATE_DIR.stat().st_mode & 0o077 == 0,
            "new_epoch_private_directory_permissive")
    private_sha = one.write_new(PRIVATE_PLAN, private)
    public = public_plan_payload(private, private_sha)
    one.write_new(PUBLIC_PLAN, public, 0o644)
    return public


def audit(ratification_private: Path) -> dict:
    expected_private, _ = build(ratification_private)
    saved, saved_sha = one.private_json(PRIVATE_PLAN)
    require(saved == expected_private and
            json.loads(PUBLIC_PLAN.read_bytes()) ==
            public_plan_payload(saved, saved_sha),
            "new_epoch_source_or_candidate_roster_changed")
    return public_plan_payload(saved, saved_sha)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "audit"))
    parser.add_argument("--ratification-private", type=Path, required=True)
    args = parser.parse_args()
    result = (freeze(args.ratification_private)
              if args.action == "freeze" else
              audit(args.ratification_private))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
