"""Read-only cross-root budget and lineage gate for a fresh Desktop 100.

The old 22 intents and every byte of their failed/complete evidence remain in
their original root. A separate v0.6.6 caret-amended root may hold up to 300
new evaluator-control intents. This module never creates a sandbox, model
sample, intent, journal, or reservation; the bridge is evaluator-private and
must exist before a future paid dispatcher runs.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3
from urllib.parse import quote

from . import qwen_v066_adapter
from .v066_final_freeze import (
    LANE_CAP_USD, LEASE_SECONDS, MAX_SANDBOX_COUNT, digest,
    intent_budget, source_hashes as common_source_hashes,
    validate_lane,
)


OLD_ADAPTER_SHA256 = "03ae9e2e84caed09a4c36738f6aed2bdd840b4250927ca264d01a302dffe09a3"
OLD_RUNNER_SHA256 = "2c2911b5f50a36a7960feb653c58fc355794edd6b8c13710fac30222308764be"
OLD_INTENTS = 22
OLD_COMPLETE_TRIOS = 7
NEW_TASKS = 100
NEW_INTENTS = NEW_TASKS * 3
OLD_LEASE_CLEANUP_GRACE_SECONDS = 90
BRIDGE_SCHEMA = "cua-native-wdi-v066-caret-full100-cross-root-bridge-v1"


def _private(path: Path, *, directory: bool) -> bool:
    return (not path.is_symlink() and
            (path.is_dir() if directory else path.is_file()) and
            path.stat().st_mode & 0o077 == 0)


def _read_private(path: Path) -> tuple[dict, bytes]:
    if not _private(path, directory=False) or path.stat().st_size > 8_000_000:
        raise ValueError("Private cross-root evidence absent or public")
    raw = path.read_bytes()
    value = json.loads(raw)
    if type(value) is not dict:
        raise ValueError("Private cross-root evidence is not an object")
    return value, raw


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def _tree_digest(root: Path) -> tuple[str, int]:
    if not _private(root, directory=True):
        raise ValueError("Original attempts root is missing or public")
    h = hashlib.sha256()
    count = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("Original attempts tree contains a symlink")
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            h.update((relative + "\0" + str(path.stat().st_size) +
                      "\0" + _sha_file(path) + "\n").encode())
            count += 1
    return h.hexdigest(), count


def _read_only_storage(root: Path) -> dict:
    database = root / "storage-ledger.sqlite3"
    if (not _private(database, directory=False) or
            database.with_name(database.name + "-wal").exists()):
        raise ValueError("Original raw-frame ledger missing or live")
    uri = "file:" + quote(str(database.resolve()), safe="/") + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=5)
    try:
        connection.execute("PRAGMA query_only=ON")
        budget = connection.execute(
            "SELECT reserved_bytes FROM budget WHERE id=1").fetchone()
        rows = connection.execute(
            "SELECT path,bytes,sha256,status FROM evidence ORDER BY path").fetchall()
    finally:
        connection.close()
    if (budget is None or type(budget[0]) is not int or
            budget[0] != sum(row[1] for row in rows) or
            len({row[0] for row in rows}) != len(rows)):
        raise ValueError("Original raw-frame reservation changed")
    for relative, size, expected, status in rows:
        candidate = Path(relative)
        if (candidate.is_absolute() or ".." in candidate.parts or
                type(size) is not int or size <= 0 or
                type(expected) is not str or len(expected) != 64 or
                status != "written"):
            raise ValueError("Original raw-frame ledger has unresolved row")
        target = root / candidate
        if (not _private(target, directory=False) or
                target.stat().st_size != size or
                _sha_file(target) != expected):
            raise ValueError("Original raw-frame bytes changed")
    return {"ledger_sha256": _sha_file(database),
            "reserved_evidence_bytes": budget[0],
            "verified_raw_evidence_rows": len(rows)}


def _inventory(candidate_root: Path) -> tuple[dict[str, dict], str]:
    raw = (candidate_root / "candidate-inventory.json").read_bytes()
    inventory = json.loads(raw)
    rows = [row for row in inventory["tasks"]
            if row.get("split") == "final_candidate"]
    if (inventory.get("design_revision") != "v2-distinct-structures" or
            len(rows) != NEW_TASKS or
            len({row["task_id"] for row in rows}) != NEW_TASKS):
        raise ValueError("Frozen final task inventory changed")
    return {row["task_id"]: row for row in rows}, digest(raw)


def audit_retained_original(*, candidate_root: Path, original_root: Path,
                            old_run_journal: Path, old_ratification: Path,
                            old_reservation: Path) -> dict:
    """Reopen original receipts, frame ledger, and stopped run without writes."""
    if (original_root.name != "v066-final-gui" or
            not _private(original_root, directory=True)):
        raise ValueError("Original v0.6.6 attempts root is not private")
    final, inventory_sha = _inventory(candidate_root)
    old_budget = intent_budget(original_root)
    if old_budget["existing_intents"] != OLD_INTENTS:
        raise ValueError("Original 22 full-lease intents changed")
    ratification, rat_raw = _read_private(old_ratification)
    reservation, res_raw = _read_private(old_reservation)
    if (ratification.get("schema") !=
            "cua-six-cell-action-profile-v066-ratification-v1" or
            ratification.get("status") != "ratified_pre_result" or
            ratification.get("common_source_sha256s") !=
            common_source_hashes() or
            ratification.get("cell_profiles", {}).get(
                "desktop-native", {}).get("adapter_sha256") !=
            OLD_ADAPTER_SHA256 or
            reservation.get("schema") !=
            "cua-native-wdi-v066-final-control-lane-reservation-v1" or
            reservation.get("ratification_sha256") != digest(rat_raw) or
            reservation.get("source_bindings", {}).get(
                "candidate_inventory_sha256") != inventory_sha or
            reservation.get("lane_cap_usd") != str(LANE_CAP_USD)):
        raise ValueError("Original source or lane binding changed")
    statuses: Counter[str] = Counter()
    groups: dict[str, set[str]] = {}
    sandbox_ids: set[str] = set()
    failed_id: str | None = None
    old_leases_mature = True
    now = datetime.now(timezone.utc)
    for path in sorted(original_root.glob("*/*/receipt.json")):
        receipt, _ = _read_private(path)
        intent, _ = _read_private(path.with_name("intent.json"))
        try:
            created = datetime.fromisoformat(intent["created_utc"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("Original lease timestamp invalid") from None
        if created.tzinfo is None:
            raise ValueError("Original lease timestamp is timezone-naive")
        old_leases_mature &= (
            now >= created.astimezone(timezone.utc) + timedelta(
                seconds=LEASE_SECONDS + OLD_LEASE_CLEANUP_GRACE_SECONDS))
        task_id, attempt = path.parent.parent.name, path.parent.name
        if (task_id not in final or
                attempt not in {"positive", "near-miss", "cold-reset"} or
                intent.get("task_id") != task_id or
                intent.get("attempt") != attempt or
                intent.get("package_sha256") !=
                final[task_id]["package_sha256"] or
                intent.get("ratification_sha256") != digest(rat_raw) or
                intent.get("reservation_sha256") != digest(res_raw) or
                receipt.get("task_id") != task_id or
                receipt.get("attempt") != attempt or
                receipt.get("package_sha256") !=
                final[task_id]["package_sha256"] or
                receipt.get("runner_sha256") != OLD_RUNNER_SHA256 or
                receipt.get("native_adapter_sha256") !=
                OLD_ADAPTER_SHA256 or
                receipt.get("ratification_sha256") != digest(rat_raw) or
                receipt.get("lane_reservation_sha256") != digest(res_raw) or
                receipt.get("official_hidden_final_model_attempts") != 0 or
                receipt.get("kill_returned") is not True or
                receipt.get("is_running_after_kill") is not False):
            raise ValueError("Original attempt source or cleanup changed")
        sandbox_id = receipt.get("sandbox_id_sha256")
        if (type(sandbox_id) is not str or len(sandbox_id) != 64 or
                sandbox_id in sandbox_ids):
            raise ValueError("Original sandbox identity duplicated")
        sandbox_ids.add(sandbox_id)
        status = receipt.get("status")
        statuses[status] += 1
        groups.setdefault(task_id, set()).add(attempt)
        if status == "control_failed_or_infrastructure_invalid":
            if (failed_id is not None or attempt != "positive" or
                    receipt.get("error_type") != "PhysicalFrameDrift" or
                    receipt.get("contract_error_code") != "stale_frame" or
                    receipt.get("expected_actor_action_count") != 53 or
                    [row.get("step") for row in receipt.get("actor_steps", [])
                     if row.get("status") == "applied"] != list(range(33)) or
                    len([row for row in
                         receipt.get("physical_frame_resamples", [])
                         if row.get("step") == 33]) != 5):
                raise ValueError("Original physical-frame failure changed")
            failed_id = task_id
    if (statuses != Counter({"control_passed": 14,
                            "cold_reset_observed": 7,
                            "control_failed_or_infrastructure_invalid": 1}) or
            len(sandbox_ids) != OLD_INTENTS or
            len(groups) != OLD_COMPLETE_TRIOS + 1 or
            Counter(tuple(sorted(attempts)) for attempts in groups.values()) !=
            Counter({("cold-reset", "near-miss", "positive"): 7,
                     ("positive",): 1})):
        raise ValueError("Original 7 complete plus 1 partial trio changed")
    journal, journal_raw = _read_private(old_run_journal)
    outcomes = journal.get("task_outcomes", [])
    outcome_counts = Counter(row.get("status") for row in outcomes)
    if (journal.get("schema") !=
            "cua-native-wdi-v066-final-rerun-private-v1" or
            journal.get("status") != "stopped_for_reconciliation" or
            journal.get("plan", {}).get("candidate_inventory_sha256") !=
            inventory_sha or
            journal.get("ratification_sha256") != digest(rat_raw) or
            journal.get("reservation_sha256") != digest(res_raw) or
            journal.get("official_final_model_attempts") != 0 or
            journal.get("official_final_admissions") != 0 or
            outcome_counts != Counter({
                "provisional_trio_complete": 6,
                "stopped_after_invalid_or_uncertain_attempt": 1,
                "stopped_before_next_create": 92}) or
            [row.get("private_task_id") for row in outcomes if row.get(
                "status") == "stopped_after_invalid_or_uncertain_attempt"] !=
            [failed_id]):
        raise ValueError("Original terminal run journal changed")
    storage = _read_only_storage(original_root)
    tree_sha, tree_files = _tree_digest(original_root)
    return {"schema": "cua-native-wdi-v066-retained-old22-audit-v1",
            "candidate_inventory_sha256": inventory_sha,
            "original_intents": OLD_INTENTS,
            "original_complete_trios": OLD_COMPLETE_TRIOS,
            "original_failed_partial_tasks": 1,
            "original_adapter_sha256": OLD_ADAPTER_SHA256,
            "original_ratification_sha256": digest(rat_raw),
            "original_reservation_sha256": digest(res_raw),
            "original_run_journal_sha256": digest(journal_raw),
            "original_attempt_tree_sha256": tree_sha,
            "original_attempt_tree_files": tree_files,
            "original_storage": storage,
            "original_distinct_sandbox_count": len(sandbox_ids),
            "original_all_leases_plus_grace_mature": old_leases_mature,
            "original_evidence_retained": True,
            "official_model_results": 0}


def combined_budget(*, original_root: Path, fresh_root: Path,
                    proposed_new_intents: int) -> dict:
    """Charge both roots at 600 seconds and $1/hour; no provider invoice claim."""
    if (original_root.name != "v066-final-gui" or
            fresh_root.name != "v066-final-gui" or
            original_root.resolve() == fresh_root.resolve() or
            fresh_root.resolve().is_relative_to(original_root.resolve()) or
            original_root.resolve().is_relative_to(fresh_root.resolve()) or
            fresh_root.is_symlink() or
            (fresh_root.exists() and
             not _private(fresh_root, directory=True))):
        raise ValueError("Original and amended attempts roots are not isolated")
    old = intent_budget(original_root)["existing_intents"]
    fresh = intent_budget(fresh_root)["existing_intents"]
    if (old != OLD_INTENTS or fresh > NEW_INTENTS or
            type(proposed_new_intents) is not int or
            not 0 <= proposed_new_intents <= NEW_INTENTS - fresh):
        raise ValueError("Cross-root intent count changed")
    combined = old + fresh + proposed_new_intents
    reserved = Decimal(combined * LEASE_SECONDS) / Decimal(3600)
    if combined > MAX_SANDBOX_COUNT or reserved > LANE_CAP_USD:
        raise ValueError("Existing $60 cross-root full-lease cap exceeded")
    return {"original_intents": old,
            "fresh_intents_existing": fresh,
            "fresh_intents_proposed": proposed_new_intents,
            "combined_full_lease_intents": combined,
            "combined_conservative_reserved_usd": str(reserved),
            "lane_cap_usd": str(LANE_CAP_USD),
            "actual_provider_billed_usd": None}


def expected_bridge(*, retained: dict, new_ratification: Path,
                    new_reservation: Path) -> dict:
    return {"schema": BRIDGE_SCHEMA,
            "status": "reserved_before_amended_final_create",
            "candidate_inventory_sha256":
                retained["candidate_inventory_sha256"],
            "original_attempt_tree_sha256":
                retained["original_attempt_tree_sha256"],
            "original_ratification_sha256":
                retained["original_ratification_sha256"],
            "original_reservation_sha256":
                retained["original_reservation_sha256"],
            "original_adapter_sha256": OLD_ADAPTER_SHA256,
            "new_ratification_sha256":
                digest(new_ratification.read_bytes()),
            "new_reservation_sha256":
                digest(new_reservation.read_bytes()),
            "new_adapter_sha256":
                digest(Path(qwen_v066_adapter.__file__).read_bytes()),
            "old_intents": OLD_INTENTS,
            "new_full100_intents_planned": NEW_INTENTS,
            "combined_full_lease_intents_planned": OLD_INTENTS + NEW_INTENTS,
            "combined_conservative_reserved_usd":
                str(Decimal((OLD_INTENTS + NEW_INTENTS) * LEASE_SECONDS) /
                    Decimal(3600)),
            "lane_cap_usd": str(LANE_CAP_USD),
            "prior_attempts_retained_immutable": True,
            "official_model_results": 0}


def preflight_fresh_full100(*, candidate_root: Path,
                            original_root: Path, fresh_root: Path,
                            old_run_journal: Path,
                            old_ratification: Path,
                            old_reservation: Path,
                            new_ratification: Path,
                            new_reservation: Path,
                            bridge_path: Path,
                            profile_private: Path,
                            guest_public: Path,
                            fair_public: Path) -> dict:
    """Require two source freezes and one cross-root bridge before new spend."""
    retained = audit_retained_original(
        candidate_root=candidate_root, original_root=original_root,
        old_run_journal=old_run_journal,
        old_ratification=old_ratification,
        old_reservation=old_reservation)
    if not retained["original_all_leases_plus_grace_mature"]:
        raise ValueError("Old leases plus cleanup grace are not mature")
    validate_lane(ratification=new_ratification,
                  reservation=new_reservation,
                  candidate_root=candidate_root,
                  guest_public=guest_public,
                  profile_private=profile_private,
                  fair_public=fair_public)
    if digest(Path(qwen_v066_adapter.__file__).read_bytes()) == OLD_ADAPTER_SHA256:
        raise ValueError("Desktop caret amendment adapter was not source changed")
    bridge, _ = _read_private(bridge_path)
    recorded = bridge.get("recorded_utc")
    try:
        recorded_at = datetime.fromisoformat(recorded)
    except (TypeError, ValueError):
        raise ValueError("Cross-root bridge timestamp invalid") from None
    if (recorded_at.tzinfo is None or
            recorded_at.astimezone(timezone.utc) > datetime.now(timezone.utc)):
        raise ValueError("Cross-root bridge date invalid")
    try:
        new_ratified_at = datetime.fromisoformat(
            json.loads(new_ratification.read_bytes())["ratified_utc"])
        new_reserved_at = datetime.fromisoformat(
            json.loads(new_reservation.read_bytes())["recorded_utc"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("New ratification or lane timestamp invalid") from None
    if (new_ratified_at.tzinfo is None or
            new_reserved_at.tzinfo is None or
            recorded_at < max(new_ratified_at, new_reserved_at)):
        raise ValueError("Cross-root bridge must follow new source and lane")
    expected = expected_bridge(
        retained=retained, new_ratification=new_ratification,
        new_reservation=new_reservation)
    if (set(bridge) != set(expected) | {"recorded_utc"} or
            any(bridge.get(key) != value for key, value in expected.items())):
        raise ValueError("Cross-root same-$60 reservation bridge invalid")
    existing = intent_budget(fresh_root)["existing_intents"]
    if existing:
        raise ValueError("Initial full100 preflight requires an unused fresh root")
    budget = combined_budget(
        original_root=original_root, fresh_root=fresh_root,
        proposed_new_intents=NEW_INTENTS)
    if (budget["combined_full_lease_intents"] != OLD_INTENTS + NEW_INTENTS or
            budget["combined_conservative_reserved_usd"] !=
            expected["combined_conservative_reserved_usd"]):
        raise ValueError("Full100 cross-root lease total changed")
    return {"schema": "cua-native-wdi-v066-caret-full100-preflight-private-v1",
            "status": "source_and_budget_ready_no_provider_probe",
            "retained_original": retained,
            "fresh_attempts_root": str(fresh_root.resolve()),
            "new_adapter_sha256": expected["new_adapter_sha256"],
            "new_ratification_sha256": expected["new_ratification_sha256"],
            "new_reservation_sha256": expected["new_reservation_sha256"],
            "bridge_sha256": _sha_file(bridge_path),
            "combined_budget": budget,
            "provider_active_zero_verified": False,
            "official_model_results": 0,
            "official_final_admissions": 0}
