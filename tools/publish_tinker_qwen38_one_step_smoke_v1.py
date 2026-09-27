"""Publish only hashes and bounded counts from one private Qwen vision smoke.

This is a training/sampling API compatibility check, never a benchmark score.
The checkpoint URI, sample tokens, model text, and account details stay under
ignored work/ with mode-0600 files.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
HASH = re.compile(r"[0-9a-f]{64}\Z")
CHECKPOINT = re.compile(r"tinker://[^\s/]+/sampler_weights/[^\s/]+\Z")


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def _private(path: Path, root: Path) -> tuple[dict, bytes]:
    _require(path.is_file() and not path.is_symlink() and
             path.resolve().is_relative_to(root.resolve()) and
             path.stat().st_mode & 0o077 == 0,
             "private_smoke_evidence_missing_or_unsafe")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("private_smoke_evidence_invalid_json") from None
    _require(type(value) is dict, "private_smoke_evidence_shape_invalid")
    return value, raw


def build(private_dir: Path) -> dict:
    root = Path(private_dir).resolve()
    _require(root.is_dir() and not root.is_symlink() and
             root.is_relative_to((ROOT / "work").resolve()) and
             root.stat().st_mode & 0o077 == 0,
             "private_smoke_directory_unsafe")
    receipt, receipt_raw = _private(root / "receipt.json", root)
    intent, intent_raw = _private(root / "training-intent.json", root)
    checkpoint, checkpoint_raw = _private(root / "private-checkpoint.json", root)
    base, base_raw = _private(root / "checkpoint-base-model.private.json", root)
    path = checkpoint.get("checkpoint_path")
    local = receipt.get("local_rendering")
    _require(receipt.get("schema") == "tinker-vision-compatibility-v1" and
             receipt.get("model") == "Qwen/Qwen3.8-27B" and
             receipt.get("renderer") == "qwen3_5_disable_thinking" and
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
             "ImageChunk" in local.get("supervised_chunk_types", []) and
             "ImageChunk" in local.get("sampling_chunk_types", []) and
             local.get("loss_weight_sum", 0) > 0 and
             intent.get("model") == receipt["model"] and
             intent.get("rank") == 8 and
             intent.get("steps") == 1 and
             intent.get("single_dispatch_only") is True and
             type(path) is str and CHECKPOINT.fullmatch(path) is not None and
             base.get("schema") ==
             "envloop-tinker-qwen38-one-step-checkpoint-base-v1" and
             base.get("checkpoint_path_sha256") ==
             sha256(path.encode()).hexdigest() and
             base.get("reported_base_model") == receipt["model"] and
             base.get("read_only_model_lookup") is True and
             base.get("new_training_calls") == 0 and
             base.get("new_sampling_calls") == 0,
             "qwen_one_step_smoke_not_verified")
    script = ROOT / "tools/smoke_tinker_vision.py"
    _require(script.is_file() and not script.is_symlink(),
             "smoke_runner_source_missing")
    return {
        "schema": "envloop-qwen38-vision-one-step-public-smoke-v1",
        "status": "paid_train_only_api_compatibility_verified_not_benchmark",
        "model": receipt["model"],
        "renderer": receipt["renderer"],
        "tinker_sdk_version": importlib.metadata.version("tinker"),
        "runner_source_sha256": sha256(script.read_bytes()).hexdigest(),
        "private_receipt_sha256": sha256(receipt_raw).hexdigest(),
        "private_training_intent_sha256": sha256(intent_raw).hexdigest(),
        "private_checkpoint_binding_sha256": sha256(checkpoint_raw).hexdigest(),
        "private_base_model_readback_sha256": sha256(base_raw).hexdigest(),
        "checkpoint_path_sha256": base["checkpoint_path_sha256"],
        "image_supervision_rendered": True,
        "optimizer_steps_completed": 1,
        "sampler_checkpoint_saved": True,
        "post_train_sampling_verified": True,
        "provider_reported_checkpoint_base_model_verified": True,
        "sample_token_count": receipt["sample_tokens"],
        "provider_weight_bytes_verified": False,
        "provider_invoice_usd": None,
        "researcher_campaigns_completed": 0,
        "official_final_model_results": 0,
        "benchmark_score": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    target = args.public_out.absolute()
    _require(target.parent.resolve() == (ROOT / "docs/evidence").resolve() and
             not target.exists() and not target.is_symlink(),
             "fresh_public_evidence_path_required")
    result = build(args.private_dir)
    with target.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({
        "status": result["status"],
        "optimizer_steps_completed": 1,
        "post_train_sampling_verified": True,
        "researcher_campaigns_completed": 0,
        "benchmark_score": None,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
