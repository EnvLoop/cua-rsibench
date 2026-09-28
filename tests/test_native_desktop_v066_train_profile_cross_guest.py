"""Offline five-guest train calibration, source binding, and stop gates."""

from __future__ import annotations

from datetime import datetime, timezone
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from PIL import Image

from native_desktop_factory import (
    runtime_fingerprint_probe,
    v066_train_profile_cross_guest as train,
    v066_train_profile_cross_guest_audit as audit,
)
from native_desktop_factory.v066_final_freeze import digest


REGISTRY = (b'<?xml version="1.0"?><items '
            b'xmlns:oor="http://openoffice.org/2001/registry">'
            b'<item oor:path="/org.openoffice.Office.Histories/Histories/'
            b'org.openoffice.Office.Histories:HistoryInfo[\'PickList\']/ItemList">'
            b'<node oor:name="one"><prop oor:name="Title"><value>one</value>'
            b'</prop></node></item>'
            b'<item oor:path="/org.openoffice.Office.Histories/Histories/'
            b'org.openoffice.Office.Histories:HistoryInfo[\'PickList\']/OrderList">'
            b'<node oor:name="0"><prop oor:name="HistoryItemRef">'
            b'<value>one</value></prop></node></item>'
            b'<item oor:path="/org.openoffice.Office.Recovery/RecoveryList">'
            b'<node oor:name="recovery_item_1"><prop oor:name="DocumentState">'
            b'<value>1</value></prop></node></item>'
            b'<item oor:path="/org.openoffice.Setup/Product">'
            b'<prop oor:name="LastTimeDonateShown"><value>123</value></prop>'
            b'<prop oor:name="LastTimeGetInvolvedShown"><value>456</value></prop>'
            b'<prop oor:name="ooSetupLastVersion"><value>7</value></prop>'
            b'</item></items>')


class FakeCommand:
    exit_code = 0

    def __init__(self, raw: bytes):
        self.stdout = raw.decode()


class FakeSandbox:
    def __init__(self, registry: bytes):
        self.registry = registry
        self.commands = self
        self.files = self

    def run(self, _command):
        rows = [{"path": "registrymodifications.xcu",
                 "sha256": digest(self.registry),
                 "bytes": len(self.registry)},
                {"path": "config/settings.bin",
                 "sha256": "a" * 64, "bytes": 4}]
        return FakeCommand(json.dumps(rows).encode())

    def read(self, _path, *, format):
        assert format == "bytes"
        return self.registry

    def screenshot(self):
        output = io.BytesIO()
        Image.new("RGB", (1280, 800), "white").save(output, format="PNG")
        return output.getvalue()


class TrainProfileCrossGuestTests(unittest.TestCase):
    def test_dated_proposal_binds_code_and_keeps_official_zero(self):
        root = Path(__file__).resolve().parents[1]
        public = json.loads((root / "docs/evidence" /
            "native-wdi-v066-scoped-profile-pre-result-amendment-2026-09-28.json"
            ).read_bytes())
        self.assertEqual(public["train_calibration_source_sha256"],
                         digest(Path(train.__file__).read_bytes()))
        self.assertEqual(public["train_calibration_audit_source_sha256"],
                         digest(Path(audit.__file__).read_bytes()))
        self.assertFalse(public["generic_acceptance_rule_changed"])
        self.assertEqual(public["official_final_admissions"], 0)

    def test_public_calibration_receipt_binds_auditor_without_final_claim(self):
        root = Path(__file__).resolve().parents[1]
        public = json.loads((root / "docs/evidence" /
            "native-wdi-v066-train-profile-cross-guest-2026-09-28.json"
            ).read_bytes())
        self.assertEqual(public["calibration_source_sha256"],
                         digest(Path(train.__file__).read_bytes()))
        self.assertEqual(public["independent_calibration_audit_source_sha256"],
                         digest(Path(audit.__file__).read_bytes()))
        self.assertEqual(public["same_application_cross_guest_pairs_passed"], 3)
        self.assertFalse(public["generic_final_acceptance_rule_changed"])
        self.assertEqual(public["official_final_admissions"], 0)

    def test_only_public_train_calc_writer_impress_packages(self):
        self.assertEqual(len(train.PLAN), 5)
        self.assertEqual([kind for _label, kind in train.PLAN],
                         ["calc", "writer", "writer", "impress", "impress"])
        for kind in train.FIXTURES:
            package, raw, filename = train._source(kind)
            self.assertEqual(package["split"], "train")
            self.assertEqual(digest(raw), package["input_sha256"])
            self.assertIn(Path(filename).suffix, (".xlsx", ".docx", ".pptx"))
        with self.assertRaisesRegex(ValueError, "Only three pinned"):
            train._source("final")

    def test_snapshot_keeps_raw_bytes_before_canonical_error(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            with patch.object(train.v066_profile_scope_analysis,
                              "scoped_profile",
                              side_effect=ValueError("synthetic scope error")):
                value = train._snapshot(FakeSandbox(REGISTRY), root,
                                        "first", time.monotonic())
            self.assertIsNone(value["scoped_profile_sha256"])
            self.assertEqual(value["canonical_error_type"], "ValueError")
            self.assertEqual(digest((root / "profile-first.registry.xml").read_bytes()),
                             value["registry_sha256"])
            self.assertEqual(digest((root / "profile-first.manifest.json").read_bytes()),
                             value["manifest_sha256"])
            self.assertEqual(digest((root / "frame-first.png").read_bytes()),
                             value["frame_sha256"])

    def test_reservation_is_exact_source_bound_and_exclusive(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            guest = root / "guest.json"
            guest.write_text(json.dumps({
                "schema": "cua-native-wdi-guest-content-identity-public-v1",
                "scoped_guest_content_identity_passed": True,
                "guest_content_probe_script_sha256": digest(
                    runtime_fingerprint_probe.GUEST_CONTENT_PROBE.encode())}))
            ratification = root / "ratification.json"
            ratification.write_text("{}")
            path = root / "reserve.private.json"
            fake_budget = {
                "within_cap": True,
                "past_conservative_reserved_usd": "40.5",
                "combined_reserved_usd": "41.33333333333333333333333333",
            }
            with (patch.object(train, "_prior_calc", return_value=(
                    {"actor_gui_actions": 0}, b"prior", b"audit")),
                  patch.object(train, "validate_ratification",
                               return_value=({}, "a" * 64)),
                  patch.object(train, "budget_audit", return_value=fake_budget)):
                value = train.prepare_reservation(
                    work_root=root, prior_calc_dir=root,
                    guest_public=guest, ratification=ratification,
                    reservation_path=path)
                self.assertEqual(value["new_full_lease_intents_reserved"], 5)
                train._reservation(
                    work_root=root, reservation_path=path,
                    prior_calc_dir=root, guest_public=guest,
                    ratification=ratification)
                with self.assertRaisesRegex(ValueError, "New exclusive"):
                    train.prepare_reservation(
                        work_root=root, prior_calc_dir=root,
                        guest_public=guest, ratification=ratification,
                        reservation_path=path)
                changed = json.loads(path.read_bytes())
                changed["calibration_source_sha256"] = "0" * 64
                path.write_text(json.dumps(changed))
                with self.assertRaisesRegex(ValueError, "source-bound"):
                    train._reservation(
                        work_root=root, reservation_path=path,
                        prior_calc_dir=root, guest_public=guest,
                        ratification=ratification)

    def test_disabled_and_first_failed_guest_stop_before_second_create(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            output = root / "gui-diagnostics" / "run"
            reservation = root / "reservation.json"
            reservation.write_text("{}")
            kwargs = {"work_root": root, "output_root": output,
                      "prior_calc_dir": root / "prior",
                      "guest_public": root / "guest",
                      "ratification": root / "rat",
                      "reservation_path": reservation}
            with self.assertRaisesRegex(ValueError, "disabled"):
                train.run_all(**kwargs)
            self.assertFalse(output.exists())

            def failed_first(**arguments):
                target = arguments["output"]
                target.mkdir()
                (target / "receipt.json").write_text("{}")
                return {"status": "train_profile_failed",
                        "sandbox_id_sha256": "a" * 64,
                        "is_running_after_kill": False}

            with (patch.object(train, "_versions_pinned"),
                  patch.object(train, "_reservation", return_value=({}, "a" * 64)),
                  patch.object(train, "budget_audit", return_value={}),
                  patch.object(train, "run_one", side_effect=failed_first) as worker):
                result = train.run_all(
                    **kwargs, enable_paid_train_calibration=True)
            self.assertEqual(result["status"], "stopped_for_reconciliation")
            self.assertEqual(len(result["attempts"]), 1)
            worker.assert_called_once()

    def test_negative_controls_detect_real_setting_state_and_file_changes(self):
        rows = json.loads(FakeSandbox(REGISTRY).run("probe").stdout)
        result = audit._negative_controls(rows, REGISTRY)
        self.assertEqual(result, {"setting_detected": True,
                                  "recovery_state_detected": True,
                                  "nonregistry_file_detected": True})

    def test_independent_six_guest_pair_audit_and_one_setting_mismatch(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            prior = root / "prior"
            output = root / "new"
            prior.mkdir()
            output.mkdir()
            reservation = root / "reservation.json"
            payload = {
                "schema": train.RESERVATION_SCHEMA,
                "calibration_source_sha256": digest(Path(train.__file__).read_bytes()),
                "scoped_analysis_source_sha256": digest(
                    Path(train.v066_profile_scope_analysis.__file__).read_bytes()),
                "calibration_audit_source_sha256":
                    digest(Path(audit.__file__).read_bytes()),
                "desktop_adapter_sha256": digest(
                    Path(train.qwen_v066_adapter.__file__).read_bytes()),
                "new_full_lease_intents_reserved": 5,
                "prior_public_calc_receipt_sha256": digest(b"prior"),
                "prior_public_calc_post_audit_sha256": digest(b"audit"),
            }
            reservation.write_text(json.dumps(payload))
            reservation_sha = digest(reservation.read_bytes())
            frame = FakeSandbox(REGISTRY).screenshot()

            def capture(directory, registry, *, new_guest):
                directory.mkdir(exist_ok=True)
                rows = json.loads(FakeSandbox(registry).run("probe").stdout)
                manifest = json.dumps(rows).encode()
                scoped = train.v066_profile_scope_analysis.scoped_profile(
                    rows, registry)
                snapshots = []
                for label, _delay in train.SNAPSHOTS:
                    (directory / f"profile-{label}.manifest.json").write_bytes(manifest)
                    (directory / f"profile-{label}.registry.xml").write_bytes(registry)
                    snapshot = {"label": label,
                                "manifest_sha256": digest(manifest),
                                "registry_sha256": digest(registry),
                                "scoped_profile_sha256": scoped}
                    if new_guest:
                        (directory / f"frame-{label}.png").write_bytes(frame)
                        snapshot.update({"frame_sha256": digest(frame),
                                         "frame_bytes": len(frame)})
                    snapshots.append(snapshot)
                (directory / "neutral-open.png").write_bytes(frame)
                return snapshots

            prior_snapshots = capture(prior, REGISTRY, new_guest=False)
            prior_receipt = {"profile_snapshots": prior_snapshots,
                             "sandbox_id_sha256": "0" * 64}
            attempts = []
            for index, (label, kind) in enumerate(train.PLAN, start=1):
                directory = output / label
                snapshots = capture(directory, REGISTRY, new_guest=True)
                package_sha = train._source(kind)[0]["package_sha256"]
                (directory / "intent.json").write_text(json.dumps({
                    "schema": "cua-native-wdi-v066-train-profile-cross-guest-intent-v1",
                    "label": label, "kind": kind, "split": "train",
                    "package_sha256": package_sha,
                    "calibration_source_sha256": payload["calibration_source_sha256"],
                    "reservation_sha256": reservation_sha,
                    "lease_seconds": 600,
                    "automatic_replay_authorized": False}))
                receipt = {
                    "schema": train.RECEIPT_SCHEMA,
                    "purpose": "v066_public_train_profile_cross_guest_no_model",
                    "label": label, "kind": kind, "split": "train",
                    "status": "train_profile_captured",
                    "guest_content_attested": True,
                    "fresh_profile_absent": True,
                    "input_unchanged_after_open": True,
                    "actor_gui_actions": 0,
                    "official_final_model_attempts": 0,
                    "kill_returned": True,
                    "is_running_after_kill": False,
                    "calibration_source_sha256": payload["calibration_source_sha256"],
                    "scoped_analysis_source_sha256":
                        payload["scoped_analysis_source_sha256"],
                    "reservation_sha256": reservation_sha,
                    "package_sha256": package_sha,
                    "profile_snapshots": snapshots,
                    "neutral_open_screenshot_sha256": digest(frame),
                    "sandbox_id_sha256": f"{index:064x}"}
                (directory / "receipt.json").write_text(json.dumps(receipt))
                attempts.append({"status": "train_profile_captured"})
            (output / "run-receipt.json").write_text(json.dumps({
                "schema": "cua-native-wdi-v066-train-profile-cross-guest-run-v1",
                "status": "all_raw_train_profiles_captured_pending_audit",
                "reservation_sha256": reservation_sha,
                "attempts": attempts}))
            with patch.object(train, "_prior_calc",
                              return_value=(prior_receipt, b"prior", b"audit")):
                private, public = audit.audit(
                    output_root=output, prior_calc_dir=prior,
                    reservation_path=reservation)
            self.assertEqual(private["status"], "three_app_pairs_passed")
            self.assertEqual(public["same_app_cross_guest_pairs_passed"], 3)
            self.assertTrue(public[
                "setting_recovery_and_nonregistry_negatives_passed"])

            # One retained setting changed in both snapshots of a single
            # guest; within-guest stability remains, but Writer pair fails.
            changed_registry = REGISTRY.replace(
                b'ooSetupLastVersion"><value>7',
                b'ooSetupLastVersion"><value>8')
            second_writer = output / "writer-second"
            changed_snapshots = capture(
                second_writer, changed_registry, new_guest=True)
            receipt_path = second_writer / "receipt.json"
            receipt = json.loads(receipt_path.read_bytes())
            receipt["profile_snapshots"] = changed_snapshots
            receipt_path.write_text(json.dumps(receipt))
            with patch.object(train, "_prior_calc",
                              return_value=(prior_receipt, b"prior", b"audit")):
                private, public = audit.audit(
                    output_root=output, prior_calc_dir=prior,
                    reservation_path=reservation)
            self.assertEqual(private["status"],
                             "cross_guest_mismatch_retained_not_ratified")
            self.assertEqual(public["same_app_cross_guest_pairs_passed"], 2)
