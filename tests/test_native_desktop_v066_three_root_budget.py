"""The old22 and stopped two remain charged before any fresh full100."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from native_desktop_factory import v066_profile_scope_three_root_budget as budget
from native_desktop_factory.v066_final_freeze import digest


def intent(root: Path, task_id: str, attempt: str) -> None:
    path = root / task_id / attempt
    path.mkdir(parents=True, exist_ok=True)
    (path / "intent.json").write_text(json.dumps({
        "schema": "cua-native-wdi-v066-final-control-intent-v1",
        "task_id": task_id, "attempt": attempt,
        "lease_seconds": 600}))


class ThreeRootBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.old = root / "old" / "v066-final-gui"
        self.failed = root / "failed" / "v066-final-gui"
        self.future = root / "future" / "v066-final-gui"
        self.old.mkdir(parents=True, mode=0o700)
        self.failed.mkdir(parents=True, mode=0o700)
        self.old.chmod(0o700)
        self.failed.chmod(0o700)
        for index in range(7):
            for attempt in ("positive", "near-miss", "cold-reset"):
                intent(self.old, f"historical-{index}", attempt)
        intent(self.old, "historical-partial", "positive")
        for index in range(2):
            intent(self.failed, f"stopped-{index}", "positive")

    def test_old22_failed2_future300_reserve_54_under_same_60(self):
        row = budget.combined_budget(
            original_root=self.old, failed_root=self.failed,
            future_root=self.future, proposed_future_intents=300)
        self.assertEqual(row["historical_original_intents"], 22)
        self.assertEqual(row["halted_amended_intents"], 2)
        self.assertEqual(row["combined_full_lease_intents"], 324)
        self.assertEqual(row["combined_conservative_reserved_usd"], "54")
        self.assertEqual(row["remaining_lease_intents_at_cap"], 36)
        self.assertIsNone(row["actual_provider_billed_usd"])

    def test_dated_proposal_binds_three_root_auditor_source(self):
        root = Path(__file__).resolve().parents[1]
        public = json.loads((root / "docs/evidence" /
            "native-wdi-v066-scoped-profile-pre-result-amendment-2026-09-28.json"
            ).read_bytes())
        self.assertEqual(public["three_root_budget_audit_source_sha256"],
                         digest(Path(budget.__file__).read_bytes()))
        self.assertEqual(public["three_root_combined_full_lease_intents_planned"],
                         324)
        self.assertFalse(public["active_three_root_paid_bridge_recorded"])

    def test_fresh_or_historical_intent_escape_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "count changed"):
            budget.combined_budget(
                original_root=self.old, failed_root=self.failed,
                future_root=self.future, proposed_future_intents=301)
        intent(self.failed, "unexpected-third", "positive")
        with self.assertRaisesRegex(ValueError, "count changed"):
            budget.combined_budget(
                original_root=self.old, failed_root=self.failed,
                future_root=self.future, proposed_future_intents=300)
        with self.assertRaisesRegex(ValueError, "not isolated"):
            budget.combined_budget(
                original_root=self.old, failed_root=self.old,
                future_root=self.future, proposed_future_intents=300)
