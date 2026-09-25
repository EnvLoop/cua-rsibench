"""Private-seeded GitLab security-operations development candidates.

The advisory facts are a pinned, CC0 excerpt of CISA's KEV catalog. All
organizations, asset assignments, users, project work, and required actions
are synthetic. An offline candidate is never an admitted final task.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
import hashlib
import hmac
import json
from pathlib import Path
import re


HERE = Path(__file__).resolve().parent
EXCERPT = HERE / "data/kev_excerpt.json"
EXCERPT_SHA256 = "28217d51a35a1faf8887b8af20578d516d37aad66b4a75682ae193412ed049e2"
RESERVE_EXCERPT = HERE / "data/kev_reserve_excerpt.json"
RESERVE_EXCERPT_SHA256 = "dfd9c995f9e1db3f086144c9272a100734ffde79508037b5c86720cfa3f43bc6"
SOURCE_COMMIT = "203fa4633af39c6944608e30984996f04ccc4541"
SOURCE_FULL_SHA256 = "39099ffcf82c3f183fa6f7326900a6d82731517b2edb5cecde06dee6e04289d1"
SCHEMA = "envloop-gitlab-original-world-v1"
AS_OF = date(2026, 9, 25)

SPLITS = (("train", 5, 4), ("selection", 5, 4), ("final_candidate_unsealed", 20, 5))
FAMILIES = {
    "train": ("issue_label_from_alert", "issue_due_from_register",
              "milestone_window_from_policy", "guest_member_from_roster"),
    "selection": ("issue_owner_transfer", "false_positive_closure",
                  "runbook_contact_annotation", "reporter_member_expiry"),
    "final_candidate_unsealed": ("cross_record_issue_triage",
                                  "release_milestone_coordination",
                                  "approved_merge_request_merge",
                                  "least_privilege_access_handoff",
                                  "ci_and_runbook_reconciliation"),
}
SITE_CODES = ("north-dc", "river-dc", "harbor-edge", "west-cloud", "east-cloud")


def sha256(value: bytes | str) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def source_excerpt() -> dict:
    raw = EXCERPT.read_bytes()
    if sha256(raw) != EXCERPT_SHA256:
        raise ValueError("CISA KEV excerpt bytes changed")
    document = json.loads(raw)
    if (document.get("schema") != "envloop-gitlab-kev-source-v1"
            or document.get("source_commit") != SOURCE_COMMIT
            or document.get("source_full_file_sha256") != SOURCE_FULL_SHA256):
        raise ValueError("CISA KEV source pin changed")
    rows = document.get("records")
    if not isinstance(rows, list) or len(rows) != 120:
        raise ValueError("expected 120 pinned advisory records")
    cves = [row["cveID"] for row in rows]
    vendors = [row["vendorProject"].strip().casefold() for row in rows]
    if len(set(cves)) != 120 or len(set(vendors)) != 120:
        raise ValueError("advisory CVE/vendor identity collision")
    if any(not re.fullmatch(r"CVE-\d{4}-\d{4,19}", cve) for cve in cves):
        raise ValueError("invalid CVE ID")
    return document


def rank(seed: str, purpose: str, value: str) -> str:
    if len(seed) < 20:
        raise ValueError("private world seed must have at least 20 characters")
    return hmac.new(seed.encode(), f"{purpose}:{value}".encode(), hashlib.sha256).hexdigest()


def _record_sort(seed: str, records: list[dict]) -> list[dict]:
    return sorted(records, key=lambda row: rank(seed, "source-record", row["cveID"]))


def _slug(seed: str, index: int) -> str:
    return "portfolio-" + rank(seed, "project-path", str(index))[:10]


def _name(seed: str, role: str, index: int) -> str:
    return role + "-" + rank(seed, role, str(index))[:12]


def _priority(primary: dict) -> str:
    return "priority::p1" if primary.get("knownRansomwareCampaignUse") == "Known" else "priority::p2"


def _files(project: dict) -> dict[str, str]:
    records = project["advisories"]
    policy = project["policy"]
    primary = records[0]
    inventory = ["asset_id,cve_id,vendor,product,site,disposition"]
    for offset, row in enumerate(records):
        disposition = "active" if offset == 0 else "watch"
        inventory.append(",".join((f"{project['asset_id']}-{offset + 1}", row["cveID"],
                                   row["vendorProject"].replace(",", " "),
                                   row["product"].replace(",", " "),
                                   project["site"], disposition)))
    return {
        "README.md": (
            f"# {project['display_name']}\n\n"
            "Synthetic internal asset portfolio for benchmark evaluation. "
            "CVE, vendor, product, and advisory facts in `security/kev-register.csv` "
            "come from the pinned CISA Known Exploited Vulnerabilities catalog. "
            "Asset ownership, roles, deadlines, and workflow records are synthetic.\n\n"
            "Use the live issues, merge requests, release policy, and response runbook "
            "to reconcile work. Similar historical and current records coexist.\n"
        ),
        "security/kev-register.csv": "\n".join(inventory) + "\n",
        "security/release-policy.md": (
            "# Current release policy\n\n"
            f"Active advisory: {primary['cveID']}\n\n"
            f"Asset: {project['asset_id']}-1 at {project['site']}\n\n"
            f"Priority: {_priority(primary)}\n\n"
            f"Internal issue due: {policy['issue_due']}\n\n"
            f"Release milestone: {policy['milestone_title']}\n\n"
            f"Release window: {policy['milestone_start']} through {policy['milestone_due']}\n\n"
            f"On-call owner: @{project['principals']['oncall']}\n\n"
            f"Incoming responder: @{project['principals']['incoming']} (Reporter through {policy['access_expiry']})\n\n"
            f"Departing contractor: @{project['principals']['contractor']} (remove access)\n\n"
            "Link the active remediation issue and its validation follow-up to the release milestone. "
            "Leave the archived duplicate and all watch-list issues unchanged.\n"
        ),
        "security/SECURITY.md": (
            "# Response evidence\n\n"
            f"Only the active {primary['cveID']} asset is in the release window. "
            "The archived duplicate is a separate, completed asset.\n\n"
            f"CISA advisory: {primary['vulnerabilityName']}\n\n"
            f"CISA action: {primary['requiredAction']}\n"
        ),
        "docs/response-runbook.md": (
            "# Response runbook\n\n"
            "Current contact: pending\n\n"
            "The merged remediation note, not the stale workaround, is the accepted release evidence.\n"
        ),
        ".gitlab-ci.yml": (
            "stages:\n  - test\n  - security\n\n"
            "unit_check:\n  stage: test\n  script:\n    - echo 'inventory check'\n\n"
            "kev_gate:\n  stage: security\n  script:\n"
            f"    - echo 'check {primary['cveID']}'\n"
            "  rules:\n    - when: never\n"
        ),
    }


def _issues(project: dict) -> list[dict]:
    advisories = project["advisories"]
    primary = advisories[0]
    entries = [
        {
            "key": "active", "title": f"Active remediation: {primary['cveID']} / {primary['product']}",
            "description": (f"Asset {project['asset_id']}-1; {project['site']}. "
                            f"CISA: {primary['shortDescription']} "
                            "Release policy applies; collect validation evidence before closure."),
            "labels": ["kev", "state::active"], "state": "opened", "confidential": False,
        },
        {
            "key": "validation", "title": f"Validate mitigation: {primary['cveID']} / {project['site']}",
            "description": (f"Validate current asset {project['asset_id']}-1 after the approved remediation "
                            "merge request is merged. This remains a separate open work item."),
            "labels": ["kev", "state::validation"], "state": "opened", "confidential": False,
        },
        {
            "key": "historical_duplicate", "title": f"Historical verification: {primary['cveID']} / retired asset",
            "description": (f"Asset {project['asset_id']}-legacy is retired. "
                            "This look-alike ticket was already mitigated; it can be closed "
                            "during a historical-cleanup task, but must never replace current work."),
            "labels": ["kev", "state::historical"], "state": "opened", "confidential": False,
        },
    ]
    for offset, row in enumerate(advisories[1:], start=2):
        entries.append({
            "key": f"watch_{offset}",
            "title": f"Watch-list review: {row['cveID']} / {row['product']}",
            "description": (f"Asset {project['asset_id']}-{offset}; {project['site']}. "
                            f"CISA: {row['shortDescription']} The current release policy does not target this asset."),
            "labels": ["kev", "state::watch"], "state": "opened", "confidential": offset == 3,
        })
    return entries


def _tasks(project: dict) -> list[dict]:
    split = project["partition"]
    cve = project["advisories"][0]["cveID"]
    repo = project["full_path"]
    prompts = {
        "issue_label_from_alert": f"In {repo}, read the CISA-backed asset register and add the policy priority label to the active {cve} remediation issue. Preserve the historical duplicate and watch-list tickets.",
        "issue_due_from_register": f"In {repo}, use the release policy to set the active {cve} remediation issue's internal due date. Do not change other issue fields or records.",
        "milestone_window_from_policy": f"In {repo}, create the release-policy milestone for {cve} with its exact start and due dates. Leave existing milestones and issues unchanged.",
        "guest_member_from_roster": f"In {repo}, add the incoming responder named by the policy as a Guest. Do not grant broader access or change existing members.",
        "issue_owner_transfer": f"In {repo}, assign the active {cve} remediation issue to the on-call owner in the release policy; leave the similar retired-asset issue alone.",
        "false_positive_closure": f"In {repo}, close only the retired-asset historical verification issue for {cve} if it is open. Keep current and watch-list work open.",
        "runbook_contact_annotation": f"In {repo}, replace `Current contact: pending` in the response runbook with the on-call owner from the policy. Keep every other line intact.",
        "reporter_member_expiry": f"In {repo}, add the incoming responder in the release policy as Reporter with its stated expiration. Do not modify other members.",
        "cross_record_issue_triage": f"In {repo}, reconcile the active {cve} remediation issue using the KEV register and release policy: set the policy priority, on-call owner, and internal due date. Keep the similarly named retired-asset and watch-list issues unchanged.",
        "release_milestone_coordination": f"In {repo}, create the release-policy milestone for the active {cve} asset with exact dates, then add both its active remediation and validation follow-up issues to that milestone. Preserve all other milestones and issues.",
        "approved_merge_request_merge": f"In {repo}, inspect the two open {cve} merge requests and merge only the approved remediation note into the default branch. Keep the stale workaround MR open and do not merge or edit unrelated branches.",
        "least_privilege_access_handoff": f"In {repo}, follow the release policy's access handoff: remove the departing contractor, add the incoming responder as Reporter through the stated expiry, and preserve all other permissions.",
        "ci_and_runbook_reconciliation": f"In {repo}, enable the existing `kev_gate` job for merge-request pipelines and replace the pending contact in `docs/response-runbook.md` with the policy's on-call owner. Keep all other CI jobs and runbook lines intact.",
    }
    tasks = []
    for task_index, family in enumerate(FAMILIES[split], start=1):
        task_id = f"GLW-{project['index']:02d}-{task_index:02d}"
        oracle = {"family": family, "project": repo, "cve": cve,
                  "issue_key": "active", "policy": project["policy"],
                  "principals": project["principals"],
                  "expected_priority": _priority(project["advisories"][0]),
                  "expected_default_branch": "main"}
        tasks.append({"task_id": task_id, "partition": split,
                      "source_family": project["source_family"],
                      "template_group": family, "project_family": repo,
                      "entity_group": project["asset_id"],
                      "prompt": prompts[family], "oracle": oracle,
                      "status": "offline_candidate_unverified"})
    return tasks


def _make_project(seed: str, index: int, partition: str, four: list[dict]) -> dict:
    if len(four) != 4 or partition not in SPLIT_PARTITIONS:
        raise ValueError("project requires four advisories and a recognized partition")
    primary = four[0]
    site = SITE_CODES[(index - 1) % len(SITE_CODES)]
    slug = _slug(seed, index)
    split_slug = {"train": "training", "selection": "selection",
                  "final_candidate_unsealed": "evaluation"}[partition]
    group = "bench-" + split_slug + "-" + rank(seed, "namespace", partition)[:8]
    principals = {role: _name(seed, f"{split_slug}-{role}", index)
                  for role in ("oncall", "incoming", "contractor", "observer")}
    start = AS_OF + timedelta(days=5 + (index % 8))
    due = start + timedelta(days=8 + (index % 5))
    policy = {
        "issue_due": (start - timedelta(days=1)).isoformat(),
        "milestone_title": "Response " + primary["cveID"] + " / " + site,
        "milestone_start": start.isoformat(),
        "milestone_due": due.isoformat(),
        "access_expiry": (due + timedelta(days=7)).isoformat(),
    }
    project = {
        "index": index, "partition": partition,
        "display_name": "Security asset portfolio " + str(index).zfill(2),
        "group_path": group, "project_path": slug,
        "full_path": group + "/" + slug,
        "source_family": "cisa-kev:" + sha256(canonical([r["cveID"] for r in four]))[:16],
        "site": site,
        "asset_id": "INV-" + rank(seed, "asset", str(index))[:8].upper(),
        "principals": principals, "policy": policy,
        "advisories": four,
    }
    project["files"] = _files(project)
    project["issues"] = _issues(project)
    return project


SPLIT_PARTITIONS = {partition for partition, _, _ in SPLITS}


def build_world(seed: str, *, records: list[dict] | None = None) -> dict:
    """Build evaluator-only world data. Caller stores it in ignored 0600 storage."""
    if not isinstance(seed, str) or len(seed) < 20:
        raise ValueError("private world seed must be at least 20 characters")
    source = source_excerpt()
    advisories = _record_sort(seed, records or source["records"])
    if len(advisories) != 120:
        raise ValueError("expected 120 advisory rows")
    projects, tasks = [], []
    index = 0
    for partition, project_count, _ in SPLITS:
        for _ in range(project_count):
            four = advisories[index * 4:index * 4 + 4]
            index += 1
            project = _make_project(seed, index, partition, four)
            projects.append(project)
            tasks.extend(_tasks(project))
    if index != 30 or len(tasks) != 140:
        raise AssertionError("world size changed")
    audit = split_audit(projects, tasks)
    if not audit["all_cross_partition_disjoint"]:
        raise AssertionError("cross-split project/source/entity/principal/template overlap")
    return {"schema": SCHEMA,
            "source": {"repository": source["source_repository"],
                       "commit": SOURCE_COMMIT, "full_file_sha256": SOURCE_FULL_SHA256,
                       "excerpt_sha256": EXCERPT_SHA256, "license": source["license"]},
            "synthetic_layer": True,
            "world_seed_sha256": sha256(seed),
            "projects": projects, "tasks": tasks, "split_audit": audit,
            "candidate_status": "not_individually_gui_admitted"}


def reserve_replacement(seed: str) -> dict:
    """Five unexposed replacement candidates on four unused CISA records."""
    raw = RESERVE_EXCERPT.read_bytes()
    if sha256(raw) != RESERVE_EXCERPT_SHA256:
        raise ValueError("reserve CISA excerpt bytes changed")
    reserve = json.loads(raw)
    if (reserve.get("schema") != "envloop-gitlab-kev-reserve-source-v1"
            or reserve.get("source_commit") != SOURCE_COMMIT
            or reserve.get("source_full_file_sha256") != SOURCE_FULL_SHA256):
        raise ValueError("reserve source pin changed")
    four = reserve.get("records")
    if not isinstance(four, list) or len(four) != 4:
        raise ValueError("reserve requires four advisory records")
    primary = source_excerpt()["records"]
    if ({row["cveID"] for row in primary} & {row["cveID"] for row in four}
            or {row["vendorProject"].casefold() for row in primary} &
            {row["vendorProject"].casefold() for row in four}):
        raise ValueError("reserve source overlaps primary source")
    project = _make_project(seed, 31, "final_candidate_unsealed",
                            _record_sort(seed, four))
    tasks = _tasks(project)
    if len(tasks) != 5:
        raise AssertionError("reserve project must yield five task candidates")
    return {"source_excerpt_sha256": RESERVE_EXCERPT_SHA256,
            "project": project, "tasks": tasks,
            "status": "unsealed_replacement_source_not_gui_admitted"}


def split_audit(projects: list[dict], tasks: list[dict]) -> dict:
    by_split: dict[str, dict[str, set[str]]] = {}
    for partition, _, _ in SPLITS:
        ps = [project for project in projects if project["partition"] == partition]
        ts = [task for task in tasks if task["partition"] == partition]
        by_split[partition] = {
            "projects": {project["full_path"] for project in ps},
            "sources": {r["cveID"] for project in ps for r in project["advisories"]},
            "vendors": {r["vendorProject"].casefold() for project in ps for r in project["advisories"]},
            "entities": {project["asset_id"] for project in ps},
            "principals": {name for project in ps for name in project["principals"].values()},
            "templates": {task["template_group"] for task in ts},
        }
    keys = ("projects", "sources", "vendors", "entities", "principals", "templates")
    pairs = [("train", "selection"), ("train", "final_candidate_unsealed"),
             ("selection", "final_candidate_unsealed")]
    overlap = {left + "_vs_" + right: {key: len(by_split[left][key] & by_split[right][key])
                                        for key in keys} for left, right in pairs}
    counts = dict(Counter(task["partition"] for task in tasks))
    return {"project_count": len(projects), "task_counts": counts,
            "source_record_count": sum(len(project["advisories"]) for project in projects),
            "overlap_counts": overlap,
            "all_cross_partition_disjoint": all(value == 0 for pair in overlap.values()
                                                 for value in pair.values()),
            "official_final_admitted": 0}


def public_receipt(world: dict) -> dict:
    """Explicitly exclude instructions, source-to-project mapping, gold and seed."""
    audit = world["split_audit"]
    return {"schema": "envloop-gitlab-world-public-receipt-v1",
            "source": world["source"], "synthetic_layer": True,
            "candidate_counts": audit["task_counts"],
            "project_count": audit["project_count"],
            "source_record_count": audit["source_record_count"],
            "cross_partition_overlap_counts": audit["overlap_counts"],
            "official_final_admitted": 0,
            "status": "offline_candidates_not_gui_admitted_or_sealed"}


def write_private(path: Path, payload: object) -> None:
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")
    path.chmod(0o600)
