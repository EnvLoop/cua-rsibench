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
    def test_historical_caret_source_refuses_current_odoo_adapter_drift(self):
        with self.assertRaisesRegex(
                ValueError, "caret_amendment_six_cell_adapter_source_changed"):
            ratify.build()
        # The dated caret record remains readable as historical evidence;
        # it cannot silently authorize the subsequently amended Odoo actor.
        historical = (ratify.ROOT / "work/full-study/"
                      "v066-caret-amended-control-ratification-20260928.private.json")
        private, _ = validate_ratification(historical)
        self.assertEqual(len(private["cell_profiles"]), 6)
        self.assertEqual(private["hidden_final_model_attempts_before_ratification"], 0)

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

    def test_changed_current_source_refuses_new_caret_record_before_write(self):
        with tempfile.TemporaryDirectory(dir=ratify.ROOT / "work") as scratch:
            private = Path(scratch) / "new-source.private.json"
            public = ratify.ROOT / "docs/evidence" / (
                "_temporary-v066-caret-source-freeze-test.json")
            try:
                with self.assertRaisesRegex(
                        ValueError, "caret_amendment_six_cell_adapter_source_changed"):
                    ratify.write(private, public)
                self.assertFalse(private.exists())
                self.assertFalse(public.exists())
                self.assertTrue(ratify.OLD_PUBLIC.is_file())
            finally:
                public.unlink(missing_ok=True)
