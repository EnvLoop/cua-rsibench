"""Freeze a dated battery-authorized evaluator-only Odoo control epoch.

The AC-only v1 freeze, split plans, three failed attempts and validator freeze
remain unchanged. This additive source epoch changes only host-power admission
and telemetry for the no-GUI gate and one selection GUI control.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from tools import odoo_v066_current_candidate_control_source_v1 as previous
from tools import odoo_v066_scale_protocol_v1 as protocol


ROOT = protocol.ROOT
FREEZE = ROOT / "docs/evidence/odoo-v066-battery-authorized-control-source-freeze-2026-09-29.json"
SCHEMA = "envloop-odoo-v066-battery-authorized-control-source-freeze-v2"
SOURCE_FILES = (
    "tools/odoo_v066_battery_authorized_power_v2.py",
    "tools/odoo_v066_current_candidate_no_gui_gate_v2.py",
    "tools/audit_odoo_v066_current_candidate_no_gui_gate_v2.py",
    "tools/odoo_v066_current_candidate_one_selection_v2.py",
    "tools/audit_odoo_v066_battery_authorized_batch_v2.py",
    "tools/odoo_v066_battery_authorized_source_v2.py",
)


class BatterySourceError(ValueError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise BatterySourceError(code)


def digest(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), "battery_source_file_missing")
    return sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    old = previous.validate()
    require(old["one_selection_control_requires_ac_and_independent_no_gui_gate"] is True and
            old["fresh_current_profile_gui_controls"] == 0 and
            old["official_final_tasks_admitted"] == 0,
            "battery_amendment_prior_ac_epoch_changed")
    return {
        "schema": SCHEMA,
        "status": "source_bound_battery_authorized_evaluator_only_pending_live_gate",
        "as_of_date": "2026-09-29",
        "user_authorization": "run_with_available_battery_do_not_wait_for_ac",
        "previous_ac_only_source_freeze_sha256": digest(previous.FREEZE),
        "new_source_sha256s": {name: digest(ROOT / name)
                               for name in SOURCE_FILES},
        "unchanged_current_candidate_private_sha256":
            old["current_candidate_private_sha256"],
        "unchanged_split_public_plan_sha256s":
            old["new_split_public_plan_sha256s"],
        "unchanged_retained_failure_public_sha256s":
            old["retained_terminal_failure_public_sha256s"],
        "host_power_samples_required": ["gate_entry", "gate_exit",
                                        "runner_pre_intent", "runner_pre_dispatch",
                                        "runner_end"],
        "ac_power_required": False,
        "battery_percent_threshold": None,
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
            "battery_amendment_source_freeze_or_prior_epoch_changed")
    return recorded


def write() -> dict:
    require(not FREEZE.exists() and not FREEZE.is_symlink(),
            "battery_amendment_source_freeze_must_be_new")
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
