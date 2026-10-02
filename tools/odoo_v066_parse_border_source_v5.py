"""One-time source freeze for the additive Odoo parse-border v5 evaluator.

The freeze binds source before any v5 no-GUI gate or GUI attempt. It does not
grant a researcher campaign, model attempt, or official final admission.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from tools import audit_odoo_v066_current_candidate_first_failure_20260929 as failure
from tools import odoo_v066_db_readiness_source_v4 as previous
from tools import odoo_v066_scale_protocol_v1 as protocol


ROOT = protocol.ROOT
FREEZE = (ROOT / "docs/evidence" /
          "odoo-v066-parse-border-v5-source-freeze-2026-09-29.json")
SCHEMA = "envloop-odoo-v066-parse-border-source-freeze-v5"
PRE_REVIEW_FREEZE_SHA256 = (
    "ab508878479acc27ce747648deac7d61ce2994de96c87862f4f876936d177961"
)
SOURCE_FILES = (
    "enterprise_fallback/odoo18/odoo_v066_scale_parse_border_adapter_v5.py",
    "tools/audit_odoo_v066_current_candidate_first_failure_20260929.py",
    "tools/audit_odoo_v066_parse_border_v5.py",
    "tools/odoo_v066_current_candidate_case_v5.py",
    "tools/audit_odoo_v066_parse_border_case_v5.py",
    "tools/odoo_v066_parse_border_plan_v5.py",
    "tools/odoo_v066_parse_border_no_gui_gate_v5.py",
    "tools/audit_odoo_v066_parse_border_no_gui_gate_v5.py",
    "tools/odoo_v066_parse_border_one_selection_v5.py",
    "tools/odoo_v066_parse_border_source_v5.py",
    "tests/test_odoo_v066_current_candidate_first_failure_20260929.py",
    "tests/test_odoo_v066_scale_parse_border_adapter_v5.py",
    "tests/test_odoo_v066_parse_border_audit_v5.py",
    "tests/test_odoo_v066_parse_border_plan_v5.py",
    "tests/test_odoo_v066_parse_border_gate_v5.py",
)


class ParseSourceError(ValueError):
    pass


def need(ok: bool, code: str) -> None:
    if not ok:
        raise ParseSourceError(code)


def digest(path: Path) -> str:
    need(path.is_file() and not path.is_symlink(),
         "parse_source_file_missing_or_symlink")
    return sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    prior = previous.validate()
    failed = protocol.public_json(failure.PUBLIC_PATH)
    need(prior["official_final_tasks_admitted"] == 0 and
         prior["model_attempts"] == 0 and
         failed.get("status") ==
         "one_original_current_candidate_gui_failure_independently_verified_no_replay" and
         failed.get("rejected_action_intent_created") is False and
         failed.get("rejected_action_dispatched") is False and
         failed.get("baseline_sql_and_full_filestore_restored_exact") is True and
         failed.get("official_final_tasks_admitted") == 0,
         "parse_source_prior_gate_or_failure_not_bound")
    return {
        "schema": SCHEMA,
        "status": "source_frozen_before_v5_baseline_gate_or_gui_control",
        "as_of_date": "2026-09-29",
        "supersedes_pre_review_source_freeze_sha256":
            PRE_REVIEW_FREEZE_SHA256,
        "review_correction":
            "all_indexed_guard_samples_and_pre_intent_rejections_audited",
        "prior_db_readiness_source_freeze_sha256": digest(previous.FREEZE),
        "prior_terminal_failure_public_receipt_sha256":
            digest(failure.PUBLIC_PATH),
        "prior_terminal_failure_receipt_sha256":
            failed["failure_receipt_sha256"],
        "prior_no_gui_gate_sha256": failed["preceding_gate_sha256"],
        "original_lease_prefix_sha256":
            failure.ORIGINAL_LEASE_PREFIX_SHA256,
        "new_source_sha256s": {
            relative: digest(ROOT / relative) for relative in SOURCE_FILES},
        "unchanged_current_candidate_private_sha256":
            prior["unchanged_current_candidate_private_sha256"],
        "exact_two_pixel_parse_alternate_only_for_purchase_rfq_click": True,
        "original_physical_dispatch_guard_required": True,
        "same_underlying_task_requires_fresh_run_nonce_and_attempt": True,
        "prior_failed_attempt_immutable_and_no_automatic_replay": True,
        "fresh_independent_no_gui_sql_full_filestore_gate_required": True,
        "source_visual_review_required": True,
        "selection_evaluator_only": True,
        "control_dispatch_authorized": False,
        "campaign_dispatch_authorized": False,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }


def validate(path: Path = FREEZE) -> dict:
    observed = protocol.public_json(path)
    expected = build()
    need(observed == expected,
         "parse_source_freeze_or_prior_evidence_changed")
    return observed


def write() -> dict:
    need(not FREEZE.exists() and not FREEZE.is_symlink(),
         "parse_source_freeze_must_be_new")
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
