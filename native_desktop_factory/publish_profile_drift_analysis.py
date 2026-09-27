"""Publish a private, fail-closed LibreOffice profile difference analysis."""

from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path

if __package__:
    from .budget_ledger import audit as audit_budget
    from . import profile_canonical
else:
    from budget_ledger import audit as audit_budget
    import profile_canonical


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def aggregate(directories: list[Path], work_root: Path) -> dict:
    if len(directories) != 2 or directories[0].resolve() == directories[1].resolve():
        raise ValueError("Exactly two different detailed runtime probes required")
    receipts_raw = [(path / "receipt.json").read_bytes() for path in directories]
    receipts = [json.loads(raw) for raw in receipts_raw]
    registries = [(path / "registrymodifications.xcu").read_bytes() for path in directories]
    if any(row.get("schema") != "cua-native-wdi-runtime-fingerprint-v1"
           or row.get("status") != "fingerprinted_and_terminated"
           or row.get("is_running_after_kill") is not False
           or len(row.get("after_open_profile_files", [])) != 27
           for row in receipts):
        raise ValueError("Detailed runtime receipts are incomplete")
    if receipts[0]["sandbox_id_sha256"] == receipts[1]["sandbox_id_sha256"]:
        raise ValueError("Profile probes did not use distinct sandboxes")
    maps = []
    guest_tree_matches_later_manifest = []
    for row, registry in zip(receipts, registries):
        files = row["after_open_profile_files"]
        pairs = [(entry["path"], entry["sha256"]) for entry in files]
        if len({path for path, _ in pairs}) != len(pairs):
            raise ValueError("Duplicate profile path")
        raw_tree = digest(json.dumps(sorted(pairs), sort_keys=True,
                                     separators=(",", ":")).encode())
        if digest(registry) != row["private_registrymodifications_sha256"]:
            raise ValueError("Captured registry bytes do not match the receipt")
        guest_tree_matches_later_manifest.append(
            raw_tree == row["after_neutral_open"]["libreoffice_profile_tree"]["sha256"])
        maps.append(dict(pairs))
    if set(maps[0]) != set(maps[1]):
        raise ValueError("Profile file sets differ")
    differing_files = [path for path in sorted(maps[0]) if maps[0][path] != maps[1][path]]
    if differing_files != ["registrymodifications.xcu"]:
        raise ValueError("Profile drift is not confined to the captured registry")
    if registries[0] == registries[1]:
        raise ValueError("Raw registry did not differ")
    canonical = [profile_canonical.canonical_registry(raw) for raw in registries]
    if canonical[0] != canonical[1]:
        raise ValueError("Registry differs beyond two allowed numeric timestamp fields")
    canonical_trees = [profile_canonical.canonical_profile_tree(
        row["after_open_profile_files"], raw)
        for row, raw in zip(receipts, registries)]
    if canonical_trees[0] != canonical_trees[1]:
        raise ValueError("Canonicalized profile trees still differ")
    ledger = audit_budget(work_root, proposed_new_sandboxes=0,
                          proposed_lease_seconds=300,
                          max_lane_reserved_usd=Decimal("40"))
    if not ledger["within_cap"]:
        raise ValueError("Profile comparison exceeded native lane reserve")
    return {
        "schema": "cua-native-wdi-profile-drift-analysis-public-v1",
        "checked_date": "2026-09-27",
        "scope": "Two additional neutral, distinct E2B Desktop sandboxes opened one public training workbook; no model or final package was used.",
        "private_receipt_sha256s": [digest(raw) for raw in receipts_raw],
        "private_registry_sha256s": [digest(raw) for raw in registries],
        "canonicalizer_sha256": digest(Path(profile_canonical.__file__).read_bytes()),
        "distinct_sandboxes": 2,
        "profile_file_count_each": [len(row["after_open_profile_files"]) for row in receipts],
        "raw_profile_tree_sha256s": [row["after_neutral_open"]["libreoffice_profile_tree"]["sha256"] for row in receipts],
        "guest_tree_matches_later_file_manifest_each": guest_tree_matches_later_manifest,
        "differing_profile_file_count": len(differing_files),
        "differing_profile_file_names": differing_files,
        "differing_registry_property_names": [name.decode() for name in profile_canonical.VOLATILE_FIELDS],
        "canonical_registry_sha256": digest(canonical[0]),
        "canonical_profile_tree_sha256": canonical_trees[0],
        "canonical_profile_stable_across_two_probes": True,
        "raw_profile_stable_across_two_probes": False,
        "provider_image_digest_available": False,
        "full_image_profile_freeze_gate_passed": False,
        "official_full_study_desktop_admissions": 0,
        "official_full_study_model_results": 0,
        "native_lane_full_lease_reserve_usd_after_all_probes": ledger["past_conservative_reserved_usd"],
        "native_lane_cap_usd": ledger["lane_usd_cap"],
        "actual_billed_usd": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe-dir", type=Path, action="append", required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Refusing to overwrite public profile analysis")
    report = aggregate(args.probe_dir, args.work_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in (
        "distinct_sandboxes", "differing_profile_file_names",
        "canonical_profile_stable_across_two_probes",
        "full_image_profile_freeze_gate_passed",
        "native_lane_full_lease_reserve_usd_after_all_probes")}, sort_keys=True))


if __name__ == "__main__":
    main()
