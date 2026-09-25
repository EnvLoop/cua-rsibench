"""GUI-solvability sweep for unsealed Sales and CRM development cases.

Each case gets its own cold database/filestore restore. This is a known-answer
environment check, not model evaluation and not hidden-task admission.
"""

from __future__ import annotations

import argparse
import json

from factory import PRIVATE, local_config
from gui_controls import (
    browser_login, crm_case, open_crm, open_sales, sales_case, view_attachment,
)
from multifamily import crm_candidates, sales_candidates
from reset import restore
from verify import score


def sweep(family: str, limit: int | None = None) -> dict:
    from playwright.sync_api import sync_playwright

    config = local_config()
    port = int(config["ODOO_PORT"])
    cases = []
    if family in ("sales", "all"):
        cases += [("sales", item) for item in sales_candidates()]
    if family in ("crm", "all"):
        cases += [("crm", item) for item in crm_candidates()]
    if limit is not None:
        cases = cases[:limit]
    receipt = {"status": "unsealed_development_gui_solvability_only",
               "official_final_tasks_admitted": 0, "cases": []}
    for family_name, case in cases:
        restored = restore()
        before = score(case["id"])
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            browser_login(page, port, config["ODOO_ADMIN_PASSWORD"])
            if family_name == "sales":
                open_sales(page, port, case["id"])
                visible = view_attachment(page, f"{case['id']}-customer-po.pdf")
                sales_case(page, case, positive=True)
            else:
                open_crm(page, port, case["id"])
                visible = view_attachment(page, f"{case['id']}-handoff.pdf")
                crm_case(page, case, positive=True)
            browser.close()
        after = score(case["id"])
        row = {"case_id": case["id"], "family": family_name,
               "source_pdf_visible_in_native_viewer": visible,
               "baseline_reward": before["reward"],
               "gui_oracle_reward": after["reward"],
               "difference_codes": after["difference_codes"],
               "protected_source_files_checked": after["protected_source_files_checked"],
               "cold_reset_before": restored["business_snapshot_equal"]
               and restored["physical_filestore_equal_before_web_restart"]}
        receipt["cases"].append(row)
        (PRIVATE / "development_gui_sweep_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps(row), flush=True)
    final_restore = restore()
    receipt["final_reset_exact"] = final_restore["business_snapshot_equal"] \
        and final_restore["physical_filestore_equal_before_web_restart"]
    receipt["passed"] = sum(row["cold_reset_before"]
                            and row["source_pdf_visible_in_native_viewer"]
                            and row["baseline_reward"] == 0.0
                            and row["gui_oracle_reward"] == 1.0
                            for row in receipt["cases"])
    receipt["attempted"] = len(receipt["cases"])
    (PRIVATE / "development_gui_sweep_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    if receipt["passed"] != receipt["attempted"] or not receipt["final_reset_exact"]:
        raise RuntimeError(f"Development sweep incomplete: {receipt['passed']}/{receipt['attempted']}")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", choices=["sales", "crm", "all"], default="all")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    sweep(args.family, args.limit)
