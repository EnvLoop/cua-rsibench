"""Fail-closed, read-only Qwen runtime audit for future campaign dispatch.

The caller must still enforce the study's six-cell freeze, dollar ledger and
selection/final boundaries. Passing this audit grants no dispatch authority.
"""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import re
import site
import subprocess
import sys
from importlib.util import find_spec


MODEL = "Qwen/Qwen3.8-27B"
COOKBOOK_COMMIT = "1e53aa3d1cdd6389b3290c2574641eccc0503242"
PUBLIC_SCHEMA = "envloop-qwen38-clean-runtime-toy-smoke-public-v1"
CHECKPOINT = re.compile(r"tinker://[^\s/]+/sampler_weights/[^\s/]+\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
PROVIDER_ENV_KEYS = (
    "TINKER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    "E2B_API_KEY", "HF_TOKEN", "HUGGING_FACE_HUB_TOKEN",
)
PRIVATE_TOY_RELATIVE = Path(
    "work/full-study/tinker-qwen38-vision-paid-transformers554-20260928")
CRITICAL_PACKAGES = (
    "tinker", "transformers", "tokenizers", "torch",
    "tml_renderers", "tinker_cookbook",
)


class RuntimeGateError(ValueError):
    """Fixed public labels; never include URI, credentials or provider body."""


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise RuntimeGateError(code)


def _sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _json(path: Path, *, private_root: Path | None = None) -> tuple[dict, bytes]:
    _require(path.is_file() and not path.is_symlink() and
             0 < path.stat().st_size <= 20_000_000 and
             (private_root is None or
              (path.resolve().is_relative_to(private_root.resolve()) and
               path.stat().st_mode & 0o077 == 0)),
             "runtime_audit_evidence_missing_or_unsafe")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RuntimeGateError("runtime_audit_json_invalid") from None
    _require(type(value) is dict, "runtime_audit_object_required")
    return value, raw


def _private_toy(root: Path, public: dict) -> None:
    _require(root.is_dir() and not root.is_symlink() and
             root.stat().st_mode & 0o077 == 0,
             "runtime_private_toy_directory_unsafe")
    names = {
        "receipt.json": "private_toy_receipt_sha256",
        "training-intent.json": "private_training_intent_sha256",
        "private-checkpoint.json": "private_checkpoint_binding_sha256",
        "checkpoint-base-model.private.json":
            "private_base_model_readback_sha256",
    }
    evidence = {}
    for filename, field in names.items():
        value, raw = _json(root / filename, private_root=root)
        _require(type(public.get(field)) is str and
                 HASH.fullmatch(public[field]) is not None and
                 _sha(raw) == public[field],
                 "runtime_private_toy_hash_changed")
        evidence[filename] = value
    receipt = evidence["receipt.json"]
    intent = evidence["training-intent.json"]
    checkpoint = evidence["private-checkpoint.json"]
    base = evidence["checkpoint-base-model.private.json"]
    uri = checkpoint.get("checkpoint_path")
    local = receipt.get("local_rendering")
    _require(type(uri) is str and CHECKPOINT.fullmatch(uri) is not None and
             receipt.get("schema") == "tinker-vision-compatibility-v1" and
             receipt.get("model") == MODEL and
             receipt.get("optimizer_steps_completed") == 1 and
             receipt.get("training_and_sampling_verified") is True and
             receipt.get("checkpoint_saved") is True and
             receipt.get("benchmark_score") is None and
             receipt.get("cost_usd") is None and
             receipt.get("sample_tokens") == public.get(
                 "sample_token_count") and
             type(local) is dict and
             "ImageChunk" in local.get("supervised_chunk_types", []) and
             "ImageChunk" in local.get("sampling_chunk_types", []) and
             intent.get("model") == MODEL and
             intent.get("rank") == 8 and
             intent.get("steps") == 1 and
             intent.get("single_dispatch_only") is True and
             base.get("schema") ==
             "envloop-tinker-qwen38-one-step-checkpoint-base-v1" and
             base.get("checkpoint_path_sha256") ==
             _sha(uri.encode()) == public.get("checkpoint_path_sha256") and
             base.get("reported_base_model") == MODEL and
             base.get("read_only_model_lookup") is True and
             base.get("new_training_calls") == 0 and
             base.get("new_sampling_calls") == 0 and
             base.get("provider_invoice_usd") is None and
             base.get("benchmark_score") is None,
             "runtime_private_toy_semantics_changed")


def validate(*, repo_root: Path, study_plan_sha256: str,
             private_toy_dir: Path) -> dict:
    """Reopen private toy evidence and run offline verifier in the root venv.

    The method returns hashes and ``dispatch_authorized=False``.
    """
    root = Path(repo_root).absolute()
    work = root / "work"
    runtime_python = (work / "qwen38-training-runtime" / ".venv" /
                      "bin" / "python")
    cookbook = work / "tinker-cookbook-pinned"
    private = Path(private_toy_dir).absolute()
    _require(root.is_dir() and not root.is_symlink() and
             work.is_dir() and not work.is_symlink() and
             runtime_python.is_file() and
             runtime_python.absolute().is_relative_to(work.absolute()) and
             cookbook.is_dir() and not cookbook.is_symlink() and
             cookbook.resolve().is_relative_to(work.resolve()) and
             private.is_dir() and not private.is_symlink() and
             private.resolve().is_relative_to((work / "full-study").resolve()) and
             type(study_plan_sha256) is str and
             HASH.fullmatch(study_plan_sha256) is not None,
             "runtime_durable_root_or_plan_missing")
    spec_path = root / "runtime/qwen38-vision/runtime-spec.json"
    lock_path = root / "runtime/qwen38-vision/requirements.lock"
    public_path = (root / "docs/evidence" /
                   "tinker-qwen38-vision-clean-runtime-2026-09-28.json")
    verifier_path = root / "tools/verify_qwen38_training_runtime_v1.py"
    attester_path = root / "tools/attest_tinker_checkpoint_base_v1.py"
    runner_path = root / "tools/smoke_tinker_vision.py"
    spec, spec_raw = _json(spec_path)
    public, public_raw = _json(public_path)
    _require(all(path.is_file() and not path.is_symlink()
                 for path in (lock_path, verifier_path, attester_path,
                              runner_path)) and
             spec.get("schema") == "cua-qwen38-training-runtime-v1" and
             public.get("schema") == PUBLIC_SCHEMA and
             public.get("status") ==
             "paid_toy_api_smoke_and_clean_offline_runtime_verified_separately" and
             public.get("model") == MODEL and
             public.get("runtime_spec_sha256") == _sha(spec_raw) and
             public.get("requirements_lock_sha256") ==
             spec.get("requirements_lock_sha256") ==
             _sha(lock_path.read_bytes()) and
             public.get("cookbook_commit") ==
             spec.get("cookbook", {}).get("commit") == COOKBOOK_COMMIT and
             public.get("cookbook_package_tree_sha256") ==
             spec.get("cookbook", {}).get("package_tree_sha256") and
             public.get("processor_config_sha256") ==
             spec.get("render_probe", {}).get("processor_config_sha256") and
             public.get("tokenizer_vocabulary_sha256") ==
             spec.get("render_probe", {}).get("tokenizer_vocabulary_sha256") and
             public.get("tinker_sdk_version") ==
             spec.get("distributions", {}).get("tinker", {}).get("version") and
             public.get("transformers_version") ==
             spec.get("distributions", {}).get("transformers", {}).get("version") and
             public.get("tokenizers_version") ==
             spec.get("distributions", {}).get("tokenizers", {}).get("version") and
             public.get("tml_renderers_version") ==
             spec.get("distributions", {}).get("tml-renderers", {}).get("version") and
             public.get("torch_version") ==
             spec.get("distributions", {}).get("torch", {}).get("version") and
             public.get("runner_source_sha256") ==
             _sha(runner_path.read_bytes()) and
             public.get("runtime_verifier_source_sha256") ==
             _sha(verifier_path.read_bytes()) and
             public.get("read_only_attester_source_sha256") ==
             _sha(attester_path.read_bytes()) and
             public.get("optimizer_steps_completed") == 1 and
             public.get("provider_reported_checkpoint_base_model_verified")
             is True and
             public.get("new_readback_training_calls") == 0 and
             public.get("new_readback_sampling_calls") == 0 and
             public.get("provider_weight_bytes_verified") is False and
             public.get("provider_invoice_usd") is None and
             public.get("researcher_campaigns_completed") == 0 and
             public.get("official_final_model_results") == 0 and
             public.get("benchmark_score") is None and
             public.get("dedicated_runtime_execution") ==
             "offline_render_only",
             "runtime_public_toy_or_source_changed")
    _private_toy(private, public)
    environment = os.environ.copy()
    for key in PROVIDER_ENV_KEYS:
        environment.pop(key, None)
    environment["PYTHONPATH"] = str(root / "src")
    environment["PYTHONNOUSERSITE"] = "1"
    environment["HF_HUB_OFFLINE"] = "1"
    environment["TRANSFORMERS_OFFLINE"] = "1"
    command = [str(runtime_python), str(verifier_path),
               "--cookbook-dir", str(cookbook),
               "--spec", str(spec_path)]
    try:
        completed = subprocess.run(
            command, cwd=root, env=environment,
            capture_output=True, text=True, timeout=180,
            check=False)
        output = json.loads(completed.stdout)
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
        raise RuntimeGateError("runtime_dedicated_verifier_failed") from None
    _require(completed.returncode == 0 and type(output) is dict and
             output.get("status") == "offline_runtime_verified" and
             output.get("runtime_spec_sha256") == _sha(spec_raw) and
             output.get("model") == MODEL and
             output.get("provider_calls") == 0 and
             output.get("benchmark_score") is None,
             "runtime_dedicated_verifier_failed")
    return {
        "status": "pre_dispatch_runtime_evidence_verified",
        "study_plan_sha256": study_plan_sha256,
        "runtime_spec_sha256": _sha(spec_raw),
        "toy_public_receipt_sha256": _sha(public_raw),
        "provider_calls": 0,
        "dispatch_authorized": False,
        "benchmark_score": None,
    }


def assert_active_worker(repo_root: Path) -> None:
    """Reject an overlay or a caller outside the verified root-owned venv.

    ``validate`` checks a fresh isolated subprocess. This second check binds
    the process that will actually execute the provider callback.
    """
    root = Path(repo_root).absolute()
    venv = root / "work/qwen38-training-runtime/.venv"
    interpreter = venv / "bin/python"
    _require(Path(sys.executable).absolute() == interpreter and
             Path(sys.prefix).absolute() == venv and
             site.ENABLE_USER_SITE is False,
             "runtime_active_worker_not_dedicated_venv")
    source = root / "src/cursibench/full_study_qwen_runtime_gate_v1.py"
    _require(source.is_file() and not source.is_symlink() and
             Path(__file__).resolve() == source.resolve(),
             "runtime_gate_source_not_root_checkout")
    paths = os.environ.get("PYTHONPATH", "")
    allowed = {root, root / "src"}
    _require(not paths or all(item and Path(item).is_absolute() and
                              not Path(item).is_symlink() and
                              Path(item).absolute() in allowed
                              for item in paths.split(os.pathsep)),
             "runtime_pythonpath_overlay_forbidden")
    for name in CRITICAL_PACKAGES:
        try:
            spec = find_spec(name)
            origin = Path(spec.origin).absolute() if spec and spec.origin else None
        except (ImportError, ModuleNotFoundError, TypeError, ValueError):
            origin = None
        _require(origin is not None and origin.is_file() and
                 not origin.is_symlink() and
                 origin.resolve().is_relative_to(venv.resolve()),
                 "runtime_active_package_origin_invalid")


def pre_dispatch(*, repo_root: Path, study_plan_sha256: str) -> dict:
    """Recheck evidence and process identity immediately before paid Tinker.

    This does not grant study admission; the campaign freeze, task partition,
    and dollar ledger remain the caller's responsibility.
    """
    root = Path(repo_root).absolute()
    receipt = validate(
        repo_root=root, study_plan_sha256=study_plan_sha256,
        private_toy_dir=root / PRIVATE_TOY_RELATIVE)
    _require(type(receipt) is dict and set(receipt) == {
        "status", "study_plan_sha256", "runtime_spec_sha256",
        "toy_public_receipt_sha256", "provider_calls",
        "dispatch_authorized", "benchmark_score",
    } and receipt["status"] == "pre_dispatch_runtime_evidence_verified" and
             receipt["study_plan_sha256"] == study_plan_sha256 and
             all(type(receipt[key]) is str and HASH.fullmatch(receipt[key])
                 for key in ("runtime_spec_sha256",
                             "toy_public_receipt_sha256")) and
             type(receipt["provider_calls"]) is int and
             receipt["provider_calls"] == 0 and
             receipt["dispatch_authorized"] is False and
             receipt["benchmark_score"] is None,
             "runtime_pre_dispatch_receipt_invalid")
    assert_active_worker(root)
    return {
        "runtime_spec_sha256": receipt["runtime_spec_sha256"],
        "toy_public_receipt_sha256": receipt["toy_public_receipt_sha256"],
        "runtime_gate_source_sha256": _sha(Path(__file__).read_bytes()),
    }


__all__ = ["validate", "assert_active_worker", "pre_dispatch",
           "RuntimeGateError"]
