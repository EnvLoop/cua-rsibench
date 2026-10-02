"""Source-bound v4 child for one untouched Desktop evaluator attempt.

The 35-file historical evaluator is unchanged.  This wrapper requires the
v4 continuation freeze, a started root-owned batch, and an fsynced intent
that names this exact child.  It substitutes only the strict, prospective
caret adapter and the established durable receipt writer.
"""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

from . import qwen_v066_adapter_v4_strict as strict
from . import v066_scoped_profile_final_attempt as original
from .v066_day_rollover_durable_child_v3 import durable_write_text
from .v066_final_freeze import LEASE_SECONDS


def _sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _flag(name: str) -> str:
    try:
        index = sys.argv.index(name)
        return sys.argv[index + 1]
    except (ValueError, IndexError):
        raise ValueError(f"Missing source-bound v4 child argument {name}") from None


def _verify_precreate_receipts(*, task_id: str, attempt: str,
                               wrapper_sha: str, intent_raw: bytes,
                               budget_raw: bytes) -> None:
    intent = json.loads(intent_raw)
    budget = json.loads(budget_raw)
    if (budget.get("schema") !=
            "cua-native-wdi-v066-precreate-budget-private-v3" or
            budget.get("status") != "fsynced_before_provider_create" or
            budget.get("task_id") != task_id or
            budget.get("attempt") != attempt or
            budget.get("provider_active_before_intent") != 0 or
            budget.get("storage_dispatch_ready") is not True or
            budget.get("credential_present") is not True or
            budget.get("sdk_versions") != {
                "e2b-desktop": "2.2.0", "e2b": "2.51.0",
                "Pillow": "11.3.0"} or
            budget.get("power", {}).get("source") not in
                ("AC Power", "Battery Power") or
            intent.get("schema") !=
            "cua-native-wdi-v066-final-control-intent-v1" or
            intent.get("status") != "recorded_before_provider_create" or
            intent.get("task_id") != task_id or
            intent.get("attempt") != attempt or
            intent.get("lease_seconds") != LEASE_SECONDS or
            intent.get("precreate_budget_sha256") != _sha(budget_raw) or
            intent.get("durable_child_wrapper_sha256") != wrapper_sha):
        raise ValueError("v4 child precreate budget or intent changed")


def _verify_batch_order(*, run: dict, root: Path,
                        task_id: str, attempt: str) -> None:
    selected = run.get("selected_private_task_ids", [])
    outcomes = run.get("task_outcomes", [])
    if (not 1 <= len(selected) <= 2 or
            not 0 <= len(outcomes) < len(selected) or
            any(row.get("private_task_id") != selected[index] or
                row.get("status") != "provisional_trio_complete"
                for index, row in enumerate(outcomes)) or
            task_id != selected[len(outcomes)]):
        raise ValueError("v4 child is not the next root-owned roster ID")
    order = ("positive", "near-miss", "cold-reset")
    index = order.index(attempt)
    task_root = root / task_id
    if ((task_root / attempt / "receipt.json").exists() or
            any((task_root / later).exists() for later in order[index + 1:])):
        raise ValueError("v4 child attempt order or exclusive receipt changed")
    for prior in order[:index]:
        receipt_path = task_root / prior / "receipt.json"
        if not receipt_path.is_file() or receipt_path.is_symlink():
            raise ValueError("v4 child lacks a completed prior attempt")
        receipt = json.loads(receipt_path.read_bytes())
        if (receipt.get("task_id") != task_id or
                receipt.get("attempt") != prior or
                receipt.get("status") != "control_passed" or
                receipt.get("is_running_after_kill") is not False):
            raise ValueError("v4 child prior attempt is incomplete")


def _verify_untouched_roster(*, frozen: dict, run: dict,
                             root: Path, candidate_root: Path) -> None:
    raw = (candidate_root / "candidate-inventory.json").read_bytes()
    if _sha(raw) != frozen.get("candidate_inventory_sha256"):
        raise ValueError("v4 child candidate inventory changed")
    inventory = json.loads(raw)
    roster = [row["task_id"] for row in inventory["tasks"]
              if row.get("split") == "final_candidate"]
    selected = run.get("selected_private_task_ids", [])
    if len(roster) != 100 or not 1 <= len(selected) <= 2:
        raise ValueError("v4 child final roster denominator changed")
    try:
        start = roster.index(selected[0])
    except (ValueError, IndexError):
        raise ValueError("v4 child selected ID absent from frozen roster") from None
    if start < 11 or selected != roster[start:start + len(selected)]:
        raise ValueError("v4 child selected a partial, reused, or skipped ID")
    for previous in roster[11:start]:
        for attempt in ("positive", "near-miss", "cold-reset"):
            receipt_path = root / previous / attempt / "receipt.json"
            if not receipt_path.is_file() or receipt_path.is_symlink():
                raise ValueError("v4 child skipped an incomplete earlier ID")
            receipt = json.loads(receipt_path.read_bytes())
            expected = ("cold_reset_observed" if attempt == "cold-reset"
                        else "control_passed")
            if (receipt.get("task_id") != previous or
                    receipt.get("attempt") != attempt or
                    receipt.get("status") != expected or
                    receipt.get("is_running_after_kill") is not False):
                raise ValueError("v4 child skipped an incomplete earlier ID")


def _precreate_gate() -> None:
    freeze_path = Path(os.environ.get("ENVLOOP_DESKTOP_V4_FREEZE", ""))
    run_dir = Path(os.environ.get("ENVLOOP_DESKTOP_V4_RUN_DIR", ""))
    if not freeze_path.is_file() or not run_dir.is_dir():
        raise ValueError("v4 source freeze or root-owned run absent")
    freeze_raw = freeze_path.read_bytes()
    frozen = json.loads(freeze_raw)
    if (frozen.get("schema") !=
            "cua-native-wdi-v066-untouched-continuation-freeze-private-v4" or
            frozen.get("status") != "frozen_before_new_v4_untouched_create" or
            frozen.get("same_id_retry_authorized") is not False or
            frozen.get("official_final_admissions") != 0):
        raise ValueError("v4 continuation freeze is not pre-result")
    repo = Path(__file__).resolve().parents[1]
    hashes = frozen.get("source_sha256s", {})
    names = (
        "native_desktop_factory/v066_day_rollover_durable_child_v4.py",
        "native_desktop_factory/qwen_v066_adapter_v4_strict.py",
    )
    if any(hashes.get(name) != _sha((repo / name).read_bytes())
           for name in names):
        raise ValueError("v4 child/adapter differs from source freeze")
    caret = json.loads(Path(frozen["caret_freeze_path"]).read_bytes())
    caret_sources = caret.get("v4_source_sha256s", {})
    if (len(caret_sources) != 4 or
            any(_sha((repo / name).read_bytes()) != expected
                for name, expected in caret_sources.items())):
        raise ValueError("Frozen cross-observation guard changed")
    run = json.loads((run_dir / "run-receipt.json").read_bytes())
    task_id, attempt = _flag("--task-id"), _flag("--attempt")
    root = Path(_flag("--attempts-root"))
    if (run.get("schema") !=
            "cua-native-wdi-v066-untouched-continuation-run-private-v4" or
            run.get("status") != "started" or
            run.get("freeze_sha256") != _sha(freeze_raw) or
            task_id not in run.get("selected_private_task_ids", []) or
            Path(frozen["attempts_root"]).resolve() != root.resolve() or
            attempt not in ("positive", "near-miss", "cold-reset")):
        raise ValueError("v4 child is not inside its root-owned bounded batch")
    _verify_untouched_roster(
        frozen=frozen, run=run, root=root,
        candidate_root=Path(_flag("--candidate-root")))
    _verify_batch_order(run=run, root=root, task_id=task_id,
                        attempt=attempt)
    intent_path = root / task_id / attempt / "intent.json"
    budget_path = intent_path.parent / "budget.json"
    if (any(not path.is_file() or path.is_symlink() or
            path.stat().st_mode & 0o077
            for path in (intent_path, budget_path))):
        raise ValueError("v4 child lacks private durable precreate receipts")
    _verify_precreate_receipts(
        task_id=task_id, attempt=attempt, wrapper_sha=hashes[names[0]],
        intent_raw=intent_path.read_bytes(), budget_raw=budget_path.read_bytes())


def main() -> None:
    _precreate_gate()
    attempt_dir = (Path(_flag("--attempts-root")) /
                   _flag("--task-id") / _flag("--attempt"))
    with patch.dict(os.environ, {
            "ENVLOOP_DESKTOP_V4_ATTEMPTS_ROOT": _flag("--attempts-root"),
            "ENVLOOP_DESKTOP_V4_ATTEMPT_DIR": str(attempt_dir)}), \
            patch.object(Path, "write_text", durable_write_text), \
            patch.object(original, "qwen_v066_adapter", strict):
        original.main()


if __name__ == "__main__":
    main()
