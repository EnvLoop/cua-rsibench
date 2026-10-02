"""Offline preparation and one-use review for a whole new 100/20 Desktop epoch.

All old controls and money/intent ceilings remain historical. This source
requires 120 new control trios, uncapped spending authorization, complete
full-lease accounting and one fresh reviewed per-ID intent. No model is called.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import importlib.metadata
import json
from pathlib import Path
import secrets

from . import factory as base
from . import v066_post_enter_source_audit_v9 as source_audit
from . import v066_post_enter_near_negative_v7 as accounting
from . import v066_scoped_profile_runtime_freeze as old_runtime
from .v066_scoped_profile_reference import validate_reference
from .v066_final_freeze import validate_ratification
from .v066_post_enter_train_calibration_v1 import SDK_VERSIONS

ROOT=Path(__file__).resolve().parents[1]
SCHEMA="cua-native-wdi-post-enter-cohort-source-private-v9"
PUBLIC_SCHEMA="cua-native-wdi-post-enter-cohort-source-public-v9"
PERMIT_SCHEMA="cua-native-wdi-post-enter-cohort-one-id-permit-private-v9"
MAX_ACTIONS=90
ACTOR_WALL_SECONDS=720
LEASE_SECONDS=1200
SOURCE_FILES=tuple(dict.fromkeys((*old_runtime.SOURCE_FILES,
    "native_desktop_factory/qwen_v066_adapter_v4_strict.py",
    "native_desktop_factory/qwen_v066_adapter_v4.py",
    "native_desktop_factory/qwen_v064_adapter.py",
    "native_desktop_factory/v066_day_rollover_attrition_audit_v4.py",
    "native_desktop_factory/v066_post_enter_source_audit_v9.py",
    "native_desktop_factory/official_scorer_freeze.py",
    "native_desktop_factory/formula_semantics.py",
    "native_desktop_factory/target_text_semantics.py",
    "src/cursibench/scale_action_contract.py",
    "src/cursibench/scale_action_output_v065.py",
    "src/cursibench/scale_action_output_v064.py",
    "native_desktop_factory/post_enter_train_probe_v1.py",
    "native_desktop_factory/post_enter_control_proxy_v9.py",
    "native_desktop_factory/v066_post_enter_source_intake_v9.py",
    "native_desktop_factory/v066_post_enter_source_audit_v9.py",
    "native_desktop_factory/v066_post_enter_epoch_v9.py",
    "native_desktop_factory/v066_post_enter_control_attempt_v9.py",
    "native_desktop_factory/v066_post_enter_control_audit_v9.py",
    "native_desktop_factory/v066_post_enter_near_negative_v7.py",
    "native_desktop_factory/v066_post_enter_train_calibration_v1.py",
    "native_desktop_factory/train_transfer_analogues.py",
    "native_desktop_factory/factory_v2.py",
    "tools/extract_wdi_country_csv_reserve_v1.py",
    "tools/capture_ppt_wdi_transfer_expansion_20260929.py",
    "tools/build_ppt_wdi_reserve_replacement_v1.py",
    "docs/NATIVE_DESKTOP_POST_ENTER_COHORT_EPOCH_V9_2026-09-30.md")))


def require(ok,reason):
    if not ok:raise ValueError(reason)


def private(path):return accounting._private(path)


def source_hashes():return {name:base.digest((ROOT/name).read_bytes()) for name in SOURCE_FILES}


def checked_train(v6:Path,v8:Path):
    a=json.loads(v6.read_bytes());b=json.loads(v8.read_bytes())
    require(a.get("status")=="three_public_train_guests_saved_state_and_reset_audited" and
            a.get("positive_saved_workflows")==2 and a.get("post_enter_raw_frames")==10 and
            a.get("calc_cold_reset_original_bytes_verified") is True and a.get("provider_active_after")==0,
            "v9_train_positive_or_timing_evidence_missing")
    require(b.get("status") in ("remaining_train_resets_audited_material_oscillation_inconclusive","remaining_train_controls_and_material_oscillation_audited") and
            b.get("combined_distinct_guests")==6 and b.get("saved_wrong_target_score_zero")==1 and
            b.get("separate_visual_modal_adjudications")==1 and b.get("combined_original_byte_resets")==3 and
            b.get("provider_active_after")==0 and b.get("unresolved_writes")==0 and
            b.get("same_intent_replay_authorized") is False and b.get("official_final_admissions")==b.get("official_model_results")==0,
            "v9_train_wrong_target_modal_reset_evidence_missing")
    # A source-independent refusal unit control does not manufacture empirical
    # material oscillation. Its absent observation is preserved, not a gate
    # demanding another paid TRAIN diagnostic.
    return {"v6_public_sha256":base.digest(v6.read_bytes()),"v8_public_sha256":base.digest(v8.read_bytes()),
            "material_oscillation_proven":b.get("material_oscillation_proven"),
            "no_action_probe_classifications":b.get("no_action_probe_classifications")}


def prepare(*,intake_root:Path,source_public:Path,v6_public:Path,v8_public:Path,
            guest_public:Path,scoped_reference:Path,ratification:Path,accounting_roots:list[Path],
            attempts_root:Path,freeze_path:Path,public_path:Path):
    require(not any(p.exists() or p.is_symlink() for p in (attempts_root,freeze_path,public_path)),
            "v9_fresh_epoch_paths_required")
    source=source_audit.audit(intake_root)
    require(source==json.loads(source_public.read_bytes()),"v9_source_public_audit_does_not_replay")
    training=checked_train(v6_public,v8_public)
    validate_reference(scoped_reference);validate_ratification(ratification)
    intake=json.loads(private(intake_root/"intake-receipt.private.json"))
    cohort=Path(intake["cohort_root"])
    inventory=json.loads(private(cohort/"candidate-inventory.json"))
    roster=sorted([r for r in inventory["tasks"] if r["split"]=="selection"],key=lambda r:r["task_id"])+\
           sorted([r for r in inventory["tasks"] if r["split"]=="final_candidate"],key=lambda r:r["task_id"])
    require(len(roster)==120,"v9_full_new_selection_final_roster_required")
    bindings={str(p.resolve()):base.digest(p.read_bytes()) for p in
              (source_public,v6_public,v8_public,guest_public,scoped_reference,ratification,intake_root/"intake-receipt.private.json",intake_root/"private-map.private.json",cohort/"candidate-inventory.json")}
    ledger=accounting.lease_accounting(accounting_roots,exclude=attempts_root)
    value={"schema":SCHEMA,"status":"source_frozen_before_any_new_control_or_model",
           "created_utc":datetime.now(timezone.utc).isoformat(),"nonce":secrets.token_hex(32),
           "public_path":str(public_path.resolve()),"intake_root":str(intake_root.resolve()),
           "candidate_root":str(cohort.resolve()),"private_map":str((intake_root/"private-map.private.json").resolve()),
           "attempts_root":str(attempts_root.resolve()),"guest_public":str(guest_public.resolve()),
           "scoped_reference":str(scoped_reference.resolve()),"ratification":str(ratification.resolve()),
           "source_public":str(source_public.resolve()),"v6_public":str(v6_public.resolve()),"v8_public":str(v8_public.resolve()),
           "bindings":bindings,"source_sha256s":source_hashes(),"training_evidence":training,
           "accounting_roots":[str(p.resolve()) for p in accounting_roots],"historical_full_lease_accounting":ledger,
           "roster":[{k:r[k] for k in ("task_id","split","workflow","package_sha256","input_sha256","source_groups","template_group")} for r in roster],
           "cohort_counts":{"train":20,"selection":20,"final_candidate":100},
           "source_family_counts":{"train":5,"selection":5,"final_candidate":25},
           "maximum_new_full_lease_intents":360,"lease_seconds_each":LEASE_SECONDS,
           "new_full_lease_seconds":360*LEASE_SECONDS,"new_planning_usd_upper":"120",
           "lane_spending_cap_usd":None,"spending_authorized_by_user":True,
           "max_actor_actions":MAX_ACTIONS,"max_actor_wall_seconds":ACTOR_WALL_SECONDS,
           "same_profile_for_base_and_selected":True,"historical_controls_carried_into_new_epoch":0,
           "same_intent_replay_authorized":False,"dispatch_authorized":False,
           "official_final_admissions":0,"official_model_results":0}
    accounting._write_new(freeze_path,value)
    public={"schema":PUBLIC_SCHEMA,"status":"whole_family_replaced_new_120_trio_source_frozen_no_dispatch",
            "private_freeze_sha256":base.digest(private(freeze_path)),"source_sha256s":value["source_sha256s"],
            "source_audit_sha256":bindings[str(source_public.resolve())],"training_evidence":training,
            "cohort_counts":value["cohort_counts"],"source_family_counts":value["source_family_counts"],
            "whole_retired_families":1,"retired_tasks":4,"replacement_tasks":4,"retained_packages_byte_identical":136,
            "new_selection_control_trios_required":20,"new_final_control_trios_required":100,
            "historical_controls_carried_into_new_epoch":0,"maximum_new_full_lease_intents":360,
            "lease_seconds_each":LEASE_SECONDS,"new_full_lease_seconds":360*LEASE_SECONDS,
            "new_planning_usd_upper":"120","lane_spending_cap_usd":None,"actual_provider_billed_usd":None,
            "max_actor_actions":MAX_ACTIONS,"max_actor_wall_seconds":ACTOR_WALL_SECONDS,
            "same_profile_for_base_and_selected":True,"same_intent_replay_authorized":False,
            "dispatch_authorized":False,"official_final_admissions":0,"official_model_results":0}
    accounting._write_new(public_path,public,public=True);return public


def validate(freeze_path:Path):
    raw=private(freeze_path);value=json.loads(raw)
    require(value.get("schema")==SCHEMA and value.get("status")=="source_frozen_before_any_new_control_or_model" and
            value.get("source_sha256s")==source_hashes() and value.get("maximum_new_full_lease_intents")==360 and
            value.get("lease_seconds_each")==LEASE_SECONDS and value.get("max_actor_wall_seconds")==ACTOR_WALL_SECONDS and
            value.get("max_actor_actions")==MAX_ACTIONS and value.get("lane_spending_cap_usd") is None and
            value.get("same_intent_replay_authorized") is value.get("dispatch_authorized") is False and
            value.get("official_final_admissions")==value.get("official_model_results")==0,
            "v9_source_or_budget_protocol_changed")
    for path,sha in value["bindings"].items():require(base.digest(Path(path).read_bytes())==sha,"v9_frozen_input_binding_changed")
    require(checked_train(Path(value["v6_public"]),Path(value["v8_public"]))==value["training_evidence"],"v9_train_evidence_changed")
    source=source_audit.audit(Path(value["intake_root"]))
    require(source==json.loads(Path(value["source_public"]).read_bytes()),"v9_real_source_replay_changed")
    public=json.loads(Path(value["public_path"]).read_bytes())
    require(public.get("schema")==PUBLIC_SCHEMA and public.get("private_freeze_sha256")==base.digest(raw) and
            public.get("source_sha256s")==value["source_sha256s"] and public.get("dispatch_authorized") is False,
            "v9_public_freeze_changed")
    validate_reference(Path(value["scoped_reference"]));validate_ratification(Path(value["ratification"]))
    require(accounting.lease_accounting([Path(p) for p in value["accounting_roots"]],exclude=Path(value["attempts_root"]))==value["historical_full_lease_accounting"],
            "v9_historical_full_lease_metadata_changed")
    return {**value,"_freeze_sha256":base.digest(raw)}


def next_row(value):
    root=Path(value["attempts_root"])
    for row in value["roster"]:
        directory=root/row["task_id"]
        if not directory.exists():return row
        from .v066_post_enter_control_audit_v9 import audit_trio
        audit_trio(value=value,row=row)
    return None


def review(*,freeze_path:Path,permit_path:Path):
    from .reconcile_interrupted_sweep import active_hashes
    value=validate(freeze_path);row=next_row(value)
    require(row is not None,"v9_all_120_controls_already_consumed")
    active,count=active_hashes();require(not active and count==0,"v9_root_review_requires_active_zero")
    permit={"schema":PERMIT_SCHEMA,"created_utc":datetime.now(timezone.utc).isoformat(),
            "freeze_sha256":base.digest(private(freeze_path)),"source_sha256s":value["source_sha256s"],
            "task_id":row["task_id"],"package_sha256":row["package_sha256"],"split":row["split"],
            "attempts":["positive","near-miss","cold-reset"],"maximum_new_intents":3,
            "provider_active_zero_at_review":True,"same_intent_replay_authorized":False,
            "official_final_admissions":0,"official_model_results":0}
    accounting._write_new(permit_path,permit);return {"status":"one_new_control_trio_reviewed_no_create","official_final_admissions":0}


def checked_permit(freeze_path,permit_path,value,row):
    p=json.loads(private(permit_path))
    require(p.get("schema")==PERMIT_SCHEMA and p.get("freeze_sha256")==base.digest(private(freeze_path)) and
            p.get("source_sha256s")==value["source_sha256s"] and p.get("task_id")==row["task_id"] and
            p.get("package_sha256")==row["package_sha256"] and p.get("split")==row["split"] and
            p.get("attempts")==["positive","near-miss","cold-reset"] and p.get("maximum_new_intents")==3 and
            p.get("provider_active_zero_at_review") is True and p.get("same_intent_replay_authorized") is False,
            "v9_exact_one_trio_permit_missing_or_changed")
    return p


def checked_inflight(value,row,attempt):
    """Only the first unfinished roster row and ordered fresh guest may create."""
    from .v066_post_enter_control_audit_v9 import audit_trio,audit_attempt
    root=Path(value["attempts_root"]);position=value["roster"].index(row)
    for earlier in value["roster"][:position]:audit_trio(value=value,row=earlier)
    require(not any((root/later["task_id"]).exists() for later in value["roster"][position+1:]),
            "v9_future_row_consumed_or_roster_skip")
    task=root/row["task_id"];started=json.loads(private(task/"trio-started.json"))
    require(started.get("source_freeze_sha256")==value["_freeze_sha256"] and started.get("task_id")==row["task_id"] and
            started.get("same_intent_replay_authorized") is False,"v9_trio_consumption_marker_changed")
    phases=["positive","near-miss","cold-reset"];index=phases.index(attempt)
    for earlier in phases[:index]:audit_attempt(value=value,row=row,attempt=earlier)
    require(not any((task/later).exists() for later in phases[index+1:]),"v9_attempt_order_or_replay_invalid")


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("mode",choices=("prepare","plan","review"))
    p.add_argument("--freeze",type=Path,required=True);p.add_argument("--permit",type=Path)
    for key in ("intake-root","source-public","v6-public","v8-public","guest-public","scoped-reference","ratification","attempts-root","public"):
        p.add_argument("--"+key,type=Path)
    p.add_argument("--accounting-root",type=Path,action="append");a=p.parse_args()
    if a.mode=="prepare":
        value=prepare(intake_root=a.intake_root,source_public=a.source_public,v6_public=a.v6_public,v8_public=a.v8_public,
                      guest_public=a.guest_public,scoped_reference=a.scoped_reference,ratification=a.ratification,
                      accounting_roots=a.accounting_root,attempts_root=a.attempts_root,freeze_path=a.freeze,public_path=a.public)
    elif a.mode=="review":value=review(freeze_path=a.freeze,permit_path=a.permit)
    else:
        frozen=validate(a.freeze);row=next_row(frozen);value={"status":"all_120_trios_complete" if row is None else "next_new_trio_metadata_only",
            "next_package_sha256":None if row is None else row["package_sha256"],"next_split":None if row is None else row["split"],
            "new_sandboxes_created":0,"official_final_admissions":0}
    print(json.dumps(value,sort_keys=True))


if __name__=="__main__":main()
