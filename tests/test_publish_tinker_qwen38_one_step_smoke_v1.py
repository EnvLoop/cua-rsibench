"""A toy Qwen smoke cannot become a full-study result or leak a URI."""

from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest

from tools import publish_tinker_qwen38_one_step_smoke_v1 as publish


class PublishQwenSmokeTests(unittest.TestCase):
    def test_private_checkpoint_path_stays_out_of_public_projection(self):
        with tempfile.TemporaryDirectory(dir=publish.ROOT / "work") as scratch:
            root = Path(scratch)
            root.chmod(0o700)
            path = "tinker://fake/sampler_weights/one-step"
            local = {"supervised_chunk_types": ["ImageChunk"],
                     "sampling_chunk_types": ["ImageChunk"],
                     "loss_weight_sum": 1.0}
            values = {
                "receipt.json": {
                    "schema": "tinker-vision-compatibility-v1",
                    "model": "Qwen/Qwen3.8-27B",
                    "renderer": "qwen3_5_disable_thinking",
                    "paid_training_requested": True,
                    "optimizer_steps_completed": 1,
                    "training_and_sampling_verified": True,
                    "checkpoint_saved": True,
                    "benchmark_score": None, "cost_usd": None,
                    "sample_tokens": 5, "sample_sha256": "a" * 64,
                    "local_rendering": local},
                "training-intent.json": {
                    "model": "Qwen/Qwen3.8-27B", "rank": 8, "steps": 1,
                    "single_dispatch_only": True},
                "private-checkpoint.json": {"checkpoint_path": path},
                "checkpoint-base-model.private.json": {
                    "schema": "envloop-tinker-qwen38-one-step-checkpoint-base-v1",
                    "checkpoint_path_sha256": publish.sha256(path.encode()).hexdigest(),
                    "reported_base_model": "Qwen/Qwen3.8-27B",
                    "read_only_model_lookup": True,
                    "new_training_calls": 0, "new_sampling_calls": 0},
            }
            for name, value in values.items():
                file = root / name
                file.write_text(json.dumps(value))
                file.chmod(0o600)
            result = publish.build(root)
            self.assertNotIn(path, json.dumps(result))
            self.assertEqual(result["researcher_campaigns_completed"], 0)
            self.assertIsNone(result["benchmark_score"])
            values["receipt.json"]["benchmark_score"] = 1
            (root / "receipt.json").write_text(json.dumps(values["receipt.json"]))
            with self.assertRaisesRegex(ValueError,
                                        "qwen_one_step_smoke_not_verified"):
                publish.build(root)


if __name__ == "__main__":
    unittest.main()
