"""Prospective, offline-only Odoo purchase selection replacements.

This module deliberately does not connect to Odoo or inspect hidden gold.
Freeze must precede real-seed materialization. No candidate is admitted here.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import random
import secrets
from datetime import date, timedelta
from pathlib import Path

BLUEPRINTS = (
    ("dispatch_release", "DISPATCH RELEASE", "released", "Dispatch quantity", "Cleared unit rate"),
    ("quality_release", "QUALITY RELEASE", "accepted", "Accepted units", "Accepted unit rate"),
    ("allocation_ticket", "ALLOCATIONS DESK TICKET", "allocated", "Allocated units", "Allocated unit rate"),
    ("rate_exception", "RATE EXCEPTION AUTHORIZATION", "approved", "Authorized units", "Exception unit rate"),
    ("split_shipment", "SPLIT-SHIPMENT NOTICE", "consolidated", "Consolidated units", "Consolidated unit rate"),
)
VENDOR_STEMS = (
    "Arden Field Components", "Briar Industrial Supply", "Calder Materials Desk",
    "Dovetail Equipment Logistics", "Elmbridge Parts Cooperative",
)
PRODUCT_STEMS = (
    "Flow control valve", "Hardened coupling", "Pressure monitor", "Cable gland",
    "Shaft collar", "Filter cartridge", "Circuit isolator", "Pump seal",
    "Bearing housing", "Mounting bracket", "Temperature probe", "Hydraulic fitting",
    "Drive belt", "Actuator rod", "Power relay",
)
SCHEMA = "envloop-odoo-selection-reserve-v1"


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> object:
    return json.loads(path.read_text())


def write_json(path: Path, value: object, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite {path}")
    path.write_text(json.dumps(value, indent=2, sort_keys=True,
                               ensure_ascii=False) + "\n")
    if private:
        path.chmod(0o600)


def _require_private(path: Path) -> None:
    if "work" not in path.resolve().parts:
        raise ValueError("Private artifacts must be kept under an ignored work/ directory")


def _manifest_rows(manifest: dict) -> tuple[list[dict], list[dict], list[dict]]:
    if set(manifest) != {"train", "selection", "official"}:
        raise ValueError("Unexpected task-manifest splits")
    rows = tuple(manifest[name] for name in ("train", "selection", "official"))
    if tuple(map(len, rows)) != (20, 20, 100):
        raise ValueError("Original task-manifest denominator changed")
    return rows  # type: ignore[return-value]


def _retired_ids(correlation: dict, manifest: dict) -> list[str]:
    if correlation.get("source_family") != "purchase":
        raise ValueError("Retirement source family is not purchase")
    identities = correlation.get("case_identities")
    if not isinstance(identities, list) or len(identities) != 5:
        raise ValueError("Exactly five correlated identities required")
    ids = [item["task_id"] for item in identities]
    selected = {row["task_id"] for row in manifest["selection"]}
    if (len(set(ids)) != 5 or any(task_id not in selected for task_id in ids)
            or any(not task_id.startswith("ELPO-SEL-") for task_id in ids)):
        raise ValueError("Retirement identities not five unique selection cases")
    if correlation.get("all_five_live_clicked_under_v6") is not False:
        raise ValueError("Do not misstate correlated risk as five observed GUI failures")
    return ids


def freeze(*, manifest_path: Path, correlation_path: Path, train_world_path: Path,
           selection_world_path: Path, private_path: Path, public_path: Path) -> dict:
    """Commit a new outcome-independent five-slot allocation before generation."""
    _require_private(private_path)
    if private_path.exists() or public_path.exists():
        raise FileExistsError("A reserve freeze already exists")
    manifest = read_json(manifest_path)
    _manifest_rows(manifest)
    correlation = read_json(correlation_path)
    ids = _retired_ids(correlation, manifest)
    train_world = read_json(train_world_path)
    selection_world = read_json(selection_world_path)
    if train_world.get("split") != "train" or selection_world.get("split") != "selection":
        raise ValueError("Incorrect development world inputs")
    seed = secrets.token_hex(32)
    inputs = {name: digest(path.read_bytes()) for name, path in (
        ("task_manifest", manifest_path), ("retirement_audit", correlation_path),
        ("train_world", train_world_path), ("selection_world", selection_world_path))}
    rule = {
        "slots": 5,
        "allocation": "retired_purchase_ordinal_1_to_5_maps_to_blueprint_ordinal_1_to_5",
        "redraw_after_failure": False,
        "selection_denominator": 20,
        "source_documents_per_case": 1,
        "target_edits_per_case": 2,
        "wrong_object_per_case": 1,
    }
    public = {
        "schema": SCHEMA + "-pre-materialization-public-freeze",
        "as_of_date": "2026-09-29",
        "status": "prospective_frozen_before_real_seed_materialization",
        "generator_sha256": digest(Path(__file__).read_bytes()),
        "seed_sha256": digest(seed.encode()),
        "blueprint_order_sha256": digest(canonical(BLUEPRINTS)),
        "retired_id_order_sha256": digest(canonical(ids)),
        "input_sha256": inputs,
        "rule": rule,
        "hidden_gold_read": False,
        "gui_controls": 0,
        "model_attempts": 0,
        "selection_admissions": 0,
        "official_final_admissions": 0,
    }
    private = {"schema": SCHEMA + "-private-freeze", "seed": seed,
               "retired_ids_in_order": ids, "public_freeze_sha256": digest(canonical(public))}
    write_json(private_path, private, private=True)
    write_json(public_path, public)
    return public


def _rng(seed: str, slot: int) -> random.Random:
    token = hashlib.sha256(f"{seed}:reserve:{slot}".encode()).digest()
    return random.Random(int.from_bytes(token, "big"))


def build_case(seed: str, slot: int) -> dict:
    if len(seed) != 64 or any(c not in "0123456789abcdef" for c in seed):
        raise ValueError("Expected a 256-bit lowercase hexadecimal private seed")
    if slot not in range(5):
        raise ValueError("Reserve slot outside frozen cohort")
    rng = _rng(seed, slot)
    name, title, authority, quantity_label, price_label = BLUEPRINTS[slot]
    tag = digest(f"{seed}:reserve-namespace:{slot}".encode())[:10].upper()
    task_id = f"ELPO-RSV-{tag}-{slot + 1:04d}"
    vendor = f"{VENDOR_STEMS[slot]} / RSV-{tag}"
    signature = {"workflow": "purchase", "source": name,
                 "decision_rule": f"{authority}_record_sets_one_line_qty_and_rate",
                 "target": "same_line_price_and_quantity"}
    target_line = rng.randrange(3)
    lines = []
    for position in range(3):
        stem = PRODUCT_STEMS[slot * 3 + position]
        sku = f"EL-RSV-{tag}-{position + 1:03d}"
        due = (date(2026, 2, 2) + timedelta(days=rng.randint(7, 74))).isoformat()
        expected = {"qty": rng.randint(9, 42),
                    "price": round(rng.uniform(24.0, 216.0), 2), "date": due}
        initial = dict(expected)
        if position == target_line:
            initial["qty"] += rng.choice((3, 4, 6))
            initial["price"] = round(expected["price"] + rng.choice((3.75, 5.25, 8.50)), 2)
        lines.append({"sku": sku, "name": f"{stem} / lot RSV-{slot + 1:02d}-{position + 1}",
                      "expected": expected, "initial": initial})
    decoy_id = f"{task_id}-NEAR"
    decoy_lines = copy.deepcopy(lines)
    for line in decoy_lines:
        line["initial"]["qty"] += rng.choice((1, 2))
        line["initial"]["price"] = round(line["initial"]["price"] + 1.25, 2)
    return {
        "id": task_id, "family": "purchase", "partition": "selection",
        "reserve_slot": slot + 1, "template_signature": signature,
        "template_group": "odoo-causal-" + digest(canonical(signature))[:16],
        "instance_group": f"odoo-instance-RSV-{tag}-purchase-{slot + 1:04d}",
        "vendor": vendor, "order_date": "2026-02-02", "lines": lines,
        "target_line_index": target_line, "source_kind": name,
        "source_title": title, "authority_token": authority,
        "quantity_label": quantity_label, "price_label": price_label,
        "source_filename": f"{task_id}-{name}.pdf",
        "decoy": {"id": decoy_id, "vendor": vendor,
                  "lines": decoy_lines, "state": "draft"},
        "prompt": (f"In Purchase, open the attached {title.lower()} for RFQ {task_id}. "
                   "Use the authorized line's quantity and USD unit rate to correct only "
                   "the matching RFQ line. Preserve all promised dates, supplier, RFQ "
                   "state, source document, other lines and unrelated RFQs."),
    }


def source_pdf(case: dict) -> bytes:
    """Five visibly distinct one-page layouts, never the retired confirmation."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    slot = case["reserve_slot"] - 1
    target = case["lines"][case["target_line_index"]]
    expected = target["expected"]
    output = io.BytesIO()
    page = canvas.Canvas(output, pagesize=letter, invariant=1)
    page.setTitle(f"{case['source_title']} for {case['id']}")
    page.setAuthor("EnvLoop synthetic selection reserve")
    width, height = letter
    ink = colors.HexColor(("#233650", "#265054", "#513E31", "#384457", "#425236")[slot])
    pale = colors.HexColor(("#E8F0F9", "#E4F3EE", "#F6EEE2", "#E9EDF4", "#EDF2E5")[slot])
    # A separate visual grammar is used for each source type.
    if slot == 0:
        page.setFillColor(ink); page.rect(0, height - 105, width, 105, fill=1, stroke=0)
        page.setFillColor(colors.white); page.setFont("Helvetica-Bold", 20)
        page.drawString(44, height - 54, case["source_title"])
        page.setFillColor(pale); page.rect(44, height - 310, width - 88, 82, fill=1, stroke=0)
    elif slot == 1:
        page.setFillColor(pale); page.rect(0, height - 120, width, 120, fill=1, stroke=0)
        page.setStrokeColor(ink); page.setLineWidth(3); page.line(44, height - 132, width - 44, height - 132)
        page.setFillColor(ink); page.setFont("Helvetica-Bold", 20)
        page.drawString(44, height - 58, case["source_title"])
        page.roundRect(44, height - 310, width - 88, 82, 8, fill=0, stroke=1)
    elif slot == 2:
        page.setFillColor(ink); page.rect(0, 0, 24, height, fill=1, stroke=0)
        page.setFillColor(pale); page.rect(44, height - 100, width - 88, 58, fill=1, stroke=0)
        page.setFillColor(ink); page.setFont("Helvetica-Bold", 18)
        page.drawString(58, height - 78, case["source_title"])
        page.line(44, height - 320, width - 44, height - 320)
    elif slot == 3:
        page.setStrokeColor(ink); page.setLineWidth(1.6)
        page.rect(40, 40, width - 80, height - 80, fill=0, stroke=1)
        page.setFillColor(ink); page.setFont("Courier-Bold", 17)
        page.drawString(56, height - 75, case["source_title"])
        page.setFillColor(pale); page.rect(56, height - 318, width - 112, 94, fill=1, stroke=0)
    else:
        page.setFillColor(ink); page.rect(44, height - 70, 52, 25, fill=1, stroke=0)
        page.setFillColor(ink); page.setFont("Helvetica-Bold", 19)
        page.drawString(111, height - 65, case["source_title"])
        page.setStrokeColor(ink); page.line(44, height - 100, width - 44, height - 100)
        page.setFillColor(pale); page.roundRect(44, height - 308, width - 88, 82, 14, fill=1, stroke=0)
    page.setFillColor(ink)
    page.setFont("Helvetica", 9)
    page.drawString(48, height - 157, f"Authorized RFQ: {case['id']}")
    page.drawString(48, height - 176, f"Supplier account: {case['vendor']}")
    page.drawString(48, height - 195, f"Record status: {case['authority_token'].upper()}")
    page.setFont("Helvetica-Bold", 11)
    page.drawString(58, height - 247, f"Line SKU: {target['sku']}")
    page.setFont("Helvetica", 10)
    page.drawString(58, height - 268,
                    f"{case['quantity_label']}: {expected['qty']}")
    page.drawString(300, height - 268,
                    f"{case['price_label']} (USD): {expected['price']:.2f}")
    page.setFont("Helvetica", 9)
    page.drawString(48, height - 360, "Context: three-line draft RFQ; this record authorizes one matching line only.")
    page.drawString(48, height - 378, "All other line values and promised dates remain as entered.")
    page.setStrokeColor(ink); page.line(48, height - 401, width - 48, height - 401)
    page.setFont("Helvetica", 8)
    for position, line in enumerate(case["lines"], 1):
        y = height - 425 - 22 * (position - 1)
        page.drawString(52, y, f"RFQ line {position}: {line['sku']} | {line['name']}")
    page.setFillColor(colors.HexColor("#65717F")); page.setFont("Helvetica", 8)
    page.drawString(48, 52, "Synthetic operations record for benchmark evaluation; no commercial order.")
    page.save()
    return output.getvalue()


def _baseline_order(case: dict) -> dict:
    return {"vendor": case["vendor"], "state": "draft",
            "attachment_sha256": case["source_sha256"],
            "lines": [{"sku": line["sku"], **line["initial"]} for line in case["lines"]]}


def materialize(*, manifest_path: Path, correlation_path: Path,
                train_world_path: Path, selection_world_path: Path,
                private_freeze_path: Path, public_freeze_path: Path,
                cohort_dir: Path) -> dict:
    _require_private(cohort_dir)
    if cohort_dir.exists():
        raise FileExistsError("Real-seed cohort already exists; no redraw permitted")
    public = read_json(public_freeze_path)
    private = read_json(private_freeze_path)
    if public["status"] != "prospective_frozen_before_real_seed_materialization":
        raise ValueError("Pre-materialization freeze absent")
    if public["generator_sha256"] != digest(Path(__file__).read_bytes()):
        raise ValueError("Frozen generator source drift")
    if private["public_freeze_sha256"] != digest(canonical(public)):
        raise ValueError("Private/public reserve freeze mismatch")
    if public["seed_sha256"] != digest(private["seed"].encode()):
        raise ValueError("Private seed commitment mismatch")
    if public["blueprint_order_sha256"] != digest(canonical(BLUEPRINTS)):
        raise ValueError("Blueprint order drift")
    input_paths = {"task_manifest": manifest_path, "retirement_audit": correlation_path,
                   "train_world": train_world_path, "selection_world": selection_world_path}
    if {name: digest(path.read_bytes()) for name, path in input_paths.items()} != public["input_sha256"]:
        raise ValueError("Frozen input drift")
    manifest = read_json(manifest_path)
    _manifest_rows(manifest)
    if _retired_ids(read_json(correlation_path), manifest) != private["retired_ids_in_order"]:
        raise ValueError("Retired slot order drift")
    cases = [build_case(private["seed"], index) for index in range(5)]
    cohort_dir.mkdir(parents=True)
    rows = []
    baseline = {"orders": {}}
    for index, case in enumerate(cases):
        pdf = source_pdf(case)
        case["source_sha256"] = digest(pdf)
        case["package_sha256"] = digest(canonical({k: v for k, v in case.items()
                                                  if k != "package_sha256"}) + b"\n" + pdf)
        slot_dir = cohort_dir / f"slot-{index + 1:02d}"
        slot_dir.mkdir()
        (slot_dir / case["source_filename"]).write_bytes(pdf)
        write_json(slot_dir / "case.private.json", case, private=True)
        row = {"task_id": case["id"], "package_sha256": case["package_sha256"],
               "source_groups": [f"odoo-source-{case['source_sha256']}"],
               "template_group": case["template_group"],
               "instance_group": case["instance_group"]}
        rows.append(row)
        baseline["orders"][case["id"]] = _baseline_order(case)
        decoy = case["decoy"]
        baseline["orders"][decoy["id"]] = {
            "vendor": decoy["vendor"], "state": decoy["state"],
            "attachment_sha256": None,
            "lines": [{"sku": line["sku"], **line["initial"]} for line in decoy["lines"]],
        }
    old_selection = manifest["selection"]
    retired = set(private["retired_ids_in_order"])
    retained = [row for row in old_selection if row["task_id"] not in retired]
    if len(retained) != 15 or len(rows) != 5:
        raise ValueError("Prospective selection denominator is not 15 + 5")
    write_json(cohort_dir / "cases.private.json", cases, private=True)
    write_json(cohort_dir / "baseline-state.private.json", baseline, private=True)
    write_json(cohort_dir / "prospective-inventory.private.json", {
        "schema": SCHEMA + "-prospective-inventory", "status": "not_admitted",
        "retained_selection": retained, "new_selection": rows,
        "prospective_count": 20, "campaign_dispatch_authorized": False,
        "model_selection_authorized": False,
    }, private=True)
    receipt = {"schema": SCHEMA + "-private-materialization",
               "status": "offline_source_packages_generated_not_admitted",
               "public_freeze_sha256": digest(public_freeze_path.read_bytes()),
               "cohort_count": 5, "source_pdf_count": 5,
               "case_package_sha256": [case["package_sha256"] for case in cases],
               "source_pdf_sha256": [case["source_sha256"] for case in cases],
               "hidden_gold_read": False, "docker_actions": 0, "gui_actions": 0,
               "model_attempts": 0, "selection_admissions": 0}
    write_json(cohort_dir / "materialization.private.json", receipt, private=True)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("freeze", "materialize"):
        cmd = commands.add_parser(name)
        for arg in ("manifest", "correlation", "train-world", "selection-world",
                    "private-freeze", "public-freeze"):
            cmd.add_argument("--" + arg, type=Path, required=True)
        if name == "materialize":
            cmd.add_argument("--cohort-dir", type=Path, required=True)
    args = parser.parse_args()
    shared = {"manifest_path": args.manifest, "correlation_path": args.correlation,
              "train_world_path": args.train_world,
              "selection_world_path": args.selection_world,
              "private_freeze_path": args.private_freeze,
              "public_freeze_path": args.public_freeze}
    if args.command == "freeze":
        result = freeze(manifest_path=args.manifest, correlation_path=args.correlation,
                        train_world_path=args.train_world,
                        selection_world_path=args.selection_world,
                        private_path=args.private_freeze, public_path=args.public_freeze)
    else:
        result = materialize(cohort_dir=args.cohort_dir, **shared)
    print(json.dumps({"status": result["status"], "cohort_count": result.get("cohort_count", 5)},
                     sort_keys=True))


if __name__ == "__main__":
    main()
