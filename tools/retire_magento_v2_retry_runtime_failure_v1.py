"""Retire the stopped Magento attempt-1 pair after a missing-Playwright error.

The frozen v2 campaign exhausted its only same-ID retry. This tool does not
reopen that campaign. It first records a read-only exact-state audit, then
requires a separate explicit cleanup command for only the two mount-free
disposable containers. A clean future 100-case run needs a new protocol.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import time

from tools import magento_resumable_100_v2 as v2
from tools import magento_v2_modal_supplement_v1 as supplement


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_SCHEMA = "envloop-magento-v2-retry-runtime-failure-private-v1"
PUBLIC_SCHEMA = "envloop-magento-v2-retry-runtime-failure-public-v1"
SOURCE = Path(__file__)


def is_missing_playwright_before_gui(stderr: bytes) -> bool:
    return (b"ModuleNotFoundError: No module named 'playwright'" in stderr and
            b"from playwright.async_api import async_playwright" in stderr)


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def _write_new(path: Path, value: dict) -> str:
    raw = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return v2.sha(raw)


def _paths(run_dir: Path) -> dict[str, Path]:
    parent = run_dir / "attempts/case-014-attempt-1"
    return {
        "audit": parent / "operator-runtime-audit.private.json",
        "intent": parent / "operator-runtime-cleanup-intent.private.json",
        "receipt": parent / "operator-runtime-cleanup-receipt.private.json",
        "public": ROOT / "docs/evidence/magento-v2-retry-runtime-failure-2026-09-28.json",
        "pair": parent / "case-014/positive",
    }


def audit(*, plan: Path, plan_sha256: str, source: Path,
          parent_freeze: Path, freeze_v2: Path, run_dir: Path) -> tuple[dict, dict]:
    ctx = supplement.context(
        plan=plan, plan_sha256=plan_sha256, source=source,
        parent_freeze=parent_freeze, freeze_v2=freeze_v2, run_dir=run_dir)
    supplement.require_cleanup_lineage(ctx)
    events = ctx["events"]
    completed = [row for row in events if row.get("event") == "case_completed"]
    scoped = [row for row in v2.case_events(events, 14)
              if row.get("attempt") == 1]
    starts = [row for row in scoped if row.get("event") ==
              "case_attempt_started"]
    failed = [row for row in scoped if row.get("event") == "step_finished"
              and row.get("exit_code") != 0]
    steps = [row.get("step") for row in scoped
             if row.get("event") == "step_intent"]
    require(len(completed) == 14 and
            events[-1].get("event") == "attempt_stopped" and
            events[-1].get("index") == 14 and
            events[-1].get("attempt") == 1 and
            len(starts) == 1 and
            len(failed) == 1 and
            failed[0].get("step") == "positive-neutral" and
            steps == ["positive-prepare", "positive-seed",
                      "positive-neutral"] and
            not any(row.get("event") in ("positive-gui",
                                        "task_gui_calibrated")
                    for row in scoped),
            "only the exhausted pre-GUI attempt-1 runtime stop can be retired")
    paths = _paths(run_dir)
    pair = paths["pair"]
    stderr = (pair / "positive-neutral-stderr.private.bin").read_bytes()
    process, process_sha = v2.read_json(
        pair / "positive-neutral-process.private.json")
    prepared, prep_sha = v2.read_json(pair / "prepare.private.json")
    seed, seed_sha = v2.read_json(pair / "seed.private.json")
    v2.old_contract.validate_prepared(
        prepared, config_sha256=ctx["parent"]["runtime"]["cron_config_sha256"])
    require(process.get("exit_code") == failed[0]["exit_code"] and
            process.get("stderr_sha256") == failed[0].get("stderr_sha256") ==
            v2.sha(stderr) and
            is_missing_playwright_before_gui(stderr) and
            seed.get("task_id") == ctx["cases"][14]["task_id"] and
            starts[0].get("package_sha256") ==
            ctx["cases"][14]["package_sha256"] and
            not (pair / "neutral/private-before.json").exists() and
            not (pair / "neutral/private-after.json").exists() and
            not (pair / "neutral/result.json").exists() and
            not (pair / "gui-positive/result.json").exists(),
            "missing-Playwright failure or pre-GUI boundary changed")
    containers = v2._live_pair(prepared)
    prior = v2.attempt_dir(run_dir, 14, 0) / (
        "case-014/positive/neutral/private-before.json")
    baseline, baseline_sha = v2.read_json(prior)
    require(seed.get("page_id") == baseline.get("page_id"),
            "same-ID seeded quote page differs from the first attempt")
    first = v2.read_snapshot(
        ctx["cases"][14], v2.old_sweep.APP, 7794, 7795,
        seed["page_id"], search_host=v2.old_sweep.SEARCH)
    v2.check_baseline(ctx["cases"][14], first)
    require(first == baseline,
            "first read differs from the frozen pre-GUI seeded state")
    time.sleep(2)
    second = v2.read_snapshot(
        ctx["cases"][14], v2.old_sweep.APP, 7794, 7795,
        seed["page_id"], search_host=v2.old_sweep.SEARCH)
    require(second == baseline,
            "second read differs from the frozen pre-GUI seeded state")
    cron = v2.clone.verify_cron_never_autostarted()
    price = v2.clone.read_price_index_shape()
    require(cron.get("config_sha256") ==
            ctx["parent"]["runtime"]["cron_config_sha256"] and
            price.get("price_rows") == 8156 and
            price.get("price_changed_rows") == 0 and
            price.get("price_key_sets_equal") is True and
            price.get("live_price_sha256") ==
            price.get("replica_price_sha256"),
            "cron or price index drifted after the runtime failure")
    private = {
        "schema": PRIVATE_SCHEMA,
        "status": "attempt1_pre_gui_operator_runtime_failure_no_retry",
        "case_index": 14,
        "task_id": ctx["cases"][14]["task_id"],
        "package_sha256": ctx["cases"][14]["package_sha256"],
        "frozen_v2_sha256": ctx["freeze_sha256"],
        "supplement_source_sha256": ctx["source_public_sha256"],
        "journal_sha256": v2.sha(ctx["journal"].read_bytes()),
        "process_sha256": process_sha,
        "stderr_sha256": v2.sha(stderr),
        "prepare_sha256": prep_sha,
        "seed_sha256": seed_sha,
        "prior_pre_gui_snapshot_sha256": baseline_sha,
        "first_snapshot_sha256": v2.sha(v2.encode(first)),
        "second_snapshot_sha256": v2.sha(v2.encode(second)),
        "containers": containers,
        "cron_config_sha256": cron["config_sha256"],
        "price_shape_sha256": v2.sha(v2.encode(price)),
        "source_sha256": v2.sha(SOURCE.read_bytes()),
        "cleanup_authorized": False,
        "third_attempt_authorized": False,
        "model_calls": 0,
        "official_final_admitted": 0,
    }
    public = {
        "schema": PUBLIC_SCHEMA,
        "status": "v2_one_retry_exhausted_on_operator_python_dependency",
        "completed_distinct_evaluator_controls": 14,
        "failed_same_id_attempts": 2,
        "second_failure_stage": "positive_neutral_before_browser_or_candidate_edit",
        "second_failure_type": "missing_Playwright_in_operator_Python",
        "monitored_state_equal_to_first_pre_gui_snapshot_twice": True,
        "container_count_still_live": 2,
        "derived_price_changed_rows": 0,
        "frozen_v2_sha256": ctx["freeze_sha256"],
        "supplement_source_sha256": ctx["source_public_sha256"],
        "journal_sha256": private["journal_sha256"],
        "source_sha256": private["source_sha256"],
        "cleanup_authorized": False,
        "third_attempt_authorized": False,
        "v2_run_complete": False,
        "model_calls": 0,
        "official_final_admitted": 0,
    }
    return private, public


def _context(args: argparse.Namespace) -> dict:
    return {
        "plan": args.plan, "plan_sha256": args.plan_sha256,
        "source": args.source, "parent_freeze": args.parent_freeze,
        "freeze_v2": args.freeze_v2, "run_dir": args.run_dir,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("audit", "cleanup"))
    for key in ("plan", "source", "parent-freeze", "freeze-v2", "run-dir"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--execute-cleanup", action="store_true")
    args = parser.parse_args()
    paths = _paths(args.run_dir)
    if args.action == "audit":
        require(not paths["audit"].exists() and not paths["public"].exists(),
                "new private/public runtime-stop audit paths required")
        private, public = audit(**_context(args))
        private_sha = _write_new(paths["audit"], private)
        public["private_audit_sha256"] = private_sha
        out = paths["public"]
        fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(fd, "wb") as stream:
            stream.write((json.dumps(public, sort_keys=True, indent=2) +
                          "\n").encode())
        print(json.dumps({"status": public["status"],
                          "completed_distinct_evaluator_controls": 14,
                          "cleanup_authorized": False,
                          "official_final_admitted": 0}, sort_keys=True))
        return
    require(args.execute_cleanup,
            "explicit_execute_cleanup_required")
    saved, saved_sha = v2.read_json(paths["audit"])
    public, _ = v2.read_json(paths["public"])
    require(saved_sha == public.get("private_audit_sha256") and
            saved.get("schema") == PRIVATE_SCHEMA and
            saved.get("source_sha256") == v2.sha(SOURCE.read_bytes()) and
            saved.get("cleanup_authorized") is False and
            saved.get("third_attempt_authorized") is False and
            not paths["receipt"].exists(),
            "read-only source-bound audit required before exact cleanup")
    current, _ = audit(**_context(args))
    require(current == saved,
            "live pair, baseline or journal changed after read-only audit")
    if not paths["intent"].exists():
        _write_new(paths["intent"], {
            "schema": "envloop-magento-v2-attempt1-runtime-cleanup-intent-v1",
            "audit_sha256": saved_sha,
            "journal_sha256": saved["journal_sha256"],
            "containers": saved["containers"],
            "source_sha256": saved["source_sha256"],
            "third_attempt_authorized": False,
            "model_calls": 0, "official_final_admitted": 0,
        })
    intent, intent_sha = v2.read_json(paths["intent"])
    require(intent.get("audit_sha256") == saved_sha and
            intent.get("containers") == saved["containers"] and
            intent.get("source_sha256") == saved["source_sha256"],
            "cleanup intent changed")
    for item in saved["containers"]:
        name = item["name"]
        info = v2._docker_inspect(name)
        require(info is not None and
                v2.sha(info["Id"].encode()) == item["container_id_sha256"] and
                info["Image"] == item["image_sha256"] and
                info.get("Mounts") == [] and
                info["State"]["Running"] is True,
                "disposable container differs before exact cleanup")
        for action in ("stop", "rm"):
            current = v2._docker_inspect(name)
            require(current is not None and
                    v2.sha(current["Id"].encode()) ==
                    item["container_id_sha256"] and
                    current["Image"] == item["image_sha256"] and
                    current.get("Mounts") == [] and
                    current["State"]["Running"] is (action == "stop"),
                    "disposable container changed before cleanup action")
            marker = paths["intent"].with_name(
                f"operator-runtime-{name}-{action}.private.json")
            require(not marker.exists(),
                    "partial cleanup needs manual review; no auto replay")
            _write_new(marker, {"schema":
                       "envloop-magento-v2-attempt1-cleanup-step-intent-v1",
                       "name": name, "action": action,
                       "container_id_sha256": item["container_id_sha256"],
                       "image_sha256": item["image_sha256"],
                       "cleanup_intent_sha256": intent_sha})
            result = subprocess.run(
                ["docker", "--context", "colima-cua-scale", action, name],
                capture_output=True, timeout=70)
            require(result.returncode == 0,
                    "exact cleanup stopped; inspect immutable step intent")
            _write_new(marker.with_name(
                f"operator-runtime-{name}-{action}-result.private.json"),
                {"schema":
                 "envloop-magento-v2-attempt1-cleanup-step-result-v1",
                 "name": name, "action": action,
                 "stdout_sha256": v2.sha(result.stdout),
                 "stderr_sha256": v2.sha(result.stderr),
                 "cleanup_intent_sha256": intent_sha})
    v2.old_sweep.assert_absent()
    receipt_sha = _write_new(paths["receipt"], {
        "schema": "envloop-magento-v2-attempt1-runtime-cleanup-receipt-v1",
        "status": "exact_disposable_pair_retired_v2_campaign_incomplete",
        "audit_sha256": saved_sha,
        "cleanup_intent_sha256": intent_sha,
        "both_containers_absent": True,
        "third_attempt_authorized": False,
        "model_calls": 0, "official_final_admitted": 0,
    })
    print(json.dumps({"status":
                      "exact_disposable_pair_retired_v2_campaign_incomplete",
                      "cleanup_receipt_sha256": receipt_sha,
                      "official_final_admitted": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
