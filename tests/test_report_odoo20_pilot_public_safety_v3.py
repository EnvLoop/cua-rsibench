"""Synthetic-only checks for the public Odoo20 report boundary.

No test reads real task bodies, invokes a provider, or operates an environment.
"""

from __future__ import annotations

import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
for import_root in (ROOT, ROOT / "src", ROOT / "enterprise_fallback" / "odoo18"):
    sys.path.insert(0, str(import_root))
from tools import report_odoo20_pilot_v3 as report  # noqa: E402


def complete_publication() -> dict:
    """A synthetic matched comparison, never a record of real execution."""
    task_ids = [f"SYNTHETIC-FINAL-{index:04d}" for index in range(20)]
    families = ("purchase", "inventory", "sales", "crm")
    outcomes = []
    for index, task_id in enumerate(task_ids):
        for lane in ("baseline", "selected_checkpoint"):
            outcomes.append({
                "task_id": task_id,
                "family": families[index // 5],
                "lane": lane,
                "score": int(lane == "selected_checkpoint"),
                "status": "saved_scored_reset_and_closed",
                "actions": 12,
                "samples": 12,
                "actor_seconds": 90.0,
                "lifecycle_seconds": 110.0,
                "rendered_input_tokens": None,
                "sampled_output_tokens": None,
                "provider_latency_ms": None,
                "termination": "task_action_budget",
            })
    return {
        "schema": "envloop-odoo20-pilot-publication-v3",
        "scope": "single_environment_20_task_pilot",
        "cell_id": "odoo-community",
        "full_study_completed": False,
        "final_task_count": 20,
        "final_outcome_count": 40,
        "task_ids": task_ids,
        "native_control_count": 20,
        "independent_source_review_complete": True,
        "selection_checkpoint_frozen_before_final": True,
        "training_owned_cleanup_verified": True,
        "matched_final_evidence_verified": True,
        "teacher_model": "gpt-6-sol",
        "student_model": "Qwen/Qwen3.8-27B",
        "actual_cost_usd": None,
        "outcomes": outcomes,
    }


class PublicSafetyTests(unittest.TestCase):
    def test_english_public_evidence_identifiers_are_allowed(self):
        # Hashes and public source links are necessary for reproducibility.
        value = {
            "scope": "Single-environment development pilot",
            "source_sha256": "a" * 64,
            "model": "Qwen/Qwen3.8-27B",
            "source": "https://github.com/EnvLoop/cua-rsibench",
            "known_cost_usd": None,
            "notes": ["No final comparison is available."],
        }
        report.public_safe(value)

    def test_secret_values_cannot_be_published(self):
        secrets = [
            "sk-" + "syntheticCredential" * 4,
            "tml-" + "syntheticCredential" * 4,
            "e2b_" + "a" * 40,
            "Authorization: Bearer synthetic-secret-token-123456789",
            "analyst@example.org",
        ]
        for value in secrets:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    report.public_safe({"notes": [{"detail": value}]})

    def test_sensitive_references_cannot_be_published(self):
        references = [
            "/Users/researcher/work/episode.private/result.json",
            "/home/researcher/work/model-private.json",
            "work/teacher-01.private/request.json",
            "https://example.org/evidence.private/receipt.json",
            "tinker://synthetic-session/weights/checkpoint-0001",
        ]
        for reference in references:
            with self.subTest(reference=reference):
                with self.assertRaises(ValueError):
                    report.public_safe({"reference": reference})

    def test_non_english_content_cannot_be_published(self):
        for text in ("English followed by \u4e2d\u6587", "English\uff0c punctuation", "\u7d50\u679c", "English followed by \U00020000"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    report.public_safe({"notes": [text]})

    def test_object_keys_are_checked_as_well_as_leaf_values(self):
        for key in (
            "sk-" + "syntheticCredential" * 4,
            "work/secrets.private/key",
            "tinker://synthetic-session/weights/checkpoint-0001",
            "\u4e2d\u6587",
        ):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    report.public_safe({"outer": [{key: "safe value"}]})

    def test_credential_fields_are_rejected_even_without_known_token_prefix(self):
        for field in ("password", "api_key", "authorization", "access_token"):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    report.public_safe({"nested": {field: "synthetic opaque value"}})


class PublicationClaimsTests(unittest.TestCase):
    def test_complete_synthetic_matched_comparison_validates(self):
        record = complete_publication()
        before = copy.deepcopy(record)
        report.validate_publication(record)
        self.assertEqual(record, before, "Validation must not rewrite evidence")

    def test_partial_comparison_cannot_authorize_publication(self):
        for count in (0, 1, 20, 39):
            record = complete_publication()
            record["outcomes"] = record["outcomes"][:count]
            record["final_outcome_count"] = count
            with self.subTest(outcome_count=count):
                with self.assertRaises(ValueError):
                    report.validate_publication(record)

    def test_forty_rows_do_not_substitute_for_matched_unique_tasks(self):
        mutations = (
            lambda value: value["outcomes"].__setitem__(39, copy.deepcopy(value["outcomes"][0])),
            lambda value: value["outcomes"][39].__setitem__("task_id", "FOREIGN-TASK"),
            lambda value: value["outcomes"][1].__setitem__("lane", "baseline"),
            lambda value: value["task_ids"].__setitem__(19, value["task_ids"][0]),
        )
        for mutation in mutations:
            record = complete_publication()
            mutation(record)
            with self.subTest(mutation=mutation):
                with self.assertRaises(ValueError):
                    report.validate_publication(record)

    def test_family_counts_and_pair_identity_are_preserved(self):
        skewed = complete_publication()
        for row in skewed["outcomes"]:
            if row["family"] == "crm":
                row["family"] = "sales"
        split_pair = complete_publication()
        split_pair["outcomes"][1]["family"] = "crm"
        for record in (skewed, split_pair):
            with self.subTest(record=record):
                with self.assertRaises(ValueError):
                    report.validate_publication(record)

    def test_single_cell_results_do_not_authorize_full_study_claims(self):
        amendments = (
            {"full_study_completed": True},
            {"scope": "full_study"},
            {"cell_id": "six_environments"},
            {"final_task_count": 600},
            {"final_outcome_count": 3000},
        )
        for amendment in amendments:
            record = complete_publication()
            record.update(amendment)
            with self.subTest(amendment=amendment):
                with self.assertRaises(ValueError):
                    report.validate_publication(record)

    def test_missing_independent_evidence_blocks_publication(self):
        fields = (
            "independent_source_review_complete",
            "selection_checkpoint_frozen_before_final",
            "training_owned_cleanup_verified",
            "matched_final_evidence_verified",
        )
        for field in fields:
            for replacement in (False, None, "true"):
                record = complete_publication()
                record[field] = replacement
                with self.subTest(field=field, replacement=replacement):
                    with self.assertRaises(ValueError):
                        report.validate_publication(record)

    def test_unscored_or_unclosed_attempts_cannot_be_counted_as_outcomes(self):
        for status in ("running", "timeout", "saved_scored", "synthetic"):
            record = complete_publication()
            record["outcomes"][0]["status"] = status
            with self.subTest(status=status):
                with self.assertRaises(ValueError):
                    report.validate_publication(record)

    def test_model_labels_cannot_claim_a_different_authenticated_epoch(self):
        for field, model in (
            ("teacher_model", "gpt-6.1-sol"),
            ("teacher_model", "gpt-6-astra"),
            ("student_model", "Qwen/Qwen3.8-8B"),
        ):
            record = complete_publication()
            record[field] = model
            with self.subTest(field=field, model=model):
                with self.assertRaises(ValueError):
                    report.validate_publication(record)

    def test_outcome_values_respect_the_actual_experiment_budget(self):
        for field, value in (
            ("score", True),
            ("score", 0.5),
            ("actions", 91),
            ("samples", 0),
            ("samples", True),
            ("actor_seconds", 720.01),
            ("actor_seconds", float("nan")),
            ("lifecycle_seconds", 1200.01),
            ("lifecycle_seconds", float("inf")),
            ("rendered_input_tokens", -1),
        ):
            record = complete_publication()
            record["outcomes"][0][field] = value
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValueError):
                    report.validate_publication(record)

    def test_complete_record_still_passes_through_public_safety_boundary(self):
        record = complete_publication()
        record["additional_metadata"] = {"checkpoint": "tinker://synthetic-session/weights/1"}
        with self.assertRaises(ValueError):
            report.validate_publication(record)

    def test_partial_evidence_cannot_render_a_gain_manuscript(self):
        record = complete_publication()
        record["outcomes"] = record["outcomes"][:3]
        with self.assertRaises(ValueError):
            report.manuscript(record)

    def test_public_true_flags_alone_cannot_authorize_artifact_generation(self):
        # A structurally valid public summary is not authenticated raw evidence.
        with tempfile.TemporaryDirectory(prefix="odoo20-report-synthetic-test-") as directory:
            output = Path(directory) / "new-report"
            with patch.object(report.evaluator.workers, "private_json",
                              return_value=complete_publication()):
                with self.assertRaises(ValueError):
                    report.generate(request_path="synthetic-test-only",
                                    request_sha="a" * 64, output_root=output)
            self.assertFalse(output.exists(), "Reject before creating any public artifact")


if __name__ == "__main__":
    unittest.main()
