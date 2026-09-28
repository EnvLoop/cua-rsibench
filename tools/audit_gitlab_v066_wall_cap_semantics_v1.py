"""Clarify that GitLab prospective per-ID wall time is checked post hoc."""

from __future__ import annotations

import ast
from hashlib import sha256
import inspect
import json
import os
from pathlib import Path

from gitlab_world import prospective_final_controls_v066 as lane


ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "docs/evidence/gitlab-v066-prospective-final-control-plan-2026-09-28.json"
PUBLIC = ROOT / "docs/evidence/gitlab-v066-prospective-wall-cap-clarification-2026-09-28.json"


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def audit() -> dict:
    raw = FROZEN.read_bytes()
    frozen = json.loads(raw)
    source = inspect.getsource(lane.run_loop)
    tree = ast.parse(source)
    function = tree.body[0]
    require(isinstance(function, ast.AsyncFunctionDef) and
            function.name == "run_loop" and
            frozen.get("schema") ==
            "envloop-gitlab-v066-prospective-control-plan-public-v1" and
            frozen.get("candidate_id_count") == 100 and
            frozen.get("max_wall_seconds_per_id") == 7200 and
            frozen.get("aggregate_hard_wall_cap_hours") == 200 and
            frozen.get("current_v066_completed_control_ids") == 0 and
            frozen.get("official_final_admitted") == 0,
            "frozen_prospective_control_plan_or_runner_changed")
    calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]
    execute_lines = [node.lineno for node in ast.walk(function)
                     if isinstance(node, ast.Await) and
                     isinstance(node.value, ast.Call) and
                     isinstance(node.value.func, ast.Name) and
                     node.value.func.id == "execute_one"]
    bound_lines = [node.lineno for node in ast.walk(function)
                   if isinstance(node, ast.Compare) and
                   any(isinstance(candidate, ast.Subscript) and
                       isinstance(candidate.slice, ast.Constant) and
                       candidate.slice.value == "max_wall_seconds_per_task"
                       for candidate in [node.left, *node.comparators])]
    watchdogs = [node for node in calls
                 if isinstance(node.func, ast.Attribute) and
                 node.func.attr in {"wait_for", "timeout", "timeout_at"}]
    require(len(execute_lines) == 1 and len(bound_lines) == 1 and
            execute_lines[0] < bound_lines[0] and not watchdogs,
            "controller_wall_cap_is_not_posthoc_as_expected")
    source_raw = Path(lane.__file__).read_bytes()
    return {
        "schema": "envloop-gitlab-v066-wall-cap-clarification-v1",
        "status": "posthoc_acceptance_limit_not_runtime_watchdog",
        "frozen_public_plan_sha256": sha256(raw).hexdigest(),
        "controller_source_sha256": sha256(source_raw).hexdigest(),
        "controller_execute_one_await_precedes_elapsed_check": True,
        "outer_per_id_timeout_or_cancellation_present": False,
        "recorded_max_wall_seconds_per_id": 7200,
        "nominal_100_id_acceptance_envelope_hours": 200,
        "hard_100_id_runtime_upper_bound_hours": None,
        "incorrect_prior_public_field": "aggregate_hard_wall_cap_hours",
        "current_v066_completed_control_ids": 0,
        "official_final_admitted": 0,
        "auditor_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
    }


def main() -> None:
    result = audit()
    require(not PUBLIC.exists(), "fresh_wall_cap_clarification_required")
    fd = os.open(PUBLIC, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "wb") as stream:
        stream.write(json.dumps(result, sort_keys=True,
                                separators=(",", ":")).encode())
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps({"status": result["status"],
                      "hard_100_id_runtime_upper_bound_hours": None,
                      "official_final_admitted": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
