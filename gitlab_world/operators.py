"""Scoped non-admin browser actors for the three GitLab partitions.

The root account is fixture/evaluator authority only. These dedicated local
users receive ownership in exactly one private group; passwords remain in
ignored mode-0600 evaluator storage, never in source or public receipts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import secrets

from . import bootstrap, factory, runtime


PRIVATE = runtime.PRIVATE
CREDENTIALS = PRIVATE / "operator-credentials-private.json"
RECEIPT = PRIVATE / "operator-bootstrap-private.json"
PARTITIONS = ("train", "selection", "final_candidate_unsealed")


def plan(world: dict) -> dict:
    groups = {}
    for partition in PARTITIONS:
        matching = {project["group_path"] for project in bootstrap.all_projects(world)
                    if project["partition"] == partition}
        if len(matching) != 1:
            raise ValueError("partition must have exactly one private GitLab group")
        groups[partition] = matching.pop()
    if len(set(groups.values())) != 3:
        raise ValueError("operator groups overlap")
    return {"schema": "envloop-gitlab-scoped-operator-plan-v1", "groups": groups,
            "expected_role_level": 50, "expected_is_admin": False}


def _credentials() -> dict:
    if CREDENTIALS.exists():
        if CREDENTIALS.stat().st_mode & 0o077:
            raise RuntimeError("operator credential file is not restrictive")
        result = json.loads(CREDENTIALS.read_text())
        if set(result) != set(PARTITIONS):
            raise RuntimeError("operator credential roster partial")
        return result
    roster = {}
    for partition in PARTITIONS:
        tag = hashlib.sha256((bootstrap.SEED_FILE.read_text().strip() +
                              ":operator:" + partition).encode()).hexdigest()[:12]
        label = {"train": "train", "selection": "selection",
                 "final_candidate_unsealed": "evaluation"}[partition]
        roster[partition] = {"username": "bench-" + label + "-operator-" + tag,
                             "password": secrets.token_urlsafe(40)}
    factory.write_private(CREDENTIALS, roster)
    return roster


def seed() -> dict:
    if not runtime.proof(runtime.WORLD)["running"]:
        raise RuntimeError("disposable GitLab world is not running")
    world = bootstrap.world()
    binding = plan(world)
    credentials = _credentials()
    api = bootstrap.GitLabAPI(bootstrap.api_token())
    progress = json.loads(bootstrap.PROGRESS_FILE.read_text())
    identities = {}
    for partition in PARTITIONS:
        username = credentials[partition]["username"]
        existing = api.call("GET", "/api/v4/users?username=" + username)
        if not isinstance(existing, list) or len(existing) > 1:
            raise RuntimeError("operator user lookup ambiguous")
        item = existing[0] if existing else api.call("POST", "/api/v4/users", {
            "username": username, "name": "Benchmark " + partition.split("_")[0].title() + " Operator",
            "email": username + "@benchmark.invalid",
            "password": credentials[partition]["password"],
            "skip_confirmation": True, "admin": False,
            "can_create_group": False, "projects_limit": 0})
        if not isinstance(item, dict) or item.get("username") != username or item.get("is_admin", False):
            raise RuntimeError("operator user identity/admin status invalid")
        group_path = binding["groups"][partition]
        group_id = int(progress["groups"][group_path])
        user_id = int(item["id"])
        member = api.get_optional(f"/api/v4/groups/{group_id}/members/{user_id}")
        if member is None:
            member = api.call("POST", f"/api/v4/groups/{group_id}/members", {
                "user_id": user_id, "access_level": 50})
        if not isinstance(member, dict) or member.get("access_level") != 50:
            raise RuntimeError("operator group owner membership not persisted")
        identities[partition] = {"user_id": user_id, "group_id": group_id,
                                 "username_sha256": factory.sha256(username)}
    private = {"schema": "envloop-gitlab-scoped-operator-bootstrap-v1",
               "identities": identities,
               "operator_credentials_file_mode": "0600",
               "root_admin_is_actor": False}
    if RECEIPT.exists():
        old = json.loads(RECEIPT.read_text())
        if old != private:
            raise RuntimeError("operator bootstrap drift")
    else:
        factory.write_private(RECEIPT, private)
    return {"schema": private["schema"], "operator_count": 3,
            "group_owner_count": 3, "non_admin": True,
            "cross_partition_reachability_gui_verified": False,
            "official_final_admitted": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(seed(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
