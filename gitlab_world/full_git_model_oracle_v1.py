"""Formal TRAIN/selection/final readback with mandatory complete Git capture.

The partition graders' function code and reward values are unchanged. This
module supplies their read-only context in isolated globals, validates raw
full-tree/diff/blob evidence, and refuses unsupported positive proof scopes.
No task/world lookup, captured-boolean credit, or historical projection exists.
"""
from __future__ import annotations

import copy
from pathlib import Path
from types import SimpleNamespace

from . import factory, verify, train_teacher_oracle_v066 as train_oracle
from . import selection_oracle_v066 as selection_oracle
from . import v066_saved_git_oracle_v1 as saved

SCHEMA = "envloop-gitlab-model-full-git-oracle-v1"
PARTITIONS = frozenset({"train", "selection", "final_candidate_unsealed"})
SOURCE_FILES = (
    "gitlab_world/full_git_model_oracle_v1.py", "gitlab_world/v066_saved_git_oracle_v1.py",
    "gitlab_world/verify.py", "gitlab_world/factory.py",
    "gitlab_world/train_teacher_oracle_v066.py", "gitlab_world/selection_oracle_v066.py",
)
_ORIGINAL_TRAIN = train_oracle.evaluate_train_task
_ORIGINAL_SELECTION = selection_oracle.evaluate_selection_task
_ORIGINAL_CHANGED_PATHS = verify._changed_paths
_ORIGINAL_GIT_BLOB = verify.git_blob


def _require(ok, code):
    if not ok:
        raise saved.SavedGitEvidenceError(code)


def source_bindings() -> dict:
    root = Path(__file__).resolve().parents[1]
    return {name: saved.sha256((root / name).read_bytes()) for name in SOURCE_FILES}


def _check_sources(expected):
    actual = source_bindings()
    _require(type(expected) is dict and set(actual) <= set(expected) and
             all(type(expected[name]) is str and expected[name] == digest
                 for name, digest in actual.items()), "formal_model_oracle_source_binding_changed")
    return actual


def _identity(task, project, progress, partition):
    _require(partition in PARTITIONS and type(task) is dict and type(project) is dict and
             task.get("partition") == partition and project.get("partition") == partition and
             task.get("project_family") == project.get("full_path") and
             type(progress) is dict and type(progress.get("project_id")) is int and progress["project_id"] > 0,
             "formal_model_oracle_partition_or_context_changed")
    families = train_oracle.TRAIN_FAMILIES if partition == "train" else (
        selection_oracle.SELECTION_FAMILIES if partition == "selection" else frozenset({
            "cross_record_issue_triage", "release_milestone_coordination", "approved_merge_request_merge",
            "least_privilege_access_handoff", "ci_and_runbook_reconciliation"}))
    _require(task.get("template_group") in families, "formal_model_oracle_family_not_supported")


def _reader(task, before, after, project, progress, captured_git, read_ref):
    _require(captured_git is not None and callable(read_ref), "formal_model_full_git_capture_required")
    reader = saved.SavedGitReader(task=task, project=project, progress=progress, before=before, after=after,
                                  captured_git=captured_git, read_ref=read_ref)
    _require(reader.full_tree_verified is True, "formal_model_full_git_capture_required")
    before_tree = saved._tree(saved._read_ref(captured_git["before_tree_ref"], read_ref))
    after_tree = saved._tree(saved._read_ref(captured_git["after_tree_ref"], read_ref))
    _require(reader.before_sha != reader.after_sha or before_tree == after_tree,
             "formal_model_same_commit_tree_disagrees")
    return reader, before_tree, after_tree


def _proof_scope(reader, before_tree, after_tree):
    return {
        "git_evidence_mode": "captured_full_tree_diff_and_blobs",
        "target_project_id": reader.project_id, "before_main_sha": reader.before_sha,
        "after_main_sha": reader.after_sha, "changed_paths": sorted(reader.changed_paths),
        "before_full_tree_entries": len(before_tree), "after_full_tree_entries": len(after_tree),
        "raw_git_refs": reader.raw_refs,
    }


def audit_model_saved_task(task, before, after, *, project, progress, captured_git, read_ref,
                           partition, expected_sourcebindings):
    """Return the original partition verdict plus source-bound full Git proof."""
    bindings = _check_sources(expected_sourcebindings)
    _identity(task, project, progress, partition)
    task, project, progress = copy.deepcopy((task, project, progress))
    reader, before_tree, after_tree = _reader(task, before, after, project, progress, captured_git, read_ref)
    scope = _proof_scope(reader, before_tree, after_tree)
    if partition == "final_candidate_unsealed":
        formal = saved.audit_formal_saved_task(
            task, before, after, project=project, progress=progress, captured_git=captured_git,
            read_ref=read_ref, expected_verifier_sha256=bindings["gitlab_world/verify.py"])
        _require(formal["full_git_tree_verified"] is True and formal["captured_live_verdict_matches"] is None,
                 "formal_model_final_reader_boundary_changed")
        verdict = formal["verdict"]
        reward = verdict["score"]
    else:
        # Validate the entire tree scope rather than interpreting six monitored
        # blob hashes as an assertion about every Git path or file mode.
        allowed = {"docs/response-runbook.md"} if task["template_group"] == "runbook_contact_annotation" else set()
        namespace = SimpleNamespace(**verify.__dict__)
        namespace._context = lambda candidate: (project, progress) if candidate == task else (_ for _ in ()).throw(
            saved.SavedGitEvidenceError("formal_model_task_context_changed"))
        globals_copy = dict(verify.__dict__)
        globals_copy["_git"] = reader.git
        namespace._git = reader.git
        namespace.git_blob = saved._copy_function(_ORIGINAL_GIT_BLOB, globals_copy)
        namespace._changed_paths = saved._copy_function(_ORIGINAL_CHANGED_PATHS, globals_copy)
        original = _ORIGINAL_TRAIN if partition == "train" else _ORIGINAL_SELECTION
        oracle_globals = dict(original.__globals__)
        oracle_globals["verify"] = namespace
        evaluator = saved._copy_function(original, oracle_globals)
        verdict = evaluator(task, before, after)
        reward = verdict["reward"]
        # Preserve the original grader's normal negative exactly. Complete
        # evidence of an unrelated Git edit is a model failure, not an
        # infrastructure exception. Unsupported scope cannot grant a positive.
        if reward == 1.0:
            _require(reader.changed_paths <= allowed, "formal_model_extra_git_path_positive_not_supported")
            _require(all(path in before_tree and path in after_tree and
                         before_tree[path][:2] == after_tree[path][:2]
                         for path in reader.changed_paths), "formal_model_git_mode_or_type_positive_not_supported")
    _require(type(reward) is float and reward in (0.0, 1.0), "formal_model_original_reward_invalid")
    return {"schema": SCHEMA, "partition": partition, "task_id": task["task_id"],
            "verdict": verdict, "reward": reward, "proof_scope": scope,
            "full_git_tree_verified": True, "complete_git_predicates_decidable": True,
            "historical_projection_allowed": False, "captured_live_verdict_is_authority": False,
            "original_grading_function_code_used": True, "source_bindings": bindings, "live_calls": 0}


def capture_model_git(task, before, after, *, project, progress, partition, git, save_ref):
    """Capture before reset through explicit native-Git/artifact callbacks.

    ``git(project_id, *args)`` returns raw bytes; ``save_ref(name, bytes)``
    returns an owner-only relative artifact reference. No default live reader
    or task lookup is supplied. The sidecar is identical to the frozen reader's.
    """
    _identity(task, project, progress, partition)
    _require(callable(git) and callable(save_ref), "formal_model_capture_callbacks_required")
    saved._snapshot(before)
    saved._snapshot(after)
    pid = progress["project_id"]
    old = before["git"][str(pid)]["refs"]["refs/heads/main"]
    new = after["git"][str(pid)]["refs"]["refs/heads/main"]
    _require(type(old) is str and type(new) is str and saved._HEX40.fullmatch(old) is not None and
             saved._HEX40.fullmatch(new) is not None, "formal_model_capture_commit_invalid")
    raw_by_ref = {}

    def retain(name, *args):
        raw = git(pid, *args)
        _require(type(raw) is bytes and len(raw) <= 8_000_000, "formal_model_capture_bytes_invalid")
        ref = save_ref(name, raw)
        checked = saved._read_ref(ref, lambda _ref: raw)
        _require(ref["path"] not in raw_by_ref, "formal_model_capture_ref_reused")
        raw_by_ref[ref["path"]] = checked
        return ref

    sidecar = {
        "schema": saved.SIDECAR_SCHEMA, "project_id": pid,
        "before_main_sha": old, "after_main_sha": new,
        "before_business_sha256": before["business_sha256"], "after_business_sha256": after["business_sha256"],
        "diff_ref": retain("diff.private.txt", "diff", "--name-only", old, new),
        "before_tree_ref": retain("before-tree.private.bin", "ls-tree", "-r", "-z", "--full-tree", old),
        "after_tree_ref": retain("after-tree.private.bin", "ls-tree", "-r", "-z", "--full-tree", new),
        "main_blob_refs": {},
    }
    for number, path in enumerate(sorted(saved.MONITORED_PATHS)):
        sidecar["main_blob_refs"][path] = retain(f"blob-{number}.private.bin", "show", new + ":" + path)
    _reader(task, before, after, project, progress, sidecar, lambda ref: raw_by_ref[ref["path"]])
    return sidecar


__all__ = ["audit_model_saved_task", "capture_model_git", "source_bindings", "SOURCE_FILES", "PARTITIONS", "SCHEMA"]
