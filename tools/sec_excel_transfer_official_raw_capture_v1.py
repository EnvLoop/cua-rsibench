"""Capture four evaluator-private SEC transfer sources with verified HTTPS.

The input is the previously screened private source-availability pilot. This
tool never exposes issuer, accession, source URL, or fact values in its public
receipt. A numeric-literal screen is intentionally weaker than independent
semantic fact review and cannot admit a training or final task.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import hmac
from html.parser import HTMLParser
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from urllib.parse import quote, urlparse

from tools.sec_excel_transfer_source_availability_v1 import _sec_url, _year_profile


SCHEMA = "envloop-sec-transfer-official-raw-capture-private-v1"
PUBLIC_SCHEMA = "envloop-sec-transfer-official-raw-capture-public-v1"
HOSTS = {"www.sec.gov", "data.sec.gov"}
KINDS = ("index", "10k", "companyfacts")


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _visible_text(raw: bytes) -> str:
    parser = _Text()
    parser.feed(raw.decode("utf-8", "replace"))
    return " ".join(parser.parts)


def _global_ip(host: str) -> str:
    if host not in HOSTS:
        raise ValueError("non_sec_hostname")
    url = f"https://dns.google/resolve?name={quote(host)}&type=A"
    result = subprocess.run(
        ["curl", "--silent", "--show-error", "--location", "--proto", "=https",
         "--proto-redir", "=https", "--connect-timeout", "8", "--max-time", "20", url],
        capture_output=True, check=False,
    )
    if result.returncode:
        raise ValueError("verified_doh_lookup_failed")
    try:
        response = json.loads(result.stdout)
        ips = [answer["data"] for answer in response["Answer"]
               if answer.get("type") == 1 and
               ipaddress.ip_address(answer.get("data", "")).is_global]
    except (KeyError, ValueError, TypeError) as error:
        raise ValueError("verified_doh_response_invalid") from error
    if response.get("Status") != 0 or not ips:
        raise ValueError("verified_doh_no_public_ipv4")
    return ips[0]


def _source_urls(record: dict) -> dict[str, str]:
    cik = record["issuer_cik"]
    accession = record["accession"]
    document = record["primary_document"]
    index = record["sec_filing_index_url"]
    filing = record["sec_original_10k_url"]
    facts = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
    if not (_sec_url(index, cik=cik, accession=accession,
                     document=document, index=True)
            and _sec_url(filing, cik=cik, accession=accession,
                         document=document, index=False)):
        raise ValueError("private_sec_source_identity_invalid")
    return {"index": index, "10k": filing, "companyfacts": facts}


def _fetch(url: str, *, ip: str, user_agent: str, out: Path) -> dict:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in HOSTS:
        raise ValueError("non_sec_source_url")
    host = parsed.hostname
    accept = "application/json" if host == "data.sec.gov" else "text/html"
    result = subprocess.run(
        ["curl", "--silent", "--show-error", "--location", "--max-redirs", "2",
         "--proto", "=https", "--proto-redir", "=https", "--connect-timeout", "12",
         "--max-time", "120", "--max-filesize", "40000000",
         "--resolve", f"{host}:443:{ip}", "--user-agent", user_agent,
         "--header", f"Accept: {accept}", "--output", str(out), "--write-out",
         "%{http_code}\t%{ssl_verify_result}\t%{remote_ip}\t%{url_effective}\t%{content_type}",
         url],
        capture_output=True, text=True, check=False,
    )
    try:
        status, verify, remote, effective, content_type = result.stdout.split("\t")
    except ValueError as error:
        raise ValueError("sec_transfer_or_tls_failed_before_http") from error
    if (result.returncode != 0 or status != "200" or verify != "0"
            or remote != ip or effective != url or not out.is_file()
            or out.stat().st_size < 1000):
        raise ValueError("verified_sec_http_200_required")
    if ("json" if host == "data.sec.gov" else "html") not in content_type:
        raise ValueError("sec_content_type_mismatch")
    return {"status": 200, "tls_verify_result": 0, "remote_ip": remote,
            "url": url, "content_type": content_type,
            "bytes": out.stat().st_size, "sha256": sha256(out.read_bytes()).hexdigest()}


def _number_literal(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("unsupported_numeric_screen_value")
    if isinstance(value, float) and value.is_integer():
        return f"{int(abs(value)):,}"
    return f"{abs(value):,}"


def _check_contents(record: dict, raw: dict[str, bytes]) -> dict:
    index_html = raw["index"].decode("utf-8", "replace")
    if not all(token in index_html for token in (
            record["accession"], record["primary_document"],
            record["filing_date"], record["report_period"])):
        raise ValueError("sec_filing_index_identity_mismatch")
    rows = re.findall(r"<tr\b[^>]*>(.*?)</tr>", index_html,
                      flags=re.IGNORECASE | re.DOTALL)
    if not any(
            record["primary_document"] in row and
            re.search(r"<td\b[^>]*>\s*10-K\s*</td>", row,
                      flags=re.IGNORECASE | re.DOTALL)
            for row in rows):
        raise ValueError("sec_filing_index_form_mismatch")
    facts = json.loads(raw["companyfacts"])
    if facts.get("cik") != record["issuer_cik"]:
        raise ValueError("companyfacts_cik_mismatch")
    matching = sum(
        entry.get("accn") == record["accession"] and entry.get("form") == "10-K"
        for taxonomy in facts.get("facts", {}).values()
        for concept in taxonomy.values()
        for unit in concept.get("units", {}).values()
        for entry in unit
    )
    if not matching:
        raise ValueError("companyfacts_filing_accession_missing")
    filing = _visible_text(raw["10k"])
    if not re.search(r"\bFORM\s+10-K\b", filing, re.IGNORECASE):
        raise ValueError("original_filing_form_mismatch")
    checked = 0
    derived_checks = 0
    for period in record["periods"]:
        profile = _year_profile(period)
        for name, value in period.items():
            if name == "period_end":
                continue
            if profile == "interest" and name == "debt_principal_total":
                # The pilot defines this as the sum of filed components. It is
                # not an additional reported line item in every 10-K table.
                derived_checks += 1
                continue
            for item in value if isinstance(value, list) else [value]:
                literal = _number_literal(item)
                if not re.search(r"(?<!\d)" + re.escape(literal) + r"(?!\d)", filing):
                    raise ValueError("original_filing_numeric_literal_missing")
                checked += 1
    return {"companyfacts_accession_10k_fact_count": matching,
            "period_numeric_literals_screened": checked,
            "derived_debt_total_arithmetic_checks": derived_checks,
            "index_identity_and_form_checked": True,
            "original_10k_form_checked": True,
            "semantic_fact_review_completed": False}


def capture(*, pilot_path: Path, salt_path: Path, out_dir: Path,
            public_out: Path, user_agent: str) -> dict:
    if "@" not in user_agent or len(user_agent) < 15:
        raise ValueError("declared_contact_user_agent_required")
    private_bytes = pilot_path.read_bytes()
    pilot = json.loads(private_bytes)
    records = pilot.get("records")
    if (pilot.get("schema") != "envloop-sec-excel-two-graph-source-availability-private-v1"
            or not isinstance(records, list) or len(records) != 4
            or any(record.get("raw_source_bytes_captured") is not False
                   for record in records)):
        raise ValueError("frozen_source_availability_pilot_required")
    salt = salt_path.read_bytes()
    if len(salt) < 32:
        raise ValueError("private_commitment_salt_too_short")
    out_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(out_dir, 0o700)
    if any(out_dir.iterdir()):
        raise ValueError("fresh_private_capture_directory_required")
    resolved = {host: _global_ip(host) for host in sorted(HOSTS)}
    rows: list[dict] = []
    last_request = 0.0
    with tempfile.TemporaryDirectory(prefix="sec-raw-", dir=out_dir) as temp:
        temp_dir = Path(temp)
        for index, record in enumerate(records):
            urls = _source_urls(record)
            pending: dict[str, Path] = {}
            metadata: dict[str, dict] = {}
            for kind in KINDS:
                elapsed = time.monotonic() - last_request
                if elapsed < 1.1:
                    time.sleep(1.1 - elapsed)
                last_request = time.monotonic()
                path = temp_dir / f"source-{index:02d}-{kind}.tmp"
                metadata[kind] = _fetch(urls[kind],
                                        ip=resolved[urlparse(urls[kind]).hostname],
                                        user_agent=user_agent, out=path)
                pending[kind] = path
            checks = _check_contents(record,
                                     {kind: path.read_bytes() for kind, path in pending.items()})
            files: dict[str, str] = {}
            for kind, temp_path in pending.items():
                ext = "json" if kind == "companyfacts" else "html"
                name = f"source-{index:02d}-{kind}.{ext}"
                dest = out_dir / name
                temp_path.replace(dest)
                dest.chmod(0o600)
                files[kind] = name
            rows.append({"source_index": index, "issuer_cik": record["issuer_cik"],
                         "accession": record["accession"], "filing_date": record["filing_date"],
                         "report_period": record["report_period"], "files": files,
                         "response": metadata, "checks": checks})
    manifest = {"schema": SCHEMA, "created_utc": datetime.now(timezone.utc).isoformat(),
                "pilot_sha256": sha256(private_bytes).hexdigest(),
                "user_agent": user_agent, "sec_requests_per_second_max": 1,
                "dns_resolution": "verified HTTPS DNS-over-HTTPS address; SEC TLS hostname and chain verified",
                "sources": rows,
                "scope": "raw source identity and numeric literal screen; semantic field review and task admission remain pending"}
    manifest_path = out_dir / "capture-manifest.private.json"
    manifest_bytes = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    manifest_path.write_bytes(manifest_bytes)
    manifest_path.chmod(0o600)
    public = {"schema": PUBLIC_SCHEMA, "status": "four_official_sec_10k_sources_captured_semantic_review_pending",
              "created_utc": manifest["created_utc"], "source_candidates": len(rows),
              "verified_original_10k_html_count": len(rows),
              "verified_sec_index_html_count": len(rows),
              "verified_companyfacts_json_count": len(rows),
              "companyfacts_accession_form_match_count": len(rows),
              "index_identity_form_match_count": len(rows),
              "period_numeric_literal_checks": sum(r["checks"]["period_numeric_literals_screened"]
                                                   for r in rows),
              "derived_debt_total_arithmetic_checks": sum(
                  r["checks"]["derived_debt_total_arithmetic_checks"] for r in rows),
              "numeric_literal_missing_count": 0,
              "independent_semantic_fact_reviews": 0,
              "authored_training_workbooks": 0, "admitted_train_analogues": 0,
              "official_final_admissions": 0,
              "private_manifest_salted_commitment": hmac.new(salt, manifest_bytes, "sha256").hexdigest(),
              "private_pilot_salted_commitment": hmac.new(salt, private_bytes, "sha256").hexdigest(),
              "source_method": "official SEC HTTPS with verified TLS and declared User-Agent; <=1 SEC request/s",
              "source_docs": {
                  "api": "https://www.sec.gov/search-filings/edgar-application-programming-interfaces",
                  "filings": "https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data",
                  "fair_access": "https://www.sec.gov/about/privacy-information",
              }}
    public_out.parent.mkdir(parents=True, exist_ok=True)
    public_out.write_text(json.dumps(public, sort_keys=True, indent=2) + "\n")
    return public


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-pilot", type=Path, required=True)
    parser.add_argument("--private-salt", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    parser.add_argument("--user-agent", required=True)
    args = parser.parse_args()
    result = capture(pilot_path=args.private_pilot, salt_path=args.private_salt,
                     out_dir=args.out_dir, public_out=args.public_out,
                     user_agent=args.user_agent)
    print(json.dumps({k: result[k] for k in (
        "status", "source_candidates", "verified_original_10k_html_count",
        "verified_companyfacts_json_count", "period_numeric_literal_checks")}))


if __name__ == "__main__":
    main()
