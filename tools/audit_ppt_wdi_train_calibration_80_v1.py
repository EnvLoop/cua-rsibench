"""Reopen all 80 private PPT training analogues and publish only aggregates."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess

from ppt_wdi_factory import plan as ppt, verify
from ppt_wdi_factory.qa import _chart_workbook, _validator
from ppt_wdi_factory.build import DEFAULT_SKILL
from tools.build_ppt_wdi_train_calibration_80_v1 import (
    PLAN_SHA, QUEUE_SHA, SCHEMA, PUBLIC_SCHEMA, blind_heldout_collision,
    train_sources,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def historical_collision(directory: Path, proposed: set[str]) -> dict:
    checked = 0
    collisions = set()
    for path in sorted(directory.glob("ppt-revised-*/candidate-plan.private.json")):
        plan = json.loads(path.read_bytes())
        if plan.get("schema") != ppt.SCHEMA:
            continue
        checked += 1
        collisions |= proposed & {row["source_group"]
                                  for row in plan["sets"]["final_candidate"]}
    require(checked >= 1, "Historical source inventory unavailable")
    return {"historical_plan_revisions_checked": checked,
            "historical_final_source_collision_count": len(collisions)}


def audit(args: argparse.Namespace) -> dict:
    private = args.private_root.resolve()
    raw_manifest = (private / "manifest.private.json").read_bytes()
    raw_receipt = (private / "receipt.private.json").read_bytes()
    manifest, receipt = json.loads(raw_manifest), json.loads(raw_receipt)
    public = json.loads(args.public_receipt.read_bytes())
    require(manifest.get("schema") == SCHEMA and
            receipt.get("schema") ==
            "envloop-ppt-wdi-train-calibration-80-receipt-private-v1" and
            public.get("schema") == PUBLIC_SCHEMA and
            manifest.get("current_plan_sha256") == PLAN_SHA and
            manifest.get("future_queue_sha256") == QUEUE_SHA and
            receipt.get("manifest_sha256") == ppt.sha(raw_manifest) ==
            public.get("private_manifest_sha256") and
            ppt.sha(raw_receipt) == public.get("private_receipt_sha256") and
            receipt.get("verifier_sha256") == ppt.sha(Path(verify.__file__).read_bytes()),
            "Private/public manifest or verifier binding differs")
    rows = manifest["rows"]
    results = receipt["results"]
    require(len(rows) == len(results) == 80 and
            len({row["task_id"] for row in rows}) == 80 and
            {row["task_id"] for row in rows} ==
            {result["task_id"] for result in results} and
            all(row["split"] == "train_policy_development" and
                row["development_source_split"] == "train" and
                row["calibration_role"] ==
                "nonfinal_train_only_four_target_analogue" and
                row["official_final_credit"] == 0 and
                len(row["target_keys"]) == 4 for row in rows),
            "Nonfinal 80-task four-target inventory changed")
    workflow_counts = Counter(row["workflow"] for row in rows)
    source_groups = {row["source_group"] for row in rows}
    require(set(workflow_counts) == set(ppt.WORKFLOWS) and
            set(workflow_counts.values()) == {8} and
            len(source_groups) == 8 and
            all(len({row["source_group"] for row in rows
                     if row["workflow"] == workflow}) == 8
                for workflow in ppt.WORKFLOWS),
            "Workflow/source-family balance changed")
    train = train_sources(args.train_packages)
    require(set(train).issubset(source_groups) and len(source_groups - set(train)) == 3,
            "Original train sources or three CSV families changed")
    collision = blind_heldout_collision(args.heldout_plan, args.future_queue,
                                        source_groups)
    require(not collision["any_collision"], "Held-out/future source collision")
    historical = historical_collision(args.historical_plan_dir, source_groups)
    require(historical["historical_final_source_collision_count"] == 0,
            "Historical final source collision")
    result_by_id = {row["task_id"]: row for row in results}
    tool_dir = DEFAULT_SKILL / "container_tools"
    for number, row in enumerate(rows, 1):
        package = private / "packages/train_policy_development" / row["task_id"]
        record = result_by_id[row["task_id"]]
        spec, deck = package / "task.private.json", package / "source.pptx"
        calibration = package / "calibration.private.json"
        require(spec.read_bytes() == ppt.canonical(row) and
                ppt.sha(spec.read_bytes()) == record["spec_sha256"] and
                ppt.sha(deck.read_bytes()) == record["deck_sha256"] and
                ppt.sha(calibration.read_bytes()) == record["calibration_sha256"],
                "Package/spec/build/control hash mismatch")
        _validator(tool_dir / "inspect_presentation_package_integrity.py",
                   ["--fail-on-findings"], deck)
        _validator(tool_dir / "inspect_presentation_layout_geometry.py",
                   ["--expected-aspect", "16:9", "--expected-slide-count", "7",
                    "--require-native-table-slide", "2",
                    "--require-native-table-slide", "4",
                    "--approved-font-family", "Arial", "--validate-heading-fit",
                    "--fail-on-findings"], deck)
        require(_chart_workbook(deck) and
                verify.calibrate(package)["offline_controls_pass"],
                "Chart/workbook or independent direct-file control failed")
        if number % 20 == 0:
            print(json.dumps({"reopened_and_rechecked": number,
                              "expected": 80, "official_final_credit": 0}),
                  flush=True)
    visual = private / "visual-qa"
    pdfs = sorted((visual / "pdf").glob("workflow-*.pdf"))
    require(len(pdfs) == 10, "One visual PDF per workflow required")
    page_counts = []
    for pdf in pdfs:
        information = subprocess.check_output(["pdfinfo", str(pdf)], text=True)
        match = re.search(r"^Pages:\s+(\d+)$", information, re.M)
        page_counts.append(int(match.group(1)) if match else -1)
    require(set(page_counts) == {7}, "Each representative PDF must have seven pages")
    contact = visual / "contact-sheet.png"
    require(contact.is_file() and contact.stat().st_size > 100_000,
            "Private visual contact sheet missing")
    return {"schema": "envloop-ppt-wdi-train-calibration-80-audit-public-v1",
            "status": "reopened_offline_train_analogues_not_model_or_gui_result",
            "train_only_analogue_tasks_rechecked": 80,
            "workflow_count": 10,
            "country_source_family_count": 8,
            "direct_file_controls_rechecked": 80,
            "package_and_layout_rechecked": 80,
            "heldout_source_collision_count": 0,
            "future_reserve_collision_count": 0,
            **historical,
            "representative_pdfs": len(pdfs),
            "representative_pdf_pages": sum(page_counts),
            "private_contact_sheet_sha256": ppt.sha(contact.read_bytes()),
            "private_manifest_sha256": ppt.sha(raw_manifest),
            "private_receipt_sha256": ppt.sha(raw_receipt),
            "model_calls": 0,
            "office_web_gui_admitted": 0,
            "official_final_admitted": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", required=True, type=Path)
    parser.add_argument("--train-packages", required=True, type=Path)
    parser.add_argument("--heldout-plan", required=True, type=Path)
    parser.add_argument("--future-queue", required=True, type=Path)
    parser.add_argument("--historical-plan-dir", required=True, type=Path)
    parser.add_argument("--public-receipt", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    require(not args.out.exists(), "Refusing to overwrite a prior public audit")
    result = audit(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                        encoding="utf-8")
    print(json.dumps({"rechecked": 80, "visual_pdf_pages": 70,
                      "official_final_credit": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
