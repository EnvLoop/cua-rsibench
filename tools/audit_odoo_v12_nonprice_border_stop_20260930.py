"""Read-only v12 terminal proof: price guarded, Ctrl+A rejected before intent."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from tools import audit_odoo_v066_train_attachment_calibration_v12 as prior
from tools import odoo_v066_train_attachment_calibration_v12 as run
from tools import odoo_v066_scale_protocol_v1 as protocol
from tools.odoo_v066_train_border_material_audit_v12 import independent_material,price_guard


def audit(worker_dir,accepted_audit_path,private_freeze_path,public_freeze_path):
 _w,private,freeze,case,wrong=run._verify_freeze(worker_dir,accepted_audit_path,private_freeze_path,public_freeze_path)
 out=private/'v066_attachment_route_calibration'/run.RUN_NAME;trace=prior._json(out/'gui_trace.json');failure=prior._json(out/'failure.private.json')
 prior.require(failure.get('schema')==run.RECEIPT_SCHEMA and failure.get('status')=='terminal_failure_no_automatic_replay' and
               failure.get('stage')=='positive_gui' and failure.get('error_code')=='stale_frame' and
               failure.get('reset_exact') is failure.get('services_restored') is True and
               len(trace.get('actions',[]))==9 and len(trace.get('guard_samples',[]))==38 and len(trace.get('pre_intent_rejections',[]))==3,
               'v12_terminal_status_or_trace_count_invalid')
 baseline=prior._json(private/'baseline_snapshot.json')
 prior.require(prior._json(out/'baseline_sql.json')==prior._json(out/'restored_sql.json')==baseline and
               prior._json(out/'restored_filestore.json')==prior._json(private/'baseline-filestore-manifest.json'),
               'v12_exact_state_reset_changed')
 action=trace['actions'][8];intent=prior._json(out/'actions/step-008-intent.private.json');result=prior._json(out/'actions/step-008-result.private.json')
 _refs,number=price_guard(out,action,intent,result,case,wrong,baseline,trace['guard_samples']);prior.require(number==1,'v12_price_guards_not_independently_proven')
 for i,ref in enumerate(trace['pre_intent_rejections']):
  d=prior._artifact(out,ref);assistant=prior._artifact(out,d['assistant_action_ref'])
  prior.require(d.get('step')==9 and d.get('observation_attempt')==i and d.get('pre_dispatch_intent_created') is d.get('gui_action_dispatched') is False and
                assistant.get('type')=='key' and assistant.get('key') in ('Control+A','Meta+A'),
                'v12_nonprice_rejection_or_action_changed')
  a=prior._ref(out,d['observed_frame_ref'],image=True)[1];b=prior._ref(out,d['current_frame_ref'],image=True)[1]
  prior.require(independent_material(a)['canonical_material_sha256']==independent_material(b)['canonical_material_sha256'],
                'v12_rejected_pair_has_material_body_change')
  prefix=Path(ref['path']).name.removesuffix('-rejection.private.json')
  prior.require(not (out/'actions'/(prefix+'-intent.private.json')).exists(),'v12_rejected_key_has_intent')
 prior.require(not (out/'positive_sql.json').exists() and not (out/'attempt.private.json').exists(),'v12_unsaved_flow_recoded_as_pass')
 hashes={}
 for path in sorted(out.rglob('*')):
  if path.is_file():prior._private(path);hashes[str(path.relative_to(out))]=protocol.digest(path.read_bytes())
 return {'schema':'envloop-odoo-v12-nonprice-finite-border-stop-audit-v1','status':'price_doubleclick_guarded_nonprice_key_terminal_before_intent',
         'private_failure_sha256':hashes['failure.private.json'],'private_trace_sha256':hashes['gui_trace.json'],
         'private_raw_manifest_sha256':protocol.digest(json.dumps(hashes,sort_keys=True,separators=(',',':')).encode()),
         'raw_files_rehashed':len(hashes),'completed_gui_actions':9,'physical_guard_pngs_checked':38,
         'price_parse_dispatch_material_guards_reopened':True,'select_all_key_preintent_rejections':3,
         'all_rejected_key_pairs_same_finite_canonical_material':True,'positive_saved_state_exists':False,
         'full_sql_filestore_reset_exact':True,'service_state_restored_by_runner_receipt':True,
         'same_intent_replay_authorized':False,'model_attempts':0,'official_final_tasks_admitted':0}


def main():
 p=argparse.ArgumentParser(description=__doc__)
 for k in ('worker-dir','accepted-audit','private-freeze','public-freeze','public-out'):p.add_argument('--'+k,type=Path,required=True)
 a=p.parse_args();result=audit(a.worker_dir,a.accepted_audit,a.private_freeze,a.public_freeze)
 protocol.write_new(a.public_out,result,private=False);print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
