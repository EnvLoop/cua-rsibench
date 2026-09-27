"""Fail-closed aggregate for independently measured Desktop guest contents."""

from __future__ import annotations

from decimal import Decimal
import argparse
import gzip
import hashlib
import json
from pathlib import Path

if __package__:
    from .budget_ledger import audit as audit_budget
else:
    from budget_ledger import audit as audit_budget


PERSONALIZED = frozenset({
    "/etc/ssl/certs/ca-certificates.crt",
    "/usr/local/share/ca-certificates/e2b-ca.crt",
})


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_probe(path: Path) -> tuple[dict, bytes, dict[str, list]]:
    raw = (path / "receipt.json").read_bytes()
    row = json.loads(raw)
    if (row.get("schema") != "cua-native-wdi-runtime-fingerprint-v1"
            or row.get("status") != "fingerprinted_and_terminated"
            or row.get("is_running_after_kill") is not False):
        raise ValueError("Guest-content probe did not finish with teardown")
    manifest_gzip = (path / "guest-content-files.jsonl.gz").read_bytes()
    if digest(manifest_gzip) != row.get("private_guest_content_files_gzip_sha256"):
        raise ValueError("Private guest file manifest hash changed")
    manifest_raw = gzip.decompress(manifest_gzip)
    if digest(manifest_raw) != row["fresh_guest_content_manifest"]["content_tree_sha256"]:
        raise ValueError("Guest content summary is not bound to file rows")
    files = {}
    for line in manifest_raw.splitlines():
        entry = json.loads(line)
        if entry[0] in files:
            raise ValueError("Duplicate guest-content path")
        files[entry[0]] = entry
    if len(files) != sum(row["fresh_guest_content_manifest"]["counts"].values()):
        raise ValueError("Guest-content file count mismatch")
    return row, raw, files


def aggregate(raw_probe_dirs: list[Path], static_probe_dirs: list[Path],
              work_root: Path) -> dict:
    if (len(raw_probe_dirs) != 2 or len(static_probe_dirs) != 2
            or len({str(p.resolve()) for p in raw_probe_dirs + static_probe_dirs}) != 4):
        raise ValueError("Need four distinct completed guest-content probes")
    raw = [read_probe(path) for path in raw_probe_dirs]
    static = [read_probe(path) for path in static_probe_dirs]
    if len({item[0]["sandbox_id_sha256"] for item in raw + static}) != 4:
        raise ValueError("Guest-content probes reused a sandbox")
    provider_shapes = {json.dumps(item[0]["provider_sandbox_info"], sort_keys=True)
                       for item in raw + static}
    if len(provider_shapes) != 1 or len({item[0]["fixture_sha256"] for item in raw + static}) != 1:
        raise ValueError("Neutral guest probes used different templates, shapes, or fixtures")
    if raw[0][0]["guest_content_probe_script_sha256"] != raw[1][0]["guest_content_probe_script_sha256"]:
        raise ValueError("Unrestricted guest probes used different scripts")
    before_a, before_b = raw[0][2], raw[1][2]
    if set(before_a) != set(before_b):
        raise ValueError("Unexcluded root filesystem path sets differ")
    changed = frozenset(path for path in before_a if before_a[path] != before_b[path])
    if changed != PERSONALIZED:
        raise ValueError("Root filesystem drift exceeds the two E2B CA files")
    after_a, after_b = static[0][0]["fresh_guest_content_manifest"], static[1][0]["fresh_guest_content_manifest"]
    if (after_a["content_tree_sha256"] != after_b["content_tree_sha256"]
            or static[0][2] != static[1][2]
            or after_a["counts"] != after_b["counts"]
            or after_a["kernel"] != after_b["kernel"]
            or static[0][0]["guest_content_probe_script_sha256"] !=
            static[1][0]["guest_content_probe_script_sha256"]):
        raise ValueError("Static guest-content identities differ")
    required_exclusions = frozenset({
        "/etc/hostname", "/etc/hosts", "/etc/resolv.conf",
        "/etc/machine-id", "/etc/mtab",
    }) | PERSONALIZED
    if (frozenset(after_a["excluded_paths"]) != required_exclusions
            or frozenset(after_b["excluded_paths"]) != required_exclusions):
        raise ValueError("Guest-content probe exclusions are not the audited seven paths")
    if (len(after_a["personalized_ca_files"]) != 2
            or len(after_b["personalized_ca_files"]) != 2
            or not all(not item[0]["fresh_guest"]["libreoffice_profile_tree"]["exists"]
                       for item in static)):
        raise ValueError("CA split or fresh-profile state is incomplete")
    for a, b in zip(after_a["personalized_ca_files"], after_b["personalized_ca_files"]):
        if a["path"] != b["path"] or a["path"] not in PERSONALIZED or a["sha256"] == b["sha256"]:
            raise ValueError("Personalized E2B CA behavior differs from prior probes")
    ledger = audit_budget(work_root, proposed_new_sandboxes=0,
                          proposed_lease_seconds=300,
                          max_lane_reserved_usd=Decimal("40"))
    if not ledger["within_cap"]:
        raise ValueError("Native Desktop lane reserve exceeded cap")
    return {
        "schema": "cua-native-wdi-guest-content-identity-public-v1",
        "checked_date": "2026-09-27",
        "scope": "Four distinct neutral E2B Desktop sandboxes; no model or final package. Two unrestricted manifests isolated dynamic CA files, and two new manifests proved exact static-content equality after excluding only those files plus five sandbox network/identity paths.",
        "distinct_guest_probes": 4,
        "private_receipt_sha256s": [digest(item[1]) for item in raw + static],
        "private_compressed_manifest_sha256s": [item[0]["private_guest_content_files_gzip_sha256"] for item in raw + static],
        "guest_content_probe_script_sha256": static[0][0]["guest_content_probe_script_sha256"],
        "provider_template_id": static[0][0]["provider_sandbox_info"]["template_id"],
        "provider_envd_version": static[0][0]["provider_sandbox_info"]["envd_version"],
        "provider_shape": {key: static[0][0]["provider_sandbox_info"][key] for key in ("vcpu", "memory_mb")},
        "unexcluded_guest_entry_count": len(before_a),
        "unexcluded_changed_entry_count": len(changed),
        "unexcluded_changed_paths": sorted(changed),
        "static_content_entry_count": len(static[0][2]),
        "static_regular_file_bytes_hashed": after_a["regular_file_bytes"],
        "static_content_sha256": after_a["content_tree_sha256"],
        "static_content_counts": after_a["counts"],
        "static_content_excluded_paths": sorted(required_exclusions),
        "kernel_identity": after_a["kernel"],
        "personalized_ca_byte_sizes_equal": [a["bytes"] == b["bytes"] for a, b in zip(
            after_a["personalized_ca_files"], after_b["personalized_ca_files"])],
        "fresh_libreoffice_profile_absent_in_both_static_probes": all(
            not item[0]["fresh_guest"]["libreoffice_profile_tree"]["exists"] for item in static),
        "scoped_guest_content_identity_passed": True,
        "provider_image_digest_available": False,
        "full_six_cell_pre_campaign_gate_passed": False,
        "official_desktop_final_admissions": 0,
        "official_desktop_model_results": 0,
        "native_lane_full_server_lease_reserve_usd": ledger["past_conservative_reserved_usd"],
        "native_lane_cap_usd": ledger["lane_usd_cap"],
        "actual_billed_usd": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-probe-dir", type=Path, action="append", required=True)
    parser.add_argument("--static-probe-dir", type=Path, action="append", required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Refusing to overwrite guest-content identity aggregate")
    result = aggregate(args.raw_probe_dir, args.static_probe_dir, args.work_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in (
        "distinct_guest_probes", "unexcluded_changed_entry_count",
        "scoped_guest_content_identity_passed", "official_desktop_final_admissions",
        "native_lane_full_server_lease_reserve_usd")}, sort_keys=True))


if __name__ == "__main__":
    main()
