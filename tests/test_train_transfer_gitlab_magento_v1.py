"""Offline-only checks for two-per-skill source-disjoint transfer pools."""

from __future__ import annotations

import copy
import json
from unittest.mock import patch
import unittest

from gitlab_world import factory as gitlab_factory
from gitlab_world import train_transfer_analogues as gitlab_transfer
from magento_catalog_factory import plan as magento_plan
from magento_catalog_factory import train_transfer_analogues as magento_transfer


GITLAB_SEED = "offline-train-transfer-fixture-seed-20260929"
MAGENTO_SEED = "offline-magento-transfer-fixture-seed-20260929"


def inventory() -> dict:
    parents = []
    for parent_id in range(1, 147):
        parents.append({
            "parent_id": parent_id,
            "parent_sku": f"CONFIG-{parent_id:03d}",
            "children": [{"entity_id": parent_id * 1000 + index,
                          "sku": f"CONFIG-{parent_id:03d}-V{index:02d}",
                          "price": str(35 + parent_id % 50 + index)}
                         for index in range(10)],
        })
    return {"schema": magento_plan.INVENTORY_SCHEMA,
            "docker_image_sha256": "sha256:" + "a" * 64,
            "quarantined_parent_ids": [1], "parents": parents}


class GitLabTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = gitlab_factory.build_world(GITLAB_SEED)
        cls.staged = gitlab_transfer.build(cls.world)

    def test_stage_two_per_workflow_and_source_separation(self):
        receipt = gitlab_transfer.public_receipt(self.staged, self.world)
        self.assertEqual(receipt["supplemental_train_count"], 10)
        self.assertEqual(set(receipt["workflow_counts"].values()), {2})
        self.assertEqual(receipt["protected_partition_source_and_entity_overlap"], 0)
        self.assertEqual(receipt["gui_controls_passed"], 0)
        self.assertEqual(receipt["model_results"], 0)
        self.assertEqual(receipt["official_final_admitted"], 0)
        public = json.dumps(receipt)
        self.assertNotIn("GLT-", public)
        self.assertNotIn("CVE-", public)
        self.assertNotIn("portfolio-", public)

    def test_near_miss_and_no_regression_semantics_cannot_be_removed(self):
        changed = copy.deepcopy(self.staged)
        changed["cases"][0]["near_miss_control"] = "none"
        with self.assertRaisesRegex(ValueError, "semantic"):
            gitlab_transfer.validate(changed, self.world)
        changed = copy.deepcopy(self.staged)
        changed["cases"][1]["no_regression_scope"] = []
        with self.assertRaisesRegex(ValueError, "semantic"):
            gitlab_transfer.validate(changed, self.world)

    def test_protected_cve_overlap_fails_closed(self):
        changed = copy.deepcopy(self.world)
        train = next(p for p in changed["projects"] if p["partition"] == "train")
        final = next(p for p in changed["projects"] if p["partition"] == "final_candidate_unsealed")
        final["advisories"][0]["cveID"] = train["advisories"][0]["cveID"]
        changed["split_audit"] = gitlab_factory.split_audit(changed["projects"], changed["tasks"])
        with self.assertRaisesRegex(ValueError, "source/entity overlaps"):
            gitlab_transfer.validate(self.staged, changed)


class MagentoTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = inventory()
        cls.inventory_sha = magento_plan.digest(cls.inventory)
        cls.binding = {"test_source": "synthetic fixture"}
        cls.pin = patch.object(magento_plan, "INVENTORY_SHA256", cls.inventory_sha)
        cls.source = patch.object(magento_transfer, "_source_binding", return_value=cls.binding)
        cls.pin.start()
        cls.source.start()
        cls.original = magento_plan.build(cls.inventory, cls.inventory_sha, MAGENTO_SEED)
        cls.staged = magento_transfer.build(
            cls.inventory, cls.inventory_sha, MAGENTO_SEED, cls.original)

    @classmethod
    def tearDownClass(cls):
        cls.source.stop()
        cls.pin.stop()

    def test_five_skus_comparators_and_two_sources_per_policy(self):
        receipt = magento_transfer.public_receipt(
            self.staged, self.inventory, self.inventory_sha, MAGENTO_SEED, self.original)
        self.assertEqual(receipt["supplemental_train_count"], 8)
        self.assertEqual(set(receipt["policy_counts"].values()), {2})
        self.assertEqual(receipt["target_skus_per_case"], 5)
        self.assertEqual(receipt["untouched_same_parent_comparators_per_case_min"], 2)
        self.assertEqual(receipt["untouched_same_parent_comparators_per_case_max"], 2)
        self.assertEqual(receipt["protected_partition_source_and_entity_overlap"], 0)
        self.assertTrue(receipt["inclusive_stock_threshold_and_parity_rounding_stress_present"])
        self.assertEqual(receipt["gui_controls_passed"], 0)
        self.assertEqual(receipt["model_results"], 0)
        public = json.dumps(receipt)
        self.assertNotIn("CONFIG-", public)
        self.assertNotIn(self.staged["cases"][0]["task_id"], public)

    def test_wrong_price_and_collateral_edits_fail_validation(self):
        changed = copy.deepcopy(self.staged)
        changed["cases"][0]["target_variants"][0]["target_price"] = "1.00"
        with self.assertRaisesRegex(ValueError, "five policy-derived"):
            magento_transfer.validate(
                changed, self.inventory, self.inventory_sha, MAGENTO_SEED, self.original)
        changed = copy.deepcopy(self.staged)
        changed["cases"][1]["near_miss_control"]["wrong_price"] = changed["cases"][1]["target_variants"][0]["target_price"]
        with self.assertRaisesRegex(ValueError, "near-miss"):
            magento_transfer.validate(
                changed, self.inventory, self.inventory_sha, MAGENTO_SEED, self.original)
        changed = copy.deepcopy(self.staged)
        changed["cases"][2]["no_regression_scope"] = []
        with self.assertRaisesRegex(ValueError, "no-regression"):
            magento_transfer.validate(
                changed, self.inventory, self.inventory_sha, MAGENTO_SEED, self.original)

    def test_insufficient_eligible_original_train_parents_fails_closed(self):
        reduced = copy.deepcopy(self.inventory)
        train_ids = {case["parent_id"] for case in self.original["cases"]["train"]}
        shortened = 0
        for parent in reduced["parents"]:
            if parent["parent_id"] in train_ids and shortened < 13:
                parent["children"] = parent["children"][:5]
                shortened += 1
        reduced_sha = magento_plan.digest(reduced)
        with patch.object(magento_plan, "INVENTORY_SHA256", reduced_sha):
            changed_plan = magento_plan.build(reduced, reduced_sha, MAGENTO_SEED)
            with self.assertRaisesRegex(ValueError, "fewer than eight"):
                magento_transfer.build(reduced, reduced_sha, MAGENTO_SEED, changed_plan)


if __name__ == "__main__":
    unittest.main()
