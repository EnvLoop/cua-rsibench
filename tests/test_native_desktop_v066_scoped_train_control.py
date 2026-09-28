"""Fake E2B public-train positive, near-miss, and cold reset are separate."""

from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from native_desktop_factory import (
    runtime_fingerprint_probe,
    v066_scoped_profile_train_control as train,
)


class FakeSandbox:
    def __init__(self, baseline: bytes, guest: dict, image: bytes):
        self.sandbox_id = "fake-train-sandbox"
        self.baseline = baseline
        self.saved = baseline
        self.guest = guest
        self.image = image
        self.files = self
        self.commands = self

    def get_info(self, **_kwargs):
        return SimpleNamespace(template_id="desktop-id", cpu_count=2,
                               memory_mb=4096, envd_version="envd")

    def run(self, command, **_kwargs):
        if command.startswith("sudo -n python3"):
            return SimpleNamespace(exit_code=0, stdout=json.dumps({
                "content_tree_sha256": self.guest["static_content_sha256"],
                "counts": self.guest["static_content_counts"],
                "kernel": self.guest["kernel_identity"],
                "excluded_paths": self.guest["static_content_excluded_paths"]}))
        return SimpleNamespace(exit_code=0, stdout="")

    def write(self, _path, _raw):
        return None

    def read(self, path, *, format):
        assert format == "bytes"
        if path.startswith("/home/user/"):
            return self.saved
        raise AssertionError("Unexpected fake sandbox file read")

    def open(self, _path):
        return None

    def screenshot(self):
        return self.image

    def press(self, _key):
        return None

    def kill(self):
        return True

    def is_running(self, **_kwargs):
        return False


class ScopedTrainControlTests(unittest.TestCase):
    def test_public_positive_receipt_binds_source_and_does_not_claim_trio(self):
        root = Path(__file__).resolve().parents[1]
        public = json.loads((root / "docs/evidence" /
            "native-wdi-v066-scoped-profile-train-positive-2026-09-28.json"
            ).read_bytes())
        self.assertEqual(public["train_control_source_sha256"],
                         train.digest(Path(train.__file__).read_bytes()))
        self.assertFalse(public["near_miss_paid_control_run"])
        self.assertFalse(public["cold_reset_paid_control_run"])
        self.assertEqual(public["official_final_admissions"], 0)

    def test_fake_positive_near_miss_and_reset_have_expected_saved_verdicts(self):
        package, _oracle, baseline, _instruction, _filename = train._train_package()
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            work = root / "work"
            work.mkdir()
            reference = root / "reference.private.json"
            reference.write_text("{}")
            reference_sha = train.digest(reference.read_bytes())
            guest = {
                "schema": "cua-native-wdi-guest-content-identity-public-v1",
                "scoped_guest_content_identity_passed": True,
                "guest_content_probe_script_sha256": train.digest(
                    runtime_fingerprint_probe.GUEST_CONTENT_PROBE),
                "provider_template_id": "desktop-id",
                "provider_envd_version": "envd",
                "provider_shape": {"vcpu": 2, "memory_mb": 4096},
                "static_content_sha256": "a" * 64,
                "static_content_counts": {"regular_file": 1},
                "kernel_identity": "kernel",
                "static_content_excluded_paths": ["/etc/hosts"],
            }
            guest_path = root / "guest.json"
            guest_path.write_text(json.dumps(guest))
            reservation = root / "reserve.private.json"
            reservation.write_text(json.dumps({
                "schema": "cua-native-wdi-v066-scoped-profile-train-controls-reservation-v1",
                "status": "reserved_before_public_train_gui_control_creates",
                "train_control_source_sha256": train.digest(
                    Path(train.__file__).read_bytes()),
                "train_control_audit_source_sha256": train.digest(
                    Path(train.__file__).with_name(
                        "v066_scoped_profile_train_control_audit.py").read_bytes()),
                "profile_guard_source_sha256": train.digest(
                    Path(train.scoped_guard.__file__).read_bytes()),
                "action_adapter_sha256": train.digest(
                    Path(train.qwen_v066_adapter.__file__).read_bytes()),
                "scoped_reference_sha256": reference_sha,
                "public_train_package_sha256": package["package_sha256"],
                "guest_identity_public_sha256": train.digest(
                    guest_path.read_bytes()),
                "lease_seconds_each": 600,
                "maximum_new_attempts": 3,
                "diagnostic_cap_usd": "42",
                "past_conservative_reserved_usd": "41.33",
                "planned_three_full_lease_reserved_usd": "41.83",
                "official_final_admissions": 0}))
            image = io.BytesIO()
            Image.new("RGB", (1280, 800), "white").save(image, format="PNG")
            for attempt in ("positive", "near-miss", "cold-reset"):
                fake = FakeSandbox(baseline, guest, image.getvalue())
                output = work / "gui-diagnostics" / "scoped-train" / attempt

                def reserve(root, path, raw):
                    path.write_bytes(raw)
                    return {"private_path": str(path.relative_to(root)),
                            "sha256": train.digest(raw), "bytes": len(raw)}

                def observe(recorder, **kwargs):
                    return SimpleNamespace(
                        screenshot_bytes=recorder.screenshot(),
                        frame_id=f"step-{kwargs['step']}")

                def dispatch(_sandbox, action):
                    if action["type"] == "type":
                        fake.saved = b"changed public train pptx"
                    return action["type"]

                def fair(_baseline, _saved, _oracle):
                    return ({"passed": False,
                             "errors": ["target_text_wrong:slide3:shape2"]}
                            if attempt == "near-miss" else
                            {"passed": True, "errors": []})

                with (patch.dict(train.os.environ, {"E2B_API_KEY": "fake"}),
                      patch.object(train, "validate_reference",
                                   return_value=({"applications": {"impress": "x" * 64}},
                                                 reference_sha)),
                      patch.object(train, "budget_audit",
                                   return_value={"within_cap": True,
                                       "past_conservative_reserved_usd": "41.33",
                                       "combined_reserved_usd": "41.50"}),
                      patch.object(train, "active_hashes",
                                   return_value=(set(), 0)),
                      patch.object(train, "storage_audit",
                                   return_value={"dispatch_storage_ready": True}),
                      patch("e2b_desktop.Sandbox.create", return_value=fake),
                      patch.object(train, "wait_for_document_ready",
                                   return_value={}),
                      patch.object(train.scoped_guard, "attest",
                                   side_effect=lambda **kwargs:
                                       kwargs["receipt"].update({
                                           "task_profile_scoped_attested": True,
                                           "task_profile_attested": True})),
                      patch.object(train, "reserve_and_write",
                                   side_effect=reserve),
                      patch.object(train.qwen_v066_adapter, "observe",
                                   side_effect=observe),
                      patch.object(train.qwen_v066_adapter,
                                   "parse_current_action",
                                   side_effect=lambda raw, *_args:
                                       json.loads(raw)),
                      patch.object(train.qwen_v066_adapter, "dispatch",
                                   side_effect=dispatch),
                      patch.object(train, "verify", side_effect=fair),
                      patch.object(train.time, "sleep")):
                    result = train.execute(
                        output=output, work_root=work,
                        guest_identity_public=guest_path,
                        scoped_reference=reference,
                        diagnostic_reservation=reservation,
                        attempt=attempt, lease_seconds=600,
                        max_lane_reserved_usd=train.Decimal("42"))
                self.assertEqual(result["status"],
                    "cold_reset_observed" if attempt == "cold-reset" else
                    "train_scoped_control_passed")
                self.assertTrue(result["kill_returned"])
                self.assertFalse(result["is_running_after_kill"])
                self.assertEqual(len(result["steps"]),
                                 0 if attempt == "cold-reset" else 18)
                if attempt != "cold-reset":
                    self.assertEqual(result["train_saved_artifact_verifier"][
                        "passed"], attempt == "positive")
                else:
                    self.assertEqual(result["restored_state_sha256"],
                                     train.digest(baseline))
