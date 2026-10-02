"""Offline source and raw-manifest checks for the public Calc diagnostic."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch

from native_desktop_factory import v066_public_calc_profile_probe as probe
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


class PublicCalcProfileProbeTests(unittest.TestCase):
    def test_pinned_source_is_public_train_and_self_hashed(self):
        package, source, filename = probe.public_train_source()
        self.assertEqual(package["split"], "train")
        self.assertEqual(package["workflow"], "calc-growth")
        self.assertEqual(digest(source), package["input_sha256"])
        self.assertTrue(filename.endswith(".xlsx"))

    def test_final_relabel_is_rejected_before_any_provider_call(self):
        with tempfile.TemporaryDirectory() as scratch:
            copied = Path(scratch) / "source"
            shutil.copytree(probe.PUBLIC_CALC, copied)
            path = copied / "package.json"
            package = json.loads(path.read_bytes())
            package["split"] = "final_candidate"
            path.write_text(json.dumps(package))
            with patch.object(probe, "PUBLIC_CALC", copied):
                with self.assertRaisesRegex(ValueError, "public Calc train"):
                    probe.public_train_source()

    def test_raw_manifest_and_registry_are_reopened_and_canonicalized(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            first = probe._snapshot(FakeSandbox(REGISTRY), root,
                                    "first", time.monotonic())
            second_registry = REGISTRY.replace(b">123<", b">789<")
            second = probe._snapshot(FakeSandbox(second_registry), root,
                                     "second", time.monotonic())
            self.assertEqual(first["canonical_profile_sha256"],
                             second["canonical_profile_sha256"])
            self.assertNotEqual(first["registry_sha256"],
                                second["registry_sha256"])
            self.assertEqual(digest((root / "profile-first.registry.xml").read_bytes()),
                             first["registry_sha256"])
            self.assertEqual(digest((root / "profile-second.manifest.json").read_bytes()),
                             second["manifest_sha256"])
            with self.assertRaises(FileExistsError):
                probe._snapshot(FakeSandbox(REGISTRY), root,
                                "first", time.monotonic())
