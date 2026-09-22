from copy import deepcopy
from .model import Task


def _slide(state: dict, slide_id: str):
    return next((s for s in state.get("slides", []) if s.get("id") == slide_id), None)


def verify(task: Task, state: dict) -> tuple[float, list[str]]:
    """Independent structural verifier; it never calls the harness."""
    errors: list[str] = []
    if state.get("metadata") != task.initial.get("metadata"):
        errors.append("metadata mutated")
    if len(state.get("slides", [])) != len(task.expected.get("slides", [])):
        errors.append("slide count changed")
    for expected in task.expected["slides"]:
        actual = _slide(state, expected["id"])
        if actual is None:
            errors.append(f"missing slide {expected['id']}")
            continue
        for key in ("title", "kpis", "note"):
            if actual.get(key) != expected.get(key):
                errors.append(f"{expected['id']}.{key} mismatch")
    # Hard failure for corruption; partial credit for a correctly targeted subset.
    checks = 1 + len(task.expected["slides"]) * 3
    passed = checks - min(len(errors), checks)
    return round(passed / checks, 4), errors


def expected_state(task: Task) -> dict:
    return deepcopy(task.expected)
