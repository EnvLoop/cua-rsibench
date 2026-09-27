import json
from pathlib import Path
import tempfile
import unittest

from tools.audit_agentrouterhub_model_smokes_v1 import MODELS, audit, rows_from_private


class ResearcherSmokeAuditTest(unittest.TestCase):
    def test_private_bytes_bind_public_without_response_text(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for model in MODELS:
                response = {"model": model, "status": "completed",
                            "output": [{"text": "private reply"}],
                            "usage": {"input_tokens": 9, "output_tokens": 2,
                                      "total_tokens": 11}}
                (root / ("tiny-" + model.replace(".", "-") + ".private.json")).write_text(
                    json.dumps(response))
            rows = [{**row, "http_status": 200} for row in rows_from_private(root)]
            public = {"schema": "envloop-researcher-model-live-smokes-v1",
                      "models": rows, "researcher_campaigns_started": 0,
                      "official_final_tasks_observed": 0,
                      "prior_sol_receipt":
                      "full-study-researcher-route-live-preflight-2026-09-27.json"}
            path = root / "public.json"
            path.write_text(json.dumps(public))
            self.assertNotIn("private reply", path.read_text())
            self.assertTrue(audit(root, path)["all_completed"])
            public["models"][0]["total_tokens"] = 12
            path.write_text(json.dumps(public))
            with self.assertRaisesRegex(ValueError, "differs"):
                audit(root, path)


if __name__ == "__main__":
    unittest.main()
