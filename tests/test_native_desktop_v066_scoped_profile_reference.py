"""Only independently audited public train guests can freeze app references."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from native_desktop_factory import v066_scoped_profile_reference as reference


class ScopedReferenceTests(unittest.TestCase):
    def test_three_app_reference_is_source_bound_private_and_exclusive(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            reservation = root / "reserve.json"
            reservation.write_text("{}")
            saved = root / "audit.private.json"
            private = {
                "schema": "cua-native-wdi-v066-train-profile-calibration-audit-private-v1",
                "status": "three_app_pairs_passed",
                "reservation_sha256": "a" * 64,
                "run_journal_sha256": "b" * 64,
                "per_guest": [
                    {"label": "calc-second", "scoped_profile_sha256": "1" * 64},
                    {"label": "writer-first", "scoped_profile_sha256": "2" * 64},
                    {"label": "impress-first", "scoped_profile_sha256": "3" * 64}],
            }
            saved.write_text(json.dumps({**private,
                "provider_active_zero_after": True,
                "official_final_admissions": 0}))
            public = {"same_app_cross_guest_pairs_passed": 3,
                      "setting_recovery_and_nonregistry_negatives_passed": True}
            target = root / "reference.private.json"
            with patch.object(reference.train_audit, "audit",
                              return_value=(private, public)):
                result = reference.write(
                    output=target, calibration_root=root,
                    prior_calc_dir=root,
                    calibration_reservation=reservation,
                    preserved_calibration_audit=saved)
            value, sha = reference.validate_reference(target)
            self.assertEqual(result["private_reference_sha256"], sha)
            self.assertEqual(value["applications"], {
                "calc": "1" * 64, "writer": "2" * 64,
                "impress": "3" * 64})
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            with patch.object(reference.train_audit, "audit",
                              return_value=(private, public)):
                with self.assertRaisesRegex(ValueError, "new file"):
                    reference.write(
                        output=target, calibration_root=root,
                        prior_calc_dir=root,
                        calibration_reservation=reservation,
                        preserved_calibration_audit=saved)
            changed = json.loads(target.read_bytes())
            changed["reference_builder_source_sha256"] = "0" * 64
            target.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "source or scope changed"):
                reference.validate_reference(target)

    def test_workflow_kind_is_explicit_and_fails_unknown(self):
        self.assertEqual(reference.workflow_kind("calc-risk"), "calc")
        self.assertEqual(reference.workflow_kind("writer-brief"), "writer")
        self.assertEqual(reference.workflow_kind("impress-deck"), "impress")
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            reference.workflow_kind("unknown")
