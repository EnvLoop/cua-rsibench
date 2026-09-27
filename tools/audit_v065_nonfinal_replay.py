"""Offline shape replay of preserved Odoo/Desktop train-only model texts.

This never dispatches a GUI action or claims a current-frame validation. New
synthetic frames bind only the saved screenshot dimensions/empty controls for
the minimal-action shape check; historical receipts remain unchanged.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sqlite3

from cursibench.scale_action_contract import (
    ContractError, make_observation, _strict_json,
)
from cursibench.scale_action_output_v064 import normalize_model_action as v064
from cursibench.scale_action_output_v065 import normalize_model_action as v065
from cursibench.scale_vision_proxy import digest as sampling_digest


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def journal_rows(path: Path) -> list[dict]:
    if (not path.is_file() or path.is_symlink()
            or path.stat().st_mode & 0o077):
        raise ValueError("Private model journal must be a regular mode-0600 file")
    with sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as database:
        rows = database.execute("SELECT state,result FROM requests ORDER BY rowid").fetchall()
    if not rows or any(state != "complete" for state, _ in rows):
        raise ValueError("Preserved model journal has incomplete requests")
    return [json.loads(raw) for _, raw in rows]


def status(normalizer, raw: str, observation) -> str:
    try:
        normalizer(raw, observation,
                   current_frame_id=observation.frame_id)
        return "accepted_synthetic_shape_only"
    except ContractError as exc:
        return exc.code


def audit(odoo_journal: Path, odoo_public_source: Path,
          desktop_attempts: list[Path]) -> dict:
    source_raw = odoo_public_source.read_bytes()
    source = json.loads(source_raw)
    if (source.get("partition") != "train_only"
            or source.get("official_hidden_task_used") is not False
            or source.get("model_actions_dispatched") != 0):
        raise ValueError("Odoo source is not a train-only no-dispatch sample")
    odoo = journal_rows(odoo_journal)
    if len(odoo) != 1 or odoo[0].get("status") != "completed":
        raise ValueError("Expected one preserved Odoo train sample")
    odoo_text = odoo[0]["text"]
    if sampling_digest(odoo_text) != source["sampling"]["text_sha256"]:
        raise ValueError("Odoo train response hash changed")
    full_action = _strict_json(odoo_text)
    if (full_action.get("type") != "click"
            or type(full_action.get("target")) is not dict
            or set(full_action["target"]) != {"ref"}):
        raise ValueError("Odoo historical fenced action shape changed")
    desktop_receipt_hashes = []
    counts = Counter()
    v064_results, v065_results = Counter(), Counter()
    for attempt_dir in desktop_attempts:
        receipt_path = attempt_dir / "receipt.json"
        receipt_raw = receipt_path.read_bytes()
        receipt = json.loads(receipt_raw)
        if (receipt.get("schema") != "cua-native-wdi-gui-development-attempt-v1"
                or receipt.get("split") != "train"
                or receipt.get("attempt") != "qwen_v064_nonfinal_smoke"
                or not receipt.get("task_binding_sha256")):
            raise ValueError("Desktop attempt is not a preserved train-only v0.6.4 smoke")
        journal = journal_rows(attempt_dir / "sampler-journal" / "requests.sqlite3")
        if len(journal) != len(receipt["sampling"]):
            raise ValueError("Desktop journal does not match receipt sample count")
        desktop_receipt_hashes.append(digest(receipt_raw))
        for index, (sample, receipt_sample) in enumerate(zip(journal, receipt["sampling"])):
            text = sample.get("text")
            if (sample.get("status") != "completed" or type(text) is not str
                    or sampling_digest(text) != receipt_sample["text_sha256"]):
                raise ValueError("Desktop model text differs from original sample receipt")
            frame_path = attempt_dir / f"frame-{index}.png"
            observation = make_observation(
                task_id=receipt["task_id"],
                task_binding_sha256=receipt["task_binding_sha256"],
                instruction="Offline train-frame parser audit only.",
                step=0, screenshot_bytes=frame_path.read_bytes(), controls=(),
            )
            try:
                stripped = text.strip()
                lines = stripped.splitlines()
                if lines and lines[0] in ("```", "```json") and lines[-1] == "```":
                    stripped = "\n".join(lines[1:-1])
                payload = json.loads(stripped)
            except (ValueError, TypeError):
                payload = {}
            counts["whole_response_fence" if text.strip().startswith("```") else "plain_json"] += 1
            counts["top_level_action_alias" if "action" in payload else
                   "top_level_type" if "type" in payload else "other_shape"] += 1
            target = payload.get("target")
            counts["coordinate_target" if type(target) is dict and set(target) == {"x", "y"} else
                   "control_ref_target" if type(target) is dict and set(target) == {"ref"} else
                   "other_target"] += 1
            v064_results[status(v064, text, observation)] += 1
            v065_results[status(v065, text, observation)] += 1
    if len(desktop_receipt_hashes) != len(set(desktop_receipt_hashes)):
        raise ValueError("Desktop train receipts duplicated")
    return {
        "schema": "cua-full-study-v065-nonfinal-offline-replay-v1",
        "checked_date": "2026-09-27",
        "scope": "Historical Odoo full-action JSON-fence syntax and Desktop v0.6.4 minimal-action shape only. Desktop observations are reconstructed from saved train screenshots with new synthetic current-frame IDs. No provider call, GUI dispatch, task score or hidden-final input.",
        "odoo_public_source_sha256": digest(source_raw),
        "odoo_historical_text_sha256": sampling_digest(odoo_text),
        "odoo_single_fence_full_action_parse_passed": True,
        "desktop_private_receipt_sha256s": desktop_receipt_hashes,
        "desktop_sample_count": sum(v065_results.values()),
        "desktop_response_shape_counts": dict(sorted(counts.items())),
        "desktop_v064_synthetic_shape_results": dict(sorted(v064_results.items())),
        "desktop_v065_synthetic_shape_results": dict(sorted(v065_results.items())),
        "v064_adapter_sha256": digest(Path(v064.__code__.co_filename).read_bytes()),
        "v065_adapter_sha256": digest(Path(v065.__code__.co_filename).read_bytes()),
        "new_provider_calls": 0,
        "new_gui_actions": 0,
        "official_hidden_task_used": False,
        "official_task_scores_added": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--odoo-journal", type=Path, required=True)
    parser.add_argument("--odoo-public-source", type=Path, required=True)
    parser.add_argument("--desktop-attempt-dir", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Refusing to overwrite offline replay")
    report = audit(args.odoo_journal, args.odoo_public_source,
                   args.desktop_attempt_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in (
        "desktop_sample_count", "desktop_v064_synthetic_shape_results",
        "desktop_v065_synthetic_shape_results", "new_provider_calls",
        "official_task_scores_added")}, sort_keys=True))


if __name__ == "__main__":
    main()
