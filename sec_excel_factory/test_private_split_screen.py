"""Structural isolation and minimum-diversity controls for sealed split plans."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import unittest

from screen_private_split import public_issuers, screen


def digest(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def synthetic_plan() -> list[dict]:
    tasks = []
    for issuer_index in range(28):
        cik = 9000000 + issuer_index
        split = "train" if issuer_index < 4 else ("selection" if issuer_index < 8 else "final")
        for variant in range(5):
            task_id = f"synthetic-{split}-{issuer_index}-{variant}"
            if split == "final":
                family = f"sealed-final-{(issuer_index + variant) % 10}"
            else:
                family = f"sealed-{split}-{variant}"
            tasks.append({"task_id": task_id, "split": split, "issuer_cik": cik,
                          "original_10k_accession": f"{cik:010d}-25-000001",
                          "source_excerpt_sha256": digest(f"source-{cik}"),
                          "template_family": family,
                          "template_semantic_sha256": digest(f"template-{family}"),
                          "actor_sha256": digest(f"actor-{task_id}"),
                          "reference_sha256": digest(f"reference-{task_id}"),
                          "source_provenance_tier": "independently_verified_exact_facts",
                          "verified_canonical_fact_count": 12})
    return tasks


class PrivateSplitScreenTest(unittest.TestCase):
    def test_public_issuer_registry_is_complete(self) -> None:
        self.assertEqual(len(public_issuers()), 28)

    def test_valid_synthetic_structure_is_only_a_candidate(self) -> None:
        result = screen(synthetic_plan())
        self.assertEqual(result["status"], "structural_candidate_only")
        self.assertEqual(result["task_counts"], {"train": 20, "selection": 20, "final": 100})
        self.assertEqual(result["registered_private_issuer_families"], 28)
        self.assertEqual(result["registered_final_workflow_families"], 10)
        self.assertEqual(result["official_excel_web_admissions"], 0)

    def test_reject_public_source_template_and_two_fact_anchor(self) -> None:
        cases = synthetic_plan()
        cases[0]["issuer_cik"] = next(iter(public_issuers()))
        cases[1]["template_family"] = "ppe_carrying_value"
        cases[2]["verified_canonical_fact_count"] = 2
        errors = screen(cases)["errors"]
        self.assertIn("public_development_issuer_reused", errors)
        self.assertIn("public_development_template_reused", errors)
        self.assertIn("insufficient_verified_canonical_facts", errors)

    def test_reject_aliases_and_cross_split_leakage(self) -> None:
        cases = deepcopy(synthetic_plan())
        cases[20]["issuer_cik"] = cases[0]["issuer_cik"]
        cases[21]["template_family"] = cases[0]["template_family"]
        cases[22]["actor_sha256"] = cases[0]["actor_sha256"]
        cases[23]["template_semantic_sha256"] = cases[0]["template_semantic_sha256"]
        errors = screen(cases)["errors"]
        self.assertIn("issuer_crosses_splits", errors)
        self.assertIn("semantic_template_family_crosses_splits", errors)
        self.assertIn("actor_sha256_reused_across_tasks", errors)
        self.assertIn("semantic_template_hash_reused_under_alias", errors)

    def test_current_empty_inventory_fails_closed(self) -> None:
        result = screen([])
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["task_counts"], {"train": 0, "selection": 0, "final": 0})
        self.assertEqual(result["official_excel_web_admissions"], 0)


if __name__ == "__main__":
    unittest.main()
