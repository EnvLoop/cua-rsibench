"""Independent train trio reopens GUI frames, profile bytes, and saved PPTX."""

from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from native_desktop_factory import (
    v066_profile_scope_analysis as scope,
    v066_scoped_profile_guard as guard,
    v066_scoped_profile_train_control as train,
    v066_scoped_profile_train_control_audit as audit,
)
from native_desktop_factory.v066_final_freeze import digest


REGISTRY = (b'<?xml version="1.0"?><items '
            b'xmlns:oor="http://openoffice.org/2001/registry">'
            b'<item oor:path="/org.openoffice.Office.Histories/Histories/'
            b'org.openoffice.Office.Histories:HistoryInfo[\'PickList\']/ItemList">'
            b'<node oor:name="one"/></item>'
            b'<item oor:path="/org.openoffice.Office.Histories/Histories/'
            b'org.openoffice.Office.Histories:HistoryInfo[\'PickList\']/OrderList">'
            b'<node oor:name="0"/></item>'
            b'<item oor:path="/org.openoffice.Office.Recovery/RecoveryList">'
            b'<node oor:name="recovery_item_1"><prop oor:name="DocumentState">'
            b'<value>1</value></prop></node></item>'
            b'<item oor:path="/org.openoffice.Setup/Product">'
            b'<prop oor:name="LastTimeDonateShown"><value>123</value></prop>'
            b'<prop oor:name="LastTimeGetInvolvedShown"><value>456</value></prop>'
            b'<prop oor:name="ooSetupLastVersion"><value>7</value></prop>'
            b'</item></items>')


class ScopedTrainAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.guest = self.root / "guest.json"
        self.guest.write_text("{}")
        self.reference = self.root / "reference.json"
        self.reference.write_text("{}")
        self.reservation = self.root / "reservation.json"
        self.reservation.write_text("{}")
        self.package, self.oracle, self.baseline, _instruction, _file = (
            train._train_package())
        rows = [{"path": "registrymodifications.xcu",
                 "sha256": digest(REGISTRY), "bytes": len(REGISTRY)},
                {"path": "config/settings.bin", "sha256": "a" * 64,
                 "bytes": 4}]
        self.manifest = json.dumps(rows).encode()
        self.profile = scope.scoped_profile(rows, REGISTRY)
        output = io.BytesIO()
        Image.new("RGB", (1280, 800), "white").save(output, format="PNG")
        self.frame = output.getvalue()
        self.controls = self.root / "controls"
        self.controls.mkdir()
        for index, attempt in enumerate(audit.ATTEMPTS, start=1):
            self.make_attempt(attempt, index)

    def bound(self, path: Path, raw: bytes) -> dict:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return {"private_path": str(path.relative_to(self.controls)),
                "sha256": digest(raw), "bytes": len(raw)}

    def make_attempt(self, attempt: str, index: int):
        path = self.controls / attempt
        path.mkdir()
        snapshots = []
        for label in ("first", "second"):
            snapshots.append({
                "label": label,
                "manifest": self.bound(
                    path / f"profile-{label}.manifest.json", self.manifest),
                "registry": self.bound(
                    path / f"profile-{label}.registry.xml", REGISTRY),
                "visible_frame": self.bound(
                    path / f"profile-{label}.png", self.frame)})
        (path / "intent.json").write_text(json.dumps({
            "schema": "cua-native-wdi-v066-scoped-profile-train-control-intent-v1",
            "attempt": attempt, "split": "train",
            "package_sha256": self.package["package_sha256"],
            "runner_sha256": digest(Path(train.__file__).read_bytes()),
            "profile_reference_sha256": digest(self.reference.read_bytes()),
            "diagnostic_reservation_sha256": digest(
                self.reservation.read_bytes()),
            "automatic_replay_authorized": False}))
        receipt = {
            "schema": "cua-native-wdi-gui-development-attempt-v1",
            "purpose": "v066_scoped_profile_public_train_gui_control_no_model",
            "status": "cold_reset_observed" if attempt == "cold-reset" else
                      "train_scoped_control_passed",
            "split": "train", "attempt": attempt,
            "package_sha256": self.package["package_sha256"],
            "input_sha256": digest(self.baseline),
            "runner_sha256": digest(Path(train.__file__).read_bytes()),
            "v066_native_adapter_sha256": digest(
                Path(train.qwen_v066_adapter.__file__).read_bytes()),
            "profile_scope_guard_source_sha256": digest(
                Path(guard.__file__).read_bytes()),
            "profile_reference_private_sha256": digest(
                self.reference.read_bytes()),
            "expected_guest_identity_public_sha256": digest(
                self.guest.read_bytes()),
            "guest_content_attested": True,
            "task_profile_scoped_attested": True,
            "kill_returned": True,
            "is_running_after_kill": False,
            "official_final_model_attempts": 0,
            "official_final_admissions": 0,
            "sandbox_id_sha256": f"{index:064x}",
            "task_profile_scoped_snapshots": snapshots,
            "steps": [],
        }
        if attempt == "cold-reset":
            receipt["restored_state_sha256"] = digest(self.baseline)
            receipt["cold_observation"] = self.bound(
                path / "cold-observation.png", self.frame)
        else:
            replacement = (next(iter(self.oracle["targets"].values()))
                           if attempt == "positive" else
                           "INTENTIONALLY_WRONG_TRAIN_SIGNAL")
            for step, action in enumerate(train._script(replacement)):
                receipt["steps"].append({
                    "step": step, "status": "applied",
                    "action_type": action["type"],
                    "dispatch_type": action["type"],
                    "action_payload_sha256": digest(json.dumps(
                        action, separators=(",", ":")).encode()),
                    "observation": self.bound(
                        path / f"frame-{step:02d}.png", self.frame),
                    "predispatch": self.bound(
                        path / f"predispatch-{step:02d}.png", self.frame)})
            saved = b"positive changed pptx" if attempt == "positive" else b"wrong changed pptx"
            receipt["saved_artifact"] = self.bound(path / "saved.pptx", saved)
            receipt["train_saved_artifact_verifier"] = (
                {"passed": True, "errors": []} if attempt == "positive"
                else {"passed": False,
                      "errors": ["target_text_wrong:slide3:shape2"]})
        (path / "receipt.json").write_text(json.dumps(receipt))

    def test_positive_near_and_reset_reopen_independent_bytes(self):
        def fair(_baseline, saved, _oracle):
            return ({"passed": True, "errors": []}
                    if saved == b"positive changed pptx" else
                    {"passed": False,
                     "errors": ["target_text_wrong:slide3:shape2"]})
        with (patch.object(audit, "validate_reference",
                           return_value=({"applications": {"impress": self.profile}},
                                         digest(self.reference.read_bytes()))),
              patch.object(audit, "verify", side_effect=fair)):
            _private, public = audit.audit_trio(
                output_root=self.controls,
                scoped_reference=self.reference,
                guest_public=self.guest,
                diagnostic_reservation=self.reservation)
            self.assertEqual(public["distinct_train_guests"], 3)
            self.assertEqual(public["official_final_admissions"], 0)
            changed = self.controls / "near-miss/frame-00.png"
            changed.write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "evidence digest changed"):
                audit.audit_trio(
                    output_root=self.controls,
                    scoped_reference=self.reference,
                    guest_public=self.guest,
                    diagnostic_reservation=self.reservation)
