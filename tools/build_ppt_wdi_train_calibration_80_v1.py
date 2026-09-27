"""Build 80 source-disjoint, four-target WDI PPT *training* analogues.

Only existing train task packages and three newly extracted official country
CSVs provide task content. The held-out plan is consulted solely by a blind
source_group collision check: no selection/final task ID, instruction, answer,
or gold is returned or copied. This is an offline calibration pool, never an
official study split or PowerPoint-web admission.
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import secrets
import subprocess

from native_desktop_factory import source as wdi
from ppt_wdi_factory import plan as ppt, verify
from ppt_wdi_factory.build import (
    DEFAULT_MODULES, DEFAULT_NODE, DEFAULT_PYTHON, DEFAULT_SKILL,
    prepare_builder,
)
from ppt_wdi_factory.qa import _chart_workbook, _validator
from tools.build_ppt_wdi_reserve_replacement_v1 import facts_from_official_response
from tools.extract_wdi_country_csv_reserve_v1 import extract
from tools.build_ppt_wdi_train_policy_development_v1 import write_new


PLAN_SHA = "71b263d9d5c899cde24b2835b3de64a98421bf2af811965001f54cc7d3b6e4ea"
QUEUE_SHA = "35ea4f56e669b1f3c66c76de0ef59c1e43987fdc5e6228ba6537ce916471c798"
SCHEMA = "envloop-ppt-wdi-train-calibration-80-private-v1"
PUBLIC_SCHEMA = "envloop-ppt-wdi-train-calibration-80-public-v1"
COUNTRY_COUNT = 8
WORKFLOW_COUNT = 10
TASK_COUNT = COUNTRY_COUNT * WORKFLOW_COUNT


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def train_sources(train_packages: Path) -> list[str]:
    paths = sorted(train_packages.glob("*/task.private.json"))
    require(len(paths) == 20, "Expected exactly 20 original train-only packages")
    rows = [json.loads(path.read_bytes()) for path in paths]
    require(all(row.get("schema") == ppt.SCHEMA and row.get("split") == "train" and
                row.get("source_snapshot_sha256") == wdi.EXPECTED_SHA256 and
                row.get("source_group") in wdi.COUNTRIES for row in rows),
            "Original train packages have unexpected source or split")
    countries = sorted({row["source_group"] for row in rows})
    require(len(countries) == 5 and
            set(Counter(row["source_group"] for row in rows).values()) == {4},
            "Five distinct four-task WDI train source families required")
    return countries


def blind_heldout_collision(heldout_plan: Path, future_queue: Path,
                            proposed: set[str]) -> dict:
    """Return aggregate collision counts only; never expose held-out rows."""
    plan_raw = heldout_plan.read_bytes()
    queue_raw = future_queue.read_bytes()
    require(ppt.sha(plan_raw) == PLAN_SHA and ppt.sha(queue_raw) == QUEUE_SHA,
            "Current pre-result plan or reserve queue changed")
    plan, queue = json.loads(plan_raw), json.loads(queue_raw)
    require(plan.get("schema") == ppt.SCHEMA and
            queue.get("schema") == "envloop-ppt-future-reserve-queue-private-v1" and
            queue.get("current_plan_sha256") == PLAN_SHA,
            "Held-out source registry is not the committed v13 registry")
    heldout_sources = {row["source_group"]
                       for split in ("selection", "final_candidate")
                       for row in plan["sets"][split]}
    future_sources = set(queue["ordered_future_country_iso"])
    collisions = proposed & (heldout_sources | future_sources)
    return {"heldout_source_collision_count": len(proposed & heldout_sources),
            "future_reserve_collision_count": len(proposed & future_sources),
            "any_collision": bool(collisions),
            "checked_current_plan_sha256": PLAN_SHA,
            "checked_future_queue_sha256": QUEUE_SHA}


def country_csv_sources(csv_root: Path) -> dict[str, tuple[dict, dict, bytes, bytes, bytes]]:
    dirs = sorted(path for path in csv_root.iterdir() if path.is_dir())
    require(len(dirs) == 3, "Exactly three new train-only CSV source directories required")
    result = {}
    for directory in dirs:
        iso = directory.name
        require(len(iso) == 3 and iso.isupper() and iso.isalpha() and
                iso not in wdi.COUNTRIES,
                "New CSV source must be outside the pinned 35-country snapshot")
        zip_path = csv_root / f"{iso}-country.private.zip"
        zip_raw = zip_path.read_bytes()
        snapshot_raw = (directory / "source-snapshot.private.json").read_bytes()
        provenance_raw = (directory / "source-provenance.private.json").read_bytes()
        provenance = json.loads(provenance_raw)
        extracted, detail = extract(zip_raw, iso)
        require(snapshot_raw == extracted and
                provenance.get("schema") ==
                "envloop-wdi-official-country-csv-extract-private-v1" and
                provenance.get("country_iso") == iso and
                provenance.get("catalog_license") == "CC BY 4.0" and
                provenance.get("zip_sha256") == ppt.sha(zip_raw) and
                provenance.get("snapshot_sha256") == ppt.sha(snapshot_raw) and
                detail["numeric_observation_count"] == 30,
                "Official WDI CSV provenance or 30 observations changed")
        facts = facts_from_official_response(snapshot_raw)
        require(facts["iso3"] == iso and facts["name"] == provenance["country_name"],
                "Country CSV and private WDI facts disagree")
        result[iso] = (facts, provenance, zip_raw, snapshot_raw, provenance_raw)
    return result


def workflow_coordinates(workflow: str) -> tuple[int, int]:
    for country_index in range(25):
        for slot in range(4):
            if ppt.workflow_for("final_candidate", country_index, slot) == workflow:
                return country_index, slot
    raise ValueError("No final-shaped workflow coordinates")


def make_rows(seed: bytes, train_countries: list[str],
              csv_sources: dict[str, tuple]) -> list[dict]:
    source = wdi.load()
    countries = [(iso, wdi.country_facts(source, iso), None)
                 for iso in train_countries]
    countries += [(iso, item[0], item[1]) for iso, item in sorted(csv_sources.items())]
    require(len(countries) == COUNTRY_COUNT and
            len({iso for iso, _, _ in countries}) == COUNTRY_COUNT,
            "Eight distinct training-only source families required")
    rows = []
    for workflow in ppt.WORKFLOWS:
        index, slot = workflow_coordinates(workflow)
        for iso, facts, provenance in countries:
            row = ppt.task(seed, "final_candidate", iso, index, slot, facts)
            require(row["workflow"] == workflow and len(row["target_keys"]) == 4,
                    "Analogue differs from final-shaped four-target workflow")
            task_id = "ppt-wdi-cal-" + ppt.keyed(
                seed, f"nonfinal-train-calibration:{iso}:{workflow}").hex()[:16]
            row.update({"task_id": task_id, "instance_group": task_id,
                        "split": "train_policy_development",
                        "development_source_split": "train",
                        "calibration_role": "nonfinal_train_only_four_target_analogue",
                        "template_group": f"train-calibration-{workflow}-v1"})
            if provenance is not None:
                csv = csv_sources[iso]
                row.update({"source_scope": "private_wdi_country_csv_reserve_v1",
                            "source_snapshot_sha256": ppt.sha(csv[3]),
                            "source_snapshot_date": provenance["download_date"],
                            "source_zip_sha256": ppt.sha(csv[2]),
                            "source_provenance_sha256": ppt.sha(csv[4]),
                            "source_csv_data_last_updated": provenance["data_last_updated"]})
            rows.append(row)
    require(len(rows) == TASK_COUNT and
            len({row["task_id"] for row in rows}) == TASK_COUNT and
            set(Counter(row["workflow"] for row in rows).values()) == {8} and
            all(len({row["source_group"] for row in rows
                     if row["workflow"] == workflow}) == 8
                for workflow in ppt.WORKFLOWS),
            "Unbalanced or duplicate calibration analogues")
    return rows


def build_one(out: Path, row: dict, csv_sources: dict, builder: Path,
              finalizer: Path, env: dict, tool_dir: Path) -> dict:
    package = out / "packages/train_policy_development" / row["task_id"]
    package.mkdir(parents=True, exist_ok=True, mode=0o700)
    spec = package / "task.private.json"
    raw_spec = ppt.canonical(row)
    if spec.exists():
        require(spec.read_bytes() == raw_spec, "Existing private task spec changed")
    else:
        write_new(spec, raw_spec)
    if row["source_group"] in csv_sources:
        _, _, zip_raw, snapshot_raw, provenance_raw = csv_sources[row["source_group"]]
        for name, raw in (("source-country.private.zip", zip_raw),
                          ("source-snapshot.private.json", snapshot_raw),
                          ("source-provenance.private.json", provenance_raw)):
            target = package / name
            if target.exists():
                require(target.read_bytes() == raw, "Existing CSV source changed")
            else:
                write_new(target, raw)
    draft, deck = package / "draft.pptx", package / "source.pptx"
    if not deck.exists():
        subprocess.run([str(DEFAULT_NODE), str(builder), str(spec), str(draft)],
                       check=True, capture_output=True, env=env, timeout=180)
        draft.chmod(0o600)
        subprocess.run([str(DEFAULT_NODE), str(finalizer), str(draft), str(deck)],
                       check=True, capture_output=True, env=env, timeout=180)
        deck.chmod(0o600)
    require(deck.is_file() and deck.stat().st_size > 5000,
            "Finalized calibration deck missing")
    _validator(tool_dir / "inspect_presentation_package_integrity.py",
               ["--fail-on-findings"], deck)
    _validator(tool_dir / "inspect_presentation_layout_geometry.py",
               ["--expected-aspect", "16:9", "--expected-slide-count", "7",
                "--require-native-table-slide", "2",
                "--require-native-table-slide", "4",
                "--approved-font-family", "Arial", "--validate-heading-fit",
                "--fail-on-findings"], deck)
    require(_chart_workbook(deck), "Native chart or embedded workbook missing")
    calibration = verify.calibrate(package)
    require(calibration["offline_controls_pass"],
            "Direct-file positive/negative controls failed")
    return {"task_id": row["task_id"], "workflow": row["workflow"],
            "source_group": row["source_group"],
            "spec_sha256": ppt.sha(spec.read_bytes()),
            "deck_sha256": ppt.sha(deck.read_bytes()),
            "calibration_sha256": ppt.sha(
                (package / "calibration.private.json").read_bytes()),
            "source_bytes": deck.stat().st_size}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-packages", type=Path, required=True)
    parser.add_argument("--heldout-plan", type=Path, required=True)
    parser.add_argument("--future-queue", type=Path, required=True)
    parser.add_argument("--csv-sources", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--public-receipt", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--limit", type=int,
                        help="Build only this many leading analogues; no public receipt")
    args = parser.parse_args()
    out = args.out_dir.resolve()
    require(out.is_relative_to((Path.cwd() / "work").resolve()) and
            1 <= args.workers <= 4 and
            (args.limit is None or 1 <= args.limit <= TASK_COUNT) and
            not args.public_receipt.exists(),
            "Ignored private output, bounded workers, fresh public receipt required")
    train = train_sources(args.train_packages)
    csv = country_csv_sources(args.csv_sources)
    candidate_sources = set(train) | set(csv)
    collision = blind_heldout_collision(args.heldout_plan, args.future_queue,
                                        candidate_sources)
    require(not collision["any_collision"],
            "Training source overlaps held-out or future reserve source")
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    seed_path = out / "calibration-seed.private"
    if not seed_path.exists():
        write_new(seed_path, secrets.token_bytes(32))
    seed = seed_path.read_bytes()
    require(len(seed) == 32, "Invalid private calibration seed")
    rows = make_rows(seed, train, csv)
    manifest = {"schema": SCHEMA, "status": "nonfinal_train_only_offline_calibration",
                "current_plan_sha256": PLAN_SHA, "future_queue_sha256": QUEUE_SHA,
                "train_packages_source_count": len(train),
                "new_official_country_csv_count": len(csv),
                "seed_commitment_sha256": ppt.sha(seed),
                "rows": rows, "model_calls": 0, "official_final_admitted": 0}
    manifest_raw = ppt.canonical(manifest)
    manifest_path = out / "manifest.private.json"
    if manifest_path.exists():
        require(manifest_path.read_bytes() == manifest_raw,
                "Prior calibration manifest changed")
    else:
        write_new(manifest_path, manifest_raw)
    builder = prepare_builder(out, DEFAULT_MODULES)
    finalizer = Path("ppt_wdi_factory/finalize_deck.mjs").resolve()
    env = {**os.environ, "NODE_OPTIONS": "--max-old-space-size=4096",
           "PRESENTATIONS_SKILL_DIR": str(DEFAULT_SKILL),
           "RUNTIME_PYTHON": str(DEFAULT_PYTHON),
           "RUNTIME_NODE": str(DEFAULT_NODE),
           "RUNTIME_NODE_MODULES": str(DEFAULT_MODULES)}
    tool_dir = DEFAULT_SKILL / "container_tools"
    selected_rows = rows if args.limit is None else rows[:args.limit]
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for number, record in enumerate(pool.map(
                lambda row: build_one(out, row, csv, builder, finalizer, env, tool_dir),
                selected_rows), 1):
            results.append(record)
            if number % 10 == 0 or number == len(selected_rows):
                print(json.dumps({"offline_built_and_checked": number,
                                  "requested": len(selected_rows),
                                  "official_final_credit": 0}), flush=True)
    if args.limit is not None:
        print(json.dumps({"status": "partial_private_build_no_public_claim",
                          "offline_built_and_checked": len(results),
                          "official_final_credit": 0}, sort_keys=True))
        return
    receipt = {"schema": "envloop-ppt-wdi-train-calibration-80-receipt-private-v1",
               "manifest_sha256": ppt.sha(manifest_raw),
               "builder_sha256": ppt.sha(builder.read_bytes()),
               "finalizer_sha256": ppt.sha(finalizer.read_bytes()),
               "verifier_sha256": ppt.sha(Path(verify.__file__).read_bytes()),
               "source_overlap_audit": collision,
               "results": results,
               "offline_passed": TASK_COUNT, "model_calls": 0,
               "official_final_admitted": 0}
    receipt_raw = ppt.canonical(receipt)
    receipt_path = out / "receipt.private.json"
    if receipt_path.exists():
        require(receipt_path.read_bytes() == receipt_raw,
                "Prior calibration receipt changed")
    else:
        write_new(receipt_path, receipt_raw)
    public = {"schema": PUBLIC_SCHEMA,
              "status": "80_nonfinal_train_only_offline_analogues_not_gui_admitted",
              "original_study_split_unchanged": True,
              "declared_workflows": WORKFLOW_COUNT,
              "calibration_analogue_tasks": TASK_COUNT,
              "tasks_per_workflow": 8,
              "train_only_source_families": COUNTRY_COUNT,
              "minimum_source_families_per_workflow": COUNTRY_COUNT,
              "new_official_wdi_csv_source_families": len(csv),
              "new_official_wdi_csv_numeric_observations": len(csv) * 30,
              "target_fields_per_analogue": 4,
              "seven_slide_native_chart_workbook_decks": TASK_COUNT,
              "package_integrity_and_layout_pass": TASK_COUNT,
              "offline_positive_partial_collateral_chart_controls_pass": TASK_COUNT,
              "heldout_source_collision_count": collision["heldout_source_collision_count"],
              "future_reserve_collision_count": collision["future_reserve_collision_count"],
              "current_heldout_plan_sha256": PLAN_SHA,
              "private_manifest_sha256": ppt.sha(manifest_raw),
              "private_receipt_sha256": ppt.sha(receipt_raw),
              "model_calls": 0,
              "office_web_gui_admitted": 0,
              "official_final_admitted": 0,
              "evidence_class": "offline direct-file controls only; no cloud save or model difficulty result"}
    args.public_receipt.parent.mkdir(parents=True, exist_ok=True)
    write_new(args.public_receipt, json.dumps(public, sort_keys=True, indent=2).encode() + b"\n")
    print(json.dumps({"calibration_analogues": TASK_COUNT,
                      "offline_controls_pass": TASK_COUNT,
                      "source_collision_count": 0,
                      "official_final_credit": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
