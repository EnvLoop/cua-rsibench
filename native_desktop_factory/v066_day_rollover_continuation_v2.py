"""Pinned-runtime, bounded root-owned continuation after Desktop interruption.

Seven independently audited trios are retained. Roster positions 7 and 8
remain quarantined, with every first-attempt lease charged and no replay.
Only the 91 originally untouched IDs can be dispatched, at most two per root-
owned invocation. The unchanged frozen child and four-root bridge execute each
GUI attempt. A separate sidecar protocol is required before any same-ID retry.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import importlib.metadata
import json
import os
from pathlib import Path
import threading

from .reconcile_interrupted_sweep import active_hashes
from .v066_caret_full100_preflight import _tree_digest
from .v066_day_rollover_attrition_audit import audit as audit_attrition
from .v066_day_rollover_bridge import combined_budget
from .v066_final_freeze import digest
from .v066_scoped_profile_bridge import validate as validate_bridge
from .v066_scoped_profile_final_controller import _final_rows, _run_one_task


SCHEMA = "cua-native-wdi-v066-bounded-continuation-freeze-private-v2"
RUN_SCHEMA = "cua-native-wdi-v066-bounded-continuation-run-private-v2"
PATH_FIELDS = frozenset({
    "candidate_root", "attempts_root", "old_run_journal",
    "old_original_root", "old_caret_root", "old_failed_scoped_root",
    "bridge_path", "runtime_freeze", "action_ratification", "reservation",
    "public_day_audit", "private_day_audit", "reference_path",
    "failed_private_stop", "failed_public_interruption", "private_map",
    "profile_private", "guest_public", "fair_public", "orphan_intent",
    "orphan_reconciliation", "seven_audit",
})


def _write_new(path: Path, value: dict) -> str:
    raw = (json.dumps(value, sort_keys=True,
                      separators=(",", ":")) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return digest(raw)


def _write_public(path: Path, value: dict) -> str:
    raw = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return digest(raw)


def _persist(path: Path, value: dict) -> None:
    raw = (json.dumps(value, sort_keys=True,
                      separators=(",", ":")) + "\n").encode()
    temp = path.with_name(path.name + ".next")
    with temp.open("wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    temp.chmod(0o600)
    os.replace(temp, path)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _paths(value: dict) -> dict[str, Path]:
    if type(value) is not dict or set(value) != PATH_FIELDS:
        raise ValueError("Exact private continuation paths required")
    paths = {key: Path(item) for key, item in value.items()}
    if any(not path.is_absolute() for path in paths.values()):
        raise ValueError("Continuation evidence paths must be absolute")
    return paths


def _prefix_trees(paths: dict[str, Path], roster: list[str]) -> dict[str, str]:
    root = paths["attempts_root"]
    return {str(index): _tree_digest(root / roster[index])[0]
            for index in range(9)}


def _baseline(paths: dict[str, Path]) -> tuple[dict, dict, list[str]]:
    validate_bridge(
        bridge_path=paths["bridge_path"],
        candidate_root=paths["candidate_root"],
        original_root=paths["old_original_root"],
        failed_root=paths["old_caret_root"],
        fresh_root=paths["attempts_root"],
        action_ratification=paths["action_ratification"],
        public_calibration=paths["public_day_audit"],
        private_calibration_audit=paths["private_day_audit"],
        scoped_reference=paths["reference_path"],
        runtime_freeze=paths["runtime_freeze"],
        new_lane_reservation=paths["reservation"],
        failed_private_stop=paths["failed_private_stop"],
        failed_public_interruption=paths["failed_public_interruption"],
        profile_private=paths["profile_private"],
        guest_public=paths["guest_public"],
        fair_public=paths["fair_public"])
    attrition, aggregate = audit_attrition(
        candidate_root=paths["candidate_root"],
        attempts_root=paths["attempts_root"],
        old_run_journal=paths["old_run_journal"],
        reference_path=paths["reference_path"],
        private_day_audit=paths["private_day_audit"],
        public_day_audit=paths["public_day_audit"],
        private_map=paths["private_map"],
        profile_private=paths["profile_private"],
        guest_public=paths["guest_public"],
        action_ratification=paths["action_ratification"],
        reservation=paths["reservation"],
        runtime_freeze=paths["runtime_freeze"],
        bridge_path=paths["bridge_path"],
        historical_roots=(paths["old_original_root"],
                          paths["old_caret_root"],
                          paths["old_failed_scoped_root"]))
    _raw, rows = _final_rows(paths["candidate_root"])
    roster = [row["task_id"] for row in rows]
    return attrition, aggregate, roster


def _reconciliation(paths: dict[str, Path], roster: list[str]) -> tuple[dict, dict]:
    intent_raw = paths["orphan_intent"].read_bytes()
    receipt_raw = paths["orphan_reconciliation"].read_bytes()
    intent, receipt = json.loads(intent_raw), json.loads(receipt_raw)
    seven = json.loads(paths["seven_audit"].read_bytes())
    if (intent.get("schema") !=
            "cua-native-wdi-v066-orphan-teardown-intent-private-v1" or
            receipt.get("schema") !=
            "cua-native-wdi-v066-orphan-teardown-reconciliation-private-v1" or
            receipt.get("status") != "retired_or_expired_active_zero" or
            receipt.get("teardown_intent_sha256") != digest(intent_raw) or
            receipt.get("provider_active_after_count") != 0 or
            receipt.get("new_e2b_creates") != 0 or
            intent.get("known_cleaned_receipts") != 22 or
            len(intent.get("pending_receipts", [])) != 2 or
            {(row.get("index"), row.get("attempt"))
             for row in intent["pending_receipts"]} !=
            {(7, "near-miss"), (8, "positive")} or
            seven.get("schema") !=
            "cua-native-wdi-v066-day-rollover-prefix-audit-private-v1" or
            len(seven.get("completed_prefix", [])) != 7 or
            seven.get("distinct_fresh_sandbox_count") != 21 or
            seven.get("official_final_admissions") != 0):
        raise ValueError("Interrupted two attempts or seven-audit lineage changed")
    attempts = paths["attempts_root"]
    for row in intent["pending_receipts"]:
        directory = attempts / roster[row["index"]] / row["attempt"]
        if (digest((directory / "intent.json").read_bytes()) !=
                row["intent_sha256"] or
                digest((directory / "receipt.json").read_bytes()) !=
                row["receipt_sha256"]):
            raise ValueError("Quarantined first-attempt bytes changed")
    return intent, receipt


def build_freeze(*, paths: dict[str, Path]) -> tuple[dict, dict]:
    attrition, public, roster = _baseline(paths)
    _intent, receipt = _reconciliation(paths, roster)
    if (public["independently_accepted_complete_trios"] != 7 or
            public["quarantined_incomplete_task_ids"] != 2 or
            public["untouched_task_ids"] != 91 or
            len(list(paths["attempts_root"].glob("*/*/intent.json"))) != 24):
        raise ValueError("Initial interrupted Desktop attrition is not 7/2/91")
    budget = combined_budget(
        original_root=paths["old_original_root"],
        failed_root=paths["old_caret_root"],
        failed_scoped_root=paths["old_failed_scoped_root"],
        fresh_root=paths["attempts_root"],
        proposed_fresh_intents=91 * 3)
    if budget["combined_full_lease_intents"] != 323:
        raise ValueError("Untouched-ID continuation budget changed")
    raw_roster = (json.dumps(roster, separators=(",", ":")) + "\n").encode()
    frozen_sources = json.loads((Path(__file__).resolve().parents[1] /
        "docs/evidence/native-wdi-v066-day-rollover-runtime-freeze-2026-09-29.json").read_bytes())[
            "source_sha256s"]
    repo = Path(__file__).resolve().parents[1]
    if (len(frozen_sources) != 35 or
            any(digest((repo / name).read_bytes()) != sha
                for name, sha in frozen_sources.items())):
        raise ValueError("Original full100 evaluator source is no longer frozen")
    private = {
        "schema": SCHEMA,
        "status": "pre_result_bounded_untouched_91_only",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "paths": {key: str(path.resolve()) for key, path in paths.items()},
        "source_sha256s": {
            "controller": digest(Path(__file__).read_bytes()),
            "attrition_auditor": digest(Path(
                __file__).with_name("v066_day_rollover_attrition_audit.py").read_bytes())},
        "frozen_full100_source_sha256s": frozen_sources,
        "roster_sha256": digest(raw_roster),
        "original_run_journal_sha256":
            digest(paths["old_run_journal"].read_bytes()),
        "orphan_teardown_intent_sha256":
            digest(paths["orphan_intent"].read_bytes()),
        "orphan_reconciliation_sha256":
            digest(paths["orphan_reconciliation"].read_bytes()),
        "seven_independent_audit_sha256":
            digest(paths["seven_audit"].read_bytes()),
        "original_nine_task_trees_sha256": _prefix_trees(paths, roster),
        "raw_storage_ledger_sha256_at_freeze":
            attrition["current_raw_storage"]["ledger_sha256"],
        "initial_full_lease_intents": 24,
        "initial_complete_trios": 7,
        "quarantined_incomplete_task_ids": 2,
        "untouched_task_ids": 91,
        "prospective_new_untouched_intents": 273,
        "projected_all_root_full_lease_intents": 323,
        "projected_all_root_reserved_usd":
            budget["combined_conservative_reserved_usd"],
        "conditional_future_retry_trios": 2,
        "conditional_future_retry_intents_not_authorized": 6,
        "conditional_full_study_intents_if_separate_retry": 329,
        "conditional_full_study_reserved_usd_if_separate_retry": str(
            Decimal(329 * 600) / Decimal(3600)),
        "provider_active_before_freeze": 0,
        "same_id_retry_authorized_here": False,
        "automatic_replay_authorized": False,
        "actual_provider_billed_usd": None,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    aggregate = {
        "schema": "cua-native-wdi-v066-bounded-continuation-freeze-public-v2",
        "status": "source_frozen_before_any_new_untouched_id_create",
        "initial_complete_gui_trios_independently_audited": 7,
        "quarantined_incomplete_task_ids": 2,
        "untouched_task_ids": 91,
        "initial_full_lease_intents_charged": 24,
        "prospective_new_untouched_intents": 273,
        "projected_all_root_full_lease_intents": 323,
        "projected_all_root_reserved_usd":
            private["projected_all_root_reserved_usd"],
        "conditional_retry_intents_not_authorized": 6,
        "conditional_full_study_intents_if_separate_retry": 329,
        "conditional_full_study_reserved_usd_if_separate_retry":
            private["conditional_full_study_reserved_usd_if_separate_retry"],
        "same_id_retry_authorized_here": False,
        "dedicated_e2b_sdk_checked_before_intent": True,
        "automatic_replay_authorized": False,
        "actual_provider_billed_usd": None,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    return private, aggregate


def prepare(*, config_path: Path, freeze_path: Path,
            public_path: Path) -> dict:
    if freeze_path.exists() or public_path.exists():
        raise ValueError("New exclusive private/public continuation freeze paths required")
    paths = _paths(json.loads(config_path.read_bytes()))
    private, public = build_freeze(paths=paths)
    active, count = active_hashes()
    if active or count:
        raise ValueError("Provider must be active-zero before continuation freeze")
    freeze_sha = _write_new(freeze_path, private)
    public["private_freeze_sha256"] = freeze_sha
    public["controller_source_sha256"] = private["source_sha256s"]["controller"]
    public["attrition_auditor_source_sha256"] = private["source_sha256s"][
        "attrition_auditor"]
    public["seven_independent_audit_sha256"] = private[
        "seven_independent_audit_sha256"]
    public["orphan_reconciliation_sha256"] = private[
        "orphan_reconciliation_sha256"]
    public["provider_active_before_freeze"] = 0
    _write_public(public_path, public)
    return public


def validate_live(*, freeze_path: Path,
                  active_run_dir: Path | None = None) -> tuple[dict, dict, dict, list[dict]]:
    if (not freeze_path.is_file() or freeze_path.is_symlink() or
            freeze_path.stat().st_mode & 0o077):
        raise ValueError("Private continuation source freeze absent")
    frozen = json.loads(freeze_path.read_bytes())
    if (frozen.get("schema") != SCHEMA or frozen.get("status") !=
            "pre_result_bounded_untouched_91_only" or
            frozen.get("source_sha256s") != {
                "controller": digest(Path(__file__).read_bytes()),
                "attrition_auditor": digest(Path(
                    __file__).with_name("v066_day_rollover_attrition_audit.py").read_bytes())} or
            frozen.get("official_final_admissions") != 0 or
            frozen.get("same_id_retry_authorized_here") is not False):
        raise ValueError("Continuation controller or freeze changed")
    paths = _paths(frozen["paths"])
    repo = Path(__file__).resolve().parents[1]
    if any(digest((repo / name).read_bytes()) != sha
           for name, sha in frozen["frozen_full100_source_sha256s"].items()):
        raise ValueError("Paid child/four-root action source changed")
    attrition, public, roster = _baseline(paths)
    _reconciliation(paths, roster)
    roster_raw = (json.dumps(roster, separators=(",", ":")) + "\n").encode()
    if (digest(roster_raw) != frozen["roster_sha256"] or
            digest(paths["old_run_journal"].read_bytes()) !=
            frozen["original_run_journal_sha256"] or
            _prefix_trees(paths, roster) !=
            frozen["original_nine_task_trees_sha256"]):
        raise ValueError("Original interrupted source or first nine task bytes changed")
    accepted = [row["roster_index"] for row in attrition["accepted_trios"]]
    resumed = sorted(index for index in accepted if index >= 9)
    if (resumed != list(range(9, 9 + len(resumed))) or
            public["independently_accepted_complete_trios"] +
            public["untouched_task_ids"] + 2 != 100):
        raise ValueError("Continuation selected noncontiguous/easy task IDs")
    intent_count = len(list(paths["attempts_root"].glob("*/*/intent.json")))
    if intent_count != 24 + 3 * len(resumed):
        raise ValueError("Every resumed trio must charge exactly three leases")
    budget = combined_budget(
        original_root=paths["old_original_root"],
        failed_root=paths["old_caret_root"],
        failed_scoped_root=paths["old_failed_scoped_root"],
        fresh_root=paths["attempts_root"], proposed_fresh_intents=0)
    if (budget["combined_full_lease_intents"] != 50 + 3 * len(resumed) or
            intent_count > 297):
        raise ValueError("Continuation full-lease accounting changed")
    run_root = paths["attempts_root"].parent / "v066-continuation-runs"
    for path in run_root.glob("*/run-receipt.json"):
        prior = json.loads(path.read_bytes())
        status_ok = (prior.get("status") == "bounded_completed_and_audited" or
                     (active_run_dir is not None and
                      path.parent == active_run_dir and
                      prior.get("status") == "started"))
        if (prior.get("schema") != RUN_SCHEMA or not status_ok or
                prior.get("official_final_admissions") != 0):
            raise ValueError("A prior bounded continuation batch is unfinished")
    _raw, rows = _final_rows(paths["candidate_root"])
    return frozen, public, paths, rows


def run_batch(*, freeze_path: Path, run_dir: Path,
              max_new_ids: int, execute: bool = False) -> dict:
    frozen, progress, paths, rows = validate_live(freeze_path=freeze_path)
    if not 1 <= max_new_ids <= 2:
        raise ValueError("One or two untouched IDs per root-owned batch required")
    new = [row for index, row in enumerate(rows)
           if index >= 9 and not (paths["attempts_root"] / row["task_id"]).exists()]
    selected = new[:max_new_ids]
    if not selected:
        return {"status": "all_91_untouched_id_trios_audited",
                "new_ids_selected": 0,
                "independently_accepted_complete_trios":
                progress["independently_accepted_complete_trios"],
                "official_final_admissions": 0}
    combined_budget(
        original_root=paths["old_original_root"],
        failed_root=paths["old_caret_root"],
        failed_scoped_root=paths["old_failed_scoped_root"],
        fresh_root=paths["attempts_root"],
        proposed_fresh_intents=3 * len(selected))
    if not execute:
        return {"status": "offline_bounded_continuation_plan",
                "new_ids_selected": len(selected),
                "existing_independently_accepted_trios":
                progress["independently_accepted_complete_trios"],
                "official_final_admissions": 0}
    if (run_dir.exists() or run_dir.parent !=
            paths["attempts_root"].parent / "v066-continuation-runs"):
        raise ValueError("New private bounded continuation run directory required")
    if not os.environ.get("E2B_API_KEY"):
        raise ValueError("Private E2B credential absent before new intent")
    try:
        import e2b_desktop  # noqa: F401 - paid child must use this same Python.
        versions = {name: importlib.metadata.version(name)
                    for name in ("e2b-desktop", "e2b", "Pillow")}
    except (ImportError, importlib.metadata.PackageNotFoundError):
        raise ValueError("Dedicated Desktop SDK runtime absent before new intent") from None
    if versions != {"e2b-desktop": "2.2.0", "e2b": "2.51.0",
                    "Pillow": "11.3.0"}:
        raise ValueError("Dedicated Desktop SDK versions changed before new intent")
    active, count = active_hashes()
    if active or count:
        raise ValueError("Provider must be active-zero before bounded batch")
    run_dir.mkdir(parents=True, mode=0o700)
    run_dir.chmod(0o700)
    journal = {
        "schema": RUN_SCHEMA,
        "status": "started",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "freeze_sha256": digest(freeze_path.read_bytes()),
        "selected_private_task_ids": [row["task_id"] for row in selected],
        "existing_complete_trios_before":
            progress["independently_accepted_complete_trios"],
        "task_outcomes": [],
        "official_final_model_attempts": 0,
        "official_final_admissions": 0,
    }
    journal_path = run_dir / "run-receipt.json"
    _write_new(journal_path, journal)
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
    lock = threading.Lock()
    for row in selected:
        outcome = _run_one_task(
            row, candidate_root=paths["candidate_root"],
            attempts_root=paths["attempts_root"],
            private_map=paths["private_map"],
            profile_private=paths["profile_private"],
            guest_public=paths["guest_public"],
            fair_public=paths["fair_public"],
            ratification=paths["action_ratification"],
            reservation=paths["reservation"], gate=gate,
            stop=stop, intent_lock=lock)
        journal["task_outcomes"].append(outcome)
        _persist(journal_path, journal)
        if outcome.get("status") != "provisional_trio_complete":
            journal["status"] = "stopped_for_reconciliation"
            break
        active, count = active_hashes()
        if active or count:
            journal["status"] = "stopped_for_provider_cleanup_audit"
            break
        try:
            _frozen, current, _paths, _rows = validate_live(
                freeze_path=freeze_path, active_run_dir=run_dir)
            journal["independently_accepted_complete_trios_after"] = current[
                "independently_accepted_complete_trios"]
            _persist(journal_path, journal)
        except Exception as exc:
            journal["status"] = "stopped_after_independent_audit_failure"
            journal["audit_error_type"] = type(exc).__name__
            break
    else:
        journal["status"] = "bounded_completed_and_audited"
    journal["completed_utc"] = datetime.now(timezone.utc).isoformat()
    _persist(journal_path, journal)
    return {"status": journal["status"],
            "new_ids_selected": len(selected),
            "new_complete_trios": sum(
                row.get("status") == "provisional_trio_complete"
                for row in journal["task_outcomes"]),
            "official_final_admissions": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "plan", "run"))
    parser.add_argument("--config", type=Path)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--public", type=Path)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--max-new-ids", type=int, default=1)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.mode == "prepare":
        if args.config is None or args.public is None:
            raise ValueError("Private config and new public freeze required")
        result = prepare(config_path=args.config,
                         freeze_path=args.freeze, public_path=args.public)
    elif args.mode == "plan":
        result = run_batch(freeze_path=args.freeze,
                           run_dir=args.run_dir or Path("unused"),
                           max_new_ids=args.max_new_ids, execute=False)
    else:
        if args.run_dir is None:
            raise ValueError("New bounded run directory required")
        result = run_batch(freeze_path=args.freeze,
                           run_dir=args.run_dir,
                           max_new_ids=args.max_new_ids,
                           execute=args.execute)
    print(json.dumps(result, sort_keys=True))
    if result.get("status", "").startswith("stopped_"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
