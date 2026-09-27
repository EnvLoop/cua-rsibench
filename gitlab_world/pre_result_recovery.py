"""Prospective, evaluator-private recovery roster for the GitLab cell.

The ordered source queue is fixed independently of qualification outcomes.
This module only plans and audits; it never bootstraps or mutates GitLab.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from . import bootstrap, factory, runtime


SCHEMA = "envloop-gitlab-pre-result-recovery-queue-v1"
RESOLUTION_SCHEMA = "envloop-gitlab-pre-result-recovery-resolution-v1"
MAX_REPLACEMENT_FAMILIES = 5
FIRST_REPLACEMENT_INDEX = 32
FULL_CATALOG = runtime.PRIVATE / "cisa-kev-pinned.json"
PRIVATE_QUEUE = runtime.PRIVATE / "pre-result-recovery-queue-private.json"
PRIVATE_RESOLUTION = runtime.PRIVATE / "pre-result-recovery-resolution-private.json"
FAILURE_STATUSES = {"development_gui_trio_failed",
                    "driver_or_environment_failed",
                    "cold_reset_or_verifier_failed"}
INFRA_STATUSES = {"driver_or_environment_failed",
                  "cold_reset_or_verifier_failed"}
PASS_STATUS = "development_gui_trio_passed"


def load_catalog(path: Path = FULL_CATALOG) -> list[dict]:
    """Accept only the previously pinned CISA catalog bytes and row shape."""
    raw = Path(path).read_bytes()
    if factory.sha256(raw) != factory.SOURCE_FULL_SHA256:
        raise ValueError("pinned full CISA catalog digest differs")
    catalog = json.loads(raw)
    records = catalog.get("vulnerabilities")
    if (catalog.get("catalogVersion") != "2026.09.24"
            or not isinstance(records, list)
            or catalog.get("count") != len(records) or len(records) < 144):
        raise ValueError("pinned full CISA catalog version or rows differ")
    cves = [item.get("cveID") for item in records]
    if (len(set(cves)) != len(cves)
            or any(not isinstance(cve, str)
                   or not re.fullmatch(r"CVE-\d{4}-\d{4,19}", cve)
                   for cve in cves)):
        raise ValueError("CISA catalog CVE identities are invalid")
    return records


def _existing_projects(world: dict) -> list[dict]:
    if (world.get("schema") != factory.SCHEMA
            or len(world.get("projects", [])) != 30
            or len(world.get("reserve_projects", [])) != 1
            or len(world.get("tasks", [])) != 140
            or len(world.get("reserve_tasks", [])) != 5):
        raise ValueError("recovery queue requires the 31-project pre-result world")
    projects = bootstrap.all_projects(world)
    if len({p["index"] for p in projects}) != 31:
        raise ValueError("existing project indices collide")
    return projects


def _boundaries(projects: list[dict]) -> dict[str, set[str]]:
    return {
        "projects": {p["full_path"] for p in projects},
        "sources": {r["cveID"] for p in projects for r in p["advisories"]},
        "vendors": {r["vendorProject"].strip().casefold()
                    for p in projects for r in p["advisories"]},
        "entities": {p["asset_id"] for p in projects},
        "principals": {name for p in projects for name in p["principals"].values()},
        "families": {p["source_family"] for p in projects},
    }


def ordered_queue(seed: str, world: dict, records: list[dict]) -> dict:
    """Pick five whole projects, one unused advisory per vendor, before results.

    HMAC rank over vendor and then CVE provides a fixed order. No failure
    category, GUI score, or model result participates in the choice.
    """
    if not isinstance(seed, str) or len(seed) < 20:
        raise ValueError("private world seed is missing or too short")
    if factory.sha256(seed) != world.get("world_seed_sha256"):
        raise ValueError("private world seed does not match the frozen world")
    projects = _existing_projects(world)
    existing = _boundaries(projects)
    if any(len(values) != expected for key, values, expected in (
            ("projects", existing["projects"], 31),
            ("sources", existing["sources"], 124),
            ("vendors", existing["vendors"], 124),
            ("entities", existing["entities"], 31),
            ("principals", existing["principals"], 124),
            ("families", existing["families"], 31))):
        raise ValueError("existing source/project/principal boundaries collide")
    unused_by_vendor: dict[str, list[dict]] = {}
    for row in records:
        vendor = row.get("vendorProject")
        cve = row.get("cveID")
        if (not isinstance(vendor, str) or not vendor.strip()
                or not isinstance(cve, str)
                or not re.fullmatch(r"CVE-\d{4}-\d{4,19}", cve)):
            raise ValueError("pinned CISA record is malformed")
        if cve in existing["sources"]:
            continue
        normalized = vendor.strip().casefold()
        if normalized not in existing["vendors"]:
            unused_by_vendor.setdefault(normalized, []).append(row)
    needed = MAX_REPLACEMENT_FAMILIES * 4
    if len(unused_by_vendor) < needed:
        raise ValueError("too few unused vendor families in pinned CISA catalog")
    vendors = sorted(unused_by_vendor,
                     key=lambda value: (factory.rank(seed, "recovery-vendor-v1", value), value))
    chosen = [min(unused_by_vendor[vendor],
                  key=lambda row: (factory.rank(seed, "recovery-cve-v1", row["cveID"]),
                                   row["cveID"])) for vendor in vendors[:needed]]
    queue = []
    for offset in range(MAX_REPLACEMENT_FAMILIES):
        four = chosen[offset * 4:(offset + 1) * 4]
        project = factory._make_project(
            seed, FIRST_REPLACEMENT_INDEX + offset, "final_candidate_unsealed", four)
        tasks = factory._tasks(project)
        queue.append({"ordinal": offset + 1, "project": project, "tasks": tasks})
    new_projects = [item["project"] for item in queue]
    combined = _boundaries(projects + new_projects)
    expected = {"projects": 36, "sources": 144, "vendors": 144,
                "entities": 36, "principals": 144, "families": 36}
    if any(len(combined[key]) != size for key, size in expected.items()):
        raise ValueError("recovery queue overlaps source/project/principal boundaries")
    existing_ids = {t["task_id"] for t in bootstrap.all_tasks(world)}
    new_ids = [t["task_id"] for item in queue for t in item["tasks"]]
    if len(new_ids) != 25 or len(set(new_ids)) != 25 or existing_ids & set(new_ids):
        raise ValueError("recovery task identity collision")
    if any({task["template_group"] for task in item["tasks"]}
           != set(factory.FAMILIES["final_candidate_unsealed"]) for item in queue):
        raise ValueError("replacement changes five-workflow family shape")
    return {"schema": SCHEMA, "source_commit": factory.SOURCE_COMMIT,
            "full_catalog_sha256": factory.SOURCE_FULL_SHA256,
            "original_world_sha256": factory.sha256(factory.canonical(world)),
            "private_seed_sha256": factory.sha256(seed),
            "max_replacement_families": MAX_REPLACEMENT_FAMILIES,
            "ordered_families": queue,
            "queue_sha256": factory.sha256(factory.canonical(queue)),
            "status": "prospective_unsealed_not_gui_qualified",
            "official_final_admitted": 0}


def public_commitment(queue: dict) -> dict:
    if (queue.get("schema") != SCHEMA
            or len(queue.get("ordered_families", [])) != 5
            or queue.get("queue_sha256")
            != factory.sha256(factory.canonical(queue["ordered_families"]))):
        raise ValueError("invalid private recovery queue")
    return {"schema": "envloop-gitlab-pre-result-recovery-commitment-v1",
            "source_commit": queue["source_commit"],
            "full_catalog_sha256": queue["full_catalog_sha256"],
            "original_world_sha256": queue["original_world_sha256"],
            "ordered_queue_sha256": queue["queue_sha256"],
            "reserve_source_families": 5,
            "reserve_candidate_tasks": 25,
            "max_whole_family_replacements": 5,
            "source_project_cve_vendor_entity_principal_disjoint": True,
            "official_final_admitted": 0,
            "model_calls": 0,
            "status": "fixed_pre_result_queue_not_admitted_final_set"}


def freeze_private_queue(queue: dict, path: Path = PRIVATE_QUEUE) -> dict:
    """Store only under evaluator-owned 0600 storage; never overwrite drift."""
    receipt = public_commitment(queue)
    path = Path(path)
    if path.exists():
        if path.stat().st_mode & 0o077:
            raise RuntimeError("private recovery queue permissions are too broad")
        if json.loads(path.read_text()) != queue:
            raise RuntimeError("existing frozen recovery queue differs")
    else:
        factory.write_private(path, queue)
    return receipt


def first_attempt_resolution(world: dict, index: dict, ledger: list[dict],
                             *, excluded_task_ids: set[str],
                             generic_fix_evidence: dict[str, str]) -> dict:
    """Reconcile all first attempts before any requalification is dispatched.

    A scored miss remains deterministic even if a later repeat in the same
    trio passed. Only a frozen generic training-control fix can authorize one
    new-clone, whole-ID requalification of that workflow.
    """
    rows = [r for r in bootstrap.all_tasks(world)
            if r["partition"] == "final_candidate_unsealed"]
    if index.get("schema") != "envloop-gitlab-development-sweep-v1":
        raise ValueError("private GUI index schema differs")
    excluded_rows = [row for row in rows if row["task_id"] in excluded_task_ids]
    if (len(excluded_task_ids) != 5 or len(excluded_rows) != 5
            or len({row["source_family"] for row in excluded_rows}) != 1):
        raise ValueError("original exposure quarantine must be one whole five-task family")
    by_id = {row["task_id"]: row for row in rows
             if row["task_id"] not in excluded_task_ids}
    items = index.get("items")
    if (not isinstance(items, dict) or len(items) != 100
            or set(items) != set(by_id)):
        raise ValueError("the original active 100-ID GUI sweep is incomplete")
    failures = []
    for task_id, item in items.items():
        history = item.get("attempts", [])
        if len(history) != 1 or item.get("status") != history[0].get("status"):
            raise ValueError("first-attempt GUI index has missing or extra attempts")
        status = item["status"]
        if status == PASS_STATUS:
            if item.get("scores") != [1.0, 0.0, 1.0] or item.get("cold_resets") != 3:
                raise ValueError("claimed GUI pass lacks full 1/0/1 and three resets")
        elif status in FAILURE_STATUSES:
            failures.append((task_id, item, by_id[task_id]))
        else:
            raise ValueError("unclassified first-attempt GUI status")
    if [entry.get("seq") for entry in ledger] != list(range(1, len(ledger) + 1)):
        raise ValueError("first failure ledger sequence is incomplete")
    ledger_by_id = {entry["task_id"]: entry for entry in ledger}
    if len(ledger_by_id) != len(failures) or set(ledger_by_id) != {t for t, _, _ in failures}:
        raise ValueError("first failures and append-only ledger do not reconcile")
    for task_id, item, row in failures:
        entry = ledger_by_id[task_id]
        if (entry.get("attempt_number") != 1
                or entry.get("status") != item["status"]
                or entry.get("scores") != item.get("scores")
                or entry.get("source_family_sha256") != factory.sha256(row["source_family"])
                or entry.get("entry_sha256") != item.get("failure_ledger_entry_sha256")):
            raise ValueError("first failure differs from immutable ledger")
    if not isinstance(generic_fix_evidence, dict):
        raise ValueError("generic fix evidence mapping is missing")
    eligible = []
    immediate_retire = []
    for task_id, item, row in sorted(failures,
                                     key=lambda entry: ledger_by_id[entry[0]]["seq"]):
        deterministic = item["status"] == "development_gui_trio_failed"
        fix = generic_fix_evidence.get(row["template_group"])
        if deterministic and (not isinstance(fix, str)
                              or not re.fullmatch(r"[0-9a-f]{64}", fix)):
            immediate_retire.append(task_id)
        else:
            eligible.append({"task_id": task_id, "first_failure_entry_sha256":
                             ledger_by_id[task_id]["entry_sha256"],
                             "first_failure_status": item["status"],
                             "source_family_sha256": factory.sha256(row["source_family"]),
                             "generic_fix_train_receipt_sha256": fix if deterministic else None,
                             "maximum_additional_attempts": 1})
    return {"schema": RESOLUTION_SCHEMA,
            "original_active_denominator": 100,
            "original_active_roster_sha256": factory.sha256(
                factory.canonical(sorted(by_id))),
            "original_first_attempts_sha256": factory.sha256(factory.canonical({
                task_id: items[task_id]["attempts"][0] for task_id in sorted(items)})),
            "original_first_attempt_passes": 100 - len(failures),
            "original_first_attempt_failures": len(failures),
            "eligible_one_time_requalifications": eligible,
            "immediate_whole_family_retirement_task_ids": immediate_retire,
            "failure_ledger_head_sha256": ledger[-1]["entry_sha256"] if ledger else None,
            "no_model_calls": True,
            "official_final_admitted": 0}


def public_resolution(private: dict) -> dict:
    if private.get("schema") != RESOLUTION_SCHEMA:
        raise ValueError("invalid private recovery resolution")
    statuses = Counter(item["first_failure_status"]
                       for item in private["eligible_one_time_requalifications"])
    return {"schema": "envloop-gitlab-pre-result-recovery-resolution-public-v1",
            "original_active_denominator": private["original_active_denominator"],
            "first_attempt_passes": private["original_first_attempt_passes"],
            "first_attempt_failures_retained": private["original_first_attempt_failures"],
            "original_active_roster_sha256": private["original_active_roster_sha256"],
            "original_first_attempts_sha256": private["original_first_attempts_sha256"],
            "eligible_one_time_requalification_count": len(
                private["eligible_one_time_requalifications"]),
            "eligible_status_counts": dict(sorted(statuses.items())),
            "immediate_retirement_task_count": len(
                private["immediate_whole_family_retirement_task_ids"]),
            "failure_ledger_head_sha256": private["failure_ledger_head_sha256"],
            "official_final_admitted": 0}


def freeze_private_resolution(resolution: dict,
                              path: Path = PRIVATE_RESOLUTION) -> dict:
    receipt = public_resolution(resolution)
    path = Path(path)
    if path.exists():
        if path.stat().st_mode & 0o077:
            raise RuntimeError("private recovery resolution permissions are too broad")
        if json.loads(path.read_text()) != resolution:
            raise RuntimeError("existing frozen recovery resolution differs")
    else:
        factory.write_private(path, resolution)
    return receipt


def read_private_resolution(path: Path = PRIVATE_RESOLUTION) -> dict:
    path = Path(path)
    if path.stat().st_mode & 0o077:
        raise RuntimeError("private recovery resolution permissions are too broad")
    result = json.loads(path.read_text())
    public_resolution(result)
    return result


def eligible_requalification_rows(rows: list[dict], index: dict,
                                  ledger: list[dict], resolution: dict) -> list[dict]:
    """Return only once-failed IDs named by a frozen first-attempt plan."""
    public_resolution(resolution)
    if (resolution.get("original_active_denominator") != 100
            or resolution.get("original_first_attempt_passes", 0)
            + resolution.get("original_first_attempt_failures", 0) != 100):
        raise ValueError("requalification resolution does not bind 100 originals")
    original_head = resolution.get("failure_ledger_head_sha256")
    ledger_hashes = {entry.get("entry_sha256") for entry in ledger}
    if (not isinstance(original_head, str)
            or original_head not in ledger_hashes):
        raise ValueError("original failure ledger head is not retained")
    allowed = resolution["eligible_one_time_requalifications"]
    if len({entry["task_id"] for entry in allowed}) != len(allowed):
        raise ValueError("duplicate eligible requalification identity")
    row_by_id = {row["task_id"]: row for row in rows}
    if len(rows) != 100 or len(row_by_id) != 100 or set(index.get("items", {})) != set(row_by_id):
        raise ValueError("requalification needs complete original 100-ID sweep")
    if (factory.sha256(factory.canonical(sorted(row_by_id)))
            != resolution.get("original_active_roster_sha256")
            or factory.sha256(factory.canonical({
                task_id: index["items"][task_id]["attempts"][0]
                for task_id in sorted(row_by_id)}))
            != resolution.get("original_first_attempts_sha256")):
        raise ValueError("first-attempt denominator or records changed after freeze")
    result = []
    for entry in allowed:
        task_id = entry["task_id"]
        if task_id not in row_by_id:
            raise ValueError("requalification identity is outside active roster")
        if entry.get("first_failure_entry_sha256") not in ledger_hashes:
            raise ValueError("first failed attempt disappeared from ledger")
        item = index["items"][task_id]
        history = item.get("attempts", [])
        if len(history) > 2:
            raise ValueError("requalification attempt cap exceeded")
        if len(history) == 2:
            continue
        if (len(history) != 1
                or item.get("status") != entry.get("first_failure_status")
                or item.get("status") not in FAILURE_STATUSES
                or history[0].get("failure_ledger_entry_sha256")
                != entry.get("first_failure_entry_sha256")
                or factory.sha256(row_by_id[task_id]["source_family"])
                != entry.get("source_family_sha256")
                or entry.get("maximum_additional_attempts") != 1):
            raise ValueError("requalification plan differs from original failed ID")
        if item["status"] == "development_gui_trio_failed":
            fix = entry.get("generic_fix_train_receipt_sha256")
            if not isinstance(fix, str) or not re.fullmatch(r"[0-9a-f]{64}", fix):
                raise ValueError("deterministic GUI miss lacks frozen generic train evidence")
        result.append(row_by_id[task_id])
    return result


def prospective_roster_after_requalification(
        world: dict, index: dict, ledger: list[dict], resolution: dict,
        queue: dict, *, excluded_task_ids: set[str]) -> dict:
    """Bind FIFO whole-family replacements after every one-time retry ends.

    This returns an inventory plan. It does not claim that any replacement has
    been bootstrapped, GUI-qualified, cold-reset, or officially admitted.
    """
    public_commitment(queue)
    public_resolution(resolution)
    current = [row for row in bootstrap.all_tasks(world)
               if row["partition"] == "final_candidate_unsealed"
               and row["task_id"] not in excluded_task_ids]
    by_id = {row["task_id"]: row for row in current}
    if len(current) != 100 or len(by_id) != 100 or set(index.get("items", {})) != set(by_id):
        raise ValueError("the original active 100-ID GUI sweep is incomplete")
    if (factory.sha256(factory.canonical(sorted(by_id)))
            != resolution.get("original_active_roster_sha256")
            or factory.sha256(factory.canonical({
                task_id: index["items"][task_id]["attempts"][0]
                for task_id in sorted(by_id)}))
            != resolution.get("original_first_attempts_sha256")):
        raise ValueError("original first-attempt denominator changed after freeze")
    first_head = resolution["failure_ledger_head_sha256"]
    original_ledger = next((entry for entry in ledger
                            if entry.get("entry_sha256") == first_head), None)
    if original_ledger is None:
        raise ValueError("original failure ledger head is missing")
    initial_failed = set(resolution["immediate_whole_family_retirement_task_ids"])
    allowed = resolution["eligible_one_time_requalifications"]
    for entry in allowed:
        task_id = entry["task_id"]
        if task_id not in by_id:
            raise ValueError("requalification task left active roster")
        item = index["items"][task_id]
        attempts = item.get("attempts", [])
        if (len(attempts) != 2
                or attempts[0].get("failure_ledger_entry_sha256")
                   != entry["first_failure_entry_sha256"]):
            raise ValueError("one-time requalification is incomplete or changed")
        if item.get("status") == PASS_STATUS:
            if item.get("scores") != [1.0, 0.0, 1.0] or item.get("cold_resets") != 3:
                raise ValueError("requalification pass lacks 1/0/1 and three resets")
        elif item.get("status") in FAILURE_STATUSES:
            second_hash = attempts[1].get("failure_ledger_entry_sha256")
            if second_hash not in {row.get("entry_sha256") for row in ledger}:
                raise ValueError("second failure is absent from append-only ledger")
            initial_failed.add(task_id)
        else:
            raise ValueError("requalification status is unclassified")
    first_failure_order = {row["task_id"]: row["seq"] for row in ledger
                           if row.get("attempt_number") == 1}
    retired_families = {}
    for task_id in initial_failed:
        if task_id not in by_id or task_id not in first_failure_order:
            raise ValueError("retired family lacks an original failed task")
        family = by_id[task_id]["source_family"]
        retired_families[family] = min(first_failure_order[task_id],
                                       retired_families.get(family, 10**9))
    retirement_order = sorted(retired_families,
                              key=lambda family: (retired_families[family], family))
    if len(retirement_order) > MAX_REPLACEMENT_FAMILIES:
        raise ValueError("prospective whole-family replacement cap exceeded")
    retired_ids = {row["task_id"] for row in current
                   if row["source_family"] in retirement_order}
    if len(retired_ids) != 5 * len(retirement_order):
        raise ValueError("retirement would split a correlated project family")
    replacements = queue["ordered_families"][:len(retirement_order)]
    replacement_ids = {task["task_id"] for item in replacements
                       for task in item["tasks"]}
    candidate_ids = ({row["task_id"] for row in current} - retired_ids) | replacement_ids
    if len(candidate_ids) != 100:
        raise ValueError("FIFO whole-family replacement did not restore 100 identities")
    return {"schema": "envloop-gitlab-prospective-roster-after-requalification-v1",
            "original_active_denominator": 100,
            "original_first_attempt_failures": resolution["original_first_attempt_failures"],
            "retired_source_families": retirement_order,
            "retired_original_task_ids": sorted(retired_ids),
            "ordered_replacements": replacements,
            "prospective_candidate_task_ids": sorted(candidate_ids),
            "still_requires_replacement_gui_trios": 5 * len(replacements),
            "replacement_queue_sha256": queue["queue_sha256"],
            "official_final_admitted": 0}


def public_roster_plan(private: dict) -> dict:
    if private.get("schema") != "envloop-gitlab-prospective-roster-after-requalification-v1":
        raise ValueError("invalid private prospective roster")
    return {"schema": "envloop-gitlab-prospective-roster-public-v1",
            "original_active_denominator": 100,
            "original_first_attempt_failures_retained": private[
                "original_first_attempt_failures"],
            "retired_whole_source_families": len(private["retired_source_families"]),
            "retired_original_task_ids": len(private["retired_original_task_ids"]),
            "fifo_replacement_source_families": len(private["ordered_replacements"]),
            "prospective_candidate_task_count": len(
                private["prospective_candidate_task_ids"]),
            "replacement_gui_trios_still_required": private[
                "still_requires_replacement_gui_trios"],
            "ordered_queue_sha256": private["replacement_queue_sha256"],
            "official_final_admitted": 0,
            "status": "prospective_inventory_only_not_qualified"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["freeze-queue", "freeze-resolution"])
    parser.add_argument("--world-path", type=Path, default=bootstrap.WORLD_FILE)
    parser.add_argument("--seed-path", type=Path, default=bootstrap.SEED_FILE)
    parser.add_argument("--catalog-path", type=Path, default=FULL_CATALOG)
    parser.add_argument("--private-queue-path", type=Path, default=PRIVATE_QUEUE)
    parser.add_argument("--generic-fix-evidence-path", type=Path)
    parser.add_argument("--private-resolution-path", type=Path,
                        default=PRIVATE_RESOLUTION)
    args = parser.parse_args()
    private_inputs = ((args.world_path, args.seed_path)
                      if args.action == "freeze-queue" else (args.world_path,))
    for private_path in private_inputs:
        if private_path.stat().st_mode & 0o077:
            raise RuntimeError("private GitLab world/seed permissions are too broad")
    world = json.loads(args.world_path.read_text())
    if args.action == "freeze-queue":
        seed = args.seed_path.read_text().strip()
        queue = ordered_queue(seed, world, load_catalog(args.catalog_path))
        public = freeze_private_queue(queue, args.private_queue_path)
    else:
        if args.generic_fix_evidence_path is None:
            raise ValueError("freeze-resolution requires explicit generic fix evidence map")
        if args.generic_fix_evidence_path.stat().st_mode & 0o077:
            raise RuntimeError("generic fix evidence map permissions are too broad")
        fixes = json.loads(args.generic_fix_evidence_path.read_text())
        if (fixes.get("schema") != "envloop-gitlab-generic-fix-evidence-map-v1"
                or not isinstance(fixes.get("workflows"), dict)):
            raise ValueError("generic fix evidence map schema differs")
        from . import failure_ledger, quarantine, sweep
        index = sweep._load()
        sweep.reconcile_failure_ledger(index)
        resolution = first_attempt_resolution(
            world, index, failure_ledger.private_entries(),
            excluded_task_ids=quarantine.excluded_task_ids(),
            generic_fix_evidence=fixes["workflows"])
        public = freeze_private_resolution(resolution, args.private_resolution_path)
    print(json.dumps(public, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
