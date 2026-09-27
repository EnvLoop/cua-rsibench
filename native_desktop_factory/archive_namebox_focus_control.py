"""Archive one Calc known-positive Name Box focus failure before a fresh retry."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

if __package__:
    from .verify import verify, xlsx_cells
else:
    from verify import verify, xlsx_cells


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def plan(candidate_root: Path, attempts_root: Path, task_id: str,
         patched_sweeper: Path) -> dict:
    package = candidate_root / "final_candidate" / task_id
    oracle = json.loads((package / "oracle.json").read_bytes())
    if oracle["workflow"] not in ("calc-growth", "calc-risk"):
        raise ValueError("Only v2 Calc known-positive controls are supported")
    baseline = next(package.glob("*.xlsx")).read_bytes()
    original_dir = attempts_root / task_id / "positive"
    receipt_raw = (original_dir / "receipt.json").read_bytes()
    receipt = json.loads(receipt_raw)
    saved = (original_dir / "saved.xlsx").read_bytes()
    if receipt["status"] != "control_failed" or receipt.get("kill_returned") is not True or receipt.get("is_running_after_kill") is not False:
        raise ValueError("Original failed control or cleanup does not match")
    if receipt.get("command_errors") or receipt.get("error_type") or not receipt.get("actor_actions"):
        raise ValueError("Not a clean known-positive GUI focus failure")
    if receipt["input_sha256"] != digest(baseline) or receipt["saved_sha256"] != digest(saved):
        raise ValueError("Baseline/saved artifact differs from receipt")
    result = verify(baseline, saved, oracle)
    targets = sorted(oracle["targets"])
    expected_errors = sorted(error for address in targets for error in
                             ("target_formula_wrong:" + address,
                              "target_cached_result_missing:" + address))
    if result != receipt.get("verifier") or sorted(result.get("errors", [])) != expected_errors:
        raise ValueError("Failure is not exactly three untouched target formulas")
    before, after = xlsx_cells(baseline), xlsx_cells(saved)
    if any(before[sheet][cell]["formula"] != after[sheet][cell]["formula"]
           for sheet, cell in (address.split("!", 1) for address in targets)):
        raise ValueError("Target formula changed despite focus-failure classification")
    patched = patched_sweeper.read_bytes()
    if b'Direct grid clicks avoid a' not in patched:
        raise ValueError("Corrected direct-grid Calc action is absent")
    archive = attempts_root / task_id / "_calibration_invalid" / ("positive-" + digest(receipt_raw)[:12])
    if archive.exists():
        raise ValueError("Failed control already archived")
    return {"task_id": task_id, "original_dir": original_dir, "archive_dir": archive,
            "original_receipt_sha256": digest(receipt_raw),
            "original_saved_sha256": digest(saved),
            "patched_sweeper_sha256": digest(patched),
            "reason": "all_three_target_formulas_untouched; screenshot shows LibreOffice invalid-reference modal and formula text in Name Box; direct-grid action requires fresh validation"}


def apply(item: dict, out: Path) -> dict:
    if out.exists():
        raise ValueError("Refusing to overwrite calibration recovery receipt")
    item["archive_dir"].parent.mkdir(parents=True, exist_ok=True)
    item["original_dir"].rename(item["archive_dir"])
    if digest((item["archive_dir"] / "receipt.json").read_bytes()) != item["original_receipt_sha256"]:
        raise ValueError("Archived failed Calc control receipt changed")
    result = {"schema": "cua-native-calc-known-positive-focus-recovery-v1",
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
