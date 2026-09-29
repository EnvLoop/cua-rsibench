"""Independent offline audit for difficulty-matched Odoo reserve v2.

Reopens private packages and PDFs without importing the V2 generator or
touching hidden-final gold. No saved Odoo state is represented here.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools import audit_odoo_selection_reserve_v1 as shared


def digest_file(path: Path) -> str:
    return shared.digest(path.read_bytes())


def audit(*, manifest_path: Path, correlation_path: Path,
          train_world_path: Path, selection_world_path: Path,
          generator_path: Path, base_generator_path: Path,
          prior_v1_cohort_dir: Path, private_freeze_path: Path,
          public_freeze_path: Path, cohort_dir: Path) -> dict:
    public = shared.load(public_freeze_path)
    if public["schema"] != "envloop-odoo-selection-reserve-v2-pre-materialization-public-freeze":
        raise ValueError("Expected prospective V2 freeze")
    if public["base_generator_sha256"] != digest_file(base_generator_path):
        raise ValueError("V2 base generator changed after freeze")
    prior_paths = {"prior_v1_cases": prior_v1_cohort_dir / "cases.private.json",
                   "prior_v1_materialization": prior_v1_cohort_dir / "materialization.private.json"}
    if any(public["input_sha256"].get(name) != digest_file(path)
           for name, path in prior_paths.items()):
        raise ValueError("Retired V1 development source drift")
    report = shared.audit(manifest_path=manifest_path,
                          correlation_path=correlation_path,
                          train_world_path=train_world_path,
                          selection_world_path=selection_world_path,
                          generator_path=generator_path,
                          private_freeze_path=private_freeze_path,
                          public_freeze_path=public_freeze_path,
                          cohort_dir=cohort_dir)
    old = shared.load(prior_v1_cohort_dir / "cases.private.json")
    new = shared.load(cohort_dir / "cases.private.json")
    if len(old) != 5 or len(new) != 5:
        raise ValueError("V1/V2 cohort sizes are not five")
    for field in ("id", "vendor", "source_sha256", "package_sha256",
                  "template_group", "instance_group"):
        if {case[field] for case in old}.intersection(case[field] for case in new):
            raise ValueError(f"V2 reuses retired V1 {field}")
    old_skus = {line["sku"] for case in old for line in case["lines"]}
    new_skus = {line["sku"] for case in new for line in case["lines"]}
    if old_skus.intersection(new_skus):
        raise ValueError("V2 reuses V1 development SKU")
    for case in new:
        if case.get("difficulty_profile") != "three_line_source_comparison_v2":
            raise ValueError("V2 source-reading difficulty tag absent")
        if "Compare all three authorized source lines" not in case["prompt"]:
            raise ValueError("V2 actor prompt does not require three-line comparison")
        if case["lines"][case["target_line_index"]]["sku"] in case["prompt"]:
            raise ValueError("V2 actor prompt discloses the faulty line")
    report.update({
        "schema": "envloop-odoo-selection-reserve-v2-independent-offline-audit",
        "status": "five_prospective_three_line_offline_packages_checked_not_gui_admitted",
        "source_rows_checked_per_case": 3,
        "private_source_scalar_fields_checked": 5 * 3 * 3,
        "prior_v1_development_identity_source_template_entity_overlap": 0,
        "v1_structurally_retired_before_any_gui_or_model_attempt": True,
        "shared_native_attachment_route_still_unqualified": True,
    })
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("manifest", "correlation", "train-world", "selection-world",
                  "generator", "base-generator", "prior-v1-cohort-dir",
                  "private-freeze", "public-freeze", "cohort-dir", "public-out"):
        parser.add_argument("--" + field, type=Path, required=True)
    args = parser.parse_args()
    report = audit(manifest_path=args.manifest,
                   correlation_path=args.correlation,
                   train_world_path=args.train_world,
                   selection_world_path=args.selection_world,
                   generator_path=args.generator,
                   base_generator_path=args.base_generator,
                   prior_v1_cohort_dir=args.prior_v1_cohort_dir,
                   private_freeze_path=args.private_freeze,
                   public_freeze_path=args.public_freeze,
                   cohort_dir=args.cohort_dir)
    if args.public_out.exists():
        raise FileExistsError("V2 independent audit already exists")
    args.public_out.parent.mkdir(parents=True, exist_ok=True)
    args.public_out.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "cohort_count": report["cohort_count"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
