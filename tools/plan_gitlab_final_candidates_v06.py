"""Build a source-pinned, status-aware GitLab qualification queue.

The output is private candidate metadata. It does not contain upstream task
instructions or evaluator answers and does not admit any official final task.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


SOURCE_COMMIT = "6473f72db5dcefc97b5725b59e734504edc28a21"
SOURCE_SHA256 = "d65275660814663375028e9017e1f929e3c38321041b125795e2713b52243d30"
HARD_SHA256 = "3b0a4df231bb5a0c642215e521c3fa97701a384f52a734dc2db8f617ad0591a7"
SEED = "envloop-gitlab-v06-candidate-split-2026-09-25"
QUARANTINED_TASKS = {
    102: "requested project and published network-assertion project disagree",
    258: "GitLab CE 18.5 visible Explore projects navigation omits a query option required by the published network assertion; isolated GUI probe scored 0.0",
}
SUCCESS = "SUCCESS"
TASK_KINDS = {"mutate", "retrieve", "navigate"}
RESERVED_PATH_HEADS = {"dashboard", "explore", "users", "help", "search", "groups", "admin", "api"}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def source_rows(source: Path, hard_ids: Path) -> tuple[list[dict], set[int]]:
    raw, hard_raw = source.read_bytes(), hard_ids.read_bytes()
    if digest(raw) != SOURCE_SHA256 or digest(hard_raw) != HARD_SHA256:
        raise ValueError("source or hard-subset bytes differ from pinned revision")
    full, hard = json.loads(raw), json.loads(hard_raw)
    if not isinstance(full, list) or not isinstance(hard, dict):
        raise ValueError("unexpected upstream manifest schema")
    ids = hard.get("task_ids")
    if not isinstance(ids, list) or not all(type(item) is int for item in ids):
        raise ValueError("hard-subset IDs missing")
    rows = [row for row in full if row.get("sites") == ["gitlab"]]
    if len(rows) != 180 or len({row.get("task_id") for row in rows}) != 180:
        raise ValueError("pinned GitLab inventory count or uniqueness changed")
    if len({row.get("intent_template_id") for row in rows}) != 41:
        raise ValueError("pinned GitLab template count changed")
    return rows, set(ids)


def evaluation_shape(row: dict) -> dict:
    evaluations = row.get("eval")
    if not isinstance(evaluations, list) or not evaluations:
        raise ValueError("missing evaluator chain")
    response = evaluations[0]
    if response.get("evaluator") != "AgentResponseEvaluator":
        raise ValueError("unexpected response evaluator")
    expected = response.get("expected", {})
    kind, status = expected.get("task_type"), expected.get("status")
    if kind not in TASK_KINDS or status not in {
        SUCCESS, "ACTION_NOT_ALLOWED_ERROR", "NOT_FOUND_ERROR", "PERMISSION_DENIED_ERROR"
    }:
        raise ValueError("unexpected task type or response status")
    network = [item for item in evaluations[1:] if item.get("evaluator") == "NetworkEventEvaluator"]
    if len(network) != len(evaluations) - 1:
        raise ValueError("unexpected extra evaluator type")
    if kind == "mutate" and status == SUCCESS and not network:
        raise ValueError("successful mutation lacks network assertion")
    if kind == "navigate" and status == SUCCESS and not network:
        raise ValueError("successful navigation lacks network assertion")
    return {
        "task_type": kind,
        "expected_status": status,
        "network_assertions": len(network),
        "requires_saved_state_oracle": kind == "mutate" and status == SUCCESS,
        "requires_answer_provenance_oracle": kind == "retrieve" and status == SUCCESS,
        "requires_rendered_destination_oracle": kind == "navigate" and status == SUCCESS,
        "requires_no_state_change_oracle": kind == "mutate" and status != SUCCESS,
    }


def _values(value: object) -> list[str]:
    if isinstance(value, (str, int)) and not isinstance(value, bool):
        return [str(value)]
    if isinstance(value, list):
        return [part for item in value for part in _values(item)]
    return []


def _normal(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower()).strip(" /#")


def _project_from_url(value: str) -> str | None:
    # Only literal two-segment project paths. Dynamic query/regex fragments are
    # deliberately ignored rather than promoted into disjointness evidence.
    path = urlsplit(value.replace("__GITLAB__", "http://localhost")).path
    parts = [part for part in path.split("/") if part]
    if len(parts) < 2 or parts[0].lower() in RESERVED_PATH_HEADS:
        return None
    if not all(re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts[:2]):
        return None
    return "/".join(part.lower() for part in parts[:2])


def source_entity_hints(row: dict) -> list[str]:
    """Conservative explicit hints; absence never establishes non-overlap."""
    params = row.get("instantiation_dict") or {}
    if not isinstance(params, dict):
        raise ValueError("unexpected instantiation dictionary")
    hints: set[str] = set()
    for key in ("repo", "source_project", "project_name", "issue_location"):
        for value in _values(params.get(key)):
            if normalized := _normal(value):
                hints.add("project:" + normalized)
    for key in ("user", "account", "reviewer", "account_list", "collaborator_account_list", "user_list"):
        for value in _values(params.get(key)):
            if normalized := _normal(value):
                hints.add("principal:" + normalized)
    for key in ("issue", "mr"):
        for value in _values(params.get(key)):
            if normalized := _normal(value):
                hints.add(key + ":" + normalized)
    for value in _values(row.get("start_urls")):
        if project := _project_from_url(value):
            hints.add("project:" + project)
    for item in row.get("eval", [])[1:]:
        expected = item.get("expected", {})
        for value in _values(expected.get("url")):
            if project := _project_from_url(value):
                hints.add("project:" + project)
    return sorted(hints)


def task_record(row: dict, hard: set[int]) -> dict:
    shape = evaluation_shape(row)
    return {
        "task_id": row["task_id"],
        "task_record_sha256": digest(canonical_bytes(row)),
        "template_group": "gitlab:" + str(row["intent_template_id"]),
        "official_hard_subset": row["task_id"] in hard,
        "source_entity_hints": source_entity_hints(row),
        "admission_status": "offline_candidate_unverified",
        **shape,
    }


def choice_hash(value: str) -> str:
    return digest((SEED + ":" + value).encode())


def choose(rows: list[dict], hard: set[int], *, selection_count: int = 20,
           final_count: int = 100) -> dict:
    if len(rows) != 180:
        raise ValueError("expected 180 GitLab source tasks")
    allowed = [row for row in rows if row["task_id"] not in QUARANTINED_TASKS
               and evaluation_shape(row)["expected_status"] == SUCCESS]
    groups: dict[int, list[dict]] = defaultdict(list)
    for row in allowed:
        groups[row["intent_template_id"]].append(task_record(row, hard))
    for group in groups.values():
        group.sort(key=lambda item: choice_hash("task:" + str(item["task_id"])))
        if len({item["task_type"] for item in group}) != 1:
            raise ValueError("mixed task types within one template family")

    selected_templates: list[int] = []
    # One whole family per task type first. Families retained for selection
    # never enter final, including unused variants in a selected family.
    for kind in ("mutate", "retrieve", "navigate"):
        candidates = [template for template, group in groups.items()
                      if template not in selected_templates and group[0]["task_type"] == kind
                      and len(group) >= 5]
        if not candidates:
            raise ValueError("missing five-case selection family for " + kind)
        selected_templates.append(min(candidates, key=lambda template:
                                      choice_hash(f"selection-type:{kind}:{template}")))
    remainder = sorted((template for template in groups if template not in selected_templates
                        and len(groups[template]) >= 5),
                       key=lambda template: choice_hash("selection-template:" + str(template)))
    while sum(len(groups[template]) for template in selected_templates) < selection_count:
        if not remainder:
            raise ValueError("insufficient selection families")
        selected_templates.append(remainder.pop(0))
    selection_pool = [item for template in selected_templates for item in groups[template]]
    selection = sorted(selection_pool, key=lambda item:
                       choice_hash("selection-task:" + str(item["task_id"])))[:selection_count]
    selection_hints = {hint for item in selection_pool for hint in item["source_entity_hints"]}
    nonselection = [item for template, group in groups.items()
                    if template not in selected_templates for item in group]
    overlapping = [item for item in nonselection
                   if selection_hints.intersection(item["source_entity_hints"])]
    final_pool = [item for item in nonselection
                  if not selection_hints.intersection(item["source_entity_hints"])]
    final_pool.sort(key=lambda item: (
        not item["official_hard_subset"],
        item["task_type"] != "mutate",
        -item["network_assertions"],
        choice_hash("final-task:" + str(item["task_id"])),
    ))
    if len(final_pool) < final_count:
        raise ValueError(f"only {len(final_pool)} final candidates after quarantine and explicit entity isolation")
    final = final_pool[:final_count]
    if {item["template_group"] for item in selection} & {item["template_group"] for item in final}:
        raise AssertionError("selection/final template leakage")
    if {hint for item in selection for hint in item["source_entity_hints"]} & {
        hint for item in final for hint in item["source_entity_hints"]
    }:
        raise AssertionError("explicit source-entity leakage")
    if len({item["task_id"] for item in selection + final}) != selection_count + final_count:
        raise AssertionError("selection/final task ID reuse")
    return {
        "selection": selection,
        "provisional_final": final,
        "selection_template_ids": sorted(selected_templates),
        "reserved_selection_family_tasks": len(selection_pool) - len(selection),
        "explicit_entity_overlap_excluded_tasks": len(overlapping),
        "unused_nonquarantined_tasks": len(final_pool) - len(final),
    }


def manifest(rows: list[dict], hard: set[int]) -> dict:
    sets = choose(rows, hard)
    final = sets["provisional_final"]
    error_statuses = Counter(evaluation_shape(row)["expected_status"] for row in rows
                             if evaluation_shape(row)["expected_status"] != SUCCESS)
    return {
        "schema": "cua-gitlab-admission-backlog-v0.6",
        "status": "offline_provisional_final_candidates_not_officially_admitted",
        "source": {"commit": SOURCE_COMMIT, "dataset_sha256": SOURCE_SHA256,
                   "hard_subset_sha256": HARD_SHA256,
                   "url": "https://github.com/ServiceNow/webarena-verified"},
        "quarantine": {"task_ids": sorted(QUARANTINED_TASKS),
                       "task_reasons": {str(key): value for key, value in QUARANTINED_TASKS.items()},
                       "other_statuses_excluded_from_success_queue": dict(sorted(error_statuses.items()))},
        "counts": {
            "published_gitlab_task_ids": len(rows),
            "published_intent_templates": len({row["intent_template_id"] for row in rows}),
            "published_hard_subset_gitlab_ids": sum(row["task_id"] in hard for row in rows),
            "selection_instances": len(sets["selection"]),
            "selection_template_families": len({row["template_group"] for row in sets["selection"]}),
            "selection_reserved_same_family_tasks": sets["reserved_selection_family_tasks"],
            "explicit_entity_overlap_excluded_tasks": sets["explicit_entity_overlap_excluded_tasks"],
            "provisional_final_instances": len(final),
            "provisional_final_template_families": len({row["template_group"] for row in final}),
            "provisional_final_hard_subset_ids": sum(row["official_hard_subset"] for row in final),
            "provisional_final_task_types": dict(sorted(Counter(row["task_type"] for row in final).items())),
            "provisional_final_expected_statuses": dict(sorted(Counter(row["expected_status"] for row in final).items())),
            "provisional_final_officially_admitted": 0,
            "unused_nonquarantined_task_ids": sets["unused_nonquarantined_tasks"],
        },
        "split_rule": "Whole selection template families; 20 selected tasks; final candidates are template-disjoint, explicit-entity-hint-disjoint, hard-subset and mutation prioritized.",
        "split_limitations": [
            "Published tasks and evaluator answers are not a sealed final set.",
            "Explicit hints do not prove database entity, workflow, or answer independence.",
            "Hard-subset membership and network assertions do not prove difficulty or saved state.",
            "All 100 provisional tasks need native GUI positive and negative controls, independent saved-state or answer readback, no-regression, and reset verification.",
            "The local task-590 milestone probe used a synthetic fixture, not the populated WebArena snapshot.",
        ],
        "task_sets": {"selection": sets["selection"], "provisional_final": final},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--hard-ids", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rows, hard = source_rows(args.source, args.hard_ids)
    result = manifest(rows, hard)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
