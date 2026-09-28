"""Shared read-only source gate for distinct Calc/Writer v0.6.6 GUI turns.

Each thin public exporter pins this helper's exact SHA-256. The helper reopens
the complete private pair, independent v2 audit, source-bound public receipt,
all current-frame PNGs, normalized actions, and actor-saved OOXML before it
constructs any in-memory SFT datum. No provider or Tinker call occurs here.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path

from cursibench.scale_action_contract import ContractLimits, make_observation
from cursibench.scale_action_output_v066 import normalize_model_action
from cursibench.full_study_teacher_adapter_v1 import _render_turns, _load_renderer
from native_desktop_factory import (
    qwen_v066_adapter,
    v066_final_freeze,
    v066_scoped_calc_writer_train_demo as demo,
    v066_scoped_calc_writer_train_demo_audit as historical_audit,
    v066_scoped_calc_writer_train_demo_audit_v2 as independent_audit,
)
from native_desktop_factory.v066_final_control_audit import _bound_file


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_EVIDENCE = (ROOT / "docs/evidence" /
    "native-wdi-v066-calc-writer-train-demo-2026-09-28.json")
PRIVATE_SCHEMA = "envloop-desktop-v066-calc-writer-train-sft-render-private-v1"
PUBLIC_SCHEMA = "envloop-desktop-v066-calc-writer-train-sft-render-public-v1"


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _private_file(path: Path) -> bytes:
    require(path.is_file() and not path.is_symlink() and
            path.stat().st_mode & 0o077 == 0,
            "private train source missing or public")
    return path.read_bytes()


def source_bound_steps(kind: str, episode_dir: Path) -> tuple[dict, list[dict]]:
    require(kind in demo.KINDS, "only Calc/Writer public train demos are allowed")
    episode = Path(episode_dir).absolute()
    root = episode.parent
    require(episode.name == kind and
            root.name == "v066-scoped-calc-writer-train-demo-20260928-001" and
            root.parent.name == "gui-diagnostics" and
            episode.is_dir() and root.is_dir() and
            not episode.is_symlink() and not root.is_symlink() and
            episode.stat().st_mode & 0o077 == 0 and
            root.stat().st_mode & 0o077 == 0,
            "private Calc/Writer train episode root missing or unsafe")
    work_root = root.parent.parent
    reference = work_root / "v066-scoped-profile-reference-20260928.private.json"
    reservation = (work_root /
                   "v066-scoped-calc-writer-train-demo-reservation-20260928.private.json")
    guest = (ROOT / "docs/evidence" /
             "native-wdi-guest-content-identity-2026-09-27.json")
    receipt_raw = _private_file(episode / "receipt.json")
    intent_raw = _private_file(episode / "intent.json")
    run_raw = _private_file(root / "run-receipt.json")
    audit_raw = _private_file(root / "audit-v2.private.json")
    audit_record = json.loads(audit_raw)
    public_raw = PUBLIC_EVIDENCE.read_bytes()
    public = json.loads(public_raw)
    require(public.get("schema") ==
            "cua-native-wdi-v066-calc-writer-train-demo-public-v1" and
            public.get("status") ==
            "two_public_train_gui_positives_independently_verified_not_registered_sft" and
            public.get("private_v2_independent_audit_sha256") ==
            digest(audit_raw) and
            public.get("private_run_journal_sha256") == digest(run_raw) and
            public.get(f"private_{kind}_receipt_sha256") ==
            digest(receipt_raw) and
            public.get("demo_runner_source_sha256") ==
            digest(Path(demo.__file__).read_bytes()) and
            public.get("historical_bound_v1_auditor_source_sha256") ==
            digest(Path(historical_audit.__file__).read_bytes()) and
            public.get("corrected_read_only_v2_auditor_source_sha256") ==
            digest(Path(independent_audit.__file__).read_bytes()) and
            public.get("official_final_admissions") == 0 and
            public.get("source_bound_sft_exporters_completed") is False,
            "published public-train source or v2 audit changed")
    require(audit_record.get("schema") ==
            "cua-native-wdi-v066-calc-writer-train-demo-audit-v2-private-v1" and
            audit_record.get("status") ==
            "two_distinct_train_gui_positives_passed" and
            audit_record.get("run_journal_sha256") == digest(run_raw) and
            audit_record.get("provider_active_zero_after") is True and
            audit_record.get("official_final_admissions") == 0,
            "private Calc/Writer independent audit changed")
    for relative, expected in audit_record.get("raw_private_file_sha256s", {}).items():
        path = (root / relative).resolve()
        require(path.is_relative_to(root.resolve()) and
                path.is_file() and not path.is_symlink() and
                digest(path.read_bytes()) == expected,
                "private GUI raw-file manifest changed")
    private, verified = independent_audit.audit_both(
        output_root=root, scoped_reference=reference,
        guest_public=guest, reservation_path=reservation)
    require(private["status"] == "two_distinct_train_gui_positives_passed" and
            verified["current_frame_actions_total"] == 20 and
            private["run_journal_sha256"] == digest(run_raw),
            "independent Calc/Writer GUI audit no longer passes")
    receipt = json.loads(receipt_raw)
    package, oracle, baseline, instruction, _filename = demo._source(kind)
    require(receipt.get("kind") == kind and
            receipt.get("split") == package["split"] == "train" and
            receipt.get("package_sha256") == package["package_sha256"] and
            receipt.get("input_sha256") == digest(baseline) and
            receipt.get("status") == "train_gui_positive_passed" and
            receipt.get("actor_gui_actions") == len(
                demo.actor_actions(kind, oracle)) and
            receipt.get("official_final_model_attempts") == 0,
            "Calc/Writer source is not a public-train positive")
    saved_record = receipt["saved_artifact"]
    saved = _bound_file(root, saved_record)
    actions = demo.actor_actions(kind, oracle)
    turns, source_frames = [], []
    for index, (row, expected) in enumerate(zip(
            receipt["normalized_actor_actions"], actions)):
        image = _bound_file(root, row["observation"])
        before_dispatch = _bound_file(root, row["predispatch"])
        projected = {key: row["normalized_action"][key] for key in expected}
        require(projected == expected and row["step"] == index and
                row["status"] == "applied" and
                qwen_v066_adapter.prior.application_frame_digest(image) ==
                qwen_v066_adapter.prior.application_frame_digest(
                    before_dispatch),
                "Calc/Writer source action or current frame changed")
        observation = make_observation(
            task_id=package["task_id"],
            task_binding_sha256=package["package_sha256"],
            instruction=instruction, step=index,
            screenshot_bytes=image,
            a11y_text="", dom_text="", controls=(),
            previous_action_result=(None if index == 0 else
                                    {"status": "applied", "code": "ok"}),
            memory="", limits=ContractLimits(max_step=demo.MAX_ACTIONS))
        recorded_action = row["normalized_action"]
        recorded_frame_id = recorded_action.get("frame_id")
        require(type(recorded_frame_id) is str and
                digest(recorded_frame_id.encode()) ==
                row.get("frame_id_sha256"),
                "recorded v0.6.6 current-frame ID changed")
        observation = replace(observation, frame_id=recorded_frame_id)
        raw_action = json.dumps(expected, separators=(",", ":"))
        normalized_again = normalize_model_action(
            raw_action, observation,
            current_frame_id=recorded_frame_id)
        require(normalized_again == recorded_action,
                "recorded v0.6.6 action envelope changed")
        turns.append({"observation": observation, "action": expected,
                      "recorded_normalized_action": recorded_action})
        source_frames.append({
            "step": index,
            "image_sha256": digest(image),
            "predispatch_sha256": digest(before_dispatch),
            "action_sha256": digest(raw_action.encode()),
            "recorded_frame_id_sha256":
                digest(recorded_frame_id.encode()),
            "live_normalized_action_sha256":
                row["normalized_action_sha256"],
        })
    return {
        "task_id": package["task_id"],
        "package_sha256": package["package_sha256"],
        "gui_receipt_sha256": digest(receipt_raw),
        "saved_artifact_sha256": digest(saved),
        "source_frames": source_frames,
        "action_types": dict(sorted(Counter(
            action["type"] for action in actions).items())),
        "independent_v2_audit_sha256": digest(audit_raw),
        "historical_bound_v1_auditor_sha256": digest(
            Path(historical_audit.__file__).read_bytes()),
    }, turns


def render(*, kind: str, episode_dir: Path, ratification: Path,
           exporter_source: Path) -> tuple[dict, dict]:
    _ratified, rat_sha = v066_final_freeze.validate_ratification(ratification)
    source, turns = source_bound_steps(kind, episode_dir)
    vision = _load_renderer()
    batch = _render_turns(
        "desktop-native", [source["task_id"]],
        [source["gui_receipt_sha256"]], turns, vision)
    lengths = batch.receipt["datum_token_lengths"]
    require(len(batch.datums) == len(batch.prompts) == len(lengths) ==
            len(turns) and len(turns) >= 5 and
            all(type(length) is int and 0 < length <= 32768
                for length in lengths),
            "real Calc/Writer image SFT datums missing or unbounded")
    private = {
        "schema": PRIVATE_SCHEMA,
        "status": "evaluator_scripted_public_train_gui_rendered_offline",
        "split": "train", "kind": kind,
        "source": source,
        "ratification_sha256": rat_sha,
        "renderer_identity": vision.identity,
        "render_receipt": batch.receipt,
        "exporter_source_sha256": digest(exporter_source.read_bytes()),
        "shared_helper_source_sha256": digest(Path(__file__).read_bytes()),
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
        "real_gui_train_turns": len(turns),
        "action_type_counts": source["action_types"],
        "supervised_datum_tokens_total": sum(lengths),
        "supervised_datum_tokens_max": max(lengths),
        "prompt_tokens_total": sum(batch.receipt["prompt_token_lengths"]),
        "source_gui_receipt_sha256": source["gui_receipt_sha256"],
        "saved_artifact_sha256": source["saved_artifact_sha256"],
        "independent_v2_audit_sha256": source["independent_v2_audit_sha256"],
        "ratification_sha256": rat_sha,
        "exporter_source_sha256": private["exporter_source_sha256"],
        "shared_helper_source_sha256": private["shared_helper_source_sha256"],
        "provider_calls": 0,
        "benchmark_score": None,
        "official_final_admissions": 0,
    }
    return private, public


def write_new(path: Path, raw: bytes, mode: int) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def publish(*, kind: str, episode_dir: Path, ratification: Path,
            exporter_source: Path, private_out: Path,
            public_out: Path) -> dict:
    private_out, public_out = private_out.absolute(), public_out.absolute()
    require(not private_out.exists() and not private_out.is_symlink() and
            not public_out.exists() and not public_out.is_symlink() and
            private_out.parent.resolve().is_relative_to(
                (ROOT / "work/full-study").resolve()) and
            public_out.parent.resolve() ==
            (ROOT / "docs/evidence").resolve(),
            "new private/public Calc/Writer render paths required")
    private, public = render(
        kind=kind, episode_dir=episode_dir,
        ratification=ratification, exporter_source=exporter_source)
    private_out.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    private_out.parent.chmod(0o700)
    raw = (json.dumps(private, sort_keys=True,
                      separators=(",", ":")) + "\n").encode()
    write_new(private_out, raw, 0o600)
    public["private_render_sha256"] = digest(raw)
    write_new(public_out, (json.dumps(public, indent=2,
                                      sort_keys=True) + "\n").encode(), 0o644)
    return {"status": public["status"],
            "real_gui_train_turns": public["real_gui_train_turns"],
            "supervised_datum_tokens_total":
                public["supervised_datum_tokens_total"],
            "provider_calls": 0,
            "benchmark_score": None}
