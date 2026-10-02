"""Freeze a new, source-only PowerPoint calibration boundary dated 2026-09-29.

The September 27 aggregate 80-case receipt is historical. Its private seed and
manifest are unavailable, and this tool never attempts to reproduce their SHA.
All country identities, source bytes, task specs, seed, and gold stay under
ignored evaluator storage. The public receipt exposes only aggregate counts and
commitments. No deck or Office GUI work is performed here.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import json
import os
from pathlib import Path
import re
import secrets
from urllib.parse import urlparse

from native_desktop_factory import source as wdi
from ppt_wdi_factory import plan as ppt
from tools.build_ppt_wdi_train_calibration_80_v1 import (
    PLAN_SHA, QUEUE_SHA, workflow_coordinates,
)
from tools.build_ppt_wdi_reserve_replacement_v1 import facts_from_official_response
from tools.extract_wdi_country_csv_reserve_v1 import extract, write_new


DATE = "2026-09-29"
SCHEMA = "envloop-ppt-wdi-calibration-source-boundary-private-20260929-v1"
SPEC_SCHEMA = "envloop-ppt-wdi-calibration-spec-plan-private-20260929-v1"
PUBLIC_SCHEMA = "envloop-ppt-wdi-calibration-source-boundary-public-20260929-v1"
OLD_PUBLIC_SCHEMA = "envloop-ppt-wdi-train-calibration-80-public-v1"
OLD_PRIVATE_MANIFEST_SHA = "bb5baafdded0384a3069be5d22707269e191744a995f83b2512a58b9afdda2c7"
SOURCE_SELECTION_SCHEMA = "envloop-ppt-calibration-source-selection-private-20260929-v1"
SOURCE_PRIORITY_SCHEMA = "envloop-ppt-calibration-country-priority-private-20260929-v1"
REQUIRED_SOURCE_FAMILIES = 8
REQUIRED_HISTORICAL_REVISIONS = 12
HISTORICAL_PLAN_INVENTORY_SHA = "ffa80d5d7d695421e12008a88c2691e6cc25f9217aac0f15b909d8948432332c"
ISO3 = re.compile(r"^[A-Z]{3}$")


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def read_json(path: Path) -> tuple[dict, bytes]:
    raw = path.read_bytes()
    data = json.loads(raw)
    require(isinstance(data, dict), "private_json_object_required")
    return data, raw


def source_package(root: Path, iso: str) -> tuple[dict, dict]:
    """Reopen exact official ZIP, extracted snapshot, and private provenance."""
    require(ISO3.fullmatch(iso) is not None, "invalid_private_source_iso3")
    zip_raw = (root / f"{iso}-country.private.zip").read_bytes()
    snapshot_raw = (root / iso / "source-snapshot.private.json").read_bytes()
    provenance_raw = (root / iso / "source-provenance.private.json").read_bytes()
    provenance = json.loads(provenance_raw)
    extracted, detail = extract(zip_raw, iso)
    require(extracted == snapshot_raw and
            provenance.get("schema") ==
            "envloop-wdi-official-country-csv-extract-private-v1" and
            provenance.get("source_type") ==
            "worldbank_official_country_csv_zip" and
            provenance.get("country_iso") == iso and
            provenance.get("country_name") == detail["country_name"] and
            provenance.get("catalog_license") == "CC BY 4.0" and
            provenance.get("official_download_url") ==
            f"https://api.worldbank.org/v2/en/country/{iso}?downloadformat=csv" and
            urlparse(provenance.get("official_page_url", "")).hostname ==
            "data.worldbank.org" and
            provenance.get("zip_sha256") == ppt.sha(zip_raw) and
            provenance.get("snapshot_sha256") == ppt.sha(snapshot_raw) and
            provenance.get("data_last_updated") == detail["data_last_updated"] and
            detail["numeric_observation_count"] == 30,
            "official_wdi_country_source_or_provenance_changed")
    date.fromisoformat(provenance["download_date"])
    facts = facts_from_official_response(snapshot_raw)
    require(facts["iso3"] == iso and facts["name"] == detail["country_name"],
            "official_wdi_country_identity_changed")
    return ({"iso3": iso, "zip_sha256": ppt.sha(zip_raw),
             "snapshot_sha256": ppt.sha(snapshot_raw),
             "provenance_sha256": ppt.sha(provenance_raw),
             "download_date": provenance["download_date"],
             "data_last_updated": detail["data_last_updated"],
             "numeric_observation_count": 30}, facts)


def packages(root: Path, expected_count: int) -> tuple[list[dict], dict[str, dict]]:
    directories = sorted(path for path in root.iterdir() if path.is_dir())
    require(len(directories) == expected_count and
            len({path.name for path in directories}) == expected_count,
            "official_country_package_count_changed")
    source_rows, facts = [], {}
    for directory in directories:
        source, value = source_package(root, directory.name)
        source_rows.append(source)
        facts[directory.name] = value
    return source_rows, facts


def anchors(original_plan: Path, future_queue: Path,
            historical_dir: Path, transfer_root: Path,
            old_public_receipt: Path) -> dict:
    """Return only source sets and commitments, not held-out task rows."""
    original = wdi.load()  # Rechecks the exact pinned 35-country WDI bytes.
    require(len(original["names"]) == 35, "pinned_original_country_count_changed")
    active, active_raw = read_json(original_plan)
    require(ppt.sha(active_raw) == PLAN_SHA and active.get("schema") == ppt.SCHEMA and
            set(active.get("sets", {})) == {"train", "selection", "final_candidate"} and
            {name: len(active["sets"][name]) for name in active["sets"]} ==
            {"train": 20, "selection": 20, "final_candidate": 100},
            "active_v13_plan_bytes_or_split_changed")
    queue, queue_raw = read_json(future_queue)
    require(ppt.sha(queue_raw) == QUEUE_SHA and
            queue.get("schema") == "envloop-ppt-future-reserve-queue-private-v1" and
            queue.get("current_plan_sha256") == PLAN_SHA and
            len(queue.get("ordered_future_country_iso", [])) == 10 and
            len(set(queue["ordered_future_country_iso"])) == 10,
            "future_reserve_queue_bytes_or_membership_changed")
    paths = sorted(historical_dir.glob("ppt-revised-*/candidate-plan.private.json"))
    require(len(paths) == REQUIRED_HISTORICAL_REVISIONS,
            "twelve_historical_final_plan_revisions_required")
    historical, history_hashes = set(), []
    for path in paths:
        value, raw = read_json(path)
        require(value.get("schema") == ppt.SCHEMA and
                len(value.get("sets", {}).get("final_candidate", [])) == 100,
                "historical_final_plan_schema_or_count_changed")
        historical.update(row["source_group"]
                          for row in value["sets"]["final_candidate"])
        history_hashes.append({"revision": path.parent.name,
                               "plan_sha256": ppt.sha(raw)})
    require(ppt.sha(ppt.canonical(history_hashes)) == HISTORICAL_PLAN_INVENTORY_SHA,
            "historical_final_plan_inventory_bytes_changed")
    transfer_sources, _ = packages(transfer_root, 2)
    transfer = {row["iso3"] for row in transfer_sources}
    require(transfer.isdisjoint(wdi.COUNTRIES),
            "new_transfer_source_hits_original_35")
    old_public, old_public_raw = read_json(old_public_receipt)
    require(old_public.get("schema") == OLD_PUBLIC_SCHEMA and
            old_public.get("calibration_analogue_tasks") == 80 and
            old_public.get("private_manifest_sha256") == OLD_PRIVATE_MANIFEST_SHA,
            "historical_public_80_case_receipt_changed")
    sets = {"original_35": set(wdi.COUNTRIES),
            "active_v13_train": {row["source_group"] for row in active["sets"]["train"]},
            "active_v13_selection": {row["source_group"] for row in active["sets"]["selection"]},
            "active_v13_final": {row["source_group"] for row in active["sets"]["final_candidate"]},
            "future_reserve": set(queue["ordered_future_country_iso"]),
            "historical_final": historical,
            "new_transfer_pair": transfer}
    require(all(all(isinstance(iso, str) and ISO3.fullmatch(iso) for iso in source_set)
                for source_set in sets.values()),
            "source_registry_contains_invalid_iso3")
    return {"sets": sets, "historical_plan_hashes": history_hashes,
            "transfer_source_packages": transfer_sources,
            "old_public_receipt_sha256": ppt.sha(old_public_raw)}


def overlap_counts(proposed: set[str], source_sets: dict[str, set[str]]) -> dict[str, int]:
    require(len(proposed) == REQUIRED_SOURCE_FAMILIES and
            all(ISO3.fullmatch(iso) for iso in proposed),
            "eight_distinct_calibration_source_families_required")
    expected = {"original_35", "active_v13_train", "active_v13_selection",
                "active_v13_final", "future_reserve", "historical_final",
                "new_transfer_pair"}
    require(set(source_sets) == expected, "incomplete_source_overlap_inventory")
    counts = {name: len(proposed & source_sets[name]) for name in sorted(expected)}
    require(all(count == 0 for count in counts.values()),
            "calibration_source_overlaps_frozen_study_or_new_transfer")
    return counts


def selection_audit(priority_path: Path, selection_path: Path,
                    source_iso: set[str]) -> tuple[str, str, int]:
    priority, priority_raw = read_json(priority_path)
    selection, selection_raw = read_json(selection_path)
    ordered = priority.get("candidate_iso3")
    chosen = selection.get("selected_iso3")
    rejected = selection.get("rejected_candidates")
    require(priority.get("schema") == SOURCE_PRIORITY_SCHEMA and
            priority.get("policy") ==
            "fixed_priority_first_eight_complete_csv_outside_frozen_source_unions" and
            isinstance(ordered, list) and len(ordered) == len(set(ordered)) and
            all(isinstance(iso, str) and ISO3.fullmatch(iso) for iso in ordered) and
            selection.get("schema") == SOURCE_SELECTION_SCHEMA and
            selection.get("candidate_priority_sha256") == ppt.sha(priority_raw) and
            selection.get("required_count") == REQUIRED_SOURCE_FAMILIES and
            isinstance(chosen, list) and len(chosen) == REQUIRED_SOURCE_FAMILIES and
            set(chosen) == source_iso and isinstance(rejected, list),
            "private_source_priority_or_selection_changed")
    rejects = [item.get("iso3") for item in rejected]
    require(len(rejects) == len(set(rejects)) and
            all(isinstance(iso, str) and ISO3.fullmatch(iso) for iso in rejects) and
            not set(rejects) & set(chosen) and
            set(chosen) <= set(ordered) and
            set(rejects) <= set(ordered) and
            set(ordered[:ordered.index(chosen[-1]) + 1]) ==
            set(chosen) | set(rejects) and
            chosen == [iso for iso in ordered if iso not in set(rejects)][:REQUIRED_SOURCE_FAMILIES],
            "source_selection_does_not_follow_frozen_priority")
    return ppt.sha(priority_raw), ppt.sha(selection_raw), len(rejected)


def source_manifest(seed: bytes, salt: bytes, source_root: Path,
                    priority_path: Path, selection_path: Path,
                    original_plan: Path, future_queue: Path,
                    historical_dir: Path, transfer_root: Path,
                    old_public_receipt: Path) -> tuple[dict, dict[str, dict]]:
    require(len(seed) == len(salt) == 32, "private_seed_and_commitment_salt_must_be_32_bytes")
    baseline = anchors(original_plan, future_queue, historical_dir,
                       transfer_root, old_public_receipt)
    sources, facts = packages(source_root, REQUIRED_SOURCE_FAMILIES)
    proposed = {row["iso3"] for row in sources}
    counts = overlap_counts(proposed, baseline["sets"])
    priority_sha, selection_sha, rejected_count = selection_audit(
        priority_path, selection_path, proposed)
    source_commitment = ppt.sha(salt + ppt.canonical(sources))
    manifest = {
        "schema": SCHEMA, "boundary_date": DATE,
        "status": "source_checked_spec_plan_only_no_decks",
        "role": "new_nonfinal_withheld_calibration_boundary_not_historical_80",
        "original_wdi_snapshot_sha256": wdi.EXPECTED_SHA256,
        "active_v13_plan_sha256": PLAN_SHA,
        "future_reserve_queue_sha256": QUEUE_SHA,
        "historical_plan_hashes": baseline["historical_plan_hashes"],
        "transfer_source_packages": baseline["transfer_source_packages"],
        "historical_80_public_receipt_sha256": baseline["old_public_receipt_sha256"],
        "historical_80_published_private_manifest_sha256": OLD_PRIVATE_MANIFEST_SHA,
        "historical_80_private_provenance_status": "unavailable_not_reconstructed",
        "historical_80_source_overlap_count": None,
        "seed_commitment_sha256": ppt.sha(seed),
        "source_salt_commitment_sha256": ppt.sha(salt),
        "source_package_commitment_sha256": source_commitment,
        "candidate_priority_sha256": priority_sha,
        "source_selection_sha256": selection_sha,
        "source_candidate_rejections": rejected_count,
        "source_families": sources,
        "source_overlap_counts": counts,
        "planned_specs": 80, "built_decks": 0,
        "offline_controls_passed": 0, "office_web_gui_admitted": 0,
        "model_calls": 0, "official_final_admitted": 0,
    }
    return manifest, facts


def spec_plan(seed: bytes, manifest: dict, facts: dict[str, dict]) -> dict:
    require(len(seed) == 32 and manifest.get("schema") == SCHEMA and
            manifest.get("seed_commitment_sha256") == ppt.sha(seed),
            "rebase_manifest_or_seed_changed")
    rows = []
    for workflow in ppt.WORKFLOWS:
        index, slot = workflow_coordinates(workflow)
        for source in manifest["source_families"]:
            iso = source["iso3"]
            row = ppt.task(seed, "final_candidate", iso, index, slot, facts[iso])
            require(row["workflow"] == workflow and
                    len(set(row["target_keys"])) == 4 and
                    all(row["draft"][key] != row["correct"][key]
                        for key in row["target_keys"]),
                    "calibration_spec_not_four_target_final_shaped")
            identifier = "ppt-wdi-cal-rebase-" + ppt.keyed(
                seed, f"nonfinal-withheld-calibration-20260929:{iso}:{workflow}").hex()[:16]
            row.update({"task_id": identifier, "instance_group": identifier,
                        "split": "train_policy_development",
                        "development_source_split": "train",
                        "calibration_role":
                        "nonfinal_withheld_rebase_20260929_source_only",
                        "template_group": f"train-calibration-rebase-20260929:{workflow}",
                        "source_scope": "private_wdi_country_csv_reserve_v1",
                        "source_snapshot_sha256": source["snapshot_sha256"],
                        "source_zip_sha256": source["zip_sha256"],
                        "source_provenance_sha256": source["provenance_sha256"],
                        "source_snapshot_date": source["download_date"],
                        "source_csv_data_last_updated": source["data_last_updated"],
                        "official_final_credit": 0})
            rows.append(row)
    require(len(rows) == 80 and len({row["task_id"] for row in rows}) == 80 and
            set(Counter(row["workflow"] for row in rows).values()) == {8},
            "unbalanced_rebased_calibration_spec_plan")
    return {"schema": SPEC_SCHEMA, "status": "spec_only_unbuilt_unadmitted",
            "boundary_date": DATE,
            "source_boundary_manifest_sha256": ppt.sha(ppt.canonical(manifest)),
            "seed_commitment_sha256": ppt.sha(seed),
            "rows": rows, "built_decks": 0,
            "offline_controls_passed": 0, "office_web_gui_admitted": 0,
            "model_calls": 0, "official_final_admitted": 0}


def public_receipt(manifest: dict, plan: dict) -> dict:
    require(manifest.get("schema") == SCHEMA and plan.get("schema") == SPEC_SCHEMA and
            plan.get("source_boundary_manifest_sha256") ==
            ppt.sha(ppt.canonical(manifest)) and
            len(manifest.get("source_families", [])) == 8 and
            len(plan.get("rows", [])) == 80,
            "private_rebase_not_ready_for_public_receipt")
    return {"schema": PUBLIC_SCHEMA, "boundary_date": DATE,
            "status": "new_source_checked_80_specs_unbuilt_historical_private_unavailable",
            "historical_80_public_receipt_sha256":
            manifest["historical_80_public_receipt_sha256"],
            "historical_80_published_private_manifest_sha256": OLD_PRIVATE_MANIFEST_SHA,
            "historical_80_private_provenance_available": False,
            "historical_80_source_overlap_count": None,
            "new_source_families_checked": 8,
            "new_official_wdi_numeric_observations_checked": 240,
            "new_planned_calibration_specs": 80,
            "new_spec_workflows": 10,
            "new_cases_per_workflow": 8,
            "source_candidate_rejections": manifest["source_candidate_rejections"],
            "original_35_source_count": 35,
            "active_v13_plan_sha256": PLAN_SHA,
            "future_reserve_queue_sha256": QUEUE_SHA,
            "historical_final_plan_revisions_checked":
                len(manifest["historical_plan_hashes"]),
            "new_transfer_source_families_checked":
                len(manifest["transfer_source_packages"]),
            "source_overlap_counts": manifest["source_overlap_counts"],
            "source_package_commitment_sha256":
                manifest["source_package_commitment_sha256"],
            "source_package_commitment_method":
                "sha256_private_32_byte_salt_plus_canonical_source_package_metadata",
            "private_source_manifest_sha256": ppt.sha(ppt.canonical(manifest)),
            "private_spec_plan_sha256": ppt.sha(ppt.canonical(plan)),
            "rights_tier": "wdi_cc_by_4_0_facts_plus_authored_simulation",
            "new_decks_built": 0, "offline_controls_passed": 0,
            "office_web_gui_admitted": 0, "model_calls": 0,
            "official_final_admitted": 0}


def validate_rebased_boundary(path: Path, expected_sha256: str) -> set[str]:
    """For source-only gates; full private replay uses `verify` below."""
    manifest, raw = read_json(path)
    require(ppt.sha(raw) == expected_sha256 and
            manifest.get("schema") == SCHEMA and
            manifest.get("boundary_date") == DATE and
            manifest.get("status") == "source_checked_spec_plan_only_no_decks" and
            manifest.get("historical_80_private_provenance_status") ==
            "unavailable_not_reconstructed" and
            manifest.get("historical_80_published_private_manifest_sha256") ==
            OLD_PRIVATE_MANIFEST_SHA and
            manifest.get("active_v13_plan_sha256") == PLAN_SHA and
            manifest.get("future_reserve_queue_sha256") == QUEUE_SHA and
            manifest.get("historical_80_source_overlap_count") is None and
            len(manifest.get("historical_plan_hashes", [])) == 12 and
            len(manifest.get("transfer_source_packages", [])) == 2 and
            manifest.get("source_overlap_counts") ==
            {name: 0 for name in ("original_35", "active_v13_train",
                                  "active_v13_selection", "active_v13_final",
                                  "future_reserve", "historical_final",
                                  "new_transfer_pair")} and
            manifest.get("built_decks") == 0 and
            manifest.get("office_web_gui_admitted") == 0 and
            manifest.get("official_final_admitted") == 0,
            "rebased_calibration_source_boundary_missing_or_changed")
    sources = manifest.get("source_families", [])
    proposed = {row.get("iso3") for row in sources if isinstance(row, dict)}
    require(len(sources) == len(proposed) == REQUIRED_SOURCE_FAMILIES and
            all(isinstance(iso, str) and ISO3.fullmatch(iso) for iso in proposed) and
            all(row.get("numeric_observation_count") == 30 and
                all(isinstance(row.get(field), str) and
                    re.fullmatch(r"[0-9a-f]{64}", row[field])
                    for field in ("zip_sha256", "snapshot_sha256",
                                  "provenance_sha256"))
                for row in sources),
            "rebased_calibration_eight_source_families_required")
    return proposed


def verify(out_dir: Path, public_path: Path, *, source_root: Path,
           priority_path: Path, selection_path: Path,
           original_plan: Path, future_queue: Path,
           historical_dir: Path, transfer_root: Path,
           old_public_receipt: Path) -> dict:
    manifest, manifest_raw = read_json(out_dir / "manifest.private.json")
    plan, plan_raw = read_json(out_dir / "spec-plan.private.json")
    public, _ = read_json(public_path)
    seed = (out_dir / "seed.private").read_bytes()
    salt = (out_dir / "source-commitment-salt.private").read_bytes()
    expected_manifest, facts = source_manifest(
        seed, salt, source_root, priority_path, selection_path,
        original_plan, future_queue, historical_dir, transfer_root,
        old_public_receipt)
    require(manifest_raw == ppt.canonical(expected_manifest),
            "private_rebase_manifest_replay_changed")
    expected_plan = spec_plan(seed, expected_manifest, facts)
    require(plan_raw == ppt.canonical(expected_plan),
            "private_rebase_spec_plan_replay_changed")
    require(public == public_receipt(expected_manifest, expected_plan),
            "public_rebase_receipt_not_exact_replay")
    validate_rebased_boundary(out_dir / "manifest.private.json", ppt.sha(manifest_raw))
    return {"schema": "envloop-ppt-wdi-calibration-rebase-replay-local-v1",
            "source_families_reopened": 8,
            "official_observations_reopened": 240,
            "historical_final_plans_reopened": 12,
            "new_specs_replayed": 80,
            "all_known_source_overlap_counts_zero": True,
            "historical_80_private_provenance_available": False,
            "new_decks_built": 0, "official_final_admitted": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("create", "verify"))
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--priority", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--original-v13-plan", type=Path, required=True)
    parser.add_argument("--future-queue", type=Path, required=True)
    parser.add_argument("--historical-plan-dir", type=Path, required=True)
    parser.add_argument("--transfer-source-root", type=Path, required=True)
    parser.add_argument("--old-public-receipt", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    kwargs = {"source_root": args.source_root, "priority_path": args.priority,
              "selection_path": args.selection,
              "original_plan": args.original_v13_plan,
              "future_queue": args.future_queue,
              "historical_dir": args.historical_plan_dir,
              "transfer_root": args.transfer_source_root,
              "old_public_receipt": args.old_public_receipt}
    if args.mode == "create":
        out = args.private_out.resolve()
        require(out.is_relative_to((Path.cwd() / "work").resolve()) and
                not out.exists() and not args.public_out.exists(),
                "fresh_ignored_private_out_and_public_receipt_required")
        seed, salt = secrets.token_bytes(32), secrets.token_bytes(32)
        manifest, facts = source_manifest(seed, salt, **kwargs)
        plan = spec_plan(seed, manifest, facts)
        public = public_receipt(manifest, plan)
        out.mkdir(parents=True, mode=0o700)
        write_new(out / "seed.private", seed)
        write_new(out / "source-commitment-salt.private", salt)
        write_new(out / "manifest.private.json", ppt.canonical(manifest))
        write_new(out / "spec-plan.private.json", ppt.canonical(plan))
        args.public_out.parent.mkdir(parents=True, exist_ok=True)
        write_new(args.public_out, json.dumps(public, sort_keys=True, indent=2).encode() + b"\n")
        print(json.dumps({"status": public["status"],
                          "new_source_families_checked": 8,
                          "new_planned_calibration_specs": 80,
                          "new_decks_built": 0,
                          "historical_80_private_provenance_available": False},
                         sort_keys=True))
    else:
        result = verify(args.private_out, args.public_out, **kwargs)
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
