"""Stage five-SKU, train-only pricing-policy analogues on disjoint parents.

This supplemental pool leaves the frozen original 20/20/100 candidate plan
unchanged. It only uses parents already assigned to the training partition.
All quote facts, child identities and computed prices remain evaluator-private.
"""

from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
from hashlib import sha256
from html import escape
import json
import os
from pathlib import Path

from . import plan


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "envloop-magento-train-transfer-analogues-v1"
PUBLIC_SCHEMA = "envloop-magento-train-transfer-analogues-public-v1"
SOURCE_RECEIPT = ROOT / "docs/evidence/magento-original-catalog-100-candidates-2026-09-25.json"
POLICIES = plan.FINAL_TEMPLATES
POLICY_TEXT = {
    "multi-variant-margin-floor": "For each listed variant, derive a list price from its supplier cost and the stated minimum gross margin. Always advance fractional cents to the next nickel.",
    "multi-variant-parity-ladder": "For each listed variant, combine the supplier anchor with its own tier adjustment, then advance to the next nickel.",
    "multi-variant-stock-promotion": "Use the stronger markdown only when the quoted stock meets or exceeds the threshold; otherwise use the smaller markdown. Advance the resulting price to the next nickel.",
    "multi-variant-freight-surcharge": "First recover the list price implied by cost and margin, then add the variant's freight-class charge. Advance the total to the next nickel.",
}
NEAR_MISS_DESCRIPTIONS = {
    "multi-variant-margin-floor": "apply the lower margin tier to a high-margin SKU",
    "multi-variant-parity-ladder": "omit one tier increment and price from the anchor alone",
    "multi-variant-stock-promotion": "use the opposite stock-threshold discount branch",
    "multi-variant-freight-surcharge": "omit one SKU's freight-class charge",
}


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def _sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _source_binding() -> dict[str, str]:
    raw = SOURCE_RECEIPT.read_bytes()
    receipt = json.loads(raw)
    _require(receipt.get("schema") == "envloop-magento-original-catalog-candidates-public-v1"
             and receipt.get("split_counts") == plan.SPLITS
             and receipt.get("private_source_inventory_sha256") == plan.INVENTORY_SHA256
             and receipt.get("final_template_counts") == {name: 25 for name in POLICIES}
             and receipt.get("official_final_tasks_admitted") == 0,
             "original Magento aggregate receipt changed")
    return {
        "original_factory_source_sha256": _sha(Path(plan.__file__).read_bytes()),
        "train_analogue_source_sha256": _sha(Path(__file__).read_bytes()),
        "aggregate_receipt_sha256": _sha(raw),
        "source_inventory_sha256": plan.INVENTORY_SHA256,
    }


def _price(row: dict, policy: str) -> Decimal:
    facts = row["source_facts"]
    old = Decimal(row["initial_price"])
    if policy == "multi-variant-margin-floor":
        return plan.nickel_up(Decimal(facts["supplier_cost"]) /
                              (Decimal(1) - Decimal(facts["gross_margin_floor"])))
    if policy == "multi-variant-parity-ladder":
        return plan.nickel_up(Decimal(facts["anchor_price"]) +
                              Decimal(facts["tier_increment"]))
    if policy == "multi-variant-stock-promotion":
        discount = (Decimal(facts["discount_if_at_least_threshold"])
                    if int(facts["quoted_stock_units"]) >= int(facts["threshold_units"])
                    else Decimal(facts["discount_otherwise"]))
        return plan.nickel_up(old * (Decimal(1) - discount))
    if policy == "multi-variant-freight-surcharge":
        return plan.nickel_up(
            Decimal(facts["supplier_cost"]) /
            (Decimal(1) - Decimal(facts["gross_margin_floor"])) +
            Decimal(facts["freight_class"]) * Decimal(facts["freight_usd_per_class"]))
    raise ValueError("unknown transfer policy")


def _wrong_price(row: dict, policy: str) -> Decimal:
    facts = row["source_facts"]
    old = Decimal(row["initial_price"])
    if policy == "multi-variant-margin-floor":
        wrong = plan.nickel_up(Decimal(facts["supplier_cost"]) /
                               (Decimal(1) - Decimal("0.31")))
    elif policy == "multi-variant-parity-ladder":
        wrong = plan.nickel_up(Decimal(facts["anchor_price"]))
    elif policy == "multi-variant-stock-promotion":
        discount = (Decimal(facts["discount_otherwise"])
                    if int(facts["quoted_stock_units"]) >= int(facts["threshold_units"])
                    else Decimal(facts["discount_if_at_least_threshold"]))
        wrong = plan.nickel_up(old * (Decimal(1) - discount))
    elif policy == "multi-variant-freight-surcharge":
        wrong = plan.nickel_up(Decimal(facts["supplier_cost"]) /
                               (Decimal(1) - Decimal(facts["gross_margin_floor"])))
    else:
        raise ValueError("unknown transfer policy")
    _require(wrong > 0 and wrong != Decimal(row["target_price"]),
             "policy near miss does not differ from gold")
    return wrong


def _quote_body(title: str, policy: str, rows: list[dict]) -> str:
    keys = sorted({key for row in rows for key in row["source_facts"]})
    header = ["Variant SKU", "Existing price"] + [key.replace("_", " ").title() for key in keys]
    body = []
    for row in sorted(rows, key=lambda value: value["sku"]):
        values = [row["sku"], row["initial_price"]] + [str(row["source_facts"].get(key, "")) for key in keys]
        body.append("<tr>" + "".join(f"<td>{escape(value)}</td>" for value in values) + "</tr>")
    return (f"<h2>{escape(title)}</h2><p>{escape(POLICY_TEXT[policy])}</p>"
            "<p>Review the current quoted facts for this parent product only.</p>"
            "<table><thead><tr>" +
            "".join(f"<th>{escape(label)}</th>" for label in header) +
            "</tr></thead><tbody>" + "".join(body) +
            "</tbody></table><p>Do not alter any unlisted variant or other business record.</p>")


def _case(seed: str, parent: dict, policy: str) -> dict:
    _require(policy in POLICIES and len(parent["children"]) >= 6,
             "five targets and an untouched same-parent comparator required")
    base = plan._case(seed, parent, "official_candidate", POLICIES.index(policy))
    rows = base["target_variants"]
    _require(len(rows) == 5 and len(base["untouched_comparators"]) >= 1,
             "final-like five-SKU source composition missing")
    if policy == "multi-variant-parity-ladder":
        # The original parity formula already lands on a nickel. A separate
        # train source fact makes the stated round-up rule causally necessary.
        facts = rows[0]["source_facts"]
        facts["tier_increment"] = str(Decimal(facts["tier_increment"]) + Decimal("0.03"))
        rows[0]["target_price"] = str(_price(rows[0], policy))
    if policy == "multi-variant-stock-promotion":
        # Train on both sides of the inclusive stock threshold, including
        # equality. These synthetic quote facts never alter final cases.
        for row, stock in zip(rows[:2], (20, 19)):
            row["source_facts"]["quoted_stock_units"] = stock
            row["target_price"] = str(_price(row, policy))
    _require(all(Decimal(row["target_price"]) != Decimal(row["initial_price"])
                 for row in rows), "train-only policy stress produced a no-op")
    opaque = plan.digest({"pool": SCHEMA, "seed": seed,
                          "parent": parent["parent_id"], "policy": policy})[:16]
    title = "Vendor renewal worksheet " + opaque
    base.update({
        "task_id": "magento-train-transfer-" + opaque,
        "split": "train",
        "template_group": "train-transfer-" + policy + "-v1",
        "quote_page_title": title,
        "quote_page_body": _quote_body(title, policy, rows),
        "instruction": (f'In Content > Pages, inspect "{title}" for configurable product '
                        f'{parent["parent_sku"]}. Resolve the policy and update all five '
                        "named child SKUs in Catalog. Save each variant and preserve "
                        "every unlisted variant and unrelated record."),
        "candidate_status": "offline_train_analogue_unverified",
        "near_miss_control": {
            "kind": "one_variant_wrong_policy_calculation",
            "sku": rows[0]["sku"],
            "wrong_price": str(_wrong_price(rows[0], policy)),
            "description": NEAR_MISS_DESCRIPTIONS[policy],
            "all_other_targets_correct": True,
            "expected_score": 0,
        },
        "no_regression_scope": ["untouched variants of the same parent",
                                "all other catalog parents and business records",
                                "quote source page unchanged"],
        "source_type": plan.MODELLED_SOURCE,
    })
    base["quote_page_body_sha256"] = _sha(base["quote_page_body"].encode())
    base["package_sha256"] = plan.digest({key: value for key, value in base.items()
                                           if key != "package_sha256"})
    return base


def build(inventory: dict, inventory_sha256: str, seed: str,
          original_plan: dict) -> dict:
    """Use eight eligible original-train parents, two per arithmetic policy."""
    expected = plan.build(inventory, inventory_sha256, seed)
    _require(original_plan == expected,
             "original candidate plan differs from pinned source and seed")
    parents = {p["parent_id"]: p for p in inventory["parents"]}
    train_ids = [case["parent_id"] for case in original_plan["cases"]["train"]]
    eligible = [parents[pid] for pid in train_ids if pid in parents and
                len(parents[pid]["children"]) >= 6]
    eligible.sort(key=lambda p: (-len(p["children"]),
                                 plan.digest({"pool": SCHEMA, "seed": seed,
                                              "parent_sku": p["parent_sku"]})))
    _require(len(eligible) >= 8,
             "fewer than eight original train parents have five targets and a comparator")
    cases = [_case(seed, eligible[i * 2 + offset], policy)
             for i, policy in enumerate(POLICIES) for offset in range(2)]
    staged = {
        "schema": SCHEMA,
        "status": "offline_train_only_candidates_no_gui_or_model_result",
        "source_binding": _source_binding(),
        "original_plan_sha256": plan.digest(original_plan),
        "private_seed_sha256": _sha(seed.encode()),
        "original_train_count": 20,
        "supplemental_train_count": 8,
        "cases": cases,
        "official_final_admitted": 0,
        "model_results": 0,
    }
    validate(staged, inventory, inventory_sha256, seed, original_plan)
    return staged


def validate(staged: dict, inventory: dict, inventory_sha256: str,
             seed: str, original_plan: dict) -> None:
    """Audit coverage, formulas, comparators, and protected source separation."""
    _require(original_plan == plan.build(inventory, inventory_sha256, seed) and
             staged.get("schema") == SCHEMA and
             staged.get("status") == "offline_train_only_candidates_no_gui_or_model_result" and
             staged.get("source_binding") == _source_binding() and
             staged.get("original_plan_sha256") == plan.digest(original_plan) and
             staged.get("private_seed_sha256") == _sha(seed.encode()) and
             staged.get("original_train_count") == 20 and
             staged.get("supplemental_train_count") == 8 and
             staged.get("official_final_admitted") == 0 and
             staged.get("model_results") == 0,
             "Magento transfer source binding or status changed")
    cases = staged.get("cases")
    _require(type(cases) is list and len(cases) == 8,
             "exactly eight five-SKU Magento train analogues required")
    parents = {p["parent_id"]: p for p in inventory["parents"]}
    train_ids = {case["parent_id"] for case in original_plan["cases"]["train"]}
    protected = original_plan["cases"]["selection"] + original_plan["cases"]["official_candidate"]
    protected_parent_ids = {case["parent_id"] for case in protected}
    protected_entity_ids = {r["entity_id"] for case in protected for r in case["target_variants"]}
    protected_skus = {r["sku"] for case in protected for r in case["target_variants"]}
    protected_sources = {case["source_family"] for case in protected}
    original_ids = {case["task_id"] for split in plan.SPLITS
                    for case in original_plan["cases"][split]}
    seen_ids: set[str] = set()
    seen_parents: set[int] = set()
    family_sources: dict[str, set[str]] = {policy: set() for policy in POLICIES}
    for case in cases:
        _require(type(case) is dict and case.get("split") == "train" and
                 case.get("policy_kind") in POLICIES and
                 case.get("template_group") ==
                 "train-transfer-" + case["policy_kind"] + "-v1" and
                 case.get("candidate_status") == "offline_train_analogue_unverified" and
                 all(case.get(flag) is False for flag in
                     ("gui_positive_passed", "gui_negative_passed",
                      "fresh_reset_passed", "official_final_admitted")),
                 "Magento train-only provenance or candidate status changed")
        policy = case["policy_kind"]
        parent = parents.get(case["parent_id"])
        _require(parent is not None and case["parent_id"] in train_ids and
                 case["parent_id"] not in protected_parent_ids and
                 case["parent_id"] not in seen_parents and
                 case["source_family"] == f"magento-parent:{parent['parent_id']}" and
                 case["source_family"] not in protected_sources and
                 case["parent_sku"] == parent["parent_sku"] and
                 len(parent["children"]) >= 6,
                 "Magento analogue parent/source is not disjoint original train data")
        child_map = {r["entity_id"]: r for r in parent["children"]}
        rows = case["target_variants"]
        comparators = case["untouched_comparators"]
        _require(len(rows) == 5 and len(comparators) == min(2, len(parent["children"]) - 5) and
                 len({r["entity_id"] for r in rows + comparators}) == 5 + len(comparators) and
                 all(r["entity_id"] in child_map and
                     r["sku"] == child_map[r["entity_id"]]["sku"] and
                     r["entity_id"] not in protected_entity_ids and
                     r["sku"] not in protected_skus for r in rows + comparators) and
                 all(Decimal(r["target_price"]) == _price(r, policy) and
                     Decimal(r["target_price"]) != Decimal(r["initial_price"])
                     for r in rows),
                 "five policy-derived SKU targets and untouched comparators required")
        _require(all(c["price"] == child_map[c["entity_id"]]["price"]
                     for c in comparators) and
                 case["quote_page_body"] == _quote_body(case["quote_page_title"], policy, rows) and
                 case["quote_page_body_sha256"] == _sha(case["quote_page_body"].encode()) and
                 case["near_miss_control"] == {
                     "kind": "one_variant_wrong_policy_calculation",
                     "sku": rows[0]["sku"],
                     "wrong_price": str(_wrong_price(rows[0], policy)),
                     "description": NEAR_MISS_DESCRIPTIONS[policy],
                     "all_other_targets_correct": True,
                     "expected_score": 0,
                 } and
                 case["no_regression_scope"] ==
                 ["untouched variants of the same parent",
                  "all other catalog parents and business records",
                  "quote source page unchanged"],
                 "Magento quote/near-miss/no-regression contract changed")
        if policy == "multi-variant-stock-promotion":
            _require([int(row["source_facts"]["quoted_stock_units"]) for row in rows[:2]]
                     == [20, 19], "inclusive stock-threshold stress missing")
        if policy == "multi-variant-parity-ladder":
            raw_first = (Decimal(rows[0]["source_facts"]["anchor_price"]) +
                         Decimal(rows[0]["source_facts"]["tier_increment"]))
            _require(raw_first % plan.NICKEL != 0 and
                     Decimal(rows[0]["target_price"]) > raw_first,
                     "parity nickel-rounding stress missing")
        unsealed = {key: value for key, value in case.items() if key != "package_sha256"}
        _require(case["package_sha256"] == plan.digest(unsealed) and
                 case["task_id"] not in original_ids and
                 case["task_id"] not in seen_ids,
                 "Magento analogue package identity changed or collides")
        seen_ids.add(case["task_id"])
        seen_parents.add(case["parent_id"])
        family_sources[policy].add(case["source_family"])
    _require(all(len(sources) == 2 for sources in family_sources.values()),
             "each Magento policy requires two disjoint train parent families")


def public_receipt(staged: dict, inventory: dict, inventory_sha256: str,
                   seed: str, original_plan: dict) -> dict:
    validate(staged, inventory, inventory_sha256, seed, original_plan)
    return {
        "schema": PUBLIC_SCHEMA,
        "status": "source_only_two_per_policy_staged_offline_no_gui_admission",
        "source_binding": staged["source_binding"],
        "original_train_count": 20,
        "supplemental_train_count": 8,
        "policy_counts": dict(sorted(Counter(c["policy_kind"] for c in staged["cases"]).items())),
        "distinct_train_parent_families_per_policy": 2,
        "target_skus_per_case": 5,
        "untouched_same_parent_comparators_per_case_min": min(len(c["untouched_comparators"]) for c in staged["cases"]),
        "untouched_same_parent_comparators_per_case_max": max(len(c["untouched_comparators"]) for c in staged["cases"]),
        "protected_partition_source_and_entity_overlap": 0,
        "inclusive_stock_threshold_and_parity_rounding_stress_present": True,
        "private_cases_sha256": plan.digest(staged),
        "gui_controls_passed": 0,
        "model_results": 0,
        "official_final_admitted": 0,
    }


def _write_new(path: Path, value: object, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False).encode() + b"\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--seed-file", type=Path, required=True)
    parser.add_argument("--original-plan", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    private_out = args.private_out.resolve()
    plan_parent = args.original_plan.resolve().parent
    _require((private_out.is_relative_to((ROOT / "work").resolve()) or
              (args.original_plan.name == "candidate-plan-v2.private.json" and
               "work" in plan_parent.parts and private_out.parent == plan_parent)) and
             not private_out.exists() and not args.public_out.exists(),
             "new ignored private output and new public receipt required")
    inventory_raw = args.inventory.read_bytes()
    plan_raw = args.original_plan.read_bytes()
    aggregate = json.loads(SOURCE_RECEIPT.read_bytes())
    _require(_sha(inventory_raw) == plan.INVENTORY_SHA256 and
             _sha(plan_raw) == aggregate["private_candidate_plan_sha256"],
             "private original inventory or plan bytes differ from public pin")
    inventory = json.loads(inventory_raw)
    original_plan = json.loads(plan_raw)
    seed = args.seed_file.read_text().strip()
    staged = build(inventory, _sha(inventory_raw), seed, original_plan)
    receipt = public_receipt(staged, inventory, _sha(inventory_raw), seed, original_plan)
    _write_new(private_out, staged, 0o600)
    _write_new(args.public_out, receipt, 0o644)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
