"""Independent final verifier recomputes every scoped raw profile pair."""

from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from native_desktop_factory import (
    v066_profile_scope_analysis as scope,
    v066_scoped_profile_final_attempt as attempt,
    v066_scoped_profile_final_audit as audit,
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


class ScopedFinalAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.task_id = "fake-private-final"
        rows = [{"path": "registrymodifications.xcu",
                 "sha256": digest(REGISTRY), "bytes": len(REGISTRY)},
                {"path": "config/settings.bin",
                 "sha256": "a" * 64, "bytes": 4}]
        self.manifest = json.dumps(rows).encode()
        self.expected = scope.scoped_profile(rows, REGISTRY)
        image = io.BytesIO()
        Image.new("RGB", (1280, 800), "white").save(image, format="PNG")
        self.frame = image.getvalue()
        self.refsha, self.runtime_sha, self.bridgesha = (
            "1" * 64, "2" * 64, "3" * 64)
        for index, name in enumerate(audit.ATTEMPTS, start=4):
            path = self.root / self.task_id / name
            path.mkdir(parents=True)
            snapshots = []
            for label in ("first", "second"):
                records = {}
                for key, ext, raw in (("manifest", "manifest.json", self.manifest),
                                      ("registry", "registry.xml", REGISTRY),
                                      ("visible_frame", "png", self.frame)):
                    relative = f"{self.task_id}/{name}/profile-{label}.{ext}"
                    (self.root / relative).write_bytes(raw)
                    records[key] = {"private_path": relative,
                                    "sha256": digest(raw), "bytes": len(raw)}
                snapshots.append({
                    "label": label, **records,
                    "profile_probe_script_sha256": digest(
                        guard.runtime_fingerprint_probe.PROFILE_FILE_PROBE.encode()),
                    "scoped_profile_sha256": self.expected})
            (path / "intent.json").write_text(json.dumps({
                "scoped_reference_sha256": self.refsha,
                "scoped_runtime_freeze_sha256": self.runtime_sha,
                "three_root_bridge_sha256": self.bridgesha}))
            (path / "receipt.json").write_text(json.dumps({
                "runner_sha256": digest(Path(attempt.__file__).read_bytes()),
                "profile_scope_guard_source_sha256": digest(
                    Path(guard.__file__).read_bytes()),
                "native_adapter_sha256": digest(
                    Path(attempt.qwen_v066_adapter.__file__).read_bytes()),
                "profile_reference_private_sha256": self.refsha,
                "scoped_runtime_freeze_sha256": self.runtime_sha,
                "three_root_bridge_sha256": self.bridgesha,
                "profile_application_kind": "calc",
                "task_profile_scoped_attested": True,
                "task_profile_scoped_self_stable": True,
                "task_profile_scoped_matches_public_train": True,
                "task_profile_scoped_sha256": self.expected,
                "task_profile_scoped_snapshots": snapshots,
                "sandbox_id_sha256": f"{index:064x}"}))

    def validate(self):
        return audit._profile_receipt(
            candidate_root=self.root,
            attempts_root=self.root,
            task_id=self.task_id, workflow="calc-growth",
            reference={"applications": {"calc": self.expected}},
            reference_sha=self.refsha,
            runtime_sha=self.runtime_sha,
            bridge_sha=self.bridgesha)

    def test_three_raw_profile_pairs_are_independently_recomputed(self):
        self.assertEqual(len(self.validate()), 3)

    def test_registry_byte_or_setting_drift_rejects(self):
        path = (self.root / self.task_id / "near-miss" /
                "profile-second.registry.xml")
        path.write_bytes(REGISTRY.replace(
            b'DocumentState"><value>1',
            b'DocumentState"><value>2'))
        with self.assertRaisesRegex(ValueError, "evidence digest changed"):
            self.validate()
