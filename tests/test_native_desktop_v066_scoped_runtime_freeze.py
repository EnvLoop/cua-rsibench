"""Desktop scoped runtime source freeze is distinct from action ratification."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from native_desktop_factory import v066_scoped_profile_runtime_freeze as freeze
from native_desktop_factory.v066_final_freeze import digest


class ScopedRuntimeFreezeTests(unittest.TestCase):
    def test_source_hashes_cover_new_runner_guard_bridge_audit_and_old_bytes(self):
        hashes = freeze.source_hashes()
        self.assertEqual(len(hashes), len(freeze.SOURCE_FILES))
        for key in ("v066_scoped_profile_guard.py",
                    "v066_scoped_profile_final_attempt.py",
                    "v066_scoped_profile_final_controller.py",
                    "v066_scoped_profile_final_audit.py",
                    "v066_scoped_profile_bridge.py",
                    "v066_final_control_attempt.py",
                    "qwen_v066_adapter.py"):
            self.assertTrue(any(path.endswith(key) for path in hashes))
        self.assertEqual(hashes[
            "native_desktop_factory/v066_final_control_attempt.py"],
            "2c2911b5f50a36a7960feb653c58fc355794edd6b8c13710fac30222308764be")
        self.assertEqual(hashes[
            "native_desktop_factory/qwen_v066_adapter.py"],
            "628f3f5383f265ecb781386d0a7ac5ab335d56238f9dec5c375f73c7baefb480")

    def test_private_freeze_requires_calibration_and_exact_current_source(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            action = root / "action.private.json"
            action.write_text("{}")
            reference = root / "reference.private.json"
            reference.write_text("{}")
            private_audit = root / "train-audit.private.json"
            private_audit.write_text(json.dumps({
                "schema": "cua-native-wdi-v066-train-profile-calibration-audit-private-v1",
                "status": "three_app_pairs_passed",
                "provider_active_zero_after": True,
                "official_final_admissions": 0}))
            public = root / "train-public.json"
            public.write_text(json.dumps({
                "schema": "cua-native-wdi-v066-train-profile-cross-guest-public-v1",
                "status": "three_public_train_application_pairs_passed_not_final_admission",
                "same_application_cross_guest_pairs_passed": 3,
                "private_independent_audit_sha256": digest(private_audit.read_bytes()),
                "official_final_admissions": 0}))
            private_freeze = root / "runtime.private.json"
            public_freeze = root / "runtime-public.json"
            with (patch.object(freeze, "validate_ratification",
                               return_value=({}, "a" * 64)),
                  patch.object(freeze, "validate_reference",
                               return_value=({}, "b" * 64))):
                aggregate = freeze.write(
                    private_path=private_freeze,
                    public_path=public_freeze,
                    action_ratification=action,
                    public_calibration=public,
                    private_calibration_audit=private_audit,
                    scoped_reference=reference)
                _value, sha = freeze.validate(
                    path=private_freeze,
                    action_ratification=action,
                    public_calibration=public,
                    private_calibration_audit=private_audit,
                    scoped_reference=reference)
                self.assertEqual(aggregate["private_runtime_freeze_sha256"], sha)
                self.assertEqual(private_freeze.stat().st_mode & 0o777, 0o600)
                changed = json.loads(private_freeze.read_bytes())
                changed["source_sha256s"][
                    "native_desktop_factory/v066_scoped_profile_guard.py"] = "0" * 64
                private_freeze.write_text(json.dumps(changed))
                with self.assertRaisesRegex(ValueError, "source bytes"):
                    freeze.validate(
                        path=private_freeze,
                        action_ratification=action,
                        public_calibration=public,
                        private_calibration_audit=private_audit,
                        scoped_reference=reference)
