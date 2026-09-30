"""Fresh all120 control epoch after immutable zero-create v9 constructor stop.

Same source cohort and v9 transport/budgets; no selection-family retirement.
Only additive selection-aware script construction changes. Metadata/layout
readiness precedes every new intent; final answer files remain sealed there.
"""
from __future__ import annotations

from datetime import datetime,timezone
import argparse
import json
from pathlib import Path

from . import v066_post_enter_epoch_v9 as parent
from . import selection_control_scripts_v10 as scripts
from . import factory as base


SCHEMA='cua-native-wdi-selection-constructor-successor-private-v10'
PUBLIC_SCHEMA='cua-native-wdi-selection-constructor-successor-public-v10'
PERMIT_SCHEMA='cua-native-wdi-selection-constructor-successor-one-id-permit-v10'
SOURCE_FILES=(*parent.SOURCE_FILES,'native_desktop_factory/selection_control_scripts_v10.py',
 'native_desktop_factory/selection_control_successor_epoch_v10.py','native_desktop_factory/selection_control_successor_worker_v10.py',
 'tests/test_desktop_selection_constructor_v10.py')
MAX_ACTIONS=parent.MAX_ACTIONS
ACTOR_WALL_SECONDS=parent.ACTOR_WALL_SECONDS
LEASE_SECONDS=parent.LEASE_SECONDS
accounting=parent.accounting
private=parent.private
require=parent.require


def source_hashes():
 root=Path(__file__).resolve().parents[1]
 return {name:base.digest((root/name).read_bytes()) for name in SOURCE_FILES}


def audit_precreate_stop(*,parent_freeze:Path,dispatch_root:Path)->dict:
 raw=private(parent_freeze);value=json.loads(raw);root=Path(value['attempts_root']);row=value['roster'][0]
 paths=sorted(root.glob('*/trio-started.json'));intents=sorted(root.glob('*/*/intent.json'))
 require(len(paths)==len(intents)==1 and paths[0].parent.name==row['task_id'] and intents[0].parent.name=='positive','v10_exact_one_precreate_intent_required')
 started=json.loads(private(paths[0]));intent=json.loads(private(intents[0]));terminal=json.loads(private(dispatch_root/'worker-terminal.private.json'))
 stderr=private(dispatch_root/'worker.stderr.private.log')
 require(started.get('source_freeze_sha256')==intent.get('source_freeze_sha256')==base.digest(raw) and
  intent.get('package_sha256')==row['package_sha256'] and intent.get('split')=='selection' and intent.get('lease_seconds')==1200 and
  terminal.get('exit_code')==1 and b'Calc v2 must have three decision-ledger targets' in stderr and
  not any(root.rglob('child-started.json')) and not any(root.rglob('receipt.json')) and not any(root.rglob('*.png')),
  'v10_constructor_stop_not_before_provider_boundary')
 manifest={str(path.relative_to(root)):base.digest(private(path)) for path in root.rglob('*') if path.is_file()}
 dispatch_manifest={str(path.relative_to(dispatch_root)):base.digest(private(path)) for path in dispatch_root.rglob('*') if path.is_file()}
 return {'schema':'cua-native-wdi-v9-precreate-constructor-forensic-private-v10','status':'constructor_failed_before_child_marker_and_provider_create',
  'parent_freeze_sha256':base.digest(raw),'original_attempt_root':str(root),'dispatch_root':str(dispatch_root),
  'original_attempt_metadata_sha256s':manifest,'original_dispatch_metadata_sha256s':dispatch_manifest,
  'parent_task_metadata':row,'intents_consumed':1,'conservative_full_lease_seconds_retained':1200,
  'actual_provider_creates':0,'actual_provider_billed_usd':None,'provider_create_not_reached_by_frozen_traceback':True,
  'same_intent_replay_authorized':False,'selection_family_retired_for_constructor_bug':False,
  'model_calls':0,'official_final_admissions':0}


def metadata_parent(parent_freeze:Path)->dict:
 raw=private(parent_freeze);value=json.loads(raw)
 require(value.get('schema')==parent.SCHEMA and value.get('source_sha256s')==parent.source_hashes() and
  value.get('cohort_counts')=={'train':20,'selection':20,'final_candidate':100} and len(value.get('roster',[]))==120,
  'v10_original_v9_source_or_roster_changed')
 for path,sha in value['bindings'].items():require(base.digest(Path(path).read_bytes())==sha,'v10_original_v9_input_binding_changed')
 # Parent's trusted reserve authoring/source audit is already frozen. Do not
 # re-open reserve/other selection oracles for successor metadata planning.
 parent.checked_train(Path(value['v6_public']),Path(value['v8_public']))
 parent.validate_reference(Path(value['scoped_reference']));parent.validate_ratification(Path(value['ratification']))
 return value


def prepare(*,parent_freeze:Path,dispatch_root:Path,attempts_root:Path,freeze_path:Path,public_path:Path)->dict:
 require(not any(path.exists() or path.is_symlink() for path in [attempts_root,freeze_path,public_path]),'v10_exclusive_successor_paths_required')
 old=metadata_parent(parent_freeze);forensic=audit_precreate_stop(parent_freeze=parent_freeze,dispatch_root=dispatch_root)
 readiness=scripts.metadata_readiness(Path(old['candidate_root']))
 # Only the already-opened current oracle is inspected, never other gold.
 current=old['roster'][0];directory=Path(old['candidate_root'])/current['split']/current['task_id']
 oracle=json.loads(private(directory/'oracle.json'))
 current_grammar={attempt:base.digest(scripts.actor_script(directory,oracle,attempt).encode()) for attempt in ['positive','near-miss','cold-reset']}
 forensic_path=freeze_path.parent/'precreate-forensic.private.json';ready_path=freeze_path.parent/'selection-layout-readiness.private.json'
 forensic_sha=accounting._write_new(forensic_path,forensic);ready_sha=accounting._write_new(ready_path,{**readiness,'current_task_script_sha256s':current_grammar})
 ledger=accounting.lease_accounting([Path(p) for p in old['accounting_roots']],exclude=attempts_root)
 value={**old,'schema':SCHEMA,'status':'fresh_all120_after_precreate_constructor_stop_no_dispatch',
  'created_utc':datetime.now(timezone.utc).isoformat(),'parent_freeze_path':str(parent_freeze),'parent_freeze_sha256':base.digest(private(parent_freeze)),
  'forensic_path':str(forensic_path),'forensic_sha256':forensic_sha,'readiness_path':str(ready_path),'readiness_sha256':ready_sha,
  'source_sha256s':source_hashes(),'frozen_v9_source_sha256s':old['source_sha256s'],
  'public_path':str(public_path),'attempts_root':str(attempts_root),'historical_full_lease_accounting':ledger,
  'original_root_replay_authorized':False,'historical_controls_carried_into_new_epoch':0,'dispatch_authorized':False}
 accounting._write_new(freeze_path,value)
 public={'schema':PUBLIC_SCHEMA,'status':value['status'],'private_freeze_sha256':base.digest(private(freeze_path)),
  'source_sha256s':value['source_sha256s'],'parent_freeze_sha256':value['parent_freeze_sha256'],
  'precreate_forensic_sha256':forensic_sha,'selection_layout_readiness_sha256':ready_sha,
  'cohort_counts':old['cohort_counts'],'source_family_counts':old['source_family_counts'],
  'selection_layouts_checked':20,'actual_selection_targets_per_profile':2,'one_target_analogue_profiles_supported':True,
  'historical_final_three_target_script_unchanged':True,'constructor_bug_family_retirements':0,
  'original_precreate_intents_retained':1,'original_actual_provider_creates':0,'actual_provider_billed_usd':None,
  'historical_full_lease_intents':ledger['past_full_lease_intents'],'maximum_new_full_lease_intents':360,
  'lease_seconds_each':1200,'new_full_lease_seconds':432000,'new_planning_usd_upper':'120','lane_spending_cap_usd':None,
  'max_actor_actions':90,'max_actor_wall_seconds':720,'original_root_replay_authorized':False,
  'same_intent_replay_authorized':False,'dispatch_authorized':False,'model_calls':0,'official_final_admissions':0}
 accounting._write_new(public_path,public,public=True);return public


def validate(freeze_path:Path)->dict:
 raw=private(freeze_path);value=json.loads(raw)
 require(value.get('schema')==SCHEMA and value.get('source_sha256s')==source_hashes() and value.get('frozen_v9_source_sha256s')==parent.source_hashes() and
  value.get('maximum_new_full_lease_intents')==360 and value.get('lease_seconds_each')==1200 and value.get('max_actor_actions')==90 and
  value.get('max_actor_wall_seconds')==720 and value.get('dispatch_authorized') is False,'v10_successor_source_or_budget_changed')
 old=metadata_parent(Path(value['parent_freeze_path']))
 require(base.digest(private(Path(value['parent_freeze_path'])))==value['parent_freeze_sha256'] and old['roster']==value['roster'] and
  value['attempts_root']!=old['attempts_root'],'v10_parent_or_fresh_root_boundary_changed')
 forensic=json.loads(private(Path(value['forensic_path'])));readiness=json.loads(private(Path(value['readiness_path'])))
 require(base.digest(private(Path(value['forensic_path'])))==value['forensic_sha256'] and
  audit_precreate_stop(parent_freeze=Path(value['parent_freeze_path']),dispatch_root=Path(forensic['dispatch_root']))==forensic,
  'v10_precreate_terminal_record_changed')
 require(base.digest(private(Path(value['readiness_path'])))==value['readiness_sha256'] and
  scripts.metadata_readiness(Path(value['candidate_root']))=={k:v for k,v in readiness.items() if k!='current_task_script_sha256s'},'v10_selection_layout_preflight_changed')
 require(accounting.lease_accounting([Path(p) for p in value['accounting_roots']],exclude=Path(value['attempts_root']))==value['historical_full_lease_accounting'],
  'v10_historical_intents_or_lease_metadata_changed')
 public=json.loads(Path(value['public_path']).read_bytes())
 require(public.get('private_freeze_sha256')==base.digest(raw) and public.get('source_sha256s')==value['source_sha256s'] and public.get('dispatch_authorized') is False,'v10_public_source_binding_changed')
 return {**value,'_freeze_sha256':base.digest(raw)}


def next_row(value):
 from .selection_control_successor_worker_v10 import context
 with context():return parent.next_row(value)
def checked_inflight(value,row,attempt):
 from .selection_control_successor_worker_v10 import context
 with context():return parent.checked_inflight(value,row,attempt)
def checked_permit(freeze_path,permit_path,value,row):
 permit=json.loads(private(permit_path))
 require(permit.get('schema')==PERMIT_SCHEMA and permit.get('freeze_sha256')==base.digest(private(freeze_path)) and
  permit.get('source_sha256s')==value['source_sha256s'] and permit.get('task_id')==row['task_id'] and permit.get('package_sha256')==row['package_sha256'] and
  permit.get('split')==row['split'] and permit.get('attempts')==['positive','near-miss','cold-reset'] and permit.get('maximum_new_intents')==3 and
  permit.get('provider_active_zero_at_review') is True and permit.get('same_intent_replay_authorized') is False,'v10_exact_fresh_trio_permit_changed')
 return permit
def review(*,freeze_path:Path,permit_path:Path):
 from .reconcile_interrupted_sweep import active_hashes
 value=validate(freeze_path);row=next_row(value);require(row is not None,'v10_all120_complete')
 active,count=active_hashes();require(not active and count==0,'v10_review_requires_provider_active_zero')
 permit={'schema':PERMIT_SCHEMA,'freeze_sha256':base.digest(private(freeze_path)),'source_sha256s':value['source_sha256s'],
  'task_id':row['task_id'],'package_sha256':row['package_sha256'],'split':row['split'],'attempts':['positive','near-miss','cold-reset'],
  'maximum_new_intents':3,'provider_active_zero_at_review':True,'same_intent_replay_authorized':False,'official_final_admissions':0,'official_model_results':0}
 accounting._write_new(permit_path,permit);return {'status':'fresh_successor_one_trio_reviewed_no_create','official_final_admissions':0}


def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['prepare','plan','review']);parser.add_argument('--freeze',type=Path,required=True)
 for name in ['parent-freeze','dispatch-root','attempts-root','public','permit']:parser.add_argument('--'+name,type=Path)
 args=parser.parse_args()
 if args.mode=='prepare':result=prepare(parent_freeze=args.parent_freeze,dispatch_root=args.dispatch_root,attempts_root=args.attempts_root,freeze_path=args.freeze,public_path=args.public)
 elif args.mode=='review':result=review(freeze_path=args.freeze,permit_path=args.permit)
 else:
  value=validate(args.freeze);row=next_row(value);result={'status':'fresh_successor_metadata_ready_no_dispatch','next_split':None if row is None else row['split'],'official_final_admissions':0}
 print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
