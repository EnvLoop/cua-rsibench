"""Aggregate-only audit of a retained Impress known-positive timing miss."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
from pathlib import Path

if __package__:
    from . import admit
else:
    import admit


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def summarize(candidate_root: Path, attempts_root: Path,
              private_map: Path, archive_ledger: Path, retry_run: Path) -> dict:
    archive_raw, retry_raw = archive_ledger.read_bytes(), retry_run.read_bytes()
    archive, run = json.loads(archive_raw), json.loads(retry_raw)
    if archive.get("status") != "failed_gui_control_archived_pending_one_corrected_retry":
        raise ValueError("Original calibration failure archive missing")
    task_id = archive["private_task_id"]
    archived_receipt = attempts_root / archive["archive_relative"] / "receipt.json"
    if digest(archived_receipt.read_bytes()) != archive["original_receipt_sha256"]:
        raise ValueError("Original failed control receipt changed")
    if run.get("schema") != "cua-native-wdi-final-gui-sweep-v1" or run.get("dry_run") is not False:
        raise ValueError("Corrected retry is not an actual GUI sweep")
    results = [r for r in run["results"] if r["task_id"] == task_id]
    if len(results) != 1 or results[0]["status"] != "gui_controls_passed":
        raise ValueError("Fresh corrected GUI trio did not pass")
    row = json.loads((candidate_root / "final_candidate" / task_id / "package.json").read_bytes())
    admitted = admit.admit_one(candidate_root, attempts_root, row)
    mapping = json.loads(private_map.read_bytes())
    key = bytes.fromhex(mapping["variant_salt"])
    return {"schema": "cua-native-impress-gui-calibration-repair-public-v1",
            "checked_date": "2026-09-25",
            "opaque_task_ref": hmac.new(key, task_id.encode(), hashlib.sha256).hexdigest(),
            "original_partial_positive_receipt_sha256": archive["original_receipt_sha256"],
            "original_partial_saved_artifact_sha256": archive["original_saved_sha256"],
            "archive_ledger_sha256": digest(archive_raw),
            "patched_sweeper_sha256": archive["patched_sweeper_sha256"],
            "corrected_retry_run_receipt_sha256": digest(retry_raw),
            "fresh_positive_near_miss_reset_receipt_sha256": admitted["attempt_receipt_sha256"],
            "old_known_positive_gui_result": "first_target_unchanged_other_two_correct; independently_rejected",
            "fresh_corrected_gui_result": "positive_accepted_near_miss_rejected_cold_reset_verified",
            "interpretation": "A two-second slide transition wait is consistent with recovery of the first-target click. The original partial attempt is retained; no student/model outcome was involved.",
            "official_full_study_admitted_final_count": 0,
            "official_model_result_count": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--attempts-root", type=Path, required=True)
    parser.add_argument("--private-map", type=Path, required=True)
    parser.add_argument("--archive-ledger", type=Path, required=True)
    parser.add_argument("--retry-run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Refusing to overwrite public calibration evidence")
    result = summarize(args.candidate_root, args.attempts_root,
                       args.private_map, args.archive_ledger, args.retry_run)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": result["fresh_corrected_gui_result"],
                      "receipt_sha256": digest(args.out.read_bytes())}, sort_keys=True))


if __name__ == "__main__":
    main()
