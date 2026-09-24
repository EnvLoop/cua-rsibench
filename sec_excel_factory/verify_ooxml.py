"""Independent, offline OOXML verifier for the SEC Excel restoration task.

This deliberately does not import the workbook builder or use Excel cached values
as the score. It reads the frozen SEC source, recomputes the expected model, and
evaluates a small explicit arithmetic/reference formula grammar from OOXML.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from extract_sec import ISSUERS, METRICS, is_annual, read_source


NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
SHEET_ORDER = ["Committee View", "FY Selection", "Drivers", "Forecast", "Raw SEC"]
MAX_UNPACKED_BYTES = 100_000_000
TOKEN = re.compile(r"\s*(?:(?P<number>(?:\d+\.?\d*|\.\d+)(?:[Ee][+-]?\d+)?)|(?P<ref>(?:(?:'[^']+'|[A-Za-z_][A-Za-z0-9_]*)!)?\$?[A-Z]{1,3}\$?\d+)|(?P<op>[()+\-*/]))")
REF = re.compile(r"(?:(?:'(?P<quoted>[^']+)'|(?P<plain>[A-Za-z_][A-Za-z0-9_]*))!)?(?P<cell>\$?[A-Z]{1,3}\$?\d+)$")


@dataclass(frozen=True)
class Cell:
    value: str | None
    formula: str | None
    type: str | None


def _value(c: ET.Element, shared: list[str]) -> str | None:
    v = c.find("m:v", NS)
    if v is not None and v.text is not None:
        if c.attrib.get("t") == "s":
            return shared[int(v.text)]
        return v.text
    inline = c.find("m:is/m:t", NS)
    return inline.text if inline is not None else None


def _shared_strings(z: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    return ["".join(t.text or "" for t in si.findall(".//m:t", NS)) for si in root.findall("m:si", NS)]


def load_xlsx(path: Path) -> tuple[dict[str, dict[str, Cell]], list[str], list[tuple[str, str]], dict[str, list[str]]]:
    with ZipFile(path) as z:
        infos = z.infolist()
        member_names = [item.filename for item in infos]
        if len(member_names) != len(set(member_names)) or sum(item.file_size for item in infos) > MAX_UNPACKED_BYTES:
            raise ValueError("duplicate_or_oversized_ooxml_package")
        if any(PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts
               for name in member_names):
            raise ValueError("unsafe_ooxml_path")
        names = set(member_names)
        for name in names:
            if name.endswith((".xml", ".rels")):
                data = z.read(name)
                if b"<!DOCTYPE" in data or b"<!ENTITY" in data:
                    raise ValueError("ooxml_entities_not_accepted")
        if any(n.startswith("xl/externalLinks/") or n.endswith("vbaProject.bin") for n in names):
            raise ValueError("external_link_or_macro")
        workbook = ET.fromstring(z.read("xl/workbook.xml"))
        relroot = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        rels = {e.attrib["Id"]: e.attrib["Target"] for e in relroot.findall(f"{{{REL_NS}}}Relationship")}
        shared = _shared_strings(z)
        sheets: dict[str, dict[str, Cell]] = {}
        order: list[str] = []
        structures: dict[str, list[str]] = {}
        for s in workbook.findall("m:sheets/m:sheet", NS):
            name = s.attrib["name"]
            order.append(name)
            target = rels[s.attrib[f"{{{NS['r']}}}id"]]
            item = target.lstrip("/") if target.startswith("/") else "xl/" + target
            root = ET.fromstring(z.read(item))
            cells: dict[str, Cell] = {}
            for c in root.findall(".//m:sheetData/m:row/m:c", NS):
                f = c.find("m:f", NS)
                value = _value(c, shared)
                if value is not None or (f is not None and f.text):
                    cells[c.attrib["r"]] = Cell(value, f.text if f is not None else None, c.attrib.get("t"))
            sheets[name] = cells
            structures[name] = []
            for tag in ("mergeCells", "dataValidations", "conditionalFormatting", "autoFilter", "tableParts"):
                for e in root.findall(f"m:{tag}", NS):
                    if tag == "tableParts":
                        # Relationship IDs are exporter-generated; table names
                        # and ranges are checked separately below.
                        structures[name].append(f"tableParts:{e.attrib.get('count', '')}")
                    else:
                        structures[name].append(ET.tostring(e, encoding="unicode"))
        tables = []
        for n in sorted(names):
            if n.startswith("xl/tables/") and n.endswith(".xml"):
                t = ET.fromstring(z.read(n))
                tables.append((t.attrib.get("name", ""), t.attrib.get("ref", "")))
        return sheets, order, sorted(tables), structures


def target_cells() -> set[tuple[str, str]]:
    return {
        *(("FY Selection", f"{col}{row}") for row in range(5, 9) for col in "DEFGHIJK"),
        *(("Drivers", f"{col}{row}") for row in range(5, 7) for col in "BCDE"),
        *(("Forecast", f"{col}{row}") for row in range(5, 9) for col in "CDEFGHI"),
        *(("Committee View", f"{col}{row}") for row in range(5, 7) for col in "BCDEFGHI"),
    }


def _number(c: Cell | None) -> float:
    if c is None or c.value is None:
        raise ValueError("missing_numeric_input")
    return float(c.value)


def expected_values(seed: dict[str, dict[str, Cell]], apple_revenue_delta_usd: int = 0, multiplier_delta: float = 0) -> dict[tuple[str, str], float]:
    # The source lookup here is independent of excerpt.json and the workbook
    # formulas: exact 2024 10-K accession, fiscal end, form, annual duration.
    raw: dict[tuple[str, str, str], float] = {}
    for issuer, spec in ISSUERS.items():
        sec = read_source(spec)
        for metric, concept in METRICS.items():
            for year, end in spec["periods"].items():
                candidates = [
                    x for x in sec["facts"]["us-gaap"][concept]["units"]["USD"]
                    if x["accn"] == spec["filing"] and x["end"] == end
                    and x["form"] == "10-K" and is_annual(x, metric)
                ]
                if len(candidates) != 1:
                    raise ValueError(f"source_ambiguity:{issuer}:{metric}:{year}")
                value = candidates[0]["val"]
                if issuer == "Apple" and year == "2024" and metric == "Revenue":
                    value += apple_revenue_delta_usd
                raw[(issuer, year, metric)] = value / 1_000_000

    out: dict[tuple[str, str], float] = {}
    data: dict[tuple[str, str], dict[str, float]] = {}
    for issuer, year, row in (("Apple", "2023", 5), ("Apple", "2024", 6), ("Microsoft", "2023", 7), ("Microsoft", "2024", 8)):
        data[(issuer, year)] = {metric: raw[(issuer, year, metric)] for metric in METRICS}
        for col, metric in zip("DEFGHIJ", METRICS):
            out[("FY Selection", f"{col}{row}")] = raw[(issuer, year, metric)]
        d = data[(issuer, year)]
        out[("FY Selection", f"K{row}")] = d["Assets"] - d["Liabilities"] - d["Equity"]

    for issuer, dr, r25, r26, vr, ar in (("Apple", 5, 5, 6, 5, 6), ("Microsoft", 6, 7, 8, 6, 8)):
        prev, cur = data[(issuer, "2023")], data[(issuer, "2024")]
        growth = cur["Revenue"] / prev["Revenue"] - 1
        ocf_ratio = cur["Operating cash flow"] / cur["Revenue"]
        capex_ratio = cur["Capital expenditures"] / cur["Revenue"]
        next_growth = growth / 2
        scenario = _number(seed["Drivers"].get(f"F{dr}")) + (multiplier_delta if issuer == "Apple" else 0)
        for col, val in zip("BCDE", (growth, ocf_ratio, capex_ratio, next_growth)):
            out[("Drivers", f"{col}{dr}")] = val
        prior_revenue = cur["Revenue"]
        for row, g in ((r25, growth), (r26, next_growth)):
            revenue = prior_revenue * (1 + g)
            ocf = revenue * ocf_ratio
            capex = revenue * capex_ratio * scenario
            fcf = ocf - capex
            operating_income = revenue * cur["Operating income"] / cur["Revenue"]
            margin = fcf / revenue
            for col, val in zip("CDEFGHI", (prior_revenue, revenue, ocf, capex, fcf, operating_income, margin)):
                out[("Forecast", f"{col}{row}")] = val
            prior_revenue = revenue
        view = (
            cur["Revenue"], cur["Operating cash flow"] - cur["Capital expenditures"],
            growth, cur["Operating income"] / cur["Revenue"],
            out[("Forecast", f"D{r26}")], out[("Forecast", f"G{r26}")],
            out[("Forecast", f"I{r26}")], out[("FY Selection", f"K{ar}")],
        )
        for col, val in zip("BCDEFGHI", view):
            out[("Committee View", f"{col}{vr}")] = val
    if set(out) != target_cells():
        raise ValueError("verifier_target_coverage_error")
    return out


class Evaluator:
    def __init__(self, sheets: dict[str, dict[str, Cell]], overrides: dict[tuple[str, str], float] | None = None):
        self.sheets = sheets
        self.overrides = overrides or {}
        self.cache: dict[tuple[str, str], float] = {}
        self.stack: set[tuple[str, str]] = set()

    def cell(self, sheet: str, addr: str) -> float:
        key = (sheet, addr.replace("$", ""))
        if key in self.overrides:
            return self.overrides[key]
        if key in self.cache:
            return self.cache[key]
        if key in self.stack:
            raise ValueError(f"formula_cycle:{sheet}!{addr}")
        c = self.sheets.get(sheet, {}).get(key[1])
        if c is None:
            raise ValueError(f"missing_cell:{sheet}!{addr}")
        if c.formula is None:
            result = _number(c)
        else:
            self.stack.add(key)
            try:
                result = self.formula(c.formula, sheet)
            finally:
                self.stack.remove(key)
        if not math.isfinite(result):
            raise ValueError(f"nonfinite_result:{sheet}!{addr}")
        self.cache[key] = result
        return result

    def formula(self, expression: str, current_sheet: str) -> float:
        tokens = []
        pos = 0
        while pos < len(expression):
            m = TOKEN.match(expression, pos)
            if m is None:
                raise ValueError(f"unsupported_formula:{current_sheet}:{expression}")
            tokens.append((m.lastgroup, m.group(m.lastgroup)))
            pos = m.end()
        index = 0

        def atom() -> float:
            nonlocal index
            if index >= len(tokens):
                raise ValueError(f"formula_syntax:{expression}")
            kind, val = tokens[index]
            if kind == "op" and val in "+-":
                index += 1
                x = atom()
                return x if val == "+" else -x
            if kind == "op" and val == "(":
                index += 1
                x = add()
                if index >= len(tokens) or tokens[index] != ("op", ")"):
                    raise ValueError(f"formula_parentheses:{expression}")
                index += 1
                return x
            index += 1
            if kind == "number":
                return float(val)
            if kind == "ref":
                ref = REF.fullmatch(val)
                if ref is None:
                    raise ValueError(f"bad_reference:{val}")
                sheet = ref.group("quoted") or ref.group("plain") or current_sheet
                return self.cell(sheet, ref.group("cell"))
            raise ValueError(f"formula_syntax:{expression}")

        def multiply() -> float:
            nonlocal index
            value = atom()
            while index < len(tokens) and tokens[index][0] == "op" and tokens[index][1] in "*/":
                op = tokens[index][1]
                index += 1
                rhs = atom()
                value = value * rhs if op == "*" else value / rhs
            return value

        def add() -> float:
            nonlocal index
            value = multiply()
            while index < len(tokens) and tokens[index][0] == "op" and tokens[index][1] in "+-":
                op = tokens[index][1]
                index += 1
                rhs = multiply()
                value = value + rhs if op == "+" else value - rhs
            return value

        result = add()
        if index != len(tokens):
            raise ValueError(f"formula_tail:{expression}")
        return result


def close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-6)


def unchanged_cell(a: Cell, b: Cell) -> bool:
    """Accept Office's lossless numeric spelling changes, not changed values.

    XLSX numbers are interpreted as IEEE-754 doubles by Excel. For example,
    ``2.18`` and ``2.1800000000000002`` serialize differently but decode to
    the same double. This equivalence applies only to numeric cells with the
    same formula and cannot forgive a substantive source-data change.
    """
    def kind(value: str | None) -> str:
        if value in (None, "n"):
            return "number"
        if value in ("s", "inlineStr", "str"):
            return "text"
        return value

    if a.formula != b.formula or kind(a.type) != kind(b.type):
        return False
    if a.value == b.value:
        return True
    if kind(a.type) != "number" or a.value is None or b.value is None:
        return False
    try:
        left, right = float(a.value), float(b.value)
    except ValueError:
        return False
    return math.isfinite(left) and math.isfinite(right) and left.hex() == right.hex()


def verify(candidate_path: Path, seed_path: Path) -> dict:
    errors: list[str] = []
    try:
        candidate, names, tables, structures = load_xlsx(candidate_path)
        seed, seed_names, seed_tables, seed_structures = load_xlsx(seed_path)
    except Exception as e:
        return {"pass": False, "errors": [f"invalid_xlsx:{e}"]}
    if names != SHEET_ORDER or names != seed_names:
        errors.append("sheet_structure_changed")
    if tables != seed_tables or structures != seed_structures:
        errors.append("table_or_sheet_structure_changed")
    targets = target_cells()
    for sheet in seed_names:
        keys = set(seed[sheet]) | set(candidate.get(sheet, {}))
        for addr in keys:
            if (sheet, addr) in targets:
                continue
            a, b = seed[sheet].get(addr), candidate.get(sheet, {}).get(addr)
            if a is None or b is None:
                errors.append(f"non_target_cell_changed:{sheet}!{addr}")
            elif not unchanged_cell(a, b):
                errors.append(f"non_target_cell_changed:{sheet}!{addr}")
    if errors:
        return {"pass": False, "errors": errors[:30]}
    try:
        expected = expected_values(seed)
        evaluator = Evaluator(candidate)
        for sheet, addr in sorted(targets):
            c = candidate.get(sheet, {}).get(addr)
            if c is None or not c.formula:
                errors.append(f"missing_formula:{sheet}!{addr}")
                continue
            actual = evaluator.cell(sheet, addr)
            if not close(actual, expected[(sheet, addr)]):
                errors.append(f"wrong_result:{sheet}!{addr}:{actual}:{expected[(sheet, addr)]}")
            if c.value is not None:
                try:
                    if not close(float(c.value), actual):
                        errors.append(f"stale_cache:{sheet}!{addr}")
                except ValueError:
                    errors.append(f"non_numeric_cache:{sheet}!{addr}")
        if errors:
            return {"pass": False, "errors": errors[:30]}
        # A hidden source change plus a scenario-input change tests dependency
        # propagation. The task workbook itself remains untouched.
        source = read_source(ISSUERS["Apple"])
        annual = [
            x for x in source["facts"]["us-gaap"][METRICS["Revenue"]]["units"]["USD"]
            if x["accn"] == ISSUERS["Apple"]["filing"]
            and x["end"] == ISSUERS["Apple"]["periods"]["2024"]
            and x["form"] == "10-K" and is_annual(x, "Revenue")
        ][0]
        raw_row_numbers = sorted(int(addr[1:]) for addr in candidate["Raw SEC"] if addr.startswith("A") and addr[1:].isdigit() and int(addr[1:]) >= 5)
        match_rows = [
            row for row in raw_row_numbers
            if candidate["Raw SEC"].get(f"B{row}", Cell(None, None, None)).value == "Apple"
            and candidate["Raw SEC"].get(f"D{row}", Cell(None, None, None)).value == "Revenue"
            and candidate["Raw SEC"].get(f"G{row}", Cell(None, None, None)).value == annual["end"]
            and candidate["Raw SEC"].get(f"J{row}", Cell(None, None, None)).value == annual["accn"]
            and candidate["Raw SEC"].get(f"F{row}", Cell(None, None, None)).value == annual["start"]
        ]
        if len(match_rows) != 1:
            raise ValueError("perturbation_source_ambiguity")
        ref = ("Raw SEC", f"O{match_rows[0]}")
        delta = 1_000_000_000
        overrides = {
            ref: _number(candidate["Raw SEC"][ref[1]]) + delta,
            ("Drivers", "F5"): _number(candidate["Drivers"]["F5"]) + 0.05,
        }
        changed = Evaluator(candidate, overrides)
        perturbed_expected = expected_values(seed, apple_revenue_delta_usd=delta, multiplier_delta=0.05)
        for key in sorted(targets):
            actual = changed.cell(*key)
            if not close(actual, perturbed_expected[key]):
                errors.append(f"dependency_failure:{key[0]}!{key[1]}")
    except Exception as e:
        errors.append(f"verification_error:{e}")
    return {"pass": not errors, "errors": errors[:30], "checked_targets": len(targets), "source_perturbation_usd": 1_000_000_000, "scenario_perturbation": 0.05}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    parser.add_argument("seed", type=Path)
    args = parser.parse_args()
    result = verify(args.candidate, args.seed)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
