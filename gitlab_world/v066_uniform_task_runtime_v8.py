"""Prospective shared task world using the proved V5 native lifecycle.

No old epoch/env/seed or result is modified. Every reset creates a fresh COW
upper, applies the same nine settings and verifies native attributes + SQL/Git.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager,ExitStack
import fcntl,json,os
from pathlib import Path
from unittest.mock import patch
from . import v066_neutral_telemetry_coldboot_v5 as cold
from . import bootstrap,operators,reset,runtime,verify,factory
from . import v066_prospective_cohort_runtime_v6 as old_scope
from . import vision_actor,vision_actor_v066_train

SCHEMA='envloop-gitlab-uniform-task-runtime-v8'
PROVED_RESULT_SHA='3aa20fa5534b685acede3ba2f7e2006d9338f4d9af5cf730b6fa3e3d94a24b7f'
FILES=('src/cursibench/native_surface_guard_policy_v1.py','gitlab_world/full_git_model_workers_v1.py','gitlab_world/full_git_final_worker_v1.py','gitlab_world/full_git_model_oracle_v1.py','gitlab_world/full_git_shared_base_execution_v1.py','gitlab_world/teacher_episode_worker_v066.py','gitlab_world/selection_worker_v066.py','gitlab_world/vision_actor.py','gitlab_world/vision_actor_v066_train.py','gitlab_world/v066_uniform_task_runtime_v8.py','gitlab_world/v066_native_surface_adapter_v8.py',
 'gitlab_world/gui_controls.py','gitlab_world/gui_workflows.py','gitlab_world/v066_uniform_reference_controls_v8.py','gitlab_world/v066_uniform_train_qualification_v8.py','gitlab_world/v066_uniform_model_workers_v8.py','tests/test_gitlab_uniform_task_runtime_v8.py',
 'tests/test_gitlab_native_surface_adapter_v8.py','tests/test_gitlab_uniform_model_workers_v8.py',
 'docs/FULL_STUDY_GITLAB_UNIFORM_RUNTIME_V8_2026-10-01.md')+cold.SOURCE_FILES
COPIES=('baseline-persisted-state.json','bootstrap-progress.json','operator-bootstrap-private.json',
 'operator-credentials-private.json','world-private.json','cohort-plan.private.json','native-acl.private.json','world-seed.txt')


def require(ok,code):
 if not ok:raise ValueError(code)


def source_hashes():
 root=Path(__file__).resolve().parents[1]
 return {n:cold.source.sha((root/n).read_bytes()) for n in dict.fromkeys(FILES)}


def write(path,value):return cold.source.write_new(path,value)


def _rosters(root):
 world=json.loads(cold.source.private(root/'world-private.json'))
 all_tasks=bootstrap.all_tasks(world);result={}
 final_plan=json.loads(cold.source.private(root/'cohort-plan.private.json'))
 for partition,count in [('train',20),('selection',20)]:
  rows=[t for t in all_tasks if t['partition']==partition]
  require(len(rows)==count and len({t['task_id'] for t in rows})==count,'Original TRAIN/selection roster changed')
  result[partition]=[{'task_id':t['task_id'],'package_sha256':factory.sha256(factory.canonical(t))} for t in rows]
 result['final_candidate_unsealed']=[{k:t[k] for k in ['task_id','package_sha256']} for t in final_plan['task_roster']]
 require(len(result['final_candidate_unsealed'])==100,'Original final100 roster changed')
 return result


def prepare(*,neutral_plan,neutral_permit,out):
 proof=cold.audit(plan=neutral_plan,permit=neutral_permit)
 require(proof['result_sha256']==PROVED_RESULT_SHA and proof['neutral_cycles_verified']==3,'Actual proved V5 three-cycle result required')
 parent,_,baseline=cold.checked_plan(neutral_plan);original=Path(parent['epoch_root']);out=Path(out).absolute()
 require(not out.exists() and not out.is_symlink(),'Fresh prospective task namespace required');out.mkdir(mode=0o700)
 for name in COPIES:cold.write_raw(out/name,cold.source.private(original/name))
 cold.write_raw(out/'runtime.env',cold.profile.render_clone_environment(cold.source.private(original/'runtime.env')))
 rosters=_rosters(out)
 cow={'schema':'envloop-gitlab-overlay-cold-reset-v1','baseline_business_sha256':baseline['business_sha256'],
  'seed_volume_lowerdirs':parent['seed_lowerdirs'],'clone_generation':0,'last_readback_equal':False}
 write(out/'cow-reset-state.json',cow)
 plan={'schema':SCHEMA,'status':'source_prepared_no_task_or_native_dispatch','source_sha256s':source_hashes(),
  'parent_neutral_plan':str(neutral_plan),'parent_neutral_permit':str(neutral_permit),'proved_native_result_sha256':PROVED_RESULT_SHA,
  'evaluator_root':parent['evaluator_root'],'protected_original_epoch':parent['epoch_root'],'native_parent':parent,
  'private_root':str(out),'runtime_env_sha256':cold.source.sha(cold.source.private(out/'runtime.env')),
  'copied_metadata_sha256s':{n:cold.source.sha(cold.source.private(out/n)) for n in COPIES},
  'rosters':rosters,'roster_sha256s':{p:cold.source.sha(factory.canonical(rows)) for p,rows in rosters.items()},
  'uniform_slots':['base','selected-1','selected-2','selected-3','selected-4','teacher','control'],
  'original_rosters_unchanged':True,'historical_credit':0,'official_final_admitted':0,'model_calls':0,
  'image_id':runtime.IMAGE_ID,'SVWAIT':'60','readiness_seconds':900,'stop_seconds':300,
  'host_port':8018,'internal_port':8018,'profile':cold.profile.VERSION,'automatic_restart_attempts':0,
  'new_task_profile_live_authorized':False,'selection_final_qualified':False}
 digest=write(out/'uniform-runtime-plan.private.json',plan)
 return {'status':plan['status'],'plan_sha256':digest,'train':20,'selection':20,'final':100,'native_calls':0}


def checked_plan(path):
 raw=cold.source.private(path);plan=json.loads(raw);root=Path(plan['private_root'])
 require(plan.get('schema')==SCHEMA and plan.get('source_sha256s')==source_hashes() and root==path.parent and
  plan.get('uniform_slots')==['base','selected-1','selected-2','selected-3','selected-4','teacher','control'] and
  plan.get('automatic_restart_attempts')==0 and plan.get('new_task_profile_live_authorized') is False,'Uniform task source/slot boundary changed')
 proof=cold.audit(plan=Path(plan['parent_neutral_plan']),permit=Path(plan['parent_neutral_permit']))
 require(proof['result_sha256']==plan['proved_native_result_sha256']==PROVED_RESULT_SHA,'Proved native lifecycle binding changed')
 parent,_,baseline=cold.checked_plan(Path(plan['parent_neutral_plan']))
 require(plan['native_parent']==parent and cold.source.sha(cold.source.private(root/'runtime.env'))==plan['runtime_env_sha256'] and
  cold.source.private(root/'runtime.env')==cold.profile.render_clone_environment(cold.source.private(Path(parent['epoch_root'])/'runtime.env')),
  'Uniform nine-setting environment or protected original changed')
 require({n:cold.source.sha(cold.source.private(root/n)) for n in COPIES}==plan['copied_metadata_sha256s'] and
  _rosters(root)==plan['rosters'],'Unchanged task corpus/roster binding changed')
 return plan,baseline


def review(*,plan_path,permit,accepted=False,note='',phase='train-qualification'):
 require(accepted is True and note.strip() and phase in ['train-qualification','final-controls','full-study'],'Exact uniform source review required')
 plan,_=checked_plan(plan_path)
 if phase in ['final-controls','full-study']:
  accepted_receipt=json.loads(cold.source.private(plan_path.parent/'train-qualification-root-accepted.private.json'))
  require(accepted_receipt.get('accepted') is True and accepted_receipt.get('plan_sha256')==cold.source.sha(cold.source.private(plan_path)) and
   accepted_receipt.get('source_sha256s')==plan['source_sha256s'],'Native TRAIN qualification root acceptance changed')
  from .v066_uniform_train_qualification_v8 import audit
  actual=audit(plan_path=plan_path,binding_path=Path(accepted_receipt['binding_path']),out=Path(accepted_receipt['qualification_out']))
  require(actual['result_sha256']==accepted_receipt['result_sha256'],'Accepted native TRAIN raw proof changed')
 value={'schema':'envloop-gitlab-uniform-task-permit-v8','plan_sha256':cold.source.sha(cold.source.private(plan_path)),
  'source_sha256s':plan['source_sha256s'],'phase':phase,'accepted':True,'note':note,'uniform_all_slots':True,'no_historical_credit':True}
 return {'permit_sha256':write(permit,value),'phase':phase,'native_calls':0}


class TaskWorld:
 def __init__(self,plan_path,permit,artifact_root,*,phase,backend_factory=cold.NativeBackend):
  self.plan_path,self.permit,self.artifact_root,self.phase=Path(plan_path),Path(permit),Path(artifact_root),phase
  self.backend_factory=backend_factory;self.backend=None;self.active_index=None;self.generation=0;self.transaction=None
 def _permit(self):
  plan,baseline=checked_plan(self.plan_path);permit=json.loads(cold.source.private(self.permit))
  require(permit.get('schema')=='envloop-gitlab-uniform-task-permit-v8' and permit.get('accepted') is True and
   permit.get('plan_sha256')==cold.source.sha(cold.source.private(self.plan_path)) and permit.get('source_sha256s')==plan['source_sha256s'] and
   permit.get('phase')==self.phase and permit.get('uniform_all_slots') is True,'Exact phase/source permit required')
  require(Path(__file__).resolve().parents[1]==Path(plan['evaluator_root']),'Original evaluator required for live task runtime')
  return plan,baseline
 @contextmanager
 def open(self):
  plan,baseline=self._permit();private=Path(plan['private_root']);self.artifact_root.mkdir(mode=0o700,exist_ok=True)
  require(not self.artifact_root.is_symlink() and not self.artifact_root.stat().st_mode&0o077,'Owned private task artifact root required')
  lock=os.open(private/'uniform-task-runtime.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  try:
   with cold.version_scope():
    yield from self._open_guarded(plan,baseline,private)
  finally:fcntl.flock(lock,fcntl.LOCK_UN);os.close(lock)
 def _open_guarded(self,plan,baseline,private):
   old_scope.no_old_worker(Path(plan['evaluator_root']))
   token=cold.source.sha(str(self.artifact_root.resolve()).encode())[:12]
   doc={**plan['native_parent'],'container_prefix':'envloop-gitlab-neutral-telemetry-'+token,
    'vm_root':'/var/lib/envloop-gitlab-neutral-telemetry-'+token,'port':8018,'neutral_base':'http://127.0.0.1:8018',
    'source_sha256s':plan['source_sha256s']}
   self.transaction=self.artifact_root/'native-runtime';self.transaction.mkdir(mode=0o700,exist_ok=False)
   # Proven native helper reads these evaluator-only fixture copies.
   for n in ['baseline-persisted-state.json','bootstrap-progress.json','operator-bootstrap-private.json','operator-credentials-private.json']:
    cold.write_raw(self.transaction/n,cold.source.private(private/n))
   cold.write_raw(self.transaction/'neutral-runtime.env',cold.source.private(private/'runtime.env'))
   self.backend=self.backend_factory(doc,self.transaction)
   before=self.backend.original_before();require(before['snapshot']==baseline,'Original baseline changed before prospective task')
   protected=self.backend.protected();seed=self.backend.seed_content()
   self.backend.record('protected-before.private.json',protected);self.backend.record('seed-before.private.json',seed)
   self.before,self.protected_before,self.seed_before=before,protected,seed
   paused=False
   try:
    self.backend.claim_parent();paused=True;self.backend.stop_original(before)
    with self._scope(private):yield self
   finally:
    try:
     if self.active_index is not None:self.backend.teardown(self.active_index);self.active_index=None
     self.backend.release_parent()
    finally:
     if paused:self.backend.resume_original(before)
     require(self.backend.protected()==protected and self.backend.seed_content()==seed,'Protected source/seed changed during task world')
     self.backend.record('protected-exit.private.json',self.backend.protected());self.backend.record('seed-exit.private.json',self.backend.seed_content())
 @contextmanager
 def _scope(self,private):
  with ExitStack() as stack,cold.version_scope():
   entries=[(runtime,{'PRIVATE':private,'BASE':'http://127.0.0.1:8018','WORLD':self.backend.doc['container_prefix']+'-0'}),
    (bootstrap,{'PRIVATE':private,'WORLD_FILE':private/'world-private.json','PROGRESS_FILE':private/'bootstrap-progress.json','SEED_FILE':private/'world-seed.txt'}),
    (operators,{'PRIVATE':private,'CREDENTIALS':private/'operator-credentials-private.json','RECEIPT':private/'operator-bootstrap-private.json'}),
    (reset,{'PRIVATE':private,'STATE_FILE':private/'cow-reset-state.json','reset':self.reset}),
    (verify,{'_ids':lambda:old_scope.ids_for_progress(private/'bootstrap-progress.json'),'verify_bootstrap':lambda s:old_scope.validate_snapshot(s,33)}),
    (vision_actor,{'local_origin':old_scope.local_url}),(vision_actor_v066_train,{'local_origin':old_scope.local_url})]
   for module,fields in entries:
    for key,value in fields.items():stack.enter_context(patch.object(module,key,value))
   yield
 def reset(self):
  require(self.backend is not None,'Task runtime lease missing')
  if self.active_index is not None:self.backend.teardown(self.active_index);self.active_index=None
  index=self.generation
  # Each generation has its own retained native proof files; nothing is reused.
  try:cycle=self.backend.boot(index)
  except Exception:
   if index in self.backend.owned_cycles:self.backend.teardown(index)
   raise
  self.active_index=index
  baseline=reset._baseline()
  require(cold.tree_digests(cycle['full_git_trees'])==cold.tree_digests(self.before['full_git_trees']),'Complete baseline Git tree changed on task reset')
  require(self.backend.protected()==self.protected_before and self.backend.seed_content()==self.seed_before,'Protected source/seed changed on task reset')
  require(cycle['state_snapshot']==baseline and cycle['effective_settings']==cold.EXPECTED_SETTINGS,'Uniform task cold reset changed SQL/Git/profile')
  require(all(cycle['services'].get(s)=='running' for s in cold.profile.CRITICAL_SERVICES) and
   all(cycle['services'].get(s)=='absent' for s in cold.profile.OPTIONAL_SERVICES),'Uniform task critical/optional service mismatch')
  self.active_index=index;self.generation+=1;runtime.WORLD=self.backend.doc['container_prefix']+'-'+str(index)
  state=json.loads(cold.source.private(reset.STATE_FILE));state.update(clone_generation=self.generation,
   first_clone_container_id_sha256=state.get('first_clone_container_id_sha256',cycle['container_id_sha256']),
   last_clone_container_id_sha256=cycle['container_id_sha256'],last_readback_equal=True)
  cold.source.persist(reset.STATE_FILE,state)
  self.backend.record(f'cycle-{index}-task-reset.private.json',{'cold_reset':True,'same_business_sha256':True,
   'full_git_exact':True,'native_profile_exact':True,'generation':self.generation,'actor_not_started_before_readback':True})
  return {'cold_reset':True,'same_business_sha256':True,'generation':self.generation,'container_identity_changed':True}


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['prepare','review']);p.add_argument('--neutral-plan',type=Path);p.add_argument('--neutral-permit',type=Path);p.add_argument('--out',type=Path)
 p.add_argument('--plan',type=Path);p.add_argument('--permit',type=Path);p.add_argument('--accept-root-review',action='store_true');p.add_argument('--note',default='');p.add_argument('--phase',default='train-qualification');a=p.parse_args()
 result=prepare(neutral_plan=a.neutral_plan,neutral_permit=a.neutral_permit,out=a.out) if a.mode=='prepare' else review(plan_path=a.plan,permit=a.permit,accepted=a.accept_root_review,note=a.note,phase=a.phase)
 print(json.dumps(result,sort_keys=True))

if __name__=='__main__':main()
