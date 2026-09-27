"""Publish a later aggregate-only GitLab GUI sweep milestone after demo restore."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path

from gitlab_world import failure_ledger, sweep
from tools.build_gitlab_sweep_progress import SENSITIVE


INDEX_FIELDS = (
    "candidate_final_total", "source_excerpt_sha256", "statuses",
    "individually_attempted_ids", "attempted_source_family_count",
    "passed_source_family_count", "failed_source_family_count",
    "attempted_workflow_counts", "passed_workflow_counts",
    "failed_workflow_counts", "development_gui_trio_passed",
    "verified_cold_resets_for_passed_ids", "retained_prior_failed_attempts",
)


def read(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise RuntimeError(f"GitLab milestone source is not an object: {path}")
    return value


def build(*, previous_public: Path, prior_index: Path, completed_summary: Path,
          restoration_receipt: Path, expected_attempted: int,
          report_date: str) -> tuple[dict, str]:
    previous = read(previous_public)
    previous_cumulative = previous["cumulative"]
    checkpoint = read(prior_index)
    current_index = sweep._load()
    sweep.reconcile_failure_ledger(current_index)
    prior_attempted = previous_cumulative["individually_attempted_ids"]
    if (len(checkpoint["items"]) != prior_attempted or
            expected_attempted <= prior_attempted or expected_attempted > 100):
        raise RuntimeError("GitLab prior checkpoint or expected milestone differs")
    for task_id, record in checkpoint["items"].items():
        if current_index["items"].get(task_id) != record:
            raise RuntimeError("earlier GitLab attempt changed or was retried")
    checkpoint_summary = sweep.public_summary(checkpoint)
    if any(checkpoint_summary[key] != previous_cumulative[key]
           for key in INDEX_FIELDS):
        raise RuntimeError("prior private GitLab index differs from public milestone")

    completed = read(completed_summary)
    durable = sweep.public_summary(current_index)
    if (completed != durable or
            completed["individually_attempted_ids"] != expected_attempted):
        raise RuntimeError("new bounded GitLab batch incomplete or index differs")
    ledger = failure_ledger.audit()
    if (not ledger["all_records_hash_chained"] or
            completed["append_only_failure_ledger"] != ledger or
            completed["retained_prior_failed_attempts"] != ledger["entry_count"]):
        raise RuntimeError("GitLab failure ledger and index do not reconcile")
    restored = read(restoration_receipt)
    if not all(restored.get(key) for key in
               ("demo_healthy", "demo_identity_preserved", "same_container_id",
                "world_removed")):
        raise RuntimeError("preserved GitLab demo was not restored healthy")
    passed_records = [item for item in current_index["items"].values()
                      if item.get("status") == "development_gui_trio_passed"]
    if not all(item.get("scores") == [1.0, 0.0, 1.0]
               and item.get("cold_resets") == 3 for item in passed_records):
        raise RuntimeError("GitLab passing controls lack complete trios or resets")
    if completed["development_gui_trio_passed"] != len(passed_records):
        raise RuntimeError("GitLab pass count differs from private index")
    if completed["official_final_admitted"] or not completed["no_model_scores"]:
        raise RuntimeError("GitLab development controls misclassified as final results")

    new_attempted = expected_attempted - prior_attempted
    new_passed = (completed["development_gui_trio_passed"] -
                  previous_cumulative["development_gui_trio_passed"])
    new_families = (completed["attempted_source_family_count"] -
                    previous_cumulative["attempted_source_family_count"])
    if not (0 <= new_passed <= new_attempted and 0 <= new_families <= new_attempted):
        raise RuntimeError("GitLab bounded batch deltas are invalid")
    public = {
        "schema": "envloop-gitlab-sweep-progress-public-v1",
        "date": report_date, "cell": "gitlab",
        "previous_public_receipt_sha256": hashlib.sha256(
            previous_public.read_bytes()).hexdigest(),
        "cumulative": completed,
        "new_bounded_batch": {
            "attempted_ids": new_attempted,
            "new_source_families": new_families,
            "new_passed_ids": new_passed,
            "new_failed_or_invalid_ids": new_attempted - new_passed,
            "prior_passes_preserved": previous_cumulative["development_gui_trio_passed"],
            "prior_failed_attempts_preserved":
                previous_cumulative["retained_prior_failed_attempts"],
        },
        "append_only_failure_ledger": ledger,
        "pre_existing_demo_restored_same_identity_healthy": True,
        "model_calls": 0, "official_final_admitted": 0,
        "researcher_campaigns_executed": 0,
        "interpretation": "Evaluator-private native GUI admission controls only; no official exam or model score.",
    }
    passed = completed["development_gui_trio_passed"]
    invalid = expected_attempted - passed
    remaining = 100 - expected_attempted
    md = f"""# GitLab scoped-GUI admission progress — {report_date}

The [previous aggregate control receipt]({previous_public.name.removesuffix('.json')}.md) records the earlier GitLab CE 18.5 evaluator-private checks. This bounded serial batch used untouched candidate IDs. Prior per-ID records are unchanged in the private index, and every invalid attempt remains in the mode-0600 SHA-chained ledger. No task ID, prompt, answer, project identity, screenshot, credential, or raw action trace is published.

| Cumulative final-candidate GUI controls | Count |
| --- | ---: |
| Distinct IDs attempted | {expected_attempted} / 100 |
| Distinct project source families attempted | {completed['attempted_source_family_count']} / 20 |
| Native-GUI correct / plausible wrong / repeated correct trios passed | {passed} |
| Failed or infrastructure-invalid IDs | {invalid} |
| Unattempted IDs | {remaining} |
| Cold resets bound to passed IDs | {completed['verified_cold_resets_for_passed_ids']} |
| Official final IDs admitted | **0** |

This batch attempted **{new_attempted} untouched IDs**, expanding source-family coverage by **{new_families}**: **{new_passed} passed** and **{new_attempted-new_passed} failed or infrastructure-invalid**. The [machine-readable aggregate](gitlab-scoped-gui-progress-{expected_attempted}-{report_date}.json) contains per-workflow counts. Every pass has independent saved-state and no-regression readback, 1/0/1 GUI scores, and three fresh cold resets. The append-only ledger has {ledger['entry_count']} verified entries; no failed ID was silently retried or converted into a model failure. The original demo was restored healthy with its pre-stop container identity.

The remaining **{remaining}** candidates lack a per-ID control. These deterministic GUI qualification checks are separate from Qwen's screenshot-only action policy. No paid training, selection feedback, researcher campaign, or official final admission is claimed. CI YAML persistence has been checked, while runner execution remains unproven. The GitLab cell remains **0/100 officially admitted** until all per-ID and global pre-campaign gates pass.
"""
    if SENSITIVE.search(json.dumps(public, sort_keys=True) + md):
        raise RuntimeError("GitLab public milestone includes a sensitive pattern")
    return public, md


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous-public", required=True, type=Path)
    parser.add_argument("--prior-index", required=True, type=Path)
    parser.add_argument("--completed-summary", required=True, type=Path)
    parser.add_argument("--restoration-receipt", required=True, type=Path)
    parser.add_argument("--expected-attempted", required=True, type=int)
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--output-stem", required=True, type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    public, md = build(previous_public=args.previous_public,
                       prior_index=args.prior_index,
                       completed_summary=args.completed_summary,
                       restoration_receipt=args.restoration_receipt,
                       expected_attempted=args.expected_attempted,
                       report_date=args.date)
    if args.write:
        args.output_stem.with_suffix(".json").write_text(
            json.dumps(public, indent=2, sort_keys=True) + "\n")
        args.output_stem.with_suffix(".md").write_text(md)
    else:
        print(json.dumps({"attempted": public["cumulative"]["individually_attempted_ids"],
                          "official_final_admitted": public["official_final_admitted"]},
                         indent=2))


if __name__ == "__main__":
    main()
