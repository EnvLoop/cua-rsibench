"""Publish a field-limited clean-runtime receipt for the second toy smoke.

Private checkpoint URI, sample tokens, provider account data, and task data
never enter the public output. The toy operation is not a campaign or score.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

from tools import verify_qwen38_training_runtime_v1 as runtime


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "envloop-qwen38-clean-runtime-toy-smoke-public-v1"
CHECKPOINT = re.compile(r"tinker://[^\s/]+/sampler_weights/[^\s/]+\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")


class PublicationError(ValueError):
    """Fixed public failure labels without private URI or provider body."""


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise PublicationError(code)


def _private(path: Path, root: Path) -> tuple[dict, bytes]:
    _require(path.is_file() and not path.is_symlink() and
             path.resolve().is_relative_to(root.resolve()) and
             path.stat().st_mode & 0o077 == 0 and
             0 < path.stat().st_size <= 1_000_000,
             "toy_private_evidence_missing_or_unsafe")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PublicationError("toy_private_json_invalid") from None
    _require(type(value) is dict, "toy_private_object_required")
    return value, raw


def build(private_dir: Path, spec_path: Path,
          cookbook_dir: Path) -> dict:
    root = Path(private_dir).absolute()
    _require(root.is_dir() and not root.is_symlink() and
             root.stat().st_mode & 0o077 == 0,
             "toy_private_directory_unsafe")
    verified = runtime.verify(spec_path, cookbook_dir)
    _require(verified["status"] == "offline_runtime_verified" and
             verified["provider_calls"] == 0,
             "toy_runtime_not_verified")
    spec_file = Path(spec_path)
    _require(spec_file.is_file() and not spec_file.is_symlink(),
             "toy_runtime_spec_changed")
    spec_raw = spec_file.read_bytes()
    try:
        spec = json.loads(spec_raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PublicationError("toy_runtime_spec_changed") from None
    _require(sha256(spec_raw).hexdigest() ==
             verified["runtime_spec_sha256"] and
             spec.get("schema") == runtime.SPEC_SCHEMA and
             spec.get("render_probe", {}).get("model") == runtime.MODEL,
             "toy_runtime_spec_changed")
    receipt, receipt_raw = _private(root / "receipt.json", root)
    intent, intent_raw = _private(root / "training-intent.json", root)
    checkpoint, checkpoint_raw = _private(
        root / "private-checkpoint.json", root)
    base, base_raw = _private(
        root / "checkpoint-base-model.private.json", root)
    uri = checkpoint.get("checkpoint_path")
    local = receipt.get("local_rendering")
    _require(receipt.get("schema") == "tinker-vision-compatibility-v1" and
             receipt.get("model") == runtime.MODEL and
             receipt.get("renderer") == runtime.RENDERER and
             receipt.get("paid_training_requested") is True and
             receipt.get("optimizer_steps_completed") == 1 and
             receipt.get("training_and_sampling_verified") is True and
             receipt.get("checkpoint_saved") is True and
             receipt.get("benchmark_score") is None and
             receipt.get("cost_usd") is None and
             type(receipt.get("sample_tokens")) is int and
             0 < receipt["sample_tokens"] <= 48 and
             type(receipt.get("sample_sha256")) is str and
             HASH.fullmatch(receipt["sample_sha256"]) is not None and
             type(local) is dict and
             local.get("image_processor") == runtime.PROCESSOR and
             "ImageChunk" in local.get("supervised_chunk_types", []) and
             "ImageChunk" in local.get("sampling_chunk_types", []) and
             local.get("loss_weight_sum", 0) > 0 and
             intent.get("model") == runtime.MODEL and
             intent.get("rank") == 8 and
             intent.get("steps") == 1 and
             intent.get("single_dispatch_only") is True and
             type(uri) is str and CHECKPOINT.fullmatch(uri) is not None and
             base.get("schema") ==
             "envloop-tinker-qwen38-one-step-checkpoint-base-v1" and
             base.get("checkpoint_path_sha256") ==
             sha256(uri.encode()).hexdigest() and
             base.get("reported_base_model") == runtime.MODEL and
             base.get("read_only_model_lookup") is True and
             base.get("new_training_calls") == 0 and
             base.get("new_sampling_calls") == 0 and
             base.get("provider_invoice_usd") is None and
             base.get("benchmark_score") is None,
             "toy_train_sample_or_base_readback_invalid")
    return {
        "schema": SCHEMA,
        "status": "paid_toy_api_smoke_and_clean_offline_runtime_verified_separately",
        "paid_toy_execution_environment":
            "isolated_transformers_5_5_4_pythonpath_overlay",
        "dedicated_runtime_execution": "offline_render_only",
        "model": runtime.MODEL,
        "renderer": runtime.RENDERER,
        "image_processor": runtime.PROCESSOR,
        "runtime_spec_sha256": verified["runtime_spec_sha256"],
        "requirements_lock_sha256": spec["requirements_lock_sha256"],
        "cookbook_commit": spec["cookbook"]["commit"],
        "cookbook_package_tree_sha256": spec["cookbook"][
            "package_tree_sha256"],
        "tinker_sdk_version": spec["distributions"]["tinker"]["version"],
        "transformers_version": spec["distributions"]["transformers"]["version"],
        "tokenizers_version": spec["distributions"]["tokenizers"]["version"],
        "tml_renderers_version": spec["distributions"]["tml-renderers"]["version"],
        "torch_version": spec["distributions"]["torch"]["version"],
        "processor_config_sha256": spec["render_probe"][
            "processor_config_sha256"],
        "tokenizer_vocabulary_sha256": spec["render_probe"][
            "tokenizer_vocabulary_sha256"],
        "runner_source_sha256": sha256((ROOT /
            "tools/smoke_tinker_vision.py").read_bytes()).hexdigest(),
        "runtime_verifier_source_sha256": sha256((ROOT /
            "tools/verify_qwen38_training_runtime_v1.py").read_bytes()).hexdigest(),
        "read_only_attester_source_sha256": sha256((ROOT /
            "tools/attest_tinker_checkpoint_base_v1.py").read_bytes()).hexdigest(),
        "private_toy_receipt_sha256": sha256(receipt_raw).hexdigest(),
        "private_training_intent_sha256": sha256(intent_raw).hexdigest(),
        "private_checkpoint_binding_sha256": sha256(
            checkpoint_raw).hexdigest(),
        "private_base_model_readback_sha256": sha256(base_raw).hexdigest(),
        "checkpoint_path_sha256": base["checkpoint_path_sha256"],
        "optimizer_steps_completed": 1,
        "sample_token_count": receipt["sample_tokens"],
        "post_train_sampling_verified": True,
        "provider_reported_checkpoint_base_model_verified": True,
        "training_intent_mode_corrected_to_0600_without_byte_change": True,
        "new_readback_training_calls": 0,
        "new_readback_sampling_calls": 0,
        "provider_weight_bytes_verified": False,
        "provider_invoice_usd": None,
        "researcher_campaigns_completed": 0,
        "official_final_model_results": 0,
        "benchmark_score": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--cookbook-dir", type=Path, required=True)
    parser.add_argument("--spec", type=Path, default=ROOT /
                        "runtime/qwen38-vision/runtime-spec.json")
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    target = args.public_out.absolute()
    _require(target.parent.resolve() == (ROOT / "docs/evidence").resolve() and
             not target.exists() and not target.is_symlink(),
             "toy_public_output_must_be_new_evidence_file")
    result = build(args.private_dir, args.spec, args.cookbook_dir)
    with target.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"],
                      "runtime_spec_sha256": result[
                          "runtime_spec_sha256"],
                      "researcher_campaigns_completed": 0,
                      "benchmark_score": None}, sort_keys=True))


if __name__ == "__main__":
    main()
