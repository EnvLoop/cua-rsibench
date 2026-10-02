"""Archive one Writer near-miss whose native Find lost document focus.

The known-negative needs exactly one wrong target with no collateral edits.
This archived attempt changed a non-target paragraph and is never admissible.
The original DOCX, screenshots, and receipt are preserved before one fresh
GUI retry with explicit Find-focus settling waits.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

if __package__:
    from .verify import docx_content, verify
else:
    from verify import docx_content, verify


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def plan(candidate_root: Path, attempts_root: Path, task_id: str,
         patched_sweeper: Path) -> dict:
    package = candidate_root / "final_candidate" / task_id
    oracle = json.loads((package / "oracle.json").read_bytes())
    if oracle["workflow"] != "writer-brief":
        raise ValueError("Only final Writer controls are supported")
    baseline = next(package.glob("*.docx")).read_bytes()
    directory = attempts_root / task_id
    positive = json.loads((directory / "positive" / "receipt.json").read_bytes())
    cold = json.loads((directory / "cold-reset" / "receipt.json").read_bytes())
    if positive.get("status") != "control_passed" or positive.get("verifier", {}).get("passed") is not True:
        raise ValueError("Writer positive control is not independently accepted")
    if cold.get("status") != "cold_reset_observed" or cold.get("restored_state_sha256") != digest(baseline):
        raise ValueError("Writer cold reset is incomplete")
    if positive.get("is_running_after_kill") is not False or cold.get("is_running_after_kill") is not False:
        raise ValueError("Positive/cold sandbox termination unverified")
    old = directory / "near-miss"
    receipt_raw = (old / "receipt.json").read_bytes()
    receipt = json.loads(receipt_raw)
    saved = (old / "saved.docx").read_bytes()
    if receipt.get("status") != "control_passed" or receipt.get("kill_returned") is not True or receipt.get("is_running_after_kill") is not False:
        raise ValueError("Original near-miss did not finish and terminate")
    if receipt.get("command_errors") or receipt.get("error_type") or not receipt.get("actor_actions"):
        raise ValueError("Not a clean native Find GUI execution failure")
    if receipt["input_sha256"] != digest(baseline) or receipt["saved_sha256"] != digest(saved):
        raise ValueError("Writer input/saved bytes differ from receipt")
    result = verify(baseline, saved, oracle)
    errors = result.get("errors", [])
    if result != receipt.get("verifier") or result.get("passed") is not False:
        raise ValueError("Independent Writer verifier differs")
    if errors == ["paragraph_count_changed"]:
        before_count = len(docx_content(baseline)["paragraphs"])
        after_count = len(docx_content(saved)["paragraphs"])
        if after_count != before_count + 1:
            raise ValueError("Paragraph-count failure differs from one misfocused insertion")
        pattern = "extra_non_target_paragraph_inserted_by_misfocused_Find"
    elif ("non_target_text_changed:paragraph1" in errors and
          sum(x.startswith("target_text_wrong:") for x in errors) == 2 and
          all(x.startswith("target_text_wrong:") or x == "non_target_text_changed:paragraph1" for x in errors)):
        pattern = "non_target_paragraph_changed_two_targets_remain_wrong"
    else:
        raise ValueError("Failure is not the observed native Find focus/collateral pattern")
    patched = patched_sweeper.read_bytes()
    if b'"press ctrl,h", "wait 1"' not in patched or b'"click 877,390", "wait 1"' not in patched:
        raise ValueError("Corrected native Find-and-Replace dialog protocol absent")
    archive = directory / "_calibration_invalid" / ("near-miss-" + digest(receipt_raw)[:12])
    if archive.exists():
        raise ValueError("Failed Writer near-miss already archived")
    return {"task_id": task_id, "original_dir": old, "archive_dir": archive,
            "original_receipt_sha256": digest(receipt_raw),
            "original_saved_sha256": digest(saved),
            "patched_sweeper_sha256": digest(patched),
            "reason": f"native Ctrl+F lost document focus ({pattern}); fresh Find-and-Replace dialog control required"}


def apply(item: dict, output: Path) -> dict:
    if output.exists():
        raise ValueError("Refusing to overwrite Writer recovery receipt")
    item["archive_dir"].parent.mkdir(parents=True, exist_ok=True)
    item["original_dir"].rename(item["archive_dir"])
    if digest((item["archive_dir"] / "receipt.json").read_bytes()) != item["original_receipt_sha256"]:
        raise ValueError("Archived Writer receipt changed")
    result = {"schema": "cua-native-writer-find-focus-recovery-v1",
              "status": "failed_gui_control_archived_pending_one_corrected_retry",
              "private_task_id": item["task_id"],
              "original_receipt_sha256": item["original_receipt_sha256"],
              "original_saved_sha256": item["original_saved_sha256"],
              "patched_sweeper_sha256": item["patched_sweeper_sha256"],
              "reason": item["reason"],
              "archive_relative": item["archive_dir"].relative_to(item["original_dir"].parents[1]).as_posix(),
              "official_model_score": None}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--attempts-root", type=Path, required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--patched-sweeper", type=Path, default=Path(__file__).with_name("calibrate_sweep.py"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    item = plan(args.candidate_root, args.attempts_root, args.task_id, args.patched_sweeper)
    if args.apply:
        result = apply(item, args.out)
        print(json.dumps({"status": result["status"],
                          "original_receipt_sha256": result["original_receipt_sha256"]}, sort_keys=True))
    else:
        print(json.dumps({"dry_run": True, "reason": item["reason"]}, sort_keys=True))


if __name__ == "__main__":
    main()
