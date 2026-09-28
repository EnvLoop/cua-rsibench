"""Render verified native-GUI training frames as Qwen3.8 vision SFT datums.

This is a train-only data-path diagnostic from one public LibreOffice fixture.
It makes no Tinker/provider call and cannot estimate selection or final gain.
The returned datums stay in memory; only source-bound metadata is published.
"""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path

from cursibench.scale_action_contract import ContractLimits, make_observation
from cursibench.scale_action_output_v066 import normalize_model_action
from cursibench.full_study_teacher_adapter_v1 import _render_turns, _load_renderer
from native_desktop_factory import (
    qwen_v066_adapter, v066_final_freeze, v066_train_primitive_smoke as smoke,
)
from native_desktop_factory.verify import verify as verify_saved


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "envloop-desktop-v066-public-train-sft-render-private-v1"
PUBLIC_SCHEMA = "envloop-desktop-v066-public-train-sft-render-public-v1"


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def source_bound_steps(episode_dir: Path) -> tuple[dict, list[dict]]:
    """Reopen the complete real E2B GUI smoke, without accepting a final ID."""
    root = Path(episode_dir).absolute()
    require(root.name == "v066-caret-train-smoke-20260928-001" and
            root.is_dir() and not root.is_symlink() and
            root.stat().st_mode & 0o077 == 0,
            "private public-train episode root missing or unsafe")
    package, oracle, baseline, instruction, _ = smoke._train_package()
    receipt_path = root / "receipt.json"
    require(receipt_path.is_file() and not receipt_path.is_symlink() and
            receipt_path.stat().st_mode & 0o077 == 0,
            "public-train GUI receipt missing or unsafe")
    receipt_raw = receipt_path.read_bytes()
    receipt = json.loads(receipt_raw)
    saved_path = root / "saved.pptx"
    require(saved_path.is_file() and not saved_path.is_symlink() and
            saved_path.stat().st_mode & 0o077 == 0,
            "saved train deck missing or unsafe")
    saved = saved_path.read_bytes()
    rechecked = verify_saved(baseline, saved, oracle)
    expected_actions = smoke._script(next(iter(oracle["targets"].values())))
    steps = receipt.get("steps")
    require(receipt.get("schema") == "cua-native-wdi-gui-development-attempt-v1"
            and receipt.get("purpose") ==
            "v066_public_train_primitive_smoke_no_model"
            and receipt.get("split") == package["split"] == "train"
            and receipt.get("task_id") == package["task_id"]
            and receipt.get("package_sha256") == package["package_sha256"]
            and receipt.get("input_sha256") == digest(baseline)
            and receipt.get("status") == "train_primitive_smoke_passed"
            and receipt.get("guest_content_attested") is True
            and receipt.get("neutral_profile_self_stable") is True
            and receipt.get("kill_returned") is True
            and receipt.get("is_running_after_kill") is False
            and receipt.get("official_final_model_attempts") == 0
            and receipt.get("official_final_admissions") == 0
            and receipt.get("runner_sha256") ==
            digest(Path(smoke.__file__).read_bytes())
            and receipt.get("v066_native_adapter_sha256") ==
            digest(Path(qwen_v066_adapter.__file__).read_bytes())
            and receipt.get("saved_sha256") == digest(saved)
            and receipt.get("train_saved_artifact_verifier") == rechecked
            and rechecked.get("passed") is True
            and type(steps) is list and
            len(steps) == len(expected_actions) == 18,
            "public-train source, GUI proof or saved artifact changed")
    turns = []
    source_frames = []
    for index, (row, action) in enumerate(zip(steps, expected_actions)):
        raw_action = json.dumps(action, separators=(",", ":"))
        pred_name = row.get("predispatch_screenshot_file")
        require(type(pred_name) is str and pred_name.startswith(
                    f"predispatch-{index:02d}-") and
                pred_name.endswith(".png") and "/" not in pred_name and
                row.get("step") == index and row.get("status") == "applied" and
                row.get("action_type") == row.get("dispatch_type") ==
                action["type"] and
                row.get("action_payload_sha256") == digest(raw_action.encode()),
                "public-train step or action trace changed")
        attempt = pred_name.removeprefix(
            f"predispatch-{index:02d}-").removesuffix(".png")
        require(attempt in {"0", "1", "2", "3", "4"},
                "public-train frame retry number invalid")
        frame_name = f"frame-{index:02d}-{attempt}.png"
        frame_path, pred_path = root / frame_name, root / pred_name
        require(all(path.is_file() and not path.is_symlink() and
                    path.stat().st_mode & 0o077 == 0
                    for path in (frame_path, pred_path)),
                "private current-frame image missing or unsafe")
        image, before_dispatch = frame_path.read_bytes(), pred_path.read_bytes()
        require(digest(image) == row["observation_screenshot_sha256"] and
                digest(before_dispatch) ==
                row["predispatch_screenshot_sha256"] and
                qwen_v066_adapter.prior.application_frame_digest(image) ==
                qwen_v066_adapter.prior.application_frame_digest(
                    before_dispatch) ==
                row["predispatch_application_frame_sha256"],
                "real GUI observation or predispatch image changed")
        observation = make_observation(
            task_id=package["task_id"],
            task_binding_sha256=package["package_sha256"],
            instruction=instruction, step=index, screenshot_bytes=image,
            a11y_text="", dom_text="", controls=(),
            previous_action_result=(None if index == 0 else
                                    {"status": "applied", "code": "ok"}),
            memory="", limits=ContractLimits(max_step=20),
        )
        normalize_model_action(
            raw_action, observation, current_frame_id=observation.frame_id)
        turns.append({"observation": observation, "action": action})
        source_frames.append({"step": index, "image_sha256": digest(image),
                              "predispatch_sha256": digest(before_dispatch),
                              "action_sha256": digest(raw_action.encode())})
    return {
        "task_id": package["task_id"],
        "package_sha256": package["package_sha256"],
        "gui_receipt_sha256": digest(receipt_raw),
        "saved_artifact_sha256": digest(saved),
        "source_frames": source_frames,
        "action_types": dict(sorted(Counter(
            action["type"] for action in expected_actions).items())),
    }, turns


def render(episode_dir: Path, ratification: Path) -> tuple[dict, dict]:
    _ratified, rat_sha = v066_final_freeze.validate_ratification(ratification)
    source, turns = source_bound_steps(episode_dir)
    vision = _load_renderer()
    batch = _render_turns(
        "desktop-native", [source["task_id"]],
        [source["gui_receipt_sha256"]], turns, vision)
    lengths = batch.receipt["datum_token_lengths"]
    require(len(batch.datums) == len(batch.prompts) == len(lengths) == 18 and
            all(type(length) is int and 0 < length <= 32768
                for length in lengths),
            "real GUI image SFT datums missing or unbounded")
    private = {
        "schema": SCHEMA,
        "status": "evaluator_scripted_public_train_gui_rendered_offline",
        "split": "train",
        "source": source,
        "ratification_sha256": rat_sha,
        "renderer_identity": vision.identity,
        "render_receipt": batch.receipt,
        "exporter_source_sha256": digest(Path(__file__).read_bytes()),
        "provider_calls": 0,
        "benchmark_score": None,
        "official_final_admissions": 0,
    }
    public = {
        "schema": PUBLIC_SCHEMA,
        "status": private["status"],
        "cell_id": "desktop-native",
        "model": vision.identity["model"],
        "action_profile": batch.receipt["action_profile"],
        "real_gui_train_turns": len(lengths),
        "action_type_counts": source["action_types"],
        "supervised_datum_tokens_total": sum(lengths),
        "supervised_datum_tokens_max": max(lengths),
        "prompt_tokens_total": sum(batch.receipt["prompt_token_lengths"]),
        "source_gui_receipt_sha256": source["gui_receipt_sha256"],
        "saved_artifact_sha256": source["saved_artifact_sha256"],
        "ratification_sha256": rat_sha,
        "exporter_source_sha256": private["exporter_source_sha256"],
        "provider_calls": 0,
        "benchmark_score": None,
        "official_final_admissions": 0,
    }
    return private, public


def _write_new(path: Path, raw: bytes, mode: int) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode-dir", type=Path, required=True)
    parser.add_argument("--ratification", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    private_out, public_out = args.private_out.absolute(), args.public_out.absolute()
    require(not private_out.exists() and not public_out.exists() and
            private_out.parent.resolve().is_relative_to(
                (ROOT / "work/full-study").resolve()) and
            public_out.parent.resolve() ==
            (ROOT / "docs/evidence").resolve(),
            "new private/public train-render output paths required")
    private, public = render(args.episode_dir, args.ratification)
    private_out.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    private_out.parent.chmod(0o700)
    private_raw = (json.dumps(private, sort_keys=True,
                              separators=(",", ":")) + "\n").encode()
    _write_new(private_out, private_raw, 0o600)
    public["private_render_sha256"] = digest(private_raw)
    _write_new(public_out, (json.dumps(public, indent=2,
                                      sort_keys=True) + "\n").encode(), 0o644)
    print(json.dumps({
        "status": public["status"],
        "real_gui_train_turns": public["real_gui_train_turns"],
        "supervised_datum_tokens_total":
            public["supervised_datum_tokens_total"],
        "provider_calls": 0,
        "benchmark_score": None,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
