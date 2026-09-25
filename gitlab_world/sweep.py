"""Fail-closed per-ID development admission sweep of 100 GitLab candidates.

Only implemented GUI drivers execute. Unsupported families remain pending, never
receive inferred positives, and cannot be counted as official final admissions.
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import json
from pathlib import Path

from . import bootstrap, factory, gui_controls, runtime, verify


INDEX = runtime.PRIVATE / "gui-development-sweep-index.json"
IMPLEMENTED_GUI_FAMILIES = {"cross_record_issue_triage"}


def candidates() -> list[dict]:
    rows = [row for row in bootstrap.world()["tasks"]
            if row["partition"] == "final_candidate_unsealed"]
    if len(rows) != 100 or len({row["task_id"] for row in rows}) != 100:
        raise RuntimeError("final candidate set is not exactly 100 unique IDs")
    return sorted(rows, key=lambda row: row["task_id"])


def _load() -> dict:
    if INDEX.exists():
        result = json.loads(INDEX.read_text())
        if result.get("schema") != "envloop-gitlab-development-sweep-v1":
            raise RuntimeError("sweep index schema differs")
        return result
    return {"schema": "envloop-gitlab-development-sweep-v1", "items": {}}


def _save(index: dict) -> None:
    temporary = INDEX.with_suffix(".tmp")
    temporary.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")
    temporary.chmod(0o600)
    temporary.replace(INDEX)


def public_summary(index: dict) -> dict:
    rows = candidates()
    counts = Counter(index["items"].get(row["task_id"], {}).get("status", "not_attempted")
                     for row in rows)
    by_family = Counter(row["template_group"] for row in rows)
    return {"schema": "envloop-gitlab-development-sweep-summary-v1",
            "source_excerpt_sha256": factory.EXCERPT_SHA256,
            "candidate_final_total": 100,
            "candidate_families": dict(sorted(by_family.items())),
            "implemented_gui_families": sorted(IMPLEMENTED_GUI_FAMILIES),
            "statuses": dict(sorted(counts.items())),
            "development_gui_trio_passed": counts.get("development_gui_trio_passed", 0),
            "official_final_admitted": 0,
            "complete_100_per_id_gui_admission": False,
            "no_model_scores": True}


async def run(max_tasks: int, *, family: str | None = None) -> dict:
    if max_tasks < 0 or max_tasks > 100:
        raise ValueError("max_tasks must be 0..100")
    index = _load()
    eligible = [row for row in candidates()
                if row["template_group"] in IMPLEMENTED_GUI_FAMILIES
                and (family is None or row["template_group"] == family)
                and index["items"].get(row["task_id"], {}).get("status") !=
                    "development_gui_trio_passed"]
    for row in eligible[:max_tasks]:
        before = verify.state_snapshot()
        baseline = json.loads((runtime.PRIVATE / "baseline-persisted-state.json").read_text())
        if before["business_sha256"] != baseline["business_sha256"]:
            raise RuntimeError("sweep candidate did not begin from cold baseline")
        result = await gui_controls.run(row["task_id"])
        index["items"][row["task_id"]] = {
            "status": "development_gui_trio_passed" if result["development_gui_control_passed"]
                      else "development_gui_trio_failed",
            "scores": result["scores"], "cold_resets": result["cold_resets"],
            "source_family_sha256": result["source_family_sha256"]}
        _save(index)
    return public_summary(index)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-tasks", type=int, default=0)
    parser.add_argument("--family", choices=sorted(IMPLEMENTED_GUI_FAMILIES))
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.max_tasks, family=args.family)),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
