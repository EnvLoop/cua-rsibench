"""Audit a complete Odoo GUI gate without exposing seed, gold or credentials.

This reports candidate environment qualification only. The global study
controller must separately freeze the common model action/observation contract
and hidden task package before promoting candidates into an official final set.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path

from factory import CODE_DIR, HERE, PRIVATE, OdooRPC, local_config
from partition_factory import (ALL_SPLIT_COUNTS, FAMILIES, ROLE_GROUP_XMLIDS,
                               validate_scale_splits)
from reset import file_hash, restore
from sweep_partition import NEGATIVE_CODES
from worker_lease import exclusive_worker_operation


def _read_only_privileges() -> bool:
    tables = ("purchase_order", "purchase_order_line", "sale_order", "sale_order_line",
              "stock_picking", "stock_move", "stock_move_line", "account_move",
              "account_move_line", "crm_lead", "res_partner", "res_users", "product_product",
              "stock_warehouse_orderpoint", "ir_attachment")
    checks = []
    for table in tables:
        checks.append(
            f"has_table_privilege('bench_verify','{table}','SELECT') AND "
            f"NOT has_table_privilege('bench_verify','{table}','UPDATE') AND "
            f"NOT has_table_privilege('bench_verify','{table}','DELETE') AND "
            f"NOT has_table_privilege('bench_verify','{table}','INSERT')")
    sql = "SELECT (" + " AND ".join(checks) + ")::text"
    command = ["docker", "compose", "--env-file", ".env", "exec", "-T", "db",
               "psql", "-U", "bench_verify", "-d", "bench", "-At",
               "-v", "ON_ERROR_STOP=1", "-c", sql]
    return subprocess.run(command, cwd=HERE, check=True,
                          capture_output=True, text=True).stdout.strip() == "true"


def audit(run_id: str, output: Path) -> dict:
    with exclusive_worker_operation("audit_partition"):
        return _audit_unlocked(run_id, output)


def _audit_unlocked(run_id: str, output: Path) -> dict:
    config = local_config()
    partition = config.get("ODOO_PARTITION")
    if partition not in ALL_SPLIT_COUNTS:
        raise RuntimeError("Audit requires an isolated candidate world")
    expected_count = ALL_SPLIT_COUNTS[partition] * len(FAMILIES)
    expected_source_files = 3 * ALL_SPLIT_COUNTS[partition] + 1
    receipt = json.loads((PRIVATE / "partition_receipt.json").read_text())
    checkpoint = json.loads((PRIVATE / "checkpoint_receipt.json").read_text())
    world = json.loads((PRIVATE / "partition_cases.json").read_text())
    sources = json.loads((PRIVATE / "source_hashes.json").read_text())
    task_sets = json.loads((PRIVATE / "task_set_manifest.json").read_text())
    if receipt["case_manifest_sha256"] != hashlib.sha256(
            json.dumps(world, sort_keys=True).encode()).hexdigest():
        raise RuntimeError("Case manifest digest drift")
    if receipt["source_hash_manifest_sha256"] != hashlib.sha256(
            json.dumps(sources, sort_keys=True).encode()).hexdigest():
        raise RuntimeError("Source hash manifest digest drift")
    if receipt["task_set_manifest_sha256"] != hashlib.sha256(
            json.dumps(task_sets, sort_keys=True).encode()).hexdigest():
        raise RuntimeError("Task package identity digest drift")
    validate_scale_splits(task_sets)
    role_policy = {"required_group_xmlids": list(ROLE_GROUP_XMLIDS),
                   "forbidden_group_xmlids": ["base.group_system"],
                   "email_domain": "example.invalid"}
    if receipt["role_policy_sha256"] != hashlib.sha256(
            json.dumps(role_policy, sort_keys=True).encode()).hexdigest():
        raise RuntimeError("Actor role policy drift")
    for filename, digest in receipt["pinned_code_and_runtime_sha256"].items():
        if file_hash(CODE_DIR / filename) != digest:
            raise RuntimeError(f"Pinned Odoo code/runtime drift: {filename}")
    for archive, key in (("baseline.pgcustom", "db_sha256"),
                         ("baseline-filestore.tgz", "filestore_sha256")):
        if file_hash(PRIVATE / archive) != checkpoint[key]:
            raise RuntimeError(f"Frozen {archive} drift")
    expected = {case["id"]: family for family in FAMILIES
                for case in world["cases"][family]}
    packages = {row["task_id"]: row["package_sha256"]
                for rows in task_sets.values() for row in rows}
    if len(expected) != expected_count:
        raise RuntimeError("Candidate world does not contain its exact frozen ID count")
    run_dir = PRIVATE / "admission_runs" / run_id
    if not run_dir.is_dir():
        raise RuntimeError("Unknown admission run ID")
    recorded = json.loads((run_dir / "summary.json").read_text())
    rows = [json.loads(path.read_text()) for path in run_dir.glob("*.json")
            if path.name != "summary.json"]
    seen = {row["case_id"] for row in rows}
    if len(rows) != len(seen) or seen != set(expected):
        raise RuntimeError("Admission run does not cover exactly the frozen 100 IDs")
    if recorded["attempted_this_run"] != expected_count or len(recorded["cases"]) != expected_count:
        raise RuntimeError("Recorded run count differs from per-case receipts")
    if {row["case_id"]: row for row in recorded["cases"]} != {
            row["case_id"]: row for row in rows}:
        raise RuntimeError("Recorded run summary differs from per-case receipts")
    ordered = recorded["cases"]
    for earlier, later in zip(ordered, ordered[1:]):
        if datetime.fromisoformat(earlier["finished_at_utc"]) > datetime.fromisoformat(
                later["started_at_utc"]):
            raise RuntimeError("Per-case GUI intervals overlap")
    pids = {row["worker_pid"] for row in ordered}
    if len(pids) != 1:
        raise RuntimeError("A single admission run changed worker process")
    worker_pid = next(iter(pids))
    first_start = datetime.fromisoformat(ordered[0]["started_at_utc"])
    last_finish = datetime.fromisoformat(ordered[-1]["finished_at_utc"])
    events_path = PRIVATE / "worker-lease-events.jsonl"
    events = [json.loads(line) for line in events_path.read_text().splitlines()]
    exclusive_interval = False
    for index, event in enumerate(events):
        if (event["operation"] != "sweep_partition" or event["event"] != "acquired"
                or event["pid"] != worker_pid
                or datetime.fromisoformat(event["at_utc"]) > first_start):
            continue
        release = next((row for row in events[index + 1:]
                        if row["operation"] == "sweep_partition"
                        and row["event"] == "released" and row["pid"] == worker_pid), None)
        if release and datetime.fromisoformat(release["at_utc"]) >= last_finish:
            exclusive_interval = True
            break
    if not exclusive_interval:
        raise RuntimeError("No completed exclusive worker lease encloses every case")
    if any(first_start <= datetime.fromisoformat(event["at_utc"]) <= last_finish
           and (event["pid"] != worker_pid or event["operation"] != "sweep_partition")
           for event in events):
        raise RuntimeError("Another worker operation overlapped admission cases")
    qualified = []
    baseline_digest = file_hash(PRIVATE / "baseline_snapshot.json")
    for row in rows:
        family = expected[row["case_id"]]
        start = datetime.fromisoformat(row["started_at_utc"])
        finish = datetime.fromisoformat(row["finished_at_utc"])
        passed = (
            row["family"] == family
            and start.tzinfo is not None and finish.tzinfo is not None and start <= finish
            and row["status"] == "candidate_environment_gui_qualified"
            and row["official_final_task"] is False
            and row["task_package_sha256"] == packages[row["case_id"]]
            and row["baseline_snapshot_sha256"] == baseline_digest
            and row["exclusive_worker_lease_held"] is True
            and row["worker_pid"] == worker_pid
            and row["cold_reset_before"] is True
            and row["cold_reset_after"] is True
            and row["source_visible_in_native_gui"] is True
            and row["baseline_reward"] == 0.0
            and row["gui_oracle_reward"] == 1.0
            and row["positive_difference_codes"] == []
            and row["wrong_object_reward"] == 0.0
            and NEGATIVE_CODES[family] in row["wrong_object_difference_codes"]
            and row["after_reset_reward"] == 0.0
            and row["protected_source_files_checked"] == expected_source_files
        )
        if passed:
            qualified.append(row)
    actor_id = receipt["actor_id"]
    rpc = OdooRPC()
    actor = rpc.call("res.users", "read", [actor_id],
                     fields=["groups_id", "email", "active"])[0]
    admin_group = rpc.call("ir.model.data", "search_read",
                           [["module", "=", "base"], ["name", "=", "group_system"]],
                           fields=["res_id"], limit=1)[0]["res_id"]
    actor_scoped = (actor["active"] and actor["email"].endswith("@example.invalid")
                    and admin_group not in actor["groups_id"]
                    and set(receipt["actor_role_group_ids"]).issubset(actor["groups_id"]))
    reset_result = restore()
    final_reset_exact = (reset_result["business_snapshot_equal"]
                         and reset_result["physical_filestore_equal_before_web_restart"])
    read_only = _read_only_privileges()
    all_qualified = len(qualified) == expected_count and actor_scoped and final_reset_exact and read_only
    result = {
        "schema": "envloop-odoo-partition-candidate-gui-audit-v1",
        "status": "candidate_environment_qualified" if all_qualified else "candidate_gate_incomplete",
        "partition": partition,
        "run_id": run_id,
        "candidate_cases": expected_count,
        "cases_with_all_per_id_controls": len(qualified),
        "per_family_qualified": dict(Counter(row["family"] for row in qualified)),
        "negative_codes_required": NEGATIVE_CODES,
        "all_sources_visible_in_native_gui": len(qualified) == expected_count,
        "actor_role_scoped_no_admin_group": bool(actor_scoped),
        "evaluator_select_only_on_scored_tables": bool(read_only),
        "exclusive_worker_lease_interval_verified": exclusive_interval,
        "final_database_and_physical_filestore_reset_exact": bool(final_reset_exact),
        "protected_attachment_files_per_attempt": expected_source_files,
        "product_planning_notes_in_database_snapshot": ALL_SPLIT_COUNTS[partition],
        "world_case_manifest_sha256": receipt["case_manifest_sha256"],
        "world_source_hash_manifest_sha256": receipt["source_hash_manifest_sha256"],
        "task_set_manifest_sha256": receipt["task_set_manifest_sha256"],
        "role_policy_sha256": receipt["role_policy_sha256"],
        "pinned_code_and_runtime_sha256": receipt["pinned_code_and_runtime_sha256"],
        "world_seed_sha256": receipt["master_seed_sha256"],
        "db_checkpoint_sha256": checkpoint["db_sha256"],
        "filestore_checkpoint_sha256": checkpoint["filestore_sha256"],
        "official_final_tasks_admitted": 0,
        "researcher_campaigns": 0,
        "model_attempts": 0,
        "global_hidden_task_and_action_contract_freeze_pending": True,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    if not all_qualified:
        raise RuntimeError(f"Candidate gate incomplete: {len(qualified)}/{expected_count}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.run_id, args.output), indent=2))
