"""Fail-closed, per-case native-GUI solvability gate for one Odoo partition.

Known-answer oracle checks never count as a researcher/model attempt. A case
passes only after cold restore, source readback, native GUI positive, a
plausible GUI wrong-object negative, independent SQL+filestore scoring and a
second exact cold restore. A global study freeze is still needed before any
case is called an official hidden final task.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
from datetime import datetime, timezone

from factory import PRIVATE, local_config
from gui_controls import (
    browser_login, crm_case, inventory_case, open_crm, open_inventory_note,
    open_purchase, open_replenishment, open_sales, purchase_case, sales_case,
    view_attachment,
)
from partition_factory import ALL_SPLIT_COUNTS, FAMILIES
from reset import file_hash, restore
from verify import score
from worker_lease import exclusive_worker_operation, require_worker_lease

NEGATIVE_CODES = {
    "purchase": "unrelated_order_line_changed",
    "inventory": "unrelated_replenishment_rule_changed",
    "sales": "unrelated_sales_order_changed",
    "crm": "unrelated_crm_opportunity_changed",
}


def _case_index() -> tuple[dict, list[tuple[str, dict, dict]]]:
    world = json.loads((PRIVATE / "partition_cases.json").read_text())
    if world["split"] != local_config().get("ODOO_PARTITION"):
        raise RuntimeError("Partition manifest and worker configuration differ")
    rows = []
    for family in FAMILIES:
        family_cases = world["cases"][family]
        for position, case in enumerate(family_cases):
            rows.append((family, case, family_cases[(position + 1) % len(family_cases)]))
    return world, rows


def _positive_gui(page, port: int, family: str, case: dict) -> bool:
    if family == "purchase":
        open_purchase(page, port, case["id"])
        visible = view_attachment(page, f"{case['id']}-source.pdf")
        purchase_case(page, case, positive=True)
    elif family == "inventory":
        visible = open_inventory_note(page, port, case)
        open_replenishment(page, port)
        inventory_case(page, case, positive=True)
    elif family == "sales":
        open_sales(page, port, case["id"])
        visible = view_attachment(page, f"{case['id']}-source.pdf")
        sales_case(page, case, positive=True)
    elif family == "crm":
        open_crm(page, port, case["id"])
        visible = view_attachment(page, f"{case['id']}-source.pdf")
        crm_case(page, case, positive=True)
    else:
        raise ValueError(family)
    return visible


def _negative_gui(page, port: int, family: str, wrong_case: dict) -> None:
    if family == "purchase":
        open_purchase(page, port, wrong_case["id"])
        purchase_case(page, wrong_case, positive=False)
    elif family == "inventory":
        open_replenishment(page, port)
        inventory_case(page, wrong_case, positive=False)
    elif family == "sales":
        open_sales(page, port, wrong_case["id"])
        sales_case(page, wrong_case, positive=False)
    elif family == "crm":
        open_crm(page, port, wrong_case["id"])
        crm_case(page, wrong_case, positive=False)
    else:
        raise ValueError(family)


def admit_one(family: str, case: dict, wrong_case: dict) -> dict:
    from playwright.sync_api import sync_playwright

    config = local_config()
    require_worker_lease()
    port = int(config["ODOO_PORT"])
    credentials = json.loads((PRIVATE / "actor_credentials.json").read_text())
    package_rows = json.loads((PRIVATE / "task_set_manifest.json").read_text())
    package = next(row for rows in package_rows.values() for row in rows
                   if row["task_id"] == case["id"])
    result = {"case_id": case["id"], "family": family,
              "status": "candidate_environment_gate_failed",
              "official_final_task": False,
              "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "task_package_sha256": package["package_sha256"],
              "baseline_snapshot_sha256": file_hash(PRIVATE / "baseline_snapshot.json"),
              "exclusive_worker_lease_held": True,
              "worker_pid": os.getpid()}
    try:
        before_restore = restore()
        before = score(case["id"])
        result["cold_reset_before"] = (
            before_restore["business_snapshot_equal"]
            and before_restore["physical_filestore_equal_before_web_restart"])
        result["baseline_reward"] = before["reward"]
        if not result["cold_reset_before"] or before["reward"] != 0.0:
            raise RuntimeError("The candidate did not start from an exact, non-solved baseline")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                browser_login(page, port, credentials["password"], credentials["login"])
                result["source_visible_in_native_gui"] = _positive_gui(page, port, family, case)
                if not result["source_visible_in_native_gui"]:
                    raise RuntimeError("Source document or planning note not visible")
                positive = score(case["id"])
                result["gui_oracle_reward"] = positive["reward"]
                result["positive_difference_codes"] = positive["difference_codes"]
                result["protected_source_files_checked"] = positive["protected_source_files_checked"]
                if positive["reward"] != 1.0 or positive["difference_codes"]:
                    raise RuntimeError("Native GUI positive did not pass the independent oracle")
                _negative_gui(page, port, family, wrong_case)
                negative = score(case["id"])
                result["wrong_object_reward"] = negative["reward"]
                result["wrong_object_difference_codes"] = negative["difference_codes"]
                if negative["reward"] != 0.0 or NEGATIVE_CODES[family] not in negative["difference_codes"]:
                    raise RuntimeError("Wrong-object GUI mutation did not fail the oracle")
            finally:
                browser.close()
        after_restore = restore()
        after = score(case["id"])
        result["cold_reset_after"] = (
            after_restore["business_snapshot_equal"]
            and after_restore["physical_filestore_equal_before_web_restart"])
        result["after_reset_reward"] = after["reward"]
        if not result["cold_reset_after"] or after["reward"] != 0.0:
            raise RuntimeError("Final cold restore failed")
        result["status"] = "candidate_environment_gui_qualified"
    except Exception as error:
        result["failure_type"] = type(error).__name__
        result["failure_message"] = str(error)[:240]
        # Never continue with a dirty worker. A failed recovery stops the sweep.
        recovery = restore()
        result["failure_recovery_reset_exact"] = (
            recovery["business_snapshot_equal"]
            and recovery["physical_filestore_equal_before_web_restart"])
        if not result["failure_recovery_reset_exact"]:
            raise RuntimeError("Admission failed and worker recovery was not exact") from error
    result["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    return result


def run(family: str | None = None, limit: int | None = None,
        case_id: str | None = None) -> dict:
    with exclusive_worker_operation("sweep_partition"):
        return _run_unlocked(family, limit, case_id)


def _run_unlocked(family: str | None = None, limit: int | None = None,
                  case_id: str | None = None) -> dict:
    world, cases = _case_index()
    if world["split"] not in ALL_SPLIT_COUNTS:
        raise RuntimeError("Unknown candidate partition")
    if family:
        cases = [row for row in cases if row[0] == family]
    if case_id:
        cases = [row for row in cases if row[1]["id"] == case_id]
        if len(cases) != 1:
            raise ValueError("Unknown or ambiguous case ID")
    if limit is not None:
        if limit < 1:
            raise ValueError("limit must be positive")
        cases = cases[:limit]
    receipts_dir = PRIVATE / "admission_receipts"
    receipts_dir.mkdir(exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
    run_dir = PRIVATE / "admission_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    summary = {"schema": "envloop-odoo-per-case-gui-admission-v1",
               "run_id": run_id,
               "partition": world["split"],
               "status": "candidate_environment_gate_only",
               "official_final_tasks_admitted": 0,
               "attempted_this_run": 0, "qualified_this_run": 0,
               "cases": []}
    for family_name, case, wrong_case in cases:
        row = admit_one(family_name, case, wrong_case)
        receipt = receipts_dir / f"{case['id']}.json"
        receipt.write_text(json.dumps(row, indent=2) + "\n")
        receipt.chmod(0o600)
        immutable = run_dir / f"{case['id']}.json"
        immutable.write_text(json.dumps(row, indent=2) + "\n")
        immutable.chmod(0o600)
        summary["cases"].append(row)
        summary["attempted_this_run"] += 1
        summary["qualified_this_run"] += row["status"] == "candidate_environment_gui_qualified"
        (PRIVATE / "admission_sweep_current.json").write_text(json.dumps(summary, indent=2) + "\n")
        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(json.dumps({"case_id": case["id"], "family": family_name,
                          "status": row["status"],
                          "qualified_this_run": summary["qualified_this_run"],
                          "attempted_this_run": summary["attempted_this_run"]}), flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", choices=FAMILIES)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--case-id")
    arguments = parser.parse_args()
    run(arguments.family, arguments.limit, arguments.case_id)
