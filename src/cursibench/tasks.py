from copy import deepcopy
from .model import Task


def _state(title: str, q1: int, q2: int, q3: int, note: str = "internal"):
    return {
        "slides": [
            {"id": "s1", "title": "Quarterly sales", "kpis": {"Q1": q1, "Q2": q2, "Q3": q3}, "note": note},
            {"id": "s2", "title": "Risks", "kpis": {"Q1": 0, "Q2": 0, "Q3": 0}, "note": "do not edit"},
        ],
        "metadata": {"theme": "blue", "author": "fixture"},
    }


def make_tasks() -> list[Task]:
    rows = [
        ("sales-q3", "Update the Q3 KPI on slide s1 to 140.", 100, 120, 140),
        ("sales-q2", "Update the Q2 KPI on slide s1 to 130.", 100, 130, 125),
        ("sales-q1", "Update the Q1 KPI on slide s1 to 110.", 110, 120, 125),
        ("risk-note", "Change the note on slide s1 to 'external'.", 100, 120, 125),
    ]
    tasks: list[Task] = []
    for i, (name, instruction, q1, q2, q3) in enumerate(rows):
        initial = _state("Quarterly sales", 100, 120, 125)
        expected = deepcopy(initial)
        target = expected["slides"][0]
        if "KPI" in instruction:
            period = instruction.split("Q")[1][0]
            target["kpis"][f"Q{period}"] = {"1": q1, "2": q2, "3": q3}[period]
        else:
            target["note"] = "external"
        split = "train" if i < 2 else "test"
        tasks.append(Task(name, split, instruction, initial, expected))
    return tasks
