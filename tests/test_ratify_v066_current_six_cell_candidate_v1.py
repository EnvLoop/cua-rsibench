"""The dated current-source candidate is reproducible and never dispatchable."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from native_desktop_factory.v066_final_freeze import validate_ratification
from tools import ratify_v066_current_six_cell_candidate_v1 as candidate


class CurrentSixCellCandidateTests(unittest.TestCase):
    def test_six_current_adapters_and_odoo_exception_are_bound(self):
        private, public = candidate.build()
        self.assertEqual(set(private["cell_profiles"]), set(candidate.CELLS))
        self.assertEqual(public["cell_adapter_sha256s"]["desktop-native"],
                         "628f3f5383f265ecb781386d0a7ac5ab335d56238f9dec5c375f73c7baefb480")
        self.assertEqual(public["cell_adapter_sha256s"]["odoo-community"],
                         "fb5b2cba08e7d9e71d372bad3cee6b38763ccb2a76033d6f89a5be37e92de168")
        self.assertEqual(private["odoo_current_runtime_source_sha256s"]
                         ["enterprise_fallback/odoo18/odoo_v066_scale_pinned_border_adapter.py"],
                         "da20b58296f94f1d3aefb231b6e9072d870c8b4a0aaaffedb2c29f8125b2d94a")
        self.assertEqual(private["odoo_current_runtime_source_sha256s"]
                         ["src/cursibench/scale_action_contract_v066.py"],
                         "68569a1ed06984985600d367975d3e5c1e6935ec9571b24e3d3ba637174dc24b")
        self.assertEqual(private["odoo_physical_dispatch_profile"],
                         "pinned-noninteractive-border-dispatch-2026-09-29")
        self.assertEqual(private["odoo_validator_amendment"],
                         "v066-pre-dispatch-validation-2026-09-29")
        self.assertEqual(public["private_candidate_sha256"],
                         candidate.digest(candidate.canonical(private)))
        self.assertFalse(public["campaign_dispatch_authorized"])
        self.assertFalse(public["all_six_current_live_smokes_ratified"])
        self.assertFalse(public["full_study_pre_campaign_witness_published"])
        self.assertEqual((public["qualified_final_tasks"],
                          public["researcher_campaigns"],
                          public["official_final_model_results"]), (0, 0, 0))
        serialized = json.dumps(public)
        self.assertNotIn("task_id", serialized)
        self.assertNotIn("@", serialized)

    def test_historical_source_ratifiers_remain_invalid(self):
        from tools import ratify_v066_action_source_for_controls_v1 as old
        from tools import ratify_v066_caret_amendment_for_controls_v1 as caret
        with self.assertRaisesRegex(ValueError, "six_cell_adapter_source_changed"):
            old.build()
        with self.assertRaisesRegex(ValueError,
                                    "caret_amendment_six_cell_adapter_source_changed"):
            caret.build()

    def test_stale_source_and_upstream_receipt_fail_closed(self):
        real = candidate.source_digest
        with patch.object(candidate, "source_digest",
                          side_effect=lambda path: "0" * 64 if path.endswith(
                              "odoo_v066_scale_pinned_border_adapter.py") else real(path)):
            with self.assertRaisesRegex(ValueError,
                                        "candidate_odoo_runtime_source_changed"):
                candidate.build()
        with patch.object(candidate, "source_digest",
                          side_effect=lambda path: "0" * 64 if path.endswith(
                              "office_web_e2b_v066_train_adapter.py") else real(path)):
            with self.assertRaisesRegex(ValueError,
                                        "candidate_six_cell_source_changed"):
                candidate.build()
        changed = dict(candidate.UPSTREAM)
        name, _ = changed["odoo_validator_source_freeze"]
        changed["odoo_validator_source_freeze"] = (name, "0" * 64)
        with patch.object(candidate, "UPSTREAM", changed):
            with self.assertRaisesRegex(ValueError,
                                        "candidate_upstream_evidence_changed"):
                candidate.build()

    def test_missing_odoo_exception_or_claimed_live_control_rejected(self):
        records, hashes = candidate.upstream()
        missing = deepcopy(records)
        del missing["odoo_validator_source_freeze"]["source_sha256s"][
            "enterprise_fallback/odoo18/odoo_v066_scale_pinned_border_adapter.py"]
        with patch.object(candidate, "upstream", return_value=(missing, hashes)):
            with self.assertRaisesRegex(ValueError,
                                        "candidate_odoo_runtime_binding_incomplete"):
                candidate.build()
        promoted = deepcopy(records)
        promoted["odoo_selection_plan"]["fresh_current_profile_gui_controls"] = 1
        with patch.object(candidate, "upstream", return_value=(promoted, hashes)):
            with self.assertRaisesRegex(ValueError,
                                        "candidate_odoo_split_plan_not_live_evidence"):
                candidate.build()

    def test_private_candidate_cannot_enter_existing_campaign_gate(self):
        private, public = candidate.build()
        (candidate.ROOT / "work").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=candidate.ROOT / "work") as scratch:
            private_path = Path(scratch) / "candidate.private.json"
            output = candidate.write_private(private_path)
            self.assertEqual(output, public)
            self.assertEqual(private_path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(private_path.read_bytes(), candidate.canonical(private))
            with self.assertRaisesRegex(ValueError,
                                        "Common six-cell v0.6.6 profile is not ratified"):
                validate_ratification(private_path)

    def test_published_receipt_must_match_before_private_materialization(self):
        private_value, public = candidate.build()
        (candidate.ROOT / "work").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=candidate.ROOT / "work") as scratch:
            private_path = Path(scratch) / "candidate.private.json"
            with tempfile.TemporaryDirectory() as public_dir:
                published = Path(public_dir) / "public.json"
                with patch.object(candidate, "EVIDENCE", Path(public_dir)), \
                     patch.object(candidate, "build", return_value=(private_value, public)):
                    published.write_text(json.dumps({**public,
                        "campaign_dispatch_authorized": True}))
                    with self.assertRaisesRegex(ValueError,
                                                "candidate_public_receipt_changed"):
                        candidate.write_private(private_path,
                                                public_path=published)
                    self.assertFalse(private_path.exists())
                    published.write_text(json.dumps(public))
                    candidate.write_private(private_path, public_path=published)
                    self.assertTrue(private_path.exists())


if __name__ == "__main__":
    unittest.main()
