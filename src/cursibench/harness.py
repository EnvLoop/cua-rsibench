import copy
import re
from .model import Task, Trajectory


def _apply(state: dict, action: dict) -> None:
    slide = next(s for s in state["slides"] if s["id"] == action["slide_id"])
    if action["field"] == "kpis":
        slide["kpis"][action["key"]] = action["value"]
    else:
        slide[action["field"]] = action["value"]


def run_harness(task: Task, policy: str) -> Trajectory:
    state = copy.deepcopy(task.initial)
    actions: list[dict] = []
    if policy == "naive":
        # Deliberately brittle: it edits the first matching KPI key without using the slide scope.
        match = re.search(r"Q([123]).*?(\d+)", task.instruction)
        if match:
            key, value = f"Q{match.group(1)}", int(match.group(2))
            for slide in state["slides"]:
                if key in slide["kpis"]:
                    slide["kpis"][key] = value
                    actions.append({"op": "set", "slide_id": slide["id"], "field": "kpis", "key": key, "value": value})
                    break
        else:
            actions.append({"op": "noop"})
    elif policy == "scoped":
        # Robust policy: parse the explicit object id and distinguish note edits from KPI edits.
        slide_id = re.search(r"slide (s\d+)", task.instruction).group(1)
        kpi = re.search(r"(Q[123]).*?to (\d+)", task.instruction)
        if kpi:
            action = {"op": "set", "slide_id": slide_id, "field": "kpis", "key": kpi.group(1), "value": int(kpi.group(2))}
        else:
            value = re.search(r"to '([^']+)'", task.instruction).group(1)
            action = {"op": "set", "slide_id": slide_id, "field": "note", "value": value}
        _apply(state, action)
        actions.append(action)
    else:
        raise ValueError(f"unknown policy: {policy}")
    return Trajectory(task.task_id, actions, state)
