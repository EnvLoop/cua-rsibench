"""Failure-closed tests for Odoo current-source control adoption proposal."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools import propose_odoo_v066_candidate_control_adoption_v1 as adoption


class CandidateControlAdoptionProposalTests(unittest.TestCase):
    def test_live_public_sources_only_propose_new_control_epoch(self) -> None:
        value = adoption.inspect()
        self.assertEqual(value["retained_terminal_selection_attempts"], 3)
        self.assertEqual(set(value["historical_split_plans"]),
                         {"selection", "official_hidden"})
        self.assertFalse(value["control_dispatch_authorized"])
        self.assertFalse(value["campaign_dispatch_authorized"])
        self.assertEqual(value["official_final_tasks_admitted"], 0)
        self.assertNotEqual(
            value["historical_split_plans"]["selection"]["historical_ratification_sha256"],
            value["current_six_cell_candidate_private_sha256"])

    def test_relabelling_old_selection_plan_as_current_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            copy = Path(directory) / "selection.json"
            plan = json.loads(adoption.SELECTION.read_bytes())
            candidate = json.loads(adoption.CANDIDATE.read_bytes())
            plan["ratification_sha256"] = candidate["private_candidate_sha256"]
            copy.write_text(json.dumps(plan), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "historical_split_plan"):
                adoption.inspect(selection_path=copy)

    def test_candidate_with_dispatch_claim_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            copy = Path(directory) / "candidate.json"
            candidate = json.loads(adoption.CANDIDATE.read_bytes())
            candidate["campaign_dispatch_authorized"] = True
            copy.write_text(json.dumps(candidate), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "current_six_cell_candidate"):
                adoption.inspect(candidate_path=copy)


if __name__ == "__main__":
    unittest.main()
