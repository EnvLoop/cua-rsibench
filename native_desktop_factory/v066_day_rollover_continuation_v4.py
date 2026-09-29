"""Source-frozen, durable Desktop continuation for 89 never-intended IDs.

This is a new evaluator-control epoch.  It retains the stopped v3 batch and
the 35 historical evaluator files verbatim, never selects any of the three
partial IDs, and does not dispatch a model or admit an official final task.
Every new one- or two-ID root-owned batch must pass independent readback
before another ID can begin.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import signal
import threading
from unittest.mock import patch

from . import v066_day_rollover_continuation_v2 as v2
from . import v066_day_rollover_continuation_v3 as v3
from . import v066_day_rollover_attrition_audit_v4 as independent
from .reconcile_interrupted_sweep import active_hashes
from .v066_day_rollover_bridge import combined_budget
from .v066_final_freeze import digest


SCHEMA = "cua-native-wdi-v066-untouched-continuation-freeze-private-v4"
PUBLIC_SCHEMA = "cua-native-wdi-v066-untouched-continuation-freeze-public-v4"
RUN_SCHEMA = "cua-native-wdi-v066-untouched-continuation-run-private-v4"
CHILD = "native_desktop_factory.v066_day_rollover_durable_child_v4"
SOURCE_NAMES = (
    "native_desktop_factory/qwen_v066_adapter_v4_strict.py",
    "native_desktop_factory/v066_day_rollover_durable_child_v4.py",
    "native_desktop_factory/v066_day_rollover_attrition_audit_v4.py",
    "native_desktop_factory/v066_day_rollover_continuation_v4.py",
)


def _sources() -> dict[str, str]:
    repo = Path(__file__).resolve().parents[1]
    return {name: digest((repo / name).read_bytes()) for name in SOURCE_NAMES}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _private(path: Path) -> bytes:
    if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o077:
        raise ValueError("Private v4 continuation evidence absent")
    return path.read_bytes()


def _audit(*, frozen: dict, active_run_dir: Path | None = None):
    return independent.audit(
        v3_freeze=Path(frozen["v3_freeze_path"]),
        caret_freeze=Path(frozen["caret_freeze_path"]),
        batch_one=Path(frozen["v3_batch_one_path"]),
        stopped_batch_two=Path(frozen["v3_stopped_batch_two_path"]),
        expected_first_eleven_trees=frozen["first_eleven_task_tree_sha256s"],
        v4_wrapper_sha=frozen["source_sha256s"][SOURCE_NAMES[1]],
        active_run_dir=active_run_dir)


def prepare(*, v3_freeze: Path, caret_freeze: Path,
            batch_one: Path, stopped_batch_two: Path,
            freeze: Path, public: Path) -> dict:
    if freeze.exists() or public.exists():
        raise ValueError("Exclusive v4 source-freeze paths required")
    private_audit, progress, paths, _rows = independent.audit(
        v3_freeze=v3_freeze, caret_freeze=caret_freeze,
        batch_one=batch_one, stopped_batch_two=stopped_batch_two)
    if (progress["independently_accepted_complete_trios"] != 8 or
            progress["original_quarantined_task_count"] != 2 or
            progress["new_stopped_v3_partial_task_count"] != 1 or
            progress["never_intended_task_count"] != 89 or
            progress["four_root_full_lease_intents_charged"] != 55):
        raise ValueError("v4 freeze requires exact 8/2/1/89 pre-result state")
    active, count = active_hashes()
    if active or count:
        raise ValueError("Provider must be active-zero before v4 source freeze")
    projected = combined_budget(
        original_root=paths["old_original_root"],
        failed_root=paths["old_caret_root"],
        failed_scoped_root=paths["old_failed_scoped_root"],
        fresh_root=paths["attempts_root"], proposed_fresh_intents=89 * 3)
    if (projected["combined_full_lease_intents"] != 322 or
            Decimal(projected["combined_conservative_reserved_usd"]) !=
            Decimal(322) / Decimal(6)):
        raise ValueError("v4 untouched-ID full-lease projection changed")
    old_v3 = json.loads(_private(v3_freeze))
    old_v2 = Path(old_v3["base_freeze_path"])
    frozen = {
        "schema": SCHEMA,
        "status": "frozen_before_new_v4_untouched_create",
        "recorded_utc": _now(),
        "v3_freeze_path": str(v3_freeze.resolve()),
        "v3_freeze_sha256": digest(_private(v3_freeze)),
        "v2_freeze_sha256": digest(_private(old_v2)),
        "caret_freeze_path": str(caret_freeze.resolve()),
        "caret_freeze_sha256": digest(_private(caret_freeze)),
        "v3_batch_one_path": str(batch_one.resolve()),
        "v3_batch_one_sha256": digest(_private(batch_one)),
        "v3_stopped_batch_two_path": str(stopped_batch_two.resolve()),
        "v3_stopped_batch_two_sha256": digest(_private(stopped_batch_two)),
        "attempts_root": str(paths["attempts_root"].resolve()),
        "public_path": str(public.resolve()),
        "source_sha256s": _sources(),
        "frozen_historical_35_source_sha256s":
            json.loads(_private(old_v2))["frozen_full100_source_sha256s"],
        "first_eleven_task_tree_sha256s":
            private_audit["first_eleven_task_tree_sha256s"],
        "candidate_inventory_sha256":
            private_audit["candidate_inventory_sha256"],
        "initial_complete_trios": 8,
        "original_quarantined_ids": 2,
        "new_stopped_v3_partial_ids": 1,
        "never_intended_ids": 89,
        "initial_four_root_full_lease_intents": 55,
        "projected_four_root_full_lease_intents": 322,
        "projected_four_root_reserved_usd_upper":
            projected["combined_conservative_reserved_usd"],
        "one_or_two_ids_per_root_batch": True,
        "same_id_retry_authorized": False,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    private_sha = v3._write_new(freeze, frozen)
    published = {
        "schema": PUBLIC_SCHEMA,
        "status": "source_frozen_before_new_v4_untouched_create",
        "private_freeze_sha256": private_sha,
        "source_sha256s": frozen["source_sha256s"],
        "historical_v3_freeze_sha256": frozen["v3_freeze_sha256"],
        "historical_caret_prototype_freeze_sha256":
            frozen["caret_freeze_sha256"],
        "candidate_inventory_sha256": frozen["candidate_inventory_sha256"],
        "initial_complete_gui_trios_independently_audited": 8,
        "original_quarantined_task_count": 2,
        "new_stopped_v3_partial_task_count": 1,
        "never_intended_task_count": 89,
        "charged_four_root_full_lease_intents": 55,
        "projected_four_root_full_lease_intents": 322,
        "projected_four_root_reserved_usd_upper":
            frozen["projected_four_root_reserved_usd_upper"],
        "one_or_two_ids_per_root_batch": True,
        "durable_budget_intent_and_receipt_required": True,
        "same_id_retry_authorized": False,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    v3._write_new(public, published, public=True)
    return published


def validate_live(*, freeze: Path,
                  active_run_dir: Path | None = None):
    raw = _private(freeze)
    frozen = json.loads(raw)
    if (frozen.get("schema") != SCHEMA or
            frozen.get("status") != "frozen_before_new_v4_untouched_create" or
            frozen.get("source_sha256s") != _sources() or
            frozen.get("same_id_retry_authorized") is not False or
            frozen.get("official_final_admissions") != 0):
        raise ValueError("v4 source freeze changed")
    published = json.loads(Path(frozen["public_path"]).read_bytes())
    if (published.get("schema") != PUBLIC_SCHEMA or
            published.get("private_freeze_sha256") != digest(raw) or
            published.get("source_sha256s") != frozen["source_sha256s"]):
        raise ValueError("Published v4 source binding changed")
    for path_field, sha_field in (
        ("v3_freeze_path", "v3_freeze_sha256"),
        ("caret_freeze_path", "caret_freeze_sha256"),
        ("v3_batch_one_path", "v3_batch_one_sha256"),
        ("v3_stopped_batch_two_path", "v3_stopped_batch_two_sha256"),
    ):
        if digest(_private(Path(frozen[path_field]))) != frozen[sha_field]:
            raise ValueError("Retained v3/caret evidence changed")
    old_v3 = json.loads(_private(Path(frozen["v3_freeze_path"])))
    if (digest(_private(Path(old_v3["base_freeze_path"]))) !=
            frozen["v2_freeze_sha256"] or
            json.loads(_private(Path(old_v3["base_freeze_path"])))[
                "frozen_full100_source_sha256s"] !=
            frozen["frozen_historical_35_source_sha256s"]):
        raise ValueError("Historical 35-file Desktop runtime changed")
    private, progress, paths, rows = _audit(
        frozen=frozen, active_run_dir=active_run_dir)
    if (private["candidate_inventory_sha256"] !=
            frozen["candidate_inventory_sha256"] or
            private["first_eleven_task_tree_sha256s"] !=
            frozen["first_eleven_task_tree_sha256s"] or
            paths["attempts_root"].resolve() !=
            Path(frozen["attempts_root"]).resolve()):
        raise ValueError("v4 roster or old partial evidence drifted")
    run_root = paths["attempts_root"].parent / "v066-v4-untouched-runs"
    if run_root.exists():
        entries = sorted(run_root.iterdir())
        if any(not entry.is_dir() or
               entry.name != f"batch-{index:04d}" or
               not (entry / "run-receipt.json").is_file()
               for index, entry in enumerate(entries, 1)):
            raise ValueError("v4 batch names or journals are nonsequential")
    completed = []
    for path in sorted(run_root.glob("batch-*/run-receipt.json")):
        receipt = json.loads(_private(path))
        is_active = (active_run_dir is not None and
                     path.parent == active_run_dir and
                     receipt.get("status") == "started")
        if (receipt.get("schema") != RUN_SCHEMA or
                receipt.get("freeze_sha256") != digest(raw) or
                receipt.get("official_final_admissions") != 0 or
                receipt.get("official_final_model_attempts") != 0 or
                not (receipt.get("status") ==
                     "bounded_completed_and_audited" or is_active)):
            raise ValueError("A v4 bounded batch is unfinished or changed")
        selected = receipt.get("selected_private_task_ids", [])
        if not 1 <= len(selected) <= 2 or len(set(selected)) != len(selected):
            raise ValueError("A v4 batch changed its one/two-ID bound")
        if not is_active:
            outcomes = receipt.get("task_outcomes", [])
            if (len(outcomes) != len(selected) or
                    any(item.get("status") != "provisional_trio_complete"
                        for item in outcomes)):
                raise ValueError("A completed v4 batch lacks complete trios")
            completed.extend(selected)
    accepted = [rows[index]["task_id"] for index in
                range(11, 11 + progress["v4_new_complete_trios"])]
    if active_run_dir is None and completed != accepted:
        raise ValueError("v4 batch journals do not match independently accepted IDs")
    if active_run_dir is not None and completed != accepted[:len(completed)]:
        raise ValueError("Prior v4 batches do not match accepted prefix")
    return frozen, progress, paths, rows


class _Interrupted(Exception):
    pass


def _on_term(_signum, _frame) -> None:
    raise _Interrupted("Root-owned v4 batch interrupted")


def run_batch(*, freeze: Path, run_dir: Path,
              max_new_ids: int, execute: bool = False) -> dict:
    frozen, progress, paths, rows = validate_live(freeze=freeze)
    if not 1 <= max_new_ids <= 2:
        raise ValueError("One or two untouched IDs per root-owned batch required")
    start = 11 + progress["v4_new_complete_trios"]
    selected = rows[start:start + max_new_ids]
    if not selected:
        return {"status": "all_89_untouched_id_trios_audited",
                "new_ids_selected": 0,
                "independently_accepted_complete_trios":
                    progress["independently_accepted_complete_trios"],
                "official_final_admissions": 0}
    if any((paths["attempts_root"] / row["task_id"]).exists()
           for row in selected):
        raise ValueError("Selected v4 ID already has an attempt root")
    projected = combined_budget(
        original_root=paths["old_original_root"],
        failed_root=paths["old_caret_root"],
        failed_scoped_root=paths["old_failed_scoped_root"],
        fresh_root=paths["attempts_root"],
        proposed_fresh_intents=3 * len(selected))
    if projected["combined_full_lease_intents"] != (
            progress["four_root_full_lease_intents_charged"] +
            3 * len(selected)):
        raise ValueError("v4 precreate full-lease accounting changed")
    if not execute:
        return {"status": "offline_bounded_v4_untouched_plan",
                "new_ids_selected": len(selected),
                "existing_independently_accepted_trios":
                    progress["independently_accepted_complete_trios"],
                "projected_four_root_full_lease_intents":
                    projected["combined_full_lease_intents"],
                "official_final_admissions": 0}
    expected_parent = paths["attempts_root"].parent / "v066-v4-untouched-runs"
    next_number = (len(list(expected_parent.iterdir())) + 1
                   if expected_parent.exists() else 1)
    if (run_dir.exists() or run_dir.parent != expected_parent or
            run_dir.name != f"batch-{next_number:04d}"):
        raise ValueError("Exclusive root-owned v4 batch directory required")
    v3._sdk_and_credential()
    v3._power_snapshot()
    active, count = active_hashes()
    if active or count:
        raise ValueError("Provider must be active-zero before bounded v4 batch")
    run_dir.mkdir(parents=True, mode=0o700)
    run_dir.chmod(0o700)
    v3._sync_dir(run_dir.parent)
    v3._sync_dir(run_dir.parent.parent)
    journal = {
        "schema": RUN_SCHEMA, "status": "started",
        "created_utc": _now(),
        "freeze_sha256": digest(_private(freeze)),
        "selected_private_task_ids": [row["task_id"] for row in selected],
        "existing_complete_trios_before":
            progress["independently_accepted_complete_trios"],
        "task_outcomes": [], "official_final_model_attempts": 0,
        "official_final_admissions": 0,
    }
    journal_path = run_dir / "run-receipt.json"
    v3._write_new(journal_path, journal)
    gate = {
        "bridge_path": paths["bridge_path"],
        "original_root": paths["old_original_root"],
        "failed_root": paths["old_caret_root"],
        "public_calibration": paths["public_day_audit"],
        "private_calibration_audit": paths["private_day_audit"],
        "scoped_reference": paths["reference_path"],
        "runtime_freeze": paths["runtime_freeze"],
        "failed_private_stop": paths["failed_private_stop"],
        "failed_public_interruption": paths["failed_public_interruption"],
    }
    stop = threading.Event()
    old_term = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, _on_term)
    try:
        for row in selected:
            with patch.object(v3, "CHILD", CHILD), patch.dict(os.environ, {
                    "ENVLOOP_DESKTOP_V4_FREEZE": str(freeze.resolve()),
                    "ENVLOOP_DESKTOP_V4_RUN_DIR": str(run_dir.resolve())}):
                outcome = v3._task(
                    row=row, paths=paths, gate=gate,
                    wrapper_sha=frozen["source_sha256s"][SOURCE_NAMES[1]],
                    stop=stop)
            journal["task_outcomes"].append(outcome)
            v2._persist(journal_path, journal)
            if outcome.get("status") != "provisional_trio_complete":
                journal["status"] = "stopped_for_reconciliation"
                break
            active, count = active_hashes()
            if active or count:
                journal["status"] = "stopped_for_provider_cleanup_audit"
                break
            try:
                _frozen, current, _paths, _rows = validate_live(
                    freeze=freeze, active_run_dir=run_dir)
                if current["independently_accepted_complete_trios"] != (
                        journal["existing_complete_trios_before"] +
                        len(journal["task_outcomes"])):
                    raise ValueError("New v4 trio was not independently accepted")
                journal["independently_accepted_complete_trios_after"] = (
                    current["independently_accepted_complete_trios"])
                v2._persist(journal_path, journal)
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
    return {"status": journal["status"],
            "new_ids_selected": len(selected),
            "new_complete_trios": sum(
                item.get("status") == "provisional_trio_complete"
                for item in journal["task_outcomes"]),
            "official_final_admissions": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "plan", "run"))
    parser.add_argument("--v3-freeze", type=Path)
    parser.add_argument("--caret-freeze", type=Path)
    parser.add_argument("--batch-one", type=Path)
    parser.add_argument("--stopped-batch-two", type=Path)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--public", type=Path)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--max-new-ids", type=int, default=1)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.mode == "prepare":
        if any(value is None for value in (args.v3_freeze, args.caret_freeze,
                                          args.batch_one,
                                          args.stopped_batch_two,
                                          args.public)):
            raise ValueError("Historical lineage and new public path required")
        result = prepare(
            v3_freeze=args.v3_freeze, caret_freeze=args.caret_freeze,
            batch_one=args.batch_one, stopped_batch_two=args.stopped_batch_two,
            freeze=args.freeze, public=args.public)
    else:
        result = run_batch(
            freeze=args.freeze, run_dir=args.run_dir or Path("unused"),
            max_new_ids=args.max_new_ids,
            execute=args.mode == "run" and args.execute)
    print(json.dumps(result, sort_keys=True))
    if result.get("status", "").startswith("stopped_"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
