"""Public train Calc/Writer scripts use v0.6.6 frames and saved OOXML."""

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
    v066_scoped_calc_writer_train_demo as demo,
)
from native_desktop_factory.v066_final_freeze import digest


class FakeSandbox:
    def __init__(self, baseline, guest, frame):
        self.sandbox_id = "fake-" + str(len(baseline))
        self.saved = baseline
        self.guest = guest
        self.frame = frame
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

    def read(self, _path, *, format):
        assert format == "bytes"
        return self.saved

    def open(self, _path):
        return None

    def screenshot(self):
        return self.frame

    def press(self, _key):
        return None

    def kill(self):
        return True

    def is_running(self, **_kwargs):
        return False


class CalcWriterTrainDemoTests(unittest.TestCase):
    def test_public_plan_binds_exact_sources_and_official_zero(self):
        root = Path(__file__).resolve().parents[1]
        public = json.loads((root / "docs/evidence" /
            "native-wdi-v066-calc-writer-train-demo-plan-2026-09-28.json"
            ).read_bytes())
        self.assertEqual(public["demo_runner_source_sha256"],
                         digest(Path(demo.__file__).read_bytes()))
        self.assertEqual(public["independent_demo_auditor_source_sha256"],
                         digest(Path(demo.__file__).with_name(
                             "v066_scoped_calc_writer_train_demo_audit.py").read_bytes()))
        self.assertFalse(public["earlier_sparse_receipts_reused_as_v066_sft"])
        self.assertEqual(public["official_final_admissions"], 0)

    def test_scripts_reconstruct_source_validated_public_train_text(self):
        _p, calc_oracle, _raw, _instruction, _filename = demo._source("calc")
        _p, writer_oracle, _raw, _instruction, _filename = demo._source("writer")
        calc = demo.actor_actions("calc", calc_oracle)
        writer = demo.actor_actions("writer", writer_oracle)
        self.assertEqual(len(calc), 12)
        self.assertEqual(len(writer), 8)
        calc_texts = [row["text"] for row in calc if row["type"] == "type"]
        self.assertEqual(calc_texts[0], "B4")
        self.assertEqual(digest(calc_texts[0].encode()),
                         "239fd09dd1c48679b74cec2120cd5e448b002c728c05e9b10f2c19f298fbdd57")
        self.assertEqual(digest(calc_texts[1].encode()),
                         "149d0ad4965eb9054099772ae4f0a69b7d7ccc028e9d114fc15b4a2c8d289463")
        writer_text = next(row["text"] for row in writer
                           if row["type"] == "type")
        self.assertEqual(digest(writer_text.encode()),
                         "ed02d2b890094b94e0e9d4c3614258b2f7e029c6f0eac22e7aef0a0f936bc530")
        self.assertIn({"type": "key", "key": "Shift+End"}, writer)

    def test_fake_calc_then_writer_positive_retains_normalized_actions(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            work = root / "work"
            work.mkdir()
            output = work / "gui-diagnostics" / "demos"
            reference = root / "reference.private.json"
            reference.write_text("{}")
            guest = {
                "schema": "cua-native-wdi-guest-content-identity-public-v1",
                "scoped_guest_content_identity_passed": True,
                "guest_content_probe_script_sha256": digest(
                    runtime_fingerprint_probe.GUEST_CONTENT_PROBE.encode()),
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
            frame = io.BytesIO()
            Image.new("RGB", (1280, 800), "white").save(frame, format="PNG")
            budget = {"within_cap": True,
                      "past_conservative_reserved_usd": "41.83",
                      "combined_reserved_usd": "42.16111111111111111111111111"}
            for kind in demo.KINDS:
                package, _oracle, baseline, _instruction, _filename = demo._source(kind)
                fake = FakeSandbox(baseline, guest, frame.getvalue())

                def reserve(root, path, raw):
                    path.write_bytes(raw)
                    return {"private_path": str(path.relative_to(root)),
                            "sha256": digest(raw), "bytes": len(raw)}

                def observe(recorder, **kwargs):
                    return SimpleNamespace(
                        screenshot_bytes=recorder.screenshot(),
                        frame_id=f"step-{kwargs['step']}")

                def dispatch(_sandbox, action):
                    if action["type"] == "type":
                        fake.saved = b"changed " + kind.encode()
                    return action["type"]

                with (patch.dict(demo.os.environ, {"E2B_API_KEY": "fake"}),
                      patch.object(demo, "validate_reference",
                                   return_value=(
                                       {"applications": {"calc": "c" * 64,
                                                         "writer": "w" * 64}},
                                       digest(reference.read_bytes()))),
                      patch.object(demo, "budget_audit", return_value=budget),
                      patch.object(demo, "active_hashes",
                                   return_value=(set(), 0)),
                      patch.object(demo, "storage_audit",
                                   return_value={"dispatch_storage_ready": True}),
                      patch("e2b_desktop.Sandbox.create", return_value=fake),
                      patch.object(demo, "wait_for_document_ready",
                                   return_value={}),
                      patch.object(demo.scoped_guard, "attest",
                                   side_effect=lambda **kwargs:
                                       kwargs["receipt"].update({
                                           "task_profile_scoped_attested": True,
                                           "task_profile_attested": True})),
                      patch.object(demo, "reserve_and_write",
                                   side_effect=reserve),
                      patch.object(demo.qwen_v066_adapter, "observe",
                                   side_effect=observe),
                      patch.object(demo.qwen_v066_adapter,
                                   "parse_current_action",
                                   side_effect=lambda raw, *_args:
                                       json.loads(raw)),
                      patch.object(demo.qwen_v066_adapter, "dispatch",
                                   side_effect=dispatch),
                      patch.object(demo, "verify",
                                   return_value={"passed": True, "errors": []}),
                      patch.object(demo.time, "sleep"),
                      patch.object(demo, "_validate_reservation",
                                   return_value="r" * 64)):
                    result = demo.run_one(
                        kind=kind, output_root=output,
                        work_root=work, guest_public=guest_path,
                        scoped_reference=reference,
                        reservation_path=root / "reservation.json")
                self.assertEqual(result["status"], "train_gui_positive_passed")
                self.assertEqual(result["actor_gui_actions"],
                                 12 if kind == "calc" else 8)
                self.assertEqual(len(result["normalized_actor_actions"]),
                                 result["actor_gui_actions"])
                self.assertTrue(result["independent_saved_verifier"]["passed"])
                self.assertFalse(result["is_running_after_kill"])
