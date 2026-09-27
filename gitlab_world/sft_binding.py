"""Private GitLab split proof for the shared cell-neutral GUI SFT gate.

This binds source/entity/template independence only. No action episode,
checkpoint, paid optimizer step, selection score, or final score is produced.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cursibench import gui_sft_episode_v2 as shared

from . import bootstrap, factory, runtime, sweep


PRIVATE = runtime.PRIVATE / "gui-sft-splits-private"
NAME = "envloop_gitlab_original_kev"
REVISION = "gitlab18.5-cisa203fa463-worldv3"
DATASET_SHA256 = factory.sha256(factory.EXCERPT_SHA256 + factory.RESERVE_EXCERPT_SHA256)


def entity_tags(project: dict) -> list[str]:
    tags = {"project:" + factory.sha256(project["full_path"])[:16],
            "asset:" + project["asset_id"]}
    tags.update("cve:" + row["cveID"] for row in project["advisories"])
    tags.update("principal:" + name for name in project["principals"].values())
    return sorted(tags)


def _item(task: dict, projects: dict[str, dict]) -> dict:
    project = projects[task["project_family"]]
    return {"task_id": task["task_id"], "template_id": task["template_group"],
            "entity_tags": entity_tags(project)}


def manifests(world: dict) -> tuple[dict, dict, dict]:
    projects = {item["full_path"]: item for item in bootstrap.all_projects(world)}
    if len(projects) != 31:
        raise ValueError("reserve-refilled GitLab source roster missing")
    selection = [task for task in world["tasks"] if task["partition"] == "selection"]
    final = sweep.candidates()
    train = [task for task in world["tasks"] if task["partition"] == "train"]
    if len(selection) != 20 or len(final) != 100 or len(train) != 20:
        raise ValueError("GitLab 20/20/100 SFT split cardinality mismatch")
    common = {"schema": shared.SPLIT_SCHEMA, "cell": "gitlab_project",
              "source_name": NAME, "source_revision": REVISION,
              "source_dataset_sha256": DATASET_SHA256,
              "status": "provisional", "entity_coverage": "complete"}
    select_manifest = {**common, "split": "selection",
                       "items": [_item(item, projects) for item in selection]}
    final_manifest = {**common, "split": "final",
                      "items": [_item(item, projects) for item in final]}
    source_task = train[0]
    source = {"name": NAME, "revision": REVISION,
              "dataset_sha256": DATASET_SHA256,
              "task_id": source_task["task_id"],
              "template_id": source_task["template_group"],
              "task_sha256": factory.sha256(factory.canonical(source_task)),
              "entity_tags": entity_tags(projects[source_task["project_family"]]),
              "observation_task_id": source_task["task_id"]}
    return select_manifest, final_manifest, source


def build() -> dict:
    if PRIVATE.exists():
        raise RuntimeError("GitLab SFT private split output already exists")
    PRIVATE.mkdir(mode=0o700, parents=True)
    selection, final, source = manifests(bootstrap.world())
    select_path, final_path = (PRIVATE / name for name in
                               ("selection.json", "final.json"))
    factory.write_private(select_path, selection)
    factory.write_private(final_path, final)
    factory.write_private(PRIVATE / "train-source.json", source)
    receipt = shared.validate_split_exclusion(
        source, "gitlab_project", select_path, final_path)
    public = {"schema": "envloop-gitlab-gui-sft-split-public-v1",
              "shared_split_schema": shared.SPLIT_SCHEMA,
              "cell_adapter": "gitlab_project",
              "study_cell": shared.STUDY_CELL_BY_ADAPTER["gitlab_project"],
              "selection_manifest_sha256": receipt["selection_sha256"],
              "final_manifest_sha256": receipt["final_sha256"],
              "selection_count": receipt["selection_count"],
              "clean_final_candidate_count": receipt["final_count"],
              "selection_final_task_template_entity_disjoint":
                  receipt["selection_final_task_template_disjoint"] and
                  receipt["selection_final_declared_entities_disjoint"],
              "train_source_disjoint_from_selection_and_final":
                  receipt["train_source_task_template_and_declared_entities_disjoint"],
              "provisional_not_frozen": receipt["selection_status"] ==
                  receipt["final_status"] == "provisional",
              "accepted_training_episodes": 0,
              "official_final_admitted": 0}
    factory.write_private(PRIVATE / "public-fields.json", public)
    return public


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(build(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
