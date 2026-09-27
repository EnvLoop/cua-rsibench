"""Exercise real Desktop guest setup against a local fake SDK surface."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from native_desktop_factory import admit
from native_desktop_factory.teacher_episode_worker_v066 import (
    RealDesktopGuest, _semantic_input,
)
from native_desktop_factory.v066_final_freeze import digest


ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "work/native-desktop/candidates-v2-distinct-d"
GUEST = json.loads((ROOT / "docs/evidence/"
                    "native-wdi-guest-content-identity-2026-09-27.json").read_bytes())
REGISTRY = (b'<?xml version="1.0"?><root>'
            b'<prop oor:name="LastTimeDonateShown"><value>123</value></prop>'
            b'<prop oor:name="LastTimeGetInvolvedShown"><value>456</value></prop>'
            b'</root>')


class FakeFiles:
    def __init__(self):
        self.data = {}

    def write(self, path, raw):
        self.data[path] = bytes(raw)

    def read(self, path, format="bytes"):
        if path.endswith("registrymodifications.xcu"):
            return REGISTRY
        return self.data[path]


class FakeCommands:
    def __init__(self, sandbox):
        self.sandbox = sandbox

    def run(self, command, **_kwargs):
        if command.startswith("sudo -n python3 /tmp/native-guest-content"):
            return SimpleNamespace(exit_code=0, stdout=json.dumps({
                "content_tree_sha256": GUEST["static_content_sha256"],
                "counts": GUEST["static_content_counts"],
                "kernel": GUEST["kernel_identity"],
                "excluded_paths": GUEST["static_content_excluded_paths"],
            }))
        if command.startswith("test ! -e "):
            return SimpleNamespace(exit_code=0, stdout="")
        if command.startswith("python3 /tmp/native-profile-file-probe"):
            return SimpleNamespace(exit_code=0, stdout=json.dumps([
                {"path": "registrymodifications.xcu",
                 "sha256": digest(REGISTRY)}]))
        if command.startswith("xdotool getactivewindow"):
            return SimpleNamespace(exit_code=0,
                                   stdout=self.sandbox.filename +
                                   " - LibreOffice")
        raise AssertionError("Unexpected trusted guest command")


class FakeDesktopSDK:
    def __init__(self, workflow, filename):
        self.sandbox_id = "fake-guest-" + workflow
        self.workflow = workflow
        self.filename = filename
        self.files = FakeFiles()
        self.commands = FakeCommands(self)

    def get_info(self, request_timeout=12):
        assert request_timeout == 12
        return SimpleNamespace(
            template_id=GUEST["provider_template_id"],
            envd_version=GUEST["provider_envd_version"],
            cpu_count=GUEST["provider_shape"]["vcpu"],
            memory_mb=GUEST["provider_shape"]["memory_mb"])

    def open(self, remote):
        assert remote.endswith(self.filename)

    def press(self, key):
        if key == ["ctrl", "s"] and self.workflow == "impress-deck":
            remote = "/home/user/" + self.filename
            self.files.data[remote] = (
                ROOT / "native_desktop_factory/dev-fixtures/"
                "wdi-native-mex-impress-deck-normalized/"
                "wdi-native-mex-impress-deck-normalized.pptx").read_bytes()

    def screenshot(self):
        return b"not-used-in-setup"


@unittest.skipUnless((CANDIDATES / "candidate-inventory.json").is_file(),
                     "evaluator-private Desktop corpus is not in this checkout")
class RealGuestFakeSDKTests(unittest.TestCase):
    def test_actor_and_reset_setup_attest_real_source_shapes(self):
        inventory = json.loads((CANDIDATES / "candidate-inventory.json").read_bytes())
        for workflow in ("calc-growth", "impress-deck", "writer-brief"):
            row = next(item for item in inventory["tasks"]
                       if item["split"] == "train" and
                       item["workflow"] == workflow and
                       "mex" in item["task_id"])
            directory, source, oracle = admit._package(CANDIDATES, row)
            file = next(path for path in directory.iterdir()
                        if path.suffix in (".xlsx", ".pptx", ".docx"))
            actor = RealDesktopGuest(FakeDesktopSDK(workflow, file.name),
                                     phase="actor")
            reset = RealDesktopGuest(FakeDesktopSDK(workflow, file.name),
                                     phase="reset")
            with self.subTest(workflow=workflow), patch(
                    "native_desktop_factory.teacher_episode_worker_v066."
                    "wait_for_document_ready", return_value={"ready": True}), patch(
                    "native_desktop_factory.teacher_episode_worker_v066.time.sleep"):
                for guest in (actor, reset):
                    guest.prepare(source=source, filename=file.name,
                                  oracle=oracle, guest_identity=GUEST)
                    self.assertTrue(guest.provider_shape_attested)
                    self.assertTrue(guest.fresh_profile_absent)
                    self.assertEqual(guest.guest_content_sha256,
                                     GUEST["static_content_sha256"])
                    self.assertEqual(_semantic_input(guest.neutral_input, file.suffix),
                                     _semantic_input(source, file.suffix))
                self.assertEqual(actor.profile_sha256, reset.profile_sha256)
                self.assertEqual(actor.neutral_input, reset.neutral_input)
                if workflow == "impress-deck":
                    self.assertNotEqual(actor.neutral_input, source)


if __name__ == "__main__":
    unittest.main()
