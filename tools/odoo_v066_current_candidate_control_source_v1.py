"""Validate a dated source-only Odoo current-candidate one-case runtime freeze."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from tools import odoo_v066_scale_protocol_v1 as protocol
from tools import propose_odoo_v066_candidate_control_adoption_v1 as proposal


ROOT = protocol.ROOT
FREEZE = ROOT / "docs/evidence/odoo-v066-current-candidate-one-case-source-freeze-2026-09-29.json"
SCHEMA = "envloop-odoo-v066-current-candidate-one-case-source-freeze-v1"
SOURCE_FILES = (
    "tools/odoo_v066_current_candidate_epoch_v1.py",
    "tools/audit_odoo_v066_current_candidate_epoch_v1.py",
    "tools/odoo_v066_current_candidate_no_gui_gate_v1.py",
    "tools/audit_odoo_v066_current_candidate_no_gui_gate_v1.py",
    "tools/odoo_v066_current_candidate_case_v1.py",
    "tools/audit_odoo_v066_current_candidate_case_v1.py",
    "tools/odoo_v066_current_candidate_one_selection_v1.py",
    "tools/odoo_v066_current_candidate_control_source_v1.py",
)
PLANS = {
    "selection": ROOT / "docs/evidence/odoo-v066-current-candidate-selection-evaluator-plan-2026-09-29.json",
    "official_hidden": ROOT / "docs/evidence/odoo-v066-current-candidate-official_hidden-evaluator-plan-2026-09-29.json",
}


class SourceFreezeError(ValueError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise SourceFreezeError(code)


def digest(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(),
            "current_case_source_or_receipt_missing")
    return sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    observed = proposal.inspect()
    require(observed == protocol.public_json(proposal.PUBLIC),
            "current_case_adoption_proposal_changed")
    old, old_sha = protocol.validate_source_freeze(proposal.FREEZE)
    require(old_sha == observed["odoo_validator_source_freeze_sha256"] and
            old["retained_selection_failed_controls_before_freeze"] == 3 and
            old["official_final_tasks_admitted"] == 0,
            "current_case_old_source_or_failure_epoch_changed")
    plans = {split: digest(path) for split, path in PLANS.items()}
    for split, path in PLANS.items():
        value = protocol.public_json(path)
        require(value.get("schema") ==
                "envloop-odoo-v066-current-candidate-evaluator-plan-public-v1" and
                value.get("status") ==
                "source_bound_evaluator_only_pending_current_baseline_gate" and
                value.get("split") == split and
                value.get("candidate_count") ==
                (20 if split == "selection" else 100) and
                value.get("current_candidate_private_sha256") ==
                observed["current_six_cell_candidate_private_sha256"] and
                value.get("source_freeze_sha256") == old_sha and
                value.get("control_dispatch_authorized") is False and
                value.get("official_final_tasks_admitted") == 0,
                "current_case_split_plan_not_source_only")
    sources = {relative: digest(ROOT / relative) for relative in SOURCE_FILES}
    return {
        "schema": SCHEMA,
        "status": "source_bound_one_selection_control_pending_ac_gate_no_gui_result",
        "as_of_date": "2026-09-29",
        "current_candidate_private_sha256":
            observed["current_six_cell_candidate_private_sha256"],
        "current_candidate_adoption_public_sha256": digest(proposal.PUBLIC),
        "old_25_file_validator_freeze_sha256": old_sha,
        "new_source_sha256s": sources,
        "new_split_public_plan_sha256s": plans,
        "retained_terminal_failure_public_sha256s":
            observed["retained_terminal_failure_public_sha256s"],
        "one_selection_control_requires_ac_and_independent_no_gui_gate": True,
        "default_cli_execute": False,
        "automatic_replay_authorized": False,
        "campaign_dispatch_authorized": False,
        "fresh_current_profile_gui_controls": 0,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }


def validate(path: Path = FREEZE) -> dict:
    observed = protocol.public_json(path)
    expected = build()
    require(observed == expected, "current_case_source_freeze_or_plan_changed")
    return observed


def write() -> dict:
    require(not FREEZE.exists() and not FREEZE.is_symlink(),
            "current_case_source_freeze_must_be_new")
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
                      "campaign_dispatch_authorized": False,
                      "official_final_tasks_admitted": 0}, sort_keys=True))
