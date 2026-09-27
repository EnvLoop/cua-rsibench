"""Publish a bounded partial Magento GUI-control milestone without scores.

The live v2 controller is immutable. This read-only adjunct snapshots its
hash-chained journal, verifies only complete 1/0/fresh-reset case receipts,
and reports aggregate development progress. It cannot issue task admission,
model success, or a final 100-case audit.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile

from tools import magento_resumable_100_v2 as v2


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "envloop-magento-resumable-progress-private-v1"
PUBLIC_SCHEMA = "envloop-magento-resumable-progress-public-v1"


def _write_new(path: Path, raw: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def audit(*, plan: Path, plan_sha256: str, source: Path,
          old_freeze: Path, freeze_v2: Path, run_dir: Path,
          private_dir: Path, public_out: Path,
          min_completed: int) -> dict:
    private = Path(private_dir).absolute()
    public = Path(public_out).absolute()
    work = ROOT / "work"
    v2.require(1 <= min_completed < 100 and
               not work.is_symlink() and
               private.parent.resolve().is_relative_to(work.resolve()) and
               not private.exists() and not private.is_symlink() and
               public.parent.resolve() == (ROOT / "docs/evidence").resolve() and
               not public.exists() and not public.is_symlink(),
               "new private audit and public aggregate paths required")
    frozen, old, freeze_sha = v2.validate_freeze(
        freeze_v2, old_freeze, plan, plan_sha256, source)
    cases = v2.validate_plan(plan, plan_sha256)
    live_journal = Path(run_dir) / "journal.private.jsonl"
    raw = live_journal.read_bytes()
    v2.require(raw.endswith(b"\n"),
               "live journal snapshot ended mid-row; retry read-only audit")
    # Validate a temporary snapshot first. A too-early or malformed milestone
    # must not strand the immutable output directory on a failed audit.
    with tempfile.TemporaryDirectory(
            prefix=".magento-progress-", dir=work) as scratch:
        snapshot = Path(scratch) / "journal-snapshot.private.jsonl"
        _write_new(snapshot, raw)
        events = v2.read_journal(snapshot)
    v2.validate_run_header(events, freeze_sha, frozen)
    v2.validate_case_sequence(events, cases)
    completed = [row for row in events
                 if row.get("event") == "case_completed"]
    started = [row for row in events
               if row.get("event") == "case_attempt_started"]
    retries = [row for row in events
               if row.get("event") == "attempt_reconciled"]
    v2.require(min_completed <= len(completed) < 100 and
               not retries and
               len(started) in (len(completed), len(completed) + 1) and
               events[-1].get("event") != "run_completed",
               "partial milestone count or retry history not eligible")
    receipts = []
    for index, row in enumerate(completed):
        digest = v2.verify_finished_attempt(
            run_dir, events, index, row["attempt"], cases[index],
            old["runtime_fingerprint_sha256"])
        v2.require(row.get("calibration_sha256") == digest,
                   "completed case calibration changed")
        receipts.append(digest)
    receipt_chain = sha256(("\n".join(receipts) + "\n").encode()).hexdigest()
    checked_at = datetime.now(timezone.utc).isoformat()
    private.mkdir(parents=True, mode=0o700)
    private.chmod(0o700)
    _write_new(private / "journal-snapshot.private.jsonl", raw)
    private_receipt = {
        "schema": SCHEMA,
        "checked_at_utc": checked_at,
        "freeze_v2_sha256": freeze_sha,
        "live_journal_snapshot_sha256": sha256(raw).hexdigest(),
        "completed_case_indices": list(range(len(completed))),
        "completed_calibration_sha256s": receipts,
        "active_unfinished_attempts": len(started) - len(completed),
        "infrastructure_retries": 0,
        "model_calls": 0,
        "official_final_admissions": 0,
    }
    private_raw = (json.dumps(private_receipt, sort_keys=True,
                              separators=(",", ":")) + "\n").encode()
    _write_new(private / "audit.private.json", private_raw)
    aggregate = {
        "schema": PUBLIC_SCHEMA,
        "status": "partial_evaluator_gui_controls_not_model_results",
        "checked_at_utc": checked_at,
        "candidate_final_count": 100,
        "completed_distinct_gui_controls": len(completed),
        "active_unfinished_attempts": len(started) - len(completed),
        "infrastructure_retries": 0,
        "positive_score_required": 1.0,
        "wrong_variant_score_required": 0.0,
        "fresh_reset_required": True,
        "freeze_v2_sha256": freeze_sha,
        "live_journal_snapshot_sha256": sha256(raw).hexdigest(),
        "completed_calibration_chain_sha256": receipt_chain,
        "private_audit_sha256": sha256(private_raw).hexdigest(),
        "model_calls": 0,
        "official_final_admissions": 0,
        "complete_100_case_audit": False,
    }
    with public.open("x", encoding="utf-8") as stream:
        json.dump(aggregate, stream, sort_keys=True, indent=2)
        stream.write("\n")
    return aggregate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--parent-freeze", type=Path, required=True)
    parser.add_argument("--freeze-v2", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    parser.add_argument("--min-completed", type=int, required=True)
    args = parser.parse_args()
    result = audit(plan=args.plan, plan_sha256=args.plan_sha256,
                   source=args.source, old_freeze=args.parent_freeze,
                   freeze_v2=args.freeze_v2, run_dir=args.run_dir,
                   private_dir=args.private_dir, public_out=args.public_out,
                   min_completed=args.min_completed)
    print(json.dumps({
        "status": result["status"],
        "completed_distinct_gui_controls":
            result["completed_distinct_gui_controls"],
        "official_final_admissions": 0,
        "model_calls": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
