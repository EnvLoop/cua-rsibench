"""Five serial public-train guests for scoped LibreOffice profile calibration.

One prior Calc train capture is retained; this run requests one new Calc and
two each Writer and Impress guests. It stages only three pinned public train
packages, makes no actor edit or model call, writes raw manifest/XML before
canonicalization, and stops after the first failed or uncertain guest. This
does not amend the frozen final-control acceptance rule.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import importlib.metadata
import json
import os
from pathlib import Path
import time

from . import (profile_canonical, qwen_v066_adapter,
               runtime_fingerprint_probe, v066_profile_scope_analysis)
from .budget_ledger import audit as budget_audit
from .factory import json_bytes
from .gui_control_shell import wait_for_document_ready
from .reconcile_interrupted_sweep import active_hashes
from .v066_final_freeze import digest, validate_ratification


FIXTURES = {
    "calc": "wdi-native-mex-calc-growth",
    "writer": "wdi-native-mex-writer-brief",
    "impress": "wdi-native-mex-impress-deck-normalized",
}
PLAN = (("calc-second", "calc"),
        ("writer-first", "writer"), ("writer-second", "writer"),
        ("impress-first", "impress"), ("impress-second", "impress"))
SNAPSHOTS = (("first", 0), ("second", 1),
             ("settled_early", 3), ("settled_late", 4))
LEASE_SECONDS = 600
DIAGNOSTIC_CAP_USD = Decimal("42")
RECEIPT_SCHEMA = "cua-native-wdi-gui-development-attempt-v1"
RESERVATION_SCHEMA = "cua-native-wdi-v066-train-profile-cross-guest-reservation-v1"


def _write_new(path: Path, raw: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _source(kind: str) -> tuple[dict, bytes, str]:
    if kind not in FIXTURES:
        raise ValueError("Only three pinned public train fixture kinds are allowed")
    directory = (Path(__file__).with_name("dev-fixtures") / FIXTURES[kind])
    package = json.loads((directory / "package.json").read_bytes())
    oracle_raw = (directory / "oracle.json").read_bytes()
    actor_raw = (directory / "actor_task.txt").read_bytes()
    inputs = [*directory.glob("*.xlsx"), *directory.glob("*.docx"),
              *directory.glob("*.pptx")]
    if (len(inputs) != 1 or package.get("split") != "train" or
            package.get("workflow") != {
                "calc": "calc-growth", "writer": "writer-brief",
                "impress": "impress-deck"}[kind] or
            package.get("package_sha256") != digest(json_bytes({
                key: value for key, value in package.items()
                if key != "package_sha256"})) or
            package.get("oracle_sha256") != digest(oracle_raw) or
            package.get("actor_task_sha256") != digest(actor_raw)):
        raise ValueError("Public train package source binding changed")
    oracle = json.loads(oracle_raw)
    raw = inputs[0].read_bytes()
    if (oracle.get("split") != "train" or
            oracle.get("task_id") != package.get("task_id") or
            oracle.get("input_sha256") != package.get("input_sha256") or
            digest(raw) != package.get("input_sha256")):
        raise ValueError("Public train OOXML input binding changed")
    return package, raw, inputs[0].name


def source_package_hashes() -> dict[str, str]:
    return {kind: _source(kind)[0]["package_sha256"]
            for kind in FIXTURES}


def _prior_calc(prior_dir: Path) -> tuple[dict, bytes, bytes]:
    receipt_path = prior_dir / "receipt.json"
    audit_path = prior_dir / "post-audit.private.json"
    raw, audit_raw = receipt_path.read_bytes(), audit_path.read_bytes()
    receipt, audit = json.loads(raw), json.loads(audit_raw)
    if (receipt.get("schema") != RECEIPT_SCHEMA or
            receipt.get("purpose") !=
            "v066_public_train_calc_profile_diagnostic_no_model" or
            receipt.get("status") != "profile_diagnostic_captured" or
            receipt.get("split") != "train" or
            receipt.get("package_sha256") !=
            _source("calc")[0]["package_sha256"] or
            receipt.get("kill_returned") is not True or
            receipt.get("is_running_after_kill") is not False or
            len(receipt.get("profile_snapshots", [])) != 4 or
            audit.get("receipt_sha256") != digest(raw)):
        raise ValueError("Prior public Calc raw train capture changed")
    for name, expected in audit.get("output_file_sha256s", {}).items():
        path = prior_dir / name
        if (path.is_symlink() or not path.is_file() or
                digest(path.read_bytes()) != expected):
            raise ValueError("Prior public Calc raw bytes changed")
    return receipt, raw, audit_raw


def _snapshot(sandbox, output: Path, label: str,
              started: float) -> dict:
    run = sandbox.commands.run(
        "python3 /tmp/native-profile-file-probe-cross-guest.py")
    if run.exit_code != 0:
        raise ValueError("Cross-guest raw profile-file probe failed")
    manifest_raw = run.stdout.encode()
    if not manifest_raw or len(manifest_raw) > 4_000_000:
        raise ValueError("Cross-guest profile manifest is unbounded")
    _write_new(output / f"profile-{label}.manifest.json", manifest_raw)
    registry_raw = bytes(sandbox.files.read(
        "/home/user/.config/libreoffice/4/user/registrymodifications.xcu",
        format="bytes"))
    if not registry_raw or len(registry_raw) > 4_000_000:
        raise ValueError("Cross-guest raw registry is unbounded")
    _write_new(output / f"profile-{label}.registry.xml", registry_raw)
    frame_raw = bytes(sandbox.screenshot())
    if not frame_raw or len(frame_raw) > 4_000_000:
        raise ValueError("Cross-guest visible frame is unbounded")
    _write_new(output / f"frame-{label}.png", frame_raw)
    record = {"label": label,
              "captured_utc": datetime.now(timezone.utc).isoformat(),
              "elapsed_seconds_after_open": round(time.monotonic() - started, 3),
              "manifest_sha256": digest(manifest_raw),
              "registry_sha256": digest(registry_raw),
              "frame_sha256": digest(frame_raw),
              "frame_bytes": len(frame_raw)}
    try:
        rows = json.loads(manifest_raw)
        record["file_count"] = len(rows)
        record["strict_profile_sha256"] = (
            profile_canonical.canonical_profile_tree(rows, registry_raw))
        record["scoped_profile_sha256"] = (
            v066_profile_scope_analysis.scoped_profile(rows, registry_raw))
    except (ValueError, TypeError, KeyError) as exc:
        record["canonical_error_type"] = type(exc).__name__
        record["canonical_error_message_private"] = str(exc)[:200]
        record["strict_profile_sha256"] = None
        record["scoped_profile_sha256"] = None
    return record


def reservation_payload(*, work_root: Path, prior_calc_dir: Path,
                        guest_public: Path, ratification: Path) -> dict:
    prior, prior_raw, prior_audit_raw = _prior_calc(prior_calc_dir)
    guest_raw = guest_public.read_bytes()
    guest = json.loads(guest_raw)
    if (guest.get("schema") !=
            "cua-native-wdi-guest-content-identity-public-v1" or
            guest.get("scoped_guest_content_identity_passed") is not True or
            guest.get("guest_content_probe_script_sha256") !=
            digest(runtime_fingerprint_probe.GUEST_CONTENT_PROBE.encode())):
        raise ValueError("Scoped guest identity changed")
    _, rat_sha = validate_ratification(ratification)
    budget = budget_audit(
        work_root, proposed_new_sandboxes=len(PLAN),
        proposed_lease_seconds=LEASE_SECONDS,
        max_lane_reserved_usd=DIAGNOSTIC_CAP_USD)
    source_sha = digest(Path(__file__).read_bytes())
    scope_sha = digest(Path(v066_profile_scope_analysis.__file__).read_bytes())
    audit_sha = digest(Path(__file__).with_name(
        "v066_train_profile_cross_guest_audit.py").read_bytes())
    adapter_sha = digest(Path(qwen_v066_adapter.__file__).read_bytes())
    expected = {
        "schema": RESERVATION_SCHEMA,
        "status": "reserved_before_five_public_train_creates",
        "calibration_source_sha256": source_sha,
        "scoped_analysis_source_sha256": scope_sha,
        "calibration_audit_source_sha256": audit_sha,
        "desktop_adapter_sha256": adapter_sha,
        "new_six_cell_ratification_sha256": rat_sha,
        "guest_identity_public_sha256": digest(guest_raw),
        "fixture_package_sha256s": source_package_hashes(),
        "prior_public_calc_receipt_sha256": digest(prior_raw),
        "prior_public_calc_post_audit_sha256": digest(prior_audit_raw),
        "past_conservative_reserved_usd":
            budget["past_conservative_reserved_usd"],
        "new_full_lease_intents_reserved": len(PLAN),
        "lease_seconds_each": LEASE_SECONDS,
        "combined_conservative_reserved_usd":
            budget["combined_reserved_usd"],
        "diagnostic_cap_usd": str(DIAGNOSTIC_CAP_USD),
        "actual_provider_billed_usd": None,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    if not budget["within_cap"] or prior.get("actor_gui_actions") != 0:
        raise ValueError("Five-guest source-bound train reserve missing")
    expected["recorded_utc"] = datetime.now(timezone.utc).isoformat()
    return expected


def prepare_reservation(*, work_root: Path, prior_calc_dir: Path,
                        guest_public: Path, ratification: Path,
                        reservation_path: Path) -> dict:
    if reservation_path.exists() or reservation_path.is_symlink():
        raise ValueError("New exclusive train calibration reservation required")
    value = reservation_payload(
        work_root=work_root, prior_calc_dir=prior_calc_dir,
        guest_public=guest_public, ratification=ratification)
    reservation_path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    _write_new(reservation_path,
               (json.dumps(value, sort_keys=True, separators=(",", ":")) +
                "\n").encode())
    return value


def _reservation(*, work_root: Path, reservation_path: Path,
                 prior_calc_dir: Path, guest_public: Path,
                 ratification: Path) -> tuple[dict, str]:
    expected = reservation_payload(
        work_root=work_root, prior_calc_dir=prior_calc_dir,
        guest_public=guest_public, ratification=ratification)
    expected.pop("recorded_utc")
    reservation_raw = reservation_path.read_bytes()
    reservation = json.loads(reservation_raw)
    if (any(reservation.get(key) != value for key, value in
            expected.items()) or
            type(reservation.get("recorded_utc")) is not str):
        raise ValueError("Five-guest source-bound train reserve changed")
    try:
        recorded = datetime.fromisoformat(reservation["recorded_utc"])
    except (TypeError, ValueError):
        raise ValueError("Train calibration reservation time invalid") from None
    if (recorded.tzinfo is None or
            recorded.astimezone(timezone.utc) > datetime.now(timezone.utc)):
        raise ValueError("Train calibration reservation time invalid")
    return reservation, digest(reservation_raw)


def _versions_pinned() -> None:
    versions = {name: importlib.metadata.version(name)
                for name in ("e2b-desktop", "e2b", "Pillow")}
    if versions != {"e2b-desktop": "2.2.0",
                    "e2b": "2.51.0", "Pillow": "11.3.0"}:
        raise ValueError("Dedicated Desktop dependency versions changed")


def run_one(*, label: str, kind: str, output: Path,
            work_root: Path, guest_public: Path,
            reservation_sha256: str) -> dict:
    if (output.exists() or output.is_symlink() or
            not output.resolve().is_relative_to(
                (work_root / "gui-diagnostics").resolve())):
        raise ValueError("Train capture output is not new/private")
    _versions_pinned()
    package, baseline, filename = _source(kind)
    budget = budget_audit(
        work_root, proposed_new_sandboxes=1,
        proposed_lease_seconds=LEASE_SECONDS,
        max_lane_reserved_usd=DIAGNOSTIC_CAP_USD)
    if not budget["within_cap"] or not os.environ.get("E2B_API_KEY"):
        raise ValueError("Train diagnostic budget or credential missing")
    active, count = active_hashes()
    if active or count:
        raise ValueError("Provider is not active-zero before train capture")
    guest_raw = guest_public.read_bytes()
    guest = json.loads(guest_raw)
    output.mkdir(parents=True, mode=0o700)
    output.chmod(0o700)
    intent = {
        "schema": "cua-native-wdi-v066-train-profile-cross-guest-intent-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "label": label, "kind": kind, "split": "train",
        "package_sha256": package["package_sha256"],
        "input_sha256": digest(baseline),
        "calibration_source_sha256": digest(Path(__file__).read_bytes()),
        "reservation_sha256": reservation_sha256,
        "lease_seconds": LEASE_SECONDS,
        "automatic_replay_authorized": False,
        "actor_gui_actions_authorized": 0,
        "official_model_results": 0,
    }
    _write_new(output / "intent.json",
               (json.dumps(intent, sort_keys=True) + "\n").encode())
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "purpose": "v066_public_train_profile_cross_guest_no_model",
        "status": "started", "stage": "pre_provider",
        "split": "train", "label": label, "kind": kind,
        "package_sha256": package["package_sha256"],
        "input_sha256": digest(baseline),
        "sandbox_timeout_seconds": LEASE_SECONDS,
        "provider_running_before_create": count,
        "reservation_sha256": reservation_sha256,
        "calibration_source_sha256": digest(Path(__file__).read_bytes()),
        "scoped_analysis_source_sha256": digest(
            Path(v066_profile_scope_analysis.__file__).read_bytes()),
        "calibration_audit_source_sha256": digest(Path(__file__).with_name(
            "v066_train_profile_cross_guest_audit.py").read_bytes()),
        "guest_identity_public_sha256": digest(guest_raw),
        "profile_probe_script_sha256": digest(
            runtime_fingerprint_probe.PROFILE_FILE_PROBE.encode()),
        "sdk_version": importlib.metadata.version("e2b-desktop"),
        "profile_snapshots": [], "actor_gui_actions": 0,
        "provider_billed_usd": None,
        "official_final_model_attempts": 0,
        "official_final_admissions": 0,
    }

    def persist() -> None:
        path = output / "receipt.json"
        path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        path.chmod(0o600)

    persist()
    sandbox = None
    try:
        from e2b_desktop import Sandbox
        receipt["stage"] = "create_desktop"
        persist()
        sandbox = Sandbox.create(
            template="desktop", resolution=(1280, 800),
            timeout=LEASE_SECONDS, allow_internet_access=False,
            metadata={"envloop_purpose": "v066-public-train-profile-calibration"})
        receipt["sandbox_id_sha256"] = digest(sandbox.sandbox_id.encode())
        info = sandbox.get_info(request_timeout=12)
        receipt["provider_sandbox_info"] = {
            "template_id": info.template_id, "vcpu": info.cpu_count,
            "memory_mb": info.memory_mb, "envd_version": info.envd_version}
        if (info.template_id != guest["provider_template_id"] or
                info.envd_version != guest["provider_envd_version"] or
                info.cpu_count != guest["provider_shape"]["vcpu"] or
                info.memory_mb != guest["provider_shape"]["memory_mb"]):
            raise ValueError("Provider Desktop shape/template changed")
        receipt["stage"] = "scoped_guest_content_attestation"
        persist()
        sandbox.files.write("/tmp/native-guest-content-probe-train-profiles.py",
                            runtime_fingerprint_probe.GUEST_CONTENT_PROBE.encode())
        run = sandbox.commands.run(
            "sudo -n python3 /tmp/native-guest-content-probe-train-profiles.py",
            timeout=450, request_timeout=480)
        if run.exit_code != 0:
            raise ValueError("Scoped guest-content probe failed")
        observed = json.loads(run.stdout)
        if (observed.get("content_tree_sha256") !=
                guest["static_content_sha256"] or
                observed.get("counts") != guest["static_content_counts"] or
                observed.get("kernel") != guest["kernel_identity"] or
                observed.get("excluded_paths") !=
                guest["static_content_excluded_paths"]):
            raise ValueError("Scoped guest identity differs")
        receipt["guest_content_attested"] = True
        if sandbox.commands.run(
                "test ! -e /home/user/.config/libreoffice/4/user").exit_code != 0:
            raise ValueError("Fresh LibreOffice profile already exists")
        receipt["fresh_profile_absent"] = True
        remote = "/home/user/" + filename
        sandbox.files.write(remote, baseline)
        if bytes(sandbox.files.read(remote, format="bytes")) != baseline:
            raise ValueError("Public train input staging changed")
        sandbox.files.write("/tmp/native-profile-file-probe-cross-guest.py",
                            runtime_fingerprint_probe.PROFILE_FILE_PROBE.encode())
        receipt["stage"] = "trusted_public_train_open"
        persist()
        sandbox.open(remote)
        receipt["trusted_setup_ready"] = wait_for_document_ready(
            sandbox, filename)
        time.sleep(7)
        sandbox.press("esc")
        time.sleep(1)
        frame = bytes(sandbox.screenshot())
        _write_new(output / "neutral-open.png", frame)
        receipt["neutral_open_screenshot_sha256"] = digest(frame)
        started = time.monotonic()
        receipt["stage"] = "raw_profile_snapshots"
        persist()
        for name, delay in SNAPSHOTS:
            if delay:
                time.sleep(delay)
            receipt["profile_snapshots"].append(
                _snapshot(sandbox, output, name, started))
            persist()
        scoped = [item.get("scoped_profile_sha256")
                  for item in receipt["profile_snapshots"]]
        receipt["scoped_within_guest_stable"] = (
            all(scoped) and len(set(scoped)) == 1)
        if not receipt["scoped_within_guest_stable"]:
            raise ValueError("Scoped public-train profile unstable or unparseable")
        if bytes(sandbox.files.read(remote, format="bytes")) != baseline:
            raise ValueError("Neutral open changed public train input")
        receipt["input_unchanged_after_open"] = True
        receipt["status"] = "train_profile_captured"
    except Exception as exc:
        receipt["error_type"] = type(exc).__name__
        receipt["error_message_private"] = str(exc)[:240]
        receipt["status"] = "train_profile_failed"
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
        persist()
    return receipt


def run_all(*, work_root: Path, output_root: Path,
            prior_calc_dir: Path, guest_public: Path,
            ratification: Path, reservation_path: Path,
            enable_paid_train_calibration: bool = False) -> dict:
    if enable_paid_train_calibration is not True:
        raise ValueError("Paid train profile calibration is disabled")
    if (output_root.exists() or output_root.is_symlink() or
            not output_root.resolve().is_relative_to(
                (work_root / "gui-diagnostics").resolve())):
        raise ValueError("New private calibration root required")
    _versions_pinned()
    _reservation(work_root=work_root,
                 reservation_path=reservation_path,
                 prior_calc_dir=prior_calc_dir,
                 guest_public=guest_public,
                 ratification=ratification)
    reservation_sha = digest(reservation_path.read_bytes())
    output_root.mkdir(parents=True, mode=0o700)
    output_root.chmod(0o700)
    journal = {
        "schema": "cua-native-wdi-v066-train-profile-cross-guest-run-v1",
        "status": "started",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "calibration_source_sha256": digest(Path(__file__).read_bytes()),
        "scoped_analysis_source_sha256": digest(
            Path(v066_profile_scope_analysis.__file__).read_bytes()),
        "reservation_sha256": reservation_sha,
        "planned_attempts": [label for label, _kind in PLAN],
        "attempts": [],
        "automatic_retry_authorized": False,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }

    def persist() -> None:
        path = output_root / "run-receipt.json"
        path.write_text(json.dumps(journal, indent=2, sort_keys=True) + "\n")
        path.chmod(0o600)

    persist()
    for label, kind in PLAN:
        try:
            result = run_one(
                label=label, kind=kind,
                output=output_root / label,
                work_root=work_root, guest_public=guest_public,
                reservation_sha256=reservation_sha)
            row = {"label": label, "kind": kind,
                   "status": result["status"],
                   "receipt_sha256": digest(
                       (output_root / label / "receipt.json").read_bytes()),
                   "sandbox_id_observed": bool(result.get("sandbox_id_sha256")),
                   "cleanup_verified": result.get(
                       "is_running_after_kill") is False}
        except Exception as exc:
            row = {"label": label, "kind": kind,
                   "status": "precreate_or_worker_exception",
                   "error_type": type(exc).__name__,
                   "receipt_sha256": None,
                   "cleanup_verified": False}
        journal["attempts"].append(row)
        persist()
        if (row["status"] != "train_profile_captured" or
                not row["cleanup_verified"]):
            journal["status"] = "stopped_for_reconciliation"
            break
    else:
        journal["status"] = "all_raw_train_profiles_captured_pending_audit"
    journal["finished_utc"] = datetime.now(timezone.utc).isoformat()
    journal["diagnostic_lane_budget"] = budget_audit(
        work_root, proposed_new_sandboxes=0,
        proposed_lease_seconds=LEASE_SECONDS,
        max_lane_reserved_usd=DIAGNOSTIC_CAP_USD)
    persist()
    return journal


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("prepare-reservation", "run"),
                        required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--prior-calc-dir", type=Path, required=True)
    parser.add_argument("--guest-public", type=Path, required=True)
    parser.add_argument("--ratification", type=Path, required=True)
    parser.add_argument("--reservation", type=Path, required=True)
    parser.add_argument("--enable-paid-train-calibration", action="store_true")
    args = parser.parse_args()
    if args.mode == "prepare-reservation":
        value = prepare_reservation(
            work_root=args.work_root, prior_calc_dir=args.prior_calc_dir,
            guest_public=args.guest_public, ratification=args.ratification,
            reservation_path=args.reservation)
        print(json.dumps({
            "status": value["status"],
            "reservation_sha256": digest(args.reservation.read_bytes()),
            "new_full_lease_intents_reserved": len(PLAN),
            "combined_conservative_reserved_usd":
                value["combined_conservative_reserved_usd"],
            "official_final_admissions": 0,
        }, sort_keys=True))
    else:
        if args.output_root is None:
            raise ValueError("New private output root required for run")
        result = run_all(
            work_root=args.work_root, output_root=args.output_root,
            prior_calc_dir=args.prior_calc_dir,
            guest_public=args.guest_public, ratification=args.ratification,
            reservation_path=args.reservation,
            enable_paid_train_calibration=args.enable_paid_train_calibration)
        print(json.dumps({
            "status": result["status"],
            "attempts_recorded": len(result["attempts"]),
            "new_train_guests_passed": sum(
                item["status"] == "train_profile_captured"
                for item in result["attempts"]),
            "run_journal_sha256": digest(
                (args.output_root / "run-receipt.json").read_bytes()),
            "official_final_admissions": 0,
        }, sort_keys=True))
        if result["status"] != "all_raw_train_profiles_captured_pending_audit":
            raise SystemExit(2)


if __name__ == "__main__":
    main()
