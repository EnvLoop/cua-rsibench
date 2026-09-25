"""Independent arithmetic semantics for saved XLSX formulas.

This module is *not yet wired into the active v2 GUI sweep*. It lets a later
frozen evaluator accept algebraically equivalent formulas while rejecting
constants, wrong source years, and hardcoded policy thresholds. No Python eval,
Office engine, or external reference is executed by the verifier.
"""

from __future__ import annotations

import ast
import hashlib
import math
import re


REFERENCE = re.compile(
    r"(?P<sheet>'(?:[^']|'')+'|[A-Za-z_][A-Za-z0-9_]*)"
    r"[!.](?P<cell>\$?[A-Z]{1,3}\$?\d{1,7})",
    flags=re.IGNORECASE,
)
MAX_FORMULA_CHARS = 512
MAX_AST_NODES = 100
MAX_REFERENCES = 30


def _sheet_name(value: str) -> str:
    return value[1:-1].replace("''", "'") if value.startswith("'") else value


def _safe_tree(formula: str) -> tuple[ast.Expression, dict[str, tuple[str, str]]]:
    if not isinstance(formula, str) or len(formula) > MAX_FORMULA_CHARS or not formula.strip():
        raise ValueError("Missing or oversized spreadsheet formula")
    expression = formula.strip()
    if expression.startswith("of:="):
        expression = expression[4:]
    expression = expression.lstrip("=")
    if "[" in expression or "]" in expression or ":" in expression:
        raise ValueError("External workbook, range, or unsupported reference")
    refs: dict[tuple[str, str], str] = {}

    def replace(match: re.Match) -> str:
        sheet = _sheet_name(match.group("sheet"))
        cell = match.group("cell").replace("$", "").upper()
        if not sheet or not re.fullmatch(r"[A-Z]{1,3}\d{1,7}", cell):
            raise ValueError("Invalid spreadsheet reference")
        key = (sheet, cell)
        if key not in refs:
            if len(refs) >= MAX_REFERENCES:
                raise ValueError("Too many spreadsheet references")
            refs[key] = f"_r{len(refs)}"
        return refs[key]

    expression = REFERENCE.sub(replace, expression).replace("^", "**")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        raise ValueError("Unsupported formula syntax") from None
    if sum(1 for _ in ast.walk(tree)) > MAX_AST_NODES:
        raise ValueError("Spreadsheet expression exceeds complexity bound")
    variables = set(refs.values())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Expression, ast.Load, ast.BinOp, ast.UnaryOp,
                             ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow,
                             ast.UAdd, ast.USub)):
            continue
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            continue
        if isinstance(node, ast.Name) and node.id in variables:
            continue
        raise ValueError("Unsupported operation in spreadsheet formula")
    if not refs:
        raise ValueError("A live reference formula is required, not a pasted constant")
    return tree, {variable: ref for ref, variable in refs.items()}


def _evaluate(tree: ast.Expression, values: dict[str, float]) -> float:
    def visit(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant):
            return float(node.value)
        if isinstance(node, ast.Name):
            return values[node.id]
        if isinstance(node, ast.UnaryOp):
            value = visit(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add):
                result = left + right
            elif isinstance(node.op, ast.Sub):
                result = left - right
            elif isinstance(node.op, ast.Mult):
                result = left * right
            elif isinstance(node.op, ast.Div):
                result = left / right
            elif isinstance(node.op, ast.Pow):
                if abs(right) > 8:
                    raise ValueError("Exponent exceeds verifier bound")
                result = left ** right
            else:
                raise ValueError("Unsupported spreadsheet operator")
            if isinstance(result, complex) or not math.isfinite(result):
                raise ValueError("Formula result is not finite and real")
            return result
        raise ValueError("Unsupported spreadsheet expression")

    return visit(tree)


def _value(cells: dict, ref: tuple[str, str]) -> float:
    sheet, address = ref
    try:
        item = cells[sheet][address]
        if item["formula"] is not None:
            raise ValueError("Target formula may not depend on another derived formula")
        value = float(item["value"])
    except (KeyError, TypeError):
        raise ValueError("Formula reference is absent from frozen source/policy cells") from None
    if not math.isfinite(value):
        raise ValueError("Nonfinite source observation")
    return value


def _perturbed(original: float, *, salt: str, trial: int, ref: tuple[str, str]) -> float:
    if trial == 0:
        return original
    hash_bytes = hashlib.sha256(f"{salt}:{trial}:{ref[0]}!{ref[1]}".encode()).digest()
    fraction = int.from_bytes(hash_bytes[:8], "big") / 2**64
    factor = 0.55 + fraction * 0.9
    offset = (fraction - 0.5) * max(0.1, min(abs(original) * 0.1, 100.0))
    return original * factor + offset


def semantically_equivalent(proposed: str, expected: str,
                            source_cells: dict[str, dict[str, dict]], *,
                            private_salt: str, trials: int = 7) -> bool:
    """Compare live formulas on frozen and hidden counterfactual source states."""
    if not private_salt or not 3 <= trials <= 20:
        raise ValueError("Private perturbation salt and bounded trials required")
    try:
        actual_tree, actual_refs = _safe_tree(proposed)
        expected_tree, expected_refs = _safe_tree(expected)
        union = set(actual_refs.values()) | set(expected_refs.values())
        originals = {ref: _value(source_cells, ref) for ref in union}
        for trial in range(trials):
            changed = {ref: _perturbed(value, salt=private_salt, trial=trial, ref=ref)
                       for ref, value in originals.items()}
            actual = _evaluate(actual_tree, {name: changed[ref] for name, ref in actual_refs.items()})
            truth = _evaluate(expected_tree, {name: changed[ref] for name, ref in expected_refs.items()})
            if not math.isclose(actual, truth, rel_tol=1e-8, abs_tol=1e-7):
                return False
        return True
    except (ValueError, ZeroDivisionError, OverflowError, KeyError):
        return False
