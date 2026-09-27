"""Publish allowlisted Odoo v0.6.5 train-only model/GUI evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

from cursibench.scale_vision_proxy import digest as sampling_digest


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def aggregate(attempt_dir: Path, source_root: Path) -> dict:
    receipt_path = attempt_dir / "receipt.json"
    private_raw = receipt_path.read_bytes()
    row = json.loads(private_raw)
    if (row.get("schema") != "envloop-odoo-qwen-v065-native-train-smoke-v1"
            or row.get("partition") != "train"
            or row.get("official_hidden_used") is not False
            or row.get("official_model_result_count") != 0
            or row.get("pre_model_full_reset_exact") is not True
            or row.get("post_model_full_reset_exact") is not True
            or row.get("tinker_session_closed") is not True
            or row.get("model") != "Qwen/Qwen3.8-27B"
            or row.get("max_actions", 0) > 3
            or row.get("max_samples", 0) > 5):
        raise ValueError("Not a bounded, restored Odoo train-only model smoke")
    required_sources = {
        "selected_v065_sha256": source_root / "src/cursibench/scale_action_output_v065.py",
        "shared_minimal_v062_sha256": source_root / "src/cursibench/scale_action_output_v062.py",
        "shared_minimal_v064_sha256": source_root / "src/cursibench/scale_action_output_v064.py",
        "shared_full_action_validator_sha256": source_root / "src/cursibench/scale_action_contract.py",
        "odoo_native_adapter_sha256": source_root / "enterprise_fallback/odoo18/odoo_native_adapter.py",
        "train_runner_sha256": source_root / "enterprise_fallback/odoo18/smoke_qwen_v065_train.py",
    }
    if any(row.get(key) != digest(path.read_bytes()) for key, path in required_sources.items()):
        raise ValueError("Model/action/adapter source changed after the live smoke")
    journal = attempt_dir / "sampler-journal" / "requests.sqlite3"
    if (not journal.is_file() or journal.is_symlink()
            or journal.stat().st_mode & 0o077):
        raise ValueError("Raw model journal is missing or not private")
    with sqlite3.connect(f"file:{journal.resolve()}?mode=ro", uri=True) as database:
        saved = database.execute("SELECT state,result FROM requests ORDER BY rowid").fetchall()
    if len(saved) != len(row["samples"]):
        raise ValueError("Provider journal/sample receipt count changed")
    alias_count = 0
    for (state, saved_raw), sample in zip(saved, row["samples"]):
        result = json.loads(saved_raw)
        if (state != "complete" or result.get("status") != "completed"
                or sampling_digest(result["text"]) != sample["text_sha256"]):
            raise ValueError("Sample text or provider state differs from private receipt")
        raw_text = result["text"].strip()
        lines = raw_text.splitlines()
        if lines and lines[0] in ("```", "```json") and lines[-1] == "```":
            raw_text = "\n".join(lines[1:-1])
        try:
            parsed = json.loads(raw_text)
        except (ValueError, TypeError):
            parsed = {}
        alias_count += type(parsed) is dict and "action" in parsed and "type" not in parsed
    applied = [action for action in row["actions"] if action["status"] == "applied"]
    if (len(applied) > row["max_actions"] or len(saved) > row["max_samples"]
            or any(action["type"] not in ("click", "type", "key", "scroll",
                                                  "drag", "wait", "finish") for action in applied)):
        raise ValueError("GUI action budget or type changed")
    return {
        "schema": "envloop-odoo-qwen-v065-native-train-public-v1",
        "checked_date": "2026-09-27",
        "scope": "One original Odoo Community 18 train-only native GUI model smoke, not a hidden-final score or researcher campaign.",
        "private_receipt_sha256": digest(private_raw),
        "private_sampler_journal_sha256": digest(journal.read_bytes()),
        "train_world_sha256": row["train_world_sha256"],
        "train_task_set_manifest_sha256": row["task_set_manifest_sha256"],
        "train_package_sha256": row["package_sha256"],
        "source_binding_sha256s": {key: row[key] for key in sorted(required_sources)},
        "model": row["model"],
        "renderer_identity": row["renderer_identity"],
        "sampling_binding_sha256": row["sampling_binding_sha256"],
        "completed_multimodal_samples": len(saved),
        "rendered_usage_not_billing": [sample.get("usage") for sample in row["samples"]],
        "live_action_alias_reply_count": alias_count,
        "applied_gui_action_types": [action["type"] for action in applied],
        "applied_target_kinds": [action["target_kind"] for action in applied],
        "rejected_model_action_codes": [action.get("error_code") for action in row["actions"]
                                        if action["status"] == "model_output_rejected"],
        "run_status": row["status"], "failure_class": row["failure_class"],
        "independent_train_reward_after_model": row.get("train_reward_after_model"),
        "pre_model_full_database_filestore_reset_exact": True,
        "post_model_full_database_filestore_reset_exact": True,
        "tinker_session_closed": True,
        "official_hidden_task_used": False,
        "official_full_study_final_admissions": 0,
        "official_model_result_count": 0,
        "provider_billed_usd": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt-dir", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Refusing to overwrite public Odoo smoke receipt")
    result = aggregate(args.attempt_dir, args.source_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in (
        "run_status", "failure_class", "completed_multimodal_samples",
        "applied_gui_action_types", "post_model_full_database_filestore_reset_exact",
        "official_model_result_count")}, sort_keys=True))


if __name__ == "__main__":
    main()
