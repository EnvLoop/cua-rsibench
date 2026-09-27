"""Fail-closed private/Desktop admission ledger under the current v0.6.5 GUI.

The 100 real native-GUI controls, saved artifacts, profiles and fair scorer are
re-audited. Historical E2B shell actions are NEVER relabeled as current-frame
v0.6.5 actions. This program emits a private per-ID blocked ledger and a public
aggregate; it intentionally emits no qualified cua-final-cell-v0.6 manifest.
"""

from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from cursibench import scale_action_contract, scale_action_output_v065
from cursibench.scale_final_v06 import validate_splits

if __package__:
    from . import admit, official_scorer_freeze, profile_baseline_audit
    from . import qwen_v064_adapter
    from .budget_ledger import audit as budget_audit
    from .source import CATALOG_URL, LICENSE_URL, EXPECTED_SHA256
    from .verify import docx_content, pptx_slide_shapes, xlsx_cells
else:
    import admit, official_scorer_freeze, profile_baseline_audit
    import qwen_v064_adapter
    from budget_ledger import audit as budget_audit
    from source import CATALOG_URL, LICENSE_URL, EXPECTED_SHA256
    from verify import docx_content, pptx_slide_shapes, xlsx_cells


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _artifact_text(raw: bytes, suffix: str) -> str:
    if suffix == ".xlsx":
        cells = xlsx_cells(raw)
        values = [str(value) for sheet in cells.values() for cell in sheet.values()
                  for value in cell.values() if value is not None]
    elif suffix == ".pptx":
        values = [str(value) for slide in pptx_slide_shapes(raw) for value in slide]
    elif suffix == ".docx":
        content = docx_content(raw)
        values = [str(value) for value in content["paragraphs"]]
        values += [str(value) for table in content["tables"]
                   for row in table for value in row]
    else:
        raise ValueError("Unknown final native Office artifact")
    return " ".join(values).lower()


def _app(row: dict) -> str:
    workflow = row["workflow"]
    return ("Calc" if workflow.startswith("calc-") else
            "Impress" if workflow.startswith("impress-") else
            "Writer" if workflow.startswith("writer-") else "unknown")


def _shell_key(keys: list[str]) -> str:
    if keys == ["ctrl", "a"]: return "Control+A"
    if keys == ["ctrl", "s"]: return "Control+S"
    if keys == ["ctrl", "f"]: return "Control+F"
    if keys == ["ctrl", "h"]: return "Control+H"
    if keys == ["ctrl", "end"]: return "Control+End"
    if keys == ["shift", "end"]: return "Shift+End"
    if keys == ["esc"]: return "Escape"
    if keys == ["enter"]: return "Enter"
    if keys == ["home"]: return "Home"
    return "+".join(keys)


def _receipt_action_gap(receipt: dict) -> dict:
    actions = receipt["actor_actions"]
    unsupported = sorted({_shell_key(action["keys"]) for action in actions
                          if action["type"] == "press" and
                          _shell_key(action["keys"]) not in scale_action_contract._ALLOWED_KEYS})
    return {
        "actor_action_count": len(actions),
        "screenshot_count": len(receipt.get("screenshots", {})),
        "double_click_used": any(action["type"] == "double" for action in actions),
        "unsupported_key_chords": unsupported,
        "focus_dependent_write_used": any(action["type"] == "write" for action in actions),
        "every_action_has_a_current_frame": all("frame_id" in action and
                                                "frame_sha256" in action
                                                for action in actions),
        "guest_content_attestation_present": bool(receipt.get("guest_content_sha256")),
    }


def audit(*, candidate_root: Path, attempts_root: Path, work_root: Path,
          private_map: Path, profile_private: Path, profile_public: Path,
          profile_runtime: Path, profile_reconciliation: Path,
          profile_provider_probe: Path, fair_public: Path,
          guest_identity_public: Path, v065_live_public: Path) -> tuple[dict, dict]:
    inventory_raw = (candidate_root / "candidate-inventory.json").read_bytes()
    inventory = json.loads(inventory_raw)
    if (inventory.get("design_revision") != "v2-distinct-structures"
            or inventory.get("source_sha256") != EXPECTED_SHA256):
        raise ValueError("Wrong WDI source or distinct-template inventory")
    task_sets = {name: [] for name in ("train", "selection", "official")}
    for row in inventory["tasks"]:
        split = "official" if row["split"] == "final_candidate" else row["split"]
        task_sets[split].append({key: row[key] for key in (
            "task_id", "package_sha256", "source_groups",
            "template_group", "instance_group")})
    if ({key: len(value) for key, value in task_sets.items()} !=
            {"train": 20, "selection": 20, "official": 100}
            or len(validate_splits(task_sets)) != 100):
        raise ValueError("20/20/100 source/template/instance split changed")
    gui = admit.audit(candidate_root, attempts_root)
    if (gui["qualified_final_count"], gui["missing_receipt_count"],
            gui["invalid_receipt_count"]) != (100, 0, 0):
        raise ValueError("100 historical native GUI trios no longer verify")
    fair_private, fair = official_scorer_freeze.audit(
        candidate_root, attempts_root, private_map)
    published_fair = json.loads(fair_public.read_bytes())
    if (fair["known_positive_passed_fair_scorer"] != 100
            or fair["known_near_miss_rejected_fair_scorer"] != 100
            or fair["fair_scorer_calibration_failures"] != 0
            or fair["scorer_bundle_sha256"] != published_fair["scorer_bundle_sha256"]
            or fair["candidate_inventory_sha256"] != published_fair["candidate_inventory_sha256"]):
        raise ValueError("Published fair scorer no longer matches actual saved controls")
    recomputed_profiles, profile_summary = profile_baseline_audit.audit(
        candidate_root, work_root, profile_runtime, profile_reconciliation,
        profile_provider_probe)
    profile_raw = profile_private.read_bytes()
    published_profile = json.loads(profile_public.read_bytes())
    if (recomputed_profiles != json.loads(profile_raw)
            or profile_summary["task_bound_profile_baselines_qualified"] != 100
            or digest(profile_raw) != published_profile["private_profile_manifest_sha256"]):
        raise ValueError("100 private task-bound profiles no longer match public binding")
    profiles = {row["private_task_id"]: row for row in recomputed_profiles["accepted"]}
    guest = json.loads(guest_identity_public.read_bytes())
    if (guest.get("schema") != "cua-native-wdi-guest-content-identity-public-v1"
            or guest.get("scoped_guest_content_identity_passed") is not True
            or guest.get("official_desktop_final_admissions") != 0):
        raise ValueError("Scoped guest-content identity is not a valid candidate")
    final = [row for row in inventory["tasks"] if row["split"] == "final_candidate"]
    normalized_impress = [row for row in final if row["workflow"] == "impress-deck"
                          and "normalization" in row]
    if len(normalized_impress) != 25:
        raise ValueError("Final Impress neutral normalization coverage changed")
    live_raw = v065_live_public.read_bytes()
    live = json.loads(live_raw)
    if (live.get("schema") != "cua-native-wdi-qwen-v065-nonfinal-live-public-v1"
            or live.get("official_hidden_final_model_attempts") != 0
            or live.get("latest_output_adapter_sha256") !=
                digest(Path(scale_action_output_v065.__file__).read_bytes())
            or live.get("latest_native_desktop_adapter_sha256") !=
                digest(Path(qwen_v064_adapter.__file__).read_bytes())
            or live.get("latest_attempt_applied_gui_actions") != 2):
        raise ValueError("Shared v0.6.5 train-only Desktop boundary changed")
    admitted_gui = {row["task_id"]: row for row in gui["admitted"]}
    fair_rows = {row["task_id"]: row for row in fair_private["tasks"]}
    details = []
    for row in final:
        task_id = row["task_id"]
        package_dir, baseline, _ = admit._package(candidate_root, row)
        files = [*package_dir.glob("*.xlsx"), *package_dir.glob("*.pptx"),
                 *package_dir.glob("*.docx")]
        text = _artifact_text(baseline, files[0].suffix)
        attribution = all(phrase in text for phrase in (
            "world bank", "cc by 4.0", "envloop"))
        polarity = {}
        missing_provider_info = 0
        matching_observed_template = True
        for attempt in ("positive", "near-miss"):
            receipt = json.loads((attempts_root / task_id / attempt / "receipt.json").read_bytes())
            polarity[attempt] = _receipt_action_gap(receipt)
            info = receipt.get("provider_sandbox_info")
            if info is None:
                missing_provider_info += 1
                continue
            matching_observed_template = matching_observed_template and (
                info.get("template_id") == guest["provider_template_id"]
                and info.get("envd_version") == guest["provider_envd_version"]
                and info.get("vcpu") == guest["provider_shape"]["vcpu"]
                and info.get("memory_mb") == guest["provider_shape"]["memory_mb"])
        cold = json.loads((attempts_root / task_id / "cold-reset" / "receipt.json").read_bytes())
        cold_guest_attestation_present = bool(cold.get("guest_content_sha256"))
        cold_info = cold.get("provider_sandbox_info")
        if cold_info is None:
            missing_provider_info += 1
        else:
            matching_observed_template = matching_observed_template and (
                cold_info.get("template_id") == guest["provider_template_id"]
                and cold_info.get("envd_version") == guest["provider_envd_version"]
                and cold_info.get("vcpu") == guest["provider_shape"]["vcpu"]
                and cold_info.get("memory_mb") == guest["provider_shape"]["memory_mb"])
        if not matching_observed_template:
            raise ValueError("Historical final GUI controls changed provider template/shape")
        reasons = []
        if not attribution: reasons.append("source_attribution_missing")
        if any(gap["double_click_used"] or gap["unsupported_key_chords"]
               for gap in polarity.values()):
            reasons.append("historical_actor_uses_action_outside_v065")
        if any(gap["focus_dependent_write_used"] for gap in polarity.values()):
            reasons.append("historical_write_lacks_v065_target")
        if any(not gap["every_action_has_a_current_frame"] for gap in polarity.values()):
            reasons.append("historical_actions_lack_per_step_current_frame")
        if (any(not gap["guest_content_attestation_present"] for gap in polarity.values())
                or not cold_guest_attestation_present):
            reasons.append("historical_gui_sandboxes_lack_scoped_guest_attestation")
        if missing_provider_info:
            reasons.append("historical_provider_identity_fields_missing")
        details.append({
            "private_task_id": task_id, "application": _app(row),
            "package_sha256": row["package_sha256"],
            "source_groups": row["source_groups"],
            "template_group": row["template_group"],
            "source_attribution_in_input": attribution,
            "historical_provider_template_shape_matched_where_recorded": matching_observed_template,
            "historical_provider_identity_receipts_present": 3 - missing_provider_info,
            "gui_control_receipt_sha256s": admitted_gui[task_id]["attempt_receipt_sha256"],
            "fair_scorer_positive_passed": fair_rows[task_id]["positive_fair_score"] == 1,
            "fair_scorer_near_miss_rejected": fair_rows[task_id]["near_miss_fair_score"] == 0,
            "profile_baseline_receipt_sha256": profiles[task_id]["receipt_sha256"],
            "profile_canonical_sha256": profiles[task_id]["canonical_profile_sha256"],
            "historical_actor": polarity, "v065_admission_blockers": reasons,
            "historical_cold_reset_guest_attestation_present": cold_guest_attestation_present,
            "qualified_under_current_v065": not reasons,
        })
    if any(row["application"] == "unknown" for row in details):
        raise ValueError("Unknown native application workflow")
    if any(row["qualified_under_current_v065"] for row in details):
        raise ValueError("Historical controls were silently promoted to v0.6.5")
    budget = budget_audit(work_root, proposed_new_sandboxes=0,
                          proposed_lease_seconds=300,
                          max_lane_reserved_usd=Decimal("40"))
    if not budget["within_cap"]:
        raise ValueError("Native calibration lane reservation exceeded cap")
    bundle = {
        "schema": "cua-native-wdi-v065-final-admission-private-preflight-v1",
        "status": "blocked_before_cua_final_cell_v0.6_manifest",
        "candidate_inventory_sha256": digest(inventory_raw),
        "source_snapshot_sha256": EXPECTED_SHA256,
        "source_catalog_url": CATALOG_URL,
        "source_license_url": LICENSE_URL,
        "source_license": "CC BY 4.0",
        "task_sets_matching_cua_final_cell_v0.6_identity_shape": task_sets,
        "gui_admission_audit_sha256": digest(json.dumps(gui, sort_keys=True).encode()),
        "fair_scorer_bundle_sha256": fair["scorer_bundle_sha256"],
        "private_profile_manifest_sha256": digest(profile_raw),
        "scoped_guest_content_public_sha256": digest(guest_identity_public.read_bytes()),
        "v065_train_only_live_public_sha256": digest(live_raw),
        "v065_model_output_source_sha256": digest(Path(scale_action_output_v065.__file__).read_bytes()),
        "shared_full_action_validator_sha256": digest(Path(scale_action_contract.__file__).read_bytes()),
        "task_rows": details,
        "official_final_admitted_count": 0,
        "official_model_result_count": 0,
    }
    counts = Counter(reason for row in details for reason in row["v065_admission_blockers"])
    public = {
        "schema": "cua-native-wdi-v065-final-admission-preflight-public-v1",
        "checked_date": "2026-09-27",
        "candidate_inventory_sha256": digest(inventory_raw),
        "candidate_counts": {"train": 20, "selection": 20, "final_candidate": 100},
        "shared_v06_split_validator_passed": True,
        "held_out_source_family_count": len({tuple(row["source_groups"]) for row in final}),
        "application_counts": dict(sorted(Counter(row["application"] for row in details).items())),
        "historical_gui_trios_passed": gui["qualified_final_count"],
        "historical_gui_receipts_with_provider_identity": sum(
            row["historical_provider_identity_receipts_present"] for row in details),
        "historical_gui_receipts_missing_provider_identity": sum(
            3 - row["historical_provider_identity_receipts_present"] for row in details),
        "historical_gui_trios_with_complete_provider_identity": sum(
            row["historical_provider_identity_receipts_present"] == 3 for row in details),
        "neutral_normalized_final_impress_inputs": len(normalized_impress),
        "fair_positive_controls_passed": fair["known_positive_passed_fair_scorer"],
        "fair_near_misses_rejected": fair["known_near_miss_rejected_fair_scorer"],
        "task_bound_profiles_qualified": profile_summary["task_bound_profile_baselines_qualified"],
        "inputs_with_world_bank_ccby_and_derived_attribution": sum(
            row["source_attribution_in_input"] for row in details),
        "source_catalog_url": CATALOG_URL, "source_license_url": LICENSE_URL,
        "source_license": "CC BY 4.0",
        "historical_action_gap_task_counts": dict(sorted(counts.items())),
        "positive_double_click_task_count": sum(row["historical_actor"]["positive"]["double_click_used"]
                                                for row in details),
        "positive_unsupported_key_task_count": sum(bool(row["historical_actor"]["positive"]["unsupported_key_chords"])
                                                    for row in details),
        "historical_positive_unsupported_key_chords": dict(sorted(Counter(
            key for row in details for key in row["historical_actor"]["positive"]["unsupported_key_chords"]
        ).items())),
        "task_count_with_per_action_current_frame_proof": sum(
            all(gap["every_action_has_a_current_frame"] for gap in row["historical_actor"].values())
            for row in details),
        "task_count_with_per_gui_sandbox_scoped_guest_attestation": sum(
            all(gap["guest_content_attestation_present"] for gap in row["historical_actor"].values())
            and row["historical_cold_reset_guest_attestation_present"]
            for row in details),
        "historical_gui_receipts_with_scoped_guest_attestation": sum(
            sum(gap["guest_content_attestation_present"] for gap in row["historical_actor"].values())
            + row["historical_cold_reset_guest_attestation_present"]
            for row in details),
        "qualified_under_current_v065": 0,
        "official_full_study_admitted_final_count": 0,
        "official_model_result_count": 0,
        "status": "blocked_action_and_runtime_parity_not_frozen",
        "scorer_bundle_sha256": fair["scorer_bundle_sha256"],
        "profile_private_manifest_sha256": digest(profile_raw),
        "guest_content_public_sha256": digest(guest_identity_public.read_bytes()),
        "v065_train_only_live_public_sha256": digest(live_raw),
        "v065_model_output_source_sha256": bundle["v065_model_output_source_sha256"],
        "native_lane_full_lease_reserve_usd": budget["past_conservative_reserved_usd"],
        "native_lane_cap_usd": budget["lane_usd_cap"],
        "actual_provider_billed_usd": None,
    }
    return bundle, public


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate-root", "attempts-root", "work-root", "private-map",
                 "profile-private", "profile-public", "profile-runtime",
                 "profile-reconciliation", "profile-provider-probe", "fair-public",
                 "guest-identity-public", "v065-live-public", "private-out", "public-out"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.private_out.exists() or args.public_out.exists():
        raise ValueError("Refusing to overwrite admission preflight evidence")
    private, public = audit(
        candidate_root=args.candidate_root, attempts_root=args.attempts_root,
        work_root=args.work_root, private_map=args.private_map,
        profile_private=args.profile_private, profile_public=args.profile_public,
        profile_runtime=args.profile_runtime,
        profile_reconciliation=args.profile_reconciliation,
        profile_provider_probe=args.profile_provider_probe,
        fair_public=args.fair_public,
        guest_identity_public=args.guest_identity_public,
        v065_live_public=args.v065_live_public)
    args.private_out.parent.mkdir(parents=True, exist_ok=True)
    args.public_out.parent.mkdir(parents=True, exist_ok=True)
    args.private_out.write_text(json.dumps(private, indent=2, sort_keys=True) + "\n")
    args.private_out.chmod(0o600)
    public["private_admission_preflight_sha256"] = digest(args.private_out.read_bytes())
    args.public_out.write_text(json.dumps(public, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: public[key] for key in (
        "historical_gui_trios_passed", "fair_positive_controls_passed",
        "task_bound_profiles_qualified", "qualified_under_current_v065",
        "status")}, sort_keys=True))


if __name__ == "__main__":
    main()
