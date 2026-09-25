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

from . import bootstrap, factory, gui_controls, quarantine, runtime, verify


INDEX = runtime.PRIVATE / "gui-development-sweep-index.json"
IMPLEMENTED_GUI_FAMILIES = {"cross_record_issue_triage"}


def candidates() -> list[dict]:
    manifest = bootstrap.world()
    rows = [row for row in bootstrap.all_tasks(manifest)
            if row["partition"] == "final_candidate_unsealed"]
    excluded = quarantine.excluded_task_ids()
    clean = [row for row in rows if row["task_id"] not in excluded]
    if len(clean) != 100 or len({row["task_id"] for row in clean}) != 100:
        raise RuntimeError("quarantined final source family not fully replaced")
    source_sizes = Counter(row["source_family"] for row in clean)
    if len(source_sizes) != 20 or set(source_sizes.values()) != {5}:
        raise RuntimeError("final tasks are not 20 complete five-task source families")
    train_selection = [row for row in manifest["tasks"]
                       if row["partition"] in ("train", "selection")]
    for key in ("source_family", "project_family", "entity_group", "template_group"):
        if {row[key] for row in train_selection} & {row[key] for row in clean}:
            raise RuntimeError(f"final candidate {key} leaks into train or selection")
    return sorted(clean, key=lambda row: row["task_id"])


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
    prior_failure_count = sum(
        sum(attempt.get("status") != "development_gui_trio_passed"
            for attempt in item.get("attempts", []))
        for item in index["items"].values())
    exposure = quarantine.public_counts()
    return {"schema": "envloop-gitlab-development-sweep-summary-v1",
            "source_excerpt_sha256": factory.EXCERPT_SHA256,
            "candidate_final_total": 100,
            "generated_final_and_reserve_candidates": 100 + exposure["reserve_replacement_candidate_ids"],
            **exposure,
            "candidate_families": dict(sorted(by_family.items())),
            "implemented_gui_families": sorted(IMPLEMENTED_GUI_FAMILIES),
            "statuses": dict(sorted(counts.items())),
            "development_gui_trio_passed": counts.get("development_gui_trio_passed", 0),
            "retained_prior_failed_attempts": prior_failure_count,
            "official_final_admitted": 0,
            "complete_100_per_id_gui_admission": False,
            "no_model_scores": True}


async def run(max_tasks: int, *, family: str | None = None,
              retry_failed: bool = False) -> dict:
    if max_tasks < 0 or max_tasks > 100:
        raise ValueError("max_tasks must be 0..100")
    index = _load()
    excluded = quarantine.excluded_task_ids()
    eligible = [row for row in candidates()
                if row["template_group"] in IMPLEMENTED_GUI_FAMILIES
                and row["task_id"] not in excluded
                and (family is None or row["template_group"] == family)
                and (row["task_id"] not in index["items"] or
                     (retry_failed and index["items"][row["task_id"]].get("status") !=
                      "development_gui_trio_passed" and
                      len(index["items"][row["task_id"]].get("attempts", [])) < 2))]
    for row in eligible[:max_tasks]:
        before = verify.state_snapshot()
        baseline = json.loads((runtime.PRIVATE / "baseline-persisted-state.json").read_text())
        if before["business_sha256"] != baseline["business_sha256"]:
            raise RuntimeError("sweep candidate did not begin from cold baseline")
        previous = index["items"].get(row["task_id"], {})
        history = list(previous.get("attempts", []))
        if previous and not history:
            history.append({key: value for key, value in previous.items()
                            if key in ("status", "scores", "error_type")})
        try:
            result = await gui_controls.run(row["task_id"], exposed_development=False)
        except Exception as exc:
            # Keep the failed ID and error class in evaluator-owned storage.
            # A crashed GUI/reset is neither a model failure nor a task admit.
            record = {
                "status": "driver_or_environment_failed",
                "error_type": type(exc).__name__,
                "source_family_sha256": factory.sha256(row["source_family"])}
            index["items"][row["task_id"]] = {**record,
                                                   "attempts": history + [record]}
            _save(index)
            raise
        record = {
            "status": "development_gui_trio_passed" if result["development_gui_control_passed"]
                      else "development_gui_trio_failed",
            "scores": result["scores"], "cold_resets": result["cold_resets"],
            "source_family_sha256": result["source_family_sha256"]}
        index["items"][row["task_id"]] = {**record,
                                              "attempts": history + [record]}
        _save(index)
    return public_summary(index)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-tasks", type=int, default=0)
    parser.add_argument("--family", choices=sorted(IMPLEMENTED_GUI_FAMILIES))
    parser.add_argument("--retry-failed", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.max_tasks, family=args.family,
                                     retry_failed=args.retry_failed)),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
