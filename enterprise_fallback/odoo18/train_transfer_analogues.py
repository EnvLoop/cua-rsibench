"""Stage eight original-software Odoo TRAIN challenges without touching 20/20/100.

The private output contains task instructions and gold.  This source-only lane
does not seed Odoo, operate its GUI, or qualify a training episode.
"""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import date, timedelta
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import secrets
import stat

from multifamily import source_pdf
from partition_factory import FAMILIES, candidate_world, source_asset


SCHEMA = "envloop-odoo-train-transfer-analogues-v1"
PUBLIC_SCHEMA = "envloop-odoo-train-transfer-analogues-public-v1"
SOURCE_LAYOUT = "flat-training-control-sheet-v1"
RULES = {
    "purchase": "revision_precedence_and_cross_line_vendor_reference",
    "inventory": "mean_range_lead_time_service_factor",
    "sales": "customer_deadline_and_multiline_reconciliation",
    "crm": "verified_contact_precedence_and_full_handoff",
}
PREFIXES = {"purchase": "ELPO", "inventory": "ELRP", "sales": "ELSQ", "crm": "ELCRM"}


def _raw(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _hash(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def _case(source: dict, world: dict, family: str, index: int) -> dict:
    case = deepcopy(source)
    tag = world["namespace"]
    case["id"] = f"{PREFIXES[family]}-TRX-{tag}-{index + 1:04d}"
    case["partition"] = "train"
    case["challenge_pool"] = "supplemental_train_transfer_v1"
    case["template_signature"] = {
        "role": "train_transfer", "workflow": family, "causal_skill": RULES[family],
        "source_layout": SOURCE_LAYOUT,
    }
    case["template_group"] = "odoo-train-transfer-" + family + "-v1"
    case["instance_group"] = f"odoo-train-transfer-{tag}-{family}-{index + 1:04d}"
    if family == "purchase":
        case["vendor_reference"] = f"ACK-TRX-{tag}-{index + 1:04d}"
        case["initial_vendor_reference"] = "DRAFT-" + case["vendor_reference"]
        for position, line in enumerate(case["lines"]):
            line["initial"] = dict(line["expected"])
            if position in (0, 2):
                line["initial"]["price"] = round(line["expected"]["price"] + 4.25, 2)
            if position in (1, 2):
                line["initial"]["qty"] = line["expected"]["qty"] + 3
        case["prompt"] = (f"In Purchase, inspect the attached supplier control sheet for RFQ {case['id']}. "
                          "The approved B column replaces the cancelled A column. Update all mismatched "
                          "quantities and prices and the approved vendor reference. Keep dates, supplier, "
                          "draft state, attachment and other records unchanged.")
    elif family == "inventory":
        params = case["formula_inputs"]
        factor = (1.25, 1.50)[index]
        weeks = params["weeks"]
        lead_weeks = params["lead_days"] / 7
        minimum = math.ceil(sum(weeks) / 4 * lead_weeks
                            + factor * (max(weeks) - min(weeks)) * math.sqrt(lead_weeks))
        minimum += params["safety_stock"]
        case["expected"] = {"minimum": minimum, "maximum": minimum + 3 * params["case_pack"]}
        case["initial"] = {"minimum": minimum + 4, "maximum": minimum + 2 * params["case_pack"]}
        params["service_factor"] = factor
        params["seasonal_uplift_pct"] = 0
        case["source_note"] = (
            f"Synthetic approved stock-control sheet for {case['sku']}. Weekly units, oldest to newest: "
            + ", ".join(map(str, weeks)) + ". "
            f"Lead time {params['lead_days']} days; service factor {factor:.2f}; "
            f"safety stock {params['safety_stock']}; case pack {params['case_pack']}. "
            "Set minimum to ceil(mean weekly units x lead weeks + service factor x "
            "(largest weekly count - smallest weekly count) x sqrt(lead weeks)) "
            "+ safety stock. Set maximum to minimum + three case packs. "
            "The older seasonal shortcut is cancelled."
        )
        case["prompt"] = (f"In Inventory, use the approved stock-control sheet for {case['sku']} "
                          "to calculate and save both WH/Stock limits. Preserve the sheet, "
                          "other replenishment rules and all other records.")
    elif family == "sales":
        case["initial_customer_reference"] = "DRAFT-" + case["customer_reference"]
        expiry = date(2027, 3, 4) + timedelta(days=3 * index)
        case["expiration_date"] = expiry.isoformat()
        case["initial_expiration_date"] = (expiry + timedelta(days=10)).isoformat()
        for position, line in enumerate(case["lines"]):
            line["initial"] = dict(line["expected"])
            if position in (0, 2):
                line["initial"]["qty"] += 2
            if position in (1, 2):
                line["initial"]["price"] = round(line["expected"]["price"] + 5.25, 2)
        case["prompt"] = (f"In Sales, use the attached customer control sheet for quote {case['id']}. "
                          "The customer's dated acceptance controls quote expiry. Correct the reference, "
                          "all mismatched quantities and prices, and expiration. Preserve discounts, "
                          "customer, draft state, source and unrelated records.")
    else:
        expected = case["expected"]
        expected["email_from"] = f"verified-{tag.lower()}-{index + 1:03d}@example.invalid"
        expected["phone"] = f"+1 555 020{index + 1}"
        case["initial"] = {
            "stage_name": "New", "salesperson_index": (expected["salesperson_index"] + 1) % 3,
            "revenue": expected["revenue"] + 2500,
            "deadline": (date.fromisoformat(expected["deadline"]) + timedelta(days=10)).isoformat(),
            "priority": "0", "email_from": f"intake-{tag.lower()}-{index + 1:03d}@example.invalid",
            "phone": f"+1 555 090{index + 1}",
        }
        case["prompt"] = (f"In CRM, use the attached verified handoff sheet for {case['id']}. "
                          "The verified contact row supersedes intake. Reconcile stage, owner, forecast, "
                          "closing date, priority, email and phone. Preserve customer, notes, "
                          "attachment and unrelated opportunities.")
    return case


def source_bytes(case: dict, world: dict) -> bytes:
    family = case["family"]
    if family == "inventory":
        return case["source_note"].encode()
    if family == "purchase":
        rows = [("Approval status", "Column A cancelled; column B approved"),
                ("Vendor reference B", case["vendor_reference"])]
        for i, line in enumerate(case["lines"], 1):
            old, new = line["initial"], line["expected"]
            rows += [(f"Line {i} A / cancelled", f"qty {old['qty']} / USD {old['price']:.2f}"),
                     (f"Line {i} B / approved", f"qty {new['qty']} / USD {new['price']:.2f}")]
        return source_pdf("SUPPLIER CONTROL SHEET", case["id"], case["vendor"], rows)
    if family == "sales":
        rows = [("Accepted PO reference", case["customer_reference"]),
                ("Customer deadline", case["expiration_date"]),
                ("Validity rule", "Customer deadline replaces seller draft")]
        for i, line in enumerate(case["lines"], 1):
            x = line["expected"]
            rows.append((f"Accepted line {i}",
                         f"qty {x['qty']} / USD {x['price']:.2f} / discount {x['discount']}%"))
        return source_pdf("CUSTOMER CONTROL SHEET", case["id"], case["customer"], rows)
    x = case["expected"]
    rows = [("Verified supersedes", "Initial intake contact"),
            ("Approved stage", x["stage_name"]),
            ("Approved owner", world["salespeople"][x["salesperson_index"]]),
            ("Forecast", f"USD {x['revenue']:,.2f}"),
            ("Closing date", x["deadline"]),
            ("Priority", x["priority"]),
            ("Verified email", x["email_from"]), ("Verified phone", x["phone"])]
    return source_pdf("VERIFIED HANDOFF SHEET", case["id"], case["customer"], rows)


def _identities(world: dict) -> dict[str, set[str]]:
    cases = [c for family in FAMILIES for c in world["cases"][family]]
    return {
        "task": {c["id"] for c in cases},
        "source": {_hash(source_asset(c, world) if c.get("challenge_pool") is None
                         else source_bytes(c, world)) for c in cases},
        "partner": set(world["vendors"] + world["customers"]),
        "product": {p["sku"] for p in world["products"]},
        "principal": set(world["salespeople"]),
        "template": {c["template_group"] for c in cases},
        "instance": {c["instance_group"] for c in cases},
    }


def build(seed: str, original: dict[str, dict]) -> dict:
    _require(len(seed) >= 32 and set(original) == {"train", "selection", "official_hidden"},
             "private seed and three original worlds are required")
    for split, world in original.items():
        _require(world.get("split") == split and all(len(world["cases"][f]) ==
                 (25 if split == "official_hidden" else 5) for f in FAMILIES),
                 "original 20/20/100 world shape changed")
    world = candidate_world(seed, "train")
    world["cases"] = {family: [_case(c, world, family, i)
                               for i, c in enumerate(world["cases"][family][:2])]
                      for family in FAMILIES}
    world["split"] = "train_transfer"
    new = _identities(world)
    overlaps = {split: {kind: len(values & _identities(old)[kind])
                        for kind, values in new.items()} for split, old in original.items()}
    _require(all(count == 0 for row in overlaps.values() for count in row.values()),
             "train transfer source/entity/template overlaps an original split")
    cases = [c for family in FAMILIES for c in world["cases"][family]]
    _require(len(cases) == 8 and len(new["source"]) == 8 and
             len(new["task"]) == 8, "two distinct source tasks per workflow required")
    return {
        "schema": SCHEMA, "status": "offline_train_only_no_gui_or_model_result",
        "seed": seed, "source_layout": SOURCE_LAYOUT,
        "original_world_sha256": {split: _hash(_raw(old)) for split, old in original.items()},
        "world": world,
        "source_assets_hex": {c["id"]: source_bytes(c, world).hex() for c in cases},
        "cross_split_overlap_counts": overlaps,
        "official_final_admitted": 0, "model_results": 0,
    }


def audit(staged: dict, original: dict[str, dict]) -> dict:
    _require(staged.get("schema") == SCHEMA and
             staged.get("status") == "offline_train_only_no_gui_or_model_result" and
             staged.get("official_final_admitted") == staged.get("model_results") == 0,
             "invalid staged status")
    replay = build(staged["seed"], original)
    _require(replay == staged, "staged source, gold, or original binding drifted")
    world = staged["world"]
    cases = [c for family in FAMILIES for c in world["cases"][family]]
    for case in cases:
        _require(bytes.fromhex(staged["source_assets_hex"][case["id"]]) ==
                 source_bytes(case, world), "source asset bytes changed")
        if case["family"] == "inventory":
            p = case["formula_inputs"]
            lead = p["lead_days"] / 7
            expected_min = math.ceil(sum(p["weeks"]) / 4 * lead + p["service_factor"] *
                                     (max(p["weeks"]) - min(p["weeks"])) * math.sqrt(lead))
            expected_min += p["safety_stock"]
            _require(case["expected"] == {"minimum": expected_min,
                       "maximum": expected_min + 3 * p["case_pack"]},
                     "stock-control gold formula changed")
        elif case["family"] in ("purchase", "sales"):
            _require(sum(line["initial"] != line["expected"] for line in case["lines"]) == 3,
                     "all three commercial lines must require reconciliation")
        else:
            _require(set(case["expected"]) == set(case["initial"]) and
                     all(case["expected"][k] != case["initial"][k]
                         for k in case["expected"]),
                     "full CRM handoff depth changed")
    return {
        "schema": PUBLIC_SCHEMA, "status": "eight_offline_train_candidates_source_audited",
        "original_world_sha256": staged["original_world_sha256"],
        "source_snapshot_binding_sha256": _hash(_raw(staged["source_assets_hex"])),
        "private_staged_sha256": _hash(_raw(staged)),
        "builder_source_sha256": _hash(Path(__file__).read_bytes()),
        "case_count": len(cases),
        "per_workflow": dict(sorted(Counter(c["family"] for c in cases).items())),
        "distinct_source_asset_count": len({_hash(source_bytes(c, world)) for c in cases}),
        "cross_split_overlap_counts": staged["cross_split_overlap_counts"],
        "source_tier": "original_synthetic_business_records; SEC reference is not task gold",
        "original_train_selection_final_counts_unchanged": [20, 20, 100],
        "gui_qualified_count": 0, "sft_episode_count": 0,
        "official_final_admitted": 0, "model_results": 0,
    }


def _read_original(root: Path) -> dict[str, dict]:
    result = {}
    for split in ("train", "selection", "official_hidden"):
        private = root / split / "private"
        path = private / "partition_cases.json"
        receipt_path = private / "partition_receipt.json"
        _require(all(p.is_file() and not p.is_symlink() and
                     stat.S_IMODE(p.stat().st_mode) & 0o077 == 0
                     for p in (path, receipt_path)),
                 "original private partition evidence unavailable or exposed")
        world = json.loads(path.read_bytes())
        receipt = json.loads(receipt_path.read_bytes())
        _require(receipt.get("schema") == "envloop-odoo-partition-candidate-v1" and
                 receipt.get("partition") == split and
                 receipt.get("official_final_tasks_admitted") == 0 and
                 receipt.get("case_manifest_sha256") ==
                 _hash(json.dumps(world, sort_keys=True).encode()),
                 "original world does not match its seeded partition receipt")
        result[split] = world
    return result


def _private_write(path: Path, payload: dict) -> None:
    _require(not path.exists() and not path.is_symlink(), "refusing to overwrite evidence")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(_raw(payload))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("stage", "audit"))
    parser.add_argument("--original-workers", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    original = _read_original(args.original_workers)
    if args.command == "stage":
        staged = build(secrets.token_hex(32), original)
        _private_write(args.private_out, staged)
    else:
        staged = json.loads(args.private_out.read_bytes())
    public = audit(staged, original)
    _require(not args.public_out.exists(), "refusing to overwrite public receipt")
    args.public_out.parent.mkdir(parents=True, exist_ok=True)
    args.public_out.write_bytes(json.dumps(public, sort_keys=True, indent=2).encode() + b"\n")
    print(json.dumps({"status": public["status"], "case_count": public["case_count"],
                      "gui_qualified_count": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
