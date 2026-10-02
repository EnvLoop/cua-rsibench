"""Capture distinct original SEC 10-K raw bundles for TRAIN transfer candidates.

This stage proves source identity and records exact bytes. It deliberately does
not claim that any graph has the required facts, or admit an Excel task.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import urlparse

from tools.sec_excel_transfer_official_raw_capture_v1 import (
    _fetch, _global_ip, _visible_text,
)


PLAN_SCHEMA = "envloop.sec_excel_train_22_raw_source_plan.private.v1"
CASE_SCHEMA = "envloop.sec_excel_train_raw_source_case.private.v1"
PUBLIC_SCHEMA = "envloop.sec_excel_train_22_raw_source_capture.public.v1"
BASE_KINDS = ("submissions", "index", "10k", "companyfacts")
ACCESSION = re.compile(r"\d{10}-\d{2}-\d{6}\Z")
DOCUMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
MAX_SINGLE_BYTES = 20_000_000
MAX_TOTAL_BYTES = 700_000_000


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def _private(path: Path, raw: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(raw)


def _load_inputs(plan_path: Path, registry_path: Path, cards_path: Path,
                 pilot_path: Path, salt_path: Path) -> tuple[dict, bytes]:
    plan_raw = plan_path.read_bytes()
    plan = json.loads(plan_raw)
    registry_raw = registry_path.read_bytes()
    cards_raw = cards_path.read_bytes()
    pilot_raw = pilot_path.read_bytes()
    registry = json.loads(registry_raw)
    cards = json.loads(cards_raw)
    pilot = json.loads(pilot_raw)
    salt = salt_path.read_bytes()
    require(plan.get("schema") == PLAN_SCHEMA and len(salt) >= 32,
            "invalid_plan_or_private_commitment_salt")
    require(plan.get("registry_sha256") == digest(registry_raw) and
            plan.get("cards_sha256") == digest(cards_raw) and
            plan.get("prior_pilot_sha256") == digest(pilot_raw),
            "frozen_source_boundary_changed")
    slots = registry.get("slots", [])
    require(len(slots) == 140 and Counter(x.get("split") for x in slots) ==
            {"train": 20, "selection": 20, "final": 100},
            "original_140_partition_changed")
    card_by_graph = {c["final_graph_reservation"]: c for c in cards.get("cards", [])}
    require(len(card_by_graph) == 13 and all(
        c.get("independent_skill_review") is True for c in card_by_graph.values()),
        "reviewed_13_graph_cards_missing")
    pilot_rows = pilot.get("records", [])
    require(len(pilot_rows) == 4 and len({r["final_graph_reservation"]
                                          for r in pilot_rows}) == 2,
            "original_four_source_pilot_changed")
    pilot_graphs = {r["final_graph_reservation"] for r in pilot_rows}
    heldout_issuers = {r["issuer_cik"] for r in slots}
    heldout_accessions = {r["original_filing_accession"] for r in slots}
    heldout_templates = {r["semantic_template_reservation"] for r in slots}
    blocked_issuers = heldout_issuers | {r["issuer_cik"] for r in pilot_rows}
    blocked_accessions = heldout_accessions | {r["accession"] for r in pilot_rows}
    blocked_templates = heldout_templates | {r["template_family"] for r in pilot_rows}
    rows = plan.get("records", [])
    require(isinstance(rows, list) and len(rows) == 22,
            "exactly_22_source_candidates_required")
    require(Counter(r.get("final_graph_reservation") for r in rows) ==
            {graph: 2 for graph in card_by_graph if graph not in pilot_graphs},
            "two_source_candidates_per_remaining_graph_required")
    seen_issuers: set[int] = set()
    seen_accessions: set[str] = set()
    graph_templates: dict[str, set[str]] = {}
    for row in rows:
        graph = row["final_graph_reservation"]
        cik = row.get("issuer_cik")
        accession = row.get("accession")
        document = row.get("primary_document")
        supporting = row.get("supporting_document")
        index_extension = row.get("index_extension")
        template = row.get("template_family")
        require(type(cik) is int and cik > 0 and cik not in blocked_issuers and
                cik not in seen_issuers, "issuer_collision_or_invalid")
        require(isinstance(accession, str) and ACCESSION.fullmatch(accession)
                and accession not in blocked_accessions and
                accession not in seen_accessions, "accession_collision_or_invalid")
        require(isinstance(document, str) and DOCUMENT.fullmatch(document) and
                document.lower().endswith((".htm", ".html")),
                "unsafe_or_non_html_primary_document")
        require(supporting is None or (isinstance(supporting, str) and
                DOCUMENT.fullmatch(supporting) and
                supporting.lower().endswith((".htm", ".html")) and
                supporting != document),
                "unsafe_or_duplicate_supporting_document")
        require(index_extension in {".htm", ".html"},
                "filing_index_extension_missing_or_invalid")
        require(isinstance(template, str) and template and
                template not in blocked_templates,
                "semantic_template_collision_or_invalid")
        require(row.get("skill_signature_sha256") ==
                card_by_graph[graph]["skill_signature_sha256"] and
                row.get("form") == "10-K", "graph_signature_or_form_mismatch")
        require(re.fullmatch(r"\d{4}-\d{2}-\d{2}",
                             str(row.get("filing_date"))) is not None and
                re.fullmatch(r"\d{4}-\d{2}-\d{2}",
                             str(row.get("report_period"))) is not None,
                "filing_or_report_date_missing")
        seen_issuers.add(cik)
        seen_accessions.add(accession)
        graph_templates.setdefault(graph, set()).add(template)
    require(all(len(v) == 1 for v in graph_templates.values()) and
            len({next(iter(v)) for v in graph_templates.values()}) == 11,
            "new_template_family_per_graph_required")
    return plan, salt


def _urls(row: dict) -> dict[str, str]:
    cik = row["issuer_cik"]
    accession = row["accession"]
    parent = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/"
    result = {
        "submissions": f"https://data.sec.gov/submissions/CIK{cik:010d}.json",
        "index": parent + accession + "-index" + row["index_extension"],
        "10k": parent + row["primary_document"],
        "companyfacts": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json",
    }
    if row.get("supporting_document"):
        result["support"] = parent + row["supporting_document"]
    return result


def _source_identity(row: dict, raw: dict[str, bytes]) -> dict:
    submissions = json.loads(raw["submissions"])
    require(submissions.get("cik") == f'{row["issuer_cik"]:010d}',
            "submissions_cik_mismatch")
    recent = submissions.get("filings", {}).get("recent", {})
    columns = ("accessionNumber", "form", "primaryDocument", "filingDate", "reportDate")
    require(all(isinstance(recent.get(k), list) for k in columns),
            "submissions_recent_columns_missing")
    matches = [i for i, accession in enumerate(recent["accessionNumber"])
               if accession == row["accession"]]
    require(len(matches) == 1, "original_10k_accession_not_unique_in_submissions")
    i = matches[0]
    require(all(len(recent[k]) > i for k in columns) and
            recent["form"][i] == "10-K" and
            recent["primaryDocument"][i] == row["primary_document"] and
            recent["filingDate"][i] == row["filing_date"] and
            recent["reportDate"][i] == row["report_period"],
            "original_10k_submission_identity_mismatch")
    index = raw["index"].decode("utf-8", "replace")
    require(all(token in index for token in (row["accession"],
            row["primary_document"], row["filing_date"], row["report_period"])) and
            re.search(r"<td[^>]*>\s*10-K\s*</td>", index, re.I) is not None,
            "original_10k_index_identity_mismatch")
    if row.get("supporting_document"):
        support_rows = re.findall(r"<tr\b[^>]*>(.*?)</tr>", index,
                                  flags=re.I | re.S)
        require(sum(row["supporting_document"] in table_row and
                    re.search(r"EX-13|EXHIBIT\s+13", table_row, re.I) is not None
                    for table_row in support_rows) == 1 and
                len(raw["support"]) >= 1000,
                "supporting_exhibit_13_not_in_original_filing_index")
    filing = _visible_text(raw["10k"])
    require(re.search(r"\bFORM\s+10-K\b", filing, re.I) is not None,
            "original_filing_form_mismatch")
    companyfacts = json.loads(raw["companyfacts"])
    require(companyfacts.get("cik") == row["issuer_cik"],
            "companyfacts_cik_mismatch")
    accession_fact_count = sum(
        fact.get("accn") == row["accession"] and fact.get("form") == "10-K"
        for taxonomy in companyfacts.get("facts", {}).values()
        for concept in taxonomy.values()
        for unit in concept.get("units", {}).values()
        for fact in unit)
    require(accession_fact_count > 0, "companyfacts_original_accession_missing")
    return {"submission_match_count": 1, "companyfacts_accession_fact_count":
            accession_fact_count, "index_form_match": True,
            "filing_form_match": True}


def _case_dir(out_dir: Path, i: int) -> Path:
    return out_dir / f"source-{i:02d}"


def _validate_saved_case(out_dir: Path, i: int, row: dict) -> tuple[dict, int]:
    directory = _case_dir(out_dir, i)
    require(directory.is_dir() and (directory.stat().st_mode & 0o777) == 0o700,
            "saved_source_directory_missing_or_exposed")
    case_path = directory / "source-case.private.json"
    require(case_path.is_file() and (case_path.stat().st_mode & 0o777) == 0o600,
            "saved_source_case_manifest_missing_or_exposed")
    saved = json.loads(case_path.read_bytes())
    require(saved.get("schema") == CASE_SCHEMA and
            saved.get("source_index") == i and
            saved.get("identity") == row and
            saved.get("urls") == _urls(row), "saved_source_plan_mismatch")
    raw: dict[str, bytes] = {}
    byte_count = 0
    for kind in _urls(row):
        path = directory / f"{kind}.{'json' if kind in {'submissions', 'companyfacts'} else 'html'}"
        require(path.is_file() and (path.stat().st_mode & 0o777) == 0o600,
                "saved_source_file_missing_or_exposed")
        value = path.read_bytes()
        response = saved["response"][kind]
        require(response["status"] == 200 and
                response["tls_verify_result"] == 0 and
                response["url"] == saved["urls"][kind] and
                ipaddress.ip_address(response["remote_ip"]).is_global and
                digest(value) == response["sha256"] and
                len(value) == response["bytes"],
                "saved_source_hash_changed")
        raw[kind] = value
        byte_count += len(value)
    require(saved["checks"] == _source_identity(row, raw),
            "saved_source_identity_changed")
    return saved, byte_count


def capture(*, plan_path: Path, registry_path: Path, cards_path: Path,
            pilot_path: Path, salt_path: Path, out_dir: Path,
            public_out: Path, user_agent: str, max_new: int = 22) -> dict:
    require("@" in user_agent and len(user_agent) >= 15,
            "declared_sec_contact_user_agent_required")
    require(0 <= max_new <= 22, "max_new_out_of_range")
    plan, salt = _load_inputs(plan_path, registry_path, cards_path,
                              pilot_path, salt_path)
    plan_raw = plan_path.read_bytes()
    out_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    require((out_dir.stat().st_mode & 0o777) == 0o700,
            "private_capture_root_mode_not_0700")
    resolved: dict[str, str] = {}
    last_request = 0.0
    new_count = 0
    completed: list[dict] = []
    total_bytes = 0
    for i, row in enumerate(plan["records"]):
        directory = _case_dir(out_dir, i)
        if directory.exists():
            saved, nbytes = _validate_saved_case(out_dir, i, row)
        elif new_count < max_new:
            urls = _urls(row)
            with tempfile.TemporaryDirectory(prefix=".sec-source-", dir=out_dir) as temp:
                scratch = Path(temp)
                pending: dict[str, Path] = {}
                response: dict[str, dict] = {}
                for kind in urls:
                    host = urlparse(urls[kind]).hostname
                    if host not in resolved:
                        resolved[host] = _global_ip(host)
                    elapsed = time.monotonic() - last_request
                    if elapsed < 1.1:
                        time.sleep(1.1 - elapsed)
                    last_request = time.monotonic()
                    path = scratch / f"{kind}.tmp"
                    response[kind] = _fetch(urls[kind], ip=resolved[host],
                                            user_agent=user_agent, out=path)
                    require(response[kind]["bytes"] <= MAX_SINGLE_BYTES,
                            "sec_source_exceeds_20mb_case_cap")
                    pending[kind] = path
                raw = {kind: path.read_bytes() for kind, path in pending.items()}
                checks = _source_identity(row, raw)
                nbytes = sum(map(len, raw.values()))
                require(total_bytes + nbytes <= MAX_TOTAL_BYTES,
                        "sec_private_raw_pool_exceeds_700mb_cap")
                staged = scratch / "complete"
                staged.mkdir(mode=0o700)
                for kind in urls:
                    ext = "json" if kind in {"submissions", "companyfacts"} else "html"
                    dest = staged / f"{kind}.{ext}"
                    pending[kind].replace(dest)
                    dest.chmod(0o600)
                saved = {"schema": CASE_SCHEMA, "source_index": i,
                         "identity": row, "retrieved_utc": datetime.now(timezone.utc).isoformat(),
                         "urls": urls, "response": response, "checks": checks,
                         "rights_tier": "public_SEC_filing_data_and_authored_scenarios_only",
                         "semantic_fact_review_completed": False,
                         "excel_web_admitted": False}
                _private(staged / "source-case.private.json",
                         (json.dumps(saved, sort_keys=True, indent=2) + "\n").encode())
                staged.replace(directory)
            new_count += 1
        else:
            continue
        total_bytes += nbytes
        require(total_bytes <= MAX_TOTAL_BYTES, "sec_private_raw_pool_exceeds_700mb_cap")
        completed.append(saved)
    public = {
        "schema": PUBLIC_SCHEMA,
        "status": "raw_capture_complete_semantic_fact_review_pending" if len(completed) == 22
                  else "partial_raw_capture_semantic_fact_review_pending",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "planned_new_source_graphs": 11,
        "planned_source_candidates": 22,
        "original_sec_10k_source_bundles_captured": len(completed),
        "distinct_new_issuer_ciks": len({r["identity"]["issuer_cik"] for r in completed}),
        "original_registry_issuer_overlap": 0,
        "original_registry_accession_overlap": 0,
        "source_hash_bindings": sum(len(row["response"]) for row in completed),
        "incorporated_or_supporting_filing_documents_captured": sum(
            "support" in row["response"] for row in completed),
        "raw_source_bytes": total_bytes,
        "private_plan_salted_commitment_sha256": hmac.new(salt, plan_raw, "sha256").hexdigest(),
        "raw_capture_case_commitment_sha256": [hmac.new(
            salt, (_case_dir(out_dir, row["source_index"]) /
                   "source-case.private.json").read_bytes(), "sha256").hexdigest()
            for row in completed],
        "source_method": "official SEC HTTPS, verified TLS, declared contact User-Agent, at most one request per second",
        "source_documentation_url":
            "https://www.sec.gov/search-filings/edgar-application-programming-interfaces",
        "rights_url": "https://www.sec.gov/about/webmaster-frequently-asked-questions",
        "independent_semantic_fact_reviews": 0,
        "new_saved_ooxml_train_controls": 0,
        "new_excel_web_admitted_train_cases": 0,
        "official_final_admissions": 0,
    }
    public_out.parent.mkdir(parents=True, exist_ok=True)
    public_out.write_text(json.dumps(public, sort_keys=True, indent=2) + "\n")
    return public


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-plan", type=Path, required=True)
    parser.add_argument("--private-registry", type=Path, required=True)
    parser.add_argument("--reviewed-cards", type=Path, required=True)
    parser.add_argument("--prior-pilot", type=Path, required=True)
    parser.add_argument("--private-salt", type=Path, required=True)
    parser.add_argument("--private-out-dir", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    parser.add_argument("--user-agent", required=True)
    parser.add_argument("--max-new", type=int, default=22)
    args = parser.parse_args()
    result = capture(plan_path=args.private_plan,
                     registry_path=args.private_registry,
                     cards_path=args.reviewed_cards,
                     pilot_path=args.prior_pilot,
                     salt_path=args.private_salt,
                     out_dir=args.private_out_dir,
                     public_out=args.public_out,
                     user_agent=args.user_agent,
                     max_new=args.max_new)
    print(json.dumps({k: result[k] for k in (
        "status", "planned_source_candidates",
        "original_sec_10k_source_bundles_captured", "raw_source_bytes")}))


if __name__ == "__main__":
    main()
