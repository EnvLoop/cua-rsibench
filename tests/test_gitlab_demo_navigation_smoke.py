"""Boundary and unchanged-upstream checks for disposable GitLab task 44."""

import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "gitlab_smoke", ROOT / "tools/qualify_gitlab_demo_navigation_v1.py")
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)
SOURCE = ROOT / "work/scale-v06/sources/webarena-verified"


def event(path, status=200):
    return {"request": {"url": smoke.BASE + path, "method": "GET",
                        "headers": [{"name": "accept", "value": "text/html"}]},
            "response": {"status": status, "headers": [], "redirectURL": "", "content": {}}}


class BoundaryTests(unittest.TestCase):
    def test_loopback_read_only_and_setup_boundary(self):
        self.assertTrue(smoke.local_request(smoke.BASE, "GET"))
        self.assertTrue(smoke.local_request(smoke.BASE, "POST", setup=True))
        self.assertFalse(smoke.local_request(smoke.BASE, "POST"))
        self.assertFalse(smoke.local_request("https://gitlab.com", "GET"))
        self.assertFalse(smoke.local_request("http://localhost:8023", "GET"))
        self.assertFalse(smoke.local_request("http://user:pass@localhost:8012", "GET"))

    def test_har_sanitization_keeps_navigation_but_removes_auth(self):
        row = event("/dashboard/todos?auth_token=hidden&sort=asc")
        row["request"]["headers"].append({"name": "cookie", "value": "_gitlab_session=hidden"})
        row["request"]["postData"] = {"text": "password=hidden"}
        row["response"]["content"] = {"text": "private body"}
        raw = {"log": {"entries": [row]}}
        before = copy.deepcopy(raw)
        clean = smoke.sanitize_har(raw)
        self.assertEqual(raw, before)
        data = json.dumps(clean)
        for secret in ("hidden", "private body", "password=hidden"):
            self.assertNotIn(secret, data)
        self.assertIn("/dashboard/todos", data)
        self.assertIn("sort=asc", data)
        self.assertEqual(clean["log"]["entries"][0]["response"]["status"], 200)

    def test_cannot_claim_success_with_infrastructure_error_or_changed_database(self):
        cases = [{"positive": value, "published_evaluator": {
            "score": float(value), "status": "success" if value else "failure"},
            "raw_and_sanitized_evaluator_equal": True,
            "final_gui": {"body_visible": True, "error_banner_visible": False},
            "blocked_requests": []}
            for value in (True, False, True)]
        snapshots = [{"sha256": "same"} for _ in range(4)]
        smoke.validate(cases, snapshots)
        wrong = copy.deepcopy(cases)
        wrong[1]["published_evaluator"]["status"] = "error"
        with self.assertRaisesRegex(ValueError, "evaluator error"):
            smoke.validate(wrong, snapshots)
        wrong = copy.deepcopy(snapshots)
        wrong[3]["sha256"] = "changed"
        with self.assertRaisesRegex(ValueError, "changed GitLab"):
            smoke.validate(cases, wrong)


@unittest.skipUnless(SOURCE.exists() and importlib.util.find_spec("webarena_verified"),
                     "pinned upstream package required")
class PublishedEvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.task, cls.source = smoke.source_proof(SOURCE)
        cls.evaluator = smoke.evaluator(SOURCE)

    def test_inventory_and_task_contract(self):
        self.assertEqual(self.source["git_commit"], smoke.COMMIT)
        self.assertEqual(self.source["gitlab_only_ids"], 180)
        self.assertEqual(self.source["unique_intent_templates"], 41)
        self.assertEqual(self.source["task_type_counts"],
                         {"navigate": 16, "retrieve": 53, "mutate": 111})
        self.assertEqual(self.task["intent"], "Open my todos page")

    def test_exact_published_evaluator_positive_negative_and_failed_http(self):
        positive = smoke.evaluate(self.evaluator, [event("/dashboard/todos")])
        negative = smoke.evaluate(self.evaluator, [event("/explore/projects")])
        failed_http = smoke.evaluate(self.evaluator, [event("/dashboard/todos", 500)])
        self.assertEqual((positive["status"], positive["score"]), ("success", 1.0))
        self.assertEqual((negative["status"], negative["score"]), ("failure", 0.0))
        self.assertEqual((failed_http["status"], failed_http["score"]), ("failure", 0.0))

    def test_redacted_trace_scores_like_raw_without_auth(self):
        row = event("/dashboard/todos")
        row["request"]["headers"].append({"name": "cookie", "value": "private-token"})
        raw = {"log": {"entries": [row]}}
        clean = smoke.sanitize_har(raw)
        self.assertEqual(smoke.evaluate(self.evaluator, raw["log"]["entries"]),
                         smoke.evaluate(self.evaluator, clean["log"]["entries"]))
        self.assertNotIn("private-token", json.dumps(clean))


if __name__ == "__main__":
    unittest.main()
