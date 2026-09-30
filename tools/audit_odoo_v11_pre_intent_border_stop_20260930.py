"""Read-only, exact raw-raster forensic for terminal v11 TRAIN run 09."""
from __future__ import annotations
import argparse
from io import BytesIO
import json
from pathlib import Path
from PIL import Image, ImageChops
from tools import audit_odoo_v066_train_attachment_calibration_v10 as prior
from tools import odoo_v066_train_attachment_calibration_v11 as run
from tools import odoo_v066_scale_protocol_v1 as protocol

TOP = {(16,155):frozenset(((246,247,249),(246,247,248))),
       (16,157):frozenset(((226,229,234),(226,230,234))),
       (17,157):frozenset(((250,250,251),(249,250,250)))}
BOTTOM = {(16,861):frozenset(((226,230,234),(226,229,234))),
          (17,861):frozenset(((249,250,250),(250,250,251))),
          (16,863):frozenset(((246,247,248),(246,247,249))),
          (17,863):frozenset(((229,233,236),(230,233,236)))}


def differences(a: bytes,b: bytes) -> dict:
    x,y=Image.open(BytesIO(a)),Image.open(BytesIO(b))
    prior.require(x.mode==y.mode=="RGB" and x.size==y.size==(1440,1000),"v11_png_mode_or_viewport_changed")
    box=ImageChops.difference(x,y).getbbox()
    result={}
    if box:
        for yy in range(box[1],box[3]):
            for xx in range(box[0],box[2]):
                old,new=x.getpixel((xx,yy)),y.getpixel((xx,yy))
                if old!=new:
                    result[(xx,yy)]=frozenset((old,new))
    return result


def audit(*,worker_dir:Path,accepted_audit_path:Path,private_freeze_path:Path,public_freeze_path:Path)->dict:
    _worker,private,freeze,_case,_wrong=run._verify_freeze(worker_dir,accepted_audit_path,private_freeze_path,public_freeze_path)
    out=private/"v066_attachment_route_calibration"/run.RUN_NAME
    trace=prior._json(out/"gui_trace.json");failure=prior._json(out/"failure.private.json")
    prior.require(failure.get("schema")==run.RECEIPT_SCHEMA and failure.get("status")=="terminal_failure_no_automatic_replay" and
                  failure.get("stage")=="positive_gui" and failure.get("error_code")=="stale_frame" and
                  failure.get("reset_exact") is failure.get("services_restored") is True and
                  failure.get("run_nonce_sha256")==protocol.digest(freeze["run_nonce"].encode()) and
                  failure.get("model_attempts")==failure.get("official_final_tasks_admitted")==0 and
                  len(trace.get("actions",[]))==8 and len(trace.get("guard_samples",[]))==35 and
                  len(trace.get("pre_intent_rejections",[]))==3,
                  "v11_terminal_status_or_trace_changed")
    prior.require(not any((out/name).exists() for name in ("attempt.private.json","positive_sql.json","negative_sql.json","positive_reload_frame.png")),
                  "v11_saved_positive_or_completed_attempt_unexpected")
    prior.require(prior._json(out/"baseline_sql.json")==prior._json(private/"baseline_snapshot.json")==prior._json(out/"restored_sql.json") and
                  prior._json(out/"restored_filestore.json")==prior._json(private/"baseline-filestore-manifest.json"),
                  "v11_sql_or_full_filestore_reset_changed")
    frames=[]
    for i,ref in enumerate(trace["pre_intent_rejections"]):
        d=prior._artifact(out,ref)
        prior.require(d.get("step")==8 and d.get("phase")=="positive" and d.get("observation_attempt")==i and
                      d.get("pre_dispatch_intent_created") is d.get("gui_action_dispatched") is False,
                      "v11_price_rejection_not_pre_intent")
        p=prior._artifact(out,d["route_probe_ref"]);decision=prior._artifact(out,d["route_decision_ref"])
        prior.require(p.get("status")==p.get("reason_code")=="ready" and p.get("strict_price_identity_present") is True and
                      p.get("visible_price_input_count")==1 and decision.get("reason_code")=="physical_or_identity_guard_rejected" and
                      decision.get("route_kind")=="price_editor" and decision.get("route_token") is None,
                      "v11_route_identity_or_nonclaim_changed")
        a=prior._ref(out,d["observed_frame_ref"],image=True)[1]
        b=prior._ref(out,d["current_frame_ref"],image=True)[1]
        delta=differences(a,b)
        prior.require(delta==(TOP if i==0 else {**TOP,**BOTTOM}),"v11_exact_corner_pair_changed")
        frames.append({"observation_attempt":i,"changed_pixel_count":len(delta),
                       "changed_coordinates":[list(xy) for xy in sorted(delta)],
                       "observed_frame_sha256":protocol.digest(a),"current_frame_sha256":protocol.digest(b)})
        prefix=Path(ref["path"]).name.removesuffix("-rejection.private.json")
        prior.require(not (out/"actions"/(prefix+"-intent.private.json")).exists() and
                      not (out/"actions"/(prefix+"-result.private.json")).exists(),"v11_rejected_price_has_intent_or_dispatch")
    price=[s for s in trace["guard_samples"] if s.get("step")==8]
    prior.require(len(price)==6 and all(s.get("stage")=="parse_price_stability" for s in price) and
                  [s.get("sample") for s in price]==[0,1]*3 and
                  [s.get("classification") for s in price]==["passive_observed","third_or_material_rejected"]*3,
                  "v11_failure_not_immediate_new_rgb_membership_rejection")
    for s in trace["guard_samples"]:prior._ref(out,s["sampled_frame_ref"],image=True)
    hashes={}
    for p in sorted(out.rglob("*")):
        if p.is_file():prior._private(p);hashes[str(p.relative_to(out))]=protocol.digest(p.read_bytes())
        else:prior._private(p,directory=True)
    return {"schema":"envloop-odoo-v11-pre-intent-border-stop-audit-20260930-v1",
            "status":"terminal_new_top_corner_rgb_rejected_before_price_intent",
            "private_freeze_sha256":protocol.digest(private_freeze_path.read_bytes()),
            "private_failure_sha256":hashes["failure.private.json"],"private_trace_sha256":hashes["gui_trace.json"],
            "private_raw_manifest_sha256":protocol.digest(json.dumps(hashes,sort_keys=True,separators=(",",":")).encode()),
            "raw_files_rehashed":len(hashes),"completed_gui_actions":8,"physical_guard_pngs_checked":35,
            "ready_price_identity_probes":3,"rejection_frames":frames,"new_top_corner_pixels":3,"previous_bottom_corner_pixels":4,
            "six_passive_rounds_exhausted":False,"price_intent_or_dispatch_exists":False,
            "positive_saved_state_exists":False,"full_sql_and_filestore_reset_exact":True,
            "service_state_restored_by_runner_receipt":True,"live_docker_state_independently_queried":False,
            "prospective_recovery":"strict_two_whole_rgb_states_per_corner_full_image_equal_elsewhere_identity_bound",
            "prospective_recovery_implemented_or_live_qualified":False,
            "same_intent_replay_authorized":False,"model_attempts":0,"official_final_tasks_admitted":0}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ("worker-dir","accepted-audit","private-freeze","public-freeze","public-out"):p.add_argument("--"+key,type=Path,required=True)
    a=p.parse_args();value=audit(worker_dir=a.worker_dir,accepted_audit_path=a.accepted_audit,private_freeze_path=a.private_freeze,public_freeze_path=a.public_freeze)
    protocol.write_new(a.public_out,value,private=False);print(json.dumps(value,sort_keys=True))


if __name__=="__main__":main()
