"""Read-only audit of new prospective control frames, saved OOXML and reset."""
from __future__ import annotations
import argparse
import json
from datetime import date
from pathlib import Path
from . import admit,factory as base,v066_profile_scope_analysis as scope
from . import qwen_v066_adapter_v4_strict as strict
from . import v066_day_rollover_attrition_audit_v4 as caret_audit
from .v066_scoped_profile_reference import validate_reference,workflow_kind
from .v066_final_control_audit import _bound_file
from .official_saved_verifier import verify_official
from .calibrate_sweep import actor_script
from .v066_control_plan import compile_script
from .post_enter_train_probe_v1 import SAMPLE_DELAYS_MS,MAX_PROBE_WALL_MS
from .qwen_v064_adapter import application_frame_digest
from . import v066_post_enter_epoch_v9 as epoch


def post_enter_samples(root:Path,out:Path,actions:list[dict],receipt:dict):
    expected=[i for i,a in enumerate(actions) if a.get("type")=="key" and a.get("key") in ("Enter","Return")]
    if receipt["profile_application_kind"]!="calc":expected=[]
    path=out/"post-enter-samples.ndjson"
    rows=[json.loads(x) for x in epoch.private(path).splitlines()] if path.exists() else []
    epoch.require(len(rows)==len(expected)*5 and receipt.get("post_enter_windows",0)==len(expected),"v9_enter_window_count_missing")
    for ordinal,step in enumerate(expected):
        group=rows[ordinal*5:(ordinal+1)*5];app=[];windows=[]
        epoch.require([r.get("sample") for r in group]==list(range(5)) and
                      [r.get("requested_delay_ms_before_sample") for r in group]==list(SAMPLE_DELAYS_MS),"v9_enter_sample_order_changed")
        for r in group:
            raw=_bound_file(root,r["frame"])
            epoch.require(r.get("schema")=="cua-native-wdi-post-enter-control-sample-v9" and
                          r.get("enter_ordinal")==ordinal and r.get("preceding_actor_step")==step and
                          r.get("full_frame_sha256")==base.digest(raw) and
                          r.get("application_frame_sha256")==application_frame_digest(raw) and
                          r.get("document_window_stable") is True and
                          r.get("window_id_before_sha256")==r.get("window_id_after_sha256") and
                          r.get("window_title_before_sha256")==r.get("window_title_after_sha256") and
                          type(r.get("monotonic_before_ns")) is type(r.get("monotonic_after_ns")) is int and
                          r["monotonic_before_ns"]<=r["monotonic_after_ns"] and
                          0<=r.get("elapsed_since_enter_ns",-1)<=MAX_PROBE_WALL_MS*1_000_000,
                          "v9_enter_raw_frame_time_or_window_changed")
            app.append(r["application_frame_sha256"]);windows.append(r["window_id_after_sha256"])
        transitions=[]
        for sha in app:
            if not transitions or sha!=transitions[-1]:transitions.append(sha)
        epoch.require(app[-1]==app[-2] and len(transitions)<=2 and len(transitions)==len(set(transitions)) and
                      len(set(windows))==1 and group[-1]["elapsed_since_enter_ns"]>=1_000_000_000 and
                      all(group[i+1]["monotonic_before_ns"]>=group[i]["monotonic_after_ns"] for i in range(4)),
                      "v9_enter_oscillation_or_time_reordering")
        # The next GUI action must have a new observed frame, never the stale
        # proposal on the pre-Enter observation. Steps remain strict contiguous.
        if step+1<len(receipt["actor_steps"]):
            epoch.require(receipt["actor_steps"][step+1]["frame_id_sha256"]!=receipt["actor_steps"][step]["frame_id_sha256"],
                          "v9_actor_reused_pre_enter_frame_identity")
    return len(expected)


def audit_attempt(*,value:dict,row:dict,attempt:str):
    from . import v066_post_enter_control_attempt_v9 as worker
    inventory=json.loads(epoch.private(Path(value["candidate_root"])/"candidate-inventory.json"))
    matches=[full for full in inventory["tasks"] if full.get("task_id")==row["task_id"]]
    epoch.require(len(matches)==1 and all(matches[0].get(k)==v for k,v in row.items()),"v9_frozen_roster_full_metadata_mismatch")
    row=matches[0]
    root=Path(value["attempts_root"]);out=root/row["task_id"]/attempt
    intent_raw=epoch.private(out/"intent.json");intent=json.loads(intent_raw)
    started=json.loads(epoch.private(out/"child-started.json"));receipt_raw=epoch.private(out/"receipt.json");receipt=json.loads(receipt_raw)
    package,baseline,oracle=admit._package(Path(value["candidate_root"]),row)
    expected_status="cold_reset_observed" if attempt=="cold-reset" else "control_passed"
    epoch.require(intent.get("schema")=="cua-native-wdi-post-enter-control-intent-v9" and
                  intent.get("task_id")==row["task_id"] and intent.get("attempt")==attempt and
                  intent.get("source_freeze_sha256")==value["_freeze_sha256"] and
                  intent.get("package_sha256")==row["package_sha256"] and intent.get("lease_seconds")==epoch.LEASE_SECONDS and
                  started.get("intent_sha256")==base.digest(intent_raw) and started.get("source_freeze_sha256")==value["_freeze_sha256"] and
                  receipt.get("schema")=="cua-native-wdi-post-enter-control-attempt-v9" and receipt.get("status")==expected_status and
                  receipt.get("source_freeze_sha256")==value["_freeze_sha256"] and
                  receipt.get("package_sha256")==row["package_sha256"] and receipt.get("input_sha256")==base.digest(baseline) and
                  receipt.get("runner_sha256")==base.digest(Path(worker.__file__).read_bytes()) and
                  receipt.get("native_adapter_sha256")==base.digest(Path(strict.__file__).read_bytes()) and
                  receipt.get("kill_returned") is True and receipt.get("is_running_after_kill") is False and
                  receipt.get("guest_content_attested") is True and receipt.get("fresh_profile_absent") is True and
                  receipt.get("sandbox_timeout_seconds")==epoch.LEASE_SECONDS and
                  receipt.get("official_hidden_final_model_attempts")==receipt.get("official_final_admissions")==0,
                  "v9_attempt_source_runtime_or_teardown_invalid")
    reference,_sha=validate_reference(Path(value["scoped_reference"]));kind=workflow_kind(row["workflow"])
    epoch.require(receipt.get("profile_application_kind")==kind and receipt.get("profile_reference_private_sha256")==_sha and
                  receipt.get("task_profile_scoped_attested") is True and receipt.get("task_profile_scoped_self_stable") is True and
                  receipt.get("task_profile_scoped_matches_public_train") is True and
                  receipt.get("task_profile_scoped_sha256")==reference["applications"][kind] and
                  len(receipt.get("task_profile_scoped_snapshots",[]))==2,"v9_profile_guard_missing")
    tip_days=[]
    for index,sample in enumerate(receipt["task_profile_scoped_snapshots"]):
        manifest=json.loads(_bound_file(root,sample["manifest"]));registry=_bound_file(root,sample["registry"])
        _bound_file(root,sample["visible_frame"])
        epoch.require(sample.get("label")==("first","second")[index] and
                      scope.scoped_profile(manifest,registry)==reference["applications"][kind]==sample.get("scoped_profile_sha256"),
                      "v9_raw_profile_reference_changed")
        if reference.get("current_public_tip_day") is not None:tip_days.append(scope.tip_calendar_day(registry))
    day_floor=reference.get("current_public_tip_day")
    if day_floor is not None:
        epoch.require(tip_days==[receipt.get("task_profile_tip_calendar_day")]*2 and
                      receipt.get("task_profile_tip_day_reference_floor")==day_floor and
                      receipt.get("task_profile_tip_day_matches_guest_clock") is True and
                      len(receipt.get("guest_calendar_probes",[]))==2,"v9_native_profile_calendar_binding_missing")
        guest_days=set()
        for label,probe in zip(("before","after"),receipt["guest_calendar_probes"]):
            raw=_bound_file(root,probe["raw"]);parsed=[(date.fromisoformat(x)-date(1970,1,1)).days for x in raw.decode().splitlines()]
            epoch.require(probe.get("label")==label and parsed==[probe.get("utc_day"),probe.get("local_day")],"v9_guest_calendar_raw_receipt_changed")
            guest_days.update(parsed)
        epoch.require(tip_days[0]>=day_floor and tip_days[0] in guest_days,"v9_profile_day_outside_guest_clock")
    script=actor_script(package,oracle,attempt);actions,_guards=compile_script(script)
    epoch.require(receipt.get("evaluator_script_sha256")==base.digest(script.encode()) and receipt.get("expected_actor_action_count")==len(actions) and
                  len(receipt.get("actor_steps",[]))==len(actions),"v9_action_script_or_count_changed")
    for index,(step,action) in enumerate(zip(receipt["actor_steps"],actions)):
        epoch.require(step.get("step")==index and step.get("status")=="applied" and
                      step.get("action_type")==step.get("dispatch_type")==action["type"] and
                      step.get("action_payload_sha256")==base.digest(json.dumps(action,separators=(",",":")).encode()),
                      "v9_action_identity_or_dispatch_changed")
        a=_bound_file(root,step["observation"]);b=_bound_file(root,step["predispatch"])
    caret_audit._guard_frames(root,receipt)
    if attempt=="cold-reset":
        _bound_file(root,receipt["cold_observation"])
        restored=_bound_file(root,receipt["restored_artifact"])
        epoch.require(restored==baseline and receipt.get("restored_state_sha256")==base.digest(baseline),"v9_cold_reset_original_bytes_changed")
    else:
        salt=json.loads(epoch.private(Path(value["private_map"])))["variant_salt"]
        saved=_bound_file(root,receipt["saved_artifact"]);score=verify_official(baseline,saved,oracle,private_salt=salt)
        expected=attempt=="positive"
        epoch.require(base.digest(saved)!=base.digest(baseline) and score["passed"] is expected and
                      (expected or score["errors"] and all(e.startswith("target_") for e in score["errors"])) and
                      receipt.get("fair_verifier")==score and receipt.get("max_actor_wall_seconds")==720 and
                      0<=receipt.get("actor_elapsed_seconds",-1)<=720 and receipt.get("max_actor_actions")==90,
                      "v9_independent_saved_state_or_uniform_clock_failed")
        post_enter_samples(root,out,actions,receipt)
    return {"attempt":attempt,"receipt_sha256":base.digest(receipt_raw),"sandbox_id_sha256":receipt["sandbox_id_sha256"]}


def audit_trio(*,value,row):
    phases=[audit_attempt(value=value,row=row,attempt=a) for a in ("positive","near-miss","cold-reset")]
    epoch.require(len({r["sandbox_id_sha256"] for r in phases})==3,"v9_trio_guests_not_distinct")
    return {"schema":"cua-native-wdi-post-enter-new-control-trio-audit-v9","status":"new_original_gui_saved_trio_independently_verified",
            "package_sha256":row["package_sha256"],"split":row["split"],"receipts":phases,
            "official_final_admissions":0,"official_model_results":0}


def audit_all(freeze_path:Path):
    value=epoch.validate(freeze_path);passed=[]
    for row in value["roster"]:passed.append(audit_trio(value=value,row=row))
    epoch.require(len(passed)==120,"v9_all_120_new_trios_required")
    from .v066_storage_budget import audit
    ledger=audit(Path(value["attempts_root"]),verify_all_bytes=True)
    epoch.require(ledger["unresolved_write_count"]==0,"v9_unresolved_raw_storage")
    return {"status":"120_new_selection_final_trios_verified_pending_formal_admission",
            "selection_trios":20,"final_trios":100,"historical_trios_used":0,"official_final_admissions":0,"official_model_results":0}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--freeze",type=Path,required=True);a=p.parse_args()
    print(json.dumps(audit_all(a.freeze),sort_keys=True))


if __name__=="__main__":main()
