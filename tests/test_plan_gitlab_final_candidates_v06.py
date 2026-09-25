"""Fail-closed tests for the GitLab source-pinned candidate queue."""

from __future__ import annotations

import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import plan_gitlab_final_candidates_v06 as plan  # noqa: E402


def fake_rows() -> list[dict]:
    rows = []
    next_id = 1000
    for template in range(35):
        kind = ("mutate", "retrieve", "navigate")[template % 3]
        for _ in range(5):
            rows.append({
                "sites": ["gitlab"], "task_id": next_id, "intent_template_id": template,
                "instantiation_dict": {"repo": f"org-{template}/project-{next_id}"},
                "start_urls": ["__GITLAB__"],
                "eval": [{"evaluator": "AgentResponseEvaluator",
                          "expected": {"task_type": kind, "status": "SUCCESS"}},
                         *([{"evaluator": "NetworkEventEvaluator",
                             "expected": {"url": "__GITLAB__/target"}}]
                           if kind != "retrieve" else [])],
            })
            next_id += 1
    for template in range(35, 40):
        rows.append({
            "sites": ["gitlab"], "task_id": next_id, "intent_template_id": template,
            "instantiation_dict": {}, "start_urls": ["__GITLAB__"],
            "eval": [{"evaluator": "AgentResponseEvaluator",
                      "expected": {"task_type": "retrieve", "status": "SUCCESS"}}],
        })
        next_id += 1
    assert len(rows) == 180
    # Split one five-case family so the synthetic inventory has 41 families.
    rows[0]["intent_template_id"] = 40
    assert len({row["intent_template_id"] for row in rows}) == 41
    return rows


class GitLabCandidateTests(unittest.TestCase):
    def test_100_success_candidates_are_template_and_hint_disjoint(self):
        rows = fake_rows()
        hard = {row["task_id"] for row in rows if row["task_id"] % 2 == 0}
        result = plan.manifest(rows, hard)
        selection, final = (result["task_sets"][name] for name in ("selection", "provisional_final"))
        self.assertEqual((len(selection), len(final)), (20, 100))
        self.assertFalse({item["template_group"] for item in selection}
                         & {item["template_group"] for item in final})
        self.assertFalse({hint for item in selection for hint in item["source_entity_hints"]}
                         & {hint for item in final for hint in item["source_entity_hints"]})
        self.assertEqual({item["expected_status"] for item in final}, {"SUCCESS"})
        self.assertEqual(result["counts"]["provisional_final_officially_admitted"], 0)
        self.assertEqual(result, plan.manifest(rows, hard))

    def test_policy_denial_and_gui_mismatches_are_quarantined(self):
        rows = fake_rows()
        rows[0]["task_id"] = 102
        rows[2]["task_id"] = 258
        rows[1]["eval"] = [{"evaluator": "AgentResponseEvaluator",
                            "expected": {"task_type": "mutate", "status": "ACTION_NOT_ALLOWED_ERROR"}}]
        result = plan.manifest(rows, set())
        chosen = {item["task_id"] for name in ("selection", "provisional_final")
                  for item in result["task_sets"][name]}
        self.assertNotIn(102, chosen)
        self.assertNotIn(258, chosen)
        self.assertNotIn(rows[1]["task_id"], chosen)
        self.assertEqual(result["quarantine"]["other_statuses_excluded_from_success_queue"],
                         {"ACTION_NOT_ALLOWED_ERROR": 1})

    def test_explicit_project_and_principal_hints_cross_field(self):
        row = fake_rows()[0]
        row["instantiation_dict"] = {"repo": "Team/Thing", "user": "Alice"}
        row["start_urls"] = ["__GITLAB__/Team/Thing/-/issues"]
        row["eval"][1]["expected"]["url"] = ["__GITLAB__/team/thing/-/issues", "__GITLAB__/dashboard/todos"]
        self.assertEqual(plan.source_entity_hints(row),
                         ["principal:alice", "project:team/thing"])

    def test_network_event_and_status_are_not_saved_state_proof(self):
        row = fake_rows()[0]
        shape = plan.evaluation_shape(row)
        self.assertTrue(shape["requires_saved_state_oracle"])
        self.assertEqual(shape["network_assertions"], 1)
        bad = copy.deepcopy(row)
        bad["eval"].append({"evaluator": "UnsupportedEvaluator"})
        with self.assertRaisesRegex(ValueError, "unexpected extra evaluator"):
            plan.evaluation_shape(bad)

    def test_pinned_hash_drift_fails_before_source_parse(self):
        with tempfile.TemporaryDirectory() as temp:
            source, hard = Path(temp) / "source.json", Path(temp) / "hard.json"
            source.write_text("[]")
            hard.write_text('{"task_ids": []}')
            with self.assertRaisesRegex(ValueError, "differ from pinned"):
                plan.source_rows(source, hard)


if __name__ == "__main__":
    unittest.main()
