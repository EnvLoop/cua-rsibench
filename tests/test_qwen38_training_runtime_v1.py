"""Offline provenance and fake read-only checkpoint tests; no provider calls."""

from __future__ import annotations

from hashlib import sha256
import base64
import csv
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import attest_tinker_checkpoint_base_v1 as base
from tools import publish_tinker_qwen38_runtime_v1 as publisher
from tools import verify_qwen38_training_runtime_v1 as runtime


class RuntimeSpecTests(unittest.TestCase):
    def test_tree_digest_detects_content_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "example.py").write_text("version = 1\n")
            first = runtime._tree_sha(root)
            (root / "example.py").write_text("version = 2\n")
            second = runtime._tree_sha(root)
            self.assertNotEqual(first, second)
            (root / "__pycache__").mkdir()
            (root / "__pycache__" / "example.pyc").write_bytes(b"cache")
            self.assertEqual(runtime._tree_sha(root), second)

    def test_exact_canonical_spec_and_drift_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime-spec.json"
            frozen = {"schema": runtime.SPEC_SCHEMA,
                      "source_sha256": "a" * 64}
            path.write_bytes(runtime._canonical(frozen))
            with patch.object(runtime, "snapshot", return_value=frozen):
                result = runtime.verify(path, Path(directory))
            self.assertEqual(result["status"], "offline_runtime_verified")
            self.assertEqual(result["provider_calls"], 0)
            with patch.object(runtime, "snapshot", return_value={
                    **frozen, "source_sha256": "b" * 64}):
                with self.assertRaisesRegex(runtime.RuntimeErrorCode,
                                            "snapshot_or_render_changed"):
                    runtime.verify(path, Path(directory))

    def test_relocation_normalizes_only_verified_console_shebang(self):
        class Distribution:
            metadata = {"Name": "fakepkg"}
            version = "1.0"

            def __init__(self, site, record):
                self.site = site
                self.record = record

            def read_text(self, name):
                return ("Name: fakepkg\nVersion: 1.0\n" if
                        name == "METADATA" else self.record)

            def locate_file(self, relative):
                return self.site / relative

        def one(prefix):
            site = prefix / "lib/python3.14/site-packages"
            package = site / "fakepkg/__init__.py"
            launcher = prefix / "bin/fakepkg"
            package.parent.mkdir(parents=True)
            launcher.parent.mkdir(parents=True)
            package.write_bytes(b"version = 1\n")
            launcher.write_bytes(
                ("#!" + str(prefix / "bin/python") + "\n").encode() +
                b"print('ok')\n")
            def row(relative, path):
                raw = path.read_bytes()
                digest = base64.urlsafe_b64encode(
                    sha256(raw).digest()).rstrip(b"=").decode()
                return [relative, "sha256=" + digest, str(len(raw))]
            stream = io.StringIO()
            writer = csv.writer(stream)
            writer.writerow(row("fakepkg/__init__.py", package))
            writer.writerow(row("../../../bin/fakepkg", launcher))
            writer.writerow(["fakepkg-1.0.dist-info/RECORD", "", ""])
            dist = Distribution(site, stream.getvalue())
            with patch.object(runtime, "EXPECTED_VERSIONS", {
                    "fakepkg": "1.0"}), \
                 patch.object(runtime.importlib.metadata,
                              "distributions", return_value=[dist]), \
                 patch.object(runtime.sys, "prefix", str(prefix)):
                first = runtime._distribution_snapshot()
            return first, launcher, dist

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, _, _ = one(root / "short")
            second, launcher, dist = one(root / "a-much-longer-venv-name")
            self.assertEqual(first, second)
            launcher.write_bytes(launcher.read_bytes() + b"# tampered\n")
            with patch.object(runtime, "EXPECTED_VERSIONS", {
                    "fakepkg": "1.0"}), \
                 patch.object(runtime.importlib.metadata,
                              "distributions", return_value=[dist]), \
                 patch.object(runtime.sys, "prefix",
                              str(root / "a-much-longer-venv-name")):
                with self.assertRaisesRegex(runtime.RuntimeErrorCode,
                                            "file_missing_or_changed"):
                    runtime._distribution_snapshot()
            rows = list(csv.reader(io.StringIO(dist.record)))
            changed = launcher.read_bytes()
            rows[1][1] = "sha256=" + base64.urlsafe_b64encode(
                sha256(changed).digest()).rstrip(b"=").decode()
            rows[1][2] = str(len(changed))
            stream = io.StringIO()
            csv.writer(stream).writerows(rows)
            dist.record = stream.getvalue()
            with patch.object(runtime, "EXPECTED_VERSIONS", {
                    "fakepkg": "1.0"}), \
                 patch.object(runtime.importlib.metadata,
                              "distributions", return_value=[dist]), \
                 patch.object(runtime.sys, "prefix",
                              str(root / "a-much-longer-venv-name")):
                self.assertNotEqual(first,
                                    runtime._distribution_snapshot())


class CheckpointBaseReadbackTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "private"
        self.root.mkdir(mode=0o700)
        self.uri = "tinker://fake/sampler_weights/checkpoint"
        self.write("private-checkpoint.json", {
            "checkpoint_path": self.uri})
        self.write("receipt.json", {
            "schema": "tinker-vision-compatibility-v1",
            "model": base.MODEL, "paid_training_requested": True,
            "optimizer_steps_completed": 1,
            "checkpoint_saved": True,
            "training_and_sampling_verified": True,
            "benchmark_score": None, "cost_usd": None})

    def write(self, name, value):
        path = self.root / name
        path.write_bytes((json.dumps(value, sort_keys=True) + "\n").encode())
        path.chmod(0o600)

    def test_one_lookup_writes_private_digest_without_sampling(self):
        calls = []
        class FakeService:
            def create_sampling_client(self, **kwargs):
                calls.append(("client", kwargs))
                return SimpleNamespace(get_base_model=lambda: base.MODEL)
            def close(self, status):
                calls.append(("close", status))
                return SimpleNamespace(result=lambda timeout: None)
        public = base.attest(self.root, service_factory=FakeService)
        self.assertEqual(calls, [
            ("client", {"model_path": self.uri}),
            ("close", "success")])
        path = self.root / "checkpoint-base-model.private.json"
        self.assertEqual(path.stat().st_mode & 0o077, 0)
        self.assertEqual(public["base_receipt_sha256"],
                         sha256(path.read_bytes()).hexdigest())
        self.assertNotIn(self.uri, str(public))
        self.assertIsNone(public["provider_invoice_usd"])
        with self.assertRaisesRegex(base.CheckpointAttestationError,
                                    "already_exists"):
            base.attest(self.root, service_factory=FakeService)

    def test_wrong_provider_base_fails_without_attestation(self):
        class WrongService:
            def create_sampling_client(self, **_kwargs):
                return SimpleNamespace(get_base_model=lambda: "wrong")
            def close(self, _status):
                return SimpleNamespace(result=lambda timeout: None)
        with self.assertRaisesRegex(base.CheckpointAttestationError,
                                    "reported_base_model_changed"):
            base.attest(self.root, service_factory=WrongService)
        self.assertFalse((self.root /
                          "checkpoint-base-model.private.json").exists())


class PublicToyReceiptTests(unittest.TestCase):
    def test_private_checkpoint_uri_never_enters_public_projection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private = root / "private"
            private.mkdir(mode=0o700)
            uri = "tinker://fake/sampler_weights/secret-checkpoint"
            values = {
                "private-checkpoint.json": {"checkpoint_path": uri},
                "training-intent.json": {
                    "model": runtime.MODEL, "rank": 8, "steps": 1,
                    "single_dispatch_only": True},
                "receipt.json": {
                    "schema": "tinker-vision-compatibility-v1",
                    "model": runtime.MODEL,
                    "renderer": runtime.RENDERER,
                    "paid_training_requested": True,
                    "optimizer_steps_completed": 1,
                    "training_and_sampling_verified": True,
                    "checkpoint_saved": True,
                    "benchmark_score": None, "cost_usd": None,
                    "sample_tokens": 16, "sample_sha256": "a" * 64,
                    "local_rendering": {
                        "image_processor": runtime.PROCESSOR,
                        "supervised_chunk_types": ["ImageChunk"],
                        "sampling_chunk_types": ["ImageChunk"],
                        "loss_weight_sum": 1.0}},
                "checkpoint-base-model.private.json": {
                    "schema": base.SCHEMA,
                    "checkpoint_path_sha256": sha256(uri.encode()).hexdigest(),
                    "reported_base_model": runtime.MODEL,
                    "read_only_model_lookup": True,
                    "new_training_calls": 0, "new_sampling_calls": 0,
                    "provider_invoice_usd": None,
                    "benchmark_score": None},
            }
            for name, value in values.items():
                path = private / name
                path.write_bytes((json.dumps(value, sort_keys=True) +
                                  "\n").encode())
                path.chmod(0o600)
            spec = root / "runtime-spec.json"
            spec.write_bytes(runtime._canonical({
                "schema": runtime.SPEC_SCHEMA,
                "render_probe": {"model": runtime.MODEL,
                                 "processor_config_sha256": "b" * 64,
                                 "tokenizer_vocabulary_sha256": "c" * 64},
                "requirements_lock_sha256": "d" * 64,
                "cookbook": {"commit": runtime.COOKBOOK_COMMIT,
                             "package_tree_sha256": "e" * 64},
                "distributions": {name: {"version": version} for
                    name, version in runtime.EXPECTED_VERSIONS.items()},
            }))
            with patch.object(publisher.runtime, "verify", return_value={
                "status": "offline_runtime_verified",
                "runtime_spec_sha256": sha256(spec.read_bytes()).hexdigest(),
                "provider_calls": 0}):
                public = publisher.build(private, spec, root)
            self.assertNotIn(uri, json.dumps(public))
            self.assertEqual(public["optimizer_steps_completed"], 1)
            self.assertEqual(public["researcher_campaigns_completed"], 0)
            self.assertIsNone(public["provider_invoice_usd"])


if __name__ == "__main__":
    unittest.main()
