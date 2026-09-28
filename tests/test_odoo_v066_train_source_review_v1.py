"""Read-only source-review audit tests on preserved evaluator artifacts."""

from __future__ import annotations

import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from tools import audit_odoo_v066_train_source_review_v1 as review


class PreservedSourceReviewTests(unittest.TestCase):
    def setUp(self):
        values = [os.environ.get(name) for name in (
            "ODOO_SECOND_PILOT_ATTEMPT", "ODOO_SECOND_TRAIN_PRIVATE",
            "ODOO_SECOND_PILOT_BINDING")]
        if not all(values):
            self.skipTest("private second-pilot paths not supplied")
        self.attempt, self.train, self.binding = map(Path, values)
        self.args = {"attempt_dir": self.attempt,
                     "train_private": self.train,
                     "pilot_binding_path": self.binding}

    def test_real_visual_review_provenance_and_public_privacy(self):
        result = review.audit(**self.args)
        self.assertEqual(result["status"],
                         "independent_visual_source_review_attested_and_hash_bound")
        self.assertEqual(result["visual_sections_attested"], 7)
        self.assertTrue(result[
            "manual_visual_match_is_review_attestation_not_pixel_equivalence"])
        self.assertTrue(result[
            "earlier_incomplete_review_artifacts_retained_and_superseded"])
        self.assertEqual(result["official_final_tasks_admitted"], 0)
        task_id = json.loads((self.attempt / "draft.private.json").read_bytes())["task_id"]
        self.assertNotIn(task_id, json.dumps(result))
        self.assertNotIn(str(self.attempt), json.dumps(result))

    def test_changed_source_render_hash_rejected_without_mutation(self):
        original = review._json
        target = self.attempt / "source-review-support-v2.private.json"

        def changed(path):
            value = original(path)
            if Path(path) == target:
                value = dict(value)
                value["source_pdf_render_sha256"] = "0" * 64
            return value

        with patch.object(review, "_json", side_effect=changed):
            with self.assertRaisesRegex(
                    review.SourceReviewAuditError,
                    "corrected_visual_review_support_unbound"):
                review.audit(**self.args)

    def test_changed_regenerated_pdf_render_rejected(self):
        with patch.object(review, "_render_pdf", return_value=b"different render"):
            with self.assertRaisesRegex(
                    review.SourceReviewAuditError,
                    "corrected_visual_review_support_unbound"):
                review.audit(**self.args)


if __name__ == "__main__":
    unittest.main()
