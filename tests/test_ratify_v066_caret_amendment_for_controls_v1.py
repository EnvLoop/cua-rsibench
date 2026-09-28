"""Prospective six-cell caret source freeze is distinct from historical v0.6.6."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from native_desktop_factory.v066_final_freeze import validate_ratification
from tools import ratify_v066_caret_amendment_for_controls_v1 as ratify


class CaretAmendmentRatificationTests(unittest.TestCase):
    def test_all_six_sources_bind_and_no_result_authority(self):
        private, public = ratify.build()
        old = json.loads(ratify.OLD_PUBLIC.read_bytes())
        self.assertEqual(len(private["cell_profiles"]), 6)
        self.assertNotEqual(
            private["cell_profiles"]["desktop-native"]["adapter_sha256"],
            old["cell_adapter_sha256s"]["desktop-native"])
        for cell, sha in old["cell_adapter_sha256s"].items():
            if cell != "desktop-native":
                self.assertEqual(
                    private["cell_profiles"][cell]["adapter_sha256"], sha)
        self.assertEqual(public["qualified_final_tasks"], 0)
        self.assertEqual(public["official_final_model_results"], 0)
        self.assertFalse(public["six_cell_live_smokes_complete"])

    def test_changed_amendment_source_refuses_before_write(self):
        amendment = json.loads(ratify.AMENDMENT.read_bytes())
        amendment["proposed_new_adapter_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as scratch:
            altered = Path(scratch) / "amendment.json"
            altered.write_text(json.dumps(amendment))
            with patch.object(ratify, "AMENDMENT", altered):
                with self.assertRaisesRegex(
                        ValueError, "six_cell_adapter_source_changed"):
                    ratify.build()

    def test_new_private_and_public_record_validate_without_old_overwrite(self):
        with tempfile.TemporaryDirectory(dir=ratify.ROOT / "work") as scratch:
            private = Path(scratch) / "new-source.private.json"
            public = ratify.ROOT / "docs/evidence" / (
                "_temporary-v066-caret-source-freeze-test.json")
            try:
                aggregate = ratify.write(private, public)
                _, digest = validate_ratification(private)
                self.assertEqual(aggregate["private_ratification_sha256"],
                                 digest)
                self.assertEqual(private.stat().st_mode & 0o777, 0o600)
                self.assertEqual(aggregate["official_final_model_results"],
                                 0)
                self.assertTrue(ratify.OLD_PUBLIC.is_file())
                with self.assertRaisesRegex(
                        ValueError, "new_private_and_public"):
                    ratify.write(private, public)
            finally:
                public.unlink(missing_ok=True)
