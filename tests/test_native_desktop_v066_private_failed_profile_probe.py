"""Offline guard and raw-before-canonical tests for one failed final ID."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from native_desktop_factory import v066_private_failed_profile_probe as probe
from native_desktop_factory.v066_final_freeze import digest


REGISTRY = (b'<?xml version="1.0"?><items>'
            b'<prop oor:name="LastTimeDonateShown"><value>123</value></prop>'
            b'<prop oor:name="LastTimeGetInvolvedShown"><value>456</value></prop>'
            b'</items>')


class FakeCommand:
    exit_code = 0

    def __init__(self, raw: bytes):
        self.stdout = raw.decode()


class FakeSandbox:
    def __init__(self, raw: bytes):
        self.raw = raw
        self.commands = self
        self.files = self

    def run(self, _command):
        return FakeCommand(json.dumps([{
            "path": "registrymodifications.xcu",
            "sha256": digest(self.raw),
            "bytes": len(self.raw),
        }]).encode())

    def read(self, _path, *, format):
        assert format == "bytes"
        return self.raw


class FailedFinalProfileProbeTests(unittest.TestCase):
    def test_raw_bytes_survive_canonicalization_failure(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            with patch.object(probe.profile_canonical,
                              "canonical_profile_tree",
                              side_effect=ValueError("synthetic canonical failure")):
                result = probe._snapshot(FakeSandbox(REGISTRY), root,
                                         "first", time.monotonic())
            self.assertIsNone(result["canonical_profile_sha256"])
            self.assertEqual(result["canonical_error_type"], "ValueError")
            self.assertEqual(
                digest((root / "profile-first.registry.xml").read_bytes()),
                result["registry_sha256"])
            self.assertEqual(
                digest((root / "profile-first.manifest.json").read_bytes()),
                result["manifest_sha256"])

    def test_only_one_of_exact_two_preserved_failed_ids_is_selectable(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            for number in (1, 2):
                task_id = f"fake-private-final-{number}"
                path = root / task_id / "positive"
                path.mkdir(parents=True)
                (path / "intent.json").write_text(json.dumps({
                    "task_id": task_id, "attempt": "positive",
                    "package_sha256": "a" * 64}))
                (path / "receipt.json").write_text(json.dumps({
                    "task_id": task_id, "attempt": "positive",
                    "package_sha256": "a" * 64,
                    "status": "control_failed_or_infrastructure_invalid",
                    "stage": "guest_content_attestation",
                    "error_type": "ValueError",
                    "guest_content_attested": True,
                    "fresh_profile_absent": True,
                    "task_profile_attested": None,
                    "actor_steps": [],
                    "kill_returned": True,
                    "is_running_after_kill": False,
                    "sandbox_id_sha256": f"{number:064x}"}))
            selected, _ = probe._failed_pair(root, "fake-private-final-1")
            self.assertEqual(selected["task_id"], "fake-private-final-1")
            with self.assertRaisesRegex(ValueError, "Only one of two"):
                probe._failed_pair(root, "unrelated-final")
            (root / "fake-private-final-2/positive/intent.json").unlink()
            with self.assertRaises(FileNotFoundError):
                probe._failed_pair(root, "fake-private-final-1")
