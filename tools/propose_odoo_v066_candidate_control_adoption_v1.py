"""Audit a proposed Odoo evaluator-control adoption; never authorize dispatch.

The current six-cell source candidate cannot retroactively ratify the three
failed Odoo selection controls or promote historical split plans. This module
records the exact public source boundary so a later, independently gated
control-only epoch can be reviewed without rewriting any earlier evidence.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from tools import ratify_v066_current_six_cell_candidate_v1 as candidate_builder
from tools import odoo_v066_scale_protocol_v1 as protocol


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/evidence"
DATE = "2026-09-29"
CANDIDATE = EVIDENCE / "full-study-v066-current-six-cell-source-candidate-2026-09-29.json"
FREEZE = EVIDENCE / "odoo-v066-scale-validator-v066-source-freeze-2026-09-29.json"
SELECTION = EVIDENCE / "odoo-v066-selection-control-plan-validator-v066-2026-09-29.json"
HIDDEN = EVIDENCE / "odoo-v066-official_hidden-control-plan-validator-v066-2026-09-29.json"
FAILURES = (
    ("first", "odoo-v066-selection-first-exact-frame-flicker-incident-2026-09-28.json",
     "failed_after_three_gui_navigation_actions_before_source_or_save"),
    ("second", "odoo-v066-selection-second-post-intent-stale-2026-09-29.json",
     "post_intent_exact_return_exhausted_before_double_click_dispatch"),
    ("third", "odoo-v066-selection-third-validator-mismatch-2026-09-29.json",
     "post_intent_pre_dispatch_base_validator_rejected_v066_double_click"),
)
PUBLIC = EVIDENCE / "odoo-v066-current-candidate-control-adoption-proposal-2026-09-29.json"
SCHEMA = "envloop-odoo-v066-current-candidate-control-adoption-proposal-public-v1"


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def read_public(path: Path) -> tuple[dict, str]:
    require(path.is_file() and not path.is_symlink() and path.stat().st_size < 2_000_000,
            "public_adoption_input_missing_or_unsafe")
    raw = path.read_bytes()
    value = json.loads(raw)
    require(type(value) is dict, "public_adoption_input_not_object")
    return value, sha256(raw).hexdigest()


def inspect(*, candidate_path: Path = CANDIDATE,
            selection_path: Path = SELECTION) -> dict:
    candidate, candidate_sha = read_public(candidate_path)
    _expected_private, expected_candidate = candidate_builder.build()
    require(candidate == expected_candidate and
            candidate.get("status") == "source_bound_candidate_only_no_dispatch_authority" and
            candidate.get("campaign_dispatch_authorized") is False and
            candidate.get("qualified_final_tasks") == 0 and
            candidate.get("researcher_campaigns") == 0 and
            candidate.get("official_final_model_results") == 0,
            "current_six_cell_candidate_not_current_or_not_source_only")

    freeze, freeze_sha = protocol.validate_source_freeze(FREEZE)
    require(freeze.get("status") ==
            "frozen_after_v066_pre_dispatch_validator_correction" and
            freeze.get("source_sha256s") == protocol.current_source_hashes() and
            freeze.get("retained_selection_failed_controls_before_freeze") == 3 and
            freeze.get("official_final_gui_controls_before_freeze") == 0 and
            freeze.get("official_final_tasks_admitted") == 0 and
            freeze.get("model_attempts") == 0 and
            candidate["upstream_evidence_sha256s"]["odoo_validator_source_freeze"] ==
            freeze_sha,
            "odoo_validator_source_epoch_changed")

    plans = {}
    for split, path, expected_count in (("selection", selection_path, 20),
                                        ("official_hidden", HIDDEN, 100)):
        plan, plan_sha = read_public(path)
        require(plan.get("schema") == protocol.PUBLIC_PLAN_SCHEMA and
                plan.get("status") == "split_source_bound_plan_only_no_gui_dispatch" and
                plan.get("split") == split and
                plan.get("candidate_count") == expected_count and
                plan.get("ratification_sha256") == freeze["ratification_sha256"] and
                plan.get("ratification_sha256") !=
                candidate["private_candidate_sha256"] and
                plan.get("source_freeze_sha256") == freeze_sha and
                plan.get("physical_dispatch_profile") ==
                freeze["physical_dispatch_profile"] and
                plan.get("validator_amendment") == freeze["validator_amendment"] and
                plan.get("fresh_current_profile_gui_controls") == 0 and
                plan.get("model_attempts") == 0 and
                plan.get("official_final_tasks_admitted") == 0 and
                plan.get("researcher_campaigns") == 0 and
                candidate["upstream_evidence_sha256s"][
                    "odoo_selection_plan" if split == "selection"
                    else "odoo_hidden_plan"] ==
                plan_sha,
                "historical_split_plan_cannot_be_relabelled_as_current_control")
        plans[split] = {"public_sha256": plan_sha,
                        "private_sha256": plan["private_plan_sha256"],
                        "historical_ratification_sha256":
                        plan["ratification_sha256"]}

    failures = {}
    for label, name, status in FAILURES:
        record, record_sha = read_public(EVIDENCE / name)
        require(record.get("status") == status and
                record.get("official_final_tasks_admitted") == 0 and
                record.get("model_attempts") == 0 and
                record.get("selection_worker_locks_free") is True,
                "retained_selection_failure_changed")
        failures[label] = record_sha

    return {
        "schema": SCHEMA,
        "date": DATE,
        "status": "source_only_rebind_proposal_no_gui_authority",
        "current_six_cell_candidate_public_sha256": candidate_sha,
        "current_six_cell_candidate_private_sha256":
            candidate["private_candidate_sha256"],
        "odoo_validator_source_freeze_sha256": freeze_sha,
        "historical_split_plans": plans,
        "retained_terminal_failure_public_sha256s": failures,
        "retained_terminal_selection_attempts": 3,
        "fresh_current_profile_selection_controls": 0,
        "new_evaluator_only_split_plan_required": True,
        "fresh_private_same_id_run_and_nonce_required": True,
        "independent_current_sql_and_full_filestore_gate_required": True,
        "old_failed_attempts_reused": False,
        "control_dispatch_authorized": False,
        "campaign_dispatch_authorized": False,
        "official_final_tasks_admitted": 0,
        "researcher_campaigns": 0,
        "model_attempts": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-public", action="store_true")
    args = parser.parse_args()
    value = inspect()
    if args.write_public:
        require(not PUBLIC.exists() and not PUBLIC.is_symlink(),
                "adoption_proposal_public_receipt_already_exists")
        with PUBLIC.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True, indent=2)
            stream.write("\n")
    else:
        observed, _ = read_public(PUBLIC)
        require(observed == value, "published_adoption_proposal_changed")
    print(json.dumps({"status": value["status"],
                      "control_dispatch_authorized": False,
                      "campaign_dispatch_authorized": False,
                      "official_final_tasks_admitted": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
