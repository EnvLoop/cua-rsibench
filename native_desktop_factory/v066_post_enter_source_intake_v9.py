"""Trusted, additive WDI intake and whole-family Desktop replacement.

Only metadata is read from historical task packages. Four new evaluator-only
oracles are authored from one official country CSV ZIP. No software, provider,
model, selection actor or final actor is started.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import shutil
from urllib.request import Request, urlopen
from unittest.mock import patch

from . import factory as base, factory_v2 as factory, source as wdi
from tools.build_ppt_wdi_reserve_replacement_v1 import facts_from_official_response
from tools.capture_ppt_wdi_transfer_expansion_20260929 import capture
from tools.extract_wdi_country_csv_reserve_v1 import extract

SCHEMA = "cua-native-wdi-whole-family-intake-private-v9"
PRIORITY = ("AUT", "BEL", "CHE", "DNK", "IRL", "PRT", "ROU", "HUN", "SVK",
            "SVN", "EST", "LVA", "LTU", "HRV", "GRC", "BGR", "ISL", "LUX",
            "MLT", "CYP", "SRB", "UKR", "URY", "CRI", "ECU", "PAN", "DOM")
ISO = re.compile(r"[A-Z]{3}\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")
METADATA_NAMES = {"candidate-inventory.json", "candidate-plan.private.json", "queue.private.json",
                  "source-provenance.private.json", "source-selection.private.json", "selection.private.json"}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def private_write(path: Path, raw: bytes):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())


def read_metadata(path: Path):
    require(path.is_file() and not path.is_symlink(), "metadata_file_missing_or_symlink")
    raw = path.read_bytes()
    require(len(raw) <= 16_000_000, "metadata_file_too_large")
    value = json.loads(raw)
    require(type(value) is dict, "metadata_object_required")
    return value, raw


def source_memberships(value: dict) -> set[str]:
    """Return identity membership only; never inspect an instruction or gold."""
    result = set()
    scalar = {"source_group", "country_iso", "country_iso3", "iso3"}
    lists = {"source_groups", "ordered_future_country_iso", "accepted_iso3", "selected_iso3"}

    def add(item):
        if type(item) is str:
            item = item.removeprefix("wdi-country:")
            if ISO.fullmatch(item):
                result.add(item)

    def walk(item):
        if type(item) is dict:
            for key, sub in item.items():
                if key in scalar:
                    add(sub)
                elif key in lists or key in ("train", "selection", "final_candidate"):
                    if type(sub) is list:
                        for entry in sub:
                            add(entry)
                            if type(entry) is dict:
                                walk(entry)
                elif key not in {"oracle", "gold", "prompt", "instruction", "actor_task", "task"}:
                    if type(sub) in (dict, list):
                        walk(sub)
        elif type(item) is list:
            for sub in item:
                if type(sub) in (dict, list):
                    walk(sub)
    walk(value)
    return result


def boundary(paths: list[Path]) -> tuple[list[dict], set[str]]:
    rows, excluded = [], set(wdi.COUNTRIES)
    for path in sorted(set(p.resolve() for p in paths)):
        value, raw = read_metadata(path)
        members = source_memberships(value)
        rows.append({"path": str(path), "sha256": base.digest(raw),
                     "source_memberships": sorted(members)})
        excluded.update(members)
    require(rows, "explicit_source_boundary_metadata_required")
    return rows, excluded


def check_boundary(rows):
    for row in rows:
        value, raw = read_metadata(Path(row["path"]))
        require(base.digest(raw) == row["sha256"] and
                sorted(source_memberships(value)) == row["source_memberships"],
                "source_boundary_changed_since_pre_download_freeze")


def checked_inventory(root: Path):
    inventory, raw = read_metadata(root / "candidate-inventory.json")
    rows = inventory.get("tasks")
    require(inventory.get("schema") == "cua-native-wdi-candidate-inventory-v1" and
            inventory.get("design_revision") == "v2-distinct-structures" and
            type(rows) is list and len(rows) == 140 and
            Counter(row.get("split") for row in rows) == Counter(base.EXPECTED_COUNTS) and
            len({row.get("task_id") for row in rows}) == 140,
            "original_20_20_100_metadata_invalid")
    for row in rows:
        require(type(row.get("source_groups")) is list and len(row["source_groups"]) == 1 and
                row.get("workflow") in base.WORKFLOWS and
                row.get("template_group") == factory.TEMPLATES[row["split"]][row["workflow"]] and
                row.get("package_sha256") == base.digest(base.json_bytes(
                    {k:v for k,v in row.items() if k != "package_sha256"})) and
                all(HEX.fullmatch(row.get(key, "")) for key in
                    ("input_sha256", "actor_task_sha256", "oracle_sha256", "package_sha256")),
                "package_metadata_hash_or_template_invalid")
    return inventory, raw


def _copy_package(original: Path, output: Path, row: dict):
    source = original / row["split"] / row["task_id"]
    dest = output / row["split"] / row["task_id"]
    require(source.is_dir() and not source.is_symlink(), "retained_package_missing")
    dest.mkdir(parents=True, mode=0o700)
    digest_set = {}
    # Read raw bytes for hash/copy only, including sealed oracle bytes.
    for path in sorted(source.rglob("*")):
        require(not path.is_symlink(), "retained_package_symlink")
        if path.is_dir():
            (dest / path.relative_to(source)).mkdir(mode=0o700, exist_ok=True)
        elif path.is_file():
            raw = path.read_bytes()
            relative = path.relative_to(source)
            private_write(dest / relative, raw)
            digest_set[str(relative)] = base.digest(raw)
    require(json.loads((dest / "package.json").read_bytes()) == row,
            "retained_package_manifest_changed")
    suffix = ".xlsx" if row["workflow"].startswith("calc-") else ".pptx" if row["workflow"].startswith("impress-") else ".docx"
    inputs = list(dest.glob("*" + suffix))
    require(len(inputs) == 1 and base.digest(inputs[0].read_bytes()) == row["input_sha256"] and
            digest_set.get("oracle.json") == row["oracle_sha256"] and
            digest_set.get("actor_task.txt") == row["actor_task_sha256"],
            "retained_raw_package_hash_changed")
    return digest_set


def build(*, original_root: Path, private_map: Path, private_output: Path,
          boundary_paths: list[Path], retired_roster_index: int = 12,
          fetch=None):
    require(retired_roster_index == 12 and not private_output.exists() and
            not private_output.is_symlink(), "fresh_v9_intake_root_and_consumed_index_required")
    inventory, old_raw = checked_inventory(original_root)
    mapping, mapping_raw = read_metadata(private_map)
    base.validate_private_map(mapping)
    require(base.digest(mapping_raw) == inventory["private_map_sha256"], "original_private_map_hash_changed")
    boundary_rows, excluded = boundary([original_root / "candidate-inventory.json", *boundary_paths])
    eligible = [iso for iso in PRIORITY if iso not in excluded]
    require(eligible, "no_unused_source_in_frozen_priority")
    private_output.mkdir(parents=True, mode=0o700)
    priority = {"schema": SCHEMA + "-priority", "created_utc": datetime.now(timezone.utc).isoformat(),
                "policy": "first_complete_official_csv_in_fixed_identity_only_priority",
                "source_boundary": boundary_rows, "excluded_union": sorted(excluded),
                "eligible_priority_iso3": eligible, "prior_inventory_sha256": base.digest(old_raw),
                "selection_and_final_content_inspected": False, "oracle_contents_inspected": False}
    private_write(private_output / "priority.private.json", base.json_bytes(priority))
    rejected = []
    source_root = private_output / "official-source"
    source_root.mkdir(mode=0o700)
    for iso in eligible:
        check_boundary(boundary_rows)
        url = f"https://api.worldbank.org/v2/en/country/{iso}?downloadformat=csv"
        requested = datetime.now(timezone.utc).isoformat()
        if fetch is None:
            with urlopen(Request(url, headers={"User-Agent":"EnvLoop-research-source-intake/1"}), timeout=90) as response:
                require(response.status == 200 and response.geturl().startswith("https://api.worldbank.org/"),
                        "official_country_response_boundary_changed")
                raw = response.read(10_000_001)
                headers = {k.lower():v for k,v in response.headers.items()}
        else:
            raw, headers = fetch(iso, url)
        try:
            extract(raw, iso)
        except ValueError as exc:
            private_write(private_output / "rejected" / (iso + ".zip"), raw)
            rejected.append({"iso3":iso, "zip_sha256":base.digest(raw), "reason":str(exc), "retrieved_at_utc":requested})
            continue
        entry = capture(raw, iso, headers, requested, source_root)
        break
    else:
        raise ValueError("frozen_country_priority_has_no_complete_source")
    check_boundary(boundary_rows)
    source_dir = source_root / entry["iso3"]
    snapshot = (source_dir / "source-snapshot.private.json").read_bytes()
    facts = facts_from_official_response(snapshot)
    source = {"names": {iso:facts["name"]}, "observations": {
        (iso, indicator, year):facts["years"][year][indicator]
        for indicator in wdi.INDICATORS for year in wdi.YEARS}}
    final = sorted((row for row in inventory["tasks"] if row["split"] == "final_candidate"), key=lambda row:row["task_id"])
    retired_group = final[retired_roster_index]["source_groups"]
    retired = [row for row in final if row["source_groups"] == retired_group]
    require(len(retired) == 4 and {row["workflow"] for row in retired} == set(base.WORKFLOWS),
            "retired_source_family_not_exact_four_workflows")
    cohort = private_output / "cohort"
    cohort.mkdir(mode=0o700)
    retained = [row for row in inventory["tasks"] if row not in retired]
    retained_trees = {row["task_id"]:_copy_package(original_root, cohort, row) for row in retained}
    new_map = {**mapping, "schema":"cua-native-wdi-private-map-plus-reserve-v9",
               "final_candidate":[iso if item == retired_group[0].removeprefix("wdi-country:") else item
                                  for item in mapping["final_candidate"]]}
    new_mapping_raw = base.json_bytes(new_map)
    private_write(private_output / "private-map.private.json", new_mapping_raw)
    attribution = (f"Source: World Bank World Development Indicators, official country CSV ZIP, "
                   f"2019–2024 extract; CC BY 4.0. Retrieved {requested[:10]}. "
                   f"Source snapshot SHA-256 {entry['snapshot_sha256']}. "
                   f"https://datacatalog.worldbank.org/search/dataset/0037712/world-development-indicators. "
                   "Derived comparisons and simulated policy inputs authored by EnvLoop.")
    with patch.object(factory, "EXPECTED_SHA256", entry["snapshot_sha256"]), \
            patch.object(base, "source_line", lambda:attribution):
        replacements = [factory.build_package(cohort, source, new_map, "final_candidate", iso, workflow)
                        for workflow in base.WORKFLOWS]
    for path in cohort.rglob("*"):
        path.chmod(0o700 if path.is_dir() else 0o600)
    revised = {**inventory, "tasks": [*retained, *replacements],
               "private_map_sha256":base.digest(new_mapping_raw),
               "status":"prospective_new_cohort_not_gui_admitted", "source_epoch":"post-enter-v9",
               "previous_inventory_sha256":base.digest(old_raw),
               "reserve_source_snapshot_sha256":entry["snapshot_sha256"],
               "reserve_source_provenance_sha256":base.digest((source_dir/"source-provenance.private.json").read_bytes())}
    check_splits(revised)
    private_write(cohort / "candidate-inventory.json", base.json_bytes(revised))
    receipt = {"schema":SCHEMA, "status":"one_official_source_four_new_packages_whole_family_replaced",
               "original_root":str(original_root.resolve()), "cohort_root":str(cohort.resolve()),
               "source_boundary":boundary_rows, "priority_sha256":base.digest((private_output/"priority.private.json").read_bytes()),
               "prior_inventory_sha256":base.digest(old_raw),
               "revised_inventory_sha256":base.digest((cohort/"candidate-inventory.json").read_bytes()),
               "original_private_map_sha256":base.digest(mapping_raw), "new_private_map_sha256":base.digest(new_mapping_raw),
               "retired_roster_index":12, "retired_source_groups":retired_group,
               "retired_package_metadata":retired, "replacements":replacements, "source":entry,
               "provenance_sha256":revised["reserve_source_provenance_sha256"], "rejected_sources":rejected,
               "retained_package_trees":retained_trees, "retained_packages_byte_identical":136,
               "source_license":"CC BY 4.0", "new_source_numeric_observations":30,
               "task_source_counts":{"train":20,"selection":20,"final_candidate":100},
               "source_family_counts":{"train":5,"selection":5,"final_candidate":25},
               "historical_controls_carried_into_new_epoch":0, "official_final_admissions":0,"model_calls":0}
    private_write(private_output / "intake-receipt.private.json", base.json_bytes(receipt))
    return receipt


def check_splits(inventory):
    rows = inventory["tasks"]
    require(len(rows) == 140 and len({row["task_id"] for row in rows}) == 140 and
            Counter(row["split"] for row in rows) == Counter(base.EXPECTED_COUNTS), "revised_task_counts_invalid")
    groups = {}
    for split, size in (("train",5),("selection",5),("final_candidate",25)):
        members = [row for row in rows if row["split"] == split]
        families = Counter(tuple(row["source_groups"]) for row in members)
        require(len(families) == size and set(families.values()) == {4} and
                Counter(row["workflow"] for row in members) == Counter({w:size for w in base.WORKFLOWS}) and
                all(row["template_group"] == factory.TEMPLATES[split][row["workflow"]] for row in members),
                "revised_family_workflow_or_template_balance_invalid")
        groups[split] = set(families)
    require(not groups["train"] & groups["selection"] and not groups["train"] & groups["final_candidate"] and
            not groups["selection"] & groups["final_candidate"], "revised_source_family_overlap")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("original-root","private-map","private-output"):
        parser.add_argument("--"+key,type=Path,required=True)
    parser.add_argument("--boundary",type=Path,action="append",required=True)
    args=parser.parse_args()
    receipt=build(original_root=args.original_root,private_map=args.private_map,
                  private_output=args.private_output,boundary_paths=args.boundary)
    print(json.dumps({"status":receipt["status"],"counts":receipt["task_source_counts"],
                      "source_family_counts":receipt["source_family_counts"],
                      "replacement_packages":4,"retained_packages_byte_identical":136,
                      "private_receipt_sha256":base.digest((args.private_output/"intake-receipt.private.json").read_bytes()),
                      "official_final_admissions":0,"model_calls":0},sort_keys=True))


if __name__=="__main__":main()
