"""Freeze the additive, evaluator-only Odoo DB-readiness amendment.

The v3 lease-prefix epoch, all three failed GUI attempts, their published
incidents, and the current candidate plans remain unchanged. This epoch
waits for PostgreSQL health and a read-only verifier SELECT before baseline
snapshotting; it never authorizes a GUI by itself.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from tools import odoo_v066_lease_prefix_source_v3 as previous
from tools import odoo_v066_scale_protocol_v1 as protocol


ROOT = protocol.ROOT
FREEZE = (ROOT / "docs/evidence" /
          "odoo-v066-db-readiness-control-source-freeze-2026-09-29.json")
SCHEMA = "envloop-odoo-v066-db-readiness-control-source-freeze-v4"
SOURCE_FILES = (
    "tools/odoo_v066_current_candidate_no_gui_gate_v4.py",
    "tools/audit_odoo_v066_current_candidate_no_gui_gate_v4.py",
    "tools/odoo_v066_current_candidate_one_selection_v4.py",
    "tools/audit_odoo_v066_battery_authorized_batch_v4.py",
    "tools/odoo_v066_db_readiness_source_v4.py",
)


class DbReadinessSourceError(ValueError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise DbReadinessSourceError(code)


def digest(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(),
            "db_readiness_source_file_missing")
    return sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    old = previous.validate()
    require(old["selection_control_only"] is True and
            old["historical_lease_rule"] ==
            "exact_published_newline_prefix_ending_in_original_release" and
            old["ac_power_required"] is False and
            old["independent_current_sql_full_filestore_gate_required"]
            is True and old["official_final_tasks_admitted"] == 0 and
            old["model_attempts"] == 0,
            "db_readiness_prior_lease_prefix_epoch_changed")
    return {
        "schema": SCHEMA,
        "status": "source_bound_db_readiness_amendment_pending_live_gate",
        "as_of_date": "2026-09-29",
        "prior_lease_prefix_source_freeze_sha256": digest(previous.FREEZE),
        "new_source_sha256s": {
            name: digest(ROOT / name) for name in SOURCE_FILES},
        "unchanged_current_candidate_private_sha256":
            old["unchanged_current_candidate_private_sha256"],
        "unchanged_split_public_plan_sha256s":
            old["unchanged_split_public_plan_sha256s"],
        "unchanged_retained_failure_public_sha256s":
            old["unchanged_retained_failure_public_sha256s"],
        "historical_lease_rule": old["historical_lease_rule"],
        "appended_lease_rule": old["appended_lease_rule"],
        "db_readiness_rule":
            "bounded_pg_isready_then_verifier_select_1_before_full_baseline",
        "db_readiness_timeout_seconds": 60,
        "db_readiness_probe_timeout_seconds": 5,
        "db_readiness_max_probes": 30,
        "prior_v3_gate_sql_filestore_outputs_must_be_absent": True,
        "old_auditors_and_attempts_unchanged": True,
        "host_power_samples_required": old["host_power_samples_required"],
        "ac_power_required": False,
        "independent_current_sql_full_filestore_gate_required": True,
        "fresh_run_nonce_and_no_automatic_replay_required": True,
        "selection_control_only": True,
        "campaign_dispatch_authorized": False,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }


def validate(path: Path = FREEZE) -> dict:
    recorded = protocol.public_json(path)
    expected = build()
    require(recorded == expected,
            "db_readiness_source_freeze_or_prior_epoch_changed")
    return recorded


def write() -> dict:
    require(not FREEZE.exists() and not FREEZE.is_symlink(),
            "db_readiness_source_freeze_must_be_new")
    value = build()
    with FREEZE.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")
    return value


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    value = write() if args.write else validate()
    print(json.dumps({"status": value["status"],
                      "source_freeze_sha256": digest(FREEZE),
                      "official_final_tasks_admitted": 0}, sort_keys=True))
