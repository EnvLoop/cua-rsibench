"""Independent saved-artifact checks for native LibreOffice task packages.

The verifier runs outside the desktop and reads the actor's saved OOXML bytes
before any trusted postprocessing.  It does not call LibreOffice, inspect the
GUI session, or credit a text response.  PNG screenshots are observational.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile


S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _zip(raw: bytes, required: tuple[str, ...]) -> zipfile.ZipFile:
    try:
        if len(raw) > 20 * 1024 * 1024:
            raise ValueError("OOXML archive exceeds size limit")
        z = zipfile.ZipFile(io.BytesIO(raw))
        if len(z.infolist()) > 3000 or sum(item.file_size for item in z.infolist()) > 50 * 1024 * 1024:
            raise ValueError("OOXML expanded contents exceed size limit")
        if z.testzip() is not None or not all(name in z.namelist() for name in required):
            raise ValueError("OOXML archive is corrupt or missing required parts")
        return z
    except zipfile.BadZipFile:
        raise ValueError("Invalid OOXML ZIP") from None


def _xml(raw: bytes) -> ET.Element:
    try:
        return ET.fromstring(raw)
    except ET.ParseError:
        raise ValueError("Invalid OOXML XML") from None


def _scalar(value: str | None, kind: str | None, shared: list[str]) -> str | None:
    if value is None:
        return None
    if kind == "s":
        try:
            return shared[int(value)]
        except (ValueError, IndexError):
            raise ValueError("Invalid shared-string index") from None
    return value


def xlsx_cells(raw: bytes) -> dict[str, dict[str, dict]]:
    with _zip(raw, ("xl/workbook.xml", "xl/_rels/workbook.xml.rels")) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = _xml(z.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in si.findall(f".//{{{S}}}t"))
                      for si in root.findall(f"{{{S}}}si")]
        relationships = _xml(z.read("xl/_rels/workbook.xml.rels"))
        refs = {x.attrib["Id"]: x.attrib["Target"] for x in relationships.findall(f"{{{PR}}}Relationship")}
        workbook = _xml(z.read("xl/workbook.xml"))
        result = {}
        for sheet in workbook.findall(f".//{{{S}}}sheets/{{{S}}}sheet"):
            name, rid = sheet.attrib["name"], sheet.attrib[f"{{{R}}}id"]
            if name in result or rid not in refs:
                raise ValueError("Duplicate or broken workbook sheet")
            target = refs[rid].lstrip("/")
            path = target if target.startswith("xl/") else posixpath.normpath(posixpath.join("xl", target))
            if path not in z.namelist():
                raise ValueError("Missing XLSX worksheet")
            tree = _xml(z.read(path))
            cells = {}
            for cell in tree.findall(f".//{{{S}}}sheetData/{{{S}}}row/{{{S}}}c"):
                address = cell.get("r")
                if not address or address in cells:
                    raise ValueError("Missing or duplicate cell address")
                f = cell.find(f"{{{S}}}f")
                v = cell.find(f"{{{S}}}v")
                inline = cell.find(f"{{{S}}}is")
                value = _scalar(v.text if v is not None else None, cell.get("t"), shared)
                if inline is not None:
                    value = "".join(t.text or "" for t in inline.findall(f".//{{{S}}}t"))
                if value is not None or f is not None:
                    cells[address] = {"formula": f.text if f is not None else None,
                                      "value": value, "kind": cell.get("t")}
            result[name] = cells
        if not result:
            raise ValueError("No XLSX sheets")
        return result


def formula_key(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip().lstrip("=").replace("$", "").replace(";", ",")
    value = value.replace("of:=", "").replace("_xlfn.", "")
    value = re.sub(r"\s+", "", value)
    return value.casefold()


def _same_value(a: str | None, b: str | None) -> bool:
    if a == b:
        return True
    if a is None or b is None:
        return False
    try:
        x, y = float(a), float(b)
    except ValueError:
        return False
    return math.isfinite(x) and math.isfinite(y) and math.isclose(x, y, rel_tol=1e-12, abs_tol=1e-6)


def verify_calc(baseline: bytes, saved: bytes, oracle: dict) -> dict:
    before, after = xlsx_cells(baseline), xlsx_cells(saved)
    if set(before) != set(after):
        return {"passed": False, "reason": "worksheet_set_changed"}
    targets = {tuple(address.split("!", 1)): rule for address, rule in oracle["targets"].items()}
    if any(len(key) != 2 for key in targets):
        return {"passed": False, "reason": "invalid_oracle_target"}
    errors = []
    for sheet in before:
        if set(before[sheet]) != set(after[sheet]):
            errors.append(f"cell_set_changed:{sheet}")
            continue
        for addr, old in before[sheet].items():
            new = after[sheet][addr]
            if (sheet, addr) in targets:
                rule = targets[(sheet, addr)]
                if formula_key(new["formula"]) != formula_key(rule["formula"]):
                    errors.append(f"target_formula_wrong:{sheet}!{addr}")
                try:
                    cached = float(new["value"])
                except (ValueError, TypeError):
                    errors.append(f"target_cached_result_missing:{sheet}!{addr}")
                else:
                    if not math.isclose(cached, rule["expected_value"], rel_tol=2e-10, abs_tol=1e-6):
                        errors.append(f"target_cached_result_wrong:{sheet}!{addr}")
            else:
                same_formula = formula_key(old["formula"]) == formula_key(new["formula"])
                # LibreOffice recalculates cached values for formulas that
                # openpyxl intentionally left uncached.  The formula itself is
                # immutable, and source observations are checked separately.
                same_value = (True if old["formula"] is not None and old["value"] is None
                              else _same_value(old["value"], new["value"]))
                if not same_formula or not same_value:
                    errors.append(f"non_target_changed:{sheet}!{addr}")
    for sheet, addr in targets:
        if sheet not in before or addr not in before[sheet]:
            errors.append(f"target_missing:{sheet}!{addr}")
    return {"passed": not errors and digest(baseline) != digest(saved), "errors": errors,
            "target_count": len(targets), "non_target_cells": sum(len(c) for c in before.values()) - len(targets)}


def _slide_names(z: zipfile.ZipFile) -> list[str]:
    presentation = _xml(z.read("ppt/presentation.xml"))
    relationships = _xml(z.read("ppt/_rels/presentation.xml.rels"))
    refs = {rel.get("Id"): rel.get("Target") for rel in relationships.findall(f"{{{PR}}}Relationship")}
    ids = presentation.findall(f".//{{{P}}}sldIdLst/{{{P}}}sldId")
    names = []
    for entry in ids:
        rid = entry.get(f"{{{R}}}id")
        if rid not in refs:
            raise ValueError("PPTX slide relationship missing")
        target = refs[rid].lstrip("/")
        path = target if target.startswith("ppt/") else posixpath.normpath(posixpath.join("ppt", target))
        if path not in z.namelist() or not re.fullmatch(r"ppt/slides/slide\d+\.xml", path):
            raise ValueError("PPTX slide path invalid")
        names.append(path)
    if len(names) != len(set(names)):
        raise ValueError("Duplicate PPTX slide reference")
    return names


def pptx_slide_shapes(raw: bytes) -> list[list[str]]:
    with _zip(raw, ("ppt/presentation.xml", "ppt/_rels/presentation.xml.rels")) as z:
        names = _slide_names(z)
        if not names:
            raise ValueError("PPTX has no slides")
        result = []
        for name in names:
            tree = _xml(z.read(name))
            shapes = []
            for shape in tree.findall(f".//{{{P}}}sp"):
                text = "\n".join("".join(t.text or "" for t in para.findall(f".//{{{A}}}t"))
                                 for para in shape.findall(f".//{{{A}}}p"))
                if text.strip():
                    shapes.append(text.strip())
            result.append(shapes)
        return result


def pptx_layout(raw: bytes) -> tuple[tuple[int, int], list[list[tuple[int, int, int, int]]]]:
    """Read slide dimensions and every text shape's position/extent in EMU."""
    with _zip(raw, ("ppt/presentation.xml", "ppt/_rels/presentation.xml.rels")) as z:
        presentation = _xml(z.read("ppt/presentation.xml"))
        slide_size = presentation.find(f"{{{P}}}sldSz")
        if slide_size is None:
            raise ValueError("PPTX slide size missing")
        size = (int(slide_size.get("cx")), int(slide_size.get("cy")))
        names = _slide_names(z)
        layouts = []
        for name in names:
            tree = _xml(z.read(name))
            shapes = []
            for shape in tree.findall(f".//{{{P}}}sp"):
                text = "".join(t.text or "" for t in shape.findall(f".//{{{A}}}t"))
                if not text.strip():
                    continue
                xfrm = shape.find(f"{{{P}}}spPr/{{{A}}}xfrm")
                if xfrm is None:
                    raise ValueError("PPTX text shape has no own geometry")
                off, ext = xfrm.find(f"{{{A}}}off"), xfrm.find(f"{{{A}}}ext")
                if off is None or ext is None:
                    raise ValueError("PPTX text shape transform incomplete")
                shapes.append((int(off.get("x")), int(off.get("y")),
                               int(ext.get("cx")), int(ext.get("cy"))))
            layouts.append(shapes)
        return size, layouts


def pptx_shape_structure(raw: bytes) -> list[list[str]]:
    """Track all drawable object kinds, including those without text."""
    with _zip(raw, ("ppt/presentation.xml", "ppt/_rels/presentation.xml.rels")) as z:
        result = []
        for name in _slide_names(z):
            tree = _xml(z.read(name))
            container = tree.find(f".//{{{P}}}spTree")
            if container is None:
                raise ValueError("PPTX shape tree missing")
            result.append([child.tag for child in container
                           if child.tag not in (f"{{{P}}}nvGrpSpPr", f"{{{P}}}grpSpPr")])
        return result


def verify_impress(baseline: bytes, saved: bytes, oracle: dict) -> dict:
    before, after = pptx_slide_shapes(baseline), pptx_slide_shapes(saved)
    size_before, layout_before = pptx_layout(baseline)
    size_after, layout_after = pptx_layout(saved)
    errors = []
    if pptx_shape_structure(baseline) != pptx_shape_structure(saved):
        errors.append("slide_drawable_structure_changed")
    if size_before != size_after:
        errors.append("slide_canvas_changed")
    target_slide = oracle["target_slide"] - 1
    if len(before) != len(after):
        errors.append("slide_count_changed")
    if [len(s) for s in before] != [len(s) for s in after]:
        errors.append("text_shape_counts_changed")
    if len(before) == len(after) and [len(s) for s in before] == [len(s) for s in after]:
        for i, (old_shapes, new_shapes) in enumerate(zip(before, after)):
            for j, (old, new) in enumerate(zip(old_shapes, new_shapes)):
                if i == target_slide and old in oracle["targets"]:
                    if new != oracle["targets"][old]:
                        errors.append(f"target_text_wrong:slide{i+1}:shape{j+1}")
                elif old != new:
                    errors.append(f"non_target_text_changed:slide{i+1}:shape{j+1}")
                try:
                    start, end = layout_before[i][j], layout_after[i][j]
                except IndexError:
                    errors.append(f"shape_geometry_missing:slide{i+1}:shape{j+1}")
                    continue
                # Native PPTX round trips may move by one screen subpixel.
                # A material geometry change in an untouched shape fails.
                tolerance = 0.02 * 914400  # 0.02 in in OOXML EMU.
                checked = range(3) if i == target_slide and old in oracle["targets"] else range(4)
                if any(abs(start[k] - end[k]) > tolerance for k in checked):
                    errors.append(f"shape_geometry_changed:slide{i+1}:shape{j+1}")
    for placeholder in oracle["targets"]:
        if target_slide >= len(before) or before[target_slide].count(placeholder) != 1:
            errors.append(f"placeholder_missing_or_duplicate:{placeholder}")
    return {"passed": not errors and digest(baseline) != digest(saved), "errors": errors,
            "slide_count": len(before), "target_count": len(oracle["targets"])}


def docx_content(raw: bytes) -> dict:
    with _zip(raw, ("word/document.xml",)) as z:
        tree = _xml(z.read("word/document.xml"))
        body = tree.find(f"{{{W}}}body")
        if body is None:
            raise ValueError("DOCX body missing")
        paragraphs = []
        tables = []
        for child in body:
            if child.tag == f"{{{W}}}p":
                paragraphs.append("".join(node.text or "" for node in child.findall(f".//{{{W}}}t")))
            elif child.tag == f"{{{W}}}tbl":
                rows = []
                for tr in child.findall(f"{{{W}}}tr"):
                    rows.append(["".join(node.text or "" for node in tc.findall(f".//{{{W}}}t"))
                                 for tc in tr.findall(f"{{{W}}}tc")])
                tables.append(rows)
        return {"paragraphs": paragraphs, "tables": tables}


def verify_writer(baseline: bytes, saved: bytes, oracle: dict) -> dict:
    before, after = docx_content(baseline), docx_content(saved)
    errors = []
    if before["tables"] != after["tables"]:
        errors.append("source_table_changed")
    old, new = before["paragraphs"], after["paragraphs"]
    if len(old) != len(new):
        errors.append("paragraph_count_changed")
    else:
        for i, (left, right) in enumerate(zip(old, new)):
            if left in oracle["targets"]:
                if right != oracle["targets"][left]:
                    errors.append(f"target_text_wrong:paragraph{i+1}")
            elif left != right:
                errors.append(f"non_target_text_changed:paragraph{i+1}")
    for placeholder in oracle["targets"]:
        if old.count(placeholder) != 1:
            errors.append(f"placeholder_missing_or_duplicate:{placeholder}")
    return {"passed": not errors and digest(baseline) != digest(saved), "errors": errors,
            "paragraph_count": len(old), "table_count": len(before["tables"]),
            "target_count": len(oracle["targets"])}


def verify(baseline: bytes, saved: bytes, oracle: dict) -> dict:
    if oracle.get("schema") != "cua-native-wdi-oracle-v1" or digest(baseline) != oracle.get("input_sha256"):
        raise ValueError("Oracle schema or baseline bytes changed")
    workflow = oracle["workflow"]
    if workflow.startswith("calc-"):
        result = verify_calc(baseline, saved, oracle)
    elif workflow == "impress-deck":
        result = verify_impress(baseline, saved, oracle)
    elif workflow == "writer-brief":
        result = verify_writer(baseline, saved, oracle)
    else:
        raise ValueError("Unknown workflow")
    return {"schema": "cua-native-wdi-saved-verifier-v1", "task_id": oracle["task_id"],
            "baseline_sha256": digest(baseline), "saved_sha256": digest(saved), **result}
