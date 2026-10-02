"""Numeric/role semantics for saved Impress and Writer decision statements.

This is an experimental guard, not yet wired into the active GUI sweep. It
accepts benign wording and precision variants while requiring one unambiguous
correct value, period and unit in the intended target object. Non-target
preservation remains the OOXML verifier's separate responsibility.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re


NUMBERS = re.compile(r"(?<![A-Za-z0-9])[-+]?\d+(?:\.\d+)?(?![A-Za-z0-9])")
YEAR = re.compile(r"20(?:19|2[0-4])\Z")


def _measurements(text: str) -> list[Decimal]:
    text = re.sub(r"^\s*(?:finding|signal)\s+\d+\s*[:.\-]\s*", "", text,
                  flags=re.IGNORECASE)
    values = []
    for match in NUMBERS.finditer(text):
        raw = match.group()
        if YEAR.fullmatch(raw):
            continue
        try:
            values.append(Decimal(raw))
        except InvalidOperation:
            raise ValueError("Malformed numeric statement") from None
    return values


def _role(expected: str) -> str:
    lower = expected.casefold()
    if "gdp" in lower:
        return "gdp"
    if "inflation" in lower or "price finding" in lower:
        return "inflation"
    if "unemployment" in lower or "labor finding" in lower:
        return "unemployment"
    raise ValueError("Unknown decision-statement role")


def semantically_correct(candidate: str, expected: str) -> bool:
    if not isinstance(candidate, str) or not isinstance(expected, str):
        return False
    if len(candidate) > 256 or "\n" in candidate or not candidate.strip():
        return False
    try:
        truth = _measurements(expected)
        actual = _measurements(candidate)
        role = _role(expected)
        if len(truth) != 1 or len(actual) != 1:
            return False
        target = truth[0].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        proposed = actual[0].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if target != proposed:
            return False
    except (ValueError, InvalidOperation):
        return False
    lower = candidate.casefold()
    if "2024" not in lower:
        return False
    if "2023" in expected and "2023" not in lower:
        return False
    if role == "gdp":
        return ("gdp" in lower and any(word in lower for word in
                ("growth", "grew", "increased", "change")) and
                ("%" in candidate or "percent" in lower))
    if role == "inflation":
        return (("inflation" in lower or "price" in lower) and
                (" pp" in lower or "percentage point" in lower))
    return ("unemployment" in lower and
            ("%" in candidate or "percent" in lower))
