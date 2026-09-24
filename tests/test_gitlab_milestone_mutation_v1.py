"""Boundary and source checks for one GitLab milestone mutation probe."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "gitlab_milestone", ROOT / "tools/qualify_gitlab_milestone_v1.py")
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)
SOURCE = ROOT / "work/scale-v06/sources/webarena-verified"
PUBLIC_RECEIPT = ROOT / "docs/evidence/gitlab-milestone-mutation-2026-09-24.json"


def event(due):
    return {"request": {"url": probe.BASE + "/primer/design/-/milestones",
                        "method": "POST", "headers": [{"name": "Cookie", "value": "private"}],
                        "postData": {"mimeType": "application/x-www-form-urlencoded",
                                     "text": "authenticity_token=private&milestone%5Btitle%5D=product+launch"
                                             "&milestone%5Bstart_date%5D=2023-01-16"
                                             "&milestone%5Bdue_date%5D=" + due}},
            "response": {"status": 302, "headers": [], "redirectURL": "",
                         "content": {"text": "private body"}}}


class LocalBoundaryTests(unittest.TestCase):
    def test_loopback_only(self):
        self.assertTrue(probe.local_request(probe.BASE + "/primer/design"))
        self.assertFalse(probe.local_request("https://gitlab.com/primer/design"))
        self.assertFalse(probe.local_request("http://localhost:8012/primer/design"))
        self.assertFalse(probe.local_request("http://user:password@localhost:8013/"))

    def test_har_sanitation_retains_only_scored_fields(self):
        raw = {"log": {"entries": [event("2023-01-30")]}}
        untouched = copy.deepcopy(raw)
        clean = probe.sanitize_har(raw)
        self.assertEqual(raw, untouched)
        data = json.dumps(clean)
        self.assertNotIn("private", data)
        self.assertIn("milestone%5Bdue_date%5D=2023-01-30", data)
        self.assertNotIn("authenticity_token", data)


@unittest.skipUnless(SOURCE.exists() and importlib.util.find_spec("webarena_verified"),
                     "pinned WebArena evaluator required")
class PublishedEvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = probe.source_proof(SOURCE)
        cls.wa = probe.evaluator(SOURCE)

    def test_source_task_is_pinned(self):
        self.assertEqual(self.source["git_commit"], probe.SOURCE_COMMIT)
        self.assertFalse(self.source["seeded_original_webarena_snapshot"])

    def test_correct_and_wrong_date_are_discriminated(self):
        right = probe.evaluate(self.wa, [event("2023-01-30")])
        wrong = probe.evaluate(self.wa, [event("2023-02-01")])
        self.assertEqual((right["status"], right["score"]), ("success", 1.0))
        self.assertEqual((wrong["status"], wrong["score"]), ("failure", 0.0))
        clean = probe.sanitize_har({"log": {"entries": [event("2023-01-30")]}})
        self.assertEqual(probe.evaluate(self.wa, clean["log"]["entries"]), right)

    def test_public_actual_events_rescore_and_reset_receipts(self):
        receipt = json.loads(PUBLIC_RECEIPT.read_text())
        runner = ROOT / "tools/qualify_gitlab_milestone_v1.py"
        fixture = ROOT / "tools/qualify_gitlab_milestone_seed_v1.rb"
        self.assertEqual(receipt["runner_sha256"], hashlib.sha256(runner.read_bytes()).hexdigest())
        self.assertEqual(receipt["fixture_sha256"], hashlib.sha256(fixture.read_bytes()).hexdigest())
        self.assertEqual(receipt["official_scores"], [1.0, 0.0, 1.0])
        self.assertEqual(receipt["qualified_task_count"], 1)
        self.assertFalse(receipt["hundred_task_ready"])
        baseline = receipt["business_baseline"]
        for case in receipt["cases"]:
            event_score = probe.evaluate(self.wa, [case["actual_sanitized_task_event"]])
            self.assertEqual(event_score, case["published_evaluator"])
            self.assertTrue(case["raw_and_sanitized_score_equal"])
            self.assertTrue(case["reset"]["business_state_restored"])
            self.assertEqual(case["reset"]["baseline_sha256"], baseline["business_sha256"])
            if case["name"] in ("positive-1", "wrong-due-date"):
                screenshot = ROOT / "docs/evidence" / (
                    "gitlab-milestone-positive-2026-09-24.png" if case["name"] == "positive-1"
                    else "gitlab-milestone-wrong-due-2026-09-24.png")
                self.assertEqual(case["screenshots_sha256"]["final.png"],
                                 hashlib.sha256(screenshot.read_bytes()).hexdigest())
        self.assertEqual(receipt["final_business_state"], baseline)


if __name__ == "__main__":
    unittest.main()
