"""Independently reopen all 80 train-only PPTX transfer controls.

This auditor reads evaluator-private packages and publishes aggregates only.
It does not grant Office-web GUI admission or a model result.
"""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess

from ppt_wdi_factory import plan as ppt, verify
from ppt_wdi_factory.build import DEFAULT_SKILL
from ppt_wdi_factory.qa import _chart_workbook, _validator
from tools import office_transfer_source_gate_v1 as gate


SCHEMA = "envloop-ppt-transfer-expansion80-independent-audit-v1"
PILOT_MANIFEST_SHA = "34a584f51ee2254d726c3a37e106e18efeaf3a41b515a72766b57407876a6499"


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def private_bytes(path: Path) -> bytes:
    require(path.is_file() and not path.is_symlink() and
            path.stat().st_mode & 0o077 == 0,
            "private_transfer_evidence_missing_or_unsafe")
    return path.read_bytes()


def audit(*, private_root: Path, source_root: Path,
          calibration_boundary: Path, original_v13_plan: Path,
          future_queue: Path, historical_plan_dir: Path,
          pilot_private_root: Path, public_receipt: Path) -> dict:
    root = Path(private_root).resolve()
    require(root.is_dir() and not root.is_symlink() and
            root.stat().st_mode & 0o077 == 0 and
            root.is_relative_to((Path.cwd() / "work").resolve()),
            "private_transfer_root_unsafe")
    manifest_raw = private_bytes(root / "manifest.private.json")
    receipt_raw = private_bytes(root / "offline-controls.private.json")
    seed = private_bytes(root / "seed.private")
    require(len(seed) == 32, "transfer_seed_invalid")
    pilot_manifest_raw = private_bytes(pilot_private_root / "manifest.private.json")
    pilot_seed = private_bytes(pilot_private_root / "seed.private")
    pilot_plan = json.loads(pilot_manifest_raw)
    require(digest(pilot_manifest_raw) == PILOT_MANIFEST_SHA and
            pilot_seed == seed and
            pilot_plan.get("stage") == "pilot" and
            len(pilot_plan.get("rows", [])) == 20,
            "frozen_transfer_pilot_missing_or_changed")
    plan = json.loads(manifest_raw)
    receipt = json.loads(receipt_raw)
    public = json.loads(public_receipt.read_bytes())
    rebuilt = gate.ppt_transfer_plan(
        seed, source_root, original_v13_plan, original_v13_plan,
        future_queue, calibration_boundary, historical_plan_dir,
        stage="expansion", pilot_plan=pilot_plan)
    require(manifest_raw == ppt.canonical(rebuilt) and plan == rebuilt,
            "transfer_plan_not_exact_source_rebuild")
    expected_public = gate.ppt_public_receipt(plan)
    expected_public.update({
        "status": "train_only_offline_controls_passed_not_gui_admitted",
        "offline_control_passed": 80,
        "private_offline_receipt_sha256": digest(receipt_raw),
    })
    require(public == expected_public and
            public.get("office_web_gui_admitted") == 0 and
            public.get("official_final_admitted") == 0 and
            public.get("model_calls") == 0,
            "transfer_public_receipt_not_exact_or_overclaims")
    require(receipt.get("schema") ==
            "envloop-ppt-transfer-offline-controls-private-v1" and
            receipt.get("plan_sha256") == digest(manifest_raw) and
            receipt.get("builder_sha256") == digest(Path(
                "ppt_wdi_factory/build_train_transfer_deck.mjs").read_bytes()) and
            receipt.get("verifier_sha256") == digest(Path(
                verify.__file__).read_bytes()) and
            receipt.get("offline_controls_passed") == 80 and
            receipt.get("office_web_gui_admitted") == 0,
            "transfer_private_receipt_changed")
    rows, results = plan["rows"], receipt.get("results")
    require(len(rows) == len(results) == 80 and
            len({row["task_id"] for row in rows}) == 80 and
            {row["task_id"] for row in rows} ==
            {result["task_id"] for result in results},
            "transfer_expansion_80_id_inventory_changed")
    workflows = Counter(row["workflow"] for row in rows)
    sources = {row["source_group"] for row in rows}
    require(len(workflows) == 10 and set(workflows.values()) == {8} and
            len(sources) == 8 and
            all(len({row["source_group"] for row in rows
                     if row["workflow"] == workflow}) == 8
                for workflow in ppt.WORKFLOWS) and
            all(row["split"] == "train_policy_development" and
                row["development_source_split"] == "train" and
                row["official_final_credit"] == 0 and
                len(row["target_keys"]) == 4
                for row in rows),
            "transfer_workflow_depth_or_source_balance_changed")
    by_id = {result["task_id"]: result for result in results}
    tool_dir = DEFAULT_SKILL / "container_tools"
    for row in rows:
        package = root / "packages/train_policy_development" / row["task_id"]
        require(package.is_dir() and not package.is_symlink() and
                package.resolve().is_relative_to(root),
                "transfer_package_directory_unsafe")
        record = by_id[row["task_id"]]
        spec = private_bytes(package / "task.private.json")
        deck_path = package / "source.pptx"
        calibration = private_bytes(package / "calibration.private.json")
        require(spec == ppt.canonical(row) and
                digest(spec) == record["spec_sha256"] and
                deck_path.is_file() and not deck_path.is_symlink() and
                digest(deck_path.read_bytes()) == record["deck_sha256"] and
                digest(calibration) == record["calibration_sha256"] and
                record["workflow"] == row["workflow"] and
                record["source_group"] == row["source_group"],
                "transfer_package_or_control_hash_changed")
        source_dir = source_root / row["source_group"]
        zip_raw = private_bytes(source_root /
                                f"{row['source_group']}-country.private.zip")
        for filename in ("source-snapshot.private.json",
                         "source-provenance.private.json"):
            require(private_bytes(package / filename) ==
                    private_bytes(source_dir / filename),
                    "transfer_package_source_bytes_changed")
        require(private_bytes(package / "source-country.private.zip") ==
                zip_raw and record["source_bytes"] == deck_path.stat().st_size,
                "transfer_package_official_zip_changed")
        saved_calibration = json.loads(calibration)
        variants = ["positive", "near-miss", "collateral", "wrong-chart"]
        if "legend_desync" in saved_calibration.get("checks", {}):
            variants.append("legend-desync")
        saved_paths = [package / "oracle.private.json"] + [
            package / "controls" / f"{name}.pptx" for name in variants]
        before = {path: digest(private_bytes(path)) for path in saved_paths}
        _validator(tool_dir / "inspect_presentation_package_integrity.py",
                   ["--fail-on-findings"], deck_path)
        _validator(tool_dir / "inspect_presentation_layout_geometry.py",
                   ["--expected-aspect", "16:9",
                    "--expected-slide-count", "7",
                    "--require-native-table-slide", "2",
                    "--require-native-table-slide", "4",
                    "--approved-font-family", "Arial",
                    "--validate-heading-fit", "--fail-on-findings"],
                   deck_path)
        require(_chart_workbook(deck_path) and
                verify.calibrate(package)["offline_controls_pass"] and
                all(digest(private_bytes(path)) == saved_sha
                    for path, saved_sha in before.items()),
                "transfer_saved_artifact_or_near_miss_control_failed")
    visual = root / "visual-qa"
    sample = json.loads(private_bytes(visual / "representatives.private.json"))
    reviewed_raw = private_bytes(visual / "visual-review.private.json")
    reviewed = json.loads(reviewed_raw)
    require(sample.get("schema") ==
            "envloop-ppt-transfer-expansion80-visual-sample-private-v1" and
            len(sample.get("rows", [])) == 10 and
            [item["workflow_index"] for item in sample["rows"]] == list(range(10)) and
            [item["workflow"] for item in sample["rows"]] == list(ppt.WORKFLOWS) and
            reviewed.get("schema") ==
            "envloop-ppt-transfer-expansion80-visual-review-private-20260929-v1" and
            reviewed.get("sample_rule") == "one_new_source_case_per_workflow" and
            reviewed.get("reviewed_contact_sheets") == 2 and
            reviewed.get("reviewed_full_resolution_pages") == 3 and
            reviewed.get("layout_findings") == [] and
            reviewed.get("powerpoint_web_rendering_checked") is False and
            reviewed.get("office_web_gui_admitted") == 0,
            "representative_visual_review_record_missing_or_overclaimed")
    bound_decks = {(result["workflow"], result["spec_sha256"],
                    result["deck_sha256"]) for result in results}
    expected_pdfs = []
    for index, item in enumerate(sample["rows"]):
        require((item["workflow"], item["spec_sha256"], item["deck_sha256"])
                in bound_decks and
                digest(private_bytes(visual / "decks" /
                    f"workflow-{index:02d}.pptx")) == item["deck_sha256"],
                "visual_representative_not_bound_to_frozen_deck")
        pdf = visual / "pdf" / f"workflow-{index:02d}.pdf"
        information = subprocess.check_output(["pdfinfo", str(pdf)], text=True)
        match = re.search(r"^Pages:\s+(\d+)$", information, re.M)
        require(match is not None and int(match.group(1)) == 7,
                "visual_representative_pdf_not_seven_pages")
        expected_pdfs.append({"filename": pdf.name,
                              "sha256": digest(private_bytes(pdf)),
                              "pages": 7})
    require(reviewed.get("representative_pdfs") == expected_pdfs and
            len(list((visual / "pdf").glob("workflow-*.pdf"))) == 10 and
            reviewed.get("contact_sheet_sha256") == [
                digest(private_bytes(visual / f"contact-{index}.png"))
                for index in (1, 2)] and
            reviewed.get("full_resolution_page_sha256") == [
                digest(private_bytes(visual / name)) for name in (
                    "workflow-08-detail-4.png", "workflow-08-detail-5.png",
                    "workflow-09-detail-7.png")],
            "visual_pdf_or_review_image_changed")
    return {
        "schema": SCHEMA,
        "status": "80_train_only_direct_file_controls_reopened_not_gui_admitted",
        "private_manifest_sha256": digest(manifest_raw),
        "frozen_pilot_manifest_sha256": digest(pilot_manifest_raw),
        "private_offline_receipt_sha256": digest(receipt_raw),
        "independent_auditor_source_sha256": digest(Path(__file__).read_bytes()),
        "train_only_task_packages_reopened": 80,
        "four_target_workflows_reopened": 10,
        "source_families_reopened": 8,
        "saved_artifact_and_near_miss_controls_passed": 80,
        "package_layout_and_native_chart_controls_passed": 80,
        "representative_pdfs_reviewed": 10,
        "representative_pdf_pages": 70,
        "visual_review_private_sha256": digest(reviewed_raw),
        "visual_pdf_review_completed": True,
        "powerpoint_web_rendering_checked": False,
        "office_web_gui_admitted": 0,
        "model_calls": 0,
        "official_final_admitted": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--calibration-boundary", type=Path, required=True)
    parser.add_argument("--original-v13-plan", type=Path, required=True)
    parser.add_argument("--future-queue", type=Path, required=True)
    parser.add_argument("--historical-plan-dir", type=Path, required=True)
    parser.add_argument("--public-receipt", type=Path, required=True)
    parser.add_argument("--pilot-private-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    require(not args.out.exists() and not args.out.is_symlink(),
            "fresh_field_limited_audit_output_required")
    result = audit(private_root=args.private_root,
                   source_root=args.source_root,
                   calibration_boundary=args.calibration_boundary,
                   original_v13_plan=args.original_v13_plan,
                   future_queue=args.future_queue,
                   historical_plan_dir=args.historical_plan_dir,
                   pilot_private_root=args.pilot_private_root,
                   public_receipt=args.public_receipt)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(result, sort_keys=True, indent=2) + "\n").encode()
    descriptor = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps({"status": result["status"],
                      "offline_rechecked": 80,
                      "office_web_gui_admitted": 0,
                      "official_final_admitted": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
