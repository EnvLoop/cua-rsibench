"""Quarantine an exposed final source family before any hidden-set freeze."""

from __future__ import annotations

import json

from . import bootstrap, factory, runtime


REGISTRY = runtime.PRIVATE / "exposed-families-private.json"


def load() -> dict:
    if REGISTRY.exists():
        result = json.loads(REGISTRY.read_text())
        if result.get("schema") != "envloop-gitlab-exposure-quarantine-v1":
            raise RuntimeError("exposure registry schema mismatch")
        return result
    return {"schema": "envloop-gitlab-exposure-quarantine-v1", "families": {}}


def add_by_task(task_id: str, *, reason: str) -> dict:
    if reason not in ("gui_development_control", "training_or_prompt_exposure",
                      "operator_review"):
        raise ValueError("exposure reason not recognized")
    world = bootstrap.world()
    rows = [row for row in bootstrap.all_tasks(world) if row["task_id"] == task_id]
    if len(rows) != 1 or rows[0]["partition"] != "final_candidate_unsealed":
        raise ValueError("exposed task is not a unique final candidate")
    family = rows[0]["source_family"]
    affected = [row["task_id"] for row in bootstrap.all_tasks(world)
                if row["partition"] == "final_candidate_unsealed"
                and row["source_family"] == family]
    if len(affected) != 5:
        raise RuntimeError("expected exactly five correlated tasks per source family")
    registry = load()
    existing = registry["families"].get(family)
    if existing and (existing["task_ids"] != affected or existing["reason"] != reason):
        raise RuntimeError("existing exposure record changed")
    registry["families"][family] = {"task_ids": affected, "reason": reason,
                                    "project_family": rows[0]["project_family"]}
    if REGISTRY.exists():
        temporary = REGISTRY.with_suffix(".tmp")
        temporary.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
        temporary.chmod(0o600)
        temporary.replace(REGISTRY)
    else:
        factory.write_private(REGISTRY, registry)
    return public_counts(registry)


def public_counts(registry: dict | None = None) -> dict:
    registry = registry or load()
    manifest = bootstrap.world()
    reserve_count = len(manifest.get("reserve_tasks", []))
    ids = {task_id for item in registry["families"].values()
           for task_id in item["task_ids"]}
    clean = 100 + reserve_count - len(ids)
    return {"quarantined_source_families": len(registry["families"]),
            "quarantined_final_candidate_ids": len(ids),
            "reserve_replacement_candidate_ids": reserve_count,
            "still_unexposed_final_candidates": clean,
            "unexposed_100_candidate_inventory_intact": clean == 100,
            "refill_complete_as_inventory_only": reserve_count == len(ids) and clean == 100,
            "official_final_admitted": 0}


def excluded_task_ids() -> set[str]:
    return {task_id for item in load()["families"].values()
            for task_id in item["task_ids"]}
