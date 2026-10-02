"""Read-only replay of the frozen WDI transfer-expansion source selection."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path

from ppt_wdi_factory import plan as ppt
from tools.extract_wdi_country_csv_reserve_v1 import extract
from tools import capture_ppt_wdi_transfer_expansion_20260929 as capture
from tools.ppt_wdi_calibration_rebase_20260929 import anchors, packages


SCHEMA = "envloop-ppt-transfer-expansion-source-independent-audit-20260929-v1"


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def private_bytes(path: Path) -> bytes:
    require(path.is_file() and not path.is_symlink() and
            path.stat().st_mode & 0o077 == 0,
            "private_expansion_source_missing_or_unsafe")
    return path.read_bytes()


def audit(*, private_root: Path, original_v13_plan: Path,
          future_reserve_queue: Path, historical_plan_dir: Path,
          transfer_pair_root: Path, calibration_csv_root: Path,
          parent_priority: Path, old_public_receipt: Path,
          public_source_receipt: Path) -> dict:
    root = private_root.resolve()
    require(root.is_dir() and not root.is_symlink() and
            root.stat().st_mode & 0o077 == 0 and
            root.is_relative_to((Path.cwd() / "work").resolve()),
            "private_expansion_source_root_unsafe")
    priority_raw = private_bytes(root / "priority.private.json")
    priority, _ = capture.read_priority(root / "priority.private.json")
    selection_raw = private_bytes(root / "selection.private.json")
    selection = json.loads(selection_raw)
    require(selection.get("schema") == capture.SCHEMA and
            selection.get("priority_sha256") == capture.PRIORITY_SHA,
            "source_selection_not_bound_to_frozen_priority")
    attempts = selection.get("attempts")
    require(isinstance(attempts, list) and
            [entry.get("iso3") for entry in attempts] ==
            priority["eligible_priority_iso3"][:len(attempts)] and
            all(entry.get("outcome") in ("accepted", "rejected")
                for entry in attempts),
            "source_attempts_do_not_follow_frozen_priority")
    source_root = root / "official-csv"
    accepted = [entry for entry in attempts if entry["outcome"] == "accepted"]
    rejected = [entry for entry in attempts if entry["outcome"] == "rejected"]
    require(len(accepted) == 6 and len(attempts) == len(accepted) + len(rejected),
            "first_six_complete_source_rule_not_satisfied")

    anchor = anchors(original_v13_plan, future_reserve_queue,
                     historical_plan_dir, transfer_pair_root,
                     old_public_receipt)
    calibration, _ = packages(calibration_csv_root, 8)
    blocked = set().union(*anchor["sets"].values()) | {
        entry["iso3"] for entry in calibration}
    raw_parent = private_bytes(parent_priority)
    require(sha256(raw_parent).hexdigest() ==
            priority["source_priority_parent_sha256"] and
            priority["eligible_priority_iso3"] == [
                iso for iso in json.loads(raw_parent)["candidate_iso3"]
                if iso not in blocked] and
            {entry["iso3"] for entry in accepted}.isdisjoint(blocked),
            "expansion_source_split_or_parent_priority_changed")
    require({path.name for path in source_root.iterdir() if path.is_dir()} ==
            {entry["iso3"] for entry in accepted} |
            {path.name for path in transfer_pair_root.iterdir() if path.is_dir()},
            "source_pool_has_missing_or_extra_family")
    for path in transfer_pair_root.iterdir():
        if path.is_dir():
            for name in ("source-snapshot.private.json",
                         "source-provenance.private.json"):
                require(private_bytes(path / name) ==
                        private_bytes(source_root / path.name / name),
                        "frozen_pilot_source_bytes_changed")
        elif path.name.endswith("-country.private.zip"):
            require(private_bytes(path) == private_bytes(source_root / path.name),
                    "frozen_pilot_zip_changed")

    etag_count = 0
    for entry in accepted:
        iso = entry["iso3"]
        zipped = private_bytes(source_root / f"{iso}-country.private.zip")
        snapshot = private_bytes(source_root / iso /
                                 "source-snapshot.private.json")
        provenance = json.loads(private_bytes(
            source_root / iso / "source-provenance.private.json"))
        metadata = json.loads(private_bytes(
            source_root / iso / "response-metadata.private.json"))
        rebuilt, detail = extract(zipped, iso)
        url = f"https://api.worldbank.org/v2/en/country/{iso}?downloadformat=csv"
        require(rebuilt == snapshot and detail["numeric_observation_count"] == 30 and
                entry["zip_sha256"] == sha256(zipped).hexdigest() ==
                provenance["zip_sha256"] == metadata["zip_sha256"] and
                entry["snapshot_sha256"] == sha256(snapshot).hexdigest() ==
                provenance["snapshot_sha256"] and
                provenance["official_download_url"] == metadata["requested_url"] == url and
                provenance["catalog_license"] == "CC BY 4.0" and
                provenance["data_last_updated"] == detail["data_last_updated"] and
                provenance["country_name"] == detail["country_name"] and
                provenance["http_etag"] == metadata["http_etag"] and
                provenance["http_last_modified"] == metadata["http_last_modified"] and
                provenance["http_date"] == metadata["http_date"] and
                provenance["retrieved_at_utc"] == metadata["retrieved_at_utc"] and
                entry["etag_supplied"] == (metadata["http_etag"] is not None),
                "official_source_package_or_http_provenance_changed")
        etag_count += int(entry["etag_supplied"])
    for entry in rejected:
        raw = private_bytes(root / "rejected" /
                            f"{entry['iso3']}-country.private.zip")
        require(sha256(raw).hexdigest() == entry["zip_sha256"],
                "rejected_source_zip_changed")
        try:
            extract(raw, entry["iso3"])
        except ValueError as error:
            require(str(error) == entry["reason"],
                    "rejected_source_reason_did_not_replay")
        else:
            raise ValueError("complete_source_was_rejected")

    package_commitment = sha256(bytes.fromhex(priority["salt_hex"]) +
        ppt.canonical([{"iso3": item["iso3"],
                        "zip_sha256": item["zip_sha256"],
                        "snapshot_sha256": item["snapshot_sha256"]}
                       for item in accepted])).hexdigest()
    expected_public = {
        "schema": "envloop-ppt-transfer-expansion-source-public-20260929-v1",
        "status": "eight_train_only_source_families_checked_no_artifacts_yet",
        "frozen_private_priority_sha256": capture.PRIORITY_SHA,
        "source_selection_private_sha256": sha256(selection_raw).hexdigest(),
        "selected_source_package_commitment_sha256": package_commitment,
        "new_official_wdi_source_families_checked": 6,
        "pilot_source_families_retained": 2,
        "candidate_rejections_before_six_complete": len(rejected),
        "numeric_observations_reopened": 180,
        "etag_supplied_for_new_sources": etag_count,
        "rights_tier": "wdi_cc_by_4_0_facts_plus_authored_simulation",
        "source_overlap_counts": {"original_35": 0, "active_v13": 0,
                                  "historical_final": 0, "future_reserve": 0,
                                  "rebased_calibration": 0, "pilot_train": 0},
        "historical_80_calibration_overlap": "unknown_private_manifest_unavailable",
        "train_only_specs_built": 0,
        "offline_controls_passed": 0,
        "office_web_gui_admitted": 0,
        "official_final_admitted": 0,
        "model_calls": 0,
    }
    require(json.loads(public_source_receipt.read_bytes()) == expected_public,
            "published_source_receipt_does_not_replay")
    return {"schema": SCHEMA,
            "status": "six_new_official_sources_reopened_with_frozen_priority",
            "frozen_private_priority_sha256": sha256(priority_raw).hexdigest(),
            "source_selection_private_sha256": sha256(selection_raw).hexdigest(),
            "six_official_zip_and_snapshot_pairs_reopened": 6,
            "rejected_candidate_zips_replayed": len(rejected),
            "numeric_observations_reopened": 180,
            "pilot_source_packages_exactly_retained": 2,
            "etag_supplied_for_new_sources": etag_count,
            "split_source_overlap_count": 0,
            "historical_80_calibration_overlap": "unknown_private_manifest_unavailable",
            "independent_auditor_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "office_web_gui_admitted": 0,
            "official_final_admitted": 0,
            "model_calls": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--original-v13-plan", type=Path, required=True)
    parser.add_argument("--future-reserve-queue", type=Path, required=True)
    parser.add_argument("--historical-plan-dir", type=Path, required=True)
    parser.add_argument("--transfer-pair-root", type=Path, required=True)
    parser.add_argument("--calibration-csv-root", type=Path, required=True)
    parser.add_argument("--parent-priority", type=Path, required=True)
    parser.add_argument("--old-public-receipt", type=Path, required=True)
    parser.add_argument("--public-source-receipt", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    require(not args.out.exists(), "fresh_public_audit_output_required")
    result = audit(private_root=args.private_root,
                   original_v13_plan=args.original_v13_plan,
                   future_reserve_queue=args.future_reserve_queue,
                   historical_plan_dir=args.historical_plan_dir,
                   transfer_pair_root=args.transfer_pair_root,
                   calibration_csv_root=args.calibration_csv_root,
                   parent_priority=args.parent_priority,
                   old_public_receipt=args.old_public_receipt,
                   public_source_receipt=args.public_source_receipt)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write((json.dumps(result, sort_keys=True, indent=2) + "\n").encode())
    print(json.dumps({"status": result["status"],
                      "reopened": 6, "official_final_admitted": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
