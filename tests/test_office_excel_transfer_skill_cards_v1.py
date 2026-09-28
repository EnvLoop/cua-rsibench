"""Synthetic schema/privacy tests; no evaluator-private workbook fixtures."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from ppt_wdi_factory import plan as ppt
from tools.office_excel_transfer_skill_cards_v1 import validate


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class ExcelTransferSkillCardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        slots = []
        for split, count in (("train", 20), ("selection", 20), ("final", 100)):
            for i in range(count):
                slots.append({"split": split,
                              "semantic_template_reservation":
                              f"private_graph_{i % 13}" if split == "final"
                              else f"other_graph_{split}_{i % 2}",
                              "issuer_cik": 100000 + len(slots),
                              "original_filing_accession":
                              f"0000100000-26-{len(slots):06d}"})
        self.registry = self.root / "registry.private.json"
        self.registry.write_text(json.dumps({
            "schema": "private-excel-20-20-100-reservations-v1",
            "slots": slots}) + "\n")
        self.registry_sha = sha(self.registry.read_bytes())
        cards = []
        for i in range(13):
            atoms = [f"Select original source scope graph {i}",
                     f"Compute causal reconciliation graph {i}",
                     f"Validate independent identity graph {i}"]
            edges = [[atoms[0], atoms[1]], [atoms[1], atoms[2]]]
            rel = f"work/private-excel/source_graph_{i}.mjs"
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "const sourceSelection = true;\n"
                "const causalBridge = true;\n"
                "const independentAudit = true;\n"
                "if (faults.size !== 9) throw Error('fault count');\n")
            binding = {"path": rel, "sha256": sha(path.read_bytes()),
                       "assertions": ["sourceSelection", "causalBridge",
                                      "independentAudit"]}
            cards.append({
                "final_graph_reservation": f"private_graph_{i}",
                "causal_skill_atoms": atoms,
                "dependency_edges": edges,
                "minimum_target_edits": 9,
                "skill_signature_sha256": sha(ppt.canonical({
                    "causal_skill_atoms": atoms, "dependency_edges": edges})),
                "final_template_sha256": sha(ppt.canonical([{
                    "path": rel, "sha256": binding["sha256"]}])),
                "independent_skill_review": False,
                "source_code_evidence": [binding],
            })
        self.cards = self.root / "cards.private.json"
        self.data = {"schema": "envloop-sec-excel-transfer-skill-cards-private-v1",
                     "registry_sha256": self.registry_sha, "cards": cards}
        self.save()

    def save(self):
        self.cards.write_text(json.dumps(self.data) + "\n")

    def run_audit(self):
        return validate(registry_path=self.registry, cards_path=self.cards,
                        source_root=self.root,
                        expected_registry_sha=self.registry_sha)

    def test_exact_source_bound_draft_public_receipt_is_field_limited(self):
        receipt = self.run_audit()
        self.assertEqual(receipt["status"], "independent_review_pending")
        self.assertEqual(receipt["exact_final_graphs_covered"], 13)
        self.assertEqual(receipt["nine_fault_guards_verified"], 13)
        self.assertNotIn("private_graph_", json.dumps(receipt))
        self.assertNotIn("0000100000-26-", json.dumps(receipt))

    def test_missing_graph_and_registry_drift_fail_closed(self):
        self.data["cards"][0]["final_graph_reservation"] = "other_graph"
        self.save()
        with self.assertRaisesRegex(ValueError, "exact_final_graphs"):
            self.run_audit()
        self.data["cards"][0]["final_graph_reservation"] = "private_graph_0"
        self.save()
        self.registry.write_bytes(self.registry.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "registry_hash_changed"):
            self.run_audit()

    def test_source_hash_and_fault_guard_fail_closed(self):
        binding = self.data["cards"][0]["source_code_evidence"][0]
        source = self.root / binding["path"]
        source.write_text(source.read_text() + "// source drift\n")
        with self.assertRaisesRegex(ValueError, "source_hash_changed"):
            self.run_audit()
        binding["sha256"] = sha(source.read_bytes())
        self.data["cards"][0]["final_template_sha256"] = sha(ppt.canonical([{
            "path": binding["path"], "sha256": binding["sha256"]}]))
        source.write_text(source.read_text().replace("faults.size !== 9", "faults.size !== 8"))
        binding["sha256"] = sha(source.read_bytes())
        self.data["cards"][0]["final_template_sha256"] = sha(ppt.canonical([{
            "path": binding["path"], "sha256": binding["sha256"]}]))
        self.save()
        with self.assertRaisesRegex(ValueError, "nine_fault_guard_missing"):
            self.run_audit()

    def test_dependency_cycle_and_extra_field_fail_closed(self):
        card = self.data["cards"][0]
        card["dependency_edges"].append([card["causal_skill_atoms"][2],
                                          card["causal_skill_atoms"][0]])
        self.save()
        with self.assertRaisesRegex(ValueError, "dependency_graph_invalid"):
            self.run_audit()
        card["dependency_edges"].pop()
        card["final_answer"] = "forbidden"
        self.save()
        with self.assertRaisesRegex(ValueError, "unexpected_or_missing_field"):
            self.run_audit()

    def test_numeric_review_flag_cannot_impersonate_independent_review(self):
        self.data["cards"][0]["independent_skill_review"] = 1
        self.save()
        with self.assertRaisesRegex(ValueError, "review_flag_invalid"):
            self.run_audit()


if __name__ == "__main__":
    unittest.main()
