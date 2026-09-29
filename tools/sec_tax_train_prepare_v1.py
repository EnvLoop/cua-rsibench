"""Prepare two source-disjoint TRAIN-only SEC tax-position analogue cases.

This adapter reads exact reviewed TRAIN source fields and the signed causal
skill card. It never reads hidden-final workbooks, task text, answer files or
model outputs. The review SHA must be supplied after independent sign-off.
"""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
import math
import os
from pathlib import Path

from tools.office_excel_transfer_signed_review_v1 import verify as verify_cards
from tools.office_transfer_source_gate_v1 import EXCEL_SPLIT_SHA


CARD_SIGNATURE = "ff413ae00b002631deefbccab6a6392405c63e6f31a968efbb5ef67aaa5506e8"
GRAPH = "uncertain_tax_position_activity_and_interest_scope"
SOURCE_PLAN_SHA256 = "d975e9a31259b6a5bf5474b3b2b57b140fc55a5da03e3357bf2cca78de3e13aa"
REVIEW_SHA256 = "0a016835fbd0eafec32361beaff0ef8486eb55efa1fa12c617eef91bcc6f455e"
BRIDGE_KEYS = ("opening", "current_year_additions", "prior_year_additions",
               "prior_year_reductions", "settlements", "lapse", "translation",
               "other", "closing")
MANDATORY = ("opening", "current_year_additions", "prior_year_additions",
             "prior_year_reductions", "settlements", "closing",
             "accrued_interest_penalties")
FLOW_NAMES = ("net_interest_expense", "combined_interest_penalties_expense_benefit")
CASE_KEYS = (*BRIDGE_KEYS, "accrued_interest_penalties", "interest_flow")
SCENARIOS = ({"additions": 53.0, "settlements": -24.0, "accrual_change": 0.08},
             {"additions": 71.0, "settlements": -31.0, "accrual_change": -0.06})


def _sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _read(path: Path) -> tuple[bytes, dict]:
    raw = path.read_bytes()
    return raw, json.loads(raw)


def _private(path: Path, obj: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    raw = (json.dumps(obj, indent=2, sort_keys=True) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(raw)
    return _sha(raw)


def _fact(item: dict, key: str, *, mandatory: bool) -> dict:
    _require(isinstance(item, dict), f"missing_reviewed_template_field:{key}")
    presence = item.get("status")
    _require(presence in {"reported", "disclosed_dash", "not_separately_reported"},
             f"unreviewed_source_presence:{key}")
    value = item.get("signed_value_musd")
    source = item.get("source_field")
    if presence == "not_separately_reported":
        _require(not mandatory and value is None and source is None,
                 f"unreported_category_misrepresented_as_filed_fact:{key}")
        return {"presence": presence, "value": None, "document": None,
                "ixbrl_tag": None, "ixbrl_context_ref": None,
                "row_locator": None}
    _require(isinstance(value, (int, float)) and not isinstance(value, bool)
             and math.isfinite(value) and isinstance(source, dict)
             and source.get("companyfacts_same_accession_match") is True
             and isinstance(source.get("document"), str)
             and isinstance(source.get("ixbrl_tag"), str)
             and source.get("ixbrl_context_ref")
             and isinstance(source.get("context_period"), dict),
             f"filed_fact_without_exact_original_support:{key}")
    if presence == "disclosed_dash":
        _require(value == 0, f"disclosed_dash_nonzero:{key}")
    if key in {"opening", "closing", "accrued_interest_penalties",
               "current_year_additions", "prior_year_additions"}:
        _require(value >= 0, f"positive_source_category_has_negative_sign:{key}")
    if key in {"prior_year_reductions", "settlements", "lapse"}:
        _require(value <= 0, f"signed_reduction_has_positive_sign:{key}")
    return {"presence": presence, "value": value,
            "document": source["document"], "ixbrl_tag": source["ixbrl_tag"],
            "ixbrl_context_ref": source["ixbrl_context_ref"],
            "row_locator": source.get("table_row_label"),
            "context_period": source["context_period"],
            "filed_value_musd": source.get("filed_musd")}


def _make_case(index: int, reviewed: dict, plan_record: dict,
               raw_root: Path, review_sha: str, card: dict) -> dict:
    _require(reviewed.get("source_index") == index and
             reviewed.get("identity") == plan_record and
             reviewed.get("semantic_source_review") == "pass" and
             reviewed.get("official_final_case_admitted") is False and
             reviewed.get("excel_web_admitted") is False,
             "source_identity_or_review_status_changed")
    raw_hashes = reviewed.get("raw_sha256")
    _require(isinstance(raw_hashes, dict) and {"10k.html", "companyfacts.json"} <= set(raw_hashes),
             "review_missing_original_sec_hashes")
    for name, expected in raw_hashes.items():
        _require(name in {"10k.html", "companyfacts.json", "support.html"} and
                 _sha((raw_root / f"source-{index:02d}" / name).read_bytes()) == expected,
                 "original_sec_raw_bytes_changed")
    _require(plan_record["final_graph_reservation"] == GRAPH and
             plan_record["skill_signature_sha256"] == CARD_SIGNATURE and
             plan_record["form"] == "10-K", "train_source_plan_graph_or_form_changed")
    source_periods = reviewed.get("periods")
    _require(isinstance(source_periods, list) and len(source_periods) == 2,
             "exact_two_annual_periods_required")
    periods = []
    source_flow_key: str | None = None
    for period in sorted(source_periods, key=lambda p: p["period_end"]):
        projection = period.get("template_fields")
        _require(isinstance(projection, dict) and set(BRIDGE_KEYS) <= set(projection)
                 and {"accrued_interest_penalties", *FLOW_NAMES} <= set(projection),
                 "complete_exact_semantic_projection_required")
        selected = [key for key in FLOW_NAMES
                    if projection[key].get("status") != "not_separately_reported"]
        _require(len(selected) == 1 and
                 (source_flow_key is None or source_flow_key == selected[0]),
                 "interest_expense_scope_ambiguous_or_changed")
        source_flow_key = selected[0]
        facts = {key: _fact(projection[key], key, mandatory=key in MANDATORY)
                 for key in BRIDGE_KEYS}
        facts["accrued_interest_penalties"] = _fact(
            projection["accrued_interest_penalties"], "accrued_interest_penalties",
            mandatory=True)
        facts["interest_flow"] = _fact(projection[source_flow_key],
                                        "interest_flow", mandatory=True)
        for key, fact in facts.items():
            if fact["presence"] != "not_separately_reported":
                _require(fact["document"] in raw_hashes,
                         f"fact_document_outside_frozen_original:{key}")
        total = facts["opening"]["value"] + sum(
            0 if facts[key]["value"] is None else facts[key]["value"]
            for key in BRIDGE_KEYS[1:-1])
        _require(abs(total - facts["closing"]["value"]) < 1e-6 and
                 abs(period.get("bridge_arithmetic_delta_musd", float("nan"))) < 1e-6,
                 "source_signed_rollforward_does_not_reconcile")
        periods.append({"period_end": period["period_end"],
                        "period_start": period["period_start"], "fields": facts})
    _require(periods[0]["period_end"] < periods[1]["period_end"] and
             card["minimum_target_edits"] <= 12 and
             card["independent_skill_review"] is True,
             "signed_skill_or_period_order_not_valid")
    flow_label = ("Net interest expense" if source_flow_key == "net_interest_expense"
                  else "Combined interest and penalties expense/(benefit)")
    identity = plan_record
    accession = identity["accession"]
    doc = reviewed["bridge_location"]["document"]
    source_url = (f"https://www.sec.gov/Archives/edgar/data/{identity['issuer_cik']}/"
                  f"{accession.replace('-', '')}/{identity['primary_document'] if doc == '10k.html' else identity['supporting_document']}")
    return {"schema": "envloop.sec_tax_train_analogue_case.private.v1",
            "scope": "TRAIN-only offline analogue; no final workbook or GUI admission",
            "case_index": index, "profile": "signed_utp_activity_and_separate_interest",
            "source": {"issuer_cik": identity["issuer_cik"],
                       "accession": accession, "original_sec_url": source_url,
                       "original_document": doc,
                       "raw_sha256": raw_hashes,
                       "semantic_review_sha256": review_sha,
                       "interest_flow_label": flow_label,
                       "source_flow_field": source_flow_key},
            "skill": {"signature_sha256": CARD_SIGNATURE,
                      "minimum_target_edits": card["minimum_target_edits"],
                      "causal_atom_count": len(card["causal_skill_atoms"]),
                      "dependency_edge_count": len(card["dependency_edges"])},
            "scenario": SCENARIOS[index],
            "scenario_provenance": "authored synthetic sensitivity, not SEC filing facts",
            "periods": periods}


def prepare(*, source_plan: Path, semantic_review: Path, expected_review_sha256: str,
            raw_root: Path, card_root: Path, public_card_review: Path,
            public_card_source: Path, out_dir: Path) -> dict:
    card_result = verify_cards(private_root=card_root,
                               public_review_path=public_card_review,
                               public_source_receipt_path=public_card_source)
    _require(card_result["status"] == "source_review_attested_cards_promoted" and
             card_result["review_flags_promoted"] == 13,
             "thirteen_signed_skill_cards_required")
    plan_raw, plan = _read(source_plan)
    review_raw, review = _read(semantic_review)
    _require(_sha(plan_raw) == SOURCE_PLAN_SHA256 and
             _sha(review_raw) == expected_review_sha256 == REVIEW_SHA256 and
             review.get("schema") == "envloop.sec_tax_train_two_field_review.private.v1" and
             review.get("scope", "").startswith("TRAIN-only") and
             review.get("source_plan_sha256") == _sha(plan_raw) and
             review.get("source_count") == 2 and
             len(review.get("source_reviews", [])) == 2,
             "exact_signed_off_train_semantic_review_required")
    card_raw, cards = _read(card_root / "skill-cards-reviewed.private.json")
    registry_raw, registry = _read(card_root / "private-split-reservations.json")
    _require(plan.get("schema") == "envloop.sec_excel_train_22_raw_source_plan.private.v1"
             and len(plan.get("records", [])) >= 2 and
             plan.get("cards_sha256") == _sha(card_raw) and
             plan.get("registry_sha256") == _sha(registry_raw) == EXCEL_SPLIT_SHA,
             "frozen_train_source_plan_or_split_changed")
    _require(registry.get("schema") == "private-excel-20-20-100-reservations-v1"
             and Counter(x["split"] for x in registry["slots"]) ==
             {"train": 20, "selection": 20, "final": 100},
             "original_private_split_not_frozen")
    card = next((x for x in cards["cards"]
                 if x["skill_signature_sha256"] == CARD_SIGNATURE and
                 x["final_graph_reservation"] == GRAPH), None)
    _require(card is not None, "signed_tax_position_skill_card_missing")
    occupied_issuers = {str(x["issuer_cik"]) for x in registry["slots"]}
    occupied_accessions = {x["original_filing_accession"] for x in registry["slots"]}
    selected = plan["records"][:2]
    _require(len({str(x["issuer_cik"]) for x in selected}) == 2 and
             len({x["accession"] for x in selected}) == 2 and
             all(str(x["issuer_cik"]) not in occupied_issuers and
                 x["accession"] not in occupied_accessions for x in selected),
             "train_sources_overlap_hidden_original_split")
    _require(not (out_dir / "cases").exists(), "private_case_directory_must_be_fresh")
    cases = [_make_case(i, review["source_reviews"][i], selected[i], raw_root,
                        _sha(review_raw), card) for i in range(2)]
    hashes = []
    for case in cases:
        hashes.append(_private(out_dir / "cases" /
                               f"case-{case['case_index']:02d}.private.json", case))
    manifest = {"schema": "envloop.sec_tax_train_case_manifest.private.v1",
                "status": "two_source_disjoint_train_tax_cases_prepared",
                "case_count": 2, "distinct_issuer_count": 2,
                "original_140_issuer_overlap": 0,
                "original_140_accession_overlap": 0,
                "source_plan_sha256": _sha(plan_raw),
                "semantic_review_sha256": _sha(review_raw),
                "signed_card_sha256": _sha(card_raw),
                "case_sha256": hashes, "official_excel_web_admitted": 0}
    manifest_sha = _private(out_dir / "cases-manifest.private.json", manifest)
    return {"status": manifest["status"], "cases": 2,
            "source_disjoint_from_original_140": True,
            "official_excel_web_admitted": 0, "manifest_sha256": manifest_sha}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-plan", type=Path, required=True)
    ap.add_argument("--semantic-review", type=Path, required=True)
    ap.add_argument("--review-sha256", required=True)
    ap.add_argument("--raw-root", type=Path, required=True)
    ap.add_argument("--card-private-root", type=Path, required=True)
    ap.add_argument("--public-card-review", type=Path, required=True)
    ap.add_argument("--public-card-source", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()
    print(json.dumps(prepare(source_plan=args.source_plan,
        semantic_review=args.semantic_review,
        expected_review_sha256=args.review_sha256, raw_root=args.raw_root,
        card_root=args.card_private_root,
        public_card_review=args.public_card_review,
        public_card_source=args.public_card_source,
        out_dir=args.out_dir), sort_keys=True))


if __name__ == "__main__":
    main()
