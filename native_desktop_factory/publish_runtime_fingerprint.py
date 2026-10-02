"""Publish aggregate-only stability results for two neutral Desktop probes."""

from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import importlib.metadata
import json
from pathlib import Path

if __package__:
    from .budget_ledger import audit as audit_budget
else:
    from budget_ledger import audit as audit_budget


FIELDS = (
    "font_tree", "libreoffice_profile_tree", "os_release_sha256",
    "libreoffice_executable_sha256", "libreoffice_version",
    "package_manifest_sha256", "package_count",
    "fontconfig_catalog_sha256", "fontconfig_entry_count",
)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def aggregate(receipts: list[Path], work_root: Path) -> dict:
    if len(receipts) != 2 or len(set(receipts)) != 2:
        raise ValueError("Exactly two distinct runtime probe receipts required")
    raw = [path.read_bytes() for path in receipts]
    rows = [json.loads(item) for item in raw]
    if any(row.get("schema") != "cua-native-wdi-runtime-fingerprint-v1"
           or row.get("status") != "fingerprinted_and_terminated"
           or row.get("is_running_after_kill") is not False
           or row.get("provider_sandbox_info", {}).get("template_id") != "k0wmnzir0zuzye6dndlw"
           for row in rows):
        raise ValueError("Runtime probe was not completed on the pinned template")
    if rows[0]["sandbox_id_sha256"] == rows[1]["sandbox_id_sha256"]:
        raise ValueError("Two probes did not use distinct sandboxes")
    for phase in ("fresh_guest", "after_neutral_open"):
        if any(set(row.get(phase, {})) != set(FIELDS) for row in rows):
            raise ValueError("Guest probe is missing a runtime field")
    ledger = audit_budget(work_root, proposed_new_sandboxes=0,
                          proposed_lease_seconds=300,
                          max_lane_reserved_usd=Decimal("40"))
    if not ledger["within_cap"]:
        raise ValueError("Runtime probes exceeded the lane reserve cap")
    first = rows[0]["after_neutral_open"]
    agreement = {field: rows[0]["after_neutral_open"][field] ==
                 rows[1]["after_neutral_open"][field] for field in FIELDS}
    if not all(agreement[field] for field in FIELDS if field != "libreoffice_profile_tree"):
        raise ValueError("Core runtime/font/package identity differs between probes")
    return {
        "schema": "cua-native-wdi-desktop-runtime-fingerprint-public-v1",
        "checked_date": "2026-09-27",
        "scope": "Two independent neutral E2B Desktop sandboxes opened the same public training fixture; no model or final package was used.",
        "distinct_sandboxes": 2,
        "private_receipt_sha256s": [digest(item) for item in raw],
        "guest_probe_script_sha256": rows[0]["guest_probe_script_sha256"],
        "e2b_desktop_sdk_version": rows[0]["sdk_version"],
        "e2b_sdk_version_checked_locally": importlib.metadata.version("e2b"),
        "provider_template_id": rows[0]["provider_sandbox_info"]["template_id"],
        "provider_envd_version": rows[0]["provider_sandbox_info"]["envd_version"],
        "provider_resource_shape": {
            "vcpu": rows[0]["provider_sandbox_info"]["vcpu"],
            "memory_mb": rows[0]["provider_sandbox_info"]["memory_mb"],
        },
        "neutral_fixture_sha256": rows[0]["fixture_sha256"],
        "fresh_profile_absent_in_both": all(not row["fresh_guest"]["libreoffice_profile_tree"]["exists"] for row in rows),
        "after_open_agreement": agreement,
        "after_open_font_file_count": first["font_tree"]["files"],
        "after_open_font_tree_sha256": first["font_tree"]["sha256"],
        "after_open_fontconfig_entry_count": first["fontconfig_entry_count"],
        "after_open_fontconfig_catalog_sha256": first["fontconfig_catalog_sha256"],
        "after_open_package_count": first["package_count"],
        "after_open_package_manifest_sha256": first["package_manifest_sha256"],
        "after_open_os_release_sha256": first["os_release_sha256"],
        "after_open_libreoffice_version": first["libreoffice_version"],
        "after_open_libreoffice_executable_sha256": first["libreoffice_executable_sha256"],
        "after_open_profile_file_count_each": [row["after_neutral_open"]["libreoffice_profile_tree"]["files"] for row in rows],
        "after_open_profile_tree_sha256s": [row["after_neutral_open"]["libreoffice_profile_tree"]["sha256"] for row in rows],
        "provider_image_digest_exposed_by_installed_sdk": False,
        "image_and_profile_freeze_gate_passed": False,
        "full_study_official_desktop_admissions": 0,
        "full_study_official_model_results": 0,
        "probe_full_server_lease_reserve_usd_each": [row["budget_before"]["proposed_reserved_usd"] for row in rows],
        "lane_full_server_lease_reserve_usd_after_probes": ledger["past_conservative_reserved_usd"],
        "lane_cap_usd": ledger["lane_usd_cap"],
        "actual_billed_usd": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, action="append", required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Refusing to overwrite runtime stability aggregate")
    result = aggregate(args.receipt, args.work_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in (
        "distinct_sandboxes", "after_open_font_file_count",
        "after_open_profile_file_count_each", "image_and_profile_freeze_gate_passed",
        "lane_full_server_lease_reserve_usd_after_probes")}, sort_keys=True))


if __name__ == "__main__":
    main()
