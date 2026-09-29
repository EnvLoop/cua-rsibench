"""Freeze a non-dispatchable Desktop v4d epoch after the v4c precreate stop.

This is a read-only provenance and budget audit followed by new private/public
source-freeze files. It never starts E2B, writes an attempt intent, or replays
the stopped v4c child. A future separately ratified controller must use a new
attempt root and the durable-output helper; the stopped intent remains charged.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path

from .reconcile_interrupted_sweep import active_hashes
from .v066_caret_full100_preflight import _tree_digest
from .v066_day_rollover_bridge import combined_budget
from .v066_day_rollover_continuation_v2 import _paths
from .v066_day_rollover_continuation_v3 import _write_new
from .v066_final_control_audit import _validate_trio
from .v066_final_freeze import digest, intent_budget
from .v066_scoped_profile_final_audit import _profile_receipt
from .v066_scoped_profile_final_controller import _final_rows
from .v066_day_rollover_reference import validate as validate_reference

SCHEMA = "cua-native-wdi-v066-v4d-continuation-freeze-private-v1"
PUBLIC_SCHEMA = "cua-native-wdi-v066-v4d-continuation-freeze-public-v1"
V4C_SOURCE_NAMES = (
    "native_desktop_factory/qwen_v066_adapter_v4_strict.py",
    "native_desktop_factory/v066_day_rollover_attrition_audit_v4.py",
    "native_desktop_factory/v066_day_rollover_continuation_v4.py",
    "native_desktop_factory/v066_day_rollover_durable_child_v4.py",
)
V4D_SOURCE_NAMES = (
    "native_desktop_factory/qwen_v066_adapter_v4_strict.py",
    "native_desktop_factory/v066_day_rollover_durable_child_v4d.py",
    "native_desktop_factory/v066_day_rollover_durable_output_v4d.py",
    "native_desktop_factory/v066_day_rollover_precreate_freeze_v4d.py",
)


def _private(path: Path) -> bytes:
    if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o077:
        raise ValueError("Private v4d provenance is absent or has unsafe mode")
    return path.read_bytes()


def _source_hashes(repo: Path, names: tuple[str, ...]) -> dict[str, str]:
    return {name: digest((repo / name).read_bytes()) for name in names}


def _prove_precreate(*, v4c: dict, terminal: dict,
                     stderr: bytes, budget_raw: bytes,
                     intent_raw: bytes, public_audit: dict,
                     repo: Path) -> None:
    outcome = terminal.get("task_outcomes", [])
    if len(outcome) != 1 or len(outcome[0].get("attempts", [])) != 1:
        raise ValueError("v4c terminal lacks the exact one-attempt stop")
    attempt = outcome[0]["attempts"][0]
    budget = json.loads(budget_raw)
    intent = json.loads(intent_raw)
    old_child = (repo / "native_desktop_factory/v066_day_rollover_durable_child_v4.py")
    old_source = old_child.read_text()
    if (terminal.get("status") != "stopped_for_reconciliation" or
            terminal.get("existing_complete_trios_before") != 8 or
            terminal.get("official_final_admissions") != 0 or
            terminal.get("official_final_model_attempts") != 0 or
            len(terminal.get("selected_private_task_ids", [])) != 1 or
            outcome[0].get("private_task_id") !=
                terminal["selected_private_task_ids"][0] or
            outcome[0].get("status") !=
                "stopped_after_invalid_or_uncertain_attempt" or
            attempt.get("attempt") != "positive" or
            attempt.get("exit_code") != 1 or
            attempt.get("status") != "missing_or_invalid_receipt" or
            attempt.get("receipt_sha256") is not None or
            attempt.get("sandbox_id_observed") is not False or
            attempt.get("child_process_exited") is not True or
            attempt.get("stdout_sha256") != digest(b"") or
            attempt.get("stderr_sha256") != digest(stderr) or
            attempt.get("budget_sha256") != digest(budget_raw) or
            attempt.get("intent_sha256") != digest(intent_raw) or
            budget.get("status") != "fsynced_before_provider_create" or
            budget.get("four_root_budget", {}).get(
                "combined_full_lease_intents") != 56 or
            budget.get("fresh_lane_budget", {}).get("combined_intents") != 30 or
            intent.get("status") != "recorded_before_provider_create" or
            intent.get("durable_child_wrapper_sha256") !=
                v4c["source_sha256s"][V4C_SOURCE_NAMES[3]] or
            b'ValueError: v4 child skipped an incomplete earlier ID' not in
                stderr or
            b'  File "' not in stderr or
            b'_verify_untouched_roster' not in stderr or
            b'original.main()' in stderr or
            old_source.index("_precreate_gate()", old_source.index("def main()")) >
                old_source.index("original.main()", old_source.index("def main()")) or
            public_audit.get("child_stderr_sha256") != digest(stderr) or
            public_audit.get("child_stderr_reproduced_sha256_match") is not True or
            public_audit.get("new_attempt_receipt_present") is not False or
            public_audit.get("new_sandbox_id_observed") is not False):
        raise ValueError("Exact hash-matched v4c precreate no-create proof absent")


def inspect(*, v4c_freeze: Path, terminal_path: Path,
            public_audit_path: Path, forensic_root: Path,
            new_attempts_root: Path, query_provider: bool = False) -> dict:
    repo = Path(__file__).resolve().parents[1]
    old_freeze_raw = _private(v4c_freeze)
    old = json.loads(old_freeze_raw)
    if (old.get("schema") !=
            "cua-native-wdi-v066-untouched-continuation-freeze-private-v4" or
            old.get("status") != "frozen_before_new_v4_untouched_create" or
            old.get("source_sha256s") != _source_hashes(repo, V4C_SOURCE_NAMES) or
            old.get("same_id_retry_authorized") is not False or
            old.get("official_final_admissions") != 0):
        raise ValueError("Immutable v4c source freeze changed")
    terminal_raw = _private(terminal_path)
    terminal = json.loads(terminal_raw)
    public_audit_raw = public_audit_path.read_bytes()
    public_audit = json.loads(public_audit_raw)
    stderr = _private(forensic_root / "replayed-main.stderr")
    private_audit_raw = _private(forensic_root / "v4c-terminal-audit.private.json")
    private_audit = json.loads(private_audit_raw)
    old_v3 = json.loads(_private(Path(old["v3_freeze_path"])))
    old_v2 = json.loads(_private(Path(old_v3["base_freeze_path"])))
    paths = _paths(old_v2["paths"])
    inventory_raw, rows = _final_rows(paths["candidate_root"])
    roster = [row["task_id"] for row in rows]
    roster_sha = digest((json.dumps(roster, separators=(",", ":")) + "\n").encode())
    if (len(roster) != 100 or roster_sha != old_v2["roster_sha256"] or
            digest(inventory_raw) != old["candidate_inventory_sha256"] or
            terminal.get("freeze_sha256") != digest(old_freeze_raw) or
            public_audit.get("private_freeze_sha256") != digest(old_freeze_raw) or
            public_audit.get("terminal_batch_receipt_sha256") !=
                digest(terminal_raw) or
            private_audit.get("run_receipt_sha256") != digest(terminal_raw) or
            private_audit.get("replayed_child_stderr_sha256") != digest(stderr)):
        raise ValueError("v4c terminal, forensic, or sorted roster binding changed")
    if terminal["selected_private_task_ids"] != [roster[11]]:
        raise ValueError("v4c stopped ID is not the first untouched sorted ID")
    expected_trees = {str(i): _tree_digest(paths["attempts_root"] /
                                         roster[i])[0] for i in range(11)}
    if expected_trees != old["first_eleven_task_tree_sha256s"]:
        raise ValueError("Historical eight complete/three partial trees changed")
    attempt_root = paths["attempts_root"] / roster[11] / "positive"
    budget_raw = _private(attempt_root / "budget.json")
    intent_raw = _private(attempt_root / "intent.json")
    if ((attempt_root / "receipt.json").exists() or
            (attempt_root.parent / "near-miss").exists() or
            (attempt_root.parent / "cold-reset").exists() or
            any((paths["attempts_root"] / task).exists() for task in roster[12:]) or
            new_attempts_root.exists()):
        raise ValueError("v4c partial, 88 untouched IDs, or new root changed")
    _prove_precreate(
        v4c=old, terminal=terminal, stderr=stderr,
        budget_raw=budget_raw, intent_raw=intent_raw,
        public_audit=public_audit, repo=repo)
    # Reopen the old saved OOXML, near-negative, reset, and profile controls.
    reference, reference_sha = validate_reference(
        path=paths["reference_path"], private_audit=paths["private_day_audit"],
        public_audit=paths["public_day_audit"])
    salt = json.loads(_private(paths["private_map"]))["variant_salt"]
    common = {
        "profile_sha": digest(_private(paths["profile_private"])),
        "guest_sha": digest(paths["guest_public"].read_bytes()),
        "private_salt": salt,
        "ratification_sha": digest(_private(paths["action_ratification"])),
        "reservation_sha": digest(_private(paths["reservation"])),
    }
    sandbox_ids: set[str] = set()
    for index in list(range(7)) + [9]:
        row = rows[index]
        result = _validate_trio(
            paths["candidate_root"], paths["attempts_root"], row, **common)
        ids = _profile_receipt(
            candidate_root=paths["candidate_root"],
            attempts_root=paths["attempts_root"],
            task_id=row["task_id"], workflow=row["workflow"],
            reference=reference, reference_sha=reference_sha,
            runtime_sha=digest(_private(paths["runtime_freeze"])),
            bridge_sha=digest(_private(paths["bridge_path"])))
        if (result.get("prospective_controls_passed") is not True or
                len(ids) != 3 or any(item in sandbox_ids for item in ids)):
            raise ValueError("Retained eight saved/profile controls changed")
        sandbox_ids.update(ids)
    if len(sandbox_ids) != 24:
        raise ValueError("Retained E2B guest uniqueness changed")
    for index in (7, 8, 10):
        partial = paths["attempts_root"] / roster[index]
        if not partial.is_dir() or (partial / "cold-reset").exists():
            raise ValueError("Original three quarantined partial IDs changed")
    fresh_intents = intent_budget(paths["attempts_root"])
    cost = combined_budget(
        original_root=paths["old_original_root"],
        failed_root=paths["old_caret_root"],
        failed_scoped_root=paths["old_failed_scoped_root"],
        fresh_root=paths["attempts_root"], proposed_fresh_intents=0)
    if (fresh_intents["existing_intents"] != 30 or
            cost["combined_full_lease_intents"] != 56 or
            Decimal(cost["combined_conservative_reserved_usd"]) !=
                Decimal(56) / Decimal(6)):
        raise ValueError("Current four-root full-lease accounting changed")
    active_count = None
    if query_provider:
        _active, active_count = active_hashes()
        if active_count != 0:
            raise ValueError("E2B running sandboxes remain before v4d freeze")
    return {
        "old_v4c_freeze_sha256": digest(old_freeze_raw),
        "terminal_batch_sha256": digest(terminal_raw),
        "public_terminal_audit_sha256": digest(public_audit_raw),
        "private_forensic_audit_sha256": digest(private_audit_raw),
        "replayed_stderr_sha256": digest(stderr),
        "precreate_budget_sha256": digest(budget_raw),
        "precreate_intent_sha256": digest(intent_raw),
        "candidate_inventory_sha256": digest(inventory_raw),
        "sorted_final_roster_sha256": roster_sha,
        "current_four_root_full_lease_intents": 56,
        "current_four_root_reserved_usd_upper": cost[
            "combined_conservative_reserved_usd"],
        "projected_new_root_full_lease_intents": 267,
        "projected_five_root_full_lease_intents": 323,
        "projected_five_root_reserved_usd_upper": str(Decimal(323) / Decimal(6)),
        "historical_complete_trios": 8,
        "historical_partial_ids": 3,
        "new_precreate_partial_ids": 1,
        "never_intended_ids": 88,
        "provider_running_sandboxes_at_query": active_count,
        "new_attempts_root": str(new_attempts_root.resolve()),
        "source_sha256s": _source_hashes(repo, V4D_SOURCE_NAMES),
        "same_intent_replay_authorized": False,
        "fresh_clone_retry_candidate_eligible": True,
        "dispatch_authorized": False,
        "official_final_admissions": 0,
        "official_final_model_attempts": 0,
    }


def prepare(*, v4c_freeze: Path, terminal_path: Path,
            public_audit_path: Path, forensic_root: Path,
            new_attempts_root: Path, freeze: Path, public: Path,
            query_provider: bool = False) -> dict:
    if freeze.exists() or public.exists():
        raise ValueError("Exclusive v4d freeze paths required")
    inspected = inspect(
        v4c_freeze=v4c_freeze, terminal_path=terminal_path,
        public_audit_path=public_audit_path, forensic_root=forensic_root,
        new_attempts_root=new_attempts_root, query_provider=query_provider)
    if inspected["provider_running_sandboxes_at_query"] is None:
        raise ValueError("Live active-zero provider check required for freeze")
    private = {
        "schema": SCHEMA,
        "status": "frozen_before_new_v4d_create",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        **inspected,
        "v4c_freeze_path": str(v4c_freeze.resolve()),
        "v4c_terminal_batch_path": str(terminal_path.resolve()),
        "v4c_public_terminal_audit_path": str(public_audit_path.resolve()),
        "private_forensic_root": str(forensic_root.resolve()),
        "public_path": str(public.resolve()),
        "sorted_first_retry_roster_index": 11,
        "one_use_new_intent_only": True,
    }
    private_sha = _write_new(freeze, private)
    published = {
        "schema": PUBLIC_SCHEMA,
        "status": "frozen_without_dispatch_authority",
        "private_freeze_sha256": private_sha,
        "old_v4c_freeze_sha256": inspected["old_v4c_freeze_sha256"],
        "terminal_batch_sha256": inspected["terminal_batch_sha256"],
        "public_terminal_audit_sha256": inspected[
            "public_terminal_audit_sha256"],
        "private_forensic_audit_sha256": inspected[
            "private_forensic_audit_sha256"],
        "replayed_stderr_sha256": inspected["replayed_stderr_sha256"],
        "candidate_inventory_sha256": inspected[
            "candidate_inventory_sha256"],
        "sorted_final_roster_sha256": inspected[
            "sorted_final_roster_sha256"],
        "current_four_root_full_lease_intents": 56,
        "current_four_root_reserved_usd_upper": inspected[
            "current_four_root_reserved_usd_upper"],
        "projected_new_root_full_lease_intents": 267,
        "projected_five_root_full_lease_intents": 323,
        "projected_five_root_reserved_usd_upper": inspected[
            "projected_five_root_reserved_usd_upper"],
        "historical_complete_trios": 8,
        "historical_partial_ids": 3,
        "new_precreate_partial_ids": 1,
        "never_intended_ids": 88,
        "provider_running_sandboxes_at_freeze": 0,
        "source_sha256s": inspected["source_sha256s"],
        "same_intent_replay_authorized": False,
        "fresh_clone_retry_candidate_eligible": True,
        "dispatch_authorized": False,
        "official_final_admissions": 0,
        "official_final_model_attempts": 0,
    }
    _write_new(public, published, public=True)
    return published


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("inspect", "prepare"))
    parser.add_argument("--v4c-freeze", type=Path, required=True)
    parser.add_argument("--terminal-batch", type=Path, required=True)
    parser.add_argument("--public-terminal-audit", type=Path, required=True)
    parser.add_argument("--private-forensic-root", type=Path, required=True)
    parser.add_argument("--new-attempts-root", type=Path, required=True)
    parser.add_argument("--freeze", type=Path)
    parser.add_argument("--public", type=Path)
    parser.add_argument("--query-provider", action="store_true")
    args = parser.parse_args()
    if args.mode == "prepare":
        if args.freeze is None or args.public is None:
            raise ValueError("Private/public v4d freeze paths required")
        result = prepare(
            v4c_freeze=args.v4c_freeze,
            terminal_path=args.terminal_batch,
            public_audit_path=args.public_terminal_audit,
            forensic_root=args.private_forensic_root,
            new_attempts_root=args.new_attempts_root,
            freeze=args.freeze, public=args.public,
            query_provider=args.query_provider)
    else:
        result = inspect(
            v4c_freeze=args.v4c_freeze,
            terminal_path=args.terminal_batch,
            public_audit_path=args.public_terminal_audit,
            forensic_root=args.private_forensic_root,
            new_attempts_root=args.new_attempts_root,
            query_provider=args.query_provider)
    # CLI output is deliberately field-limited; private paths and task IDs stay local.
    print(json.dumps({key: result[key] for key in (
        "status", "current_four_root_full_lease_intents",
        "projected_five_root_full_lease_intents",
        "historical_complete_trios", "never_intended_ids",
        "dispatch_authorized", "official_final_admissions") if key in result},
        sort_keys=True))


if __name__ == "__main__":
    main()
