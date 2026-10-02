"""Exact-reviewed bootstrap/100-roster continuation with supervised one-use IDs.

Every prospective control is new evidence under the32-project baseline/ACL.
An uncertain or failed child is terminal; no historical control transfers and
no model call or official admission is available through this controller.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import copy
import fcntl
import json
import os
from pathlib import Path
import sys

from . import factory,gui_controls,verify,reset
from . import prospective_final_controls_v066 as lane
from . import v066_supervised_final_one_v1 as supervisor
from . import v066_infra_requalification_v1 as process_audit
from . import v066_prospective_cohort_v5 as source
from . import v066_prospective_cohort_runtime_v5 as scoped


PERMIT_SCHEMA='envloop-gitlab-prospective100-exact-permit-private-v5'
PLAN_SCHEMA='envloop-gitlab-prospective100-baseline-plan-private-v5'
JOURNAL_SCHEMA='envloop-gitlab-prospective100-journal-event-private-v5'


def cold_seed_binding(value:dict,baseline:dict)->dict:
 root=Path(value['epoch_root']);state=json.loads(source.private(root/'cow-reset-state.json'))
 expected={role:'/var/lib/docker/volumes/'+name+'/_data' for role,name in value['clone_volume_names'].items()}
 if (state.get('schema')!='envloop-gitlab-overlay-cold-reset-v1' or state.get('baseline_business_sha256')!=baseline['business_sha256'] or
     state.get('seed_volume_lowerdirs')!=expected or type(state.get('clone_generation')) is not int or state['clone_generation']<1 or
     state.get('first_clone_readback_equal') is not True):
  raise ValueError('New32-project cold seed must bind exact dedicated new volumes and baseline')
 return {k:state[k] for k in ('schema','baseline_business_sha256','seed_volume_lowerdirs','first_clone_container_id_sha256','first_clone_readback_equal')}


def freeze_baseline_plan(*,value:dict,freeze_path:Path,baseline:dict,acl_sha:str,world:dict)->dict:
 root=Path(value['epoch_root']);world_sha=source.sha(source.private(root/'world-private.json'))
 by_id={t['task_id']:t for t in world['tasks']+world['reserve_tasks']};roster=[]
 for index,metadata in enumerate(value['candidate_roster']):
  task=by_id[metadata['task_id']]
  if task['template_group']!=metadata['template_group'] or factory.sha256(task['source_family'])!=metadata['source_family_sha256']:
   raise ValueError('Materialized task metadata differs from prospective source roster')
  package={'world_sha256':world_sha,'baseline_business_sha256':baseline['business_sha256'],'native_acl_sha256':acl_sha,'task':task}
  roster.append({**metadata,'index':index,'previous_package_sha256':metadata['package_sha256'],
   'package_sha256':source.sha(factory.canonical(package)),'task_object_sha256':source.sha(factory.canonical(task)),
   'historical_control_transferred':False})
 source.validate_roster(roster,value['retired_task_metadata'])
 if len({r['package_sha256'] for r in roster})!=100:raise ValueError('New baseline-bound100 package identities collide')
 seed_binding=cold_seed_binding(value,baseline)
 plan={'schema':PLAN_SCHEMA,'source_freeze_sha256':source.sha(source.private(freeze_path)),
  'source_sha256s':value['source_sha256s'],'task_roster':roster,'baseline_sha256':source.sha(source.private(root/'baseline-persisted-state.json')),
  'baseline_business_sha256':baseline['business_sha256'],'world_sha256':world_sha,'native_acl_sha256':acl_sha,
  'source_bundle_sha256':lane.sha(lane.canonical(lane.source_sha256s())),
  'cold_seed_binding':seed_binding,'first_clone_generation':1,'fixed_case_scores':[1.0,0.0,1.0],'fresh_cold_resets_per_task':3,
  'max_wall_seconds_per_task':7200,'historical_controls_transferred':0,'model_calls':0,'official_final_admitted':0}
 sha=source.write_new(root/'cohort-plan.private.json',plan)
 (root/'controls').mkdir(mode=0o700);(root/'controls/attempts').mkdir(mode=0o700);(root/'controls/supervision').mkdir(mode=0o700)
 return {'plan_sha256':sha,'candidate_count':100,'source_families':20,'historical_controls_transferred':0,'model_calls':0,'official_final_admitted':0}


def baseline_inputs(value:dict,freeze_path:Path)->tuple[dict,str,dict]:
 root=Path(value['epoch_root']);receipt=json.loads(source.private(root/'bootstrap-receipt.private.json'))
 plan_raw=source.private(root/'cohort-plan.private.json');plan=json.loads(plan_raw)
 baseline_raw=source.private(root/'baseline-persisted-state.json');baseline=json.loads(baseline_raw)
 acl_raw=source.private(root/'native-acl.private.json');acl=json.loads(acl_raw)
 cold=json.loads(source.private(root/'first-cold-readback.private.json'))
 if (receipt.get('status')!='new32_project_fifo_baseline_acl_exact_cold_clone_frozen' or
     receipt.get('original_runtime_unmodified') is not True or receipt.get('original31_project_projection_unchanged') is not True or
     receipt.get('first_cold_clone_exact') is not True or plan.get('schema')!=PLAN_SCHEMA or
     plan.get('source_freeze_sha256')!=source.sha(source.private(freeze_path)) or plan.get('source_sha256s')!=value['source_sha256s'] or
     receipt.get('cohort_plan_sha256')!=source.sha(plan_raw) or plan.get('baseline_sha256')!=source.sha(baseline_raw) or
     plan.get('world_sha256')!=source.sha(source.private(root/'world-private.json')) or plan.get('native_acl_sha256')!=source.sha(acl_raw) or
     acl.get('own_project_successes')!=3 or acl.get('cross_partition_denials')!=6 or acl.get('non_admin_actors') is not True or cold!=baseline or
     plan.get('historical_controls_transferred')!=0 or plan.get('model_calls')!=0 or plan.get('official_final_admitted')!=0):
  raise ValueError('New32-project bootstrap/baseline/ACL/readback binding incomplete')
 scoped.validate_snapshot(baseline,32);source.validate_roster(plan['task_roster'],value['retired_task_metadata'])
 scoped.audit_native_acl(root,acl)
 if plan.get('cold_seed_binding')!=cold_seed_binding(value,baseline):raise ValueError('Prospective invariant cold seed provenance changed')
 if len({r['package_sha256'] for r in plan['task_roster']})!=100 or any(r['historical_control_transferred'] is not False for r in plan['task_roster']):
  raise ValueError('All100 identities must bind new baseline with no transferred controls')
 return plan,source.sha(plan_raw),baseline


def journal_state(rows:list[dict])->dict:
 completed=[];pending=None;terminal=False;previous='0'*64
 for index,row in enumerate(rows):
  if (row.get('schema')!=JOURNAL_SCHEMA or row.get('seq')!=index+1 or row.get('previous_sha256')!=previous or
   row.get('entry_sha256')!=source.sha(factory.canonical({k:v for k,v in row.items() if k!='entry_sha256'}))):
   raise ValueError('Prospective one-use journal hash chain changed')
  if row['kind']=='intent':
   if pending is not None or terminal or row['task_index']!=len(completed) or len(completed)>=100:raise ValueError('Uncertain/failed prospective identity cannot replay or advance')
   pending=row
  elif row['kind']=='terminal':
   if pending is None or row['task_index']!=pending['task_index']:raise ValueError('Prospective terminal has no matching intent')
   if row['passed'] is True:completed.append(row)
   else:terminal=True
   pending=None
  else:raise ValueError('Unknown prospective journal event')
  previous=row['entry_sha256']
 return {'completed':completed,'pending':pending,'terminal_failure':terminal,'next_index':len(completed),'head_sha256':previous}


def read_journal(root:Path)->list[dict]:
 path=root/'controls/journal.private.jsonl'
 if not path.exists():return []
 raw=source.private(path)
 if raw and not raw.endswith(b'\n'):raise ValueError('Incomplete prospective journal tail')
 rows=[json.loads(line) for line in raw.splitlines()];journal_state(rows);return rows


def append(root:Path,rows:list[dict],payload:dict)->dict:
 row={'schema':JOURNAL_SCHEMA,'seq':len(rows)+1,'previous_sha256':rows[-1]['entry_sha256'] if rows else '0'*64,**payload}
 row['entry_sha256']=source.sha(factory.canonical(row));raw=(json.dumps(row,sort_keys=True,separators=(',',':'))+'\n').encode()
 journal_state([*rows,row])  # Rejected operations must not corrupt the existing journal.
 path=root/'controls/journal.private.jsonl';fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
 with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
 rows.append(row);journal_state(rows);return row


def review(*,freeze_path:Path,review_path:Path,permit_path:Path,phase:str,count:int=1,root_review_accepted:bool=False,note:str='')->dict:
 if root_review_accepted is not True or not note.strip():raise ValueError('Exact independent root source acceptance and rationale required')
 value=source.validate_source(freeze_path);root=Path(value['epoch_root'])
 if phase not in ['bootstrap','controls'] or not 1<=count<=100 or any(p.exists() or p.is_symlink() or not p.is_absolute() for p in [review_path,permit_path]):
  raise ValueError('Exclusive exact prospective permit paths/scope required')
 first=0;plan_sha=None
 if phase=='bootstrap':
  if root.exists():raise ValueError('Bootstrap epoch already consumed')
 else:
  _,plan_sha,_=baseline_inputs(value,freeze_path);state=journal_state(read_journal(root))
  if state['pending'] is not None or state['terminal_failure'] or state['next_index']+count>100:raise ValueError('Next prospective range is terminal/uncertain/outside roster')
  first=state['next_index']
 binding={'source_freeze_sha256':source.sha(source.private(freeze_path)),'source_sha256s':value['source_sha256s'],'phase':phase,
  'first_index':first,'maximum_control_count':count if phase=='controls' else 0,'cohort_plan_sha256':plan_sha,
  'same_intent_replay_authorized':False,'model_calls':0,'official_final_admitted':0}
 reviewed={**binding,'schema':'envloop-gitlab-prospective100-root-review-private-v5','private_review_note':note,'reviewed_utc':source.now()}
 review_sha=source.write_new(review_path,reviewed)
 permit={**binding,'schema':PERMIT_SCHEMA,'review_path':str(review_path),'review_sha256':review_sha,'execution_authorized':True}
 permit_sha=source.write_new(permit_path,permit)
 return {'status':'exact_prospective_permit_written_no_live_mutation','private_permit_sha256':permit_sha,'phase':phase,'model_calls':0,'official_final_admitted':0}


def checked_permit(*,freeze_path:Path,permit_path:Path,value:dict,phase:str)->dict:
 permit=json.loads(source.private(permit_path));review_path=Path(permit.get('review_path',''))
 if not review_path.is_absolute():raise ValueError('Private root review absent')
 review_raw=source.private(review_path);reviewed=json.loads(review_raw)
 if (permit.get('schema')!=PERMIT_SCHEMA or permit.get('phase')!=phase or permit.get('execution_authorized') is not True or
     permit.get('source_freeze_sha256')!=source.sha(source.private(freeze_path)) or permit.get('source_sha256s')!=value['source_sha256s'] or
     permit.get('review_sha256')!=source.sha(review_raw) or not reviewed.get('private_review_note','').strip() or
     permit.get('same_intent_replay_authorized') is not False or permit.get('model_calls')!=0 or permit.get('official_final_admitted')!=0 or
     any(reviewed.get(k)!=permit.get(k) for k in ['source_freeze_sha256','source_sha256s','phase','first_index','maximum_control_count','cohort_plan_sha256'])):
  raise ValueError('Exact prospective root permit binding changed')
 if phase=='controls':
  _,plan_sha,_=baseline_inputs(value,freeze_path)
  if plan_sha!=permit['cohort_plan_sha256'] or not 1<=permit.get('maximum_control_count',0)<=100:raise ValueError('Prospective control range/baseline binding changed')
 return permit


def audit_one(*,value:dict,plan:dict,plan_sha:str,baseline:dict,index:int)->dict:
 root=Path(value['epoch_root']);run=root/'controls';folder=run/'attempts'/f'{index:03d}';identity=plan['task_roster'][index]
 trio=json.loads(source.private(folder/'trio-complete.private.json'))
 if (trio.get('schema')!=lane.TRIO_SCHEMA or trio.get('task_id')!=identity['task_id'] or trio.get('package_sha256')!=identity['package_sha256'] or
     trio.get('plan_sha256')!=plan_sha or trio.get('source_bundle_sha256')!=plan['source_bundle_sha256'] or
     trio.get('control_scores')!=[1.0,0.0,1.0] or trio.get('model_calls')!=0 or trio.get('official_final_admitted')!=0):
  raise ValueError('Prospective trio source/package/score receipt changed')
 task=gui_controls._task(identity['task_id']);generations=[];screens=0
 package={'world_sha256':plan['world_sha256'],'baseline_business_sha256':baseline['business_sha256'],
  'native_acl_sha256':plan['native_acl_sha256'],'task':task}
 if (source.sha(factory.canonical(task))!=identity['task_object_sha256'] or source.sha(factory.canonical(package))!=identity['package_sha256']):
  raise ValueError('Prospective current task/baseline/ACL package binding changed')
 for label,_variant,score in lane.CASES[identity['template_group']]:
  out=folder/label;complete=json.loads(source.private(out/'case-complete.private.json'))
  after_raw=source.private(out/'after-persisted-state.json');after=json.loads(after_raw)
  restored_raw=source.private(out/'after-reset-persisted-state.json');restored=json.loads(restored_raw)
  completion_sha=source.sha(source.private(out/'case-complete.private.json'))
  if (complete.get('plan_sha256')!=plan_sha or complete.get('task_id')!=identity['task_id'] or complete.get('expected_score')!=score or
      complete.get('schema')!=lane.CASE_SCHEMA or complete.get('case')!=label or complete.get('source_bundle_sha256')!=plan['source_bundle_sha256'] or
      complete.get('after_state_sha256')!=source.sha(after_raw) or complete.get('restored_state_sha256')!=source.sha(restored_raw) or
      complete.get('raw_receipt_sha256')!=source.sha(source.private(out/'receipt.json')) or
      {'case':label,'case_completion_sha256':completion_sha} not in trio['cases'] or restored!=baseline):
   raise ValueError('Prospective saved-state/reset/case binding changed')
  saved=copy.deepcopy(after);digest=saved.pop('business_sha256')
  if source.sha(factory.canonical(saved))!=digest:raise ValueError('Saved DB/Git state digest changed')
  verdict=verify.evaluate_final_task(task,baseline,after,inspect_live_git=False)
  if verdict.get('score')!=score or verdict.get('persisted_oracle') is not True or verdict.get('no_regression') is not (score==1.0):
   raise ValueError('Independent prospective persisted-state scorer disagrees')
  cold=complete.get('reset_receipt',{})
  if cold.get('cold_reset') is not True or cold.get('same_business_sha256') is not True or cold.get('container_identity_changed') is not True:
   raise ValueError('Prospective fresh cold-reset evidence absent')
  generations.append(cold['generation'])
  for name,digest in complete['all_gui_screenshot_sha256s'].items():
   if source.sha(source.private(out/name))!=digest:raise ValueError('Owner-only retained GUI PNG changed')
   screens+=1
 if generations!=list(range(2+3*index,5+3*index)):raise ValueError('Prospective cold reset generations are not consecutive and new')
 altered=json.loads(source.private(folder/'unrelated-change-state.private.json'))
 rechecked=verify.evaluate_final_task(task,baseline,altered,inspect_live_git=False)
 if rechecked.get('score')!=0.0 or rechecked.get('no_regression') is not False:raise ValueError('Unrelated-change penalty accepted a regression')
 probe_raw=source.private(folder/'unrelated-probe.private.json');probe=json.loads(probe_raw)
 if (trio.get('unrelated_probe_sha256')!=source.sha(probe_raw) or probe.get('schema')!=lane.PROBE_SCHEMA or
     probe.get('task_id')!=identity['task_id'] or probe.get('plan_sha256')!=plan_sha or
     probe.get('unrelated_state_sha256')!=source.sha(source.private(folder/'unrelated-change-state.private.json')) or
     probe.get('verifier_response')!=rechecked):raise ValueError('Prospective unrelated-change probe/source binding changed')
 return {'index':index,'trio_sha256':source.sha(source.private(folder/'trio-complete.private.json')),'scores':[1.0,0.0,1.0],
  'fresh_cold_resets':3,'cold_generations':generations,'owner_only_pngs':screens,'model_calls':0,'official_final_admitted':0}


def audit_prefix(*,freeze_path:Path)->dict:
 value=source.validate_source(freeze_path);root=Path(value['epoch_root'])
 if not root.exists():return {'status':'source_frozen_bootstrap_not_executed','prospective_denominator':100,'new_baseline_controls_completed':0,
  'historical_controls_transferred':0,'model_calls':0,'official_final_admitted':0}
 bootstrap_path=root/'bootstrap-receipt.private.json'
 if not bootstrap_path.exists() or json.loads(source.private(bootstrap_path)).get('status')!='new32_project_fifo_baseline_acl_exact_cold_clone_frozen':
  return {'status':json.loads(source.private(bootstrap_path)).get('status') if bootstrap_path.exists() else 'pending_bootstrap_intent_no_replay',
   'prospective_denominator':100,'new_baseline_controls_completed':0,'historical_controls_transferred':0,'model_calls':0,'official_final_admitted':0}
 plan,plan_sha,baseline=baseline_inputs(value,freeze_path);rows=read_journal(root);state=journal_state(rows);audits=[]
 with scoped.cohort_context(value):
  for entry in state['completed']:
   index=entry['task_index'];path=root/'controls/supervision'/f'{index:03d}-result.private.json'
   raw=source.private(path);result=json.loads(raw)
   if source.sha(raw)!=entry['supervisor_result_sha256'] or result.get('passed') is not True or result.get('child',{}).get('process_group_terminated') is not True:
    raise ValueError('Earlier prospective supervisor result changed')
   child=result['child'];marker=json.loads(source.private(root/'controls/supervision'/f'{index:03d}-child-started.private.json'))
   intents=[r for r in rows if r['kind']=='intent' and r['task_index']==index]
   if (len(intents)!=1 or marker.get('schema')!='envloop-gitlab-prospective100-child-started-private-v5' or
       marker.get('task_index')!=index or marker.get('parent_pid')!=intents[0]['supervisor_pid'] or
       marker.get('child_pid')!=child.get('child_pid') or marker.get('pending_intent_sha256')!=intents[0]['entry_sha256'] or
       marker.get('source_freeze_sha256')!=source.sha(source.private(freeze_path)) or marker.get('permit_sha256')!=intents[0]['permit_sha256'] or
       marker.get('same_intent_replay_authorized') is not False or
       child.get('exit_code')!=0 or child.get('timed_out') is not False or
       child.get('stdout_sha256')!=source.sha(source.private(root/'controls/supervision'/f'{index:03d}-stdout.private.log')) or
       child.get('stderr_sha256')!=source.sha(source.private(root/'controls/supervision'/f'{index:03d}-stderr.private.log'))):
    raise ValueError('Prospective one-shot child marker or retained stdout/stderr bytes changed')
   audited=audit_one(value=value,plan=plan,plan_sha=plan_sha,baseline=baseline,index=index)
   if result.get('independent_audit')!=audited:raise ValueError('Earlier prospective raw control audit changed')
   audits.append(audited)
 return {'status':'terminal_prospective_failure_no_replay' if state['terminal_failure'] else 'pending_prospective_intent_no_replay' if state['pending'] else 'new_baseline_prefix_independently_reopened',
  'prospective_denominator':100,'new_baseline_controls_completed':len(audits),'prospective_source_families':20,
  'historical_controls_transferred':0,'pending_intent':state['pending'] is not None,'terminal_failure':state['terminal_failure'],
  'model_calls':0,'official_final_admitted':0}


def child(*,freeze_path:Path,permit_path:Path,index:int,parent_pid:int)->dict:
 value=source.validate_source(freeze_path);permit=checked_permit(freeze_path=freeze_path,permit_path=permit_path,value=value,phase='controls')
 if Path(__file__).resolve().parents[1]!=Path(value['evaluator_root']) or os.getppid()!=parent_pid:raise ValueError('Cohort child must belong to original evaluator supervisor')
 plan,plan_sha,baseline=baseline_inputs(value,freeze_path);root=Path(value['epoch_root'])
 state=journal_state(read_journal(root));pending=state['pending']
 if pending is None or pending['task_index']!=index or pending.get('supervisor_pid')!=parent_pid or not permit['first_index']<=index<permit['first_index']+permit['maximum_control_count']:
  raise ValueError('Prospective child lacks exact one-use supervisor intent')
 source.write_new(root/'controls/supervision'/f'{index:03d}-child-started.private.json',{
  'schema':'envloop-gitlab-prospective100-child-started-private-v5','task_index':index,'parent_pid':parent_pid,'child_pid':os.getpid(),
  'source_freeze_sha256':source.sha(source.private(freeze_path)),'permit_sha256':source.sha(source.private(permit_path)),
  'pending_intent_sha256':pending['entry_sha256'],'created_utc':source.now(),'same_intent_replay_authorized':False})
 with scoped.cohort_context(value):
  if verify.state_snapshot()!=baseline:raise ValueError('New cohort is not at exact32-project baseline')
  result=asyncio.run(lane.live_one(plan,plan_sha,index,root/'controls',baseline))
  audited=audit_one(value=value,plan=plan,plan_sha=plan_sha,baseline=baseline,index=index)
 source.write_new(root/'controls/supervision'/f'{index:03d}-child-result.private.json',{'result':result,'audit':audited})
 return {'status':'new_baseline_prospective_trio_completed','index':index,'model_calls':0,'official_final_admitted':0}


def run(*,freeze_path:Path,permit_path:Path,max_tasks:int=1,execute:bool=False)->dict:
 if execute is not True:raise ValueError('Prospective GUI control execution is disabled')
 value=source.validate_source(freeze_path);permit=checked_permit(freeze_path=freeze_path,permit_path=permit_path,value=value,phase='controls')
 if Path(__file__).resolve().parents[1]!=Path(value['evaluator_root']):raise ValueError('Only original evaluator checkout may run prospective controls')
 if not 1<=max_tasks<=permit['maximum_control_count']:raise ValueError('Requested prospective batch exceeds exact permit')
 root=Path(value['epoch_root']);plan,plan_sha,baseline=baseline_inputs(value,freeze_path)
 audit_prefix(freeze_path=freeze_path)
 lock=os.open(root/'controls/.supervisor.lock',os.O_RDWR|os.O_CREAT,0o600);fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 try:
  rows=read_journal(root);state=journal_state(rows)
  if state['pending'] is not None or state['terminal_failure'] or state['next_index']!=permit['first_index']:raise ValueError('Prospective permit range consumed/uncertain/terminal')
  for index in range(permit['first_index'],permit['first_index']+max_tasks):
   item=plan['task_roster'][index]
   append(root,rows,{'kind':'intent','task_index':index,'task_id':item['task_id'],'package_sha256':item['package_sha256'],
    'plan_sha256':plan_sha,'permit_sha256':source.sha(source.private(permit_path)),'supervisor_pid':os.getpid(),'created_utc':source.now(),
    'same_intent_replay_authorized':False,'model_calls':0,'official_final_admitted':0})
   folder=root/'controls/supervision';argv=[sys.executable,'-m','gitlab_world.v066_prospective_cohort_controller_v5','child','--freeze',str(freeze_path),'--permit',str(permit_path),
    '--index',str(index),'--supervisor-pid',str(os.getpid()),'--execute']
   child_result=process_audit._confirm_child_process_group(supervisor.supervise_child(argv,cwd=Path(value['evaluator_root']),env=os.environ.copy(),
    stdout_path=folder/f'{index:03d}-stdout.private.log',stderr_path=folder/f'{index:03d}-stderr.private.log',timeout_seconds=7200,grace_seconds=30))
   passed=False;audited=None;cleanup=None
   try:
    if child_result.get('exit_code')!=0 or child_result.get('timed_out') is not False or child_result.get('process_group_terminated') is not True:
     raise ValueError('Prospective child failed or process group remains uncertain')
    with scoped.cohort_context(value):
     audited=audit_one(value=value,plan=plan,plan_sha=plan_sha,baseline=baseline,index=index)
     if verify.state_snapshot()!=baseline:raise ValueError('Prospective post-child32-project baseline mismatch')
    passed=True
   except Exception as exc:
    audited={'error_type':type(exc).__name__}
    if child_result.get('process_group_terminated') is True:
     try:
      with scoped.cohort_context(value):
       forensic=scoped.capture_forensics(root/'startup-forensics'/('supervisor-terminal-'+str(index)+'-'+str(__import__('time').monotonic_ns())))
       reset.reset();cleanup={'exact_baseline':verify.state_snapshot()==baseline,'forensics':forensic}
     except Exception as failure:cleanup={'exact_baseline':False,'error_type':type(failure).__name__}
   result={'schema':'envloop-gitlab-prospective100-supervised-id-private-v5','index':index,'passed':passed,
    'child':child_result,'independent_audit':audited,'cleanup':cleanup,'model_calls':0,'official_final_admitted':0}
   result_sha=source.write_new(folder/f'{index:03d}-result.private.json',result)
   append(root,rows,{'kind':'terminal','task_index':index,'passed':passed,'supervisor_result_sha256':result_sha,
    'model_calls':0,'official_final_admitted':0})
   if not passed:break
  state=journal_state(rows)
  return {'status':'terminal_prospective_control_failure_no_replay' if state['terminal_failure'] else 'new_baseline_prospective_prefix_audited',
   'new_baseline_controls_completed':len(state['completed']),'prospective_denominator':100,'historical_controls_transferred':0,'model_calls':0,'official_final_admitted':0}
 finally:fcntl.flock(lock,fcntl.LOCK_UN);os.close(lock)


def main()->None:
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['review-bootstrap','review-controls','run','child','audit-prefix'])
 parser.add_argument('--freeze',type=Path,required=True);parser.add_argument('--review-out',type=Path);parser.add_argument('--permit',type=Path)
 parser.add_argument('--accept-root-review',action='store_true');parser.add_argument('--private-review-note',default='')
 parser.add_argument('--max-tasks',type=int,default=1);parser.add_argument('--index',type=int);parser.add_argument('--supervisor-pid',type=int)
 parser.add_argument('--execute',action='store_true');args=parser.parse_args()
 if args.mode=='audit-prefix':result=audit_prefix(freeze_path=args.freeze)
 elif args.mode.startswith('review'):
  if args.review_out is None or args.permit is None:raise ValueError('Exact independent review/permit paths required')
  result=review(freeze_path=args.freeze,review_path=args.review_out,permit_path=args.permit,phase='bootstrap' if args.mode=='review-bootstrap' else 'controls',
   count=args.max_tasks,root_review_accepted=args.accept_root_review,note=args.private_review_note)
 elif args.mode=='run':
  if args.permit is None:raise ValueError('Exact control permit required')
  result=run(freeze_path=args.freeze,permit_path=args.permit,max_tasks=args.max_tasks,execute=args.execute)
 else:
  if not args.execute or args.permit is None or args.index is None or args.supervisor_pid is None:raise ValueError('Exact supervised child execution required')
  result=child(freeze_path=args.freeze,permit_path=args.permit,index=args.index,parent_pid=args.supervisor_pid)
 print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
