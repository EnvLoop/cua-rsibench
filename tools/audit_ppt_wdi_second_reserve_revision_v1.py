"""Publish aggregate-only evidence for two pre-result WDI source replacements."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import zipfile

from ppt_wdi_factory import verify
from tools import pptx_title_size_guard as package_guard
from tools.audit_ppt_wdi_reserve_revision_v1 import require, sha


def audit_axes(root: Path, plan: dict) -> int:
    checked = 0
    for split in ("train", "selection", "final_candidate"):
        for row in plan["sets"][split]:
            deck = root / "packages" / split / row["task_id"] / "source.pptx"
            with zipfile.ZipFile(deck) as archive:
                charts = [name for name in archive.namelist()
                          if "/charts/chart" in name and name.endswith(".xml")]
                require(len(charts) == 1, "candidate native chart missing")
                chart = ET.fromstring(archive.read(charts[0]))
            axes = list(chart.iter(verify.C + "valAx"))
            require(len(axes) == 1, "candidate chart value axis ambiguous")
            scaling = axes[0].find(verify.C + "scaling")
            require(scaling is not None, "candidate chart scaling absent")
            nodes = [scaling.find(verify.C + "min"),
                     scaling.find(verify.C + "max"),
                     axes[0].find(verify.C + "majorUnit")]
            require(all(node is not None for node in nodes),
                    "candidate chart axis bounds absent")
            lower, upper, step = [float(node.attrib["val"]) for node in nodes]
            values = [float(value) for series in row["chart"]["series"]
                      for value in series["values"]]
            smooth = list(chart.iter(verify.C + "smooth"))
            require(values and all(math.isfinite(value) for value in values) and
                    all(math.isfinite(value) for value in (lower, upper, step)) and
                    step > 0 and lower < upper and lower <= min(values) and
                    upper > max(values) and lower <= 0 <= upper and
                    (upper - lower) / step <= 10.01 and
                    len(smooth) == len(row["chart"]["series"]) + 1 and
                    all(node.get("val") == "0" for node in smooth),
                    "candidate chart clips or smooths a WDI observation")
            checked += 1
    require(checked == 140, "native chart audit incomplete")
    return checked


def semantic_deck_equal(first: Path, second: Path) -> bool:
    _, before = package_guard.package(first)
    _, after = package_guard.package(second)
    slides = [name for name in before if name.startswith("ppt/slides/slide")
              and name.endswith(".xml") and
              name.removeprefix("ppt/slides/slide").removesuffix(".xml").isdigit()]
    if len(slides) != 7 or not all(name in after for name in slides):
        return False

    def visible_objects(raw: bytes) -> list[tuple]:
        root = package_guard.xml(raw)
        objects = []
        for element in root.iter():
            if element.tag == verify.P + "sp":
                identity = element.find(verify.P + "nvSpPr/" + verify.P + "cNvPr")
                if identity is None:
                    return []
                objects.append(("shape", identity.get("id"), identity.get("name"),
                                "".join(node.text or "" for node in
                                        element.iter(verify.A + "t"))))
            elif element.tag == verify.P + "graphicFrame":
                identity = element.find(verify.P + "nvGraphicFramePr/" +
                                        verify.P + "cNvPr")
                if identity is None:
                    return []
                tables = list(element.iter(verify.A + "tbl"))
                if len(tables) > 1:
                    return []
                cells = tuple(tuple("".join(node.text or "" for node in
                                             cell.iter(verify.A + "t"))
                                    for cell in row.iter(verify.A + "tc"))
                              for row in tables[0].iter(verify.A + "tr")) if tables else ()
                objects.append(("graphic_frame", identity.get("id"), cells))
        return objects

    if not all(visible_objects(before[name]) == visible_objects(after[name])
               for name in slides):
        return False
    chart_a, workbook_a = verify._chart_and_workbook_parts(before)
    chart_b, workbook_b = verify._chart_and_workbook_parts(after)
    return (verify._masked_chart(before[chart_a], [], True) ==
            verify._masked_chart(after[chart_b], [], True) and
            verify._masked_workbook_equal(before[workbook_a],
                                          after[workbook_b], []))


def write_new(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prior-root", type=Path, required=True)
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--second-quarantine", type=Path, required=True)
    parser.add_argument("--country-provenance", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    private = (Path.cwd() / "work").resolve()
    root, prior_root = args.private_root.resolve(), args.prior_root.resolve()
    require(root.is_relative_to(private) and prior_root.is_relative_to(private) and
            not args.out.exists(), "private revised roots and new public output required")
    raw_plan = (root / "candidate-plan.private.json").read_bytes()
    prior_raw = (prior_root / "candidate-plan.private.json").read_bytes()
    plan, prior = json.loads(raw_plan), json.loads(prior_raw)
    qraw = args.second_quarantine.read_bytes()
    quarantine = json.loads(qraw)
    praw = args.country_provenance.read_bytes()
    provenance = json.loads(praw)
    require(plan["revision"] == "private_wdi_two_reserves_and_web_chart_v4" and
            plan["previous_plan_sha256"] == sha(prior_raw) and
            prior["revision"] == "private_wdi_reserve_and_web_chart_v3" and
            plan["second_quarantine_receipt_sha256"] == sha(qraw) and
            plan["second_reserve_provenance_sha256"] == sha(praw) and
            quarantine["revised_plan_sha256"] == sha(prior_raw) and
            provenance["schema"] ==
            "envloop-wdi-official-country-csv-extract-private-v1" and
            provenance["catalog_license"] == "CC BY 4.0" and
            provenance["numeric_observation_count"] == 30 and
            urlparse(provenance["official_download_url"]).hostname ==
            "api.worldbank.org" and
            urlparse(provenance["official_page_url"]).hostname ==
            "data.worldbank.org",
            "two-reserve plan/source/quarantine provenance changed")
    require({key: len(rows) for key, rows in plan["sets"].items()} ==
            {"train": 20, "selection": 20, "final_candidate": 100},
            "revised split counts changed")
    finals = plan["sets"]["final_candidate"]
    first = [row for row in finals if row.get("source_scope") ==
             "private_wdi_reserve_v1"]
    second = [row for row in finals if row.get("source_scope") ==
              "private_wdi_country_csv_reserve_v1"]
    require(len(first) == len(second) == 4 and
            len({row["source_group"] for row in first}) ==
            len({row["source_group"] for row in second}) == 1 and
            len({row["source_group"] for row in finals}) == 25 and
            set(Counter(row["workflow"] for row in finals).values()) == {10} and
            {row["task_id"] for row in finals}.isdisjoint(
                quarantine["task_ids"]) and
            quarantine["source_group"] not in
            {row["source_group"] for row in finals} and
            not ({row["source_group"] for row in
                  plan["sets"]["train"] + plan["sets"]["selection"]} &
                 {row["source_group"] for row in finals}),
            "two-reserve final pool or source isolation changed")
    preserved = 0
    prior_by_id = {row["task_id"]: row for rows in prior["sets"].values()
                   for row in rows}
    for split in ("train", "selection", "final_candidate"):
        for row in plan["sets"][split]:
            package = root / "packages" / split / row["task_id"]
            if row["task_id"] not in prior_by_id:
                continue
            require(row == prior_by_id[row["task_id"]] and
                    semantic_deck_equal(
                        prior_root / "packages" / split / row["task_id"] /
                        "source.pptx", package / "source.pptx"),
                    "unexposed prior task or visible/chart/workbook source changed")
            preserved += 1
    require(preserved == 136, "136 prior task and semantic deck contracts required")
    for row in first + second:
        package = root / "packages/final_candidate" / row["task_id"]
        frozen = verify.freeze(package / "source.pptx", row)
        require(frozen["source_snapshot_sha256"] ==
                row["source_snapshot_sha256"] and
                json.loads((package / "calibration.private.json").read_bytes())
                ["offline_controls_pass"] is True,
                "reserve source/oracle/calibration changed")
        if row in second:
            require(sha((package / "source-snapshot.private.json").read_bytes())
                    == plan["second_reserve_source_sha256"] and
                    sha((package / "source-country.private.zip").read_bytes())
                    == plan["second_reserve_zip_sha256"] and
                    sha((package / "source-provenance.private.json").read_bytes())
                    == plan["second_reserve_provenance_sha256"],
                    "official CSV source not retained in each replacement package")
    build_raw = (root / "build-receipt.private.json").read_bytes()
    qa_raw = (root / "qa-aggregate.private.json").read_bytes()
    calibration_raw = (root / "calibration-run.private.json").read_bytes()
    build, qa, calibration = (json.loads(raw) for raw in
                              (build_raw, qa_raw, calibration_raw))
    require(build["plan_sha256"] == calibration["plan_sha256"] ==
            sha(raw_plan) and len(build["rows"]) == 140 and
            qa == {"candidate_decks": 140, "package_integrity_pass": 140,
                   "layout_geometry_pass": 140,
                   "chart_workbook_contract_pass": 140} and
            calibration["candidate_count"] ==
            calibration["offline_passed"] == 140,
            "full two-reserve build/QA/calibration receipt incomplete")
    axis_pass = audit_axes(root, plan)
    visual = root / "visual-qa/second-reserve.pdf"
    pages = subprocess.check_output(["pdfinfo", str(visual)], text=True,
                                    timeout=15)
    require(re.search(r"^Pages:\s+7$", pages, re.MULTILINE) is not None and
            (root / "visual-qa/second-reserve-contact-sheet.png").is_file(),
            "seven-page replacement visual QA missing")
    public = {"schema": "envloop-ppt-wdi-two-reserve-revision-public-v1",
              "status": "two_reserve_20_20_100_offline_candidates_not_web_admitted",
              "prior_plan_sha256": sha(prior_raw),
              "revised_plan_sha256": sha(raw_plan),
              "second_quarantine_private_sha256": sha(qraw),
              "second_source_provenance_private_sha256": sha(praw),
              "two_quarantined_source_families": 2,
              "two_reserve_source_families": 2,
              "replacement_tasks_total": 8,
              "unchanged_prior_task_specs_and_semantic_decks": preserved,
              "split_candidate_counts": {key: len(rows) for key, rows in
                                         plan["sets"].items()},
              "final_source_families": 25,
              "final_workflows": 10,
              "second_source_observations": 30,
              "second_source_kind": "official_world_bank_country_csv_extract",
              "source_license": "World Development Indicators CC BY 4.0",
              "build_receipt_private_sha256": sha(build_raw),
              "qa_receipt_private_sha256": sha(qa_raw),
              "calibration_receipt_private_sha256": sha(calibration_raw),
              "package_integrity_pass": 140,
              "layout_geometry_pass": 140,
              "native_chart_workbook_contract_pass": 140,
              "native_chart_axis_bounds_and_unsmoothed_pass": axis_pass,
              "offline_positive_negative_controls_pass": 140,
              "visual_qa_pages": 7,
              "office_web_gui_admitted": 0,
              "official_final_tasks_admitted": 0,
              "model_calls": 0,
              "researcher_campaigns": 0}
    write_new(args.out, (json.dumps(public, sort_keys=True, indent=2) + "\n").encode())
    print(json.dumps({"status": public["status"],
                      "revised_plan_sha256": sha(raw_plan),
                      "preserved_prior_semantic_decks": preserved,
                      "offline_passed": 140,
                      "official_final_tasks_admitted": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
