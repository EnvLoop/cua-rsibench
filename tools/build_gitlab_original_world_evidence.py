"""Publish field-limited, pre-result GitLab world evidence without private gold."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from gitlab_world import bootstrap, factory, quarantine, runtime, sweep


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_JSON = ROOT / "docs/evidence/gitlab-original-world-development-2026-09-25.json"
PUBLIC_MD = ROOT / "docs/evidence/gitlab-original-world-development-2026-09-25.md"
PRIVATE = runtime.PRIVATE
SENSITIVE = re.compile(r"glpat-|GITLAB_ROOT_PASSWORD|@benchmark\.invalid|"
                       r"(?:sk-[a-z0-9]{16,})|(?:localhost|127\.0\.0\.1):8014|"
                       r"/work/gitlab-full-world/", re.I)


def read(path: Path) -> dict:
    result = json.loads(path.read_text())
    if not isinstance(result, dict):
        raise ValueError("private evidence is not an object")
    return result


def build() -> tuple[dict, str]:
    world = bootstrap.world()
    if len(bootstrap.all_projects(world)) != 31 or len(bootstrap.all_tasks(world)) != 145:
        raise RuntimeError("full reserve-refilled private world missing")
    seed = read(PRIVATE / "bootstrap-reserve-summary.json") if (
        PRIVATE / "bootstrap-reserve-summary.json").exists() else read(
            PRIVATE / "bootstrap-full-summary.json")
    persisted = read(PRIVATE / "real-readback-v2.json")
    promoted = read(PRIVATE / "reserve-promotion-receipt.json")
    restored = read(PRIVATE / "demo-restoration-receipt.json")
    trio = read(PRIVATE / "gui-trio-summary-v2.json")
    if trio.get("scores") != [1.0, 0.0, 1.0] or trio.get("cold_resets") != 3:
        raise RuntimeError("original development GUI trio incomplete")
    if not promoted.get("replacement_source_refilled") or not promoted.get(
            "new_cold_clone_equal"):
        raise RuntimeError("reserve baseline was not cold-frozen")
    if not restored.get("demo_identity_preserved") or not restored.get("demo_healthy"):
        raise RuntimeError("preserved GitLab demo restoration is unverified")
    exposure = quarantine.public_counts()
    if not exposure["refill_complete_as_inventory_only"]:
        raise RuntimeError("exposed source family not fully replaced")
    summary = sweep.public_summary(sweep._load())
    public = {
        "schema": "envloop-gitlab-original-world-development-public-v1",
        "date": "2026-09-25",
        "cell": "gitlab",
        "source": {"original_task_source": "EnvLoop authored",
                   "real_fact_source": world["source"],
                   "reserve_excerpt_sha256": factory.RESERVE_EXCERPT_SHA256,
                   "synthetic_internal_operations": True,
                   "WebArena_task_ids_or_scores_transferred": False},
        "runtime": {"application": "GitLab CE 18.5.0-ce.0",
                    "image_sha256": runtime.IMAGE_ID,
                    "isolated_loopback_instance": True,
                    "copy_on_write_cold_container_reset": True,
                    "pre_existing_demo_identity_preserved_and_restored_healthy": True,
                    "post_reserve_business_sha256": promoted["new_business_sha256"]},
        "world": {"projects": persisted["counts"]["projects"],
                  "users": seed["counts"]["users"],
                  "issues": persisted["counts"]["issues"],
                  "merge_requests": persisted["counts"]["merge_requests"],
                  "direct_acl_memberships": persisted["counts"]["members"],
                  "labels": persisted["counts"]["labels"],
                  "source_advisories": 124,
                  "train_candidates": 20, "selection_candidates": 20,
                  "original_final_candidates": 100,
                  "reserve_candidates": 5,
                  **exposure},
        "independent_oracle": {
            "postgresql_and_git_readback": persisted[
                "independent_postgresql_and_git_readback"],
            "all_31_projects_monitored_for_no_regression": True,
            "target_workflow_families_specified": 5,
        },
        "gui_development_control": {
            "source_families": 1, "positive_negative_positive_scores": trio["scores"],
            "fresh_browser_attempts": trio["fresh_browser_attempts"],
            "cold_resets": trio["cold_resets"],
            "model_calls": trio["model_calls"],
            "source_family_quarantined_before_refill": True,
        },
        "evaluator_owned_sweep": summary,
        "official_final_task_identities_admitted": 0,
        "full_researcher_campaigns_executed": 0,
        "limitations": [
            "Only the composite issue triage GUI driver is implemented; other four final families remain unattempted by the sweeper.",
            "The development trio used administrator login and DOM-located actions; the eventual model requires scoped operator credentials and a frozen screenshot/action contract.",
            "The saved CI configuration is not evidence of a functioning runner or passing pipeline.",
            "Candidate difficulty and model discrimination are unmeasured; no 100-task final set is admitted or sealed.",
        ],
    }
    md = f"""# Original GitLab CE development world: source, reset, and admission status

**Pre-result status.** This is an original EnvLoop GitLab CE 18.5 world, not a WebArena-Verified GitLab reproduction or an official final-task result. The [machine-readable public receipt](gitlab-original-world-development-2026-09-25.json) contains no task prompts, project identities, credentials, gold, private HAR, or final-ID list.

The [pinned CISA KEV catalog](https://github.com/cisagov/kev-data/tree/{factory.SOURCE_COMMIT}) contributed 124 real advisory records across the primary and reserve excerpts. The catalog mirror is [CC0 1.0](https://github.com/cisagov/kev-data/blob/{factory.SOURCE_COMMIT}/LICENSE). Internal projects, personnel, asset assignments, issue/MR records, deadlines, and operational requests are synthetic and explicitly labeled in the application. The original CE image digest is `{runtime.IMAGE_ID}`. The earlier 180 public WebArena-Verified GitLab tasks remain separate development references and supply no identity, evaluator, or score here.

| Persisted application state | Read back from the real instance |
| --- | ---: |
| Private projects | {persisted['counts']['projects']} |
| Distinct synthetic users | {seed['counts']['users']} |
| Issues | {persisted['counts']['issues']} |
| Open merge requests | {persisted['counts']['merge_requests']} |
| Direct ACL memberships | {persisted['counts']['members']} |
| Labels | {persisted['counts']['labels']} |

Five training projects yield 20 candidates, five disjoint selection projects yield 20, and 20 final projects yield 100. The first final project used for an inspectable development GUI trio was quarantined as a whole five-task source family. A 31st project built from four previously unused CISA/vendor records supplies five reserve tasks, restoring **100 unexposed final candidates across 20 project families**. Inventory is still not per-task admission.

One held-out composite issue-triage development control performed three fresh visible-UI attempts on a real GitLab project. The saved-state PostgreSQL/Git/no-regression oracle scored correct target **1.0**, plausible wrong retired-asset **0.0**, and correct repeat **1.0**. The wrong action mutated a different persisted issue and was rejected. Each attempt was followed by a new container on fresh overlayfs upperdirs; all three cold resets returned to the identical frozen business baseline. The development project family was excluded before reserve refill. The pre-existing GitLab demo was then restored healthy with the same container identity, image, ports, and mounts. No model ran.

The bounded evaluator-owned sweep has **{summary['development_gui_trio_passed']}/100 clean candidate IDs with a privately passed GUI trio**; one earlier failed trio remains in the private attempt history and its count is public. Only the issue-triage family currently has a GUI driver, and all task-level screenshots/gold remain private. These controls use DOM-located Playwright actions and an administrator fixture account. The final Qwen student must instead use a frozen screenshot/action interface and scoped operators. There is no demonstrated CI runner or pipeline success, and no measured model difficulty. **Official GitLab final admission is 0/100; researcher campaigns are 0/4 for this cell.**

The [dated source amendment](../FULL_STUDY_GITLAB_SOURCE_AMENDMENT_2026-09-25.md) records this source change before any final result. Reproduce the private fixture and per-ID gate with the [world implementation](../../gitlab_world/README.md). An evaluator must finish positive/negative/cold-reset controls for every identity, isolate actors from final projects, freeze model/runtime/verifier hashes, and seal the 100-task exam before a scored comparison.
"""
    serialized = json.dumps(public, indent=2, sort_keys=True) + "\n" + md
    if SENSITIVE.search(serialized):
        raise RuntimeError("public GitLab evidence contains a sensitive pattern")
    return public, md


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    public, md = build()
    if args.write:
        PUBLIC_JSON.write_text(json.dumps(public, indent=2, sort_keys=True) + "\n")
        PUBLIC_MD.write_text(md)
    else:
        print(json.dumps({"public_valid": True,
                          "unexposed_final_candidates": public["world"][
                              "still_unexposed_final_candidates"],
                          "official_final_admitted": public[
                              "official_final_task_identities_admitted"]},
                         indent=2))


if __name__ == "__main__":
    main()
