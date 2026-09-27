"""One explicit read-only Tinker checkpoint/base-model lookup.

The checkpoint URI remains private. This never calls train, optim_step, or
sample and cannot produce a benchmark score or a provider invoice.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Callable


MODEL = "Qwen/Qwen3.8-27B"
SCHEMA = "envloop-tinker-qwen38-one-step-checkpoint-base-v1"
CHECKPOINT = re.compile(r"tinker://[^\s/]+/sampler_weights/[^\s/]+\Z")


class CheckpointAttestationError(ValueError):
    """Fixed failure labels; private URI and provider body are never exposed."""


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise CheckpointAttestationError(code)


def _private(path: Path, root: Path) -> dict:
    _require(path.is_file() and not path.is_symlink() and
             path.resolve().is_relative_to(root.resolve()) and
             path.stat().st_mode & 0o077 == 0 and
             0 < path.stat().st_size <= 1_000_000,
             "checkpoint_private_evidence_missing_or_unsafe")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise CheckpointAttestationError(
            "checkpoint_private_json_invalid") from None
    _require(type(value) is dict, "checkpoint_private_json_invalid")
    return value


def attest(private_dir: Path, service_factory: Callable | None = None) -> dict:
    root = Path(private_dir).absolute()
    _require(root.is_dir() and not root.is_symlink() and
             root.stat().st_mode & 0o077 == 0,
             "checkpoint_private_directory_unsafe")
    output = root / "checkpoint-base-model.private.json"
    _require(not output.exists() and not output.is_symlink(),
             "checkpoint_base_attestation_already_exists")
    checkpoint = _private(root / "private-checkpoint.json", root)
    receipt = _private(root / "receipt.json", root)
    uri = checkpoint.get("checkpoint_path")
    _require(type(uri) is str and CHECKPOINT.fullmatch(uri) is not None and
             receipt.get("schema") == "tinker-vision-compatibility-v1" and
             receipt.get("model") == MODEL and
             receipt.get("paid_training_requested") is True and
             receipt.get("optimizer_steps_completed") == 1 and
             receipt.get("checkpoint_saved") is True and
             receipt.get("training_and_sampling_verified") is True and
             receipt.get("benchmark_score") is None and
             receipt.get("cost_usd") is None,
             "checkpoint_toy_smoke_not_complete")
    if service_factory is None:
        import tinker
        service_factory = lambda: tinker.ServiceClient(
            user_metadata={"purpose": "qwen38-checkpoint-base-readback"})
    _require(callable(service_factory),
             "checkpoint_service_factory_invalid")
    service = None
    success = False
    try:
        service = service_factory()
        sampler = service.create_sampling_client(model_path=uri)
        base = sampler.get_base_model()
        _require(base == MODEL, "checkpoint_reported_base_model_changed")
        service.close("success").result(timeout=30)
        success = True
    except CheckpointAttestationError:
        raise
    except Exception:
        raise CheckpointAttestationError(
            "checkpoint_read_only_lookup_failed") from None
    finally:
        if service is not None and not success:
            try:
                service.close("errored").result(timeout=30)
            except Exception:
                pass
    result = {
        "schema": SCHEMA,
        "checkpoint_path_sha256": sha256(uri.encode()).hexdigest(),
        "reported_base_model": MODEL,
        "read_only_model_lookup": True,
        "new_training_calls": 0,
        "new_sampling_calls": 0,
        "provider_invoice_usd": None,
        "benchmark_score": None,
    }
    raw = (json.dumps(result, sort_keys=True, separators=(",", ":")) +
           "\n").encode()
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {"status": "read_only_base_model_verified",
            "base_receipt_sha256": sha256(raw).hexdigest(),
            "checkpoint_path_sha256": result["checkpoint_path_sha256"],
            "new_training_calls": 0,
            "new_sampling_calls": 0,
            "provider_invoice_usd": None,
            "benchmark_score": None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--allow-read-only-provider", action="store_true")
    args = parser.parse_args()
    _require(args.allow_read_only_provider,
             "explicit_read_only_provider_flag_required")
    print(json.dumps(attest(args.private_dir), sort_keys=True))


if __name__ == "__main__":
    main()
