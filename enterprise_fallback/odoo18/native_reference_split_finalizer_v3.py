"""Additive saved-only full20/full100 qualification from independent visual review.

This module creates no review, native environment, model request or formal task.
Original pending result/audit/frame bytes are never rewritten.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json,math,os
from pathlib import Path
from PIL import Image
from . import native_surface_workers_v13 as workers,partition_factory
from tools import odoo_v066_native_reference_qualification_v3 as qualification

SCHEMA='envloop-odoo-v066-derived-full-split-native-qualification-v3'
STATUS='full_split_saved_controls_and_independent_source_visual_review_verified'
REVIEW_SCHEMA='envloop-odoo-v066-full-split-native-source-review-v3'
REVIEW_STATUS='independent_full_split_native_source_frame_review_verified'
REVIEW_FIELDS={'schema','status','split','expected_case_count','qa_manifest_ref','actual_result_ref','outer_plan_sha256',
 'native_core_plan_sha256','native_worker_binding_sha256','native_adapter_binding_sha256','reference_binding_sha256',
 'run_nonce_sha256','require_exact_task_roster_order','no_formal_registration_by_review_alone','reviewer_approval','rows'}
ROW_FIELDS={'index','ordinal','family','task_id','package_sha256','source_asset_sha256','source_frame_sha256',
 'attempt_sha256','audit_sha256','qa_pair_sha256','reviewer_independent_of_actor','source_attachment_readable',
 'source_matches_package','reviewed_at_utc','review_notes'}
COUNTS={'selection':20,'official_hidden':100}


def require(ok,code):
 if not ok:raise ValueError(code)
def digest(raw):return sha256(raw).hexdigest()
def canonical(value):return workers.canonical(value)


class SavedReader:
 def __init__(self):self.seen={}
 def raw(self,path):
  path=Path(path)
  require(path.is_file() and not path.is_symlink() and path.stat().st_mode&0o077==0 and
   0<path.stat().st_size<=64_000_000,'private_saved_evidence_missing_or_unsafe')
  raw=path.read_bytes();self.seen[str(path.resolve())]=digest(raw);return raw
 def value(self,path,expected=None):
  raw=self.raw(path);require(expected is None or digest(raw)==expected,'saved_evidence_hash_changed')
  value=json.loads(raw);require(type(value) is dict,'saved_evidence_object_required');return value,raw
 def ref(self,reference,root=None):
  require(type(reference) is dict and set(reference)=={'path','sha256'} and type(reference['path']) is str and
   workers.HEX64.fullmatch(str(reference['sha256'])) is not None,'saved_reference_shape_invalid')
  path=Path(reference['path'])
  if root is not None:
   require(not path.is_absolute() and '..' not in path.parts,'saved_relative_reference_unsafe');path=Path(root)/path
  else:require(path.is_absolute(),'saved_absolute_reference_required')
  raw=self.raw(path);require(digest(raw)==reference['sha256'],'saved_reference_hash_changed');return path,raw
 def unchanged(self):
  for path,expected in self.seen.items():require(digest(Path(path).read_bytes())==expected,'original_changed_during_saved_replay')


def _stamp(value):
 try:stamp=datetime.fromisoformat(value)
 except (ValueError,TypeError):raise ValueError('source_review_timestamp_invalid') from None
 require(stamp.tzinfo is not None,'source_review_timestamp_not_aware');return stamp


def _reference_provenance(read,plan_path,outer,outer_raw,result):
 """A V3 outer plan cannot relabel a native-only or earlier reference run."""
 plan=outer['native_core_plan'];reference=outer['reference_binding'];stage=Path(plan_path).parent
 nonce=plan['run_nonce_hex']
 core,core_raw=read.value(stage/(nonce+'-core-plan.private.json'))
 require(core==plan and core_raw==canonical(plan),'saved_reference_native_core_plan_changed')
 intent,intent_raw=read.value(stage/(nonce+'-reference-intent.private.json'))
 expected_intent={'schema':'odoo-native-reference-dispatch-intent-v3','plan_sha256':digest(outer_raw),
  'native_core_plan_sha256':digest(core_raw),'reference_binding':reference,
  'same_episode_replay_authorized':False,'native_actor_epoch':'v13','native_scorer_reset_unchanged':True}
 require(canonical(intent)==canonical(expected_intent),'saved_current_v3_reference_intent_required')
 outcome,outcome_raw=read.value(stage/(nonce+'-reference-result.private.json'))
 expected_outcome={'schema':'odoo-native-reference-run-result-v3',
  'reference_binding_sha256':reference['reference_binding_sha256'],
  'native_core_result':{key:value for key,value in result.items() if key!='audits'},
  'formal_registration_performed':False,'old_reference_control_credit':0}
 require(canonical(outcome)==canonical(expected_outcome),'saved_current_v3_reference_result_required')
 return {'native_core_plan_artifact_sha256':digest(core_raw),'reference_dispatch_intent_sha256':digest(intent_raw),
  'reference_run_result_sha256':digest(outcome_raw),'v3_reference_run_provenance_verified':True}


def _bounds(value):
 return (type(value) is dict and set(value)=={'x','y','width','height'} and
  all(type(value[key]) in (int,float) and math.isfinite(value[key]) for key in value) and
  value['width']>0 and value['height']>0)


def _v3_action_provenance(read,attempt,receipt,audit,reference):
 """Reopen original intents; coordinates alone cannot attest V3 resolution."""
 _trace_path,raw=read.ref(receipt['refs']['gui_trace'],attempt);trace=json.loads(raw)
 require(type(trace) is dict and type(trace.get('actions')) is list and trace['actions'] and
  len(trace['actions'])==audit['native_guard_action_count'],'saved_v3_action_trace_count_changed')
 deferred=None;scroll_count=scrolls=optional_count=0;nonces=set()
 for step,item in enumerate(trace['actions']):
  paths=list((attempt/'actions').glob(f'step-{step:03d}*-intent.private.json'))
  require(len(paths)==1,'saved_v3_action_intent_ambiguous')
  intent,_raw=read.value(paths[0]);action=intent.get('normalized_action')
  require(type(action) is dict and type(intent.get('step')) is int and intent['step']==step and
   type(action.get('step')) is int and action['step']==step and type(intent.get('frame_id')) is str and intent['frame_id'] and
   intent['frame_id']==action.get('frame_id') and intent['frame_id'] not in nonces and
   intent.get('dispatch_state')=='intent_durable_before_gui_action' and
   {'optional_native_facet_resolution','native_candidate_viewport_resolution'}<=set(intent),
   'saved_v3_action_resolution_fields_required')
  nonces.add(intent['frame_id']);optional=intent['optional_native_facet_resolution'];viewport=intent['native_candidate_viewport_resolution']
  require(optional is None or viewport is None,'saved_v3_action_resolution_ambiguous')
  coordinates=type(action.get('target')) is dict and set(action['target'])=={'x','y'}
  if coordinates and action.get('type') in ('click','double_click','type'):
   require(type(optional) is dict or type(viewport) is dict,'saved_v3_locator_resolution_required')
  if optional is not None:
   require(type(optional) is dict,'saved_v3_optional_resolution_invalid');optional_count+=1
   if optional.get('status') in ('absent_after_observation','not_visible_after_observation'):
    require(set(optional)=={'status','actual_wait_selected_before_intent','matched_handles'} and
     optional['actual_wait_selected_before_intent'] is True and type(optional['matched_handles']) is int and
     optional['matched_handles']==(0 if optional['status']=='absent_after_observation' else 1) and
     action.get('type')=='wait' and action.get('duration_ms')==100,'saved_v3_optional_wait_changed')
   else:
    require(set(optional)=={'status','actual_wait_selected_before_intent','matched_handles','bounds'} and
     optional['status']=='native_current_unique_handle' and optional['actual_wait_selected_before_intent'] is False and
     type(optional['matched_handles']) is int and optional['matched_handles']==1 and _bounds(optional['bounds']) and
     action.get('type')=='click' and action.get('target')=={
      'x':int(optional['bounds']['x']+optional['bounds']['width']/2),
      'y':int(optional['bounds']['y']+optional['bounds']['height']/2)},'saved_v3_optional_click_changed')
  if viewport is None:
   require(deferred is None,'saved_v3_deferred_candidate_action_missing');continue
  require(type(viewport) is dict and _bounds(viewport.get('candidate_bounds')) and
   type(viewport.get('viewport')) is list and len(viewport['viewport'])==2 and
   all(type(size) is int and size>0 for size in viewport['viewport']) and
   viewport.get('candidate_resolved_after_observation') is True,'saved_v3_viewport_resolution_invalid')
  frame_path,_frame=read.ref(item['frame'],attempt)
  with Image.open(frame_path) as frame:require(list(frame.size)==viewport['viewport'],'saved_v3_resolution_viewport_changed')
  width,height=viewport['viewport'];box=viewport['candidate_bounds']
  require(box['width']<=width and box['height']<=height,'saved_v3_candidate_larger_than_view')
  inside=box['x']>=0 and box['y']>=0 and box['x']+box['width']<=width and box['y']+box['height']<=height
  fields={'status','candidate_bounds','viewport','scroll_selected_before_intent','candidate_resolved_after_observation'}
  if viewport.get('scroll_selected_before_intent') is True:
   require(set(viewport)==fields|{'scroll_target_kind','original_action_type','original_action_deferred'} and not inside and
    viewport['status']=='offviewport_candidate_guarded_scroll_selected' and viewport['original_action_deferred'] is True and
    viewport['original_action_type'] in ('click','double_click','type') and
    viewport['scroll_target_kind']=='current_viewport_center_subject_to_native_ownership_hit_guard' and
    action.get('type')=='scroll' and action.get('target')=={'x':width//2,'y':height//2} and
    all(type(action.get(axis)) is int for axis in ('dx','dy')) and (action['dx'] or action['dy']),
    'saved_v3_guarded_scroll_resolution_changed')
   expected_dx=(-480 if box['x']<0 else 480 if box['x']+box['width']>width else 0)
   expected_dy=(-480 if box['y']<0 else 480 if box['y']+box['height']>height else 0)
   require((action['dx'],action['dy'])==(expected_dx,expected_dy),'saved_v3_scroll_direction_or_delta_changed')
   require(deferred is None or deferred==(viewport['original_action_type'],intent.get('phase')),
    'saved_v3_deferred_candidate_identity_changed')
   deferred=(viewport['original_action_type'],intent.get('phase'));scroll_count+=1;scrolls+=1
   require(scroll_count<=reference['max_scroll_actions_per_candidate'],'saved_v3_candidate_scroll_bound_changed')
  else:
   require(set(viewport)==fields and viewport['scroll_selected_before_intent'] is False and inside and
    viewport['status']=='current_candidate_inside_viewport' and action.get('type') in ('click','double_click','type') and
    action.get('target')=={'x':int(box['x']+box['width']/2),'y':int(box['y']+box['height']/2)},
    'saved_v3_current_candidate_resolution_changed')
   require(deferred is None or deferred==(action['type'],intent.get('phase')),'saved_v3_deferred_candidate_action_changed')
   deferred=None;scroll_count=0
 require(deferred is None,'saved_v3_deferred_candidate_action_missing')
 return {'v3_reference_action_provenance_verified':True,'reference_viewport_scroll_action_count':scrolls,
  'reference_optional_facet_action_count':optional_count}


def derive(*,plan_path,worker_dir,run_dir,source_review_path,source_review_sha256):
 """Reopen and rederive every ordered case. No output or approval is written."""
 read=SavedReader();outer,outer_raw=read.value(plan_path)
 qualification.validate_plan(outer);plan=outer['native_core_plan'];split=plan['split'];count=COUNTS.get(split)
 require(count is not None and plan['task_count']==len(plan['tasks'])==count,'exact_full_twenty_or_hundred_required')
 worker=Path(worker_dir).resolve();run=Path(run_dir).resolve();private=worker/'private'
 require(worker.name==split and run.parent==(private/'v066_native_surface_controls_v13').resolve() and
  run.name==plan['fresh_run_directory_name'] and run.is_dir() and not run.is_symlink() and run.stat().st_mode&0o077==0,
  'saved_split_run_namespace_changed')
 require(not (run/'failed.private.json').exists(),'failed_split_cannot_finalize')
 result,result_raw=read.value(run/'result.private.json');intent,_=read.value(run/'batch-intent.private.json')
 core_sha=digest(canonical(plan));binding=plan['native_worker_binding'];reference=outer['reference_binding']
 provenance=_reference_provenance(read,plan_path,outer,outer_raw,result)
 require(result['schema']==qualification.core.BATCH_SCHEMA and
  result['status']=='full_native_surface_gui_control_semantics_verified_source_visual_review_pending' and
  result['split']==split and result['fresh_native_gui_controls']==result['expected_case_count']==count and
  result['source_visual_review_pending'] is True and result['model_attempts']==result['official_final_tasks_admitted']==result['old_positive_credit']==0 and
  result['plan_sha256']==intent['plan_sha256']==core_sha and result['native_worker_binding_sha256']==binding['binding_sha256'] and
  result['native_adapter_binding_sha256']==plan['native_adapter_binding_sha256'] and result['run_nonce_sha256']==plan['run_nonce_sha256'] and
  result['task_roster_sha256']==digest(canonical(plan['tasks'])) and type(result['audits']) is list and len(result['audits'])==count,
  'actual_full_split_pending_result_changed')
 require(intent['expected_case_count']==count and intent['native_worker_binding_sha256']==binding['binding_sha256'] and
  intent['run_nonce_sha256']==plan['run_nonce_sha256'] and intent['old_positive_credit']==0 and
  intent['automatic_replay_authorized'] is False and intent['model_attempts']==intent['official_final_tasks_admitted']==0 and
  workers.HEX64.fullmatch(str(intent['fresh_train_control_sha256'])) is not None,'actual_batch_intent_changed')
 review,review_raw=read.value(source_review_path,source_review_sha256)
 expected={'schema':REVIEW_SCHEMA,'status':REVIEW_STATUS,'split':split,'expected_case_count':count,
  'outer_plan_sha256':digest(outer_raw),'native_core_plan_sha256':core_sha,'native_worker_binding_sha256':binding['binding_sha256'],
  'native_adapter_binding_sha256':plan['native_adapter_binding_sha256'],'reference_binding_sha256':reference['reference_binding_sha256'],
  'run_nonce_sha256':plan['run_nonce_sha256'],'require_exact_task_roster_order':True,
  'no_formal_registration_by_review_alone':True,'reviewer_approval':True}
 require(set(review)==REVIEW_FIELDS and all(type(review.get(k)) is type(v) and review[k]==v for k,v in expected.items()) and
  type(review['rows']) is list and len(review['rows'])==count,'complete_current_root_visual_review_required')
 result_path,review_result=read.ref(review['actual_result_ref']);require(result_path.resolve()==(run/'result.private.json').resolve() and review_result==result_raw,'review_actual_result_not_exact')
 qa_path,qa_raw=read.ref(review['qa_manifest_ref']);qa=json.loads(qa_raw)
 require(qa['schema']=='odoo-saved-native-source-visual-qa-manifest-v3' and qa['split']==split and qa['case_count']==count and
  len(qa['rows'])==count and qa['native_core_plan_sha256']==core_sha and qa['native_binding_sha256']==binding['binding_sha256'] and
  qa['reference_binding_sha256']==reference['reference_binding_sha256'] and qa['actual_result_ref']==review['actual_result_ref'] and
  qa['outer_plan_ref']['sha256']==digest(outer_raw),'exact_root_inspected_qa_manifest_required')
 world_path=private/'partition_cases.json';world,world_raw=read.value(world_path)
 require(world['split']==split,'source_partition_changed')
 cases={}
 for family in ('purchase','inventory','sales','crm'):
  require(type(world['cases'][family]) is list and len(world['cases'][family])==count//4,'full_family_partition_required')
  for case in world['cases'][family]:
   require(case['id'] not in cases,'duplicate_partition_task');cases[case['id']]=(family,case)
 require(set(cases)=={r['task_id'] for r in plan['tasks']},'source_roster_partition_changed')
 facade=qualification._facade(reference);verified=[]
 for ordinal,(metadata,entry,approved,qa_row) in enumerate(zip(plan['tasks'],result['audits'],review['rows'],qa['rows'],strict=True)):
  require(type(approved) is dict and set(approved)==ROW_FIELDS and type(approved['index']) is int and type(approved['ordinal']) is int and
   approved['index']==qa_row['index']==ordinal+1 and approved['ordinal']==qa_row['ordinal']==ordinal and
   all(approved[k]==metadata[k]==qa_row[k] for k in ('family','task_id','package_sha256','source_asset_sha256')),
   'visual_review_roster_order_or_identity_changed')
  require(approved['reviewer_independent_of_actor'] is True and approved['source_attachment_readable'] is True and
   approved['source_matches_package'] is True and type(approved['review_notes']) is str and approved['review_notes'].strip(),
   'independent_readability_and_match_review_required')
  attempt=run/f'attempt-{ordinal:03d}';receipt,receipt_raw=read.value(attempt/'attempt.private.json');audit,audit_raw=read.value(attempt/'independent-audit.private.json')
  require(entry['task_id']==metadata['task_id'] and entry['family']==metadata['family'] and entry['audit']==audit and
   entry['attempt_sha256']==approved['attempt_sha256']==digest(receipt_raw) and entry['audit_sha256']==approved['audit_sha256']==digest(audit_raw),
   'review_or_result_independent_case_hash_changed')
  require(all(receipt[k]==metadata[k] for k in ('task_id','family','package_sha256')) and receipt['plan_sha256']==core_sha and
   receipt['run_nonce_sha256']==plan['run_nonce_sha256'] and receipt['model_attempts']==receipt['official_final_tasks_admitted']==0,
   'original_attempt_binding_changed')
  row=facade._case_row(plan,metadata,intent['fresh_train_control_sha256'])
  actual=facade.audit_case(plan=plan,row=row,attempt=attempt,worker_private=private)
  require(actual==audit,'independent_saved_case_replay_changed')
  action_provenance=_v3_action_provenance(read,attempt,receipt,audit,reference)
  frame_path,frame=read.ref(receipt['refs']['source_frame'],attempt)
  require(digest(frame)==approved['source_frame_sha256']==qa_row['original_native_frame']['sha256'] and
   Path(qa_row['original_native_frame']['path']).resolve()==frame_path.resolve(),'review_original_source_frame_changed')
  family,case=cases[metadata['task_id']];asset=partition_factory.source_asset(case,world)
  require(family==metadata['family'] and digest(asset)==metadata['source_asset_sha256'] and
   digest(json.dumps(case,sort_keys=True).encode()+b'\n'+asset)==metadata['package_sha256'] and
   digest(case['prompt'].encode())==metadata['visible_instruction_sha256'],'deterministic_source_or_package_not_equivalent')
  asset_path,copy=read.ref(qa_row['exact_source_asset_copy']);require(copy==asset,'inspected_source_asset_copy_changed')
  copy_path,native_copy=read.ref(qa_row['unchanged_native_frame_copy']);require(native_copy==frame,'inspected_native_frame_copy_changed')
  qa_image,qa_bytes=read.ref(qa_row['side_by_side_qa']);require(digest(qa_bytes)==approved['qa_pair_sha256'],'reviewed_qa_pair_changed')
  with Image.open(frame_path) as native_image,Image.open(qa_image) as pair:
   x,y=qa_row['native_crop_origin'];native_image=native_image.convert('RGB')
   require(pair.crop((x,y,x+native_image.width,y+native_image.height)).convert('RGB').tobytes()==native_image.tobytes(),
    'inspected_native_panel_pixels_changed')
  stamp=_stamp(approved['reviewed_at_utc']);require(stamp>=_stamp(receipt['finished_at_utc']) and stamp>=_stamp(qa['generated_at_utc']),
   'source_review_predates_actual_attempt_or_qa')
  require(audit['source_visual_review_pending'] is True and audit['source_visual_review_verified'] is False,'pending_original_audit_was_rewritten')
  verified.append({**action_provenance,'ordinal':ordinal,'family':family,'task_id':metadata['task_id'],'package_sha256':metadata['package_sha256'],
   'source_asset_sha256':digest(asset),'source_frame_sha256':digest(frame),'original_attempt_sha256':digest(receipt_raw),
   'original_independent_audit_sha256':digest(audit_raw),'review_row_sha256':digest(canonical(approved)),
   'reviewed_at_utc':approved['reviewed_at_utc'],'independent_scores':[audit['independent_baseline_reward'],audit['independent_positive_reward'],audit['independent_wrong_object_reward']],
   'native_guard_action_count':audit['native_guard_action_count'],'source_visual_review_verified':True,'source_attachment_readback':True})
 read.unchanged()
 return {**provenance,'schema':SCHEMA,'status':STATUS,'split':split,'qualified_control_case_count':count,'formal_task_registration_count':0,
  'outer_plan_sha256':digest(outer_raw),'native_core_plan_sha256':core_sha,'original_pending_result_sha256':digest(result_raw),
  'independent_root_source_review_sha256':digest(review_raw),'qa_manifest_sha256':digest(qa_raw),'native_worker_binding_sha256':binding['binding_sha256'],
  'native_adapter_binding_sha256':plan['native_adapter_binding_sha256'],'reference_binding_sha256':reference['reference_binding_sha256'],
  'run_nonce_sha256':plan['run_nonce_sha256'],'full_ordered_roster_sha256':digest(canonical(plan['tasks'])),
  'native_train_control_prerequisite_sha256':intent['fresh_train_control_sha256'],
  'native_train_prerequisite_is_v3_reference_train_credit':False,'v3_reference_train_control_credit':0,'old_reference_control_credit':0,
  'all_saved_audits_independently_rederived':True,'all_source_and_packages_equivalent':True,'originals_preserved':True,
  'visual_approval_authored_by_finalizer':False,'model_calls':0,'provider_calls':0,'native_calls':0,'formal_registration_performed':False,
  'finalizer_source_sha256':digest(Path(__file__).read_bytes()),'rows':verified}


def finalize(*,output_path,**arguments):
 output=Path(output_path);parent=Path(arguments['plan_path']).resolve().parent
 require(output.parent.resolve()==parent and output.parent.stat().st_mode&0o077==0 and not output.exists() and not output.is_symlink(),
  'fresh_private_derived_output_next_to_plan_required')
 value=derive(**arguments);value['derived_at_utc']=datetime.now(timezone.utc).isoformat()
 fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb') as f:f.write(canonical(value));f.flush();os.fsync(f.fileno())
 return {'schema':SCHEMA,'status':STATUS,'split':value['split'],'qualified_control_case_count':value['qualified_control_case_count'],
  'derived_receipt_ref':{'path':str(output.resolve()),'sha256':digest(output.read_bytes())},'formal_registration_performed':False,'native_calls':0}


def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('plan','worker-dir','run-dir','source-review','source-review-sha256','out'):p.add_argument('--'+name,required=True)
 a=p.parse_args();result=finalize(plan_path=Path(a.plan),worker_dir=Path(a.worker_dir),run_dir=Path(a.run_dir),
  source_review_path=Path(a.source_review),source_review_sha256=a.source_review_sha256,output_path=Path(a.out))
 print(json.dumps(result,sort_keys=True))

if __name__=='__main__':main()
