"""Source-only, train-partition composite GitLab challenge candidates.

The original 20/20/100 world and its final-task oracle are not changed. This
module derives ten supplemental tasks from the five existing training projects.
No GUI action, model call, final admission, or scored result occurs here.
"""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path

from . import factory


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "envloop-gitlab-train-transfer-analogues-v1"
PUBLIC_SCHEMA = "envloop-gitlab-train-transfer-analogues-public-v1"
SOURCE_RECEIPT = ROOT / "docs/evidence/gitlab-original-world-development-2026-09-25.json"
FAMILIES = factory.FAMILIES["final_candidate_unsealed"]
NEAR_MISSES = {
    "cross_record_issue_triage": {"kind": "wrong_lookalike_issue", "issue_key": "historical_duplicate", "description": "apply the policy fields to the retired-asset issue"},
    "release_milestone_coordination": {"kind": "wrong_second_issue", "issue_key": "historical_duplicate", "description": "link the retired issue instead of the validation follow-up"},
    "approved_merge_request_merge": {"kind": "wrong_open_mr", "mr_key": "stale", "description": "merge the stale workaround instead of approved evidence"},
    "least_privilege_access_handoff": {"kind": "overprivileged_responder", "access_level": 40, "description": "grant Maintainer rather than Reporter after removing contractor"},
    "ci_and_runbook_reconciliation": {"kind": "omitted_ci_gate", "file": ".gitlab-ci.yml", "description": "update the runbook but leave the security gate disabled"},
}
NO_REGRESSION = {
    "cross_record_issue_triage": ("historical and watch-list issues", "other labels and assignments", "all repository files"),
    "release_milestone_coordination": ("historical and watch-list issues", "other milestones", "all repository files"),
    "approved_merge_request_merge": ("stale MR and source branches", "non-runbook files", "other projects"),
    "least_privilege_access_handoff": ("all other memberships", "all issues", "all repository files"),
    "ci_and_runbook_reconciliation": ("other CI jobs", "other runbook lines", "all other files and projects"),
}
TARGETS = {
    "cross_record_issue_triage": ("active_issue.priority_label", "active_issue.assignee", "active_issue.due_date"),
    "release_milestone_coordination": ("new_milestone.window", "active_issue.milestone", "validation_issue.milestone"),
    "approved_merge_request_merge": ("approved_mr.state", "default_branch.runbook_note"),
    "least_privilege_access_handoff": ("contractor.membership", "incoming.membership_role", "incoming.expiry"),
    "ci_and_runbook_reconciliation": ("ci.kev_gate_rule", "runbook.current_contact"),
}


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def _sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _source_binding() -> dict[str, str]:
    receipt_raw = SOURCE_RECEIPT.read_bytes()
    receipt = json.loads(receipt_raw)
    _require(receipt.get("schema") == "envloop-gitlab-original-world-development-public-v1"
             and receipt.get("world", {}).get("train_candidates") == 20
             and receipt.get("world", {}).get("selection_candidates") == 20
             and receipt.get("world", {}).get("original_final_candidates") == 100
             and receipt.get("official_final_task_identities_admitted") == 0
             and receipt.get("source", {}).get("real_fact_source", {}).get("excerpt_sha256")
             == factory.EXCERPT_SHA256,
             "original GitLab aggregate receipt changed")
    return {
        "factory_source_sha256": _sha(Path(factory.__file__).read_bytes()),
        "train_analogue_source_sha256": _sha(Path(__file__).read_bytes()),
        "aggregate_receipt_sha256": _sha(receipt_raw),
        "cisa_excerpt_sha256": factory.EXCERPT_SHA256,
    }


def _prompt(project: dict, family: str) -> str:
    repo = project["full_path"]
    cve = project["advisories"][0]["cveID"]
    common = (f"Training exercise in {repo}: the live {cve} asset is the one marked active "
              "in the register. Read the current release policy and compare similar records. ")
    action = {
        "cross_record_issue_triage": "Bring its active issue into agreement with the policy on priority, assignee, and deadline; keep retired and watch-list issues intact.",
        "release_milestone_coordination": "Create the dated release window and connect both the remediation issue and its separate validation issue; leave the retired duplicate outside it.",
        "approved_merge_request_merge": "Compare both open remediation MRs and land only the approved evidence note on the default branch; keep the stale workaround unmerged.",
        "least_privilege_access_handoff": "Complete the documented responder handoff by withdrawing contractor access and adding the incoming person with the policy's bounded Reporter access.",
        "ci_and_runbook_reconciliation": "Make the existing security gate run for merge-request pipelines and update the runbook's current contact from the policy without touching other jobs or lines.",
    }[family]
    return common + action


def _case(project: dict, base_task: dict, family: str) -> dict:
    _require(base_task["partition"] == "train" and
             base_task["project_family"] == project["full_path"] and
             base_task["source_family"] == project["source_family"],
             "GitLab analogue source is not an original training project")
    slug = _sha(factory.canonical({"project": project["full_path"], "family": family}))[:16]
    case = {
        "task_id": "GLT-" + slug,
        "partition": "train",
        "source_family": project["source_family"],
        "project_family": project["full_path"],
        "entity_group": project["asset_id"],
        "template_group": "train-transfer-" + family + "-v1",
        "workflow_skill": family,
        "prompt": _prompt(project, family),
        "oracle": {**base_task["oracle"], "family": family},
        "target_state_fields": list(TARGETS[family]),
        "near_miss_control": {**NEAR_MISSES[family], "expected_score": 0,
                              "all_other_targets_correct": True},
        "no_regression_scope": list(NO_REGRESSION[family]),
        "evidence_inputs": ["KEV asset register", "current release policy",
                            "live GitLab records and repository state"],
        "candidate_status": "offline_train_analogue_unverified",
        "gui_positive_passed": False,
        "gui_negative_passed": False,
        "fresh_reset_passed": False,
        "official_final_admitted": False,
    }
    case["package_sha256"] = factory.sha256(factory.canonical(case))
    return case


def build(world: dict) -> dict:
    """Stage exactly two train-source analogues per final workflow skill."""
    _require(world.get("schema") == factory.SCHEMA and
             world.get("candidate_status") == "not_individually_gui_admitted" and
             len(world.get("projects", [])) == 30 and
             len(world.get("tasks", [])) == 140 and
             world.get("split_audit") == factory.split_audit(
                 world["projects"], world["tasks"]) and
             world["split_audit"]["all_cross_partition_disjoint"] is True and
             world.get("source", {}).get("excerpt_sha256") == factory.EXCERPT_SHA256 and
             world.get("source", {}).get("commit") == factory.SOURCE_COMMIT,
             "original GitLab world or split audit changed")
    train = sorted((p for p in world["projects"] if p["partition"] == "train"),
                   key=lambda p: p["index"])
    _require(len(train) == 5 and len({p["source_family"] for p in train}) == 5,
             "five disjoint training source projects required")
    by_project: dict[str, list[dict]] = {}
    for task in world["tasks"]:
        if task["partition"] == "train":
            by_project.setdefault(task["project_family"], []).append(task)
    _require(len(by_project) == 5 and
             all(len(by_project[p["full_path"]]) == 4 for p in train),
             "original 20-task training split changed")
    cases = [_case(train[(i + offset) % 5],
                   by_project[train[(i + offset) % 5]["full_path"]][0], family)
             for i, family in enumerate(FAMILIES) for offset in range(2)]
    result = {
        "schema": SCHEMA,
        "status": "offline_train_only_candidates_no_gui_or_model_result",
        "source_binding": _source_binding(),
        "world_seed_sha256": world["world_seed_sha256"],
        "original_train_count": 20,
        "supplemental_train_count": len(cases),
        "analogue_level": "two_distinct_train_source_projects_per_workflow",
        "cases": cases,
        "official_final_admitted": 0,
        "model_results": 0,
    }
    validate(result, world)
    return result


def validate(staged: dict, world: dict) -> None:
    """Independent structural audit; GUI controls and saved-state scoring remain pending."""
    _require(staged.get("schema") == SCHEMA and
             staged.get("status") == "offline_train_only_candidates_no_gui_or_model_result" and
             staged.get("source_binding") == _source_binding() and
             staged.get("world_seed_sha256") == world.get("world_seed_sha256") and
             staged.get("original_train_count") == 20 and
             staged.get("supplemental_train_count") == 10 and
             staged.get("official_final_admitted") == 0 and
             staged.get("model_results") == 0,
             "GitLab transfer source binding or status changed")
    cases = staged.get("cases")
    _require(type(cases) is list and len(cases) == 10,
             "exactly ten GitLab train analogues required")
    projects = {p["full_path"]: p for p in world["projects"]}
    protected = [p for p in world["projects"] if p["partition"] != "train"]
    protected_ids = {
        "project": {p["full_path"] for p in protected},
        "asset": {p["asset_id"] for p in protected},
        "source": {p["source_family"] for p in protected},
        "cve": {r["cveID"] for p in protected for r in p["advisories"]},
        "vendor": {r["vendorProject"].casefold() for p in protected for r in p["advisories"]},
        "principal": {u for p in protected for u in p["principals"].values()},
    }
    seen_task_ids: set[str] = set()
    family_sources: dict[str, set[str]] = {family: set() for family in FAMILIES}
    for case in cases:
        _require(type(case) is dict and case.get("partition") == "train" and
                 case.get("workflow_skill") in FAMILIES and
                 case.get("template_group") ==
                 "train-transfer-" + case["workflow_skill"] + "-v1" and
                 case.get("candidate_status") == "offline_train_analogue_unverified" and
                 all(case.get(flag) is False for flag in
                     ("gui_positive_passed", "gui_negative_passed",
                      "fresh_reset_passed", "official_final_admitted")),
                 "train-only provenance or candidate status changed")
        family = case["workflow_skill"]
        project = projects.get(case["project_family"])
        _require(project is not None and project["partition"] == "train" and
                 case["source_family"] == project["source_family"] and
                 case["entity_group"] == project["asset_id"] and
                 case["oracle"]["family"] == family and
                 case["oracle"]["project"] == project["full_path"] and
                 case["oracle"]["cve"] == project["advisories"][0]["cveID"] and
                 case["oracle"]["policy"] == project["policy"] and
                 case["oracle"]["principals"] == project["principals"] and
                 case["target_state_fields"] == list(TARGETS[family]) and
                 case["near_miss_control"] ==
                 {**NEAR_MISSES[family], "expected_score": 0,
                  "all_other_targets_correct": True} and
                 case["no_regression_scope"] == list(NO_REGRESSION[family]) and
                 case["prompt"] == _prompt(project, family),
                 "GitLab analogue semantic or training-source contract changed")
        _require(case["project_family"] not in protected_ids["project"] and
                 case["entity_group"] not in protected_ids["asset"] and
                 case["source_family"] not in protected_ids["source"] and
                 not ({r["cveID"] for r in project["advisories"]} & protected_ids["cve"]) and
                 not ({r["vendorProject"].casefold() for r in project["advisories"]}
                      & protected_ids["vendor"]) and
                 not (set(project["principals"].values()) & protected_ids["principal"]),
                 "GitLab training source/entity overlaps selection or final")
        unsealed = {key: value for key, value in case.items() if key != "package_sha256"}
        _require(case["package_sha256"] == factory.sha256(factory.canonical(unsealed)) and
                 case["task_id"] not in seen_task_ids and
                 case["task_id"] not in {t["task_id"] for t in world["tasks"]},
                 "GitLab analogue package identity changed or collides")
        seen_task_ids.add(case["task_id"])
        family_sources[family].add(case["source_family"])
    _require(all(len(sources) == 2 for sources in family_sources.values()),
             "each GitLab workflow requires two disjoint train source families")


def public_receipt(staged: dict, world: dict) -> dict:
    validate(staged, world)
    cases = staged["cases"]
    return {
        "schema": PUBLIC_SCHEMA,
        "status": "source_only_two_per_skill_staged_offline_no_gui_admission",
        "source_binding": staged["source_binding"],
        "original_train_count": 20,
        "supplemental_train_count": 10,
        "workflow_counts": dict(sorted(Counter(c["workflow_skill"] for c in cases).items())),
        "distinct_train_source_families_per_workflow": 2,
        "protected_partition_source_and_entity_overlap": 0,
        "multi_target_and_near_miss_no_regression_contracts_present": True,
        "private_cases_sha256": factory.sha256(factory.canonical(staged)),
        "gui_controls_passed": 0,
        "model_results": 0,
        "official_final_admitted": 0,
    }


def _write_new(path: Path, value: object, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False).encode() + b"\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    private_out = args.private_out.resolve()
    world_parent = args.world.resolve().parent
    _require((private_out.is_relative_to((ROOT / "work").resolve()) or
              (args.world.name == "world-private.json" and
               "work" in world_parent.parts and private_out.parent == world_parent)) and
             not private_out.exists() and not args.public_out.exists(),
             "new ignored private output and new public receipt required")
    world = json.loads(args.world.read_bytes())
    staged = build(world)
    receipt = public_receipt(staged, world)
    _write_new(private_out, staged, 0o600)
    _write_new(args.public_out, receipt, 0o644)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
