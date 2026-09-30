"""Source-frozen FIFO bootstrap and prospective100 epoch; offline by default.

Preparation consumes roster/recipe metadata and closed source hashes only.
Actor prompts/oracles are removed from its world view. Existing final-answer
packages and GUI controls are never opened during preparation.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re

from . import factory,pre_result_recovery as fifo,v066_infra_recovery_v4 as recovery


SCHEMA='envloop-gitlab-prospective100-source-freeze-private-v5'
PUBLIC_SCHEMA='envloop-gitlab-prospective100-source-freeze-public-v5'
RECIPE_SCHEMA='envloop-gitlab-fifo-bootstrap-recipe-private-v5'
SOURCE_FILES=(
 'gitlab_world/v066_prospective_cohort_v5.py','gitlab_world/v066_prospective_cohort_runtime_v5.py',
 'gitlab_world/v066_prospective_cohort_controller_v5.py','tests/test_gitlab_prospective_cohort_v5.py',
 'gitlab_world/bootstrap.py','gitlab_world/pre_result_recovery.py','gitlab_world/factory.py',
 'gitlab_world/runtime.py','gitlab_world/reset.py','gitlab_world/operators.py','gitlab_world/operator_acl_probe.py',
 'gitlab_world/verify.py','gitlab_world/gui_controls.py','gitlab_world/gui_workflows.py',
 'gitlab_world/prospective_final_controls_v066.py','gitlab_world/v066_supervised_final_one_v1.py',
 'gitlab_world/v066_infra_requalification_v1.py','gitlab_world/v066_boot_only_probe_v5.py',
 'tools/audit_gitlab_final_candidate_preflight_v1.py')
TASK_METADATA_KEYS=('task_id','partition','source_family','project_family','entity_group','template_group')
PROJECT_METADATA_KEYS=('index','partition','full_path','group_path','source_family','asset_id','principals','advisories')
BOUND_FILES=(
 'world-private.json','world-seed.txt','cisa-kev-pinned.json','baseline-persisted-state.json',
 'bootstrap-progress.json','operator-bootstrap-private.json','cow-reset-state.json','active-volume-version.txt',
 'v066-infra-recovery-v4-20260929/source-plan.private.json',
 'v066-prospective-final-controls-20260928/plan.private.json',
 'v066-infra-requalification-branch-v3-20260929/journal.private.jsonl',
 'v066-infra-requalification-branch-v3-20260929/continuation-v1-20260929/batches/journal.private.jsonl',
 'v066-new-train-diagnostic-v7-20260930/interruption-reconciliation.private.json',
 'v066-new-train-diagnostic-v7-20260930/intent.private.json',
 'v066-new-train-diagnostic-v7-20260930/child-result.private.json')


def sha(raw:bytes)->str:return hashlib.sha256(raw).hexdigest()
def now()->str:return datetime.now(timezone.utc).isoformat()
def encode(value)->bytes:return (json.dumps(value,sort_keys=True,indent=2)+'\n').encode()
def private(path:Path)->bytes:
 if not path.is_file() or path.is_symlink() or path.stat().st_mode&0o077:raise ValueError('Private metadata absent or unsafe')
 return path.read_bytes()
def write_new(path:Path,value,mode=0o600)->str:
 path.parent.mkdir(parents=True,mode=0o700,exist_ok=True)
 if mode==0o600:path.parent.chmod(0o700)
 raw=encode(value);fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,mode)
 with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
 parent=os.open(path.parent,os.O_RDONLY)
 try:os.fsync(parent)
 finally:os.close(parent)
 return sha(raw)
def persist(path:Path,value)->None:
 temporary=path.with_name(path.name+'.next');raw=encode(value)
 with temporary.open('wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
 temporary.chmod(0o600);os.replace(temporary,path)
def source_hashes()->dict:
 root=Path(__file__).resolve().parents[1]
 return {name:sha((root/name).read_bytes()) for name in SOURCE_FILES}


def metadata_world(raw:bytes)->dict:
 def discard_answers(value):
  return {k:v for k,v in value.items() if k not in {'prompt','oracle','gold','actor_task','answer','expected_answer'}}
 world=json.loads(raw,object_hook=discard_answers)
 return {'schema':world['schema'],'world_seed_sha256':world['world_seed_sha256'],
  'projects':[{k:p[k] for k in PROJECT_METADATA_KEYS} for p in world['projects']],
  'reserve_projects':[{k:p[k] for k in PROJECT_METADATA_KEYS} for p in world.get('reserve_projects',[])],
  'tasks':[{k:t[k] for k in TASK_METADATA_KEYS} for t in world['tasks']],
  'reserve_tasks':[{k:t[k] for k in TASK_METADATA_KEYS} for t in world.get('reserve_tasks',[])]}


def validate_roster(rows:list[dict],retired:list[dict])->dict:
 families=Counter(row['source_family_sha256'] for row in rows)
 if (len(rows)!=100 or len({r['task_id'] for r in rows})!=100 or len(families)!=20 or set(families.values())!={5} or
     {r['task_id'] for r in rows}&{r['task_id'] for r in retired}):
  raise ValueError('Prospective denominator must be100 distinct tasks in20 complete families without retired tasks')
 if [i for i,r in enumerate(rows) if r['provenance']=='first_precommitted_fifo_reserve_family']!=list(range(10,15)):
  raise ValueError('Only whole-family FIFO replacement at indices10 through14 is allowed')
 workflows=Counter(r['template_group'] for r in rows)
 if len(workflows)!=5 or set(workflows.values())!={20}:raise ValueError('Prospective five-workflow matrix changed')
 return {'tasks':100,'source_families':20,'workflows':5}


def inputs(*,evaluator_root:Path,mirror_root:Path)->tuple[dict,dict]:
 original=evaluator_root/'work/gitlab-full-world'
 v4_path=original/'v066-infra-recovery-v4-20260929/source-plan.private.json'
 old_path=original/'v066-prospective-final-controls-20260928/plan.private.json'
 v4=json.loads(private(v4_path));old=json.loads(private(old_path))
 if (v4.get('schema')!=recovery.PRIVATE_SCHEMA or v4.get('retired_family_original_indices')!=list(range(10,15)) or
     v4.get('official_final_admitted')!=0 or v4.get('model_calls')!=0 or v4.get('same_identity_replay_authorized') is not False):
  raise ValueError('Original FIFO retirement metadata changed')
 for relative,field in [
  ('v066-infra-requalification-branch-v3-20260929/journal.private.jsonl','terminal_branch_journal_sha256'),
  ('v066-infra-requalification-branch-v3-20260929/continuation-v1-20260929/batches/journal.private.jsonl','terminal_batch_journal_sha256')]:
  if sha(private(original/relative))!=v4[field]:raise ValueError('Original terminal index13 journal changed')
 world_raw=private(original/'world-private.json')
 if sha(world_raw)!=old['world_sha256']:raise ValueError('Closed original world source bytes changed')
 world=metadata_world(world_raw);seed=private(original/'world-seed.txt').decode().strip()
 # Reconstruct committed reserve from source metadata. Generator answer fields
 # are used only as opaque commitment bytes and are discarded from the recipe.
 queue=fifo.ordered_queue(seed,world,fifo.load_catalog(original/'cisa-kev-pinned.json'))
 if queue['queue_sha256']!=v4['fifo_queue_sha256']:raise ValueError('FIFO source recipe no longer matches pre-result commitment')
 first=queue['ordered_families'][0]
 proposed=recovery.replacement_roster(old['task_roster'],first)
 if proposed['candidate_roster']!=v4['candidate_roster'] or sha(factory.canonical(proposed['candidate_roster']))!=v4['candidate_roster_sha256']:
  raise ValueError('Frozen prospective100 roster changed')
 retired=[old['task_roster'][i] for i in range(10,15)]
 validate_roster(v4['candidate_roster'],retired)
 v7_public=mirror_root/'docs/evidence/gitlab-v066-v7-interruption-reconciled-2026-09-30.json'
 published=json.loads(v7_public.read_bytes())
 reconciliation_path=original/'v066-new-train-diagnostic-v7-20260930/interruption-reconciliation.private.json'
 reconciliation=json.loads(private(reconciliation_path))
 if (published.get('saved_child_case_scores')!=[1.0,0.0,1.0] or published.get('separate_reconciliation_executed') is not True or
     published.get('same_intent_replay_authorized') is not False or published.get('official_final_admitted')!=0 or
     published.get('success_claim_authorized') is not False or
     published.get('separate_reconciliation_receipt_sha256')!=sha(private(reconciliation_path)) or
     reconciliation.get('saved_child_case_scores')!=[1.0,0.0,1.0] or reconciliation.get('live_exact_baseline_at_reconciliation') is not True):
  raise ValueError('TRAIN child terminal/reconciliation boundary is incomplete')
 reset_metadata=json.loads(private(original/'cow-reset-state.json'))
 lower=reset_metadata['seed_volume_lowerdirs']
 if set(lower)!={'config','logs','data'} or any(not str(p).startswith('/var/lib/docker/volumes/') or not str(p).endswith('/_data') for p in lower.values()):
  raise ValueError('Immutable original seed lowerdirs are not validated named-volume paths')
 recipe={'schema':RECIPE_SCHEMA,'fifo_ordinal':1,'fifo_queue_sha256':queue['queue_sha256'],
  'project':first['project'],'project_recipe_sha256':sha(factory.canonical(first['project'])),
  'task_metadata':[{**{k:t[k] for k in TASK_METADATA_KEYS},'task_object_sha256':sha(factory.canonical(t))} for t in first['tasks']],
  'task_prompts_or_oracles_exported':False,'bootstrap_project_count':1,'new_principals':4,
  'repository_files':len(first['project']['files']),'issues':len(first['project']['issues']),'merge_requests':2,
  'direct_member_levels':{'oncall':30,'contractor':20,'observer':10}}
 bound={}
 for name in BOUND_FILES:
  path=original/name
  raw=path.read_bytes() if name=='cisa-kev-pinned.json' else private(path)
  bound[str(path)]=sha(raw)
 bound[str(v7_public)]=sha(v7_public.read_bytes())
 baseline=json.loads(private(original/'baseline-persisted-state.json'))
 if baseline['business_sha256']!=old['baseline_business_sha256'] or len(baseline['project_ids'])!=31:
  raise ValueError('Original31-project baseline metadata changed')
 metadata={'evaluator_root':str(evaluator_root),'original_private_root':str(original),
  'bound_metadata_sha256s':bound,'candidate_roster':v4['candidate_roster'],'candidate_roster_sha256':v4['candidate_roster_sha256'],
  'retired_original_indices':list(range(10,15)),'retired_task_metadata':retired,'historical_retained_controls':10,
  'old_terminal_failed_index':13,'old_terminal_controls_preserved':13,'fifo_queue_sha256':queue['queue_sha256'],
  'original_world_sha256':sha(world_raw),'original_baseline_sha256':sha(private(original/'baseline-persisted-state.json')),
  'original_baseline_business_sha256':baseline['business_sha256'],'original_seed_lowerdirs':lower,
  'v7_reconciliation_sha256':sha(private(reconciliation_path)),'v7_public_reconciliation_sha256':sha(v7_public.read_bytes())}
 return metadata,recipe


def prepare(*,evaluator_root:Path,mirror_root:Path,epoch_root:Path,freeze_path:Path,public_path:Path)->dict:
 if (not all(p.is_absolute() for p in [evaluator_root,mirror_root,epoch_root,freeze_path,public_path]) or
     any(p.exists() or p.is_symlink() for p in [epoch_root,freeze_path,public_path]) or
     epoch_root.parent!=evaluator_root/'work/gitlab-full-world'):
  raise ValueError('Exclusive absolute prospective epoch/source paths required')
 metadata,recipe=inputs(evaluator_root=evaluator_root,mirror_root=mirror_root)
 recipe_path=freeze_path.parent/'fifo-bootstrap-recipe.private.json'
 recipe_sha=write_new(recipe_path,recipe)
 source=source_hashes();tag=sha(factory.canonical({'roster':metadata['candidate_roster_sha256'],'source':source,'recipe':recipe_sha}))[:12]
 value={**metadata,'schema':SCHEMA,'status':'source_frozen_no_live_mutation','created_utc':now(),'source_sha256s':source,
  'epoch_root':str(epoch_root),'public_path':str(public_path),'recipe_path':str(recipe_path),'recipe_sha256':recipe_sha,
  'clone_container_name':'envloop-gitlab-prospective-'+tag,'clone_volume_names':{r:'envloop-gitlab-prospective-'+tag+'-'+r for r in ['config','logs','data']},
  'clone_vm_root':'/var/lib/envloop-gitlab-prospective-'+tag,'clone_host_port':8016,
  'new_project_count':32,'new_control_count':100,'fixed_case_scores':[1.0,0.0,1.0],'fresh_resets_per_task':3,
  'historical_controls_transferred_to_new_baseline':0,'bootstrap_authorized':False,'task_dispatch_authorized':False,
  'reserve_project_bootstrapped':False,'new_baseline_and_acl_frozen':False,
  'same_intent_replay_authorized':False,'model_calls':0,'official_final_admitted':0}
 freeze_sha=write_new(freeze_path,value)
 public={'schema':PUBLIC_SCHEMA,'status':'prospective100_executable_source_frozen_no_live_mutation','private_freeze_sha256':freeze_sha,
  'source_sha256s':source,'recipe_sha256':recipe_sha,'fifo_queue_sha256':metadata['fifo_queue_sha256'],
  'candidate_roster_sha256':metadata['candidate_roster_sha256'],'prospective_tasks':100,'source_families':20,
  'retired_original_indices':list(range(10,15)),'retained_historical_controls':10,'historical_controls_transferred':0,
  'existing_projects':31,'new_projects':1,'new_baseline_projects':32,'planned_case_scores':[1.0,0.0,1.0],
  'planned_exact_cold_resets_per_task':3,'v7_public_reconciliation_sha256':metadata['v7_public_reconciliation_sha256'],
  'v7_private_reconciliation_sha256':metadata['v7_reconciliation_sha256'],'original_seed_and_runtime_mutation_authorized':False,
  'separate_clone_port':8016,'metadata_only_preparation':True,'final_answer_files_opened':0,
  'reserve_project_bootstrapped':False,'new_baseline_and_acl_frozen':False,'native_cohort_controls_completed':0,
  'bootstrap_authorized':False,'task_dispatch_authorized':False,'same_intent_replay_authorized':False,
  'provider_calls':0,'model_calls':0,'official_final_admitted':0}
 write_new(public_path,public,0o644);return public


def validate_source(freeze_path:Path)->dict:
 raw=private(freeze_path);value=json.loads(raw)
 if (value.get('schema')!=SCHEMA or value.get('status')!='source_frozen_no_live_mutation' or value.get('source_sha256s')!=source_hashes() or
     value.get('bootstrap_authorized') is not False or value.get('task_dispatch_authorized') is not False or
     value.get('same_intent_replay_authorized') is not False or value.get('new_project_count')!=32 or value.get('new_control_count')!=100 or
     value.get('model_calls')!=0 or value.get('official_final_admitted')!=0):raise ValueError('Prospective source/denominator/execution boundary changed')
 match=re.fullmatch('envloop-gitlab-prospective-([0-9a-f]{12})',value.get('clone_container_name',''))
 if (not match or value.get('clone_host_port')!=8016 or not re.fullmatch('/var/lib/envloop-gitlab-prospective-[0-9a-f]{12}',value.get('clone_vm_root','')) or
     set(value.get('clone_volume_names',{}))!={'config','logs','data'} or
     any(not re.fullmatch('envloop-gitlab-prospective-[0-9a-f]{12}-'+role,name) for role,name in value['clone_volume_names'].items())):
  raise ValueError('Clone-only volume/VM namespace or separate port changed')
 if value['clone_vm_root']!='/var/lib/'+value['clone_container_name'] or any(name!=value['clone_container_name']+'-'+role for role,name in value['clone_volume_names'].items()):
  raise ValueError('Clone-only namespace tags must be identical')
 for path,digest in value['bound_metadata_sha256s'].items():
  if sha(Path(path).read_bytes())!=digest:raise ValueError('Original sealed metadata/terminal bytes changed')
 if sha(private(Path(value['recipe_path'])))!=value['recipe_sha256']:raise ValueError('Exact FIFO bootstrap recipe changed')
 validate_roster(value['candidate_roster'],value['retired_task_metadata'])
 public=json.loads(Path(value['public_path']).read_bytes())
 if public.get('private_freeze_sha256')!=sha(raw) or public.get('source_sha256s')!=value['source_sha256s'] or public.get('task_dispatch_authorized') is not False:
  raise ValueError('Public prospective source freeze changed')
 return value


def main()->None:
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['prepare','validate','bootstrap'])
 parser.add_argument('--freeze',type=Path,required=True);parser.add_argument('--evaluator-root',type=Path);parser.add_argument('--mirror-root',type=Path)
 parser.add_argument('--epoch-root',type=Path);parser.add_argument('--public-out',type=Path);parser.add_argument('--permit',type=Path)
 parser.add_argument('--execute-reviewed-bootstrap',action='store_true');args=parser.parse_args()
 if args.mode=='prepare':
  if not all([args.evaluator_root,args.mirror_root,args.epoch_root,args.public_out]):raise ValueError('Exact evaluator/source/epoch/public paths required')
  result=prepare(evaluator_root=args.evaluator_root,mirror_root=args.mirror_root,epoch_root=args.epoch_root,freeze_path=args.freeze,public_path=args.public_out)
 elif args.mode=='validate':validate_source(args.freeze);result={'status':'source_frozen_no_live_mutation','private_freeze_sha256':sha(private(args.freeze))}
 else:
  from .v066_prospective_cohort_runtime_v5 import bootstrap_clone
  result=bootstrap_clone(freeze_path=args.freeze,permit_path=args.permit,execute=args.execute_reviewed_bootstrap)
 print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
