"""Read-only independent replay of SEC TRAIN raw-source identity and hashes.

This auditor does not import the capture tool or promote any source to a
semantic fact review, saved workbook, GUI case, or official result.
"""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
from html.parser import HTMLParser
import hmac
import ipaddress
import json
from pathlib import Path
import re
from urllib.parse import urlparse


class Visible(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, value: str) -> None:
        self.parts.append(value)


def _text(raw: bytes) -> str:
    parser = Visible()
    parser.feed(raw.decode("utf-8", "replace"))
    return " ".join(parser.parts)


def _sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def audit(*, plan_path: Path, registry_path: Path, cards_path: Path,
          pilot_path: Path, salt_path: Path, raw_root: Path,
          public_capture_path: Path) -> dict:
    plan_raw = plan_path.read_bytes()
    registry_raw = registry_path.read_bytes()
    card_raw = cards_path.read_bytes()
    pilot_raw = pilot_path.read_bytes()
    salt = salt_path.read_bytes()
    plan = json.loads(plan_raw)
    registry = json.loads(registry_raw)
    cards = json.loads(card_raw)
    pilot = json.loads(pilot_raw)
    public = json.loads(public_capture_path.read_bytes())
    _require(plan.get("schema") ==
             "envloop.sec_excel_train_22_raw_source_plan.private.v1" and
             public.get("schema") ==
             "envloop.sec_excel_train_22_raw_source_capture.public.v1" and
             len(salt) >= 32,
             "source_plan_public_schema_or_salt_changed")
    _require(plan.get("registry_sha256") == _sha(registry_raw) and
             plan.get("cards_sha256") == _sha(card_raw) and
             plan.get("prior_pilot_sha256") == _sha(pilot_raw) and
             public.get("private_plan_salted_commitment_sha256") ==
             hmac.new(salt, plan_raw, "sha256").hexdigest(),
             "frozen_boundary_or_salted_plan_changed")
    slots = registry.get("slots", [])
    _require(len(slots) == 140 and Counter(row.get("split") for row in slots) ==
             {"train": 20, "selection": 20, "final": 100},
             "original_partition_changed")
    card_map = {row["final_graph_reservation"]: row for row in cards.get("cards", [])}
    pilot_rows = pilot.get("records", [])
    _require(len(card_map) == 13 and len(pilot_rows) == 4 and
             all(row.get("independent_skill_review") is True
                 for row in card_map.values()),
             "reviewed_graph_or_prior_pilot_changed")
    prior_graphs = {row["final_graph_reservation"] for row in pilot_rows}
    rows = plan.get("records", [])
    _require(len(rows) == 22 and Counter(
        row.get("final_graph_reservation") for row in rows) ==
        {graph: 2 for graph in card_map if graph not in prior_graphs},
        "eleven_graph_two_source_allocation_changed")
    blocked_ciks = {row["issuer_cik"] for row in slots} | {
        row["issuer_cik"] for row in pilot_rows}
    blocked_accessions = {row["original_filing_accession"] for row in slots} | {
        row["accession"] for row in pilot_rows}
    _require(len({row["issuer_cik"] for row in rows}) == 22 and
             len({row["accession"] for row in rows}) == 22 and
             {row["issuer_cik"] for row in rows}.isdisjoint(blocked_ciks) and
             {row["accession"] for row in rows}.isdisjoint(blocked_accessions) and
             all(row["skill_signature_sha256"] ==
                 card_map[row["final_graph_reservation"]]["skill_signature_sha256"]
                 for row in rows),
             "source_disjointness_or_graph_signature_changed")
    count = public.get("original_sec_10k_source_bundles_captured")
    _require(type(count) is int and 0 <= count <= 22 and
             public.get("distinct_new_issuer_ciks") == count and
             public.get("independent_semantic_fact_reviews") == 0 and
             public.get("new_saved_ooxml_train_controls") == 0 and
             public.get("new_excel_web_admitted_train_cases") == 0 and
             public.get("official_final_admissions") == 0,
             "public_counts_or_admission_boundary_changed")
    _require((raw_root.stat().st_mode & 0o777) == 0o700,
             "private_raw_root_exposed")
    case_dirs = sorted(path for path in raw_root.iterdir() if path.is_dir()
                       and path.name.startswith("source-"))
    _require([path.name for path in case_dirs] ==
             [f"source-{i:02d}" for i in range(count)],
             "raw_capture_case_set_not_contiguous")
    total_bytes = 0
    source_files = 0
    supporting_files = 0
    commitments = []
    for i, directory in enumerate(case_dirs):
        row = rows[i]
        _require((directory.stat().st_mode & 0o777) == 0o700,
                 "raw_case_directory_exposed")
        case_path = directory / "source-case.private.json"
        case_raw = case_path.read_bytes()
        case = json.loads(case_raw)
        _require((case_path.stat().st_mode & 0o777) == 0o600 and
                 case.get("schema") ==
                 "envloop.sec_excel_train_raw_source_case.private.v1" and
                 case.get("source_index") == i and
                 case.get("identity") == row and
                 case.get("semantic_fact_review_completed") is False and
                 case.get("excel_web_admitted") is False,
                 "raw_case_manifest_changed")
        commitments.append(hmac.new(salt, case_raw, "sha256").hexdigest())
        cik = row["issuer_cik"]
        accession = row["accession"]
        prefix = (f"https://www.sec.gov/Archives/edgar/data/{cik}/"
                  f"{accession.replace('-', '')}/")
        expected_urls = {
            "submissions": f"https://data.sec.gov/submissions/CIK{cik:010d}.json",
            "index": prefix + accession + "-index" + row["index_extension"],
            "10k": prefix + row["primary_document"],
            "companyfacts": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json",
        }
        if row.get("supporting_document"):
            expected_urls["support"] = prefix + row["supporting_document"]
            supporting_files += 1
        _require(case.get("urls") == expected_urls,
                 "saved_original_sec_urls_changed")
        raw = {}
        for kind, url in expected_urls.items():
            extension = "json" if kind in {"submissions", "companyfacts"} else "html"
            path = directory / f"{kind}.{extension}"
            data = path.read_bytes()
            response = case["response"][kind]
            address = ipaddress.ip_address(response["remote_ip"])
            _require((path.stat().st_mode & 0o777) == 0o600 and
                     response["status"] == 200 and
                     response["tls_verify_result"] == 0 and
                     address.is_global and
                     urlparse(response["url"]).hostname in {"www.sec.gov", "data.sec.gov"} and
                     response["url"] == url and
                     response["bytes"] == len(data) and
                     response["sha256"] == _sha(data),
                     "saved_raw_response_hash_tls_or_url_changed")
            total_bytes += len(data)
            source_files += 1
            raw[kind] = data
        recent = json.loads(raw["submissions"])["filings"]["recent"]
        matches = [j for j, acc in enumerate(recent["accessionNumber"])
                   if acc == accession]
        _require(len(matches) == 1 and
                 json.loads(raw["submissions"])["cik"] == f"{cik:010d}" and
                 all(recent[key][matches[0]] == value for key, value in (
                     ("form", "10-K"), ("primaryDocument", row["primary_document"]),
                     ("filingDate", row["filing_date"]),
                     ("reportDate", row["report_period"]))),
                 "original_submission_identity_not_reproduced")
        index = raw["index"].decode("utf-8", "replace")
        _require(all(value in index for value in (
                     accession, row["primary_document"], row["filing_date"],
                     row["report_period"])) and
                 re.search(r"<td[^>]*>\s*10-K\s*</td>", index, re.I) is not None and
                 re.search(r"\bFORM\s+10-K\b", _text(raw["10k"]), re.I) is not None,
                 "original_index_or_filing_form_not_reproduced")
        if row.get("supporting_document"):
            _require(row["supporting_document"] in index and
                     len(raw["support"]) >= 1000,
                     "incorporated_support_document_not_in_index")
        facts = json.loads(raw["companyfacts"])
        count_for_accession = sum(
            fact.get("accn") == accession and fact.get("form") == "10-K"
            for taxonomy in facts.get("facts", {}).values()
            for concept in taxonomy.values()
            for unit in concept.get("units", {}).values()
            for fact in unit)
        _require(facts.get("cik") == cik and count_for_accession > 0 and
                 case["checks"]["companyfacts_accession_fact_count"] ==
                 count_for_accession,
                 "companyfacts_accession_not_reproduced")
    _require(public.get("source_hash_bindings") == source_files and
             public.get("incorporated_or_supporting_filing_documents_captured") ==
             supporting_files and
             public.get("raw_capture_case_commitment_sha256") == commitments and
             public.get("raw_source_bytes") == total_bytes,
             "public_capture_commitments_or_byte_count_changed")
    return {
        "schema": "envloop.sec_excel_train_22_raw_independent_audit.public.v1",
        "status": "independent_raw_source_replay_passed",
        "source_bundles_reopened": count,
        "original_sec_submissions_index_10k_companyfacts_and_support_reopened":
            source_files,
        "incorporated_or_supporting_filing_documents_reopened": supporting_files,
        "distinct_new_issuers_outside_frozen_140_and_prior_four": count,
        "raw_source_bytes_rehashed": total_bytes,
        "semantic_fact_reviews": 0,
        "saved_ooxml_train_controls": 0,
        "excel_web_train_admissions": 0,
        "official_final_admissions": 0,
        "capture_receipt_sha256": _sha(public_capture_path.read_bytes()),
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-plan", type=Path, required=True)
    parser.add_argument("--private-registry", type=Path, required=True)
    parser.add_argument("--reviewed-cards", type=Path, required=True)
    parser.add_argument("--prior-pilot", type=Path, required=True)
    parser.add_argument("--private-salt", type=Path, required=True)
    parser.add_argument("--private-raw-root", type=Path, required=True)
    parser.add_argument("--public-capture", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    result = audit(plan_path=args.private_plan,
                   registry_path=args.private_registry,
                   cards_path=args.reviewed_cards,
                   pilot_path=args.prior_pilot,
                   salt_path=args.private_salt,
                   raw_root=args.private_raw_root,
                   public_capture_path=args.public_capture)
    args.public_out.parent.mkdir(parents=True, exist_ok=True)
    args.public_out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in (
        "status", "source_bundles_reopened", "raw_source_bytes_rehashed")}))


if __name__ == "__main__":
    main()
