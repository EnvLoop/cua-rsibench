"""Field-limited, read-only screen for SEC Excel transfer-source candidates.

This does not fetch filings or admit training cases. The evaluator keeps issuer,
accession, skill mapping, and fact values in an ignored private record. Only
aggregate counts and a salted commitment may be exported.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import hmac
import json
from pathlib import Path
import re
from urllib.parse import urlparse


SCHEMA = "envloop-sec-excel-two-graph-source-availability-private-v1"
PUBLIC_SCHEMA = "envloop-sec-excel-transfer-source-availability-public-v1"
ACCESSION = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
CASH_FIELDS = {
    "period_end", "operating", "investing", "financing", "fx",
    "net_change", "beginning", "ending", "cash", "restricted",
}
INTEREST_FIELDS = {
    "period_end", "operating_income", "interest_expense_abs",
    "cash_from_operations", "debt_principal_components", "debt_principal_total",
}


def _number(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("invalid_numeric_field")
    try:
        result = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError("invalid_numeric_field") from error
    if not result.is_finite():
        raise ValueError("nonfinite_numeric_field")
    return result


def _year_profile(period: dict) -> str:
    keys = set(period)
    if keys == CASH_FIELDS:
        if (_number(period["operating"]) + _number(period["investing"])
                + _number(period["financing"]) + _number(period["fx"])
                != _number(period["net_change"])):
            raise ValueError("cash_flow_bridge_mismatch")
        if (_number(period["beginning"]) + _number(period["net_change"])
                != _number(period["ending"])):
            raise ValueError("cash_balance_bridge_mismatch")
        if (_number(period["cash"]) + _number(period["restricted"])
                != _number(period["ending"])):
            raise ValueError("cash_scope_bridge_mismatch")
        return "cash"
    if keys == INTEREST_FIELDS:
        if any(_number(period[k]) <= 0 for k in (
                "operating_income", "interest_expense_abs",
                "cash_from_operations", "debt_principal_total")):
            raise ValueError("nonpositive_interest_profile_field")
        components = period["debt_principal_components"]
        if (not isinstance(components, list) or len(components) < 2
                or any(_number(component) < 0 for component in components)
                or sum(map(_number, components), Decimal(0))
                != _number(period["debt_principal_total"])):
            raise ValueError("debt_components_mismatch")
        return "interest"
    raise ValueError("unrecognized_fact_profile")


def _sec_url(url: object, *, cik: int, accession: str, document: str,
             index: bool) -> bool:
    if not isinstance(url, str):
        return False
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "www.sec.gov":
        return False
    parent = f"/Archives/edgar/data/{cik}/{accession.replace('-', '')}/"
    expected = accession + "-index.htm" if index else document
    return parsed.path == parent + expected and not parsed.query


def audit(*, registry_path: Path, cards_path: Path, pilot_path: Path,
          salt_path: Path) -> dict:
    raw = pilot_path.read_bytes()
    private = json.loads(raw)
    registry_raw = registry_path.read_bytes()
    cards_raw = cards_path.read_bytes()
    registry = json.loads(registry_raw)
    cards = json.loads(cards_raw)
    errors: set[str] = set()
    if private.get("schema") != SCHEMA:
        errors.add("private_schema_mismatch")
    if private.get("original_140_registry_sha256") != sha256(registry_raw).hexdigest():
        errors.add("original_registry_digest_mismatch")
    if private.get("reviewed_cards_sha256") != sha256(cards_raw).hexdigest():
        errors.add("reviewed_cards_digest_mismatch")
    slots = registry.get("slots", [])
    card_rows = cards.get("cards", [])
    if (len(slots) != 140 or Counter(x.get("split") for x in slots)
            != {"train": 20, "selection": 20, "final": 100}):
        errors.add("original_140_partition_mismatch")
    card_by_graph = {c["final_graph_reservation"]: c for c in card_rows}
    if len(card_by_graph) != 13 or not all(
            c.get("independent_skill_review") is True for c in card_rows):
        errors.add("reviewed_13_card_gate_mismatch")
    heldout_ciks = {x.get("issuer_cik") for x in slots}
    heldout_accessions = {x.get("original_filing_accession") for x in slots}
    heldout_templates = {x.get("semantic_template_reservation") for x in slots}
    rows = private.get("records", [])
    if not isinstance(rows, list) or len(rows) != 4:
        errors.add("two_graph_four_source_pilot_required")
        rows = rows if isinstance(rows, list) else []
    graphs: Counter[str] = Counter()
    graph_lanes: dict[str, set[str]] = defaultdict(set)
    graph_profiles: dict[str, set[str]] = defaultdict(set)
    graph_templates: dict[str, set[str]] = defaultdict(set)
    issuers: set[int] = set()
    accessions: set[str] = set()
    candidate_issuers: set[int] = set()
    candidate_accessions: set[str] = set()
    profiles_checked = 0
    for row in rows:
        try:
            graph = row["final_graph_reservation"]
            card = card_by_graph[graph]
            issuer = row["issuer_cik"]
            accession = row["accession"]
            document = row["primary_document"]
            lane = row["analogue_lane"]
            template = row["template_family"]
            if (not isinstance(issuer, int) or issuer <= 0
                    or not isinstance(accession, str)
                    or not ACCESSION.fullmatch(accession)
                    or not isinstance(document, str) or "/" in document
                    or not isinstance(template, str) or not template):
                raise ValueError("invalid_candidate_identity")
            candidate_issuers.add(issuer)
            candidate_accessions.add(accession)
            if (issuer in heldout_ciks or accession in heldout_accessions
                    or issuer in issuers or accession in accessions):
                raise ValueError("original_or_pilot_source_overlap")
            if template in heldout_templates:
                raise ValueError("original_template_family_overlap")
            if (row.get("skill_signature_sha256")
                    != card.get("skill_signature_sha256")):
                raise ValueError("signed_skill_signature_mismatch")
            if (row.get("primary_document_type_checked") != "10-K"
                    or not _sec_url(row.get("sec_filing_index_url"), cik=issuer,
                                    accession=accession, document=document,
                                    index=True)
                    or not _sec_url(row.get("sec_original_10k_url"), cik=issuer,
                                    accession=accession, document=document,
                                    index=False)):
                raise ValueError("original_sec_filing_identity_mismatch")
            years = row.get("periods")
            if not isinstance(years, list) or len(years) != 2:
                raise ValueError("two_period_fact_availability_missing")
            profiles = {_year_profile(year) for year in years}
            if len(profiles) != 1 or years[0]["period_end"] == years[1]["period_end"]:
                raise ValueError("source_period_or_profile_mismatch")
            if (row.get("raw_source_bytes_captured") is not False
                    or row.get("companyfacts_snapshot_captured") is not False
                    or row.get("independent_fact_review_completed") is not False):
                raise ValueError("unsupported_source_admission_claim")
            graphs[graph] += 1
            graph_lanes[graph].add(lane)
            graph_profiles[graph].update(profiles)
            graph_templates[graph].add(template)
            issuers.add(issuer)
            accessions.add(accession)
            profiles_checked += 1
        except (KeyError, TypeError, ValueError) as error:
            errors.add(str(error) if isinstance(error, ValueError) else
                       "malformed_candidate_record")
    if (len(graphs) != 2 or any(count != 2 for count in graphs.values())
            or any(lanes != {"A", "B"} for lanes in graph_lanes.values())
            or len(issuers) != 4 or len(accessions) != 4):
        errors.add("four_unique_sources_across_two_graphs_required")
    if (set(map(frozenset, graph_profiles.values()))
            != {frozenset({"cash"}), frozenset({"interest"})}):
        errors.add("two_distinct_fact_profiles_required")
    if any(len(v) != 1 for v in graph_templates.values()) or len({
            next(iter(v)) for v in graph_templates.values() if v}) != 2:
        errors.add("new_template_family_per_graph_required")
    salt = salt_path.read_bytes()
    if len(salt) < 32:
        errors.add("commitment_salt_too_short")
    return {
        "schema": PUBLIC_SCHEMA,
        "status": ("source_identity_and_fact_availability_screened_raw_capture_pending"
                   if not errors else "blocked"),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_10k_candidates_checked": len(rows),
        "graph_profiles_screened": len(graphs),
        "distinct_new_issuers": len(issuers),
        "distinct_new_10k_accessions": len(accessions),
        "two_period_fact_profiles_arithmetic_checked": profiles_checked,
        "source_issuer_overlap_count": len(candidate_issuers & heldout_ciks),
        "source_accession_overlap_count": len(candidate_accessions & heldout_accessions),
        "original_registry_sha256": sha256(registry_raw).hexdigest(),
        "private_source_availability_salted_commitment":
            hmac.new(salt, raw, "sha256").hexdigest(),
        "source_access": "SEC original 10-K HTML browser research; host raw byte capture pending",
        "original_filing_bytes_captured": 0,
        "companyfacts_snapshots_captured": 0,
        "independently_verified_complete_fact_sets": 0,
        "authored_training_workbooks": 0,
        "saved_ooxml_controls": 0,
        "original_excel_web_gui_controls": 0,
        "admitted_train_analogues": 0,
        "official_final_admissions": 0,
        "errors": sorted(errors),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-registry", type=Path, required=True)
    parser.add_argument("--reviewed-cards", type=Path, required=True)
    parser.add_argument("--private-pilot", type=Path, required=True)
    parser.add_argument("--private-salt", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    result = audit(registry_path=args.private_registry,
                   cards_path=args.reviewed_cards, pilot_path=args.private_pilot,
                   salt_path=args.private_salt)
    args.public_out.parent.mkdir(parents=True, exist_ok=True)
    args.public_out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    if result["errors"]:
        raise SystemExit("source availability screen failed: " +
                         ", ".join(result["errors"]))


if __name__ == "__main__":
    main()
