"""Audit and retire a stopped Magento positive with only a low-stock clock.

The failed development control remains immutable. A new scorer may recognize
the target product's system-owned timestamp, but this tool never silently
turns the stopped sweep into an admitted final task or model result.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import time

from magento_catalog_factory.plan import ROOT, require
from magento_catalog_factory.seed import load_case
from magento_catalog_factory.verify import read_snapshot, score_saved_state
from tools.sweep_magento_original_gui_controls_v1 import (
    append_event, assert_absent, cleanup_pair, sha, write_new,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sweep-dir", type=Path, required=True)
    parser.add_argument("--index", type=int, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()
    private = (ROOT / "work").resolve()
    sweep, plan = args.sweep_dir.resolve(), args.plan.resolve()
    require(sweep.is_relative_to(private) and plan.is_relative_to(private) and
            sha(plan.read_bytes()) == args.plan_sha256,
            "private stopped sweep and frozen plan required")
    journal = sweep / "events.private.jsonl"
    events = [json.loads(line) for line in journal.read_bytes().splitlines()]
    require(events and events[-1]["event"] == "sweep_stopped" and
            any(row.get("event") == "step_finished" and
                row.get("index") == args.index and
                row.get("step") == "positive-gui" and
                row.get("exit_code") != 0 for row in events) and
            not any(row.get("index") == args.index and
                    row.get("step", "").startswith("negative-") for row in events),
            "failure is not an isolated post-positive GUI stop")
    manifest = json.loads(plan.read_bytes())
    case_row = manifest["cases"]["official_candidate"][args.index]
    case = load_case(plan, args.plan_sha256, case_row["task_id"])
    positive = sweep / f"case-{args.index:03d}/positive"
    before_path = positive / "gui-positive/private-before.json"
    after_path = positive / "gui-positive/private-after.json"
    runtime_path = positive / "runtime.private.json"
    seed_path = positive / "seed.private.json"
    require(all(path.is_file() for path in
                (before_path, after_path, runtime_path, seed_path)),
            "positive GUI state/runtime receipt missing")
    before_raw, after_raw = before_path.read_bytes(), after_path.read_bytes()
    before, after = json.loads(before_raw), json.loads(after_raw)
    score = score_saved_state(case, before, after)
    require(score["score"] == 1.0 and score["failure_codes"] == [] and
            score["allowed_volatile_fields"] ==
            ["target_stock_low_stock_date_clock"],
            "positive saved state has a material collateral mutation")
    seed = json.loads(seed_path.read_bytes())
    require(seed["task_id"] == case["task_id"] and
            seed["page_id"] == before["page_id"] == after["page_id"],
            "source/task/page binding changed")
    lock_path = ROOT / "work/magento-original/exclusive-worker.lock"
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        current = read_snapshot(case, "envloop-magento-original-control", 7794,
                                7795, seed["page_id"],
                                search_host="envloop-magento-native-es")
        current_score = score_saved_state(case, before, current)
        require(current_score["score"] == 1.0 and
                current_score["allowed_volatile_fields"] ==
                ["target_stock_low_stock_date_clock"],
                "live disposable pair no longer matches material positive state")
        if args.audit_only:
            print(json.dumps({"status": "postpositive_volatile_state_audited",
                              "saved_positive_score": 1.0,
                              "live_positive_score": 1.0,
                              "model_calls": 0,
                              "official_final_admitted": 0}, sort_keys=True))
            return
        cleanup_pair(runtime_path)
        assert_absent()
        receipt = {
            "schema": "envloop-magento-postpositive-volatile-cleanup-private-v1",
            "status": "stopped_positive_pair_retired_for_explicit_recovery",
            "index": args.index,
            "task_id": case["task_id"],
            "plan_sha256": args.plan_sha256,
            "original_journal_sha256": sha(journal.read_bytes()),
            "before_sha256": sha(before_raw),
            "after_sha256": sha(after_raw),
            "live_state_sha256": sha((json.dumps(current, sort_keys=True,
                                                 separators=(",", ":")) + "\n").encode()),
            "runtime_sha256": sha(runtime_path.read_bytes()),
            "saved_positive_score_under_revised_verifier": score["score"],
            "allowed_volatile_fields": score["allowed_volatile_fields"],
            "both_containers_cleaned": True,
            "task_seeded": True,
            "model_calls": 0,
            "official_final_admitted": 0,
        }
        receipt_sha = write_new(positive / "recovery-cleanup.private.json",
                                receipt)
        append_event(journal, {
            "event": "operator_reconciled_postpositive_volatile",
            "index": args.index, "time": time.time(),
            "task_seeded": True,
            "both_containers_cleaned": True,
            "cleanup_receipt_sha256": receipt_sha,
            "model_calls": 0,
            "official_final_admitted": 0,
        })
        print(json.dumps({"status": receipt["status"],
                          "cleanup_receipt_sha256": receipt_sha,
                          "official_final_admitted": 0}, sort_keys=True))
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


if __name__ == "__main__":
    main()
