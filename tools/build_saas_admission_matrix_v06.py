"""Build private Magento/GitLab candidate manifests and a fail-closed gate matrix.

This does not run agents or software tasks. A source-pinned public candidate is
never promoted into a sealed final task by a planner or by a network trace.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

import plan_gitlab_final_candidates_v06 as gitlab
import plan_magento_final_candidates_v06 as magento


COMMON_PENDING = [
    "fresh_authentic_seed_and_task_injection",
    "native_gui_positive_control",
    "plausible_wrong_object_or_wrong_route_negative",
    "independent_target_binding_and_no_regression",
    "reset_to_exact_monitored_baseline",
    "qwen_observation_action_interface_and_budget",
    "evaluator_owned_unpublished_variant_and_answer_seal",
]


def pending_for(item: dict) -> list[str]:
    requirements = list(COMMON_PENDING)
    if item["task_type"] == "mutate":
        requirements.insert(3, "persisted_saved_state_readback")
    elif item["task_type"] == "retrieve":
        requirements.insert(3, "browsing_and_answer_provenance")
    elif item["task_type"] == "navigate":
        requirements.insert(3, "rendered_final_destination_readback")
    else:
        raise ValueError("unsupported candidate task type")
    return requirements


def make_cell(site: str, manifest: dict) -> dict:
    selection = manifest["task_sets"]["selection"]
    final = manifest["task_sets"]["provisional_final"]
    if len(selection) != 20 or len(final) != 100:
        raise ValueError("cell does not have 20 selection and 100 provisional final candidates")
    if manifest["counts"]["provisional_final_officially_admitted"] != 0:
        raise ValueError("a source-candidate planner cannot admit official final tasks")
    if {row["task_id"] for row in selection} & {row["task_id"] for row in final}:
        raise ValueError("task identity appears in both splits")
    if {row["template_group"] for row in selection} & {row["template_group"] for row in final}:
        raise ValueError("template family appears in both splits")
    if any(row["expected_status"] != "SUCCESS" for row in final):
        raise ValueError("non-success source task in successful final queue")
    if site == "shopping_admin" and any(
        row["task_id"] in magento.TRAIN_RESERVED_TASK_IDS
        or row["template_group"] in {"shopping_admin:" + str(template)
                                      for template in magento.QUARANTINED_TEMPLATES}
        for row in selection + final
    ):
        raise ValueError("train-reserved or quarantined Magento template leaked into candidate splits")
    for row in selection + final:
        if row.get("admission_status", "offline_candidate_unverified") not in {
            "offline_candidate_unverified"
        }:
            raise ValueError("source candidate has an unsupported admission claim")
    return {
        "site": site,
        "source": manifest["source"],
        "status": "all_public_source_final_identities_are_provisional",
        "selection_count": len(selection),
        "provisional_final_count": len(final),
        "official_final_admitted_count": 0,
        "provisional_final_task_types": dict(sorted(Counter(row["task_type"] for row in final).items())),
        "provisional_final_hard_subset_count": sum(row["official_hard_subset"] for row in final),
        "candidate_gate_queue": [{
            "task_id": row["task_id"],
            "task_record_sha256": row["task_record_sha256"],
            "template_group": row["template_group"],
            "task_type": row["task_type"],
            "admission_status": "offline_candidate_unverified",
            "pending": pending_for(row),
        } for row in final],
    }


def build(source: Path, hard_ids: Path) -> dict:
    magento_rows, magento_hard = magento.source_rows(source, hard_ids)
    gitlab_rows, gitlab_hard = gitlab.source_rows(source, hard_ids)
    if magento_hard != gitlab_hard:
        raise ValueError("hard-subset source differs across cells")
    manifests = {
        "shopping_admin": magento.manifest(magento_rows, magento_hard),
        "gitlab": gitlab.manifest(gitlab_rows, gitlab_hard),
    }
    cells = {site: make_cell(site, value) for site, value in manifests.items()}
    return {
        "schema": "cua-saas-admission-matrix-v0.6",
        "status": "public_source_candidate_queue_not_official_study",
        "source": {"commit": gitlab.SOURCE_COMMIT, "dataset_sha256": gitlab.SOURCE_SHA256,
                   "hard_subset_sha256": gitlab.HARD_SHA256},
        "counts": {
            "cells": 2,
            "selection_candidates": sum(cell["selection_count"] for cell in cells.values()),
            "provisional_final_candidates": sum(cell["provisional_final_count"] for cell in cells.values()),
            "official_final_admitted": 0,
        },
        "manifests": manifests,
        "cells": cells,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--hard-ids", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.source, args.hard_ids)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "magento-100-admission-plan.json": result["manifests"]["shopping_admin"],
        "gitlab-100-admission-plan.json": result["manifests"]["gitlab"],
        "saas-admission-matrix.json": {
            key: value for key, value in result.items() if key != "manifests"
        },
    }
    for name, value in outputs.items():
        path = args.out_dir / name
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
        path.chmod(0o600)
    print(json.dumps({
        "counts": result["counts"],
        "cells": {site: {key: value for key, value in cell.items()
                          if key in ("selection_count", "provisional_final_count",
                                     "official_final_admitted_count", "provisional_final_task_types",
                                     "provisional_final_hard_subset_count")}
                  for site, cell in result["cells"].items()},
    }, sort_keys=True))


if __name__ == "__main__":
    main()
