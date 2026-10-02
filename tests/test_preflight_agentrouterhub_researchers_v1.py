import json
import unittest

from tools.preflight_agentrouterhub_researchers_v1 import MODELS, public_summary


class ResearcherRoutePreflightTest(unittest.TestCase):
    def test_public_summary_allowlists_data(self):
        secret = "sk-SECRET-DO-NOT-PUBLISH"
        roster = {"data": [{"id": name, "internal": secret} for name in MODELS]}
        sample = {"status": "completed", "model": "gpt-6-sol",
                  "output": [{"text": secret}],
                  "usage": {"input_tokens": 12, "output_tokens": 3,
                            "total_tokens": 15}}
        public = public_summary(json.dumps(roster).encode(), json.dumps(sample).encode())
        self.assertNotIn(secret, json.dumps(public))
        self.assertEqual(public["tiny_sol_sample"]["total_tokens"], 15)
        self.assertEqual(public["researcher_campaigns_started"], 0)

    def test_missing_model_fails_closed(self):
        roster = {"data": [{"id": name} for name in MODELS[:-1]]}
        with self.assertRaisesRegex(ValueError, "absent"):
            public_summary(json.dumps(roster).encode(), None)

    def test_incomplete_sample_fails_closed(self):
        roster = {"data": [{"id": name} for name in MODELS]}
        sample = {"status": "incomplete", "model": "gpt-6-sol",
                  "usage": {"input_tokens": 1, "output_tokens": 0,
                            "total_tokens": 1}}
        with self.assertRaisesRegex(ValueError, "not complete"):
            public_summary(json.dumps(roster).encode(), json.dumps(sample).encode())


if __name__ == "__main__":
    unittest.main()
