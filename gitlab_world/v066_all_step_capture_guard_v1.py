"""Source-only all-step GitLab GUI capture stability and dispatch ledger.

The existing actor, action parser, and worker stay unchanged. This scoped
wrapper may resample an observation only before that same step has a provider
intent, response, accepted frame, or GUI dispatch intent. It writes a private
dispatch intent before calling the original dispatcher and never retries a
provider request or a GUI action. No live run is enabled by this module.
"""

from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import time

from cursibench.scale_action_contract import ContractError

from . import teacher_episode_worker_v066 as worker


MAX_CAPTURE_ATTEMPTS_PER_STEP = 5
REJECTION_SCHEMA = "envloop-gitlab-v066-all-step-capture-reject-v1"
DISPATCH_INTENT_SCHEMA = "envloop-gitlab-v066-dispatch-intent-v1"
DISPATCH_RESULT_SCHEMA = "envloop-gitlab-v066-dispatch-result-v1"
_ACTIVE = False


class GuardError(RuntimeError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise GuardError(code)


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode()


def write_new(path: Path, value: dict) -> str:
    require(path.parent.is_dir() and not path.parent.is_symlink() and
            path.parent.stat().st_mode & 0o077 == 0 and
            not path.exists() and not path.is_symlink(),
            "all_step_guard_private_output_not_fresh")
    raw = canonical(value)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return sha256(raw).hexdigest()


def arm_for(run_dir: Path) -> str:
    return ("negative" if (run_dir / "negative-intent.private.json").exists()
            else "positive")


def step_paths(run_dir: Path, arm: str, step: int) -> dict[str, Path]:
    require(arm in {"positive", "negative"} and
            type(step) is int and 0 <= step < 90,
            "all_step_guard_arm_or_step_invalid")
    base = f"{arm}-step-{step:03d}"
    provider = run_dir / (arm + "-provider")
    return {
        "provider_intent": provider / f"step-{step:03d}-intent.private.json",
        "provider_request": provider / f"step-{step:03d}-request.private.json",
        "provider_response": provider / f"step-{step:03d}-response.private.json",
        "accepted_frame": run_dir / arm / "frames" / f"step-{step:03d}.png",
        "dispatch_intent": run_dir / f"{base}-dispatch-intent.private.json",
        "dispatch_result": run_dir / f"{base}-dispatch-result.private.json",
    }


def assert_before_step_intent(run_dir: Path, arm: str, step: int) -> None:
    paths = step_paths(run_dir, arm, step)
    require(all(not path.exists() and not path.is_symlink()
                for path in paths.values()),
            "all_step_capture_retry_forbidden_after_step_intent_or_action")


@contextmanager
def install(run_dir: Path, *, plan_sha256: str):
    """Patch one bounded train process; restore both methods on every exit."""
    global _ACTIVE
    run_dir = Path(run_dir).absolute()
    require(not _ACTIVE and run_dir.is_dir() and not run_dir.is_symlink() and
            run_dir.stat().st_mode & 0o077 == 0 and
            type(plan_sha256) is str and len(plan_sha256) == 64 and
            all(char in "0123456789abcdef" for char in plan_sha256),
            "all_step_guard_requires_exclusive_private_frozen_run")
    original_observe = worker._RealGitLabSession.observe
    original_dispatch = worker._RealGitLabSession.dispatch

    def observe(self, *, memory: str):
        step = self.step
        arm = arm_for(run_dir)
        visited = getattr(self, "_all_step_capture_guard_visited", None)
        if visited is None:
            visited = set()
            self._all_step_capture_guard_visited = visited
        require(step not in visited and self.latest is None,
                "same_step_observe_reentry_or_previous_frame_present")
        visited.add(step)
        for attempt in range(1, MAX_CAPTURE_ATTEMPTS_PER_STEP + 1):
            require(self.step == step,
                    "all_step_capture_session_step_changed_during_retry")
            assert_before_step_intent(run_dir, arm, step)
            try:
                observation = original_observe(self, memory=memory)
                if self.current_frame_id() != observation.frame_id:
                    raise ContractError("stale_frame")
                return observation
            except ContractError as exc:
                if str(exc) != "stale_frame":
                    raise
                write_new(
                    run_dir /
                    f"capture-reject-{arm}-step-{step:03d}-attempt-{attempt:02d}.private.json",
                    {"schema": REJECTION_SCHEMA,
                     "plan_sha256": plan_sha256,
                     "arm": arm, "step": step, "attempt": attempt,
                     "reason": "stale_frame",
                     "provider_intent_exists": False,
                     "accepted_frame_exists": False,
                     "gui_dispatch_intent_exists": False,
                     "provider_or_gui_replay_authorized": False},
                )
                if attempt == MAX_CAPTURE_ATTEMPTS_PER_STEP:
                    raise
                time.sleep(min(0.25 * attempt, 1.0))
        raise AssertionError("bounded all-step capture loop exhausted")

    def dispatch(self, action: dict):
        step = self.step
        arm = arm_for(run_dir)
        paths = step_paths(run_dir, arm, step)
        require(type(action) is dict and action.get("step") == step and
                paths["provider_intent"].is_file() and
                paths["provider_request"].is_file() and
                paths["provider_response"].is_file() and
                paths["accepted_frame"].is_file() and
                not paths["dispatch_intent"].exists() and
                not paths["dispatch_result"].exists(),
                "gui_dispatch_not_bound_to_one_paid_current_step")
        write_new(paths["dispatch_intent"], {
            "schema": DISPATCH_INTENT_SCHEMA,
            "plan_sha256": plan_sha256,
            "arm": arm, "step": step,
            "action": action,
            "provider_response_sha256": sha256(
                paths["provider_response"].read_bytes()).hexdigest(),
            "accepted_frame_sha256": sha256(
                paths["accepted_frame"].read_bytes()).hexdigest(),
            "provider_or_gui_replay_authorized": False,
        })
        try:
            result = original_dispatch(self, action)
        except BaseException as exc:
            write_new(paths["dispatch_result"], {
                "schema": DISPATCH_RESULT_SCHEMA,
                "plan_sha256": plan_sha256,
                "arm": arm, "step": step,
                "status": "dispatch_outcome_uncertain_or_failed",
                "reason_type": type(exc).__name__,
                "provider_or_gui_replay_authorized": False,
            })
            raise
        if (self.step != step + 1 or
                self.previous != {"status": "applied", "code": "ok"}):
            write_new(paths["dispatch_result"], {
                "schema": DISPATCH_RESULT_SCHEMA,
                "plan_sha256": plan_sha256,
                "arm": arm, "step": step,
                "status": "dispatch_outcome_uncertain_or_failed",
                "reason_type": "MissingAppliedAcknowledgment",
                "provider_or_gui_replay_authorized": False,
            })
            raise GuardError("original_gui_dispatch_did_not_acknowledge_application")
        write_new(paths["dispatch_result"], {
            "schema": DISPATCH_RESULT_SCHEMA,
            "plan_sha256": plan_sha256,
            "arm": arm, "step": step,
            "status": "original_gui_dispatch_acknowledged_applied",
            "action_sha256": sha256(canonical(action)).hexdigest(),
            "provider_or_gui_replay_authorized": False,
        })
        return result

    _ACTIVE = True
    worker._RealGitLabSession.observe = observe
    worker._RealGitLabSession.dispatch = dispatch
    try:
        yield
    finally:
        worker._RealGitLabSession.observe = original_observe
        worker._RealGitLabSession.dispatch = original_dispatch
        _ACTIVE = False
