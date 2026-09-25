"""Seed the original development world through a disposable GitLab instance.

This is fixture setup, not an agent action channel. Never expose the token,
password, private task manifest, or source-to-project mapping in public logs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import secrets
import subprocess
import time
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from . import factory, runtime


PRIVATE = runtime.PRIVATE
WORLD_FILE = PRIVATE / "world-private.json"
SEED_FILE = PRIVATE / "world-seed.txt"
TOKEN_FILE = PRIVATE / "bootstrap-token.txt"
PROGRESS_FILE = PRIVATE / "bootstrap-progress.json"


def world() -> dict:
    if WORLD_FILE.exists():
        result = json.loads(WORLD_FILE.read_text())
        if result.get("schema") != factory.SCHEMA:
            raise RuntimeError("private world schema mismatch")
        return result
    if not SEED_FILE.exists():
        runtime.private_write(SEED_FILE, secrets.token_urlsafe(40) + "\n")
    result = factory.build_world(SEED_FILE.read_text().strip())
    factory.write_private(WORLD_FILE, result)
    return result


def api_token() -> str:
    if TOKEN_FILE.exists():
        if TOKEN_FILE.stat().st_mode & 0o077:
            raise RuntimeError("token file permissions are not restrictive")
        return TOKEN_FILE.read_text().strip()
    ruby = (
        "u=User.find_by_username('root') or raise 'root missing';"
        "t=u.personal_access_tokens.create!(name:'envloop-world-bootstrap',"
        "scopes:['api'],expires_at:Date.today+2);"
        "puts t.token"
    )
    output = runtime.docker("exec", runtime.WORLD, "gitlab-rails", "runner", ruby,
                            timeout=180).splitlines()
    token = output[-1].strip() if output else ""
    if not re.fullmatch(r"glpat-[A-Za-z0-9_.-]{12,}", token):
        raise RuntimeError("GitLab bootstrap token not returned in expected format")
    runtime.private_write(TOKEN_FILE, token + "\n")
    return token


class GitLabAPI:
    def __init__(self, token: str):
        self.token = token

    def call(self, method: str, path: str, data: dict | None = None,
             *, expected: tuple[int, ...] = (200, 201)) -> object:
        if not path.startswith("/") or ".." in path or not path.startswith("/api/v4/"):
            raise ValueError("API path must stay inside local GitLab API")
        body = json.dumps(data).encode() if data is not None else None
        request = Request(runtime.BASE + path, data=body, method=method,
                          headers={"PRIVATE-TOKEN": self.token,
                                   "Content-Type": "application/json"})
        for attempt in range(4):
            try:
                with urlopen(request, timeout=90) as response:
                    if response.status not in expected:
                        raise RuntimeError(f"GitLab {method} {path} unexpected HTTP {response.status}")
                    raw = response.read()
                    return json.loads(raw) if raw else None
            except HTTPError as exc:
                if exc.code in (429, 502, 503, 504) and attempt < 3:
                    time.sleep(3 * (attempt + 1))
                    continue
                raise RuntimeError(f"GitLab {method} {path} HTTP {exc.code}") from None
        raise AssertionError("unreachable API retry loop")

    def get_optional(self, path: str) -> dict | None:
        try:
            item = self.call("GET", path)
            if not isinstance(item, dict):
                raise RuntimeError("expected GitLab object")
            return item
        except RuntimeError as exc:
            if str(exc).endswith("HTTP 404"):
                return None
            raise


def key(value: str) -> str:
    return quote(value, safe="")


def _progress() -> dict:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {"schema": "envloop-gitlab-bootstrap-progress-v1", "projects": {},
            "groups": {}, "users": {}}


def _save_progress(progress: dict) -> None:
    temporary = PROGRESS_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(progress, indent=2, sort_keys=True) + "\n")
    temporary.chmod(0o600)
    temporary.replace(PROGRESS_FILE)


def _group(api: GitLabAPI, path: str, progress: dict) -> int:
    if path in progress["groups"]:
        return int(progress["groups"][path])
    existing = api.get_optional("/api/v4/groups/" + key(path))
    item = existing or api.call("POST", "/api/v4/groups", {
        "name": "Benchmark " + path.split("-")[1].title() + " Operations",
        "path": path, "visibility": "private"})
    if not isinstance(item, dict) or item.get("full_path") != path:
        raise RuntimeError("GitLab group path differs from private manifest")
    progress["groups"][path] = item["id"]
    _save_progress(progress)
    return int(item["id"])


def _user(api: GitLabAPI, username: str, progress: dict) -> int:
    if username in progress["users"]:
        return int(progress["users"][username])
    existing = api.call("GET", "/api/v4/users?" + urlencode({"username": username}))
    if not isinstance(existing, list) or len(existing) > 1:
        raise RuntimeError("GitLab user lookup ambiguous")
    item = existing[0] if existing else api.call("POST", "/api/v4/users", {
        "username": username, "name": username.replace("-", " ").title(),
        "email": username + "@benchmark.invalid",
        "password": secrets.token_urlsafe(36),
        "skip_confirmation": True, "admin": False,
        "can_create_group": False, "projects_limit": 0})
    if not isinstance(item, dict) or item.get("username") != username:
        raise RuntimeError("GitLab user identity differs from private manifest")
    progress["users"][username] = item["id"]
    _save_progress(progress)
    return int(item["id"])


def _project(api: GitLabAPI, project: dict, group_id: int) -> dict:
    full = project["full_path"]
    existing = api.get_optional("/api/v4/projects/" + key(full))
    item = existing or api.call("POST", "/api/v4/projects", {
        "name": project["display_name"], "path": project["project_path"],
        "namespace_id": group_id, "visibility": "private",
        "description": "Synthetic security-operations workflow anchored to a pinned CISA KEV excerpt.",
        "initialize_with_readme": True, "default_branch": "main",
        "jobs_enabled": False, "shared_runners_enabled": False,
        "only_allow_merge_if_pipeline_succeeds": False})
    if not isinstance(item, dict) or item.get("path_with_namespace") != full:
        raise RuntimeError("GitLab project path differs from private manifest")
    for _ in range(30):
        item = api.call("GET", "/api/v4/projects/" + str(item["id"]))
        if isinstance(item, dict) and item.get("default_branch"):
            break
        time.sleep(2)
    if item.get("default_branch") != "main":
        raise RuntimeError("GitLab default branch is not main")
    return item


def _files(api: GitLabAPI, project_id: int, project: dict) -> None:
    files = project["files"]
    path = f"/api/v4/projects/{project_id}/repository/files/" + key("security/kev-register.csv")
    if api.get_optional(path + "?ref=main") is not None:
        return
    actions = [{"action": "update" if filename == "README.md" else "create",
                "file_path": filename, "content": content}
               for filename, content in files.items()]
    api.call("POST", f"/api/v4/projects/{project_id}/repository/commits", {
        "branch": "main", "commit_message": "Seed security operations register and policies",
        "actions": actions})


def _issues(api: GitLabAPI, project_id: int, project: dict) -> dict[str, int]:
    existing = api.call("GET", f"/api/v4/projects/{project_id}/issues?per_page=100&scope=all")
    if not isinstance(existing, list):
        raise RuntimeError("GitLab issue response is not a list")
    by_title = {row["title"]: row for row in existing}
    iids = {}
    for item in project["issues"]:
        issue = by_title.get(item["title"])
        if issue is None:
            issue = api.call("POST", f"/api/v4/projects/{project_id}/issues", {
                "title": item["title"], "description": item["description"],
                "labels": ",".join(item["labels"]),
                "confidential": item["confidential"]})
        if not isinstance(issue, dict) or issue.get("title") != item["title"]:
            raise RuntimeError("GitLab issue identity mismatch")
        iids[item["key"]] = int(issue["iid"])
    return iids


def _labels(api: GitLabAPI, project_id: int) -> None:
    current = api.call("GET", f"/api/v4/projects/{project_id}/labels?per_page=100")
    if not isinstance(current, list):
        raise RuntimeError("GitLab label response is not a list")
    names = {item["name"] for item in current}
    for name, color in (("priority::p1", "#b31b1b"), ("priority::p2", "#d08700")):
        if name not in names:
            api.call("POST", f"/api/v4/projects/{project_id}/labels", {
                "name": name, "color": color,
                "description": "Internal remediation priority from local release policy"})


def _members(api: GitLabAPI, project_id: int, project: dict,
             user_ids: dict[str, int]) -> None:
    levels = {"oncall": 30, "contractor": 20, "observer": 10}
    for role, level in levels.items():
        user_id = user_ids[role]
        path = f"/api/v4/projects/{project_id}/members/{user_id}"
        current = api.get_optional(path)
        if current is None:
            current = api.call("POST", f"/api/v4/projects/{project_id}/members", {
                "user_id": user_id, "access_level": level})
        if not isinstance(current, dict) or current.get("access_level") != level:
            raise RuntimeError("GitLab direct membership role mismatch")


def _merge_requests(api: GitLabAPI, project_id: int, project: dict) -> dict[str, int]:
    cve = project["advisories"][0]["cveID"]
    names = {"approved": "response-" + cve.lower() + "-review",
             "stale": "response-" + cve.lower() + "-legacy"}
    current = api.call("GET", f"/api/v4/projects/{project_id}/merge_requests?state=opened&per_page=100")
    if not isinstance(current, list):
        raise RuntimeError("GitLab MR response is not a list")
    by_branch = {item["source_branch"]: item for item in current}
    out = {}
    for role, branch in names.items():
        item = by_branch.get(branch)
        if item is None:
            api.call("POST", f"/api/v4/projects/{project_id}/repository/branches", {
                "branch": branch, "ref": "main"})
            original = project["files"]["docs/response-runbook.md"]
            evidence = (f"Approved remediation evidence for {cve} on {project['asset_id']}-1."
                        if role == "approved" else
                        f"Stale workaround for retired {project['asset_id']}-legacy; do not release.")
            content = original + "\n" + evidence + "\n"
            api.call("POST", f"/api/v4/projects/{project_id}/repository/commits", {
                "branch": branch, "commit_message": "Propose response evidence",
                "actions": [{"action": "update", "file_path": "docs/response-runbook.md",
                             "content": content}]})
            item = api.call("POST", f"/api/v4/projects/{project_id}/merge_requests", {
                "source_branch": branch, "target_branch": "main",
                "title": f"Response evidence proposal {role[0].upper()} for {cve}",
                "description": (f"Asset {project['asset_id']}-1; approved release evidence from current "
                                "register and validation follow-up."
                                if role == "approved" else
                                f"Retired asset {project['asset_id']}-legacy. Historical workaround "
                                "is not current release evidence."),
                "remove_source_branch": False, "squash": False})
        if not isinstance(item, dict) or item.get("source_branch") != branch:
            raise RuntimeError("GitLab MR branch mismatch")
        out[role] = int(item["iid"])
    return out


def seed(max_projects: int = 30) -> dict:
    if not 1 <= max_projects <= 30:
        raise ValueError("max_projects must be 1..30")
    state = runtime.proof(runtime.WORLD)
    if not state["running"] or state["health"] != "healthy":
        raise RuntimeError("disposable GitLab world is not healthy")
    manifest = world()
    api = GitLabAPI(api_token())
    progress = _progress()
    for project in manifest["projects"][:max_projects]:
        full = project["full_path"]
        if full in progress["projects"] and progress["projects"][full].get("complete"):
            _labels(api, int(progress["projects"][full]["project_id"]))
            continue
        group_id = _group(api, project["group_path"], progress)
        user_ids = {role: _user(api, name, progress)
                    for role, name in project["principals"].items()}
        item = _project(api, project, group_id)
        project_id = int(item["id"])
        _files(api, project_id, project)
        _labels(api, project_id)
        issue_iids = _issues(api, project_id, project)
        _members(api, project_id, project, user_ids)
        mr_iids = _merge_requests(api, project_id, project)
        progress["projects"][full] = {
            "complete": True, "project_id": project_id,
            "issue_iids": issue_iids, "mr_iids": mr_iids,
            "user_ids": user_ids, "default_branch": "main"}
        _save_progress(progress)
    counts = {"groups": len(progress["groups"]), "users": len(progress["users"]),
              "projects_complete": sum(bool(row.get("complete")) for row in progress["projects"].values()),
              "issues_expected": 6 * len(progress["projects"]),
              "merge_requests_expected": 2 * len(progress["projects"]),
              "candidate_final_admitted": 0}
    return {"schema": "envloop-gitlab-bootstrap-summary-v1", "counts": counts,
            "source_excerpt_sha256": factory.EXCERPT_SHA256,
            "fixture_synthetic_layer": True,
            "status": "development_world_seeded_not_gui_admitted"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-projects", type=int, default=30)
    args = parser.parse_args()
    print(json.dumps(seed(args.max_projects), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
