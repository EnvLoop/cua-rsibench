"""No-model 20-ID native selection profile plan and guarded future sweeper.

This module does not run during the live final-control sweep. Plan/audit paths
are offline. Future dispatch requires a terminal final-control journal, zero
active provider sandboxes, a separate private $4 full-lease reservation, the
pinned Desktop extra, and no prior failed/uncertain profile receipt. Each
create is intent-journaled before E2B; no automatic retry is permitted.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import importlib.metadata
import io
import json
import os
from pathlib import Path
import shutil
import time

from PIL import Image, UnidentifiedImageError

from .reconcile_interrupted_sweep import active_hashes

from . import profile_canonical, runtime_fingerprint_probe
from .selection_worker_v066 import (
    MAX_TASKS, SelectionPackage, _load_selection_packages,
    RealDesktopSelectionBackend,
)
from .teacher_episode_worker_v066 import _semantic_input
from .v066_final_freeze import digest


RECEIPT_SCHEMA = "cua-native-wdi-v066-selection-profile-baseline-v1"
MANIFEST_SCHEMA = "cua-native-wdi-v066-selection-profile-baselines-private-v1"
LANE_SCHEMA = "cua-native-wdi-v066-selection-profile-lane-v1"
LEASE_SECONDS = 600
LEASE_RESERVE_USD = Decimal("0.166666667")
LANE_CAP_USD = Decimal("4.000000000")
# Decimal nine-place rounding makes 24 * $0.166666667 exceed $4 by $0.000000008.
MAX_CREATE_INTENTS = 23
MIN_HOST_FREE_BYTES = 8 * 1024 ** 3


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def _private(path: Path, *, directory: bool) -> bool:
    return (not path.is_symlink() and
            (path.is_dir() if directory else path.is_file()) and
            path.stat().st_mode & 0o077 == 0)


def _write_new(path: Path, raw: bytes) -> str:
    if (path.exists() or path.is_symlink() or not raw or
            not _private(path.parent, directory=True) or
            shutil.disk_usage(path.parent).free - len(raw) <
            MIN_HOST_FREE_BYTES):
        raise ValueError("selection_profile_private_output_or_space_unsafe")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return sha256(raw).hexdigest()


def _packages(candidate_root: Path, private_map: Path,
              expected_inventory_sha256: str) -> list[SelectionPackage]:
    inventory = json.loads((candidate_root / "candidate-inventory.json").read_bytes())
    identities = [{key: row[key] for key in
                   ("task_id", "package_sha256")}
                  for row in inventory["tasks"] if row["split"] == "selection"]
    return _load_selection_packages(
        candidate_root, private_map, identities,
        expected_inventory_sha256)


def plan(*, candidate_root: Path, private_map: Path,
         expected_inventory_sha256: str,
         receipts_root: Path) -> tuple[list[SelectionPackage], dict]:
    packages = _packages(candidate_root, private_map,
                         expected_inventory_sha256)
    passed = 0
    fresh = []
    for package in packages:
        directory = receipts_root / package.identity["task_id"]
        if not directory.exists():
            fresh.append(package)
            continue
        receipt_path = directory / "receipt.json"
        if not receipt_path.is_file():
            raise ValueError("selection_profile_existing_intent_or_receipt_uncertain")
        receipt = json.loads(receipt_path.read_bytes())
        if (receipt.get("schema") != RECEIPT_SCHEMA or
                receipt.get("task_id") != package.identity["task_id"] or
                receipt.get("package_sha256") !=
                package.identity["package_sha256"] or
                receipt.get("status") != "profile_baseline_passed" or
                receipt.get("is_running_after_kill") is not False):
            raise ValueError("selection_profile_existing_failure_requires_reconciliation")
        passed += 1
    return fresh, {
        "schema": "cua-native-wdi-v066-selection-profile-offline-plan-v1",
        "candidate_inventory_sha256": expected_inventory_sha256,
        "selection_candidate_count": len(packages),
        "existing_verified_profile_count": passed,
        "fresh_selection_profiles_needed": len(fresh),
        "new_e2b_leases_planned": len(fresh),
        "new_full_lease_reserve_usd": str(
            LEASE_RESERVE_USD * Decimal(len(fresh))),
        "provider_invoice_usd": None,
        "model_calls": 0,
        "selection_scores": 0,
    }


def _terminal_final_sweep(path: Path) -> str:
    if not _private(path, directory=False):
        raise ValueError("final_control_sweep_terminal_receipt_missing")
    raw = path.read_bytes()
    value = json.loads(raw)
    if (value.get("schema") != "cua-native-wdi-v066-final-rerun-private-v1" or
            value.get("status") != "all_selected_trios_provisional" or
            not value.get("completed_utc")):
        raise ValueError("final_control_sweep_still_live_or_unreconciled")
    return digest(raw)


def prepare_lane(*, path: Path, final_sweep_terminal: Path,
                 expected_inventory_sha256: str,
                 guest_reference_sha256: str) -> dict:
    if path.exists() or path.is_symlink():
        raise ValueError("selection_profile_lane_already_exists")
    final_sha = _terminal_final_sweep(final_sweep_terminal)
    value = {
        "schema": LANE_SCHEMA,
        "status": "reserved_before_selection_profile_create",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_inventory_sha256": expected_inventory_sha256,
        "guest_identity_public_sha256": guest_reference_sha256,
        "terminal_final_sweep_sha256": final_sha,
        "initial_task_count": MAX_TASKS,
        "initial_full_lease_reserve_usd": str(
            LEASE_RESERVE_USD * Decimal(MAX_TASKS)),
        "maximum_create_intents_including_manual_recovery":
            MAX_CREATE_INTENTS,
        "lane_cap_usd": str(LANE_CAP_USD),
        "provider_invoice_usd": None,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    _write_new(path, _canonical(value))
    return value


def _validate_lane(path: Path, *, final_sweep_terminal: Path,
                   expected_inventory_sha256: str,
                   guest_reference_sha256: str) -> dict:
    if not _private(path, directory=False):
        raise ValueError("selection_profile_lane_not_reserved")
    value = json.loads(path.read_bytes())
    if (value.get("schema") != LANE_SCHEMA or
            value.get("status") !=
            "reserved_before_selection_profile_create" or
            value.get("candidate_inventory_sha256") !=
            expected_inventory_sha256 or
            value.get("guest_identity_public_sha256") !=
            guest_reference_sha256 or
            value.get("terminal_final_sweep_sha256") !=
            _terminal_final_sweep(final_sweep_terminal) or
            value.get("initial_task_count") != MAX_TASKS or
            value.get("initial_full_lease_reserve_usd") != str(
                LEASE_RESERVE_USD * Decimal(MAX_TASKS)) or
            value.get("maximum_create_intents_including_manual_recovery") !=
            MAX_CREATE_INTENTS or
            value.get("lane_cap_usd") != str(LANE_CAP_USD) or
            value.get("provider_invoice_usd") is not None):
        raise ValueError("selection_profile_lane_binding_changed")
    return value


def _pinned_e2b_extra() -> None:
    try:
        versions = {name: importlib.metadata.version(name) for name in
                    ("e2b-desktop", "e2b", "Pillow")}
    except Exception:
        raise ValueError("selection_profile_pinned_e2b_extra_missing") from None
    if versions != {"e2b-desktop": "2.2.0",
                    "e2b": "2.51.0", "Pillow": "11.3.0"}:
        raise ValueError("selection_profile_pinned_e2b_extra_missing")


def _canonical_profile(sandbox) -> str:
    run = sandbox.commands.run(
        "python3 /tmp/native-profile-file-probe-teacher.py")
    if run.exit_code != 0:
        raise ValueError("selection_profile_probe_failed")
    rows = json.loads(run.stdout)
    registry = bytes(sandbox.files.read(
        "/home/user/.config/libreoffice/4/user/registrymodifications.xcu",
        format="bytes"))
    return profile_canonical.canonical_profile_tree(rows, registry)


def _native_frame(raw: bytes) -> bool:
    if not raw or len(raw) > 4_000_000:
        return False
    try:
        with Image.open(io.BytesIO(raw)) as opened:
            if opened.format != "PNG" or opened.size != (1280, 800):
                return False
            opened.load()
            return True
    except (UnidentifiedImageError, OSError, ValueError):
        return False


def run_one(*, package: SelectionPackage, out_dir: Path,
            guest_reference: dict,
            backend: object) -> dict:
    """One future no-model neutral open; fake backend tests call this only."""
    if out_dir.exists() or out_dir.is_symlink():
        raise ValueError("selection_profile_attempt_must_be_new")
    out_dir.mkdir(parents=True, mode=0o700)
    out_dir.chmod(0o700)
    intent = {
        "schema": "cua-native-wdi-v066-selection-profile-intent-v1",
        "task_id": package.identity["task_id"],
        "package_sha256": package.identity["package_sha256"],
        "input_sha256": digest(package.source),
        "lease_seconds": LEASE_SECONDS,
        "full_lease_reserved_usd": str(LEASE_RESERVE_USD),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "automatic_replay_authorized": False,
    }
    _write_new(out_dir / "intent.json", _canonical(intent))
    receipt = {"schema": RECEIPT_SCHEMA,
               "status": "started", "split": "selection",
               "task_id": package.identity["task_id"],
               "package_sha256": package.identity["package_sha256"],
               "input_sha256": digest(package.source),
               "lease_seconds": LEASE_SECONDS,
               "full_lease_reserved_usd": str(LEASE_RESERVE_USD),
               "provider_invoice_usd": None,
               "model_calls": 0}
    guest = None
    try:
        guest = backend.create("selection-profile", LEASE_SECONDS,
                               package)
        receipt["sandbox_id_sha256"] = digest(
            guest.sandbox_id.encode())
        guest.prepare(source=package.source,
                      filename=package.filename,
                      oracle=package.oracle,
                      guest_identity=guest_reference)
        if (guest.guest_content_sha256 !=
                guest_reference["static_content_sha256"] or
                guest.provider_shape_attested is not True or
                guest.fresh_profile_absent is not True or
                guest.raw_input_sha256 != digest(package.source) or
                type(guest.neutral_input) is not bytes or
                type(guest.profile_sha256) is not str or
                len(guest.profile_sha256) != 64 or
                _semantic_input(guest.neutral_input,
                                Path(package.filename).suffix) !=
                _semantic_input(package.source,
                                Path(package.filename).suffix)):
            raise ValueError("selection_profile_guest_attestation_invalid")
        first = _canonical_profile(guest.sandbox)
        time.sleep(1)
        second = _canonical_profile(guest.sandbox)
        if first != second or first != guest.profile_sha256:
            raise ValueError("selection_profile_neutral_snapshot_unstable")
        raw = guest._screenshot()
        if not _native_frame(raw):
            raise ValueError("selection_profile_neutral_frame_invalid")
        receipt["neutral_open_screenshot_sha256"] = _write_new(
            out_dir / "neutral-open.png", raw)
        receipt["neutral_input_sha256"] = _write_new(
            out_dir / ("neutral-baseline" +
                       Path(package.filename).suffix),
            guest.neutral_input)
        receipt["guest_content_sha256"] = guest.guest_content_sha256
        receipt["provider_shape_attested"] = True
        receipt["fresh_profile_absent"] = True
        receipt["source_semantics_equal_after_neutral_save"] = True
        receipt["profile_snapshot_sha256s"] = [first, second]
        receipt["canonical_profile_sha256"] = first
        receipt["provider_kind"] = (
            "fake_offline" if getattr(backend, "is_fake", False)
            else "e2b_desktop")
        receipt["sdk_version"] = (
            "fake_offline" if getattr(backend, "is_fake", False)
            else importlib.metadata.version("e2b-desktop"))
        receipt["status"] = "observed_before_teardown"
    except Exception as exc:
        receipt["status"] = "failed_or_uncertain"
        receipt["error_type"] = type(exc).__name__
    finally:
        if guest is not None:
            try:
                receipt["kill_returned"] = bool(guest.close())
                receipt["is_running_after_kill"] = not guest.killed
            except Exception as exc:
                receipt["kill_error_type"] = type(exc).__name__
                receipt["is_running_after_kill"] = None
        if (receipt.get("status") == "observed_before_teardown" and
                receipt.get("kill_returned") is True and
                receipt.get("is_running_after_kill") is False):
            receipt["status"] = "profile_baseline_passed"
        elif receipt.get("is_running_after_kill") is not False:
            receipt["status"] = "cleanup_unverified"
        _write_new(out_dir / "receipt.json", _canonical(receipt))
    return receipt


def audit_manifest(*, candidate_root: Path, private_map: Path,
                   expected_inventory_sha256: str,
                   receipts_root: Path,
                   guest_reference_public: Path,
                   manifest_out: Path) -> dict:
    if manifest_out.exists() or manifest_out.is_symlink():
        raise ValueError("selection_profile_manifest_refuses_overwrite")
    if not receipts_root.resolve().is_relative_to(
            manifest_out.parent.resolve()):
        raise ValueError("selection_profile_receipts_outside_private_manifest_root")
    packages = _packages(candidate_root, private_map,
                         expected_inventory_sha256)
    guest_raw = guest_reference_public.read_bytes()
    guest = json.loads(guest_raw)
    accepted = []
    sandboxes = set()
    for package in packages:
        path = receipts_root / package.identity["task_id"] / "receipt.json"
        if not _private(path, directory=False):
            raise ValueError("selection_profile_receipt_missing")
        raw = path.read_bytes()
        receipt = json.loads(raw)
        frame_path = path.with_name("neutral-open.png")
        neutral_path = path.with_name(
            "neutral-baseline" + Path(package.filename).suffix)
        if (receipt.get("schema") != RECEIPT_SCHEMA or
                receipt.get("status") != "profile_baseline_passed" or
                receipt.get("split") != "selection" or
                receipt.get("task_id") != package.identity["task_id"] or
                receipt.get("package_sha256") !=
                package.identity["package_sha256"] or
                receipt.get("input_sha256") != digest(package.source) or
                receipt.get("guest_content_sha256") !=
                guest["static_content_sha256"] or
                receipt.get("provider_shape_attested") is not True or
                receipt.get("fresh_profile_absent") is not True or
                receipt.get("source_semantics_equal_after_neutral_save")
                is not True or
                receipt.get("kill_returned") is not True or
                receipt.get("is_running_after_kill") is not False or
                receipt.get("model_calls") != 0 or
                receipt.get("provider_invoice_usd") is not None or
                receipt.get("provider_kind") != "e2b_desktop" or
                receipt.get("sdk_version") != "2.2.0" or
                receipt.get("lease_seconds") != LEASE_SECONDS or
                receipt.get("full_lease_reserved_usd") !=
                str(LEASE_RESERVE_USD) or
                receipt.get("profile_snapshot_sha256s") !=
                [receipt.get("canonical_profile_sha256")] * 2 or
                not _private(frame_path, directory=False) or
                digest(frame_path.read_bytes()) !=
                receipt.get("neutral_open_screenshot_sha256") or
                not _native_frame(frame_path.read_bytes()) or
                not _private(neutral_path, directory=False) or
                digest(neutral_path.read_bytes()) !=
                receipt.get("neutral_input_sha256") or
                _semantic_input(neutral_path.read_bytes(),
                                neutral_path.suffix) !=
                _semantic_input(package.source,
                                neutral_path.suffix) or
                receipt.get("sandbox_id_sha256") in sandboxes):
            raise ValueError("selection_profile_receipt_not_independently_accepted")
        sandboxes.add(receipt["sandbox_id_sha256"])
        accepted.append({
            "task_id": package.identity["task_id"],
            "package_sha256": package.identity["package_sha256"],
            "canonical_profile_sha256":
                receipt["canonical_profile_sha256"],
            "receipt_path": str(path.relative_to(manifest_out.parent)),
            "receipt_sha256": digest(raw),
        })
    manifest = {"schema": MANIFEST_SCHEMA,
                "candidate_inventory_sha256":
                expected_inventory_sha256,
                "guest_identity_public_sha256": digest(guest_raw),
                "accepted": accepted,
                "distinct_sandbox_count": len(sandboxes),
                "model_calls": 0,
                "provider_invoice_usd": None}
    manifest_out.parent.mkdir(parents=True, exist_ok=True)
    manifest_out.parent.chmod(0o700)
    _write_new(manifest_out, _canonical(manifest))
    return manifest


def execute(*, candidate_root: Path, private_map: Path,
            expected_inventory_sha256: str,
            guest_reference_public: Path,
            receipts_root: Path, manifest_out: Path,
            run_dir: Path, lane_reservation: Path,
            final_sweep_terminal: Path,
            enable_live: bool = False,
            backend: object | None = None) -> dict:
    """Serial future dispatch; every paid create is counted at full lease."""
    if enable_live is not True or backend is not None:
        raise ValueError("selection_profile_live_dispatch_not_authorized")
    if run_dir.exists() or manifest_out.exists():
        raise ValueError("selection_profile_run_or_manifest_already_exists")
    guest_raw = guest_reference_public.read_bytes()
    guest = json.loads(guest_raw)
    if (guest.get("schema") !=
            "cua-native-wdi-guest-content-identity-public-v1" or
            guest.get("scoped_guest_content_identity_passed") is not True):
        raise ValueError("selection_profile_guest_identity_reference_invalid")
    lane = _validate_lane(
        lane_reservation, final_sweep_terminal=final_sweep_terminal,
        expected_inventory_sha256=expected_inventory_sha256,
        guest_reference_sha256=digest(guest_raw))
    _pinned_e2b_extra()
    if not os.environ.get("E2B_API_KEY"):
        raise ValueError("selection_profile_e2b_key_missing")
    active, count = active_hashes()
    if count or active:
        raise ValueError("selection_profile_provider_has_active_sandboxes")
    fresh, summary = plan(
        candidate_root=candidate_root, private_map=private_map,
        expected_inventory_sha256=expected_inventory_sha256,
        receipts_root=receipts_root)
    if (summary["existing_verified_profile_count"] != 0 or
            len(fresh) != MAX_TASKS):
        raise ValueError("selection_profile_initial_run_requires_all_twenty_fresh")
    if (Decimal(len(fresh)) * LEASE_RESERVE_USD >
            Decimal(lane["lane_cap_usd"]) or
            len(fresh) > lane[
                "maximum_create_intents_including_manual_recovery"]):
        raise ValueError("selection_profile_full_lease_lane_exhausted")
    receipts_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    receipts_root.chmod(0o700)
    run_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    run_dir.chmod(0o700)
    journal = {
        "schema": "cua-native-wdi-v066-selection-profile-run-private-v1",
        "status": "started",
        "candidate_inventory_sha256": expected_inventory_sha256,
        "guest_identity_public_sha256": digest(guest_raw),
        "lane_reservation_sha256": digest(lane_reservation.read_bytes()),
        "terminal_final_sweep_sha256": digest(final_sweep_terminal.read_bytes()),
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "planned_task_count": MAX_TASKS,
        "planned_full_lease_reserve_usd": str(
            Decimal(MAX_TASKS) * LEASE_RESERVE_USD),
        "attempts": [], "provider_invoice_usd": None,
        "model_calls": 0,
    }

    def persist() -> None:
        path = run_dir / "run-receipt.json"
        raw = _canonical(journal)
        if path.exists():
            path.write_bytes(raw)
            path.chmod(0o600)
        else:
            _write_new(path, raw)

    persist()
    real_backend = RealDesktopSelectionBackend()
    for package in fresh:
        if shutil.disk_usage(receipts_root).free < MIN_HOST_FREE_BYTES:
            journal["status"] = "stopped_for_storage_floor"
            break
        if len(journal["attempts"]) >= MAX_CREATE_INTENTS:
            journal["status"] = "stopped_for_lease_cap"
            break
        if ((Decimal(len(journal["attempts"]) + 1) *
                LEASE_RESERVE_USD) > LANE_CAP_USD):
            journal["status"] = "stopped_for_dollar_cap"
            break
        attempt_dir = receipts_root / package.identity["task_id"]
        receipt = run_one(package=package, out_dir=attempt_dir,
                          guest_reference=guest, backend=real_backend)
        journal["attempts"].append({
            "task_id": package.identity["task_id"],
            "package_sha256": package.identity["package_sha256"],
            "receipt_sha256": digest((attempt_dir / "receipt.json").read_bytes()),
            "status": receipt["status"],
            "sandbox_acknowledged": bool(receipt.get("sandbox_id_sha256")),
            "cleanup_verified": receipt.get("is_running_after_kill") is False,
        })
        persist()
        if receipt["status"] != "profile_baseline_passed":
            journal["status"] = "stopped_for_manual_reconciliation"
            break
    else:
        journal["status"] = "twenty_neutral_profiles_observed"
    if journal["status"] == "twenty_neutral_profiles_observed":
        audit_manifest(
            candidate_root=candidate_root,
            private_map=private_map,
            expected_inventory_sha256=expected_inventory_sha256,
            receipts_root=receipts_root,
            guest_reference_public=guest_reference_public,
            manifest_out=manifest_out)
        journal["manifest_sha256"] = digest(manifest_out.read_bytes())
        journal["status"] = "complete_and_independently_audited"
    journal["completed_utc"] = datetime.now(timezone.utc).isoformat()
    persist()
    return journal


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("plan", "prepare-lane", "execute"),
                        required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--private-map", type=Path, required=True)
    parser.add_argument("--expected-inventory-sha256", required=True)
    parser.add_argument("--receipts-root", type=Path, required=True)
    parser.add_argument("--guest-reference-public", type=Path)
    parser.add_argument("--final-sweep-terminal", type=Path)
    parser.add_argument("--lane-reservation", type=Path)
    parser.add_argument("--manifest-out", type=Path)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--enable-live", action="store_true")
    args = parser.parse_args()
    if args.mode == "plan":
        _fresh, result = plan(
            candidate_root=args.candidate_root,
            private_map=args.private_map,
            expected_inventory_sha256=args.expected_inventory_sha256,
            receipts_root=args.receipts_root)
        safe = {key: result[key] for key in (
            "selection_candidate_count", "existing_verified_profile_count",
            "fresh_selection_profiles_needed", "new_e2b_leases_planned",
            "new_full_lease_reserve_usd")}
    elif args.mode == "prepare-lane":
        if not all((args.guest_reference_public, args.final_sweep_terminal,
                    args.lane_reservation)):
            raise ValueError("selection_profile_prepare_lane_paths_required")
        lane = prepare_lane(
            path=args.lane_reservation,
            final_sweep_terminal=args.final_sweep_terminal,
            expected_inventory_sha256=args.expected_inventory_sha256,
            guest_reference_sha256=digest(
                args.guest_reference_public.read_bytes()))
        safe = {key: lane[key] for key in (
            "status", "initial_task_count",
            "initial_full_lease_reserve_usd", "lane_cap_usd")}
    else:
        if not all((args.guest_reference_public, args.final_sweep_terminal,
                    args.lane_reservation, args.manifest_out, args.run_dir)):
            raise ValueError("selection_profile_execute_paths_required")
        journal = execute(
            candidate_root=args.candidate_root,
            private_map=args.private_map,
            expected_inventory_sha256=args.expected_inventory_sha256,
            guest_reference_public=args.guest_reference_public,
            receipts_root=args.receipts_root,
            manifest_out=args.manifest_out,
            run_dir=args.run_dir,
            lane_reservation=args.lane_reservation,
            final_sweep_terminal=args.final_sweep_terminal,
            enable_live=args.enable_live)
        safe = {"status": journal["status"],
                "attempted": len(journal["attempts"]),
                "provider_invoice_usd": None}
        if journal["status"] != "complete_and_independently_audited":
            raise SystemExit(2)
    print(json.dumps(safe, sort_keys=True))


if __name__ == "__main__":
    main()
