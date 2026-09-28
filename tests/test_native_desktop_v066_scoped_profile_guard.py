"""Raw-first scoped Desktop profile guard keeps settings fail-closed."""

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
    v066_scoped_profile_final_attempt as final_attempt,
    v066_scoped_profile_reference as reference,
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


class FakeRun:
    exit_code = 0

    def __init__(self, rows):
        self.stdout = json.dumps(rows)


class FakeSandbox:
    def __init__(self, registry=REGISTRY, nonregistry_sha="a" * 64):
        self.registry = registry
        self.nonregistry_sha = nonregistry_sha
        self.files = self
        self.commands = self

    def write(self, _path, _raw):
        return None

    def read(self, _path, *, format):
        assert format == "bytes"
        return self.registry

    def run(self, _command):
        return FakeRun([{
            "path": "registrymodifications.xcu",
            "sha256": digest(self.registry), "bytes": len(self.registry)},
            {"path": "config/settings.bin",
             "sha256": self.nonregistry_sha, "bytes": 4}])

    def screenshot(self):
        output = io.BytesIO()
        Image.new("RGB", (1280, 800), "white").save(output, format="PNG")
        return output.getvalue()


class ScopedGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.reference = self.root / "train-reference.private.json"
        rows = json.loads(FakeSandbox().run("probe").stdout)
        expected = scope.scoped_profile(rows, REGISTRY)
        self.reference.write_text(json.dumps({
            "schema": "cua-native-wdi-v066-scoped-profile-reference-private-v1",
            "status": "frozen_public_train_profiles_before_final_attempts",
            "reference_builder_source_sha256": digest(
                Path(reference.__file__).read_bytes()),
            "profile_scope_source_sha256": digest(Path(scope.__file__).read_bytes()),
            "applications": {"calc": expected, "writer": expected,
                             "impress": expected},
            "distinct_public_train_guest_count": 6,
            "same_app_cross_guest_pairs_passed": 3,
            "negative_controls_passed": True,
            "official_final_admissions": 0,
            "official_model_results": 0}))
        self.reference.chmod(0o600)

    def check(self, sandbox, name):
        root = self.root / name
        out = root / "fake-task" / "positive"
        out.mkdir(parents=True)
        receipt = {}
        persisted = []
        def persist():
            persisted.append(len(receipt.get("task_profile_scoped_snapshots", [])))
        with patch.object(guard.time, "sleep"):
            try:
                result = guard.attest(
                    sandbox=sandbox, attempts_root=root, out=out,
                    app_kind="calc", reference_path=self.reference,
                    receipt=receipt, persist=persist)
                error = None
            except Exception as exc:
                result, error = None, exc
        return result, error, receipt, persisted, out

    def test_matching_public_train_reference_preserves_six_raw_files(self):
        result, error, receipt, persisted, out = self.check(
            FakeSandbox(), "positive")
        self.assertIsNone(error)
        self.assertEqual(result, receipt["task_profile_scoped_sha256"])
        self.assertTrue(receipt["task_profile_scoped_attested"])
        self.assertTrue(receipt["task_profile_attested"])
        self.assertEqual(len(receipt["task_profile_scoped_snapshots"]), 2)
        self.assertEqual(len(list(out.glob("profile-*"))), 6)
        self.assertIn(1, persisted)
        self.assertIn(2, persisted)

    def test_new_final_runner_cannot_reach_provider_without_new_freeze(self):
        with self.assertRaisesRegex(ValueError, "disabled before source freeze"):
            final_attempt.execute(
                candidate_root=self.root / "missing-candidates",
                attempts_root=self.root / "missing-attempts",
                task_id="private-final", attempt="positive",
                private_map=self.root / "missing-map",
                profile_private=self.root / "missing-profile",
                guest_public=self.root / "missing-guest",
                fair_public=self.root / "missing-fair",
                ratification=self.root / "missing-rat",
                reservation=self.root / "missing-reservation",
                scoped_reference=self.reference)

    def test_setting_recovery_and_nonregistry_drift_reject(self):
        variants = [
            FakeSandbox(REGISTRY.replace(
                b'ooSetupLastVersion"><value>7',
                b'ooSetupLastVersion"><value>8')),
            FakeSandbox(REGISTRY.replace(
                b'DocumentState"><value>1',
                b'DocumentState"><value>2')),
            FakeSandbox(REGISTRY, nonregistry_sha="b" * 64),
        ]
        for index, sandbox in enumerate(variants):
            with self.subTest(index=index):
                _result, error, receipt, _persisted, out = self.check(
                    sandbox, f"drift-{index}")
                self.assertIsInstance(error, guard.ScopedProfileDrift)
                self.assertFalse(receipt["task_profile_scoped_matches_public_train"])
                self.assertEqual(len(list(out.glob("profile-*"))), 6)
                self.assertNotIn("task_profile_attested", receipt)

    def test_normalization_error_still_retains_raw_first_capture(self):
        root = self.root / "invalid"
        out = root / "task" / "positive"
        out.mkdir(parents=True)
        snapshots = []
        persisted = []
        with patch.object(guard.scope, "scoped_profile",
                          side_effect=ValueError("synthetic scope failure")):
            with self.assertRaisesRegex(ValueError, "normalization failed"):
                guard._capture(
                    FakeSandbox(), attempts_root=root, out=out,
                    label="first", started=0,
                    snapshots=snapshots,
                    persist=lambda: persisted.append(len(snapshots)))
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(len(list(out.glob("profile-*"))), 3)
        self.assertEqual(persisted, [1, 1])
