"""Independently re-open private SEC bytes and audit a field-limited receipt."""

from __future__ import annotations

import argparse
from hashlib import sha256
import hmac
import ipaddress
import json
from pathlib import Path

from tools.sec_excel_transfer_official_raw_capture_v1 import (
    KINDS, PUBLIC_SCHEMA, SCHEMA, _check_contents, _source_urls,
)


AUDIT_SCHEMA = "envloop-sec-transfer-official-raw-capture-audit-public-v1"


def audit(*, pilot_path: Path, availability_path: Path, salt_path: Path,
          capture_dir: Path, receipt_path: Path) -> dict:
    pilot_bytes = pilot_path.read_bytes()
    pilot = json.loads(pilot_bytes)
    salt = salt_path.read_bytes()
    availability = json.loads(availability_path.read_text())
    manifest_path = capture_dir / "capture-manifest.private.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    receipt = json.loads(receipt_path.read_text())
    errors: set[str] = set()
    if len(salt) < 32 or manifest.get("schema") != SCHEMA or receipt.get("schema") != PUBLIC_SCHEMA:
        errors.add("capture_schema_or_salt_invalid")
    if (availability.get("private_source_availability_salted_commitment")
            != hmac.new(salt, pilot_bytes, "sha256").hexdigest()
            or availability.get("original_registry_sha256")
            != pilot.get("original_140_registry_sha256")):
        errors.add("frozen_source_availability_binding_mismatch")
    if (manifest.get("pilot_sha256") != sha256(pilot_bytes).hexdigest()
            or receipt.get("private_pilot_salted_commitment")
            != hmac.new(salt, pilot_bytes, "sha256").hexdigest()
            or receipt.get("private_manifest_salted_commitment")
            != hmac.new(salt, manifest_bytes, "sha256").hexdigest()):
        errors.add("capture_commitment_mismatch")
    if (capture_dir.stat().st_mode & 0o077
            or manifest_path.stat().st_mode & 0o077):
        errors.add("private_capture_permissions_too_open")
    source_rows = manifest.get("sources", [])
    pilot_rows = pilot.get("records", [])
    if len(source_rows) != 4 or len(pilot_rows) != 4:
        errors.add("four_source_rows_required")
    file_count = 0
    literal_count = 0
    derived_count = 0
    accession_matches = 0
    for index, (source, candidate) in enumerate(zip(source_rows, pilot_rows)):
        if (source.get("source_index") != index
                or source.get("issuer_cik") != candidate.get("issuer_cik")
                or source.get("accession") != candidate.get("accession")):
            errors.add("capture_source_identity_mismatch")
            continue
        try:
            urls = _source_urls(candidate)
            raw: dict[str, bytes] = {}
            for kind in KINDS:
                name = source["files"][kind]
                if Path(name).name != name:
                    raise ValueError("unsafe_private_source_filename")
                path = capture_dir / name
                if (path.is_symlink() or not path.is_file()
                        or path.stat().st_mode & 0o077):
                    raise ValueError("private_source_file_missing_or_open")
                raw[kind] = path.read_bytes()
                metadata = source["response"][kind]
                remote_ip = ipaddress.ip_address(metadata["remote_ip"])
                if (metadata["status"] != 200 or metadata["tls_verify_result"] != 0
                        or metadata["url"] != urls[kind] or not remote_ip.is_global
                        or metadata["bytes"] != len(raw[kind])
                        or metadata["sha256"] != sha256(raw[kind]).hexdigest()):
                    raise ValueError("official_source_response_or_hash_mismatch")
                file_count += 1
            checks = _check_contents(candidate, raw)
            if checks != source.get("checks"):
                raise ValueError("source_content_check_mismatch")
            literal_count += checks["period_numeric_literals_screened"]
            derived_count += checks["derived_debt_total_arithmetic_checks"]
            accession_matches += 1
        except (KeyError, ValueError, TypeError) as error:
            errors.add(str(error) if isinstance(error, ValueError)
                       else "malformed_private_source_capture")
    if (receipt.get("verified_original_10k_html_count") != accession_matches
            or receipt.get("verified_companyfacts_json_count") != accession_matches
            or receipt.get("verified_sec_index_html_count") != accession_matches
            or receipt.get("period_numeric_literal_checks") != literal_count
            or receipt.get("derived_debt_total_arithmetic_checks") != derived_count):
        errors.add("public_aggregate_count_mismatch")
    public_serialized = receipt_path.read_text()
    if any(str(row.get("accession")) in public_serialized
           or str(row.get("issuer_cik")) in public_serialized
           or str(row.get("issuer_name")) in public_serialized
           for row in pilot_rows):
        errors.add("public_source_identity_leak")
    if any(receipt.get(key) != 0 for key in (
            "independent_semantic_fact_reviews", "authored_training_workbooks",
            "admitted_train_analogues", "official_final_admissions")):
        errors.add("unsupported_admission_claim")
    return {
        "schema": AUDIT_SCHEMA,
        "status": "verified_raw_source_capture_semantic_review_pending" if not errors else "blocked",
        "private_capture_files_rehashed": file_count,
        "four_source_identity_checks": accession_matches,
        "numeric_literal_checks_replayed": literal_count,
        "derived_debt_total_checks_replayed": derived_count,
        "source_availability_commitment_verified":
            "frozen_source_availability_binding_mismatch" not in errors,
        "private_capture_commitment_verified": "capture_commitment_mismatch" not in errors,
        "public_identity_leak_count": int("public_source_identity_leak" in errors),
        "independent_semantic_fact_reviews": 0,
        "authored_training_workbooks": 0,
        "official_final_admissions": 0,
        "errors": sorted(errors),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-pilot", type=Path, required=True)
    parser.add_argument("--source-availability-public", type=Path, required=True)
    parser.add_argument("--private-salt", type=Path, required=True)
    parser.add_argument("--capture-dir", type=Path, required=True)
    parser.add_argument("--capture-public", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    result = audit(pilot_path=args.private_pilot,
                   availability_path=args.source_availability_public,
                   salt_path=args.private_salt, capture_dir=args.capture_dir,
                   receipt_path=args.capture_public)
    args.public_out.parent.mkdir(parents=True, exist_ok=True)
    args.public_out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    if result["errors"]:
        raise SystemExit("SEC raw source capture audit failed: " + ", ".join(result["errors"]))


if __name__ == "__main__":
    main()
