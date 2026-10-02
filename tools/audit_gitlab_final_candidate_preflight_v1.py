"""Read-only, per-task GitLab candidate audit before v0.6 final admission.

The retained GUI controls are evaluator-only development evidence. This tool
never writes a qualified manifest, a v0.6 task proof, or a model result.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path

from cursibench import scale_final_v06
from gitlab_world import factory
from native_desktop_factory.v066_final_freeze import validate_ratification


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_RATIFICATION = ROOT / "docs/evidence/full-study-v066-code-only-control-ratification-2026-09-28.json"
PUBLIC_REQUALIFICATION = ROOT / "docs/evidence/gitlab-requalification-100-2026-09-28.json"
PRIVATE_SCHEMA = "envloop-gitlab-final-candidate-preflight-private-v1"
PUBLIC_SCHEMA = "envloop-gitlab-final-candidate-preflight-public-v1"
BLOCKERS = (
    "per_task_v06_reset_and_verifier_proofs_not_issued",
    "per_task_gui_controller_source_at_execution_not_bound",
    "v066_live_student_observation_and_sampling_not_qualified",
    "complete_cell_runtime_hidden_set_and_cost_freeze_absent",
    "six_cell_pre_campaign_witness_absent",
)
SCREENSHOT_BY_FIELD = {
    "policy_screenshot_sha256": "policy.png",
    "milestone_screenshot_sha256": "milestone-saved.png",
    "merge_screenshot_sha256": "merge-request-after.png",
    "member_screenshot_sha256": "members-after.png",
    "ci_saved_screenshot_sha256": "ci-saved.png",
}
NEGATIVE_CASE_BY_FAMILY = {
    "cross_record_issue_triage": "wrong-retired-asset",
    "release_milestone_coordination": "wrong-due-date",
    "approved_merge_request_merge": "wrong-stale-mr",
    "least_privilege_access_handoff": "overprivileged-role",
    "ci_and_runbook_reconciliation": "partial-ci-only",
}


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
    return factory.canonical(value)


def read_file(path: Path, private_root: Path, *, maximum: int = 32 * 1024 * 1024) -> bytes:
    """Read only a bounded, non-symlink regular file inside mode-0700 storage."""
    root = private_root.absolute()
    require(root.is_dir() and not root.is_symlink() and
            root.stat().st_mode & 0o077 == 0, "private_root_not_restrictive")
    require(path.is_relative_to(root), "private_evidence_outside_root")
    current = root
    for part in path.relative_to(root).parts:
        current = current / part
        require(not current.is_symlink(), "private_evidence_symlink")
    # Early browser screenshots retained mode 0644. Their enclosing
    # evaluator-owned private root and gui-controls directory are both 0700.
    require(path.is_file() and path.stat().st_size <= maximum,
            "private_evidence_missing_or_oversize")
    return path.read_bytes()


def read_json(path: Path, root: Path) -> tuple[dict, str]:
    raw = read_file(path, root)
    value = json.loads(raw)
    require(type(value) is dict, "private_json_object_required")
    return value, sha(raw)


def active_world(private_root: Path) -> tuple[dict, list[dict], list[dict], list[dict], dict]:
    world, world_sha = read_json(private_root / "world-private.json", private_root)
    seed = read_file(private_root / "world-seed.txt", private_root, maximum=1024).decode().strip()
    built = factory.build_world(seed)
    for key, value in built.items():
        require(world.get(key) == value, "private_world_differs_from_pinned_generator")
    reserve = factory.reserve_replacement(seed)
    require(world.get("reserve_projects") == [reserve["project"]] and
            world.get("reserve_tasks") == reserve["tasks"] and
            world.get("reserve_source_excerpt_sha256") == reserve["source_excerpt_sha256"],
            "reserve_world_changed")
    quarantine, quarantine_sha = read_json(
        private_root / "exposed-families-private.json", private_root)
    require(quarantine.get("schema") == "envloop-gitlab-exposure-quarantine-v1" and
            type(quarantine.get("families")) is dict and len(quarantine["families"]) == 1,
            "exposure_quarantine_changed")
    excluded = set()
    for family, row in quarantine["families"].items():
        require(type(row) is dict and type(row.get("task_ids")) is list and
                len(row["task_ids"]) == 5 and row.get("reason") == "gui_development_control",
                "exposure_quarantine_changed")
        expected = {task["task_id"] for task in world["tasks"]
                    if task["source_family"] == family}
        require(set(row["task_ids"]) == expected and len(expected) == 5,
                "exposure_quarantine_does_not_cover_whole_family")
        excluded.update(expected)
    train = [row for row in world["tasks"] if row["partition"] == "train"]
    selection = [row for row in world["tasks"] if row["partition"] == "selection"]
    final = [row for row in world["tasks"] + world["reserve_tasks"]
             if row["partition"] == "final_candidate_unsealed"
             and row["task_id"] not in excluded]
    require((len(train), len(selection), len(final)) == (20, 20, 100) and
            len({row["task_id"] for row in train + selection + final}) == 140,
            "private_split_counts_or_uniqueness_changed")
    projects = {row["full_path"]: row for row in
                world["projects"] + world["reserve_projects"]}
    require(len(projects) == 31, "private_project_roster_changed")
    def identity(task: dict) -> dict:
        project = projects[task["project_family"]]
        sources = ([task["source_family"]] +
                   ["cisa-kev:" + item["cveID"] for item in project["advisories"]] +
                   ["cisa-vendor:" + item["vendorProject"].strip().casefold()
                    for item in project["advisories"]])
        return {"task_id": task["task_id"],
                "package_sha256": sha(canonical({"world_sha256": world_sha, "task": task})),
                "source_groups": sorted(set(sources)),
                "template_group": task["template_group"],
                "instance_group": "gitlab-task:" + task["task_id"]}
    sets = {"train": [identity(row) for row in sorted(train, key=lambda row: row["task_id"])],
            "selection": [identity(row) for row in sorted(selection, key=lambda row: row["task_id"])],
            "official": [identity(row) for row in sorted(final, key=lambda row: row["task_id"])]}
    scale_final_v06.validate_splits(sets)
    family, family_sha = read_json(private_root / "analysis-families-private.json", private_root)
    require(family.get("schema") == "cua-cell-analysis-families-v1" and
            family.get("cell_id") == "gitlab" and
            family.get("family_by_task") == {row["task_id"]: row["source_family"]
                                              for row in final} and
            len(set(family["family_by_task"].values())) == 20 and
            Counter(family["family_by_task"].values()) == Counter({
                source: 5 for source in set(family["family_by_task"].values())}),
            "analysis_family_map_changed")
    return world, train, selection, sorted(final, key=lambda row: row["task_id"]), {
        "world_sha256": world_sha, "quarantine_sha256": quarantine_sha,
        "analysis_families_sha256": family_sha, "task_sets": sets,
    }


def failure_history(private_root: Path, index: dict, final: list[dict],
                    *, index_sha: str) -> tuple[str, str, int]:
    raw = read_file(private_root / "gui-sweep-failures-v3.jsonl", private_root)
    require(raw.endswith(b"\n"), "failure_ledger_incomplete_tail")
    previous = "0" * 64
    entries = []
    for number, line in enumerate(raw.splitlines(), 1):
        value = json.loads(line)
        require(type(value) is dict and value.get("seq") == number and
                value.get("previous_sha256") == previous and
                value.get("entry_sha256") == sha(canonical({
                    key: item for key, item in value.items() if key != "entry_sha256"})),
                "failure_ledger_chain_changed")
        entries.append(value)
        previous = value["entry_sha256"]
    require(len(entries) == 6, "failure_ledger_denominator_changed")
    ledger = {entry["entry_sha256"]: entry for entry in entries}
    expected_ids = {row["task_id"] for row in final}
    items = index.get("items")
    require(index.get("schema") == "envloop-gitlab-development-sweep-v1" and
            type(items) is dict and set(items) == expected_ids,
            "gui_index_roster_changed")
    failure_refs = []
    for task_id, item in items.items():
        attempts = item.get("attempts")
        require(type(attempts) is list and len(attempts) in (1, 2) and
                attempts[-1]["status"] == "development_gui_trio_passed" and
                attempts[-1]["scores"] == [1.0, 0.0, 1.0] and
                attempts[-1]["cold_resets"] == 3 and
                item["status"] == attempts[-1]["status"] and
                item["scores"] == attempts[-1]["scores"] and
                item["cold_resets"] == 3,
                "gui_index_active_control_changed")
        for prior in attempts[:-1]:
            proof = prior.get("failure_ledger_entry_sha256")
            require(proof in ledger and ledger[proof]["task_id"] == task_id and
                    ledger[proof]["status"] == prior["status"],
                    "retained_failure_not_bound_to_index")
            failure_refs.append(proof)
    require(len(failure_refs) == 6 and set(failure_refs) == set(ledger),
            "retained_failure_count_or_coverage_changed")
    resolution, resolution_sha = read_json(
        private_root / "pre-result-recovery-resolution-private.json", private_root)
    first = {task_id: item["attempts"][0] for task_id, item in items.items()}
    require(resolution.get("original_active_denominator") == 100 and
            resolution.get("original_first_attempt_passes") == 94 and
            resolution.get("original_first_attempt_failures") == 6 and
            resolution.get("original_first_attempts_sha256") == sha(canonical(first)) and
            resolution.get("original_active_roster_sha256") ==
            sha(canonical(sorted(expected_ids))) and
            resolution.get("failure_ledger_head_sha256") == previous and
            resolution.get("no_model_calls") is True and
            resolution.get("official_final_admitted") == 0,
            "pre_result_resolution_differs_from_preserved_history")
    audit, audit_sha = read_json(
        private_root / "requalification-100-audit.private.json", private_root)
    public = json.loads(PUBLIC_REQUALIFICATION.read_bytes())
    require(public.get("private_audit_sha256") == audit_sha and
            public.get("index_sha256") == index_sha and
            audit.get("index_sha256") == index_sha and
            audit.get("resolution_sha256") == resolution_sha and
            audit.get("failure_ledger_head_sha256") == previous and
            audit.get("current_gui_trios_passed") == 100 and
            audit.get("current_cold_resets_verified") == 300 and
            audit.get("official_final_admitted") == 0,
            "dated_requalification_audit_differs_from_private_evidence")
    return previous, resolution_sha, len(entries)


def verify_snapshot(snapshot: dict, baseline: dict, expected_digest: str) -> None:
    require(snapshot.get("schema") == baseline["schema"] and
            snapshot.get("project_ids") == baseline["project_ids"] and
            snapshot.get("business_sha256") == expected_digest and
            sha(canonical({key: value for key, value in snapshot.items()
                           if key != "business_sha256"})) == expected_digest,
            "persisted_state_readback_changed")


def verify_case(root: Path, folder: Path, attempt: dict, *, task_id: str,
                baseline: dict, expected_score: float) -> dict:
    require(type(attempt) is dict and attempt.get("task_id") == task_id and
            attempt.get("schema") == "envloop-gitlab-gui-control-attempt-v1" and
            attempt.get("case") == folder.name and
            attempt.get("fresh_browser_context") is True and
            attempt.get("scoped_non_admin_operator") is True and
            attempt.get("credential_retained_in_receipt") is False and
            attempt.get("raw_har_retained") is False and
            attempt.get("model_calls") == 0,
            "case_actor_provenance_changed")
    raw_receipt = dict(attempt)
    raw_receipt.pop("cold_reset", None)
    receipt, receipt_sha = read_json(folder / "receipt.json", root)
    require(receipt == raw_receipt, "raw_case_receipt_differs_from_trio")
    saved, saved_sha = read_json(folder / "after-persisted-state.json", root)
    oracle = attempt.get("persisted_oracle")
    require(type(oracle) is dict and oracle.get("task_id") == task_id and
            oracle.get("score") == expected_score and
            oracle.get("persisted_oracle") is True and
            oracle.get("no_regression") is (expected_score == 1.0) and
            oracle.get("before_business_sha256") == baseline["business_sha256"] and
            oracle.get("after_business_sha256") != baseline["business_sha256"],
            "case_oracle_or_no_regression_changed")
    verify_snapshot(saved, baseline, oracle["after_business_sha256"])
    reset = attempt.get("cold_reset")
    require(type(reset) is dict and reset.get("cold_reset") is True and
            reset.get("same_business_sha256") is True and
            reset.get("container_identity_changed") is True and
            type(reset.get("generation")) is int and reset["generation"] > 0,
            "case_fresh_reset_receipt_changed")
    gui = attempt.get("gui")
    require(type(gui) is dict and gui.get("policy_rendered") is True and
            gui.get("saved_visible") is True, "case_visible_gui_control_changed")
    named = gui.get("screenshot_sha256")
    if named is None:
        named = {filename: gui[field] for field, filename in SCREENSHOT_BY_FIELD.items()
                 if field in gui}
        require(len(named) == 2, "case_screen_hashes_missing")
    require(type(named) is dict and len(named) >= 2, "case_screen_hashes_missing")
    files = {}
    for name, expected in named.items():
        require(type(name) is str and name.endswith(".png") and
                Path(name).name == name and scale_final_v06.is_hash(expected),
                "case_screen_reference_invalid")
        actual = sha(read_file(folder / name, root))
        require(actual == expected, "case_screen_bytes_changed")
        files[name] = actual
    return {"case": folder.name, "receipt_sha256": receipt_sha,
            "persisted_state_sha256": saved_sha,
            "screenshot_sha256s": files,
            "mutated_business_sha256": oracle["after_business_sha256"],
            "reset_generation": reset["generation"]}


def verify_trio(private_root: Path, task: dict, index_item: dict,
                baseline: dict) -> dict:
    task_id = task["task_id"]
    controls_root = private_root / "gui-controls"
    require(controls_root.is_dir() and not controls_root.is_symlink() and
            controls_root.stat().st_mode & 0o077 == 0,
            "gui_controls_root_not_restrictive")
    folder = private_root / "gui-controls" / task_id
    # The enclosing gui-controls directory is mode 0700. Eight early task
    # folders retained mode 0755, but cannot be traversed past that parent.
    require(folder.is_dir() and not folder.is_symlink(),
            "task_gui_folder_missing_or_unsafe")
    runs = sorted(path for path in folder.iterdir()
                  if path.is_dir() and path.name.startswith("trio-"))
    require(runs and all(path.name[5:].isdigit() and not path.is_symlink()
                         for path in runs), "task_gui_run_history_invalid")
    current = runs[-1]
    trio, trio_sha = read_json(current / "trio-private.json", private_root)
    require(trio.get("schema") == "envloop-gitlab-original-world-gui-trio-v1" and
            trio.get("task_id") == task_id and
            trio.get("source_family_sha256") == sha(task["source_family"].encode()) and
            trio.get("scores") == [1.0, 0.0, 1.0] and
            trio.get("cold_resets") == 3 and
            trio.get("fresh_browser_attempts") == 3 and
            trio.get("development_gui_control_passed") is True and
            trio.get("evaluator_owned_private_control") is True and
            trio.get("model_calls") == 0 and
            trio.get("official_final_admitted") == 0 and
            trio.get("scores") == index_item["scores"] and
            trio.get("source_family_sha256") == index_item["source_family_sha256"],
            "latest_gui_trio_differs_from_active_index")
    attempts = trio.get("attempts")
    require(type(attempts) is list and len(attempts) == 3 and
            [row.get("case") for row in attempts] ==
            ["positive-1", NEGATIVE_CASE_BY_FAMILY[task["template_group"]],
             "positive-2"],
            "gui_trio_case_order_invalid")
    cases = [verify_case(private_root, current / row["case"], row,
                         task_id=task_id, baseline=baseline, expected_score=score)
             for row, score in zip(attempts, (1.0, 0.0, 1.0), strict=True)]
    generations = [row["reset_generation"] for row in cases]
    require(generations == list(range(generations[0], generations[0] + 3)),
            "three_cold_resets_not_consecutive")
    return {"task_id": task_id, "current_trio_sha256": trio_sha,
            "retained_run_count": len(runs), "cases": cases,
            "first_failed_index_attempt_retained": len(index_item["attempts"]) == 2}


def audit(private_root: Path, ratification_path: Path) -> tuple[dict, dict]:
    private_root = private_root.absolute()
    world, train, selection, final, context = active_world(private_root)
    baseline, baseline_sha = read_json(
        private_root / "baseline-persisted-state.json", private_root)
    verify_snapshot(baseline, baseline, baseline["business_sha256"])
    index, index_sha = read_json(
        private_root / "gui-development-sweep-index-v3.json", private_root)
    ledger_head, resolution_sha, failed_count = failure_history(
        private_root, index, final, index_sha=index_sha)
    ratification, ratification_sha = validate_ratification(ratification_path)
    ratification_public = json.loads(PUBLIC_RATIFICATION.read_bytes())
    require(ratification_public.get("private_ratification_sha256") == ratification_sha and
            ratification_public.get("qualified_final_tasks") == 0 and
            ratification_public.get("researcher_campaigns") == 0 and
            ratification["cell_profiles"]["gitlab"]["adapter_sha256"] ==
            sha((ROOT / "gitlab_world/vision_actor_v066_train.py").read_bytes()),
            "v066_action_code_ratification_changed")
    raw_controls = [verify_trio(private_root, task, index["items"][task["task_id"]],
                                baseline) for task in final]
    require(sum(row["first_failed_index_attempt_retained"] for row in raw_controls) ==
            failed_count, "prior_failures_not_preserved_per_id")
    identities = context["task_sets"]
    ledger = [{**identity, "control_evidence": raw,
               "control_preflight_passed": True, "official_admitted": False,
               "admission_blockers": list(BLOCKERS)}
              for identity, raw in zip(identities["official"], raw_controls, strict=True)]
    require(all(row["task_id"] == row["control_evidence"]["task_id"] for row in ledger),
            "task_identity_control_order_mismatch")
    private = {
        "schema": PRIVATE_SCHEMA,
        "status": "evaluator_gui_controls_verified_not_officially_admitted",
        "cell_id": "gitlab", "application": "GitLab CE 18.5.0-ce.0",
        "auditor_source_sha256": sha(Path(__file__).read_bytes()),
        "source_is_original_envloop_cisa_anchored_tasks": True,
        "world_sha256": context["world_sha256"],
        "source_excerpt_sha256": world["source"]["excerpt_sha256"],
        "quarantine_sha256": context["quarantine_sha256"],
        "analysis_families_sha256": context["analysis_families_sha256"],
        "baseline_snapshot_sha256": baseline_sha,
        "index_sha256": index_sha,
        "resolution_sha256": resolution_sha,
        "failure_ledger_head_sha256": ledger_head,
        "v066_code_only_ratification_sha256": ratification_sha,
        "task_sets": {"train": identities["train"],
                      "selection": identities["selection"],
                      "provisional_final": identities["official"]},
        "per_task_control_evidence": ledger,
        "admission_blockers": list(BLOCKERS),
        "official_final_admitted": 0, "model_calls_in_controls": 0,
        "researcher_campaigns": 0,
    }
    public = {
        "schema": PUBLIC_SCHEMA,
        "status": "100_individual_evaluator_gui_controls_verified_not_admitted",
        "cell_id": "gitlab", "application": "GitLab CE 18.5.0-ce.0",
        "auditor_source_sha256": private["auditor_source_sha256"],
        "real_advisory_source": "CISA KEV CC0; internal operations are synthetic",
        "train_candidates": len(train), "selection_candidates": len(selection),
        "provisional_final_candidates": len(final),
        "final_source_families": 20, "tasks_per_source_family": 5,
        "current_gui_positive_negative_positive_trios": len(raw_controls),
        "current_cold_reset_receipts": sum(len(row["cases"]) for row in raw_controls),
        "retained_first_attempt_failures": failed_count,
        "all_raw_case_receipts_snapshots_and_named_screens_rehashed": True,
        "index_sha256": index_sha,
        "analysis_families_sha256": context["analysis_families_sha256"],
        "failure_ledger_head_sha256": ledger_head,
        "v066_code_only_ratification_sha256": ratification_sha,
        "admission_blockers": list(BLOCKERS),
        "official_final_admitted": 0, "official_model_outcomes": 0,
        "researcher_campaigns": 0,
    }
    return private, public


def write_new(path: Path, value: dict, mode: int) -> str:
    raw = (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return sha(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--ratification", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    private_out = args.private_out.absolute()
    public_out = args.public_out.absolute()
    require(private_out.parent == args.private_root.absolute() and
            public_out.parent == (ROOT / "docs/evidence").absolute() and
            not private_out.exists() and not public_out.exists(),
            "fresh_private_and_public_output_paths_required")
    private, public = audit(args.private_root, args.ratification)
    private_sha = write_new(private_out, private, 0o600)
    public["private_per_task_ledger_sha256"] = private_sha
    public_sha = write_new(public_out, public, 0o644)
    print(json.dumps({"status": public["status"],
                      "public_sha256": public_sha,
                      "official_final_admitted": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
