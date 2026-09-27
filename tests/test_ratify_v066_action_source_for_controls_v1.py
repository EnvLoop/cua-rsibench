"""Code-only ratification must match six tracked adapters, not task results."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import ratify_v066_action_source_for_controls_v1 as ratify
from native_desktop_factory.v066_final_freeze import validate_ratification


class CodeOnlyRatificationTests(unittest.TestCase):
    def test_six_exact_adapter_sources_and_no_result_authority(self):
        value, public = ratify.build()
        self.assertEqual(len(value["cell_profiles"]), 6)
        self.assertEqual(public["synthetic_action_tests"], 26)
        self.assertFalse(public["six_cell_live_smokes_complete"])
        self.assertFalse(public["full_study_pre_campaign_witness_published"])
        self.assertEqual(public["qualified_final_tasks"], 0)

    def test_changed_adapter_source_refuses_before_output(self):
        raw = ratify.LEDGER.read_bytes()
        changed = json.loads(raw)
        changed["cells"][0]["adapter_source_sha256s"][
            changed["cells"][0]["v066_adapter_source"]] = "0" * 64
        with tempfile.TemporaryDirectory() as scratch:
            ledger = Path(scratch) / "changed-ledger.json"
            ledger.write_text(json.dumps(changed))
            # Exercise the source check without editing tracked files.
            with patch.object(ratify, "LEDGER", ledger):
                with self.assertRaisesRegex(ValueError,
                                            "six_cell_adapter_source_changed"):
                    ratify.build()

    def test_private_record_validates_and_public_has_no_results(self):
        with tempfile.TemporaryDirectory(dir=ratify.ROOT / "work") as scratch:
            private = Path(scratch) / "freeze.private.json"
            public = ratify.ROOT / "docs/evidence" / (
                "_temporary-v066-code-freeze-test.json")
            try:
                result = ratify.write(private, public)
                _, digest = validate_ratification(private)
                self.assertEqual(result["private_ratification_sha256"], digest)
                self.assertEqual(private.stat().st_mode & 0o777, 0o600)
                self.assertEqual(result["official_final_model_results"], 0)
            finally:
                public.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
