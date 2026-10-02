"""Preserve one failed known-positive Impress control before a corrected retry.

The strict pattern is a slide-five first-target miss with other targets and
non-target state correct. This is evaluator-script calibration, never a student
outcome. The original saved PPTX, screenshots and action receipt are archived.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

if __package__:
    from .verify import pptx_slide_shapes, verify
else:
    from verify import pptx_slide_shapes, verify


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def plan(candidate_root: Path, attempts_root: Path, task_id: str,
         patched_sweeper: Path) -> dict:
    package = candidate_root / "final_candidate" / task_id
    oracle = json.loads((package / "oracle.json").read_bytes())
    if oracle["workflow"] != "impress-deck" or oracle["target_slide"] != 5:
        raise ValueError("Only v2 slide-five Impress controls are supported")
    baseline = next(package.glob("*.pptx")).read_bytes()
    original_dir = attempts_root / task_id / "positive"
    receipt_raw = (original_dir / "receipt.json").read_bytes()
    receipt = json.loads(receipt_raw)
    saved = (original_dir / "saved.pptx").read_bytes()
    if receipt["status"] != "control_failed" or receipt.get("kill_returned") is not True or receipt.get("is_running_after_kill") is not False:
        raise ValueError("Original failed control or cleanup does not match")
    if receipt.get("command_errors") or receipt.get("error_type") or not receipt.get("actor_actions"):
        raise ValueError("Failure is not a clean known-positive GUI script miss")
    if receipt["input_sha256"] != digest(baseline) or receipt["saved_sha256"] != digest(saved):
        raise ValueError("Input/saved artifact differs from receipt")
    result = verify(baseline, saved, oracle)
    if result != receipt.get("verifier") or result.get("errors") != ["target_text_wrong:slide5:shape4"]:
        raise ValueError("Failure is not exactly the first target text miss")
    before, after = pptx_slide_shapes(baseline)[4], pptx_slide_shapes(saved)[4]
    targets = [(i, old, oracle["targets"][old]) for i, old in enumerate(before)
               if old in oracle["targets"]]
    if len(targets) != 3 or after[targets[0][0]] != targets[0][1] or any(after[i] != expected for i, _, expected in targets[1:]):
        raise ValueError("Observed slide changes differ from the timing-miss pattern")
    patched = patched_sweeper.read_bytes()
    if b'"click 81,557", "wait 2"' not in patched:
        raise ValueError("Corrected slide transition wait is absent from sweeper")
    archive = attempts_root / task_id / "_calibration_invalid" / ("positive-" + digest(receipt_raw)[:12])
    if archive.exists():
        raise ValueError("Failed control already archived")
    return {"task_id": task_id, "original_dir": original_dir, "archive_dir": archive,
            "original_receipt_sha256": digest(receipt_raw),
            "original_saved_sha256": digest(saved),
            "patched_sweeper_sha256": digest(patched),
            "reason": "observed_first_target_unchanged_after_slide_navigation; GUI timing fix is a hypothesis to verify in a fresh sandbox"}


def apply(item: dict, out: Path) -> dict:
    if out.exists():
        raise ValueError("Refusing to overwrite calibration recovery receipt")
    item["archive_dir"].parent.mkdir(parents=True, exist_ok=True)
    item["original_dir"].rename(item["archive_dir"])
    if digest((item["archive_dir"] / "receipt.json").read_bytes()) != item["original_receipt_sha256"]:
        raise ValueError("Archived failed calibration receipt hash changed")
    result = {"schema": "cua-native-impress-known-positive-calibration-recovery-v1",
              "status": "failed_gui_control_archived_pending_one_corrected_retry",
              "private_task_id": item["task_id"],
              "original_receipt_sha256": item["original_receipt_sha256"],
              "original_saved_sha256": item["original_saved_sha256"],
              "patched_sweeper_sha256": item["patched_sweeper_sha256"],
              "reason": item["reason"],
              "archive_relative": item["archive_dir"].relative_to(item["original_dir"].parents[1]).as_posix(),
              "official_model_score": None}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
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
