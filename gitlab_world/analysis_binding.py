"""Pre-result project-family assignment for the proposed GitLab final pool."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from . import factory, runtime, sweep


PRIVATE = runtime.PRIVATE / "analysis-families-private.json"


def manifest() -> dict:
    tasks = sweep.candidates()
    families = {item["task_id"]: item["source_family"] for item in tasks}
    sizes = Counter(families.values())
    if len(families) != 100 or len(sizes) != 20 or set(sizes.values()) != {5}:
        raise ValueError("GitLab final source-family structure changed")
    return {"schema": "cua-cell-analysis-families-v1", "cell_id": "gitlab",
            "family_by_task": families}


def build() -> dict:
    result = manifest()
    if PRIVATE.exists():
        if json.loads(PRIVATE.read_text()) != result:
            raise RuntimeError("frozen GitLab family mapping drifted")
    else:
        factory.write_private(PRIVATE, result)
    return {"schema": "envloop-gitlab-analysis-family-public-v1",
            "analysis_manifest_sha256": hashlib.sha256(PRIVATE.read_bytes()).hexdigest(),
            "clean_final_task_count": 100,
            "project_source_family_count": 20,
            "tasks_per_project_source_family": 5,
            "candidate_family_mapping_pinned_before_any_official_outcome": True,
            "official_final_admitted": 0}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True))
