"""Replace one quarantined PPT final family with a private, new WDI source.

This creates a revised 20/20/100 candidate manifest and four evaluator-only
source snapshots. It does not build decks, run Office, or admit final tasks.
"""

from __future__ import annotations

from collections import Counter
import argparse
import hashlib
import json
import os
from pathlib import Path
import re

from native_desktop_factory import source as wdi
from ppt_wdi_factory import plan as ppt


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_new(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def facts_from_official_response(raw: bytes) -> dict:
    payload = json.loads(raw)
    require(isinstance(payload, list) and len(payload) == 2,
            "World Bank reserve response envelope changed")
    header, rows = payload
    require(header.get("page") == header.get("pages") == 1 and
            header.get("total") == len(rows) == 30,
            "World Bank reserve response incomplete")
    countries, names, observations = set(), set(), {}
    for row in rows:
        iso = row.get("countryiso3code")
        indicator = row.get("indicator", {}).get("id")
        year = row.get("date")
        value = row.get("value")
        key = (indicator, year)
        require(indicator in wdi.INDICATORS and year in wdi.YEARS and
                key not in observations and isinstance(value, (int, float)) and
                not isinstance(value, bool),
                "Reserve observation missing, duplicated, or nonnumeric")
        countries.add(iso)
        names.add(row.get("country", {}).get("value"))
        observations[key] = value
    require(len(countries) == len(names) == 1 and None not in names and
            len(observations) == len(wdi.INDICATORS) * len(wdi.YEARS),
            "Reserve country data cube changed")
    iso = next(iter(countries))
    return {"iso3": iso, "name": next(iter(names)),
            "years": {year: {indicator: observations[(indicator, year)]
                             for indicator in wdi.INDICATORS}
                      for year in wdi.YEARS}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-plan", type=Path, required=True)
    parser.add_argument("--original-plan-sha256", required=True)
    parser.add_argument("--seed-file", type=Path, required=True)
    parser.add_argument("--quarantine", type=Path, required=True)
    parser.add_argument("--reserve-snapshot", type=Path, required=True)
    parser.add_argument("--reserve-snapshot-date", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    out = args.out_dir.resolve()
    require(out.is_relative_to((Path.cwd() / "work").resolve()) and
            not out.exists(), "fresh ignored work/ output required")
    raw_original = args.original_plan.read_bytes()
    require(sha(raw_original) == args.original_plan_sha256,
            "original candidate plan digest changed")
    original = json.loads(raw_original)
    require(original["schema"] == ppt.SCHEMA and
            {key: len(rows) for key, rows in original["sets"].items()} == ppt.COUNTS,
            "original 20/20/100 plan changed")
    seed = bytes.fromhex(args.seed_file.read_text().strip())
    require(len(seed) == 32 and original["seed_commitment_sha256"] == sha(seed),
            "private plan seed changed")
    aligned = {"schema": "cua-native-wdi-private-map-v1"}
    for split in ppt.COUNTS:
        aligned[split] = list(dict.fromkeys(row["source_group"]
                                            for row in original["sets"][split]))
    rebuilt = ppt.build(seed, aligned)
    require(all([row["source_group"] for row in rebuilt["sets"][split]] ==
                [row["source_group"] for row in original["sets"][split]]
                for split in ppt.COUNTS),
            "revised workflow generation changed the source-family partition")
    quarantine_raw = args.quarantine.read_bytes()
    quarantine = json.loads(quarantine_raw)
    source_group = quarantine["source_group"]
    old_final = rebuilt["sets"]["final_candidate"]
    old_rows = [(index, row) for index, row in enumerate(old_final)
                if row["source_group"] == source_group]
    require(len(old_rows) == 4 and
            {row["task_id"] for _, row in old_rows} == set(quarantine["task_ids"]) and
            {index // 4 for index, _ in old_rows} == {old_rows[0][0] // 4} and
            [index % 4 for index, _ in old_rows] == [0, 1, 2, 3],
            "quarantined family no longer has four ordered tasks")
    reserve_raw = args.reserve_snapshot.read_bytes()
    reserve_sha = sha(reserve_raw)
    require(re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.reserve_snapshot_date) is not None,
            "reserve source observation date required")
    facts = facts_from_official_response(reserve_raw)
    reserved_iso = facts["iso3"]
    require(reserved_iso not in set(wdi.COUNTRIES) and
            reserved_iso not in {row["source_group"] for rows in original["sets"].values()
                                 for row in rows},
            "reserve source family is not new and disjoint")
    revised = rebuilt
    revised["revision"] = "private_wdi_reserve_and_web_chart_v3"
    revised["previous_plan_sha256"] = args.original_plan_sha256
    revised["quarantine_receipt_sha256"] = sha(quarantine_raw)
    revised["reserve_source_sha256"] = reserve_sha
    revised["country_partition_alignment"] = "shared_wdi_desktop_private_partition_plus_one_new_reserve"
    country_index = old_rows[0][0] // 4
    replacements = []
    for index, old in old_rows:
        slot = index % 4
        replacement = ppt.task(seed, "final_candidate", reserved_iso,
                               country_index, slot, facts)
        require(replacement["workflow"] == old["workflow"] and
                replacement["target_keys"] == old["target_keys"],
                "replacement changes workflow or target quota")
        replacement["source_scope"] = "private_wdi_reserve_v1"
        replacement["source_snapshot_sha256"] = reserve_sha
        replacement["source_snapshot_date"] = args.reserve_snapshot_date
        revised["sets"]["final_candidate"][index] = replacement
        replacements.append(replacement)
    require(len({row["task_id"] for rows in revised["sets"].values()
                 for row in rows}) == 140 and
            len({row["source_group"] for row in revised["sets"]["final_candidate"]}) == 25 and
            set(Counter(row["workflow"] for row in revised["sets"]["final_candidate"]).values()) == {10} and
            not ({row["source_group"] for row in revised["sets"]["train"] +
                  revised["sets"]["selection"]} &
                 {row["source_group"] for row in revised["sets"]["final_candidate"]}),
            "revised candidate split or workflow balance changed")
    out.mkdir(parents=True, mode=0o700)
    plan_raw = ppt.canonical(revised)
    write_new(out / "candidate-plan.private.json", plan_raw)
    for row in replacements:
        package = out / "packages/final_candidate" / row["task_id"]
        write_new(package / "source-snapshot.private.json", reserve_raw)
    receipt = {"schema": "envloop-ppt-wdi-reserve-replacement-private-v1",
               "status": "revised_candidates_not_built_or_gui_admitted",
               "previous_plan_sha256": args.original_plan_sha256,
               "revised_plan_sha256": sha(plan_raw),
               "reserve_source_sha256": reserve_sha,
               "quarantine_receipt_sha256": sha(quarantine_raw),
               "replacement_task_ids": [row["task_id"] for row in replacements],
               "replacement_source_group": reserved_iso,
               "counts": {key: len(rows) for key, rows in revised["sets"].items()},
               "final_source_families": 25, "final_workflows": 10,
               "official_final_admitted": 0, "model_calls": 0}
    receipt_raw = ppt.canonical(receipt)
    write_new(out / "replacement-receipt.private.json", receipt_raw)
    print(json.dumps({"status": receipt["status"],
                      "revised_plan_sha256": sha(plan_raw),
                      "reserve_source_sha256": reserve_sha,
                      "private_receipt_sha256": sha(receipt_raw),
                      "replacement_tasks": 4,
                      "final_candidate_count": 100,
                      "final_source_families": 25,
                      "official_final_admitted": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
