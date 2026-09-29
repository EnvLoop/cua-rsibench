"""Additive read-only completeness audit for the frozen Odoo v6 GUI trace.

The v6 actor, runner, and source freeze remain byte-for-byte unchanged. This
auditor closes two evidence gaps before a raw control can be promoted: every
normalized action must name its observed task/frame, and every physical guard
PNG written by the indexed sink must appear in the trace exactly once.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from tools import audit_odoo_v066_two_frame_dispatch_v6 as frozen_audit
from tools import odoo_v066_scale_protocol_v1 as protocol
from tools import odoo_v066_two_frame_source_v6 as frozen_source


FREEZE = (protocol.ROOT / "docs/evidence" /
          "odoo-v066-two-frame-v6a-audit-source-freeze-2026-09-29.json")
SCHEMA = "envloop-odoo-v066-two-frame-v6a-independent-audit-source-freeze"
SOURCE_FILES = (
    "tools/audit_odoo_v066_two_frame_dispatch_v6a.py",
    "tests/test_odoo_v066_two_frame_dispatch_v6a.py",
)


class StrictAuditError(ValueError):
    pass


def need(ok: bool, code: str) -> None:
    if not ok:
        raise StrictAuditError(code)


def digest(path: Path) -> str:
    need(path.is_file() and not path.is_symlink(),
         "strict_audit_file_missing_or_symlink")
    return sha256(path.read_bytes()).hexdigest()


def validate_source() -> dict:
    frozen_source.validate()
    freeze = protocol.public_json(FREEZE)
    need(freeze == {
        "schema": SCHEMA,
        "status": "additive_read_only_audit_before_v6_raw_control_promotion",
        "as_of_date": "2026-09-29",
        "frozen_v6_source_freeze_sha256": digest(frozen_source.FREEZE),
        "source_sha256s": {
            relative: digest(protocol.ROOT / relative)
            for relative in SOURCE_FILES
        },
        "actor_or_runner_modified": False,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }, "strict_audit_source_freeze_changed")
    return freeze


def audit_trace(attempt: Path, trace: dict, row: dict) -> dict:
    """Run the frozen independent PNG audit, then close its identity gaps."""
    result = frozen_audit.audit_trace(attempt, trace, row)
    actions = trace["actions"]
    for step in range(len(actions)):
        candidates = list((attempt / "actions").glob(
            f"step-{step:03d}*-intent.private.json"))
        need(len(candidates) == 1,
             "strict_audit_action_intent_not_unique")
        need(candidates[0].is_file() and not candidates[0].is_symlink(),
             "strict_audit_action_intent_file_invalid")
        intent = json.loads(candidates[0].read_bytes())
        need(type(intent) is dict,
             "strict_audit_action_intent_json_invalid")
        action = intent.get("normalized_action")
        need(type(action) is dict and
             action.get("task_id") == row["task_id"] and
             action.get("task_binding_sha256") == row["package_sha256"] and
             action.get("step") == step and
             action.get("frame_id") == intent.get("frame_id") and
             intent.get("task_id") == row["task_id"] and
             intent.get("task_binding_sha256") == row["package_sha256"],
             "strict_audit_normalized_action_task_or_frame_unbound")
    frames = attempt / "frames"
    need(frames.is_dir() and not frames.is_symlink(),
         "strict_audit_guard_directory_invalid")
    actual = {path.name for path in frames.iterdir()
              if path.name.startswith("guard-")}
    expected = {f"guard-{index:04d}.png" for index in range(
        len(trace["exact_return_guard_samples"]))}
    need(actual == expected and all(
        (frames / name).is_file() and not (frames / name).is_symlink()
        for name in expected),
         "strict_audit_guard_sink_file_set_unbound")
    return {
        **result,
        "status": "all_v6_guards_actions_and_sink_files_independently_bound",
        "indexed_guard_pngs": len(expected),
        "normalized_actions_bound_to_task_frame": len(actions),
        "unreferenced_guard_pngs": 0,
    }


def audit_saved(*, private_plan: Path, attempt: Path) -> dict:
    validate_source()
    plan = protocol.private_json(private_plan)
    need(plan.get("schema") ==
         "envloop-odoo-v066-two-frame-selection-plan-private-v6" and
         attempt.resolve() == (
             private_plan.parent.parent / "v066_scale_controls" /
             plan["fresh_run_directory_name"] / "attempt-000").resolve(),
         "strict_audit_attempt_or_plan_unbound")
    trace = protocol.private_json(attempt / "gui_trace.json")
    result = audit_trace(attempt, trace, plan["tasks"][0])
    return {
        **result,
        "private_plan_sha256": digest(private_plan),
        "frozen_v6_source_freeze_sha256": digest(frozen_source.FREEZE),
        "strict_audit_source_freeze_sha256": digest(FREEZE),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-plan", type=Path, required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit_saved(private_plan=args.private_plan,
                                 attempt=args.attempt), sort_keys=True))


if __name__ == "__main__":
    main()
