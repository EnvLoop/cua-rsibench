"""Publish aggregate-only evidence for a replacement WDI PPT source family."""

from __future__ import annotations

from collections import Counter
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from urllib.parse import urlparse
import zipfile
import xml.etree.ElementTree as ET

from ppt_wdi_factory import verify


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--quarantine", type=Path, required=True)
    parser.add_argument("--source-provenance", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root, out = args.private_root.resolve(), args.out.resolve()
    require(root.is_relative_to((Path.cwd() / "work").resolve()) and
            not out.exists(), "private revised work/ and new public receipt required")
    raw_plan = (root / "candidate-plan.private.json").read_bytes()
    plan = json.loads(raw_plan)
    quarantine_raw = args.quarantine.read_bytes()
    quarantine = json.loads(quarantine_raw)
    provenance_raw = args.source_provenance.read_bytes()
    provenance = json.loads(provenance_raw)
    require(plan["revision"] == "private_wdi_reserve_and_web_chart_v3" and
            plan["quarantine_receipt_sha256"] == sha(quarantine_raw) and
            plan["reserve_source_sha256"] == provenance["raw_response_sha256"] and
            provenance["source_snapshot_date"] == "2026-09-27" and
            provenance["numeric_observation_count"] == 30 and
            provenance["catalog_license"] == "CC BY 4.0" and
            urlparse(provenance["official_api_url"]).hostname == "api.worldbank.org",
            "revision/source provenance binding changed")
    require({key: len(rows) for key, rows in plan["sets"].items()} ==
            {"train": 20, "selection": 20, "final_candidate": 100},
            "revised split task counts changed")
    finals = plan["sets"]["final_candidate"]
    reserve = [row for row in finals if row.get("source_scope") == "private_wdi_reserve_v1"]
    require(len(reserve) == 4 and
            len({row["source_group"] for row in reserve}) == 1 and
            len({row["source_group"] for row in finals}) == 25 and
            set(Counter(row["workflow"] for row in finals).values()) == {10} and
            Counter(row["workflow"] for row in finals)["chart_caption_reconciliation"] == 10 and
            Counter(row["workflow"] for row in finals)["chart_series_relabel"] == 0 and
            not (set(quarantine["task_ids"]) & {row["task_id"] for row in finals}) and
            quarantine["source_group"] not in {row["source_group"] for row in finals},
            "quarantined source or final workflow count re-entered")
    for row in reserve:
        package = root / "packages/final_candidate" / row["task_id"]
        require(sha((package / "source-snapshot.private.json").read_bytes()) ==
                plan["reserve_source_sha256"] and
                row["source_snapshot_date"] == provenance["source_snapshot_date"] and
                json.loads((package / "calibration.private.json").read_bytes())["offline_controls_pass"] is True,
                "replacement source or calibration changed")
        deck = package / "source.pptx"
        frozen = verify.freeze(deck, row)
        require(frozen["source_snapshot_sha256"] == plan["reserve_source_sha256"],
                "reserve oracle does not bind its distinct World Bank response")
        with zipfile.ZipFile(deck) as archive:
            require(b"2026-09-27" in archive.read("ppt/slides/slide2.xml"),
                    "replacement slide attribution has stale source date")
    build_raw = (root / "build-receipt.private.json").read_bytes()
    qa_raw = (root / "qa-aggregate.private.json").read_bytes()
    calibration_raw = (root / "calibration-run.private.json").read_bytes()
    build = json.loads(build_raw)
    qa = json.loads(qa_raw)
    calibration = json.loads(calibration_raw)
    require(build["plan_sha256"] == calibration["plan_sha256"] == sha(raw_plan) and
            len(build["rows"]) == 140 and
            qa == {"candidate_decks": 140, "package_integrity_pass": 140,
                   "layout_geometry_pass": 140,
                   "chart_workbook_contract_pass": 140} and
            calibration["candidate_count"] == calibration["offline_passed"] == 140,
            "full replacement build/QA/calibration receipt incomplete")
    chart_axis_checked = 0
    for split in ("train", "selection", "final_candidate"):
        for row in plan["sets"][split]:
            deck = root / "packages" / split / row["task_id"] / "source.pptx"
            with zipfile.ZipFile(deck) as archive:
                charts = [name for name in archive.namelist()
                          if "/charts/chart" in name and name.endswith(".xml")]
                require(len(charts) == 1, "candidate native chart missing")
                chart = ET.fromstring(archive.read(charts[0]))
            axes = list(chart.iter(verify.C + "valAx"))
            require(len(axes) == 1, "candidate value axis ambiguous")
            scaling = axes[0].find(verify.C + "scaling")
            require(scaling is not None, "candidate axis scaling absent")
            lower_node, upper_node = (scaling.find(verify.C + name)
                                      for name in ("min", "max"))
            step_node = axes[0].find(verify.C + "majorUnit")
            require(all(node is not None for node in
                        (lower_node, upper_node, step_node)),
                    "candidate explicit axis bounds absent")
            lower, upper, step = (float(node.attrib["val"])
                                  for node in (lower_node, upper_node, step_node))
            values = [float(value) for series in row["chart"]["series"]
                      for value in series["values"]]
            smooth = list(chart.iter(verify.C + "smooth"))
            require(values and all(math.isfinite(value) for value in values) and
                    math.isfinite(lower) and math.isfinite(upper) and
                    math.isfinite(step) and step > 0 and lower < upper and
                    lower <= min(values) and upper > max(values) and
                    lower <= 0 <= upper and (upper - lower) / step <= 10.01 and
                    len(smooth) == len(row["chart"]["series"]) + 1 and
                    all(node.get("val") == "0" for node in smooth),
                    "candidate chart axis clips a WDI value or smooths it")
            chart_axis_checked += 1
    require(chart_axis_checked == 140, "full chart presentation audit incomplete")
    public = {"schema": "envloop-ppt-wdi-reserve-revision-public-v1",
              "status": "replacement_20_20_100_offline_candidates_not_web_admitted",
              "previous_plan_sha256": plan["previous_plan_sha256"],
              "revised_plan_sha256": sha(raw_plan),
              "reserve_source_sha256": plan["reserve_source_sha256"],
              "source_provenance_private_sha256": sha(provenance_raw),
              "quarantine_private_sha256": sha(quarantine_raw),
              "source_license": "World Development Indicators CC BY 4.0",
              "split_candidate_counts": {key: len(rows) for key, rows in plan["sets"].items()},
              "replacement_tasks": 4,
              "quarantined_original_tasks": 4,
              "final_source_families": 25,
              "final_causal_workflows": 10,
              "web_editable_chart_caption_tasks": 10,
              "removed_native_chart_legend_edit_tasks": 10,
              "replacement_source_observations": 30,
              "source_snapshot_date": provenance["source_snapshot_date"],
              "build_receipt_private_sha256": sha(build_raw),
              "qa_receipt_private_sha256": sha(qa_raw),
              "calibration_receipt_private_sha256": sha(calibration_raw),
              "package_integrity_pass": 140,
              "layout_geometry_pass": 140,
              "native_chart_workbook_contract_pass": 140,
              "native_chart_axis_bounds_and_unsmoothed_pass": chart_axis_checked,
              "offline_positive_negative_controls_pass": 140,
              "office_web_gui_admitted": 0,
              "official_final_tasks_admitted": 0,
              "model_calls": 0,
              "researcher_campaigns": 0}
    raw = (json.dumps(public, sort_keys=True, indent=2) + "\n").encode()
    out.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps({"status": public["status"],
                      "revised_plan_sha256": sha(raw_plan),
                      "replacement_tasks": 4,
                      "offline_passed": 140,
                      "official_final_tasks_admitted": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
