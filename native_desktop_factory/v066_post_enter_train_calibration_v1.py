"""Source-frozen, reviewed, three-guest public-train GUI calibration.

This module has no final-task path. Its paid execution is disabled without a
separate exact permit. The first two guests run the unchanged public-train
Calc/Writer positive demonstrations through a no-action post-Enter proxy;
the third guest checks a fresh Calc baseline/profile cold reset. No model is
called and no result contributes to official final admissions.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import time
from unittest.mock import patch

from . import runtime_fingerprint_probe
from . import v066_scoped_calc_writer_train_demo as demo
from . import v066_scoped_calc_writer_train_demo_audit_v2 as demo_audit
from . import v066_scoped_profile_guard as profile_guard
from .budget_ledger import audit as budget_audit
from .gui_control_shell import wait_for_document_ready
from .post_enter_train_probe_v1 import PostEnterProbeProxy
from .reconcile_interrupted_sweep import active_hashes
from .v066_scoped_profile_reference import validate_reference
from .v066_storage_budget import audit as storage_audit, reserve_and_write


SCHEMA = "cua-native-wdi-v066-post-enter-train-calibration-freeze-private-v1"
PUBLIC_SCHEMA = "cua-native-wdi-v066-post-enter-train-calibration-freeze-public-v1"
PERMIT_SCHEMA = "cua-native-wdi-v066-post-enter-train-calibration-permit-private-v1"
LEASE_SECONDS = 600
LANE_CAP_USD = Decimal("43")
SDK_VERSIONS = {"e2b-desktop": "2.2.0", "e2b": "2.51.0", "Pillow": "11.3.0"}
SOURCE_NAMES = (
    "native_desktop_factory/v066_post_enter_train_calibration_v1.py",
    "native_desktop_factory/v066_post_enter_train_calibration_audit_v1.py",
    "native_desktop_factory/post_enter_train_probe_v1.py",
    "native_desktop_factory/post_enter_settle_candidate_v1.py",
    "native_desktop_factory/v066_scoped_calc_writer_train_demo.py",
    "native_desktop_factory/v066_scoped_calc_writer_train_demo_audit.py",
    "native_desktop_factory/v066_scoped_calc_writer_train_demo_audit_v2.py",
    "native_desktop_factory/v066_train_profile_cross_guest.py",
    "native_desktop_factory/v066_scoped_profile_guard.py",
    "native_desktop_factory/v066_scoped_profile_reference.py",
    "native_desktop_factory/v066_profile_scope_analysis.py",
    "native_desktop_factory/qwen_v066_adapter.py",
    "native_desktop_factory/qwen_v064_adapter.py",
    "native_desktop_factory/v066_final_control_audit.py",
    "native_desktop_factory/gui_control_shell.py",
    "native_desktop_factory/reconcile_interrupted_sweep.py",
    "native_desktop_factory/v066_final_freeze.py",
    "native_desktop_factory/admit.py",
    "native_desktop_factory/source.py",
    "native_desktop_factory/factory.py",
    "native_desktop_factory/verify.py",
    "native_desktop_factory/runtime_fingerprint_probe.py",
    "native_desktop_factory/v066_storage_budget.py",
    "native_desktop_factory/budget_ledger.py",
    "src/cursibench/scale_action_contract.py",
    "src/cursibench/scale_action_contract_v066.py",
    "src/cursibench/scale_action_output_v064.py",
    "src/cursibench/scale_action_output_v066.py",
)


def digest(raw: bytes) -> str:
    from hashlib import sha256
    return sha256(raw).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _private(path: Path) -> bytes:
    if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o077:
        raise ValueError("Private train calibration evidence absent or unsafe")
    return path.read_bytes()


def _write_new(path: Path, value: dict, *, public: bool = False) -> str:
    raw = (json.dumps(value, sort_keys=True,
                      indent=2 if public else None,
                      separators=None if public else (",", ":")) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not public:
        path.parent.chmod(0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                         0o644 if public else 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return digest(raw)


def _persist(path: Path, value: dict) -> None:
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    temp = path.with_name(path.name + ".next")
    with temp.open("wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    temp.chmod(0o600)
    os.replace(temp, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _sources(repo: Path) -> dict[str, str]:
    return {name: digest((repo / name).read_bytes()) for name in SOURCE_NAMES}


def prepare(*, work_root: Path, output_root: Path,
            guest_public: Path, scoped_reference: Path,
            reservation_path: Path, freeze_path: Path,
            public_path: Path) -> dict:
    repo = Path(__file__).resolve().parents[1]
    expected_root = work_root / "gui-diagnostics"
    if (any(path.exists() or path.is_symlink() for path in
            (output_root, reservation_path, freeze_path, public_path)) or
            not all(path.is_absolute() for path in
                    (work_root, output_root, guest_public, scoped_reference,
                     reservation_path, freeze_path, public_path)) or
            output_root.parent.resolve() != expected_root.resolve()):
        raise ValueError("Exclusive absolute train-only calibration paths required")
    calc, _oracle, baseline, _instruction, _filename = demo._source("calc")
    writer = demo._source("writer")[0]
    if (calc.get("split") != "train" or writer.get("split") != "train" or
            calc["package_sha256"] == writer["package_sha256"]):
        raise ValueError("Only two distinct public-train source packages allowed")
    budget = budget_audit(
        work_root, proposed_new_sandboxes=3,
        proposed_lease_seconds=LEASE_SECONDS,
        max_lane_reserved_usd=LANE_CAP_USD)
    if budget["within_cap"] is not True:
        raise ValueError("Three separate train calibration leases exceed cap")
    demo.prepare_reservation(
        path=reservation_path, work_root=work_root,
        guest_public=guest_public, scoped_reference=scoped_reference)
    value = {
        "schema": SCHEMA, "status": "source_frozen_no_dispatch",
        "recorded_utc": _now(), "public_path": str(public_path),
        "work_root": str(work_root), "output_root": str(output_root),
        "guest_public": str(guest_public),
        "scoped_reference": str(scoped_reference),
        "reservation_path": str(reservation_path),
        "reservation_sha256": digest(_private(reservation_path)),
        "guest_public_sha256": digest(guest_public.read_bytes()),
        "scoped_reference_sha256": digest(scoped_reference.read_bytes()),
        "calc_package_sha256": calc["package_sha256"],
        "calc_input_sha256": digest(baseline),
        "writer_package_sha256": writer["package_sha256"],
        "source_sha256s": _sources(repo),
        "three_full_lease_intents": 3,
        "three_lease_reserved_usd_upper": str(Decimal(3 * LEASE_SECONDS) / 3600),
        "combined_diagnostic_reserved_usd_upper": budget["combined_reserved_usd"],
        "sample_delays_ms": [0, 250, 250, 250, 250],
        "same_intent_replay_authorized": False,
        "dispatch_authorized": False,
        "official_final_admissions": 0,
    }
    private_sha = _write_new(freeze_path, value)
    public = {
        "schema": PUBLIC_SCHEMA,
        "status": "train_only_source_frozen_pending_independent_review",
        "private_freeze_sha256": private_sha,
        "source_sha256s": value["source_sha256s"],
        "source_scope": "pinned_public_train_calc_writer_only",
        "guest_count": 3,
        "full_lease_reservation_usd_upper": value["three_lease_reserved_usd_upper"],
        "sample_delays_ms": value["sample_delays_ms"],
        "saved_state_scoring_required": True,
        "fresh_calc_reset_required": True,
        "modal_and_oscillation_stop_required": True,
        "same_intent_replay_authorized": False,
        "dispatch_authorized": False,
        "official_final_admissions": 0,
    }
    _write_new(public_path, public, public=True)
    return public


def validate_source(freeze_path: Path) -> dict:
    raw = _private(freeze_path)
    value = json.loads(raw)
    repo = Path(__file__).resolve().parents[1]
    if (value.get("schema") != SCHEMA or
            value.get("status") != "source_frozen_no_dispatch" or
            value.get("dispatch_authorized") is not False or
            value.get("same_intent_replay_authorized") is not False or
            value.get("official_final_admissions") != 0 or
            value.get("three_full_lease_intents") != 3 or
            value.get("sample_delays_ms") != [0, 250, 250, 250, 250] or
            value.get("source_sha256s") != _sources(repo) or
            value.get("reservation_sha256") != digest(_private(
                Path(value["reservation_path"]))) or
            value.get("guest_public_sha256") != digest(
                Path(value["guest_public"]).read_bytes()) or
            value.get("scoped_reference_sha256") != digest(
                Path(value["scoped_reference"]).read_bytes())):
        raise ValueError("Train calibration source or private binding changed")
    public = json.loads(Path(value["public_path"]).read_bytes())
    if (public.get("schema") != PUBLIC_SCHEMA or
            public.get("status") !=
                "train_only_source_frozen_pending_independent_review" or
            public.get("private_freeze_sha256") != digest(raw) or
            public.get("source_sha256s") != value["source_sha256s"] or
            public.get("dispatch_authorized") is not False):
        raise ValueError("Train calibration public source freeze changed")
    calc, _oracle, baseline, _instruction, _filename = demo._source("calc")
    if (calc["package_sha256"] != value["calc_package_sha256"] or
            digest(baseline) != value["calc_input_sha256"] or
            demo._source("writer")[0]["package_sha256"] !=
                value["writer_package_sha256"]):
        raise ValueError("Pinned public-train packages changed")
    return value


def _checked_permit(freeze_path: Path, permit_path: Path, value: dict) -> dict:
    from .v066_post_enter_train_calibration_audit_v1 import checked_permit
    return checked_permit(
        freeze_path=freeze_path, permit_path=permit_path, value=value)


def _runtime_preflight(value: dict) -> None:
    versions = {name: importlib.metadata.version(name) for name in SDK_VERSIONS}
    if versions != SDK_VERSIONS or not os.environ.get("E2B_API_KEY"):
        raise ValueError("Pinned E2B runtime or private credential unavailable")
    active, count = active_hashes()
    if active or count:
        raise ValueError("E2B provider not active-zero before train calibration")
    power = subprocess.run(["pmset", "-g", "batt"], capture_output=True,
                           text=True, timeout=5, check=True).stdout
    if ("Now drawing from 'AC Power'" not in power and
            "Now drawing from 'Battery Power'" not in power):
        raise ValueError("Host power telemetry unavailable")
    if storage_audit(Path(value["work_root"]) / "gui-diagnostics")[
            "dispatch_storage_ready"] is not True:
        raise ValueError("Raw train calibration storage unavailable")


def _cold_reset(*, value: dict, freeze_path: Path, permit_path: Path,
                sandbox_factory) -> dict:
    output_root = Path(value["output_root"])
    out = output_root / "cold-reset"
    if out.exists() or out.is_symlink():
        raise ValueError("Fresh cold-reset intent required")
    package, _oracle, baseline, _instruction, filename = demo._source("calc")
    active, count = active_hashes()
    if active or count:
        raise ValueError("Provider must be active-zero before fresh reset")
    budget = budget_audit(Path(value["work_root"]), proposed_new_sandboxes=1,
                          proposed_lease_seconds=LEASE_SECONDS,
                          max_lane_reserved_usd=LANE_CAP_USD)
    if budget["within_cap"] is not True:
        raise ValueError("Third train calibration lease exceeds cap")
    out.mkdir(mode=0o700)
    out.chmod(0o700)
    intent = {
        "schema": "cua-native-wdi-v066-post-enter-train-cold-intent-v1",
        "status": "recorded_before_provider_create", "created_utc": _now(),
        "split": "train", "package_sha256": package["package_sha256"],
        "input_sha256": digest(baseline),
        "freeze_sha256": digest(_private(freeze_path)),
        "permit_sha256": digest(_private(permit_path)),
        "lease_seconds": LEASE_SECONDS,
        "same_intent_replay_authorized": False,
        "official_final_admissions": 0,
    }
    _write_new(out / "intent.json", intent)
    receipt = {
        "schema": "cua-native-wdi-v066-post-enter-train-cold-receipt-v1",
        "status": "started", "stage": "pre_provider", "split": "train",
        "package_sha256": package["package_sha256"],
        "input_sha256": digest(baseline),
        "intent_sha256": digest(_private(out / "intent.json")),
        "official_final_admissions": 0,
        "actual_provider_billed_usd": None,
    }
    receipt_path = out / "receipt.json"
    _write_new(receipt_path, receipt)

    def persist():
        _persist(receipt_path, receipt)

    sandbox = None
    try:
        guest = json.loads(Path(value["guest_public"]).read_bytes())
        reference, _sha = validate_reference(Path(value["scoped_reference"]))
        if "calc" not in reference["applications"]:
            raise ValueError("Public Calc profile reference missing")
        receipt["stage"] = "create_desktop"
        persist()
        sandbox = sandbox_factory(
            template="desktop", resolution=(1280, 800),
            timeout=LEASE_SECONDS, allow_internet_access=False,
            metadata={"envloop_purpose": "v066-public-train-post-enter-cold-reset"})
        receipt["sandbox_id_sha256"] = digest(sandbox.sandbox_id.encode())
        info = sandbox.get_info(request_timeout=12)
        if (info.template_id != guest["provider_template_id"] or
                info.envd_version != guest["provider_envd_version"] or
                info.cpu_count != guest["provider_shape"]["vcpu"] or
                info.memory_mb != guest["provider_shape"]["memory_mb"]):
            raise ValueError("Fresh reset guest provider shape changed")
        sandbox.files.write("/tmp/post-enter-train-content-probe.py",
                            runtime_fingerprint_probe.GUEST_CONTENT_PROBE.encode())
        result = sandbox.commands.run(
            "sudo -n python3 /tmp/post-enter-train-content-probe.py",
            timeout=450, request_timeout=480)
        content = json.loads(result.stdout) if result.exit_code == 0 else {}
        if (content.get("content_tree_sha256") != guest["static_content_sha256"] or
                content.get("counts") != guest["static_content_counts"] or
                content.get("kernel") != guest["kernel_identity"] or
                content.get("excluded_paths") !=
                    guest["static_content_excluded_paths"]):
            raise ValueError("Fresh reset guest content changed")
        receipt["guest_content_attested"] = True
        if sandbox.commands.run(
                "test ! -e /home/user/.config/libreoffice/4/user").exit_code != 0:
            raise ValueError("Fresh reset LibreOffice profile already exists")
        receipt["fresh_profile_absent"] = True
        remote = "/home/user/" + filename
        sandbox.files.write(remote, baseline)
        if bytes(sandbox.files.read(remote, format="bytes")) != baseline:
            raise ValueError("Reset input staging changed")
        sandbox.open(remote)
        receipt["trusted_setup_ready"] = wait_for_document_ready(sandbox, filename)
        time.sleep(7)
        sandbox.press("esc")
        time.sleep(1)
        profile_guard.attest(
            sandbox=sandbox, attempts_root=output_root, out=out,
            app_kind="calc", reference_path=Path(value["scoped_reference"]),
            receipt=receipt, persist=persist)
        frame = bytes(sandbox.screenshot())
        receipt["cold_observation"] = reserve_and_write(
            output_root, out / "cold-neutral-open.png", frame)
        restored = bytes(sandbox.files.read(remote, format="bytes"))
        receipt["restored_artifact"] = reserve_and_write(
            output_root, out / "restored-original.xlsx", restored)
        if restored != baseline:
            raise ValueError("Fresh reset source OOXML bytes changed")
        receipt["restored_state_sha256"] = digest(restored)
        receipt["status"] = "cold_reset_observed_before_teardown"
    except Exception as exc:
        receipt["status"] = "cold_reset_failed_or_infrastructure_invalid"
        receipt["error_type"] = type(exc).__name__
    finally:
        if sandbox is not None:
            try:
                receipt["kill_returned"] = bool(sandbox.kill())
                receipt["is_running_after_kill"] = bool(
                    sandbox.is_running(request_timeout=12))
            except Exception as exc:
                receipt["kill_error_type"] = type(exc).__name__
        if receipt.get("is_running_after_kill") is not False:
            receipt["status"] = "cleanup_unverified"
        elif receipt["status"] == "cold_reset_observed_before_teardown":
            receipt["status"] = "cold_reset_observed"
        persist()
    return receipt


def run(*, freeze_path: Path, permit_path: Path,
        enable_paid_train_calibration: bool = False) -> dict:
    if enable_paid_train_calibration is not True:
        raise ValueError("Paid train calibration requires explicit enablement")
    value = validate_source(freeze_path)
    _checked_permit(freeze_path, permit_path, value)
    output_root = Path(value["output_root"])
    work_root = Path(value["work_root"])
    run_path = output_root.parent / (output_root.name + ".calibration-run.private.json")
    if (output_root.exists() or output_root.is_symlink() or
            run_path.exists() or run_path.is_symlink()):
        raise ValueError("Train calibration output or root-owned run already consumed")
    _runtime_preflight(value)
    journal = {
        "schema": "cua-native-wdi-v066-post-enter-train-calibration-run-private-v1",
        "status": "started", "started_utc": _now(),
        "freeze_sha256": digest(_private(freeze_path)),
        "permit_sha256": digest(_private(permit_path)),
        "output_root": str(output_root), "guest_count_planned": 3,
        "official_final_admissions": 0,
    }
    _write_new(run_path, journal)
    from e2b_desktop import Sandbox
    real_create = Sandbox.create
    next_kind = iter(("calc", "writer"))

    def instrumented_create(*args, **kwargs):
        kind = next(next_kind)
        sandbox = real_create(*args, **kwargs)
        filename = demo._source(kind)[4]
        if kind == "calc":
            return PostEnterProbeProxy(
                sandbox, storage_root=output_root, output=output_root / kind,
                document_filename=filename)
        return sandbox

    try:
        with patch.object(Sandbox, "create", instrumented_create):
            result = demo.run_both(
                output_root=output_root, work_root=work_root,
                guest_public=Path(value["guest_public"]),
                scoped_reference=Path(value["scoped_reference"]),
                reservation_path=Path(value["reservation_path"]),
                enable_paid_train_demos=True)
        if result["status"] != "two_public_train_gui_positives_pending_audit":
            raise ValueError("Public-train saved-state demo stopped")
        demo_audit.audit_both(
            output_root=output_root,
            scoped_reference=Path(value["scoped_reference"]),
            guest_public=Path(value["guest_public"]),
            reservation_path=Path(value["reservation_path"]))
        journal["stage"] = "two_train_saved_positives_independently_audited"
        _persist(run_path, journal)
        cold = _cold_reset(
            value=value, freeze_path=freeze_path,
            permit_path=permit_path, sandbox_factory=real_create)
        if cold["status"] != "cold_reset_observed":
            raise ValueError("Fresh public-train Calc reset failed")
        from .v066_post_enter_train_calibration_audit_v1 import audit
        audited = audit(freeze_path=freeze_path, run_path=run_path)
        journal["status"] = "three_train_guests_independently_audited"
        journal["audit_sha256"] = digest((json.dumps(
            audited, sort_keys=True, separators=(",", ":")) + "\n").encode())
    except Exception as exc:
        journal["status"] = "stopped_for_reconciliation"
        journal["error_type"] = type(exc).__name__
    journal["finished_utc"] = _now()
    _persist(run_path, journal)
    return {"status": journal["status"],
            "official_final_admissions": 0,
            "run_receipt_sha256": digest(_private(run_path))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "run"))
    parser.add_argument("--work-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--guest-public", type=Path)
    parser.add_argument("--scoped-reference", type=Path)
    parser.add_argument("--reservation", type=Path)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--public", type=Path)
    parser.add_argument("--permit", type=Path)
    parser.add_argument("--enable-paid-train-calibration", action="store_true")
    args = parser.parse_args()
    if args.mode == "prepare":
        if any(item is None for item in (
                args.work_root, args.output_root, args.guest_public,
                args.scoped_reference, args.reservation, args.public)):
            raise ValueError("Train calibration source paths required")
        result = prepare(
            work_root=args.work_root, output_root=args.output_root,
            guest_public=args.guest_public,
            scoped_reference=args.scoped_reference,
            reservation_path=args.reservation,
            freeze_path=args.freeze, public_path=args.public)
    else:
        if args.permit is None:
            raise ValueError("Exact independent train permit required")
        result = run(
            freeze_path=args.freeze, permit_path=args.permit,
            enable_paid_train_calibration=args.enable_paid_train_calibration)
    print(json.dumps(result, sort_keys=True))
    if result.get("status", "").startswith("stopped_"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
