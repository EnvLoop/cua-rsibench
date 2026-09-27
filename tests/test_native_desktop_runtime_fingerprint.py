"""Runtime fingerprints never substitute for a missing image/profile freeze."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from native_desktop_factory.publish_runtime_fingerprint import aggregate


class RuntimeFingerprintTests(unittest.TestCase):
    def test_two_stable_guests_with_profile_drift_stay_unadmitted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for batch in ("batch-001", "batch-002"):
                receipt = root / "final-v2-normalization" / batch / "batch-receipt.json"
                receipt.parent.mkdir(parents=True)
                receipt.write_text(json.dumps({
                    "schema": "cua-native-impress-batch-normalization-v1",
                    "status": "finished", "lease_seconds": 120,
                    "sandbox_id_sha256": batch,
                }))
            paths = []
            for index in (1, 2):
                path = root / "gui-diagnostics" / f"runtime-fingerprint-0{index}" / "receipt.json"
                path.parent.mkdir(parents=True)
                core = {
                    "font_tree": {"exists": True, "files": 2, "sha256": "fonts"},
                    "libreoffice_profile_tree": {"exists": False, "files": 0, "sha256": "empty"},
                    "os_release_sha256": "os", "libreoffice_executable_sha256": "office",
                    "libreoffice_version": "LibreOffice 7.3.7.2",
                    "package_manifest_sha256": "packages", "package_count": 3,
                    "fontconfig_catalog_sha256": "fc", "fontconfig_entry_count": 2,
                }
                opened = core | {"libreoffice_profile_tree": {
                    "exists": True, "files": 27, "sha256": f"profile-{index}"}}
                path.write_text(json.dumps({
                    "schema": "cua-native-wdi-runtime-fingerprint-v1",
                    "status": "fingerprinted_and_terminated", "lease_seconds": 180,
                    "sandbox_id_sha256": f"sandbox-{index}",
                    "is_running_after_kill": False,
                    "provider_sandbox_info": {
                        "template_id": "k0wmnzir0zuzye6dndlw", "envd_version": "0.9.0",
                        "vcpu": 8, "memory_mb": 8192,
                    },
                    "fresh_guest": core, "after_neutral_open": opened,
                    "guest_probe_script_sha256": "script", "sdk_version": "2.2.0",
                    "fixture_sha256": "fixture",
                    "budget_before": {"proposed_reserved_usd": "0.05"},
                }))
                paths.append(path)
            with patch("native_desktop_factory.publish_runtime_fingerprint.importlib.metadata.version",
                       return_value="2.51.0"):
                report = aggregate(paths, root)
            self.assertEqual(report["distinct_sandboxes"], 2)
            self.assertTrue(report["after_open_agreement"]["font_tree"])
            self.assertFalse(report["after_open_agreement"]["libreoffice_profile_tree"])
            self.assertFalse(report["image_and_profile_freeze_gate_passed"])
            self.assertEqual(report["full_study_official_desktop_admissions"], 0)


if __name__ == "__main__":
    unittest.main()
