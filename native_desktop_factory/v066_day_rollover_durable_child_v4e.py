"""Source-bound v4e Desktop child; no create without a reviewed batch permit."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

from . import qwen_v066_adapter_v4_strict as strict
from . import v066_day_rollover_precreate_freeze_v4d as old_proof
from . import v066_scoped_profile_final_attempt as original
from .v066_day_rollover_durable_child_v3 import durable_write_text
from .v066_day_rollover_durable_child_v4d import (
    _sha, _verify_batch_order, _verify_precreate_receipts,
)
from .v066_day_rollover_five_root_v4e import five_root_budget
from .v066_caret_full100_preflight import _tree_digest
from .v066_day_rollover_continuation_v2 import _paths
from .v066_scoped_profile_final_controller import _final_rows
from .v066_day_rollover_bridge import validate as validate_old_bridge


def _flag(name: str) -> str:
    try:
        return sys.argv[sys.argv.index(name) + 1]
    except (ValueError, IndexError):
        raise ValueError(f"Missing v4e child argument {name}") from None


def _private(path: Path) -> bytes:
    if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o077:
        raise ValueError("v4e child private control is absent or unsafe")
    return path.read_bytes()


def _old_paths(frozen: dict) -> dict[str, Path]:
    old_v4d = json.loads(_private(Path(frozen["v4d_freeze_path"])))
    old_v4c = json.loads(_private(Path(old_v4d["v4c_freeze_path"])))
    old_v3 = json.loads(_private(Path(old_v4c["v3_freeze_path"])))
    old_v2 = json.loads(_private(Path(old_v3["base_freeze_path"])))
    return _paths(old_v2["paths"])


def validate_original_bridge(*, bridge_path: Path, candidate_root: Path,
                             original_root: Path, failed_root: Path,
                             fresh_root: Path, action_ratification: Path,
                             public_calibration: Path,
                             private_calibration_audit: Path,
                             scoped_reference: Path, runtime_freeze: Path,
                             new_lane_reservation: Path,
                             failed_private_stop: Path,
                             failed_public_interruption: Path,
                             profile_private: Path, guest_public: Path,
                             fair_public: Path) -> tuple[dict, str]:
    """Validate the immutable old bridge plus the fifth-root budget.

    The frozen original evaluator imports its bridge validator into a local
    name. Patching only that name preserves all of its other checks and raw
    receipt code while allowing an isolated fifth attempt root.
    """
    frozen = json.loads(_private(Path(os.environ["ENVLOOP_DESKTOP_V4E_FREEZE"])))
    paths = _old_paths(frozen)
    if (fresh_root.resolve() != Path(frozen["new_attempts_root"]).resolve() or
            candidate_root.resolve() != paths["candidate_root"].resolve() or
            bridge_path.resolve() != paths["bridge_path"].resolve()):
        raise ValueError("v4e child new root or original bridge changed")
    old, old_sha = validate_old_bridge(
        bridge_path=bridge_path, candidate_root=candidate_root,
        original_root=original_root, failed_root=failed_root,
        fresh_root=paths["attempts_root"],
        action_ratification=action_ratification,
        public_calibration=public_calibration,
        private_calibration_audit=private_calibration_audit,
        scoped_reference=scoped_reference, runtime_freeze=runtime_freeze,
        new_lane_reservation=new_lane_reservation,
        profile_private=profile_private, guest_public=guest_public,
        fair_public=fair_public)
    five_root_budget(
        original_root=paths["old_original_root"],
        failed_root=paths["old_caret_root"],
        failed_scoped_root=paths["old_failed_scoped_root"],
        date_amended_root=paths["attempts_root"],
        new_root=fresh_root)
    return old, old_sha


def _verify_roster(*, frozen: dict, run: dict, root: Path,
                   candidate_root: Path) -> None:
    raw, rows = _final_rows(candidate_root)
    roster = [row["task_id"] for row in rows]
    roster_raw = (json.dumps(roster, separators=(",", ":")) + "\n").encode()
    selected = run.get("selected_private_task_ids", [])
    if (len(roster) != 100 or _sha(raw) != frozen["candidate_inventory_sha256"]
            or _sha(roster_raw) != frozen["sorted_final_roster_sha256"]
            or not 1 <= len(selected) <= 2):
        raise ValueError("v4e sorted roster or denominator changed")
    if run["mode"] == "untouched":
        try:
            start = roster.index(selected[0])
        except (ValueError, IndexError):
            raise ValueError("v4e selected task absent from roster") from None
        if start < 12 or selected != roster[start:start + len(selected)]:
            raise ValueError("v4e untouched run skipped or reused a task")
        previous = roster[12:start]
    elif run["mode"] == "clone":
        if selected != [roster[11]]:
            raise ValueError("v4e clone must be the exact precreate-stopped ID")
        previous = ()
    else:
        raise ValueError("v4e run mode changed")
    for task_id in previous:
        for attempt in ("positive", "near-miss", "cold-reset"):
            path = root / task_id / attempt / "receipt.json"
            receipt = json.loads(_private(path))
            expected = ("cold_reset_observed" if attempt == "cold-reset"
                        else "control_passed")
            if (receipt.get("task_id") != task_id or
                    receipt.get("attempt") != attempt or
                    receipt.get("status") != expected or
                    receipt.get("is_running_after_kill") is not False):
                raise ValueError("v4e child skipped an incomplete earlier ID")


def _precreate_gate() -> None:
    freeze_path = Path(os.environ.get("ENVLOOP_DESKTOP_V4E_FREEZE", ""))
    permit_path = Path(os.environ.get("ENVLOOP_DESKTOP_V4E_PERMIT", ""))
    run_dir = Path(os.environ.get("ENVLOOP_DESKTOP_V4E_RUN_DIR", ""))
    freeze_raw = _private(freeze_path)
    frozen = json.loads(freeze_raw)
    permit_raw = _private(permit_path)
    permit = json.loads(permit_raw)
    run = json.loads(_private(run_dir / "run-receipt.json"))
    repo = Path(__file__).resolve().parents[1]
    source = frozen.get("source_sha256s", {})
    for name in (
        "native_desktop_factory/v066_day_rollover_durable_child_v4e.py",
        "native_desktop_factory/qwen_v066_adapter_v4_strict.py",
        "native_desktop_factory/v066_day_rollover_five_root_v4e.py",
    ):
        if source.get(name) != _sha((repo / name).read_bytes()):
            raise ValueError("v4e child source differs from frozen source")
    if (frozen.get("schema") !=
            "cua-native-wdi-v066-five-root-freeze-private-v4e" or
            frozen.get("status") != "frozen_without_dispatch_authority" or
            frozen.get("dispatch_authorized") is not False or
            frozen.get("same_intent_replay_authorized") is not False or
            frozen.get("official_final_admissions") != 0 or
            permit.get("schema") !=
            "cua-native-wdi-v066-v4e-reviewed-dispatch-permit-private-v1" or
            permit.get("status") != "independently_reviewed_one_batch" or
            permit.get("dispatch_authorized") is not True or
            permit.get("freeze_sha256") != _sha(freeze_raw) or
            permit.get("source_sha256s") != source or
            permit.get("mode") != run.get("mode") or
            permit.get("batch_number") != run.get("batch_number") or
            permit.get("maximum_new_ids") !=
                len(run.get("selected_private_task_ids", [])) or
            run.get("schema") !=
            "cua-native-wdi-v066-v4e-bounded-run-private-v1" or
            run.get("status") != "started" or
            run.get("freeze_sha256") != _sha(freeze_raw) or
            run.get("permit_sha256") != _sha(permit_raw) or
            Path(run.get("permit_path", "")).resolve() != permit_path.resolve() or
            run.get("official_final_admissions") != 0 or
            run.get("official_final_model_attempts") != 0):
        raise ValueError("v4e independently reviewed dispatch permit absent")
    from .v066_day_rollover_controller_v4e import _checked_permit, _v4d_lineage
    _checked_permit(
        freeze=freeze_path, frozen=frozen, permit_path=permit_path,
        mode=run["mode"],
        selected=[{"task_id": task} for task in run["selected_private_task_ids"]],
        batch_number=run["batch_number"])
    _v4d_lineage(Path(frozen["v4d_freeze_path"]))
    task_id, attempt = _flag("--task-id"), _flag("--attempt")
    root = Path(_flag("--attempts-root"))
    if (root.resolve() != Path(frozen["new_attempts_root"]).resolve() or
            task_id not in run["selected_private_task_ids"] or
            attempt not in ("positive", "near-miss", "cold-reset")):
        raise ValueError("v4e child is outside its root-owned bounded run")
    old_raw = _private(Path(frozen["v4d_freeze_path"]))
    old = json.loads(old_raw)
    paths = _old_paths(frozen)
    if (_sha(old_raw) != frozen["v4d_freeze_sha256"] or
            old.get("dispatch_authorized") is not False or
            _sha(Path(old["public_path"]).read_bytes()) !=
                frozen["v4d_public_sha256"] or
            _sha(_private(paths["bridge_path"])) !=
                frozen["old_bridge_sha256"]):
        raise ValueError("v4e child retained source boundary changed")
    _verify_roster(frozen=frozen, run=run, root=root,
                   candidate_root=Path(_flag("--candidate-root")))
    _raw, ordered = _final_rows(paths["candidate_root"])
    for index in range(11):
        if (_tree_digest(paths["attempts_root"] /
                         ordered[index]["task_id"])[0] !=
                frozen["historical_first_eleven_task_tree_sha256s"][str(index)]):
            raise ValueError("v4e child retained control tree changed")
    stopped = paths["attempts_root"] / ordered[11]["task_id"] / "positive"
    old_budget_raw = _private(stopped / "budget.json")
    old_intent_raw = _private(stopped / "intent.json")
    if (_sha(old_budget_raw) !=
            frozen["old_precreate_budget_sha256"] or
            _sha(old_intent_raw) !=
            frozen["old_precreate_intent_sha256"] or
            (stopped / "receipt.json").exists()):
        raise ValueError("v4e child old precreate intent changed or replayed")
    old_v4c = json.loads(_private(Path(old["v4c_freeze_path"])))
    terminal_raw = _private(Path(old["v4c_terminal_batch_path"]))
    public_audit_raw = Path(old["v4c_public_terminal_audit_path"]).read_bytes()
    stderr_raw = _private(Path(old["private_forensic_root"]) /
                          "replayed-main.stderr")
    forensic_raw = _private(Path(old["private_forensic_root"]) /
                            "v4c-terminal-audit.private.json")
    if (_sha(terminal_raw) != old["terminal_batch_sha256"] or
            _sha(public_audit_raw) != old["public_terminal_audit_sha256"] or
            _sha(stderr_raw) != old["replayed_stderr_sha256"] or
            _sha(forensic_raw) != old["private_forensic_audit_sha256"]):
        raise ValueError("v4e child precreate forensic source changed")
    old_proof._prove_precreate(
        v4c=old_v4c, terminal=json.loads(terminal_raw),
        stderr=stderr_raw, budget_raw=old_budget_raw,
        intent_raw=old_intent_raw,
        public_audit=json.loads(public_audit_raw), repo=repo)
    _verify_batch_order(run=run, root=root, task_id=task_id, attempt=attempt)
    attempt_dir = root / task_id / attempt
    budget_raw = _private(attempt_dir / "budget.json")
    intent_raw = _private(attempt_dir / "intent.json")
    _verify_precreate_receipts(
        task_id=task_id, attempt=attempt,
        wrapper_sha=source[
            "native_desktop_factory/v066_day_rollover_durable_child_v4e.py"],
        intent_raw=intent_raw, budget_raw=budget_raw)
    budget = json.loads(budget_raw)
    intent = json.loads(intent_raw)
    if (budget.get("five_root_budget", {}).get("schema") !=
            "cua-native-wdi-v066-five-root-lease-budget-v4e" or
            intent.get("v4e_freeze_sha256") != _sha(freeze_raw) or
            intent.get("v4e_permit_sha256") != _sha(permit_raw) or
            intent.get("same_intent_replay_authorized") is not False):
        raise ValueError("v4e fifth-root precreate intent changed")


def main() -> None:
    _precreate_gate()
    attempt_dir = (Path(_flag("--attempts-root")) /
                   _flag("--task-id") / _flag("--attempt"))
    with patch.dict(os.environ, {
            "ENVLOOP_DESKTOP_V4_ATTEMPTS_ROOT": _flag("--attempts-root"),
            "ENVLOOP_DESKTOP_V4_ATTEMPT_DIR": str(attempt_dir)}), \
            patch.object(Path, "write_text", durable_write_text), \
            patch.object(original, "qwen_v066_adapter", strict), \
            patch.object(original, "validate_bridge", validate_original_bridge):
        original.main()


if __name__ == "__main__":
    main()
