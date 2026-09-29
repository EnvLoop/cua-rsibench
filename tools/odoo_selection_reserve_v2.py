"""Three-line, difficulty-matched prospective Odoo selection reserve v2.

V1's one-line source documents are permanently unadmitted development material.
V2 uses a fresh private seed and checks disjointness against those packages.
There are no Docker, Odoo, GUI, or model operations in this module.
"""

from __future__ import annotations

import argparse
import io
import json
import secrets
from pathlib import Path

from tools import odoo_selection_reserve_v1 as base

SCHEMA = "envloop-odoo-selection-reserve-v2"


def build_case(seed: str, slot: int) -> dict:
    case = base.build_case(seed, slot)
    case["difficulty_profile"] = "three_line_source_comparison_v2"
    case["source_kind"] += "_three_line_schedule"
    case["source_title"] += " / LINE SCHEDULE"
    case["source_filename"] = f"{case['id']}-{case['source_kind']}.pdf"
    signature = dict(case["template_signature"])
    signature["source"] = case["source_kind"]
    signature["decision_rule"] = (f"compare_all_three_{case['authority_token']}_line_values"
                                   "_to_draft_rfq")
    case["template_signature"] = signature
    case["template_group"] = "odoo-causal-" + base.digest(base.canonical(signature))[:16]
    case["prompt"] = (
        f"In Purchase, open the attached {case['source_title'].lower()} for RFQ {case['id']}. "
        "Compare all three authorized source lines to the draft RFQ, then correct "
        "every mismatched quantity and USD unit rate. Preserve promised dates, "
        "supplier, RFQ state, source document and unrelated RFQs."
    )
    return case


def source_pdf(case: dict) -> bytes:
    """Show every source line; do not mark which line is faulty."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    slot = case["reserve_slot"] - 1
    palette = ("#294257", "#305A58", "#6B5038", "#3F4F68", "#475A3F")
    ink = colors.HexColor(palette[slot])
    pale = colors.HexColor(("#E8F0F9", "#E4F3EE", "#F6EEE2", "#E9EDF4", "#EDF2E5")[slot])
    output = io.BytesIO()
    page = canvas.Canvas(output, pagesize=letter, invariant=1)
    page.setTitle(f"{case['source_title']} for {case['id']}")
    page.setAuthor("EnvLoop synthetic selection reserve")
    width, height = letter
    if slot == 0:
        page.setFillColor(ink); page.rect(0, height - 98, width, 98, fill=1, stroke=0)
        page.setFillColor(colors.white)
    elif slot == 1:
        page.setFillColor(pale); page.rect(0, height - 98, width, 98, fill=1, stroke=0)
        page.setFillColor(ink)
        page.setStrokeColor(ink); page.setLineWidth(3)
        page.line(40, height - 104, width - 40, height - 104)
    elif slot == 2:
        page.setFillColor(ink); page.rect(0, 0, 19, height, fill=1, stroke=0)
        page.setFillColor(pale); page.rect(42, height - 87, width - 84, 47, fill=1, stroke=0)
        page.setFillColor(ink)
    elif slot == 3:
        page.setFillColor(ink); page.setStrokeColor(ink)
        page.rect(38, 38, width - 76, height - 76, fill=0, stroke=1)
    else:
        page.setFillColor(ink); page.rect(42, height - 78, 36, 36, fill=1, stroke=0)
        page.setStrokeColor(ink); page.line(42, height - 108, width - 42, height - 108)
    page.setFont("Helvetica-Bold" if slot != 3 else "Courier-Bold", 15)
    page.drawString(44 if slot != 4 else 90, height - 67, case["source_title"])
    page.setFillColor(ink); page.setFont("Helvetica", 9)
    page.drawString(48, height - 133, f"Authorized RFQ: {case['id']}")
    page.drawString(48, height - 151, f"Supplier account: {case['vendor']}")
    page.drawString(48, height - 169, f"Record status: {case['authority_token'].upper()}")
    page.drawString(48, height - 190,
                    "All three approved lines below govern this draft RFQ; compare each line before editing.")
    for position, line in enumerate(case["lines"], 1):
        top = height - 211 - (position - 1) * 151
        if slot in (0, 2, 4):
            page.setFillColor(pale)
            if slot == 4:
                page.roundRect(48, top - 124, width - 96, 112, 8, fill=1, stroke=0)
            else:
                page.rect(48, top - 124, width - 96, 112, fill=1, stroke=0)
        else:
            page.setStrokeColor(ink); page.setLineWidth(1)
            page.roundRect(48, top - 124, width - 96, 112, 6, fill=0, stroke=1)
        page.setFillColor(ink)
        page.setFont("Helvetica-Bold", 10)
        page.drawString(62, top - 35, f"Line {position} SKU: {line['sku']}")
        page.setFont("Helvetica", 8.5)
        page.drawString(62, top - 53, f"Item: {line['name']}")
        expected = line["expected"]
        page.setFont("Helvetica", 9)
        page.drawString(62, top - 78, f"Authorized quantity: {expected['qty']}")
        page.drawString(280, top - 78, f"Authorized unit rate (USD): {expected['price']:.2f}")
        page.drawString(62, top - 99, f"Promised date: {expected['date']}")
    page.setFillColor(colors.HexColor("#596879")); page.setFont("Helvetica", 8)
    page.drawString(48, 49, "Synthetic operations record for benchmark evaluation; no commercial order.")
    page.save()
    return output.getvalue()


def _inputs(manifest_path: Path, correlation_path: Path, train_world_path: Path,
            selection_world_path: Path, prior_v1_cohort_dir: Path) -> dict[str, Path]:
    return {"task_manifest": manifest_path, "retirement_audit": correlation_path,
            "train_world": train_world_path, "selection_world": selection_world_path,
            "prior_v1_cases": prior_v1_cohort_dir / "cases.private.json",
            "prior_v1_materialization": prior_v1_cohort_dir / "materialization.private.json"}


def freeze(*, manifest_path: Path, correlation_path: Path, train_world_path: Path,
           selection_world_path: Path, prior_v1_cohort_dir: Path,
           private_path: Path, public_path: Path) -> dict:
    base._require_private(private_path)
    if private_path.exists() or public_path.exists():
        raise FileExistsError("V2 reserve freeze already exists")
    manifest = base.read_json(manifest_path)
    base._manifest_rows(manifest)
    ids = base._retired_ids(base.read_json(correlation_path), manifest)
    prior = base.read_json(prior_v1_cohort_dir / "cases.private.json")
    if len(prior) != 5 or any(case["partition"] != "selection" for case in prior):
        raise ValueError("Expected five terminal V1 development packages")
    if base.read_json(train_world_path).get("split") != "train":
        raise ValueError("Train world not supplied")
    if base.read_json(selection_world_path).get("split") != "selection":
        raise ValueError("Selection world not supplied")
    seed = secrets.token_hex(32)
    paths = _inputs(manifest_path, correlation_path, train_world_path,
                    selection_world_path, prior_v1_cohort_dir)
    public = {
        "schema": SCHEMA + "-pre-materialization-public-freeze",
        "as_of_date": "2026-09-29",
        "status": "prospective_v2_frozen_before_real_seed_materialization",
        "generator_sha256": base.digest(Path(__file__).read_bytes()),
        "base_generator_sha256": base.digest(Path(base.__file__).read_bytes()),
        "seed_sha256": base.digest(seed.encode()),
        "blueprint_order_sha256": base.digest(base.canonical(base.BLUEPRINTS)),
        "retired_id_order_sha256": base.digest(base.canonical(ids)),
        "input_sha256": {name: base.digest(path.read_bytes()) for name, path in paths.items()},
        "rule": {
            "selection_denominator": 20, "retained_slots": 15, "new_slots": 5,
            "allocation": "retired_purchase_ordinal_1_to_5_maps_to_blueprint_ordinal_1_to_5",
            "source_rows_per_case": 3, "target_edits_per_case": 2,
            "wrong_object_per_case": 1, "redraw_after_failure": False,
            "prior_v1_identities_permanently_development_only": True,
        },
        "hidden_gold_read": False, "docker_actions": 0, "gui_actions": 0,
        "model_attempts": 0, "selection_admissions": 0,
        "official_final_admissions": 0,
    }
    private = {"schema": SCHEMA + "-private-freeze", "seed": seed,
               "retired_ids_in_order": ids,
               "public_freeze_sha256": base.digest(base.canonical(public))}
    base.write_json(private_path, private, private=True)
    base.write_json(public_path, public)
    return public


def materialize(*, manifest_path: Path, correlation_path: Path,
                train_world_path: Path, selection_world_path: Path,
                prior_v1_cohort_dir: Path, private_freeze_path: Path,
                public_freeze_path: Path, cohort_dir: Path) -> dict:
    base._require_private(cohort_dir)
    if cohort_dir.exists():
        raise FileExistsError("V2 cohort already exists; no redraw permitted")
    public = base.read_json(public_freeze_path)
    private = base.read_json(private_freeze_path)
    if public["status"] != "prospective_v2_frozen_before_real_seed_materialization":
        raise ValueError("V2 pre-materialization freeze absent")
    if public["generator_sha256"] != base.digest(Path(__file__).read_bytes()):
        raise ValueError("V2 frozen generator drift")
    if public["base_generator_sha256"] != base.digest(Path(base.__file__).read_bytes()):
        raise ValueError("Frozen base generator drift")
    if public["seed_sha256"] != base.digest(private["seed"].encode()):
        raise ValueError("V2 private seed commitment mismatch")
    if private["public_freeze_sha256"] != base.digest(base.canonical(public)):
        raise ValueError("V2 private/public freeze mismatch")
    if public["blueprint_order_sha256"] != base.digest(base.canonical(base.BLUEPRINTS)):
        raise ValueError("V2 blueprint order drift")
    paths = _inputs(manifest_path, correlation_path, train_world_path,
                    selection_world_path, prior_v1_cohort_dir)
    if {name: base.digest(path.read_bytes()) for name, path in paths.items()} != public["input_sha256"]:
        raise ValueError("V2 frozen input drift")
    manifest = base.read_json(manifest_path)
    base._manifest_rows(manifest)
    if base._retired_ids(base.read_json(correlation_path), manifest) != private["retired_ids_in_order"]:
        raise ValueError("V2 retired slot order drift")
    prior = base.read_json(prior_v1_cohort_dir / "cases.private.json")
    cases = [build_case(private["seed"], slot) for slot in range(5)]
    cohort_dir.mkdir(parents=True)
    rows = []
    baseline = {"orders": {}}
    for slot, case in enumerate(cases, 1):
        pdf = source_pdf(case)
        case["source_sha256"] = base.digest(pdf)
        case["package_sha256"] = base.digest(base.canonical({key: value for key, value in case.items()
                                                             if key != "package_sha256"}) + b"\n" + pdf)
        target = cohort_dir / f"slot-{slot:02d}"
        target.mkdir()
        (target / case["source_filename"]).write_bytes(pdf)
        base.write_json(target / "case.private.json", case, private=True)
        rows.append({"task_id": case["id"], "package_sha256": case["package_sha256"],
                     "source_groups": [f"odoo-source-{case['source_sha256']}"],
                     "template_group": case["template_group"],
                     "instance_group": case["instance_group"]})
        baseline["orders"][case["id"]] = base._baseline_order(case)
        decoy = case["decoy"]
        baseline["orders"][decoy["id"]] = {
            "vendor": decoy["vendor"], "state": decoy["state"],
            "attachment_sha256": None,
            "lines": [{"sku": line["sku"], **line["initial"]} for line in decoy["lines"]],
        }
    for field in ("id", "vendor", "source_sha256", "package_sha256",
                  "template_group", "instance_group"):
        if set(case[field] for case in cases).intersection(case[field] for case in prior):
            raise ValueError(f"V2 overlaps retired V1 development {field}")
    old_skus = {line["sku"] for case in prior for line in case["lines"]}
    if old_skus.intersection(line["sku"] for case in cases for line in case["lines"]):
        raise ValueError("V2 overlaps V1 development SKUs")
    retired = set(private["retired_ids_in_order"])
    retained = [row for row in manifest["selection"] if row["task_id"] not in retired]
    if len(retained) != 15:
        raise ValueError("V2 prospective selection denominator changed")
    base.write_json(cohort_dir / "cases.private.json", cases, private=True)
    base.write_json(cohort_dir / "baseline-state.private.json", baseline, private=True)
    base.write_json(cohort_dir / "prospective-inventory.private.json", {
        "schema": SCHEMA + "-prospective-inventory", "status": "not_admitted",
        "retained_selection": retained, "new_selection": rows,
        "prospective_count": 20, "campaign_dispatch_authorized": False,
        "model_selection_authorized": False,
    }, private=True)
    result = {
        "schema": SCHEMA + "-private-materialization",
        "status": "offline_three_line_source_packages_generated_not_admitted",
        "public_freeze_sha256": base.digest(public_freeze_path.read_bytes()),
        "cohort_count": 5, "source_pdf_count": 5,
        "case_package_sha256": [case["package_sha256"] for case in cases],
        "source_pdf_sha256": [case["source_sha256"] for case in cases],
        "prior_v1_development_overlap": 0,
        "hidden_gold_read": False, "docker_actions": 0, "gui_actions": 0,
        "model_attempts": 0, "selection_admissions": 0,
    }
    base.write_json(cohort_dir / "materialization.private.json", result, private=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("freeze", "materialize"):
        command = commands.add_parser(name)
        for field in ("manifest", "correlation", "train-world", "selection-world",
                      "prior-v1-cohort-dir", "private-freeze", "public-freeze"):
            command.add_argument("--" + field, type=Path, required=True)
        if name == "materialize":
            command.add_argument("--cohort-dir", type=Path, required=True)
    args = parser.parse_args()
    shared = {"manifest_path": args.manifest, "correlation_path": args.correlation,
              "train_world_path": args.train_world,
              "selection_world_path": args.selection_world,
              "prior_v1_cohort_dir": args.prior_v1_cohort_dir}
    if args.command == "freeze":
        result = freeze(private_path=args.private_freeze,
                        public_path=args.public_freeze, **shared)
    else:
        result = materialize(private_freeze_path=args.private_freeze,
                             public_freeze_path=args.public_freeze,
                             cohort_dir=args.cohort_dir, **shared)
    print(json.dumps({"status": result["status"], "cohort_count": result.get("cohort_count", 5)},
                     sort_keys=True))


if __name__ == "__main__":
    main()
