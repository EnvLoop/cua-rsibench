"""Metadata-only full100 successor after the consumed v5 reset failure.

Retire/refill the complete affected five-task family from the precommitted FIFO
queue. Old source/history/seeds remain immutable; no old intent is replayed.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import re
from . import factory,pre_result_recovery as fifo
from . import v066_prospective_cohort_v5 as parent_source
from . import v066_prospective_cohort_controller_v5 as parent_controller

sha=parent_source.sha;private=parent_source.private;write_new=parent_source.write_new
persist=parent_source.persist;now=parent_source.now;metadata_world=parent_source.metadata_world
SCHEMA='envloop-gitlab-prospective100-source-freeze-private-v6'
PUBLIC_SCHEMA='envloop-gitlab-prospective100-source-freeze-public-v6'
SVWAIT_SECONDS=60
NEW_FILES=('gitlab_world/v066_prospective_cohort_v6.py','gitlab_world/v066_prospective_cohort_runtime_v6.py',
 'gitlab_world/v066_prospective_cohort_controller_v6.py','gitlab_world/v066_prospective_v5_terminal_forensic.py',
 'tests/test_gitlab_prospective_cohort_v6.py','tests/test_gitlab_prospective_v5_terminal_forensic.py',
 'docs/FULL_STUDY_GITLAB_V6_POST_POSITIVE_RESET_SUCCESSOR_2026-09-30.md')
SOURCE_FILES=tuple(dict.fromkeys(parent_source.SOURCE_FILES+NEW_FILES))


def source_hashes():
 root=Path(__file__).resolve().parents[1]
 return {name:sha((root/name).read_bytes()) for name in SOURCE_FILES}


def validate_roster(rows,retired):
 families=Counter(row['source_family_sha256'] for row in rows)
 if (len(rows)!=100 or len({r['task_id'] for r in rows})!=100 or len(families)!=20 or set(families.values())!={5} or
     {r['task_id'] for r in rows}&{r['task_id'] for r in retired}):
  raise ValueError('Successor requires100 distinct tasks in20 complete families without retired identities')
 expected={'second_precommitted_fifo_reserve_family':list(range(0,5)),
           'first_precommitted_fifo_reserve_family':list(range(10,15))}
 for provenance,indices in expected.items():
  if [i for i,r in enumerate(rows) if r['provenance']==provenance]!=indices:raise ValueError('Two exact whole-family FIFO replacements required')
 if any(r['provenance'] not in {*expected,'original_roster'} for r in rows):raise ValueError('Unknown successor task provenance')
 workflows=Counter(r['template_group'] for r in rows)
 if len(workflows)!=5 or set(workflows.values())!={20}:raise ValueError('Successor five-workflow matrix changed')
 return {'tasks':100,'source_families':20,'workflows':5}


def replacement_roster(parent_rows,next_family):
 retired=parent_rows[:5];by_workflow={t['template_group']:t for t in next_family['tasks']}
 if len(by_workflow)!=5 or set(by_workflow)!={r['template_group'] for r in retired}:raise ValueError('Next FIFO family must contain all five workflows')
 new=[]
 for row in retired:
  t=by_workflow[row['template_group']]
  if t['partition']!='final_candidate_unsealed':raise ValueError('FIFO reserve partition changed')
  new.append({'task_id':t['task_id'],'template_group':t['template_group'],'source_family_sha256':factory.sha256(t['source_family']),
              'task_object_sha256':sha(factory.canonical(t)),'package_sha256':None,'provenance':'second_precommitted_fifo_reserve_family'})
 if (len({r['source_family_sha256'] for r in new})!=1 or
     new[0]['source_family_sha256'] in {r['source_family_sha256'] for r in parent_rows} or
     {r['task_id'] for r in new}&{r['task_id'] for r in parent_rows}):raise ValueError('Next FIFO source/identity overlaps parent roster')
 return new+parent_rows[5:],retired


def checked_parent(parent_freeze,terminal_review):
 parent=parent_source.validate_source(parent_freeze)
 root=Path(parent['epoch_root']);state=parent_controller.journal_state(parent_controller.read_journal(root))
 if [r['task_index'] for r in state['completed']]!=[0,1,2] or state['terminal_failure'] is not True or state['pending'] is not None:
  raise ValueError('Successor requires exact consumed three-pass v5 terminal epoch')
 prefix={'status':'terminal_prospective_failure_no_replay','prospective_denominator':100,'new_baseline_controls_completed':3,'prospective_source_families':20,'historical_controls_transferred':0,'pending_intent':False,'terminal_failure':True,'model_calls':0,'official_final_admitted':0}
 review_raw=private(terminal_review);review=json.loads(review_raw)
 if (review.get('schema')!='envloop-gitlab-prospective-v5-terminal-independent-private-v1' or
     review.get('auditor_source_sha256')!=sha((Path(__file__).resolve().parent/'v066_prospective_v5_terminal_forensic.py').read_bytes()) or review.get('source_freeze_sha256')!=sha(private(parent_freeze)) or review.get('failed_index')!=3 or
     review.get('prefix')!=prefix or review.get('failed_positive_completion_claim') is not False or
     review.get('same_intent_replay_authorized') is not False or
     review.get('cause',{}).get('uniform_svwait_60_empirically_validated') is not False):
  raise ValueError('Independent v5 terminal review binding changed')
 manifest=review.get('epoch_file_sha256s',{})
 actual={str(p.relative_to(root)):sha(private(p)) for p in sorted(root.rglob('*')) if p.is_file()}
 if not manifest or actual!=manifest:raise ValueError('Original v5 saved epoch tree changed')
 plan_raw=private(root/'cohort-plan.private.json');plan=json.loads(plan_raw);plan_sha=sha(plan_raw)
 baseline_raw=private(root/'baseline-persisted-state.json');baseline=json.loads(baseline_raw)
 receipt=json.loads(private(root/'bootstrap-receipt.private.json'))
 if plan.get('source_freeze_sha256')!=sha(private(parent_freeze)) or plan.get('source_sha256s')!=parent['source_sha256s'] or plan.get('baseline_sha256')!=sha(baseline_raw) or receipt.get('cohort_plan_sha256')!=plan_sha or len(baseline.get('project_ids',[]))!=32:
  raise ValueError('Closed parent32 baseline/plan/source metadata changed')
 if plan_sha!=review.get('plan_sha256') or review['journal_sha256']!=sha(private(root/'controls/journal.private.jsonl')):
  raise ValueError('V5 terminal plan/journal changed')
 return parent,plan,baseline,manifest


def prepare(*,parent_freeze,terminal_review,epoch_root,freeze_path,public_path):
 if not all(p.is_absolute() for p in [parent_freeze,terminal_review,epoch_root,freeze_path,public_path]) or any(p.exists() or p.is_symlink() for p in [epoch_root,freeze_path,public_path]):
  raise ValueError('Exclusive absolute source/epoch/output paths required')
 parent,plan,baseline,manifest=checked_parent(parent_freeze,terminal_review)
 evaluator=Path(parent['evaluator_root']);parent_root=Path(parent['epoch_root'])
 if epoch_root.parent!=evaluator/'work/gitlab-full-world':raise ValueError('Successor epoch must belong to original evaluator')
 original=Path(parent['original_private_root']);world=metadata_world(private(original/'world-private.json'))
 seed=private(original/'world-seed.txt').decode().strip()
 queue=fifo.ordered_queue(seed,world,fifo.load_catalog(original/'cisa-kev-pinned.json'))
 if queue['queue_sha256']!=parent['fifo_queue_sha256']:raise ValueError('Original precommitted FIFO queue changed')
 next_family=queue['ordered_families'][1]
 if next_family['ordinal']!=2:raise ValueError('Only next precommitted FIFO family may refill')
 roster,new_retired=replacement_roster(plan['task_roster'],next_family)
 retired=parent['retired_task_metadata']+new_retired;validate_roster(roster,retired)
 recipe={'schema':'envloop-gitlab-fifo-bootstrap-recipe-private-v6','fifo_ordinal':2,'fifo_queue_sha256':queue['queue_sha256'],
  'project':next_family['project'],'project_recipe_sha256':sha(factory.canonical(next_family['project'])),
  'task_metadata':[{**{k:t[k] for k in parent_source.TASK_METADATA_KEYS},'task_object_sha256':sha(factory.canonical(t))} for t in next_family['tasks']],
  'task_prompts_or_oracles_exported':False,'bootstrap_project_count':1,'new_principals':4,
  'repository_files':len(next_family['project']['files']),'issues':len(next_family['project']['issues']),'merge_requests':2,
  'direct_member_levels':{'oncall':30,'contractor':20,'observer':10}}
 recipe_path=freeze_path.parent/'fifo-bootstrap-recipe.private.json';recipe_sha=write_new(recipe_path,recipe)
 cold=json.loads(private(parent_root/'cow-reset-state.json'))
 expected_lower={r:'/var/lib/docker/volumes/'+n+'/_data' for r,n in parent['clone_volume_names'].items()}
 if cold['seed_volume_lowerdirs']!=expected_lower or cold['baseline_business_sha256']!=baseline['business_sha256']:
  raise ValueError('Parent immutable32 seed provenance changed')
 sources=source_hashes();tag=sha(factory.canonical({'parent':sha(private(parent_freeze)),'recipe':recipe_sha,'source':sources,'profile':SVWAIT_SECONDS}))[:12]
 value={'schema':SCHEMA,'status':'source_frozen_no_live_mutation','created_utc':now(),'source_sha256s':sources,
  'evaluator_root':str(evaluator),'original_private_root':str(parent_root),'protected_original_private_root':str(original),
  'parent_source_freeze_path':str(parent_freeze),'parent_source_freeze_sha256':sha(private(parent_freeze)),
  'parent_terminal_review_path':str(terminal_review),'parent_terminal_review_sha256':sha(private(terminal_review)),
  'parent_epoch_manifest':manifest,'parent_clone_container_name':parent['clone_container_name'],
  'parent_baseline_business_sha256':baseline['business_sha256'],'parent_plan_sha256':sha(private(parent_root/'cohort-plan.private.json')),
  'bound_metadata_sha256s':parent['bound_metadata_sha256s'],'protected_original_seed_lowerdirs':parent['original_seed_lowerdirs'],
  'original_seed_lowerdirs':expected_lower,'original_baseline_sha256':sha(private(parent_root/'baseline-persisted-state.json')),
  'original_baseline_business_sha256':baseline['business_sha256'],'original_world_sha256':sha(private(parent_root/'world-private.json')),
  'candidate_roster':roster,'candidate_roster_sha256':sha(factory.canonical(roster)),'retired_task_metadata':retired,
  'newly_retired_parent_indices':list(range(5)),'prior_retired_original_indices':list(range(10,15)),
  'historical_parent_passes_preserved':3,'historical_controls_transferred_to_new_baseline':0,
  'fifo_queue_sha256':parent['fifo_queue_sha256'],'recipe_path':str(recipe_path),'recipe_sha256':recipe_sha,
  'epoch_root':str(epoch_root),'public_path':str(public_path),'clone_container_name':'envloop-gitlab-successor-'+tag,
  'clone_volume_names':{r:'envloop-gitlab-successor-'+tag+'-'+r for r in ['config','logs','data']},
  'clone_vm_root':'/var/lib/envloop-gitlab-successor-'+tag,'clone_host_port':8018,'new_project_count':33,
  'new_control_count':100,'fixed_case_scores':[1.0,0.0,1.0],'fresh_resets_per_task':3,
  'startup_profile':{'SVWAIT':str(SVWAIT_SECONDS),'readiness_seconds':900,'supervisor_seconds':7200,'startup_restart_attempts':0},
  'archived_parent_runtime_graceful_stop_required':True,'protected_original_runtime_stop_authorized':False,
  'bootstrap_authorized':False,'task_dispatch_authorized':False,'reserve_project_bootstrapped':False,'new_baseline_and_acl_frozen':False,
  'same_intent_replay_authorized':False,'model_calls':0,'official_final_admitted':0}
 freeze_sha=write_new(freeze_path,value)
 public={'schema':PUBLIC_SCHEMA,'status':'full100_successor_source_frozen_no_live_mutation','private_freeze_sha256':freeze_sha,
  'source_sha256s':sources,'parent_source_freeze_sha256':value['parent_source_freeze_sha256'],
  'parent_terminal_review_sha256':value['parent_terminal_review_sha256'],'recipe_sha256':recipe_sha,'fifo_ordinal':2,
  'fifo_queue_sha256':value['fifo_queue_sha256'],'candidate_roster_sha256':value['candidate_roster_sha256'],
  'newly_retired_parent_indices':list(range(5)),'prior_retired_original_indices':list(range(10,15)),
  'prospective_tasks':100,'source_families':20,'new_baseline_projects':33,'new_projects':1,
  'historical_parent_passes_preserved':3,'historical_controls_transferred':0,'planned_case_scores':[1.0,0.0,1.0],
  'planned_exact_cold_resets_per_task':3,'startup_profile':value['startup_profile'],
  'startup_profile_empirically_validated':False,'parent_runtime_graceful_archive_stop_required':True,
  'protected_original_runtime_stop_authorized':False,'separate_clone_port':8018,
  'metadata_only_preparation':True,'final_answer_files_opened':0,'native_cohort_controls_completed':0,
  'bootstrap_authorized':False,'task_dispatch_authorized':False,'same_intent_replay_authorized':False,
  'provider_calls':0,'model_calls':0,'official_final_admitted':0}
 write_new(public_path,public,0o644);return public


def validate_source(freeze_path):
 raw=private(freeze_path);value=json.loads(raw)
 if (value.get('schema')!=SCHEMA or value.get('status')!='source_frozen_no_live_mutation' or
     value.get('source_sha256s')!=source_hashes() or value.get('new_project_count')!=33 or value.get('new_control_count')!=100 or
     value.get('bootstrap_authorized') is not False or value.get('task_dispatch_authorized') is not False or
     value.get('same_intent_replay_authorized') is not False or value.get('model_calls')!=0 or value.get('official_final_admitted')!=0 or
     value.get('startup_profile')!={'SVWAIT':'60','readiness_seconds':900,'supervisor_seconds':7200,'startup_restart_attempts':0} or
     value.get('archived_parent_runtime_graceful_stop_required') is not True or value.get('protected_original_runtime_stop_authorized') is not False):
  raise ValueError('Successor source/profile/denominator boundary changed')
 parent,_,baseline,manifest=checked_parent(Path(value['parent_source_freeze_path']),Path(value['parent_terminal_review_path']))
 if (sha(private(Path(value['parent_source_freeze_path'])))!=value['parent_source_freeze_sha256'] or
     sha(private(Path(value['parent_terminal_review_path'])))!=value['parent_terminal_review_sha256'] or manifest!=value['parent_epoch_manifest'] or
     baseline['business_sha256']!=value['parent_baseline_business_sha256'] or
     value['original_private_root']!=parent['epoch_root'] or value['protected_original_private_root']!=parent['original_private_root']):
  raise ValueError('Saved parent source/terminal/baseline provenance changed')
 name=value.get('clone_container_name','')
 if not re.fullmatch('envloop-gitlab-successor-[0-9a-f]{12}',name) or value.get('clone_host_port')!=8018 or value['clone_vm_root']!='/var/lib/'+name or value['clone_volume_names']!={r:name+'-'+r for r in ['config','logs','data']}:
  raise ValueError('Exclusive successor container/volume/VM/port namespace changed')
 for path,digest in value['bound_metadata_sha256s'].items():
  if sha(Path(path).read_bytes())!=digest:raise ValueError('Protected original metadata changed')
 if sha(private(Path(value['recipe_path'])))!=value['recipe_sha256']:raise ValueError('Next FIFO recipe changed')
 validate_roster(value['candidate_roster'],value['retired_task_metadata'])
 public=json.loads(Path(value['public_path']).read_bytes())
 if public.get('private_freeze_sha256')!=sha(raw) or public.get('source_sha256s')!=value['source_sha256s'] or public.get('task_dispatch_authorized') is not False:
  raise ValueError('Public successor source freeze changed')
 return value


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['prepare','validate','bootstrap'])
 for opt in ['freeze','parent-freeze','terminal-review','epoch-root','public-out','permit']:p.add_argument('--'+opt,type=Path)
 p.add_argument('--execute-reviewed-bootstrap',action='store_true');a=p.parse_args()
 if a.freeze is None:raise ValueError('Source freeze path required')
 if a.mode=='prepare':
  if not all([a.parent_freeze,a.terminal_review,a.epoch_root,a.public_out]):raise ValueError('Exact parent/terminal/epoch/output paths required')
  result=prepare(parent_freeze=a.parent_freeze,terminal_review=a.terminal_review,epoch_root=a.epoch_root,freeze_path=a.freeze,public_path=a.public_out)
 elif a.mode=='validate':validate_source(a.freeze);result={'status':'source_frozen_no_live_mutation','private_freeze_sha256':sha(private(a.freeze))}
 else:
  from .v066_prospective_cohort_runtime_v6 import bootstrap_clone
  result=bootstrap_clone(freeze_path=a.freeze,permit_path=a.permit,execute=a.execute_reviewed_bootstrap)
 print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
