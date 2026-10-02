"""Public source freeze for the additive Odoo v6 two-frame dispatch epoch."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from tools import audit_odoo_v066_parse_border_dispatch_failure_20260929 as failure
from tools import odoo_v066_parse_border_source_v5 as previous
from tools import odoo_v066_scale_protocol_v1 as protocol


ROOT = protocol.ROOT
FREEZE = (ROOT / "docs/evidence" /
          "odoo-v066-two-frame-v6-source-freeze-2026-09-29.json")
SCHEMA = "envloop-odoo-v066-two-frame-dispatch-source-freeze-v6"
SOURCE_FILES = (
    "enterprise_fallback/odoo18/odoo_v066_two_frame_dispatch_adapter_v6.py",
    "tools/audit_odoo_v066_two_frame_dispatch_v6.py",
    "tools/odoo_v066_current_candidate_case_v6.py",
    "tools/audit_odoo_v066_two_frame_case_v6.py",
    "tools/odoo_v066_two_frame_plan_v6.py",
    "tools/odoo_v066_two_frame_no_gui_gate_v6.py",
    "tools/audit_odoo_v066_two_frame_no_gui_gate_v6.py",
    "tools/odoo_v066_two_frame_one_selection_v6.py",
    "tools/odoo_v066_two_frame_source_v6.py",
    "tests/test_odoo_v066_two_frame_dispatch_adapter_v6.py",
    "tests/test_odoo_v066_two_frame_dispatch_audit_v6.py",
    "tests/test_odoo_v066_two_frame_plan_v6.py",
    "tests/test_odoo_v066_two_frame_gate_v6.py",
)


class TwoFrameSourceError(ValueError):
    pass


def need(ok: bool, code: str) -> None:
    if not ok:
        raise TwoFrameSourceError(code)


def digest(path: Path) -> str:
    need(path.is_file() and not path.is_symlink(),
         "two_frame_source_file_missing_or_symlink")
    return sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    prior = previous.validate()
    incident = protocol.public_json(failure.PUBLIC_AUDIT)
    need(prior["official_final_tasks_admitted"] == 0 and
         incident.get("status") ==
         "original_v5_dispatch_frame_failure_independently_verified_no_replay" and
         incident.get("source_freeze_sha256") == digest(previous.FREEZE) and
         incident.get("final_physical_classification") ==
         "exact_observed_return_after_six_identical_two_pixel_alternates" and
         incident.get("frozen_final_sample_label") ==
         "third_or_material_frame_rejected" and
         incident.get("third_physical_image_observed") is False and
         incident.get("failed_action_click_dispatched") is False and
         incident.get("baseline_sql_and_full_filestore_restored_exact") is True and
         incident.get("official_final_tasks_admitted") == 0 and
         incident.get("model_attempts") == 0,
         "two_frame_source_prior_failure_or_boundary_unbound")
    return {
        "schema": SCHEMA,
        "status": "source_frozen_before_private_epoch_or_v6_gui_control",
        "as_of_date": "2026-09-29",
        "prior_v5_source_freeze_sha256": digest(previous.FREEZE),
        "prior_v5_terminal_failure_public_audit_sha256":
            digest(failure.PUBLIC_AUDIT),
        "prior_v5_failure_receipt_sha256":
            incident["failure_receipt_sha256"],
        "prior_v5_no_gui_gate_sha256":
            incident["prior_no_gui_gate_sha256"],
        "new_source_sha256s": {
            relative: digest(ROOT / relative) for relative in SOURCE_FILES},
        "full_png_membership":
            "exact_observed_or_one_proven_two_pixel_alternate_only",
        "two_identical_final_full_png_reads_required": True,
        "unchanged_task_frame_url_and_target_control_required": True,
        "all_indexed_guard_samples_independently_reopened": True,
        "third_or_material_frame_rejected": True,
        "prior_v4_v5_attempts_and_source_freezes_immutable": True,
        "fresh_candidate_nonce_and_no_automatic_replay_required": True,
        "selection_evaluator_only": True,
        "control_dispatch_authorized": False,
        "campaign_dispatch_authorized": False,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }


def validate(path: Path = FREEZE) -> dict:
    recorded = protocol.public_json(path)
    expected = build()
    need(recorded == expected,
         "two_frame_source_freeze_or_prior_evidence_changed")
    return recorded


def write() -> dict:
    need(not FREEZE.exists() and not FREEZE.is_symlink(),
         "two_frame_source_freeze_must_be_new")
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
