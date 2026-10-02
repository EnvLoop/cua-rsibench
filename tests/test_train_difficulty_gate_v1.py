"""Boundary tests for the nonfinal, saved-state difficulty screen."""

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from cursibench.train_difficulty_gate_v1 import evaluate


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def marker(value):
    return digest(value.encode())


class TrainDifficultyGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.profile = marker("shared-v066-profile")
        self.verifier = marker("read-only-verifier")
        self.actor_config = {"base_qwen": marker("qwen-config"),
                             "stronger_reference": marker("astra-config")}

    def put(self, name, value):
        raw = (json.dumps(value, sort_keys=True).encode() if isinstance(value, dict)
               else value)
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return {"path": name, "sha256": digest(raw)}

    def fixture(self, base, strong, *, controls_pass=True, complexity=4,
                invalid_index=None, reference_valid_actions=3):
        tasks = []
        attempts = []
        for index in range(8):
            tid = marker(f"train-task-{index}")
            family = marker(f"family-{index // 4}")
            control = {
                "schema": "cua-train-difficulty-control-v1", "partition": "train",
                "task_sha256": tid, "verifier_sha256": self.verifier,
                "positive_score": 1 if controls_pass or index else 0,
                "near_miss_score": 0, "cold_reset_score": 0,
                "positive_no_regression": True,
                "near_miss_rejected_for_intended_reason": True,
                "positive_saved_state_sha256": marker(f"pos-{index}"),
                "near_miss_saved_state_sha256": marker(f"near-{index}"),
                "cold_reset_saved_state_sha256": marker(f"reset-{index}"),
            }
            tasks.append({
                "task_sha256": tid, "source_family_sha256": family,
                "workflow_sha256": marker("workflow-a"),
                "verifier_sha256": self.verifier,
                "complexity": {"target_fields": complexity, "causal_steps": 2,
                               "distractor_objects": 3, "screen_transitions": 2},
                "control_receipt": self.put(f"controls/{index}.json", control),
            })
            for actor, score in (("base_qwen", base[index]),
                                 ("stronger_reference", strong[index])):
                sequence = 0
                if invalid_index == index and actor == "base_qwen":
                    invalid = {
                        "schema": "cua-train-difficulty-attempt-v1",
                        "partition": "train", "task_sha256": tid, "actor": actor,
                        "action_profile_sha256": self.profile,
                        "actor_configuration_sha256": self.actor_config[actor],
                        "verifier_sha256": self.verifier,
                        "status": "infrastructure_invalid", "score": None,
                        "partial_targets": None, "failure_class": "transport",
                        "action_attempts": 1, "valid_actions": 1, "wall_seconds": 5,
                        "observation_trace_sha256": marker("observation"),
                        "action_trace_sha256": marker("action"),
                        "reset_receipt_sha256": marker("reset receipt"),
                        "reset_verified": True,
                    }
                    attempts.append({"task_sha256": tid, "actor": actor,
                                     "sequence": 0,
                                     "receipt": self.put(f"attempts/{index}-{actor}-invalid.json",
                                                         invalid)})
                    sequence = 1
                saved_ref = self.put(f"saved/{index}-{actor}.bin",
                                     f"persisted-{index}-{actor}-{score}".encode())
                verifier = {
                    "schema": "cua-train-difficulty-verifier-v1",
                    "partition": "train", "producer": "independent_evaluator",
                    "task_sha256": tid, "verifier_sha256": self.verifier,
                    "saved_state_sha256": saved_ref["sha256"], "score": score,
                    "partial_targets": 4 if score else 1, "total_targets": 4,
                    "no_regression": True, "model_visible": False,
                }
                verifier_ref = self.put(f"verifiers/{index}-{actor}.json", verifier)
                attempt = {
                    "schema": "cua-train-difficulty-attempt-v1",
                    "partition": "train", "task_sha256": tid, "actor": actor,
                    "action_profile_sha256": self.profile,
                    "actor_configuration_sha256": self.actor_config[actor],
                    "verifier_sha256": self.verifier, "status": "scored",
                    "score": score, "partial_targets": 4 if score else 1,
                    "total_targets": 4, "no_regression": True,
                    "saved_state": saved_ref,
                    "saved_state_sha256": saved_ref["sha256"],
                    "independent_verifier_receipt": verifier_ref,
                    "action_attempts": 3,
                    "valid_actions": (reference_valid_actions
                                      if actor == "stronger_reference" else 3),
                    "wall_seconds": 10,
                    "observation_trace_sha256": marker("observation"),
                    "action_trace_sha256": marker("action"),
                    "reset_receipt_sha256": marker("reset receipt"),
                    "reset_verified": True, "stop_reason": "finish",
                }
                attempts.append({"task_sha256": tid, "actor": actor,
                                 "sequence": sequence,
                                 "receipt": self.put(f"attempts/{index}-{actor}.json", attempt)})
        manifest = {
            "schema": "cua-train-difficulty-input-v1", "partition": "train",
            "cell_id": "powerpoint-web", "action_profile_sha256": self.profile,
            "actors": {
                actor: {"model_id": ("Qwen/Qwen3.8-27B" if actor == "base_qwen"
                                      else "gpt-6-astra"),
                        "configuration_sha256": self.actor_config[actor],
                        "prompt_sha256": marker(f"{actor}-prompt"),
                        "provider_route_sha256": marker(f"{actor}-route"),
                        "task_visible_only": True}
                for actor in ("base_qwen", "stronger_reference")},
            "max_actions": 80, "max_wall_seconds": 1800,
            "minimum_complexity": {"target_fields": 4, "causal_steps": 2,
                                   "distractor_objects": 3, "screen_transitions": 2},
            "tasks": tasks, "attempts": attempts,
        }
        return manifest

    def run_manifest(self, manifest):
        path = self.root / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return evaluate(path)

    def test_discriminative_train_screen_is_not_an_official_result(self):
        report = self.run_manifest(self.fixture(
            [1, 1, 0, 0, 0, 0, 0, 0], [1, 1, 1, 1, 1, 1, 0, 0]))
        row = report["workflow_screens"][0]
        self.assertEqual(row["decision"], "discriminative_train_screen")
        self.assertEqual((row["base_successes"], row["stronger_reference_successes"]),
                         (2, 6))
        self.assertEqual(report["official_final_admissions"], 0)
        self.assertNotIn(marker("train-task-0"), json.dumps(report))

    def test_trivial_and_reference_floor_are_excluded(self):
        for base, strong, expected in (
            ([1] * 8, [1] * 8, "exclude_workflow_ceiling"),
            ([0] * 8, [0] * 8, "exclude_workflow_floor"),
        ):
            with self.subTest(expected=expected):
                report = self.run_manifest(self.fixture(base, strong))
                self.assertEqual(report["workflow_screens"][0]["decision"], expected)

    def test_failed_controls_and_nonrepresentative_train_complexity_hold(self):
        base = [1, 1, 0, 0, 0, 0, 0, 0]
        strong = [1, 1, 1, 1, 1, 1, 0, 0]
        failed = self.run_manifest(self.fixture(base, strong, controls_pass=False))
        self.assertEqual(failed["workflow_screens"][0]["decision"],
                         "exclude_failed_control_source_families")
        shallow = self.run_manifest(self.fixture(base, strong, complexity=1))
        self.assertEqual(shallow["workflow_screens"][0]["decision"],
                         "hold_nonrepresentative_train_complexity")

    def test_infrastructure_retry_is_counted_separately(self):
        report = self.run_manifest(self.fixture(
            [1, 1, 0, 0, 0, 0, 0, 0], [1, 1, 1, 1, 1, 1, 0, 0], invalid_index=0))
        row = report["workflow_screens"][0]
        self.assertEqual(row["infrastructure_invalid_attempts"], 1)
        self.assertEqual(row["paired_train_tasks"], 8)
        self.assertEqual(row["base_successes"], 2)

    def test_reference_action_invalidity_holds_despite_aggregate_success(self):
        report = self.run_manifest(self.fixture(
            [1, 1, 0, 0, 0, 0, 0, 0], [1, 1, 1, 1, 1, 1, 0, 0],
            reference_valid_actions=2))
        row = report["workflow_screens"][0]
        self.assertEqual(row["decision"], "hold_interface_or_budget")
        self.assertLess(row["actor_diagnostics"]["stronger_reference"]
                        ["valid_action_fraction"], 0.85)

    def test_unresolved_infrastructure_is_not_a_model_zero(self):
        manifest = self.fixture(
            [1, 1, 0, 0, 0, 0, 0, 0], [1, 1, 1, 1, 1, 1, 0, 0],
            invalid_index=0)
        manifest["attempts"] = [entry for entry in manifest["attempts"]
                                if not (entry["task_sha256"] == marker("train-task-0")
                                        and entry["actor"] == "base_qwen"
                                        and entry["sequence"] == 1)]
        row = self.run_manifest(manifest)["workflow_screens"][0]
        self.assertEqual(row["paired_train_tasks"], 7)
        self.assertEqual(row["base_successes"], 1)
        self.assertEqual(row["decision"], "insufficient_train_evidence")

    def test_final_partition_and_tampered_saved_state_fail_closed(self):
        manifest = self.fixture([0] * 8, [1] * 8)
        final = copy.deepcopy(manifest)
        final["partition"] = "final"
        with self.assertRaisesRegex(ValueError, "train-only"):
            self.run_manifest(final)
        saved = self.root / "saved/0-base_qwen.bin"
        saved.write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.run_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
