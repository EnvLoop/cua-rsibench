"""Calc/Writer SFT sources require raw current frames and saved-file proof."""

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
    v066_scoped_calc_writer_train_demo as demo,
    v066_scoped_calc_writer_train_demo_audit as audit,
    v066_scoped_profile_guard as guard,
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


class CalcWriterDemoAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / "demos"
        self.output.mkdir()
        self.ref = self.root / "ref.json"
        self.ref.write_text("{}")
        self.guest = self.root / "guest.json"
        self.guest.write_text("{}")
        self.res = self.root / "res.json"
        self.res.write_text("{}")
        rows = [{"path": "registrymodifications.xcu",
                 "sha256": digest(REGISTRY), "bytes": len(REGISTRY)},
                {"path": "config/settings.bin",
                 "sha256": "a" * 64, "bytes": 4}]
        self.manifest = json.dumps(rows).encode()
        self.fingerprint = scope.scoped_profile(rows, REGISTRY)
        image = io.BytesIO()
        Image.new("RGB", (1280, 800), "white").save(image, format="PNG")
        self.frame = image.getvalue()
        for index, kind in enumerate(demo.KINDS, start=1):
            self.make(kind, index)
        (self.output / "run-receipt.json").write_text(json.dumps({
            "schema": "cua-native-wdi-v066-calc-writer-train-demo-run-v1",
            "status": "two_public_train_gui_positives_pending_audit",
            "reservation_sha256": digest(self.res.read_bytes()),
            "attempts": [{"status": "train_gui_positive_passed"}] * 2}))

    def bound(self, path: Path, raw: bytes):
        path.write_bytes(raw)
        return {"private_path": str(path.relative_to(self.output)),
                "sha256": digest(raw), "bytes": len(raw)}

    def make(self, kind, index):
        package, oracle, baseline, _instruction, _filename = demo._source(kind)
        path = self.output / kind
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
            "schema": "cua-native-wdi-v066-calc-writer-train-demo-intent-v1",
            "kind": kind, "split": "train",
            "package_sha256": package["package_sha256"],
            "demo_source_sha256": digest(Path(demo.__file__).read_bytes()),
            "scoped_reference_sha256": digest(self.ref.read_bytes()),
            "reservation_sha256": digest(self.res.read_bytes()),
            "automatic_replay_authorized": False}))
        saved = b"changed-" + kind.encode()
        actions = []
        for step, action in enumerate(demo.actor_actions(kind, oracle)):
            actions.append({
                "step": step, "status": "applied",
                "normalized_action": action,
                "dispatch_type": action["type"],
                "normalized_action_sha256": digest(json.dumps(
                    action, sort_keys=True,
                    separators=(",", ":")).encode()),
                "script_payload_sha256": digest(json.dumps(
                    action, separators=(",", ":")).encode()),
                "observation": self.bound(
                    path / f"frame-{step:02d}.png", self.frame),
                "predispatch": self.bound(
                    path / f"predispatch-{step:02d}.png", self.frame)})
        receipt = {
            "schema": "cua-native-wdi-gui-development-attempt-v1",
            "purpose": "v066_scoped_public_train_calc_writer_gui_positive_no_model",
            "kind": kind, "split": "train",
            "status": "train_gui_positive_passed",
            "package_sha256": package["package_sha256"],
            "input_sha256": digest(baseline),
            "demo_source_sha256": digest(Path(demo.__file__).read_bytes()),
            "action_adapter_sha256": digest(
                Path(demo.qwen_v066_adapter.__file__).read_bytes()),
            "profile_guard_source_sha256": digest(Path(guard.__file__).read_bytes()),
            "scoped_reference_sha256": digest(self.ref.read_bytes()),
            "reservation_sha256": digest(self.res.read_bytes()),
            "guest_identity_public_sha256": digest(self.guest.read_bytes()),
            "guest_content_attested": True,
            "task_profile_scoped_attested": True,
            "kill_returned": True,
            "is_running_after_kill": False,
            "official_final_model_attempts": 0,
            "official_final_admissions": 0,
            "task_profile_scoped_snapshots": snapshots,
            "normalized_actor_actions": actions,
            "actor_gui_actions": len(actions),
            "saved_artifact": self.bound(path / ("saved.xlsx" if kind == "calc"
                                              else "saved.docx"), saved),
            "saved_sha256": digest(saved),
            "independent_saved_verifier": {"passed": True, "errors": []},
            "sandbox_id_sha256": f"{index:064x}"}
        (path / "receipt.json").write_text(json.dumps(receipt))

    def test_both_public_workflows_and_tampered_frame(self):
        with (patch.object(audit, "validate_reference", return_value=(
                {"applications": {"calc": self.fingerprint,
                                  "writer": self.fingerprint}},
                digest(self.ref.read_bytes()))),
              patch.object(audit, "verify",
                           return_value={"passed": True, "errors": []})):
            _private, public = audit.audit_both(
                output_root=self.output, scoped_reference=self.ref,
                guest_public=self.guest, reservation_path=self.res)
            self.assertEqual(public["distinct_public_train_workflows"], 2)
            self.assertEqual(public["current_frame_actions_total"], 20)
            self.assertTrue(public[
                "actor_saved_xlsx_and_docx_independently_verified"])
            (self.output / "writer/frame-00.png").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "evidence digest changed"):
                audit.audit_both(
                    output_root=self.output, scoped_reference=self.ref,
                    guest_public=self.guest, reservation_path=self.res)
