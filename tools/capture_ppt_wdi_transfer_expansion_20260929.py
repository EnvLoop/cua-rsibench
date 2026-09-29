"""Capture source-only WDI expansion from a priority frozen before download.

Only the six first complete country CSV packages are accepted. Private source
identities, response metadata, and raw ZIP bytes stay under ignored work/.
The public receipt has counts and a salted package commitment only.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
from urllib.request import Request, urlopen

from native_desktop_factory import source as wdi
from ppt_wdi_factory import plan as ppt
from tools.extract_wdi_country_csv_reserve_v1 import extract
from tools.ppt_wdi_calibration_rebase_20260929 import anchors, packages


PRIORITY_SHA = "1bd5df014f4cf2e58f4a73be4c2707155effb135027302ea75f407bcb5a0e530"
SCHEMA = "envloop-ppt-transfer-expansion-source-selection-private-20260929-v1"


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def write_new(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def atomic_private(path: Path, data: dict) -> None:
    temp = path.with_name(path.name + ".new")
    write_new(temp, ppt.canonical(data))
    os.replace(temp, path)


def read_priority(path: Path) -> tuple[dict, bytes]:
    raw = path.read_bytes()
    priority = json.loads(raw)
    require(sha256(raw).hexdigest() == PRIORITY_SHA and
            priority.get("schema") ==
            "envloop-ppt-transfer-expansion-priority-private-20260929-v1" and
            priority.get("policy") ==
            "first_six_complete_official_country_csvs_in_frozen_remaining_priority" and
            priority.get("required_new_source_families") == 6 and
            priority.get("selected_iso3") == [] and
            priority.get("rejected_iso3") == [] and
            len(priority.get("eligible_priority_iso3", [])) >= 6 and
            len(set(priority["eligible_priority_iso3"])) ==
            len(priority["eligible_priority_iso3"]),
            "frozen_transfer_priority_missing_or_changed")
    return priority, raw


def verify_sources(priority: dict, *, original_plan: Path, future_queue: Path,
                   historical_dir: Path, transfer_pair: Path,
                   calibration_csv: Path, old_public_receipt: Path,
                   source_parent_priority: Path) -> None:
    a = anchors(original_plan, future_queue, historical_dir,
                transfer_pair, old_public_receipt)
    calibration, _ = packages(calibration_csv, 8)
    excluded = set().union(*a["sets"].values()) | {
        item["iso3"] for item in calibration}
    old_priority_raw = source_parent_priority.read_bytes()
    require(sha256(old_priority_raw).hexdigest() ==
            priority["source_priority_parent_sha256"],
            "parent_country_priority_changed")
    old_priority = json.loads(old_priority_raw)
    expected = [iso for iso in old_priority["candidate_iso3"]
                if iso not in excluded]
    require(expected == priority["eligible_priority_iso3"] and
            len(excluded) == priority["excluded_union_count"] and
            all(iso not in wdi.COUNTRIES for iso in expected),
            "transfer_expansion_source_boundary_changed")


def capture(raw: bytes, iso: str, headers: dict, requested_at: str,
            source_root: Path) -> dict:
    snapshot, detail = extract(raw, iso)
    source_dir = source_root / iso
    source_dir.mkdir(parents=True, mode=0o700)
    url = f"https://api.worldbank.org/v2/en/country/{iso}?downloadformat=csv"
    provenance = {
        "schema": "envloop-wdi-official-country-csv-extract-private-v1",
        "source_type": "worldbank_official_country_csv_zip",
        "official_download_url": url,
        "official_page_url": f"https://data.worldbank.org/country/{iso.lower()}",
        "zip_sha256": sha256(raw).hexdigest(),
        "snapshot_sha256": sha256(snapshot).hexdigest(),
        "download_date": requested_at[:10],
        "catalog_license": "CC BY 4.0",
        "http_etag": headers.get("etag"),
        "http_last_modified": headers.get("last-modified"),
        "http_date": headers.get("date"),
        "retrieved_at_utc": requested_at,
        **detail,
    }
    write_new(source_root / f"{iso}-country.private.zip", raw)
    write_new(source_dir / "source-snapshot.private.json", snapshot)
    write_new(source_dir / "source-provenance.private.json",
              ppt.canonical(provenance))
    write_new(source_dir / "response-metadata.private.json", ppt.canonical({
        "requested_url": url,
        "retrieved_at_utc": requested_at,
        "http_etag": headers.get("etag"),
        "http_last_modified": headers.get("last-modified"),
        "http_date": headers.get("date"),
        "content_type": headers.get("content-type"),
        "zip_sha256": sha256(raw).hexdigest(),
    }))
    return {"iso3": iso, "zip_sha256": sha256(raw).hexdigest(),
            "snapshot_sha256": sha256(snapshot).hexdigest(),
            "etag_supplied": headers.get("etag") is not None,
            "numeric_observations": detail["numeric_observation_count"]}


def run(args: argparse.Namespace) -> dict:
    root = args.private_root.resolve()
    require(root.is_relative_to((Path.cwd() / "work").resolve()) and
            root.is_dir() and root.stat().st_mode & 0o077 == 0,
            "private_source_root_unsafe")
    priority, priority_raw = read_priority(root / "priority.private.json")
    verify_sources(priority, original_plan=args.original_v13_plan,
                   future_queue=args.future_reserve_queue,
                   historical_dir=args.historical_plan_dir,
                   transfer_pair=args.transfer_pair_root,
                   calibration_csv=args.calibration_csv_root,
                   old_public_receipt=args.old_public_receipt,
                   source_parent_priority=args.source_parent_priority)
    selection_path = root / "selection.private.json"
    selection = (json.loads(selection_path.read_bytes())
                 if selection_path.exists() else {
                     "schema": SCHEMA,
                     "priority_sha256": sha256(priority_raw).hexdigest(),
                     "attempts": [],
                 })
    attempts = selection["attempts"]
    ordered = priority["eligible_priority_iso3"]
    require(selection.get("schema") == SCHEMA and
            selection.get("priority_sha256") == PRIORITY_SHA and
            [item["iso3"] for item in attempts] == ordered[:len(attempts)],
            "selection_not_frozen_priority_prefix")
    source_root = root / "official-csv"
    if not source_root.exists():
        source_root.mkdir(mode=0o700)
        for source in args.transfer_pair_root.iterdir():
            if source.is_dir():
                shutil.copytree(source, source_root / source.name)
            elif source.name.endswith("-country.private.zip"):
                shutil.copyfile(source, source_root / source.name)
                (source_root / source.name).chmod(0o600)
        require(len([p for p in source_root.iterdir() if p.is_dir()]) == 2,
                "pilot_transfer_pair_copy_incomplete")
    selected = [item for item in attempts if item["outcome"] == "accepted"]
    for iso in ordered[len(attempts):]:
        if len(selected) == 6:
            break
        url = f"https://api.worldbank.org/v2/en/country/{iso}?downloadformat=csv"
        request = Request(url, headers={"User-Agent": "EnvLoop-Research-WDI-Capture/1.0"})
        with urlopen(request, timeout=90) as response:
            require(response.status == 200 and
                    response.url == url and
                    len(response.read(0)) == 0,
                    "official_wdi_response_not_direct_200")
            headers = {key.lower(): value for key, value in response.headers.items()}
            raw = response.read(10_000_001)
        require(len(raw) < 10_000_000, "official_wdi_zip_too_large")
        timestamp = datetime.now(timezone.utc).isoformat()
        try:
            entry = {"outcome": "accepted", **capture(raw, iso, headers,
                                                        timestamp, source_root)}
        except ValueError as error:
            rejected_dir = root / "rejected"
            rejected_dir.mkdir(exist_ok=True, mode=0o700)
            write_new(rejected_dir / f"{iso}-country.private.zip", raw)
            entry = {"iso3": iso, "outcome": "rejected",
                     "reason": str(error), "zip_sha256": sha256(raw).hexdigest(),
                     "retrieved_at_utc": timestamp,
                     "etag_supplied": headers.get("etag") is not None}
        attempts.append(entry)
        atomic_private(selection_path, selection)
        if entry["outcome"] == "accepted":
            selected.append(entry)
    require(len(selected) == 6, "six_complete_official_wdi_packages_not_yet_captured")
    require(len([path for path in source_root.iterdir() if path.is_dir()]) == 8,
            "eight_source_families_not_in_combined_pool")
    selected_order = [entry["iso3"] for entry in selected]
    require(selected_order == [item["iso3"] for item in attempts
                               if item["outcome"] == "accepted"][:6],
            "selected_source_order_changed")
    package_raw = ppt.canonical([{
        "iso3": item["iso3"],
        "zip_sha256": item["zip_sha256"],
        "snapshot_sha256": item["snapshot_sha256"],
    } for item in selected])
    commitment = sha256(bytes.fromhex(priority["salt_hex"]) + package_raw).hexdigest()
    public = {
        "schema": "envloop-ppt-transfer-expansion-source-public-20260929-v1",
        "status": "eight_train_only_source_families_checked_no_artifacts_yet",
        "frozen_private_priority_sha256": PRIORITY_SHA,
        "source_selection_private_sha256": sha256(selection_path.read_bytes()).hexdigest(),
        "selected_source_package_commitment_sha256": commitment,
        "new_official_wdi_source_families_checked": 6,
        "pilot_source_families_retained": 2,
        "candidate_rejections_before_six_complete": len(attempts) - 6,
        "numeric_observations_reopened": 6 * 30,
        "etag_supplied_for_new_sources": sum(item["etag_supplied"] for item in selected),
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
    require(not args.public_out.exists(), "fresh_public_source_receipt_required")
    args.public_out.parent.mkdir(parents=True, exist_ok=True)
    args.public_out.write_text(json.dumps(public, sort_keys=True, indent=2) + "\n")
    return public


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--original-v13-plan", type=Path, required=True)
    parser.add_argument("--future-reserve-queue", type=Path, required=True)
    parser.add_argument("--historical-plan-dir", type=Path, required=True)
    parser.add_argument("--transfer-pair-root", type=Path, required=True)
    parser.add_argument("--calibration-csv-root", type=Path, required=True)
    parser.add_argument("--old-public-receipt", type=Path, required=True)
    parser.add_argument("--source-parent-priority", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    result = run(args)
    print(json.dumps({key: result[key] for key in (
        "status", "new_official_wdi_source_families_checked",
        "candidate_rejections_before_six_complete", "etag_supplied_for_new_sources",
        "official_final_admitted")}, sort_keys=True))


if __name__ == "__main__":
    main()
