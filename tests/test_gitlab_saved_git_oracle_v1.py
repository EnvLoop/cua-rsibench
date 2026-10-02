"""Offline replays keep all unchanged Git path/content and SQL predicates."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import unittest
from unittest.mock import patch

from gitlab_world import factory, verify
from gitlab_world import v066_saved_git_oracle_v1 as saved


PROJECT = {"full_path": "final/consumed-fixture", "asset_id": "INV-FIXTURE",
           "principals": {"oncall": "fixture-oncall"},
           "policy": {"issue_due": "2030-01-07", "milestone_title": "Fixture release",
                      "milestone_start": "2030-01-02", "milestone_due": "2030-01-09",
                      "access_expiry": "2030-02-01"},
           "files": {"README.md": "fixture\n", ".gitlab-ci.yml": "job:\n  rules:\n    - when: never\n",
                     "docs/response-runbook.md": "# Runbook\nCurrent contact: pending\n",
                     "security/kev-register.csv": "asset,cve\n",
                     "security/release-policy.md": "policy\n", "security/SECURITY.md": "security\n"}}
PROGRESS = {"project_id": 1, "issue_iids": {"active": 1, "validation": 2},
            "user_ids": {"oncall": 10, "contractor": 11, "incoming": 12},
            "mr_iids": {"approved": 1, "stale": 2}}
FAMILIES = ("cross_record_issue_triage", "release_milestone_coordination", "approved_merge_request_merge",
            "least_privilege_access_handoff", "ci_and_runbook_reconciliation")


def seal(value):
    value.pop("business_sha256", None)
    value["business_sha256"] = saved.sha256(factory.canonical(value))
    return value


def task(family):
    return {"task_id": "consumed-" + str(FAMILIES.index(family)), "partition": "final_candidate_unsealed",
            "project_family": PROJECT["full_path"], "template_group": family,
            "oracle": {"cve": "CVE-2030-0001", "expected_priority": "priority::p2"}}


def baseline():
    return seal({"schema": verify.SCHEMA, "project_ids": [1], "db": {
        "projects": [{"id": 1}], "issues": [
            {"id": 101, "project_id": 1, "iid": 1, "title": "active", "due_date": None, "milestone_id": None},
            {"id": 102, "project_id": 1, "iid": 2, "title": "validation", "due_date": None, "milestone_id": None}],
        "issue_assignees": [], "labels": [{"id": 201, "project_id": 1, "title": "priority::p2"}],
        "issue_label_links": [], "milestones": [],
        "members": [{"id": 301, "source_id": 1, "user_id": 11, "access_level": 20, "expires_at": None},
                    {"id": 302, "source_id": 1, "user_id": 10, "access_level": 30, "expires_at": None}],
        "merge_requests": [{"id": 401 + i, "target_project_id": 1, "iid": 1 + i, "source_branch": "response-cve-fixture-" + str(i),
                            "target_branch": "main", "state_id": 1, "merge_commit_sha": None,
                            "merged_commit_sha": None} for i in range(2)]},
        "git": {"1": {"refs": {"refs/heads/main": "a" * 40,
                                 "refs/heads/response-cve-fixture-0": "b" * 40,
                                 "refs/heads/response-cve-fixture-1": "c" * 40},
                       "main_blobs_sha256": {path: saved.sha256(text.encode()) for path, text in PROJECT["files"].items()}}}})


def changed(family, negative=False):
    after = deepcopy(baseline())
    files = {path: text.encode() for path, text in PROJECT["files"].items()}
    policy = PROJECT["policy"]
    if family == FAMILIES[0]:
        index = 1 if negative else 0
        after["db"]["issues"][index]["due_date"] = policy["issue_due"]
        after["db"]["issue_assignees"].append({"issue_id": 101 + index, "user_id": 10})
        after["db"]["issue_label_links"].append({"id": 202, "target_id": 101 + index, "label_id": 201})
    elif family == FAMILIES[1]:
        after["db"]["milestones"].append({"id": 501, "project_id": 1, "title": policy["milestone_title"],
                                          "start_date": policy["milestone_start"],
                                          "due_date": "2030-03-01" if negative else policy["milestone_due"]})
        for issue in after["db"]["issues"]:issue["milestone_id"] = 501
    elif family == FAMILIES[2]:
        after["db"]["merge_requests"][1 if negative else 0].update(
            state_id=3, merge_commit_sha="d" * 40, merged_commit_sha="d" * 40)
        suffix = ("Stale workaround for retired INV-FIXTURE-legacy; do not release.\n" if negative else
                  "Approved remediation evidence for CVE-2030-0001 on INV-FIXTURE-1.\n")
        files["docs/response-runbook.md"] += b"\n" + suffix.encode()
    elif family == FAMILIES[3]:
        after["db"]["members"] = [after["db"]["members"][1],
                                   {"id": 303, "source_id": 1, "user_id": 12,
                                    "access_level": 40 if negative else 20, "expires_at": policy["access_expiry"]}]
    else:
        files[".gitlab-ci.yml"] = PROJECT["files"][".gitlab-ci.yml"].replace(
            "    - when: never\n", "    - if: '$CI_PIPELINE_SOURCE == \"merge_request_event\"'\n").encode()
        if not negative:
            files["docs/response-runbook.md"] = PROJECT["files"]["docs/response-runbook.md"].replace(
                "Current contact: pending", "Current contact: @fixture-oncall").encode()
    if family in (FAMILIES[2], FAMILIES[4]):
        after["git"]["1"]["refs"]["refs/heads/main"] = "d" * 40
        after["git"]["1"]["main_blobs_sha256"] = {path: saved.sha256(raw) for path, raw in files.items()}
    return seal(after), files


def object_id(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def sidecar(before, after, files, extra=None, before_extra=None):
    old_files = {path: text.encode() for path, text in PROJECT["files"].items()}
    before_tree = {path: ("100644", "blob", object_id(raw)) for path, raw in old_files.items()}
    after_tree = {path: ("100644", "blob", object_id(raw)) for path, raw in files.items()}
    before_tree.update(before_extra or {})
    after_tree.update(extra or {})
    def tree_bytes(tree):
        return b"".join((" ".join(tree[path]) + "\t" + path).encode() + b"\0" for path in sorted(tree))
    changed_paths = {path for path in set(before_tree) | set(after_tree) if before_tree.get(path) != after_tree.get(path)}
    raws = {}
    def ref(name, raw):
        raws[name] = raw
        return {"path": name, "sha256": saved.sha256(raw)}
    value = {"schema": saved.SIDECAR_SCHEMA, "project_id": 1,
             "before_main_sha": before["git"]["1"]["refs"]["refs/heads/main"],
             "after_main_sha": after["git"]["1"]["refs"]["refs/heads/main"],
             "before_business_sha256": before["business_sha256"], "after_business_sha256": after["business_sha256"],
             "before_tree_ref": ref("git/before-tree.raw", tree_bytes(before_tree)),
             "after_tree_ref": ref("git/after-tree.raw", tree_bytes(after_tree)),
             "diff_ref": ref("git/diff.raw", ("\n".join(sorted(changed_paths)) + ("\n" if changed_paths else "")).encode()),
             "main_blob_refs": {path: ref("git/blob-" + str(i) + ".raw", raw) for i, (path, raw) in enumerate(files.items())}}
    return value, raws


class SavedGitOracleTests(unittest.TestCase):
    def score(self, family, after, **kwargs):
        return saved.audit_saved_task(task(family), baseline(), after, project=PROJECT, progress=PROGRESS, **kwargs)

    def test_all_five_three_phase_verdicts_match_unchanged_live_callbacks(self):
        for family in FAMILIES:
            for negative in (False, True, False):
                after, files = changed(family, negative)
                paths = {p for p in saved.MONITORED_PATHS if baseline()["git"]["1"]["main_blobs_sha256"][p] != after["git"]["1"]["main_blobs_sha256"][p]}
                with patch.object(verify, "_context", return_value=(PROJECT, PROGRESS)), \
                     patch.object(verify, "_changed_paths", return_value=paths), \
                     patch.object(verify, "git_blob", side_effect=lambda _pid, _ref, path: files[path]):
                    captured = verify.evaluate_final_task(task(family), baseline(), after, inspect_live_git=True)
                audited = self.score(family, after, captured_verdict=captured)
                self.assertIs(audited["captured_live_verdict_matches"], True)
                self.assertEqual(audited["verdict"]["score"], 0.0 if negative else 1.0)
                self.assertIs(audited["verdict"]["no_regression"], not negative)
                self.assertIs(audited["full_git_tree_verified"], False)

    def test_partial_ci_negative_preserves_exact_false_no_regression_and_reason(self):
        after, _ = changed(FAMILIES[4], True)
        with patch.object(verify, "_context", return_value=(PROJECT, PROGRESS)):
            bad_replay = verify.evaluate_final_task(task(FAMILIES[4]), baseline(), after, inspect_live_git=False)
        self.assertEqual((bad_replay["score"], bad_replay["no_regression"]), (1.0, True))
        verdict = self.score(FAMILIES[4], after)["verdict"]
        self.assertEqual((verdict["score"], verdict["no_regression"]), (0.0, False))
        self.assertEqual(verdict["failure_code"], "CI/runbook task changed unexpected files")

    def test_historical_unknown_hash_and_unknown_monitored_path_fail_closed(self):
        after, _ = changed(FAMILIES[4])
        for mode in ("hash", "path", "digest"):
            bad = deepcopy(after)
            if mode == "hash":bad["git"]["1"]["main_blobs_sha256"][".gitlab-ci.yml"] = "f" * 64
            elif mode == "path":bad["git"]["1"]["main_blobs_sha256"]["unknown.txt"] = "f" * 64
            else:bad["business_sha256"] = "f" * 64
            if mode != "digest":seal(bad)
            with self.subTest(mode=mode), self.assertRaises(saved.SavedGitEvidenceError):self.score(FAMILIES[4], bad)

    def test_historical_content_predicate_runs_when_both_paths_changed(self):
        after, _ = changed(FAMILIES[4])
        # A known approved-MR blob is not the required on-call runbook content.
        approved, _ = changed(FAMILIES[2])
        after["git"]["1"]["main_blobs_sha256"]["docs/response-runbook.md"] = approved["git"]["1"]["main_blobs_sha256"]["docs/response-runbook.md"]
        seal(after)
        verdict = self.score(FAMILIES[4], after)["verdict"]
        self.assertEqual(verdict["score"], 0.0)
        self.assertEqual(verdict["failure_code"], "CI rule or runbook contact is incorrect")

    def test_complete_sidecar_proves_full_tree_and_preserves_content_checks(self):
        after, files = changed(FAMILIES[4])
        evidence, raws = sidecar(baseline(), after, files)
        result = self.score(FAMILIES[4], after, captured_git=evidence, read_ref=lambda ref: raws[ref["path"]])
        self.assertEqual(result["verdict"]["score"], 1.0)
        self.assertIs(result["full_git_tree_verified"], True)
        self.assertEqual(len(result["raw_git_refs"]), 9)

    def test_full_tree_detects_unmonitored_file_and_mode_changes(self):
        after, files = changed(FAMILIES[4])
        for extra in ({"unmonitored.txt": ("100644", "blob", "e" * 40)},
                      {"README.md": ("100755", "blob", object_id(files["README.md"]))}):
            evidence, raws = sidecar(baseline(), after, files, extra=extra)
            verdict = self.score(FAMILIES[4], after, captured_git=evidence, read_ref=lambda ref: raws[ref["path"]])["verdict"]
            self.assertEqual((verdict["score"], verdict["no_regression"]), (0.0, False))
            self.assertEqual(verdict["failure_code"], "CI/runbook task changed unexpected files")

    def test_raw_diff_tree_blob_and_snapshot_binding_mutations_fail_closed(self):
        after, files = changed(FAMILIES[4])
        for mutation in ("commit", "business", "blob", "tree", "diff", "rawhash", "path"):
            evidence, raws = sidecar(baseline(), after, files)
            if mutation == "commit":evidence["after_main_sha"] = "e" * 40
            elif mutation == "business":evidence["after_business_sha256"] = "e" * 64
            elif mutation == "blob":
                ref = evidence["main_blob_refs"][".gitlab-ci.yml"];raws[ref["path"]] = b"wrong";ref["sha256"] = saved.sha256(b"wrong")
            elif mutation in ("tree", "diff"):
                ref = evidence["after_tree_ref" if mutation == "tree" else "diff_ref"]
                raws[ref["path"]] = b"";ref["sha256"] = saved.sha256(b"")
            elif mutation == "rawhash":raws[evidence["diff_ref"]["path"]] += b"wrong\n"
            else:evidence["diff_ref"]["path"] = "../outside"
            with self.subTest(mutation=mutation), self.assertRaises(saved.SavedGitEvidenceError):
                self.score(FAMILIES[4], after, captured_git=evidence, read_ref=lambda ref: raws[ref["path"]])

    def test_captured_unknown_content_scores_zero_without_reconstructing_it(self):
        after, files = changed(FAMILIES[4])
        files["docs/response-runbook.md"] = b"wrong captured contact\n"
        after["git"]["1"]["main_blobs_sha256"]["docs/response-runbook.md"] = saved.sha256(files["docs/response-runbook.md"])
        seal(after)
        evidence, raws = sidecar(baseline(), after, files)
        verdict = self.score(FAMILIES[4], after, captured_git=evidence, read_ref=lambda ref: raws[ref["path"]])["verdict"]
        self.assertEqual(verdict["failure_code"], "CI rule or runbook contact is incorrect")

    def test_no_native_calls_or_global_mutation_and_source_pin_required(self):
        after, _ = changed(FAMILIES[4])
        original = (verify._git, verify.git_blob, verify._context, verify._changed_paths)
        with patch.object(verify, "_git", side_effect=AssertionError("live Git forbidden")), \
             patch.object(verify.bootstrap, "world", side_effect=AssertionError("world lookup forbidden")), \
             patch.object(verify, "evaluate_final_task", side_effect=AssertionError("mutable global wrapper forbidden")):
            self.assertEqual(self.score(FAMILIES[4], after)["verdict"]["score"], 1.0)
        self.assertEqual(original, (verify._git, verify.git_blob, verify._context, verify._changed_paths))
        with self.assertRaisesRegex(saved.SavedGitEvidenceError, "verifier_source_changed"):
            self.score(FAMILIES[4], after, expected_verifier_sha256="f" * 64)
        with self.assertRaisesRegex(saved.SavedGitEvidenceError, "captured_live_verdict_disagrees"):
            self.score(FAMILIES[4], after, captured_verdict={"score": 0.0})


if __name__ == "__main__":
    unittest.main()
