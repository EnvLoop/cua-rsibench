"""Offline, source-bound preflight for the full-study Qwen vision runtime.

No Tinker client, model sampling, training, browser, or final task is opened.
The freeze operation records a clean, hash-locked venv; verify fails closed if
its packages, cookbook, renderer, processor, or toy SFT rendering drift.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SPEC_SCHEMA = "cua-qwen38-training-runtime-v1"
COOKBOOK_COMMIT = "1e53aa3d1cdd6389b3290c2574641eccc0503242"
MODEL = "Qwen/Qwen3.8-27B"
RENDERER = "qwen3_5_disable_thinking"
PROCESSOR = "Qwen2VLImageProcessorPil"
SOURCE_FILES = (
    "src/cursibench/scale_vision_proxy.py",
    "src/cursibench/gui_sft_data_v1.py",
    "src/cursibench/full_study_teacher_adapter_v1.py",
    "tools/smoke_tinker_vision.py",
    "tools/verify_qwen38_training_runtime_v1.py",
)
CRITICAL_MODULES = {
    "tinker": "tinker",
    "transformers": "transformers",
    "tokenizers": "tokenizers",
    "tml-renderers": "tml_renderers",
    "tinker-cookbook": "tinker_cookbook",
}
EXPECTED_VERSIONS = {
    "tinker": "0.30.0",
    "tinker-cookbook": "0.5.8.dev5+g1e53aa3d1",
    "transformers": "5.5.4",
    "tokenizers": "0.22.2",
    "tml-renderers": "0.1.0",
    "torch": "2.13.0",
    "pillow": "12.3.0",
    "blobfile": "3.3.0",
    "chz": "0.4.0",
}


class RuntimeErrorCode(ValueError):
    """Fixed public errors; never include private paths or package contents."""


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise RuntimeErrorCode(code)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode()


def _tree_sha(root: Path) -> str:
    _require(root.is_dir() and not root.is_symlink(),
             "runtime_source_tree_missing")
    digest = hashlib.sha256()
    count = 0
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        _require(path.is_file() and not path.is_symlink() and
                 path.resolve().is_relative_to(root.resolve()),
                 "runtime_source_tree_unsafe")
        relative = path.relative_to(root).as_posix().encode()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        size = path.stat().st_size
        digest.update(size.to_bytes(8, "big"))
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        count += 1
    _require(count > 0, "runtime_source_tree_empty")
    return digest.hexdigest()


def _distribution_snapshot() -> dict:
    result = {}
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name", "").lower().replace("_", "-")
        _require(bool(name) and name not in result,
                 "runtime_distribution_duplicate_or_unnamed")
        metadata = distribution.read_text("METADATA")
        record = distribution.read_text("RECORD")
        _require(type(metadata) is str and type(record) is str,
                 "runtime_distribution_record_missing")
        result[name] = {
            "version": distribution.version,
            "metadata_sha256": _sha(metadata.encode()),
            "record_sha256": _sha(record.encode()),
        }
    _require(set(EXPECTED_VERSIONS) <= set(result) and
             all(result[name]["version"] == version for name, version in
                 EXPECTED_VERSIONS.items()),
             "runtime_pinned_distribution_version_changed")
    return dict(sorted(result.items()))


def _critical_sources() -> dict:
    result = {}
    prefix = Path(sys.prefix).resolve()
    for name, module_name in CRITICAL_MODULES.items():
        module = importlib.import_module(module_name)
        directory = Path(module.__file__).resolve().parent
        _require(directory.is_relative_to(prefix),
                 "runtime_external_package_overlay_forbidden")
        result[name] = _tree_sha(directory)
    return result


def _cookbook(checkout: Path) -> dict:
    checkout = Path(checkout).resolve()
    _require(checkout.is_dir() and not checkout.is_symlink(),
             "runtime_cookbook_checkout_missing")
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=checkout,
            capture_output=True, text=True, check=True).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=normal"],
            cwd=checkout, capture_output=True, text=True,
            check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        raise RuntimeErrorCode("runtime_cookbook_git_unavailable") from None
    _require(commit == COOKBOOK_COMMIT and not status and
             (checkout / "pyproject.toml").is_file(),
             "runtime_cookbook_commit_or_tree_changed")
    return {
        "commit": commit,
        "pyproject_sha256": _sha((checkout / "pyproject.toml").read_bytes()),
        "package_tree_sha256": _tree_sha(checkout / "tinker_cookbook"),
    }


def _render_probe() -> dict:
    from PIL import Image
    from cursibench.scale_vision_proxy import QwenVisionRenderer
    from tinker_cookbook.renderers import ImagePart, Message, TextPart
    from tinker_cookbook.supervised.data import datum_from_model_input_weights

    renderer = QwenVisionRenderer.load()
    identity = renderer.identity
    _require(identity["model"] == MODEL and
             identity["renderer"] == RENDERER and
             identity["image_processor"] == PROCESSOR,
             "runtime_renderer_identity_changed")
    image = Image.new("RGB", (112, 112), (220, 40, 40))
    user = Message(role="user", content=[
        ImagePart(type="image", image=image),
        TextPart(type="text", text="Return one disposable JSON action.")])
    assistant = Message(role="assistant",
                        content='{"action":{"type":"done"}}')
    supervised, weights = renderer.renderer.build_supervised_example(
        [user, assistant])
    prompt, info = renderer.render(
        image, "Return one disposable JSON action.", "offline runtime probe")
    datum = datum_from_model_input_weights(
        supervised, weights, max_length=2048, reduction="none")
    supervised_types = [type(chunk).__name__ for chunk in supervised.chunks]
    _require("ImageChunk" in supervised_types and
             "ImageChunk" in info["chunk_types"] and
             info["image_tokens"] > 0 and
             info["input_tokens"] == prompt.length and
             float(weights.sum().item()) > 0 and datum is not None,
             "runtime_image_sft_render_failed")
    return {
        "model": MODEL, "renderer": RENDERER,
        "image_processor": PROCESSOR,
        "processor_config_sha256": identity["processor_config_sha256"],
        "tokenizer_vocabulary_sha256": identity[
            "tokenizer_vocabulary_sha256"],
        "supervised_chunk_types": supervised_types,
        "sampling_chunk_types": info["chunk_types"],
        "sampling_input_tokens": info["input_tokens"],
        "sampling_image_tokens": info["image_tokens"],
        "positive_loss_weight": True,
    }


def snapshot(cookbook_dir: Path) -> dict:
    _require(sys.prefix != sys.base_prefix and
             sys.version_info[:3] == (3, 14, 7) and
             platform.system() == "Darwin" and
             platform.machine() == "arm64",
             "runtime_dedicated_cpython314_arm64_required")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    sources = {relative: _sha((ROOT / relative).read_bytes())
               for relative in SOURCE_FILES}
    return {
        "schema": SPEC_SCHEMA,
        "python": "CPython 3.14.7",
        "platform": "Darwin arm64",
        "requirements_in_sha256": _sha((ROOT / "runtime/qwen38-vision/requirements.in").read_bytes()),
        "requirements_lock_sha256": _sha((ROOT / "runtime/qwen38-vision/requirements.lock").read_bytes()),
        "cookbook": _cookbook(cookbook_dir),
        "distributions": _distribution_snapshot(),
        "critical_package_tree_sha256s": _critical_sources(),
        "repo_source_sha256s": sources,
        "render_probe": _render_probe(),
        "network_provider_calls": 0,
        "benchmark_score": None,
    }


def verify(spec_path: Path, cookbook_dir: Path) -> dict:
    path = Path(spec_path)
    _require(path.is_file() and not path.is_symlink(),
             "runtime_spec_missing")
    raw = path.read_bytes()
    try:
        frozen = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RuntimeErrorCode("runtime_spec_invalid") from None
    observed = snapshot(cookbook_dir)
    _require(frozen == observed and raw == _canonical(frozen),
             "runtime_snapshot_or_render_changed")
    return {"status": "offline_runtime_verified",
            "runtime_spec_sha256": _sha(raw),
            "model": MODEL, "provider_calls": 0,
            "benchmark_score": None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cookbook-dir", type=Path, required=True)
    parser.add_argument("--spec", type=Path, default=ROOT /
                        "runtime/qwen38-vision/runtime-spec.json")
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    if args.freeze:
        target = args.spec.absolute()
        _require(target.parent.resolve() ==
                 (ROOT / "runtime/qwen38-vision").resolve() and
                 not target.exists(), "runtime_fresh_spec_path_required")
        data = _canonical(snapshot(args.cookbook_dir))
        target.write_bytes(data)
        print(json.dumps({"status": "offline_runtime_frozen",
                          "runtime_spec_sha256": _sha(data),
                          "provider_calls": 0,
                          "benchmark_score": None}, sort_keys=True))
    else:
        print(json.dumps(verify(args.spec, args.cookbook_dir),
                         sort_keys=True))


if __name__ == "__main__":
    main()
