"""Read-only source-bound audit of the stopped Magento v2 neutral UI step.

This is evaluator development evidence. It cannot classify a v2 retry, clean
containers, admit a final task, or issue a model score. The existing v2
reconciler deliberately refuses this previously unlisted timeout.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time

from tools import magento_resumable_100_v2 as v2


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "envloop-magento-v2-modal-stop-audit-private-v1"
PUBLIC_SCHEMA = "envloop-magento-v2-modal-stop-audit-public-v1"


def is_premutation_modal_timeout(stderr: bytes) -> bool:
    """Match the specific Content-menu obstruction, not an arbitrary timeout."""
    return all(marker in stderr for marker in (
        b"Locator.click: Timeout 60000ms exceeded.",
        b"line 50, in read_quote_in_gui",
        b"admin__form-loading-mask",
        b"modal-popup confirm _show",
        b"intercepts pointer events",
    ))


def audit(*, plan: Path, plan_sha256: str, source: Path,
          parent_freeze: Path, freeze_v2: Path, run_dir: Path) -> tuple[dict, dict]:
    frozen, parent, freeze_sha = v2.validate_freeze(
        freeze_v2, parent_freeze, plan, plan_sha256, source)
    cases = v2.validate_plan(plan, plan_sha256)
    journal = run_dir / "journal.private.jsonl"
    raw_journal = journal.read_bytes()
    events = v2.read_journal(journal)
    v2.validate_run_header(events, freeze_sha, frozen)
    v2.validate_case_sequence(events, cases)
    completed = [row for row in events if row.get("event") == "case_completed"]
    index = len(completed)
    v2.require(index == 14 and events[-1].get("event") == "attempt_stopped" and
               events[-1].get("index") == index and
               not any(row.get("event") in ("attempt_reconciled", "run_completed")
                       for row in events),
               "only the retained fifteenth-case v2 stop may be audited")
    for ordinal, row in enumerate(completed):
        observed = v2.verify_finished_attempt(
            run_dir, events, ordinal, row["attempt"], cases[ordinal],
            parent["runtime_fingerprint_sha256"])
        v2.require(row.get("calibration_sha256") == observed,
                   "a previous passing control changed")
    scoped = [row for row in v2.case_events(events, index)
              if row.get("attempt") == 0]
    failed = [row for row in scoped if row.get("event") == "step_finished"
              and row.get("exit_code") != 0]
    steps = [row.get("step") for row in scoped
             if row.get("event") == "step_intent"]
    v2.require(len(failed) == 1 and failed[0].get("step") ==
               "positive-neutral" and steps == [
                   "positive-prepare", "positive-seed", "positive-neutral"] and
               not any(row.get("event") == "task_gui_calibrated" for row in scoped),
               "stopped step is not the pre-edit positive neutral control")
    pair = v2.attempt_dir(run_dir, index, 0) / f"case-{index:03d}" / "positive"
    process, process_sha = v2.read_json(
        pair / "positive-neutral-process.private.json")
    stderr = (pair / "positive-neutral-stderr.private.bin").read_bytes()
    before, before_sha = v2.read_json(pair / "neutral/private-before.json")
    prepared, prepared_sha = v2.read_json(pair / "prepare.private.json")
    seed, seed_sha = v2.read_json(pair / "seed.private.json")
    v2.old_contract.validate_prepared(
        prepared, config_sha256=parent["runtime"]["cron_config_sha256"])
    v2.require(process.get("exit_code") == failed[0]["exit_code"] and
               process.get("stderr_sha256") == failed[0].get("stderr_sha256") ==
               v2.sha(stderr) and
               is_premutation_modal_timeout(stderr) and
               seed.get("task_id") == cases[index]["task_id"] and
               before.get("page_id") == seed.get("page_id") and
               not (pair / "neutral/private-after.json").exists() and
               not (pair / "neutral/result.json").exists() and
               not (pair / "gui-positive/result.json").exists() and
               not any(step == "positive-gui" for step in steps),
               "modal timeout or pre-edit evidence changed")
    witness = v2._material_witness(
        cases[index], pair, scoped, exact_pre_gui=False)
    v2.require(witness.get("state") == "seeded_pre_gui" and
               witness.get("material_equal_exact") is True and
               witness.get("material_current_snapshot") == before and
               witness.get("allowed_volatile_fields") == [] and
               len(witness.get("containers", [])) == 2,
               "first live readback differs from the seeded pre-GUI state")
    time.sleep(2)
    second = v2.read_snapshot(
        cases[index], v2.old_sweep.APP, 7794, 7795, seed["page_id"],
        search_host=v2.old_sweep.SEARCH)
    v2.require(second == before,
               "second live readback differs from the seeded pre-GUI state")
    cron = v2.clone.verify_cron_never_autostarted()
    price = v2.clone.read_price_index_shape()
    v2.require(cron.get("config_sha256") ==
               parent["runtime"]["cron_config_sha256"] and
               price.get("price_rows") == 8156 and
               price.get("price_changed_rows") == 0 and
               price.get("price_key_sets_equal") is True and
               price.get("live_price_sha256") ==
               price.get("replica_price_sha256"),
               "cron or derived price index drifted after the neutral stop")
    private = {
        "schema": SCHEMA,
        "status": "pre_edit_modal_obstruction_material_exact_no_retry_authorized",
        "case_index": index,
        "task_id": cases[index]["task_id"],
        "package_sha256": cases[index]["package_sha256"],
        "plan_sha256": plan_sha256,
        "freeze_v2_sha256": freeze_sha,
        "journal_sha256": v2.sha(raw_journal),
        "process_sha256": process_sha,
        "stderr_sha256": v2.sha(stderr),
        "prepare_sha256": prepared_sha,
        "seed_sha256": seed_sha,
        "pre_gui_snapshot_sha256": before_sha,
        "second_snapshot_sha256": v2.sha(v2.encode(second)),
        "material_witness": witness,
        "cron_config_sha256": cron["config_sha256"],
        "price_shape_sha256": v2.sha(v2.encode(price)),
        "source_sha256": v2.sha(Path(__file__).read_bytes()),
        "model_calls": 0,
        "official_final_admitted": 0,
        "cleanup_authorized": False,
        "retry_authorized": False,
    }
    public = {
        "schema": PUBLIC_SCHEMA,
        "status": "fourteen_controls_then_pre_edit_modal_stop",
        "completed_distinct_evaluator_controls": 14,
        "stopped_case_ordinal": 15,
        "failure_stage": "positive_neutral_before_candidate_gui_edit",
        "failure_class": "release_notification_mask_and_confirm_modal_intercepted_content_menu",
        "live_material_exact_on_two_reads": True,
        "derived_price_rows": 8156,
        "derived_price_changed_rows": 0,
        "container_count_still_live": 2,
        "freeze_v2_sha256": freeze_sha,
        "journal_sha256": v2.sha(raw_journal),
        "source_sha256": private["source_sha256"],
        "cleanup_authorized": False,
        "retry_authorized": False,
        "complete_100_case_audit": False,
        "model_calls": 0,
        "official_final_admitted": 0,
    }
    return private, public


def _write_new(path: Path, raw: bytes, mode: int) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plan", "source", "parent-freeze", "freeze-v2",
                 "run-dir", "private-out", "public-out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    args = parser.parse_args()
    private_out = args.private_out.absolute()
    public_out = args.public_out.absolute()
    v2.require(not private_out.exists() and not public_out.exists() and
               private_out.parent.resolve().is_relative_to(
                   (ROOT / "work").resolve()) and
               public_out.parent.resolve() ==
               (ROOT / "docs/evidence").resolve(),
               "new private and public audit paths required")
    private, public = audit(
        plan=args.plan, plan_sha256=args.plan_sha256,
        source=args.source, parent_freeze=args.parent_freeze,
        freeze_v2=args.freeze_v2, run_dir=args.run_dir)
    private_out.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    private_out.parent.chmod(0o700)
    private_raw = (json.dumps(private, sort_keys=True,
                              separators=(",", ":")) + "\n").encode()
    _write_new(private_out, private_raw, 0o600)
    public["private_audit_sha256"] = v2.sha(private_raw)
    _write_new(public_out, (json.dumps(public, indent=2,
                                      sort_keys=True) + "\n").encode(), 0o644)
    print(json.dumps({"status": public["status"],
                      "completed_distinct_evaluator_controls": 14,
                      "cleanup_authorized": False,
                      "retry_authorized": False,
                      "official_final_admitted": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
