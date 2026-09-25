"""Independent saved-OOXML verifier and offline control fixtures for WDI PPT.

The verifier takes a frozen evaluator baseline, never an actor-supplied answer.
Its offline fixtures are synthetic direct OOXML mutations. They do not prove
visible PowerPoint-web editing, cloud isolation, download, or reset.
"""

from __future__ import annotations

import argparse
import copy
import io
import json
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

from native_desktop_factory.source import EXPECTED_SHA256, INDICATORS, YEARS, country_facts, load
from ppt_wdi_factory.plan import canonical, sha
from tools import pptx_title_size_guard as package_guard

P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
C = "{http://schemas.openxmlformats.org/drawingml/2006/chart}"
X = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
SCHEMA = "ppt-wdi-original-frozen-oracle-v1"
LOCATIONS = {"summary": ("ppt/slides/slide1.xml", "target__summary"),
             "ledger": ("ppt/slides/slide4.xml", "table:1:1"),
             "interpretation": ("ppt/slides/slide5.xml", "target__interpretation"),
             "decision": ("ppt/slides/slide6.xml", "target__decision"),
             "attribution": ("ppt/slides/slide7.xml", "target__attribution")}
LEGEND_LOCATIONS = {"legend_cpi": (0, "B1"),
                    "legend_unemployment": (1, "D1")}
FINAL_TARGETS = {
    "source_year_reconciliation": ["summary", "ledger", "interpretation", "attribution"],
    "chart_series_relabel": ["summary", "legend_cpi", "legend_unemployment", "interpretation"],
}
DEFAULT_FINAL_TARGETS = ["summary", "ledger", "interpretation", "decision"]


def _shape(slide: ET.Element, name: str) -> ET.Element:
    matches = [shape for shape in slide.iter(P + "sp")
               if (c := shape.find(P + "nvSpPr/" + P + "cNvPr")) is not None and c.get("name") == name]
    if len(matches) != 1:
        raise ValueError("Named shape absent or ambiguous: " + name)
    return matches[0]


def _target_node(slide: ET.Element, location: str) -> ET.Element:
    if location.startswith("table:"):
        _, row, col = location.split(":")
        tables = list(slide.iter(A + "tbl"))
        if len(tables) != 1:
            raise ValueError("Expected one table on target slide")
        return list(list(tables[0].iter(A + "tr"))[int(row)].iter(A + "tc"))[int(col)]
    return _shape(slide, location)


def _text(node: ET.Element) -> str:
    return "".join((n.text or "") for n in node.iter(A + "t"))


def _set_text(node: ET.Element, value: str) -> None:
    texts = list(node.iter(A + "t"))
    if len(texts) != 1:
        raise ValueError("Offline fixture requires one run at target")
    texts[0].text = value


def _slidable(part: str) -> bool:
    return part.startswith("ppt/slides/slide") and part.endswith(".xml")


def _chart_and_workbook_parts(members: dict[str, bytes]) -> tuple[str, str]:
    charts = [name for name in members if "/charts/chart" in name and name.endswith(".xml")]
    workbooks = [name for name in members if name.startswith("ppt/embeddings/") and name.endswith(".xlsx")]
    if len(charts) != 1 or len(workbooks) != 1:
        raise ValueError("Expected one chart and its unique embedded workbook")
    return charts[0], workbooks[0]


def _workbook_members(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos = archive.infolist()
        if (len(infos) > 100 or len({info.filename for info in infos}) != len(infos)
                or sum(info.file_size for info in infos) > 10_000_000
                or any(info.file_size > 5_000_000 or ".." in Path(info.filename).parts
                       for info in infos)):
            raise ValueError("Embedded chart workbook is unsafe or oversized")
        return {info.filename: archive.read(info) for info in infos if not info.is_dir()}


def _workbook_header(sheet: ET.Element, cell_ref: str) -> ET.Element:
    matches = [cell for cell in sheet.iter(X + "c") if cell.get("r") == cell_ref]
    if len(matches) != 1:
        raise ValueError("Chart workbook header cell missing or ambiguous")
    texts = list(matches[0].iter(X + "t"))
    if len(texts) != 1:
        raise ValueError("Chart workbook header is not an inline text cell")
    return texts[0]


def _chart_series_name(chart: ET.Element, index: int) -> ET.Element:
    series = list(chart.iter(C + "ser"))
    if len(series) <= index:
        raise ValueError("Chart series missing")
    name = series[index].find(C + "tx/" + C + "v")
    if name is None:
        raise ValueError("Chart series has no literal legend label")
    return name


def _legend_names(members: dict[str, bytes], index: int, cell_ref: str) -> dict[str, str]:
    chart_part, workbook_part = _chart_and_workbook_parts(members)
    chart = package_guard.xml(members[chart_part])
    workbook = _workbook_members(members[workbook_part])
    sheet = package_guard.xml(workbook["xl/worksheets/sheet1.xml"])
    return {"chart": _chart_series_name(chart, index).text or "",
            "workbook": _workbook_header(sheet, cell_ref).text or ""}


def _replace_legend(members: dict[str, bytes], index: int, cell_ref: str,
                    value: str) -> None:
    chart_part, workbook_part = _chart_and_workbook_parts(members)
    chart = package_guard.xml(members[chart_part])
    _chart_series_name(chart, index).text = value
    members[chart_part] = ET.tostring(chart, encoding="utf-8", xml_declaration=True)
    workbook = _workbook_members(members[workbook_part])
    sheet = package_guard.xml(workbook["xl/worksheets/sheet1.xml"])
    _workbook_header(sheet, cell_ref).text = value
    workbook["xl/worksheets/sheet1.xml"] = ET.tostring(sheet, encoding="utf-8", xml_declaration=True)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(workbook):
            archive.writestr(name, workbook[name])
    members[workbook_part] = output.getvalue()


def _masked_chart(data: bytes, indices: list[int]) -> str:
    chart = package_guard.xml(data)
    for index in indices:
        _chart_series_name(chart, index).text = "__PERMITTED_LEGEND_LABEL__"
    return package_guard.canonical(chart)


def _masked_workbook_equal(left: bytes, right: bytes, header_cells: list[str]) -> bool:
    before, after = _workbook_members(left), _workbook_members(right)
    if set(before) != set(after):
        return False
    for name in before:
        if name == "xl/worksheets/sheet1.xml":
            a, b = package_guard.xml(before[name]), package_guard.xml(after[name])
            for cell in header_cells:
                _workbook_header(a, cell).text = "__PERMITTED_LEGEND_LABEL__"
                _workbook_header(b, cell).text = "__PERMITTED_LEGEND_LABEL__"
            if package_guard.canonical(a) != package_guard.canonical(b):
                return False
        elif name.endswith((".xml", ".rels")):
            if package_guard.canonical(package_guard.xml(before[name])) != package_guard.canonical(package_guard.xml(after[name])):
                return False
        elif before[name] != after[name]:
            return False
    return True


def _expected_numeric(facts: dict, workflow: str) -> float:
    y = {year: {
        "NY.GDP.MKTP.CD": round(row["NY.GDP.MKTP.CD"] / 1e9, 1),
        "NY.GDP.PCAP.CD": round(row["NY.GDP.PCAP.CD"], 0),
        "FP.CPI.TOTL.ZG": round(row["FP.CPI.TOTL.ZG"], 2),
        "SP.POP.TOTL": round(row["SP.POP.TOTL"] / 1e6, 2),
        "SL.UEM.TOTL.ZS": round(row["SL.UEM.TOTL.ZS"], 2),
    } for year, row in facts["years"].items()}
    a, b, z = y["2019"], y["2023"], y["2024"]
    gdp = (z["NY.GDP.MKTP.CD"] / b["NY.GDP.MKTP.CD"] - 1) * 100
    pc = (z["NY.GDP.PCAP.CD"] / b["NY.GDP.PCAP.CD"] - 1) * 100
    equations = {
        "nominal_output_growth": gdp,
        "per_capita_growth": pc,
        "inflation_acceleration": z["FP.CPI.TOTL.ZG"] - b["FP.CPI.TOTL.ZG"],
        "labor_rate_change": z["SL.UEM.TOTL.ZS"] - a["SL.UEM.TOTL.ZS"],
        "population_growth": (z["SP.POP.TOTL"] / a["SP.POP.TOTL"] - 1) * 100,
        "output_per_person_divergence": gdp - pc,
        "price_labor_spread": z["FP.CPI.TOTL.ZG"] - z["SL.UEM.TOTL.ZS"],
        "dual_threshold_review": max(z["FP.CPI.TOTL.ZG"] - 5, z["SL.UEM.TOTL.ZS"] - 6),
        "source_year_reconciliation": z["FP.CPI.TOTL.ZG"],
        "chart_series_relabel": z["FP.CPI.TOTL.ZG"] - z["SL.UEM.TOTL.ZS"],
    }
    return round(equations[workflow], 2)


def _validate_task_source(task: dict) -> None:
    if task.get("schema") != "ppt-wdi-original-candidates-v1" or task.get("source_snapshot_sha256") != EXPECTED_SHA256:
        raise ValueError("Task/source schema mismatch")
    actual = country_facts(load(), task["source_group"])
    if task["country_name"] != actual["name"] or task["facts"] != actual["years"]:
        raise ValueError("Task source observations differ from pinned WDI")
    if task["calculation"]["value"] != _expected_numeric(actual, task["workflow"]):
        raise ValueError("Task target is not independently derived from WDI")
    display = f"{task['calculation']['value']:+.2f} {task['calculation']['unit']}"
    if display not in task["correct"]["summary"] or display not in task["correct"]["ledger"]:
        raise ValueError("Correct answer does not contain independently derived value")
    if task["workflow"] == "source_year_reconciliation":
        stale_year = task["calculation"]["wrong_source_year"]
        stale = round(actual["years"][stale_year]["FP.CPI.TOTL.ZG"], 2)
        if (stale_year == "2024" or task["calculation"]["wrong_value"] != stale
                or "FP.CPI.TOTL.ZG; 2024 observation for the 2024 review" not in task["correct"]["attribution"]
                or f"{task['calculation']['value']:+.2f}%" not in task["correct"]["attribution"]
                or f"FP.CPI.TOTL.ZG; {stale_year} observation for the 2024 review" not in task["draft"]["attribution"]
                or f"{stale:+.2f}%" not in task["draft"]["attribution"]):
            raise ValueError("Source-year attribution does not match WDI observations")
    if task["workflow"] == "chart_series_relabel":
        if (task["correct"]["legend_cpi"] != "CPI inflation"
                or task["correct"]["legend_unemployment"] != "Unemployment"
                or task["draft"]["legend_cpi"] != "Unemployment"
                or task["draft"]["legend_unemployment"] != "CPI inflation"):
            raise ValueError("Chart legend correction is not the intended WDI mapping")
    for key in task["target_keys"]:
        if task["correct"][key] == task["draft"][key]:
            raise ValueError("Target is already correct: " + key)
    if task["split"] == "final_candidate" and task["target_keys"] != FINAL_TARGETS.get(
            task["workflow"], DEFAULT_FINAL_TARGETS):
        raise ValueError("Final task lacks its four workflow-specific dependent edits")


def _source_table(members: dict[str, bytes], task: dict) -> None:
    slide = package_guard.xml(members["ppt/slides/slide2.xml"])
    tables = list(slide.iter(A + "tbl"))
    if len(tables) != 1:
        raise ValueError("Evidence table is not native")
    rows = list(tables[0].iter(A + "tr"))
    if len(rows) != 7:
        raise ValueError("Evidence table year count changed")
    for row, year in zip(rows[1:], YEARS):
        cells = list(row.iter(A + "tc"))
        v = task["facts"][year]
        expected = [year, f"{v['NY.GDP.MKTP.CD']/1e9:.1f}", f"{v['NY.GDP.PCAP.CD']:.0f}",
                    f"{v['FP.CPI.TOTL.ZG']:.2f}", f"{v['SP.POP.TOTL']/1e6:.2f}",
                    f"{v['SL.UEM.TOTL.ZS']:.2f}"]
        if [_text(cell) for cell in cells] != expected:
            raise ValueError("Evidence table differs from authentic WDI rows")
    chart_part, workbook_part = _chart_and_workbook_parts(members)
    chart = package_guard.xml(members[chart_part])
    workbook = _workbook_members(members[workbook_part])
    sheet = package_guard.xml(workbook["xl/worksheets/sheet1.xml"])
    series = list(chart.iter(C + "ser"))
    if len(series) != len(task["chart"]["series"]):
        raise ValueError("Native chart series count differs")
    workflow = task["workflow"]
    if workflow == "nominal_output_growth":
        sources = [("NY.GDP.MKTP.CD", 1e9, 1, "GDP")]
    elif workflow in ("per_capita_growth", "output_per_person_divergence"):
        sources = [("NY.GDP.PCAP.CD", 1, 0, "GDP per capita")]
    elif workflow == "population_growth":
        sources = [("SP.POP.TOTL", 1e6, 2, "Population")]
    elif workflow in ("price_labor_spread", "dual_threshold_review", "chart_series_relabel"):
        names = (("Unemployment", "CPI inflation") if workflow == "chart_series_relabel"
                 else ("CPI inflation", "Unemployment"))
        sources = [("FP.CPI.TOTL.ZG", 1, 2, names[0]),
                   ("SL.UEM.TOTL.ZS", 1, 2, names[1])]
    elif workflow == "labor_rate_change":
        sources = [("SL.UEM.TOTL.ZS", 1, 2, "Unemployment")]
    else:
        sources = [("FP.CPI.TOTL.ZG", 1, 2, "CPI inflation")]
    if len(sources) != len(series):
        raise ValueError("Unexpected chart source-series contract")
    for index, (node, declared, source) in enumerate(zip(series, task["chart"]["series"], sources)):
        indicator, divisor, precision, expected_name = source
        expected_values = [round(task["facts"][year][indicator] / divisor, precision) for year in YEARS]
        values = [float(p.findtext(C + "v")) for p in node.find(C + "val").iter(C + "pt")]
        column = "B" if index == 0 else "D"
        workbook_values = []
        for row_number in range(2, 8):
            cell_ref = f"{column}{row_number}"
            cells = [cell for cell in sheet.iter(X + "c") if cell.get("r") == cell_ref]
            if len(cells) != 1:
                raise ValueError("Chart workbook value cell missing")
            workbook_values.append(float(cells[0].findtext(X + "v")))
        if values != expected_values or workbook_values != expected_values or declared["values"] != expected_values:
            raise ValueError("Native chart values differ from WDI")
        cell_ref = "B1" if index == 0 else "D1"
        if set(_legend_names(members, index, cell_ref).values()) != {expected_name} or declared["name"] != expected_name:
            raise ValueError("Chart/cache/workbook series labels disagree")


def freeze(source: Path, task: dict) -> dict:
    _validate_task_source(task)
    raw, members = package_guard.package(source)
    slides = sorted(n for n in members if _slidable(n))
    if len(slides) != 7:
        raise ValueError("Expected seven-slide source deck")
    _source_table(members, task)
    targets = {}
    for key in task["target_keys"]:
        if key in LEGEND_LOCATIONS:
            index, cell_ref = LEGEND_LOCATIONS[key]
            part, workbook_part = _chart_and_workbook_parts(members)
            observed = _legend_names(members, index, cell_ref)
            if set(observed.values()) != {task["draft"][key]}:
                raise ValueError("Chart/workbook baseline legend differs from task draft")
            targets[key] = {"kind": "legend", "part": part,
                            "workbook_part": workbook_part, "series_index": index,
                            "header_cell": cell_ref, "baseline": task["draft"][key],
                            "correct": task["correct"][key]}
        else:
            part, location = LOCATIONS[key]
            baseline = _text(_target_node(package_guard.xml(members[part]), location))
            if baseline != task["draft"][key]:
                raise ValueError("Baseline target differs from frozen task draft: " + key)
            targets[key] = {"kind": "text", "part": part, "location": location,
                            "baseline": baseline, "correct": task["correct"][key]}
    return {"schema": SCHEMA, "source_sha256": sha(raw), "task_sha256": sha(canonical(task)),
            "task_id": task["task_id"], "source_snapshot_sha256": EXPECTED_SHA256,
            "targets": targets, "office_web_normalized": False,
            "scope": "offline source OOXML; freeze again from untouched Microsoft-normalized download",
            "official_final_credit": 0}


def _canonical_target_slide(data: bytes, target_locations: list[str]) -> str:
    root = package_guard.xml(data)
    for location in target_locations:
        node = _target_node(root, location)
        _set_text(node, "__PERMITTED_TARGET_TEXT__")
    return package_guard.canonical(root)


def verify(source: Path, attempt: Path, oracle: dict) -> dict:
    try:
        if oracle.get("schema") != SCHEMA:
            raise ValueError("Oracle schema mismatch")
        original, before = package_guard.package(source)
        if sha(original) != oracle["source_sha256"]:
            raise ValueError("Frozen source artifact changed")
        _, after = package_guard.package(attempt)
        values = {}
        by_part: dict[str, list[str]] = {}
        legend_chart_part = legend_workbook_part = None
        legend_indices: list[int] = []
        legend_cells: list[str] = []
        missing_targets = set()
        for key, target in oracle["targets"].items():
            part = target["part"]
            if target["kind"] == "legend":
                legend_chart_part, legend_workbook_part = part, target["workbook_part"]
                legend_indices.append(target["series_index"])
                legend_cells.append(target["header_cell"])
                try:
                    observed = _legend_names(after, target["series_index"], target["header_cell"])
                except (KeyError, ValueError, IndexError, zipfile.BadZipFile):
                    observed = None
                    missing_targets.update((part, target["workbook_part"]))
                values[key] = {"correct": observed is not None and
                               all(value == target["correct"] for value in observed.values()),
                               "changed": observed is None or
                               any(value != target["baseline"] for value in observed.values())}
            else:
                location = target["location"]
                by_part.setdefault(part, []).append(location)
                try:
                    observed = _text(_target_node(package_guard.xml(after[part]), location))
                except (KeyError, ValueError, IndexError):
                    # A valid deck whose target object was deleted or renamed
                    # is a candidate failure, not an infrastructure outage.
                    observed = None
                    missing_targets.add(part)
                values[key] = {"correct": observed == target["correct"],
                               "changed": observed != target["baseline"]}
        unexpected = set(before) ^ set(after)
        unexpected.update(missing_targets)
        for name in set(before) & set(after):
            if before[name] == after[name]:
                continue
            if name == legend_chart_part:
                try:
                    equal = _masked_chart(before[name], legend_indices) == _masked_chart(after[name], legend_indices)
                except (ValueError, IndexError):
                    equal = False
            elif name == legend_workbook_part:
                try:
                    equal = _masked_workbook_equal(before[name], after[name], legend_cells)
                except (ValueError, IndexError, KeyError, zipfile.BadZipFile):
                    equal = False
            elif name in by_part:
                try:
                    equal = _canonical_target_slide(before[name], by_part[name]) == _canonical_target_slide(after[name], by_part[name])
                except (ValueError, IndexError):
                    equal = False
            elif oracle["office_web_normalized"] and name in package_guard.OFFICE_DERIVED_PARTS:
                equal = package_guard.office_derived_part_equal(name, before[name], after[name])
            elif name.endswith((".xml", ".rels")):
                equal = package_guard.canonical(package_guard.xml(before[name])) == package_guard.canonical(package_guard.xml(after[name]))
            else:
                equal = False
            if not equal:
                unexpected.add(name)
        correct = bool(values) and all(row["correct"] for row in values.values())
        preservation = not unexpected
        return {"status": "scored", "score": float(correct and preservation),
                "target_correct": correct, "preservation_pass": preservation,
                "per_target": values, "unexpected_parts": sorted(unexpected),
                "gui_provenance": "unverified", "official_final_credit": 0}
    except (package_guard.ArtifactUnavailable, OSError, ValueError, KeyError, TypeError,
            ET.ParseError, zipfile.BadZipFile) as error:
        return {"status": "infrastructure_error", "score": None,
                "error_type": type(error).__name__, "official_final_credit": 0}


def _write_variant(source: Path, path: Path, mutations: dict[str, str], oracle: dict,
                   *, collateral: bool = False, chart_damage: bool = False,
                   legend_desync: bool = False) -> None:
    _, members = package_guard.package(source)
    changed = dict(members)
    for key, value in mutations.items():
        target = oracle["targets"][key]
        if target["kind"] == "legend":
            _replace_legend(changed, target["series_index"], target["header_cell"], value)
        else:
            part = target["part"]
            root = package_guard.xml(changed[part])
            _set_text(_target_node(root, target["location"]), value)
            changed[part] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    if collateral:
        part = "ppt/slides/slide7.xml"
        root = package_guard.xml(changed[part])
        node = _shape(root, "method_3")
        _set_text(node, _text(node) + " Unauthorized collateral change.")
        changed[part] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    if chart_damage:
        part = next(n for n in changed if n.endswith(".xml") and "/charts/chart" in n)
        root = package_guard.xml(changed[part])
        value = next(root.iter(C + "val")).find(".//" + C + "v")
        value.text = str(float(value.text) + 1.0)
        changed[part] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    if legend_desync:
        target = oracle["targets"]["legend_cpi"]
        part = target["workbook_part"]
        workbook = _workbook_members(changed[part])
        sheet = package_guard.xml(workbook["xl/worksheets/sheet1.xml"])
        _workbook_header(sheet, target["header_cell"]).text = target["baseline"]
        workbook["xl/worksheets/sheet1.xml"] = ET.tostring(sheet, encoding="utf-8", xml_declaration=True)
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in sorted(workbook):
                archive.writestr(name, workbook[name])
        changed[part] = output.getvalue()
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(changed):
            archive.writestr(name, changed[name])
    path.chmod(0o600)


def calibrate(package: Path) -> dict:
    source = package / "source.pptx"
    task_path = package / "task.private.json"
    task = json.loads(task_path.read_bytes())
    frozen = freeze(source, task)
    oracle_path = package / "oracle.private.json"
    oracle_bytes = canonical(frozen)
    if oracle_path.exists() and oracle_path.read_bytes() != oracle_bytes:
        raise ValueError("Existing frozen oracle differs")
    if not oracle_path.exists():
        oracle_path.write_bytes(oracle_bytes)
        oracle_path.chmod(0o600)
    targets = {key: row["correct"] for key, row in frozen["targets"].items()}
    control = package / "controls"
    positive = control / "positive.pptx"
    near = control / "near-miss.pptx"
    collateral = control / "collateral.pptx"
    wrong_chart = control / "wrong-chart.pptx"
    for path, changes, damage, chart_damage in (
        (positive, targets, False, False),
        (near, {next(iter(targets)): next(iter(targets.values()))} if len(targets) > 1 else {}, False, False),
        (collateral, targets, True, False),
        (wrong_chart, targets, False, True),
    ):
        if not path.exists():
            _write_variant(source, path, changes, frozen, collateral=damage, chart_damage=chart_damage)
    legend_desync = control / "legend-desync.pptx"
    if "legend_cpi" in targets and not legend_desync.exists():
        _write_variant(source, legend_desync, targets, frozen, legend_desync=True)
    checks = {"baseline": verify(source, source, frozen),
              "positive": verify(source, positive, frozen),
              "near_miss": verify(source, near, frozen),
              "collateral": verify(source, collateral, frozen),
              "wrong_chart": verify(source, wrong_chart, frozen)}
    if "legend_cpi" in targets:
        checks["legend_desync"] = verify(source, legend_desync, frozen)
    valid = (checks["baseline"]["status"] == "scored" and checks["baseline"]["score"] == 0
             and checks["positive"]["score"] == 1
             and checks["near_miss"]["score"] == 0 and checks["near_miss"]["preservation_pass"]
             and checks["collateral"]["score"] == 0 and checks["collateral"]["target_correct"]
             and not checks["collateral"]["preservation_pass"]
             and checks["wrong_chart"]["score"] == 0 and checks["wrong_chart"]["target_correct"]
             and not checks["wrong_chart"]["preservation_pass"])
    if "legend_desync" in checks:
        valid = (valid and checks["legend_desync"]["status"] == "scored"
                 and checks["legend_desync"]["score"] == 0
                 and not checks["legend_desync"]["target_correct"]
                 and checks["legend_desync"]["preservation_pass"])
    receipt = {"schema": "ppt-wdi-original-offline-calibration-v1",
               "task_id": task["task_id"], "source_sha256": frozen["source_sha256"],
               "oracle_sha256": sha(oracle_bytes), "checks": checks,
               "offline_controls_pass": bool(valid), "gui_admitted": False,
               "official_final_credit": 0}
    receipt_path = package / "calibration.private.json"
    data = canonical(receipt)
    if receipt_path.exists() and receipt_path.read_bytes() != data:
        raise ValueError("Existing calibration receipt differs")
    if not receipt_path.exists():
        receipt_path.write_bytes(data)
        receipt_path.chmod(0o600)
    return {"task_id": task["task_id"], "offline_controls_pass": bool(valid),
            "source_sha256": frozen["source_sha256"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    plan = json.loads((args.private_root / "candidate-plan.private.json").read_bytes())
    rows = [r for split in ("train", "selection", "final_candidate") for r in plan["sets"][split]]
    if args.limit:
        rows = rows[:args.limit]
    result = [calibrate(args.private_root / "packages" / r["split"] / r["task_id"])
              for r in rows]
    if args.limit is None:
        if len(result) != 140 or not all(r["offline_controls_pass"] for r in result):
            raise ValueError("Full calibration requires 140 passing candidates")
        receipt_hashes = [sha((args.private_root / "packages" / r["split"] / r["task_id"] /
                              "calibration.private.json").read_bytes()) for r in rows]
        run_receipt = {"schema": "ppt-wdi-original-calibration-run-v1",
                       "plan_sha256": sha((args.private_root / "candidate-plan.private.json").read_bytes()),
                       "verifier_sha256": sha(Path(__file__).read_bytes()),
                       "calibration_receipts_commitment_sha256": sha(canonical(receipt_hashes)),
                       "candidate_count": len(result), "offline_passed": len(result),
                       "official_final_credit": 0}
        destination = args.private_root / "calibration-run.private.json"
        data = canonical(run_receipt)
        if destination.exists() and destination.read_bytes() != data:
            raise ValueError("Existing calibration run receipt differs")
        if not destination.exists():
            destination.write_bytes(data)
            destination.chmod(0o600)
    print(json.dumps({"calibrated": len(result),
                      "offline_passed": sum(r["offline_controls_pass"] for r in result),
                      "official_final_credit": 0}))


if __name__ == "__main__":
    main()
