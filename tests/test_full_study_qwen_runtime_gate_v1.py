"""Fake-only pre-dispatch runtime gate; never opens a provider client."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cursibench import full_study_qwen_runtime_gate_v1 as gate


def _raw(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) +
            "\n").encode()


class QwenRuntimeGateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.work = self.root / "work"
        self.private = self.work / "full-study" / "toy"
        self.private.mkdir(mode=0o700, parents=True)
        self.private.chmod(0o700)
        self.cookbook = self.work / "tinker-cookbook-pinned"
        self.cookbook.mkdir(mode=0o700)
        python = (self.work / "qwen38-training-runtime" / ".venv" /
                  "bin" / "python")
        python.parent.mkdir(parents=True)
        python.write_bytes(b"synthetic interpreter")
        self.uri = "tinker://fake/sampler_weights/checkpoint"
        self.private_files = {
            "receipt.json": {
                "schema": "tinker-vision-compatibility-v1",
                "model": gate.MODEL,
                "optimizer_steps_completed": 1,
                "training_and_sampling_verified": True,
                "checkpoint_saved": True,
                "benchmark_score": None, "cost_usd": None,
                "sample_tokens": 16,
                "local_rendering": {
                    "supervised_chunk_types": ["ImageChunk"],
                    "sampling_chunk_types": ["ImageChunk"]}},
            "training-intent.json": {
                "model": gate.MODEL, "rank": 8, "steps": 1,
                "single_dispatch_only": True},
            "private-checkpoint.json": {
                "checkpoint_path": self.uri},
            "checkpoint-base-model.private.json": {
                "schema":
                    "envloop-tinker-qwen38-one-step-checkpoint-base-v1",
                "checkpoint_path_sha256":
                    sha256(self.uri.encode()).hexdigest(),
                "reported_base_model": gate.MODEL,
                "read_only_model_lookup": True,
                "new_training_calls": 0, "new_sampling_calls": 0,
                "provider_invoice_usd": None,
                "benchmark_score": None},
        }
        raw = {}
        for name, value in self.private_files.items():
            path = self.private / name
            data = _raw(value)
            path.write_bytes(data)
            path.chmod(0o600)
            raw[name] = sha256(data).hexdigest()
        self.source_paths = {
            "tools/verify_qwen38_training_runtime_v1.py": b"verifier",
            "tools/attest_tinker_checkpoint_base_v1.py": b"attester",
            "tools/smoke_tinker_vision.py": b"runner",
            "runtime/qwen38-vision/requirements.lock": b"lock",
        }
        for relative, data in self.source_paths.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.spec = self.root / "runtime/qwen38-vision/runtime-spec.json"
        spec_data = {
            "schema": "cua-qwen38-training-runtime-v1",
            "requirements_lock_sha256": sha256(b"lock").hexdigest(),
            "cookbook": {"commit": gate.COOKBOOK_COMMIT,
                         "package_tree_sha256": "b" * 64},
            "render_probe": {
                "processor_config_sha256": "c" * 64,
                "tokenizer_vocabulary_sha256": "d" * 64},
            "distributions": {
                "tinker": {"version": "0.30.0"},
                "transformers": {"version": "5.5.4"},
                "tokenizers": {"version": "0.22.2"},
                "tml-renderers": {"version": "0.1.0"},
                "torch": {"version": "2.13.0"}},
        }
        self.spec.write_bytes(_raw(spec_data))
        self.spec_sha = sha256(self.spec.read_bytes()).hexdigest()
        self.public = (self.root / "docs/evidence" /
                       "tinker-qwen38-vision-clean-runtime-2026-09-28.json")
        self.public.parent.mkdir(parents=True)
        self.public.write_bytes(_raw({
            "schema": gate.PUBLIC_SCHEMA,
            "status":
                "paid_toy_api_smoke_and_clean_offline_runtime_verified_separately",
            "model": gate.MODEL,
            "runtime_spec_sha256": self.spec_sha,
            "requirements_lock_sha256": sha256(b"lock").hexdigest(),
            "cookbook_commit": gate.COOKBOOK_COMMIT,
            "cookbook_package_tree_sha256": "b" * 64,
            "processor_config_sha256": "c" * 64,
            "tokenizer_vocabulary_sha256": "d" * 64,
            "tinker_sdk_version": "0.30.0",
            "transformers_version": "5.5.4",
            "tokenizers_version": "0.22.2",
            "tml_renderers_version": "0.1.0",
            "torch_version": "2.13.0",
            "runner_source_sha256": sha256(b"runner").hexdigest(),
            "runtime_verifier_source_sha256":
                sha256(b"verifier").hexdigest(),
            "read_only_attester_source_sha256":
                sha256(b"attester").hexdigest(),
            "optimizer_steps_completed": 1,
            "provider_reported_checkpoint_base_model_verified": True,
            "new_readback_training_calls": 0,
            "new_readback_sampling_calls": 0,
            "provider_weight_bytes_verified": False,
            "provider_invoice_usd": None,
            "researcher_campaigns_completed": 0,
            "official_final_model_results": 0,
            "benchmark_score": None,
            "dedicated_runtime_execution": "offline_render_only",
            "sample_token_count": 16,
            "checkpoint_path_sha256":
                sha256(self.uri.encode()).hexdigest(),
            "private_toy_receipt_sha256": raw["receipt.json"],
            "private_training_intent_sha256": raw["training-intent.json"],
            "private_checkpoint_binding_sha256":
                raw["private-checkpoint.json"],
            "private_base_model_readback_sha256":
                raw["checkpoint-base-model.private.json"],
        }))

    def fake_verifier(self, command, *, cwd, env, capture_output,
                      text, timeout, check):
        self.assertEqual(Path(command[0]), self.work /
                         "qwen38-training-runtime/.venv/bin/python")
        self.assertEqual(Path(cwd), self.root)
        self.assertNotIn("TINKER_API_KEY", env)
        self.assertEqual(env["HF_HUB_OFFLINE"], "1")
        self.assertTrue(capture_output and text and not check)
        self.assertEqual(timeout, 180)
        return SimpleNamespace(returncode=0, stdout=json.dumps({
            "status": "offline_runtime_verified",
            "runtime_spec_sha256": self.spec_sha,
            "model": gate.MODEL, "provider_calls": 0,
            "benchmark_score": None}), stderr="")

    def test_source_and_private_toy_audit_returns_no_authority(self):
        with patch.dict(os.environ, {"TINKER_API_KEY": "synthetic-test-key"}):
            with patch.object(gate.subprocess, "run",
                              side_effect=self.fake_verifier):
                result = gate.validate(
                    repo_root=self.root, study_plan_sha256="a" * 64,
                    private_toy_dir=self.private)
        self.assertEqual(result["status"],
                         "pre_dispatch_runtime_evidence_verified")
        self.assertFalse(result["dispatch_authorized"])
        self.assertEqual(result["provider_calls"], 0)
        self.assertNotIn(self.uri, json.dumps(result))

    def test_private_mode_or_model_drift_fails_before_verifier(self):
        (self.private / "training-intent.json").chmod(0o644)
        with patch.object(gate.subprocess, "run",
                          side_effect=AssertionError("verifier should not run")):
            with self.assertRaises(gate.RuntimeGateError):
                gate.validate(repo_root=self.root,
                              study_plan_sha256="a" * 64,
                              private_toy_dir=self.private)

    def test_verifier_failure_cannot_grant_dispatch(self):
        with patch.object(gate.subprocess, "run", return_value=
                          SimpleNamespace(returncode=1, stdout="{}")):
            with self.assertRaisesRegex(gate.RuntimeGateError,
                                        "dedicated_verifier_failed"):
                gate.validate(repo_root=self.root,
                              study_plan_sha256="a" * 64,
                              private_toy_dir=self.private)

    def test_pre_dispatch_rechecks_evidence_and_active_worker(self):
        receipt = {
            "status": "pre_dispatch_runtime_evidence_verified",
            "study_plan_sha256": "a" * 64,
            "runtime_spec_sha256": "b" * 64,
            "toy_public_receipt_sha256": "c" * 64,
            "provider_calls": 0,
            "dispatch_authorized": False,
            "benchmark_score": None,
        }
        with patch.object(gate, "validate", return_value=receipt) as check:
            with patch.object(gate, "assert_active_worker") as worker:
                binding = gate.pre_dispatch(
                    repo_root=self.root, study_plan_sha256="a" * 64)
        self.assertEqual(check.call_args.kwargs["private_toy_dir"],
                         self.root / gate.PRIVATE_TOY_RELATIVE)
        worker.assert_called_once_with(self.root)
        self.assertEqual(binding["runtime_spec_sha256"], "b" * 64)
        self.assertEqual(binding["toy_public_receipt_sha256"], "c" * 64)
        self.assertEqual(binding["runtime_gate_source_sha256"],
                         sha256(Path(gate.__file__).read_bytes()).hexdigest())

    def test_pre_dispatch_rejects_forged_runtime_receipt(self):
        forged = {
            "status": "pre_dispatch_runtime_evidence_verified",
            "study_plan_sha256": "a" * 64,
            "runtime_spec_sha256": "b" * 64,
            "toy_public_receipt_sha256": "c" * 64,
            "provider_calls": 1,
            "dispatch_authorized": True,
            "benchmark_score": 1,
        }
        with patch.object(gate, "validate", return_value=forged):
            with patch.object(gate, "assert_active_worker") as worker:
                with self.assertRaisesRegex(gate.RuntimeGateError,
                                            "pre_dispatch_receipt_invalid"):
                    gate.pre_dispatch(repo_root=self.root,
                                      study_plan_sha256="a" * 64)
        worker.assert_not_called()

    def test_active_worker_rejects_general_interpreter_before_imports(self):
        with self.assertRaisesRegex(gate.RuntimeGateError,
                                    "active_worker_not_dedicated_venv"):
            gate.assert_active_worker(self.root)

    def test_active_worker_accepts_only_root_packages_and_pythonpath(self):
        source = (self.root / "src/cursibench" /
                  "full_study_qwen_runtime_gate_v1.py")
        source.parent.mkdir(parents=True)
        source.write_bytes(b"synthetic root gate")
        venv = self.work / "qwen38-training-runtime/.venv"
        packages = {}
        for name in gate.CRITICAL_PACKAGES:
            origin = (venv / "lib/python3.14/site-packages" / name /
                      "__init__.py")
            origin.parent.mkdir(parents=True, exist_ok=True)
            origin.write_bytes(b"synthetic package")
            packages[name] = origin
        def spec(name):
            return SimpleNamespace(origin=str(packages[name]))
        with patch.object(gate, "__file__", str(source)), \
             patch.object(gate.sys, "executable", str(venv / "bin/python")), \
             patch.object(gate.sys, "prefix", str(venv)), \
             patch.object(gate.site, "ENABLE_USER_SITE", False), \
             patch.object(gate, "find_spec", side_effect=spec), \
             patch.dict(os.environ, {"PYTHONPATH": str(self.root / "src")}):
            gate.assert_active_worker(self.root)
            os.environ["PYTHONPATH"] = str(self.root / "src") + \
                os.pathsep + "/tmp/foreign-overlay"
            with self.assertRaisesRegex(gate.RuntimeGateError,
                                        "pythonpath_overlay_forbidden"):
                gate.assert_active_worker(self.root)
            os.environ["PYTHONPATH"] = str(self.root / "src")
            foreign = self.root / "foreign-package.py"
            foreign.write_bytes(b"synthetic overlay")
            packages["tinker"] = foreign
            with self.assertRaisesRegex(gate.RuntimeGateError,
                                        "active_package_origin_invalid"):
                gate.assert_active_worker(self.root)


if __name__ == "__main__":
    unittest.main()
