"""Unchanged GitLab verifier with bound offline Git readers.

Historical six-blob snapshots can reconstruct only their monitored paths and
known frozen source bytes. They cannot establish a complete historical Git
tree. A captured full-tree/diff/blob sidecar provides that stronger coverage.
No live Git, Docker, application, world loader, or task lookup is called here.
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path, PurePosixPath
import re
from types import FunctionType

from . import factory, verify

_ORIGINAL_EVALUATOR = verify.evaluate_final_task
_ORIGINAL_GIT_BLOB = verify.git_blob
_ORIGINAL_CHANGED_PATHS = verify._changed_paths
SIDECAR_SCHEMA = "envloop-gitlab-saved-git-sidecar-v1"
AUDIT_SCHEMA = "envloop-gitlab-saved-git-oracle-audit-v1"
MONITORED_PATHS = frozenset({"README.md", ".gitlab-ci.yml", "docs/response-runbook.md",
                           "security/kev-register.csv", "security/release-policy.md", "security/SECURITY.md"})
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class SavedGitEvidenceError(ValueError):
    """Missing or contradictory evidence must never be a positive verdict."""


def _require(ok, code):
    if not ok:
        raise SavedGitEvidenceError(code)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def verifier_sha256() -> str:
    return sha256(Path(verify.__file__).read_bytes())


def _snapshot(value):
    _require(type(value) is dict and value.get("schema") == verify.SCHEMA,
             "saved_git_snapshot_schema_invalid")
    body = copy.deepcopy(value)
    digest = body.pop("business_sha256", None)
    _require(type(digest) is str and _HEX64.fullmatch(digest) is not None and
             sha256(factory.canonical(body)) == digest, "saved_git_snapshot_digest_changed")


def _path(value):
    _require(type(value) is str and value and "\0" not in value and "\n" not in value and
             "\r" not in value and not PurePosixPath(value).is_absolute() and
             all(part not in (".", "..", "") for part in value.split("/")),
             "saved_git_path_invalid")
    return value


def frozen_blob_candidates(task: dict, project: dict) -> dict[str, bytes]:
    """Known frozen source variants, matched only through recorded SHA256."""
    files = project.get("files")
    _require(type(files) is dict and set(files) == MONITORED_PATHS and
             all(type(text) is str for text in files.values()), "saved_git_frozen_files_invalid")
    pool = {sha256(text.encode()): text.encode() for text in files.values()}
    ci = files[".gitlab-ci.yml"].replace(
        "    - when: never\n", "    - if: '$CI_PIPELINE_SOURCE == \"merge_request_event\"'\n")
    runbook = files["docs/response-runbook.md"]
    contact = runbook.replace("Current contact: pending", "Current contact: @" + project["principals"]["oncall"])
    approved = runbook + "\n" + f"Approved remediation evidence for {task['oracle']['cve']} on {project['asset_id']}-1.\n"
    stale = runbook + "\n" + f"Stale workaround for retired {project['asset_id']}-legacy; do not release.\n"
    for text in (ci, contact, approved, stale):
        raw = text.encode()
        pool[sha256(raw)] = raw
    return pool


def _read_ref(ref, reader):
    _require(callable(reader) and type(ref) is dict and set(ref) == {"path", "sha256"} and
             type(ref["sha256"]) is str and _HEX64.fullmatch(ref["sha256"]) is not None,
             "saved_git_raw_ref_invalid")
    _path(ref["path"])
    try:
        raw = reader(ref)
    except (OSError, ValueError, TypeError, KeyError):
        raise SavedGitEvidenceError("saved_git_raw_ref_unavailable") from None
    _require(type(raw) is bytes and len(raw) <= 8_000_000 and sha256(raw) == ref["sha256"],
             "saved_git_raw_ref_digest_changed")
    return raw


def _tree(raw):
    """Parse retained `git ls-tree -r -z --full-tree <commit>` bytes."""
    _require(not raw or raw.endswith(b"\0"), "saved_git_tree_format_invalid")
    result = {}
    for record in raw.split(b"\0")[:-1]:
        try:
            header, name = record.split(b"\t", 1)
            mode, kind, object_id = header.decode("ascii").split(" ")
            path = _path(name.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise SavedGitEvidenceError("saved_git_tree_format_invalid") from None
        _require(path not in result and _HEX40.fullmatch(object_id) is not None and
                 ((kind == "blob" and mode in ("100644", "100755", "120000")) or
                  (kind == "commit" and mode == "160000")), "saved_git_tree_entry_invalid")
        result[path] = (mode, kind, object_id)
    return result


class SavedGitReader:
    def __init__(self, *, task, project, progress, before, after, captured_git=None, read_ref=None):
        _snapshot(before)
        _snapshot(after)
        _require(type(progress.get("project_id")) is int and progress["project_id"] > 0 and
                 task["project_family"] == project["full_path"], "saved_git_project_context_invalid")
        self.project_id = progress["project_id"]
        self.before = before
        self.after = after
        key = str(self.project_id)
        _require(key in before["git"] and key in after["git"], "saved_git_project_missing")
        b, a = before["git"][key], after["git"][key]
        self.before_sha = b["refs"]["refs/heads/main"]
        self.after_sha = a["refs"]["refs/heads/main"]
        _require(type(self.before_sha) is str and type(self.after_sha) is str and
                 _HEX40.fullmatch(self.before_sha) is not None and _HEX40.fullmatch(self.after_sha) is not None,
                 "saved_git_main_commit_invalid")
        bm, am = b["main_blobs_sha256"], a["main_blobs_sha256"]
        _require(set(bm) == MONITORED_PATHS and set(am) == MONITORED_PATHS and
                 all(type(d) is str and _HEX64.fullmatch(d) is not None for d in (*bm.values(), *am.values())),
                 "saved_git_monitored_paths_or_hash_invalid")
        pool = frozen_blob_candidates(task, project)
        self.before_blobs = {}
        for path, digest in bm.items():
            _require(digest == sha256(project["files"][path].encode()) and digest in pool,
                     "saved_git_baseline_blob_unknown")
            self.before_blobs[path] = pool[digest]
        self.full_tree_verified = captured_git is not None
        self.raw_refs = []
        if captured_git is None:
            self.after_blobs = {}
            for path, digest in am.items():
                _require(digest in pool, "saved_git_historical_blob_unknown")
                self.after_blobs[path] = pool[digest]
            self.changed_paths = {path for path in MONITORED_PATHS if bm[path] != am[path]}
        else:
            fields = {"schema", "project_id", "before_main_sha", "after_main_sha",
                      "before_business_sha256", "after_business_sha256", "diff_ref",
                      "before_tree_ref", "after_tree_ref", "main_blob_refs"}
            _require(type(captured_git) is dict and set(captured_git) == fields and
                     captured_git["schema"] == SIDECAR_SCHEMA and
                     type(captured_git["project_id"]) is int and captured_git["project_id"] == self.project_id and
                     captured_git["before_main_sha"] == self.before_sha and captured_git["after_main_sha"] == self.after_sha and
                     captured_git["before_business_sha256"] == before["business_sha256"] and
                     captured_git["after_business_sha256"] == after["business_sha256"],
                     "saved_git_capture_snapshot_binding_changed")
            refs = captured_git["main_blob_refs"]
            _require(type(refs) is dict and set(refs) == MONITORED_PATHS, "saved_git_capture_blob_paths_invalid")
            self.after_blobs = {path: _read_ref(ref, read_ref) for path, ref in refs.items()}
            _require(all(sha256(raw) == am[path] for path, raw in self.after_blobs.items()),
                     "saved_git_capture_blob_snapshot_mismatch")
            btree = _tree(_read_ref(captured_git["before_tree_ref"], read_ref))
            atree = _tree(_read_ref(captured_git["after_tree_ref"], read_ref))
            for tree, blobs in ((btree, self.before_blobs), (atree, self.after_blobs)):
                for path, raw in blobs.items():
                    blob_id = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
                    _require(path in tree and tree[path][1:] == ("blob", blob_id),
                             "saved_git_tree_blob_identity_changed")
            changed = {path for path in set(btree) | set(atree) if btree.get(path) != atree.get(path)}
            diff = _read_ref(captured_git["diff_ref"], read_ref)
            try:
                lines = diff.decode("utf-8").splitlines()
                paths = [_path(path) for path in lines]
            except (UnicodeDecodeError, ValueError):
                raise SavedGitEvidenceError("saved_git_diff_format_invalid") from None
            _require(len(set(paths)) == len(paths) and set(paths) == changed,
                     "saved_git_tree_diff_disagrees")
            self.changed_paths = changed
            self.raw_refs = [captured_git[name] for name in ("diff_ref", "before_tree_ref", "after_tree_ref")] + list(refs.values())

    def git(self, project_id, *args):
        _require(project_id == self.project_id, "saved_git_query_project_changed")
        if args == ("diff", "--name-only", self.before_sha, self.after_sha):
            return ("\n".join(sorted(self.changed_paths)) + ("\n" if self.changed_paths else "")).encode()
        if len(args) == 2 and args[0] == "show" and args[1].startswith("refs/heads/main:"):
            path = args[1].split(":", 1)[1]
            _require(path in self.after_blobs, "saved_git_query_path_unknown")
            return self.after_blobs[path]
        raise SavedGitEvidenceError("saved_git_query_not_captured")


def _copy_function(function, scope):
    clone = FunctionType(function.__code__, scope, function.__name__, function.__defaults__, function.__closure__)
    clone.__kwdefaults__ = function.__kwdefaults__
    return clone


def audit_saved_task(task, before, after, *, project, progress, captured_git=None,
                     read_ref=None, captured_verdict=None, expected_verifier_sha256=None):
    """Re-run the exact verifier code; do not globally monkeypatch its module."""
    actual_source = verifier_sha256()
    _require(expected_verifier_sha256 is None or expected_verifier_sha256 == actual_source,
             "saved_git_verifier_source_changed")
    task, project, progress = copy.deepcopy((task, project, progress))
    reader = SavedGitReader(task=task, project=project, progress=progress, before=before, after=after,
                            captured_git=captured_git, read_ref=read_ref)
    scope = dict(_ORIGINAL_EVALUATOR.__globals__)
    scope["_git"] = reader.git
    scope["git_blob"] = _copy_function(_ORIGINAL_GIT_BLOB, scope)
    scope["_changed_paths"] = _copy_function(_ORIGINAL_CHANGED_PATHS, scope)
    scope["_context"] = lambda candidate: (project, progress) if candidate == task else (_ for _ in ()).throw(
        SavedGitEvidenceError("saved_git_task_context_changed"))
    evaluator = _copy_function(_ORIGINAL_EVALUATOR, scope)
    verdict = evaluator(task, before, after, inspect_live_git=True)
    matched = None if captured_verdict is None else verdict == captured_verdict
    _require(matched is not False, "saved_git_captured_live_verdict_disagrees")
    return {"schema": AUDIT_SCHEMA, "verdict": verdict, "verifier_sha256": actual_source,
            "verifier_inspect_live_git": True, "offline_git_callbacks": True,
            "captured_live_verdict_matches": matched,
            "git_evidence_mode": "captured_full_tree_diff_and_blobs" if reader.full_tree_verified else "historical_six_blob_source_reconstruction",
            "full_git_tree_verified": reader.full_tree_verified,
            "complete_git_predicates_decidable": reader.full_tree_verified or task["template_group"] not in {"approved_merge_request_merge", "ci_and_runbook_reconciliation"},
            "historical_changed_path_projection_is_conditional": not reader.full_tree_verified and task["template_group"] in {"approved_merge_request_merge", "ci_and_runbook_reconciliation"},
            "captured_live_verdict_is_authority": False,
            "historical_full_tree_evidence_available": reader.full_tree_verified,
            "monitored_paths": sorted(MONITORED_PATHS), "changed_paths": sorted(reader.changed_paths),
            "raw_git_refs": reader.raw_refs, "live_calls": 0}


def audit_formal_saved_task(task, before, after, *, captured_git, read_ref, **kwargs):
    """Formal model/final readback never uses historical six-path projection."""
    _require(captured_git is not None and callable(read_ref), "formal_saved_git_full_sidecar_required")
    result = audit_saved_task(task, before, after, captured_git=captured_git, read_ref=read_ref, **kwargs)
    _require(result["full_git_tree_verified"] is True, "formal_saved_git_full_tree_not_verified")
    return result


def evaluate_saved_task(task, before, after, **kwargs):
    return audit_saved_task(task, before, after, **kwargs)["verdict"]


__all__ = ["audit_saved_task", "audit_formal_saved_task", "evaluate_saved_task", "SavedGitReader", "SavedGitEvidenceError",
           "SIDECAR_SCHEMA", "AUDIT_SCHEMA", "MONITORED_PATHS", "frozen_blob_candidates", "verifier_sha256"]
