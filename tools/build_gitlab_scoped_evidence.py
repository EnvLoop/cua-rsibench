"""Build an aggregate-only English GitLab scoped-GUI pre-result receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from gitlab_world import factory, quarantine, runtime, sweep, vision_actor


ROOT = Path(__file__).resolve().parents[1]
PRIVATE = runtime.PRIVATE
OUTPUT_JSON = ROOT / "docs/evidence/gitlab-scoped-gui-development-2026-09-27.json"
OUTPUT_MD = ROOT / "docs/evidence/gitlab-scoped-gui-development-2026-09-27.md"
SENSITIVE = re.compile(
    r"glpat-|GITLAB_ROOT_PASSWORD|@benchmark\.invalid|"
    r"(?:sk-[a-z0-9]{16,})|(?:e2b_[a-z0-9]{16,})|(?:tml-[a-z0-9]{16,})|"
    r"(?:localhost|127\.0\.0\.1):8014|/work/gitlab-full-world/|"
    r"GLW-\d{2}-\d{2}|portfolio-[0-9a-f]{10}|INV-[0-9A-F]{8}", re.I)


def read(name: str) -> dict:
    result = json.loads((PRIVATE / name).read_text())
    if not isinstance(result, dict):
        raise RuntimeError("private GitLab evidence item is not an object")
    return result


def build() -> tuple[dict, str]:
    acl = read("operator-acl-gui-summary.json")
    v3 = read("operator-v3-promotion-receipt.json")
    state = read("operator-readback-v3.json")
    qwen = read("vision-actor-smoke-v064-summary.json")
    sft_split = read("gui-sft-split-summary.json")
    analysis = read("analysis-family-public-fields.json")
    legacy = read("legacy-driver-failure-public-fields.json")
    restore = read("demo-restoration-v3-receipt.json")
    sweep_result = read("bounded-scoped-v3-sweep-summary.json")
    if not (acl.get("acl_gui_passed") and acl.get("own_project_gui_successes") == 3
            and acl.get("cross_partition_gui_denials") == 6):
        raise RuntimeError("scoped actor GUI ACL control not proven")
    if not (v3.get("cold_clone_equal") and state["business_sha256"] ==
            v3["baseline_business_sha256"]):
        raise RuntimeError("v3 ACL baseline not cold-restored")
    if not (qwen.get("same_business_sha256") and qwen.get("stale_frame_rejected")
            and qwen.get("shared_source_sha256") == vision_actor.SHARED_SOURCE_SHA256
            and qwen.get("model_calls") == 0):
        raise RuntimeError("revised shared Qwen action binding not proven")
    if not (sft_split.get("selection_count") == 20 and
            sft_split.get("clean_final_candidate_count") == 100 and
            sft_split.get("selection_final_task_template_entity_disjoint") and
            sft_split.get("train_source_disjoint_from_selection_and_final") and
            sft_split.get("accepted_training_episodes") == 0):
        raise RuntimeError("shared GUI SFT split exclusion not proven")
    family_path = PRIVATE / "analysis-families-private.json"
    if not (analysis.get("clean_final_task_count") == 100 and
            analysis.get("project_source_family_count") == 20 and
            analysis.get("tasks_per_project_source_family") == 5 and
            analysis.get("analysis_manifest_sha256") ==
            hashlib.sha256(family_path.read_bytes()).hexdigest()):
        raise RuntimeError("GitLab pre-result analysis-family binding invalid")
    if not (legacy.get("partial_unscored_driver_failure_count") == 2 and
            legacy.get("native_gui_screenshots_retained_private") >= 5 and
            legacy.get("promoted_to_official_results") is False):
        raise RuntimeError("early partial GUI selector failures were not retained")
    if not (restore.get("demo_identity_preserved") and restore.get("demo_healthy")
            and restore.get("world_removed")):
        raise RuntimeError("pre-existing GitLab demo restoration unverified")
    if sweep_result != sweep.public_summary(sweep._load()):
        raise RuntimeError("public sweep receipt differs from durable private index")
    development = {}
    for family, filename in (
        ("release_milestone_coordination", "milestone-dev-trio-summary-v2.json"),
        ("approved_merge_request_merge", "mr-dev-trio-summary.json"),
        ("least_privilege_access_handoff", "access-dev-trio-summary-v3.json"),
        ("ci_and_runbook_reconciliation", "ci-runbook-dev-trio-summary-v2.json"),
    ):
        row = read(filename)
        if row.get("scores") != [1.0, 0.0, 1.0] or row.get("cold_resets") != 3 or not row.get(
                "development_gui_control_passed"):
            raise RuntimeError("one scoped development workflow trio incomplete")
        development[family] = {"positive_negative_positive": [1.0, 0.0, 1.0],
                               "cold_resets": 3, "model_calls": 0}
    exposed = quarantine.public_counts()
    if not exposed["refill_complete_as_inventory_only"]:
        raise RuntimeError("exposed development family was not replaced")
    private_cases = PRIVATE / "gui-controls"
    failed_completed = sum(not json.loads(path.read_text()).get(
        "development_gui_control_passed", False)
        for path in private_cases.glob("GLW-11-*/trio-*/trio-private.json"))
    failed_drivers = len(list(private_cases.glob("GLW-11-*/trio-*/failed-run.json")))
    public = {
        "schema": "envloop-gitlab-scoped-gui-development-public-v1",
        "date": "2026-09-27", "cell": "gitlab",
        "source": {"real_advisory_source": "CISA KEV CC0 1.0",
                   "source_commit": factory.SOURCE_COMMIT,
                   "source_full_file_sha256": factory.SOURCE_FULL_SHA256,
                   "primary_excerpt_sha256": factory.EXCERPT_SHA256,
                   "reserve_excerpt_sha256": factory.RESERVE_EXCERPT_SHA256,
                   "internal_operations_are_synthetic": True,
                   "WebArena_identity_or_score_transferred": False},
        "application": {"name": "GitLab CE", "version": "18.5.0-ce.0",
                        "image_sha256": runtime.IMAGE_ID,
                        "projects": state["counts"]["projects"],
                        "issues": state["counts"]["issues"],
                        "merge_requests": state["counts"]["merge_requests"],
                        "project_direct_members": state["counts"]["members"],
                        "private_groups": state["counts"]["groups"],
                        "group_members": state["counts"]["group_members"],
                        "non_admin_partition_operators": state["counts"]["operators"],
                        "all_project_and_group_business_state_monitored": True,
                        "v3_cold_baseline_sha256": v3["baseline_business_sha256"],
                        "pre_existing_demo_restored_healthy_same_identity": True},
        "partition_acl": {"own_project_gui_successes": 3,
                          "cross_partition_gui_denials": 6,
                          "root_administrator_is_not_actor": True},
        "candidate_inventory": {"train": 20, "selection": 20,
                                "original_final": 100, "reserve": 5,
                                "exposed_quarantined": 5,
                                "unexposed_final_after_refill": 100,
                                "unexposed_final_source_families": 20},
        "development_gui_controls": development,
        "retained_failed_completed_development_trios": failed_completed,
        "retained_driver_failure_receipts": failed_drivers,
        "retained_legacy_partial_unscored_failures": legacy,
        "shared_qwen_actor": {"student": "Qwen/Qwen3.8-27B",
                              "action_contract": qwen["shared_action_contract_version"],
                              "output_contract": qwen["shared_output_version"],
                              "source_sha256": qwen["shared_source_sha256"],
                              "read_only_native_gui_smoke": True,
                              "stale_frame_rejected": True,
                              "model_calls": 0},
        "shared_gui_sft_split_gate": sft_split,
        "analysis_family_binding": analysis,
        "evaluator_private_bounded_sweep": sweep_result,
        "official_final_admitted": 0,
        "researcher_campaigns_executed": 0,
        "limitations": [
            "The bounded per-ID GUI sweep is not 100 individual admissions.",
            "Deterministic DOM-located qualification controls are separate from a paid Qwen screenshot-only rollout; no model result is reported.",
            "The CI task verifies saved Git configuration and runbook blobs, not execution by a registered CI runner.",
            "The final task identity/gold and preregistered campaign manifest are not yet frozen.",
        ],
    }
    passed = sweep_result["development_gui_trio_passed"]
    attempted = sweep_result["individually_attempted_ids"]
    failed = attempted - passed
    md = f"""# Scoped GitLab GUI development controls — 2026-09-27

**Pre-result evidence only.** The [aggregate machine receipt](gitlab-scoped-gui-development-2026-09-27.json) excludes task IDs, project names, screenshots, instructions, gold, credentials, and private action traces. These are original EnvLoop tasks in actual GitLab CE 18.5, not WebArena-Verified GitLab results. CISA's [CC0 KEV catalog](https://github.com/cisagov/kev-data/tree/{factory.SOURCE_COMMIT}) supplies advisory facts; internal operations, people, repos, issues, MRs, and deadlines are synthetic.

The frozen v3 world contains 31 private projects, 186 issues, 62 competing MRs, 93 direct project memberships, and three separate non-admin group-owner actors. Real GUI checks let each actor open its own partition's project (3/3) and denied every cross-partition probe with a 404 (6/6). The independently read PostgreSQL/Git business baseline includes private groups, operator administrator flags, group roles, project members, issues, labels, milestones, MRs, and Git refs/blobs. Fresh overlayfs-backed containers reproduced the same v3 digest before each control. The pre-existing GitLab demo returned healthy with the same identity, image, mounts, and ports after the sweep.

The train, selection, and clean final inventories remain 20/20/100. The first five-task development project family was quarantined; an unused CISA/vendor source family supplied five reserve candidates, restoring 100 unexposed final candidates in 20 correlated project families. A private candidate-level analysis mapping assigns exactly five tasks to each project family and is hash-bound before any official outcome. These are candidate identities, not admitted exam tasks.

Four causally distinct workflows have scoped-operator development controls:

| Saved workflow | Correct / plausible wrong / repeated correct | Cold resets |
| --- | --- | ---: |
| Release milestone plus two linked issues | 1 / 0 / 1 | 3 |
| Approved MR versus stale workaround | 1 / 0 / 1 | 3 |
| Contractor removal and time-bounded Reporter handoff versus overprivileged role | 1 / 0 / 1 | 3 |
| CI gate and response-runbook edits versus partial change | 1 / 0 / 1 | 3 |

The independent oracle caught a GitLab invitation-date discrepancy: the modal showed the policy date, while the saved member row and database initially held the preceding day. A visible saved-row correction was required. It also rejected a whole-file Monaco edit that reported a successful commit but changed unrelated YAML indentation. Two early selector timeouts retain five private GUI screenshots but never reached an independent score; the public receipt counts them separately from completed failed trios and later scored outcomes. A related historical [GitLab date display issue](https://gitlab.com/gitlab-org/gitlab/-/issues/24399) exists; the exact mechanism in this 18.5 container is an inference, while the one-day saved-state difference is directly observed.

The shared Qwen3.8 screenshot/action boundary was bound to the revised root action parser source hash `{vision_actor.SHARED_SOURCE_SHA256['scale_action_contract.py']}` and cell-neutral v0.6.4 output adapter hash `{vision_actor.SHARED_SOURCE_SHA256['scale_action_output_v064.py']}`. A scoped train operator produced a real GitLab screenshot frame with current visible controls, applied one read-only wait, rejected a stale frame, and left the business digest unchanged. The shared GUI SFT v2 split gate also accepted a private 20-selection/100-clean-final manifest with complete disjoint project/CVE/principal tags; its public receipt contains only hashes and counts. The earlier v0.6.3 read-only diagnostic remains historical and is not rewritten as a v0.6.4 run. **No Qwen model sampling or accepted training episode occurred in these controls.**

The bounded evaluator-private sweep attempted **{attempted}/100 clean final candidates** across **{sweep_result['attempted_source_family_count']} source families**: **{passed} passed**, **{failed} failed or infrastructure-invalid**, and **{100-attempted} unattempted**. Its v3 private index retains {sweep_result['retained_prior_failed_attempts']} prior failed attempts on these same IDs; the earlier selector, date, YAML, and v2 repeat failures belong to separate development records. Each pass requires correct/wrong/correct saved-state scoring plus three cold resets under the scoped operator. These deterministic GUI checks still do not establish Qwen action-contract solvability, complete per-ID admission, or model discrimination. **Official final admitted: 0/100; researcher campaigns: 0/4 for GitLab.**

The implementation and reset instructions are in the [GitLab world module](../../gitlab_world/README.md); the [dated source amendment](../FULL_STUDY_GITLAB_SOURCE_AMENDMENT_2026-09-25.md) preserves the pre-result source boundary. The next gate is individual admission for every clean ID under the frozen screenshot/action/runtime contract, an independent CI-runner check if that claim is retained, and the global pre-campaign freeze.
"""
    serialized = json.dumps(public, indent=2, sort_keys=True) + "\n" + md
    if SENSITIVE.search(serialized):
        raise RuntimeError("public GitLab scoped evidence contains a sensitive pattern")
    return public, md


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    public, md = build()
    if args.write:
        OUTPUT_JSON.write_text(json.dumps(public, indent=2, sort_keys=True) + "\n")
        OUTPUT_MD.write_text(md)
    else:
        print(json.dumps({"safe_aggregate": True,
                          "attempted": public["evaluator_private_bounded_sweep"][
                              "individually_attempted_ids"],
                          "official_final_admitted": public["official_final_admitted"]},
                         indent=2))


if __name__ == "__main__":
    main()
