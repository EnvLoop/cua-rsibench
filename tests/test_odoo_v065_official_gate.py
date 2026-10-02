"""Official Odoo dispatch stays shut until the six-cell v0.6.5 freeze."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ODOO_DIR = Path(__file__).resolve().parents[1] / "enterprise_fallback/odoo18"
sys.path.insert(0, str(ODOO_DIR))
from official_runner_v065 import (  # noqa: E402
    FreezeError, _preflight_budget, execute_frozen_base, preflight,
)


class OfficialOdooGateTests(unittest.TestCase):
    def test_missing_freeze_rejects_before_any_hidden_or_provider_use(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            with self.assertRaises(FreezeError) as error:
                preflight(root / "missing-freeze.json", root / "not-a-worker",
                          "private-synthetic", root / "result")
            self.assertEqual(error.exception.code, "six_cell_freeze_missing")
            self.assertEqual(list(root.iterdir()), [])

    def test_unratified_freeze_rejects_before_references_are_read(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            freeze = root / "freeze.json"
            freeze.write_text(json.dumps({
                "schema": "cua-odoo-v065-official-dispatch-freeze-v1",
                "status": "draft", "cell_id": "odoo-community",
                "output_version": "scale-action-output-v0.6.5",
                "provider_dispatch_enabled": False,
                "official_outcomes_before_ratification": 0,
                "ratified_utc": "2026-09-27T00:00:00+00:00",
                "public_protocol_release_sha256": "a" * 64,
                "campaign_id": "odoo-v065-base-test",
                "checkpoint": {"role": "base", "model_path": "Qwen/Qwen3.8-27B",
                               "checkpoint_sha256": "a" * 64},
                "pre_campaign_manifest": {"path": "absent", "sha256": "a" * 64},
                "pre_campaign_plan": {"path": "absent", "sha256": "a" * 64},
                "action_bundle": {"path": "absent", "sha256": "a" * 64},
                "odoo_runtime_bundle": {"path": "absent", "sha256": "a" * 64},
                "hidden_boundary_public": {"path": "absent", "sha256": "a" * 64},
                "hidden_gui_public": {"path": "absent", "sha256": "a" * 64},
                "budget_authority": {"path": "absent", "sha256": "a" * 64},
            }))
            os.chmod(freeze, 0o600)
            with self.assertRaises(FreezeError) as error:
                preflight(freeze, root / "not-a-worker", "private-synthetic",
                          root / "result")
            self.assertEqual(error.exception.code, "six_cell_freeze_not_ratified")
            self.assertFalse((root / "result").exists())

    def test_missing_provider_credential_prevents_budget_or_hidden_io(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            with patch.dict(os.environ, {"TINKER_API_KEY": ""}):
                with self.assertRaises(FreezeError) as error:
                    execute_frozen_base({"worker_dir": str(root),
                                         "output_dir": str(root / "result")})
            self.assertEqual(error.exception.code,
                             "provider_credential_missing_before_reservation")
            self.assertEqual(list(root.iterdir()), [])

    def test_budget_gate_requires_available_balance_and_locked_limits(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            authority = {
                "schema": "cua-odoo-v065-budget-authority-v1",
                "status": "funded_and_metered_before_dispatch", "currency": "USD",
                "atomic_append_ledger_enabled": True,
                "provider_invoice_reconciliation_required": True,
                "cost_basis": "all_in_including_provider_compute_inference_storage_and_licenses",
                "per_task_usd_micro_upper": 5_000_000,
                "campaign_usd_micro_ceiling": 600_000_000,
                "available_balance_usd_micro": 600_000_000,
                "pricing_source_sha256": "a" * 64,
                "provider_billing_authority_sha256": "b" * 64,
                "user_authorization_receipt_sha256": "c" * 64,
                "max_model_samples_per_task": 3,
                "campaign_model_sample_cap": 300,
                "max_output_tokens_per_sample": 512,
                "campaign_output_token_cap": 153_600,
                "max_actions_per_task": 3,
                "max_wall_seconds_per_task": 720,
                "ledger_filename": "campaign-budget.jsonl",
            }
            protocol = {"budget": {"per_campaign_all_in_ceiling_usd": "600.000000"}}
            odoo = {"execution": {"max_actions_per_task": 3,
                                   "max_wall_seconds_per_task": 720},
                    "sampling": {"max_output_tokens": 512}}
            with patch("official_runner_v065._referenced_json",
                       return_value=(authority, "d" * 64)):
                checked = _preflight_budget({"budget_authority": {}}, root,
                                            protocol, odoo)
            self.assertEqual(checked["ledger_filename"], "campaign-budget.jsonl")
            authority["available_balance_usd_micro"] = 1
            with patch("official_runner_v065._referenced_json",
                       return_value=(authority, "d" * 64)):
                with self.assertRaises(FreezeError) as error:
                    _preflight_budget({"budget_authority": {}}, root,
                                      protocol, odoo)
            self.assertEqual(error.exception.code, "atomic_budget_authority_missing")


if __name__ == "__main__":
    unittest.main()
