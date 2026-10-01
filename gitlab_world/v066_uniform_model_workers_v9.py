"""Mandatory common runtime/safety wrapper for base, four CPs and teacher.

Legacy workers/oracles stay byte-frozen. New source closure/ratification and
plan permit are mandatory; every factory replaces the old cohort backend.
"""
from __future__ import annotations
from contextlib import contextmanager,ExitStack
from dataclasses import replace
import inspect,json,textwrap
from pathlib import Path
from types import FunctionType
from unittest.mock import patch
from cursibench import native_surface_guard_policy_v1 as guard_policy
from . import full_git_model_workers_v1 as common,full_git_final_worker_v1 as final_worker
from . import teacher_episode_worker_v066 as teacher,selection_worker_v066 as selection,operators
from . import v066_uniform_task_runtime_v9 as world
from . import v066_native_surface_adapter_v9 as safety

ROOT=Path(__file__).resolve().parents[1]
FILES=world.FILES+('src/cursibench/native_surface_guard_policy_v1.py',)
_BaseBackend=common.FullGitBackend
_Public=common.public_binding
_TrainFactory=common.train_worker
_SelectionFactory=common.selection_worker
_TeacherLoop=teacher.GitLabTrainEpisodeWorker.run_episode
_StudentLoop=selection.GitLabSelectionWorker._task_episode


def public_binding():
 with source_scope():value=_Public()
 payload={k:v for k,v in value.items() if k!='binding_sha256'}
 payload.update(uniform_native_policy_sha256=guard_policy.POLICY_SHA,
  uniform_runtime_profile=world.cold.profile.VERSION,uniform_native_result_sha256=world.PROVED_RESULT_SHA,
  uniform_backend_for_all_slots=True,old_cohort_backend_fallback=False,
  matched_actor_budget={'max_actions':90,'wall_seconds':720,'teacher_actor_starts_after_exact_initial_reset':True})
 return {**payload,'binding_sha256':common.digest(common.canonical(payload))}


def validate_binding(value):
 common.require(common.canonical(value)==common.canonical(public_binding()),'uniform_whole_source_binding_changed');return value


def _loop(function):
 """One explicit source-bound amendment: a rejected finish cannot end an episode."""
 source=textwrap.dedent(inspect.getsource(function))
 needle='if action["type"] == "finish":' if function.__name__=='run_episode' else 'if sampled["action"]["type"] == "finish":'
 common.require(source.count(needle)==1,'uniform_worker_finish_branch_changed')
 source=source.replace(needle,needle[:-1]+' and active.finished:')
 scope=dict(function.__globals__);scope['MAX_ACTIONS']=90;scope['WALL_SECONDS']=720
 if function.__name__=='run_episode':
  marker='            for step in range(MAX_ACTIONS):'
  common.require(source.count(marker)==1,'uniform_teacher_actor_clock_branch_changed')
  source=source.replace(marker,'            started = time.monotonic()\n'+marker)
 namespace={};exec(compile(source,'<gitlab-uniform-v9-'+function.__name__+'>','exec'),scope,namespace)
 return namespace[function.__name__]


@contextmanager
def source_scope():
 with ExitStack() as stack:
  for module,key,value in [(teacher,'RUNTIME_FILES',tuple(dict.fromkeys(teacher.RUNTIME_FILES+FILES))),
   (selection,'RUNTIME_FILES',tuple(dict.fromkeys(selection.RUNTIME_FILES+FILES))),
   (common,'FILES',tuple(dict.fromkeys(common.FILES+FILES))),
   (common,'public_binding',public_binding),(common,'FullGitBackend',FullGitBackend),
   (teacher.GitLabTrainEpisodeWorker,'run_episode',_loop(_TeacherLoop)),
   (selection.GitLabSelectionWorker,'_task_episode',_loop(_StudentLoop))]:stack.enter_context(patch.object(module,key,value))
  yield


class FullGitBackend(_BaseBackend):
 def __init__(self,backend,*,partition,binding,cohort_freeze_path=None):
  # The same explicit plan path is passed to every base/checkpoint/teacher slot.
  common.require(cohort_freeze_path is not None,'uniform_task_plan_required')
  self.plan_path=Path(cohort_freeze_path);plan,_=world.checked_plan(self.plan_path)
  self.permit_path=self.plan_path.parent/'full-study-permit.private.json';self.phase='full-study'
  self.backend,self.partition,self.binding=backend,partition,validate_binding(binding)
  self.cohort_freeze_path=self.plan_path;self.cohort_source_file_sha256=common.digest(self.plan_path.read_bytes());self.output_root=None
 def set_output_root(self,path):self.output_root=Path(path) if path is not None else None
 @contextmanager
 def open(self,identity):
  validate_binding(self.binding);common.require(self.output_root is not None,'uniform_owned_output_root_required')
  root=self.output_root/'artifacts';common.require(root.is_dir() and not root.stat().st_mode&0o077,'uniform_private_artifacts_missing')
  with world.TaskWorld(self.plan_path,self.permit_path,root,phase=self.phase).open():
   with self.backend.open(identity) as active:
    roster=json.loads(operators.RECEIPT.read_bytes());account=roster['identities'][self.partition]['user_id']
    gate=safety.NativeGuard(active,root/'native-safety',account_uid=account,partition=self.partition);gate.bind()
    session=safety.GuardedSession(active,gate)
    wrapper=common.FullGitSession(session,partition=self.partition,artifact_root=root,binding=self.binding,
     cohort_source_file_sha256=self.cohort_source_file_sha256)
    error=None
    try:yield wrapper
    except BaseException as failure:error=failure;raise
    finally:
     try:wrapper.retain_before_reset(error)
     finally:gate.close()


def qualification_backend(*,plan_path,permit_path,binding,output_root):
 with source_scope():backend=FullGitBackend(teacher.RealGitLabTrainBackend(),partition='train',binding=binding,cohort_freeze_path=plan_path)
 backend.permit_path=Path(permit_path);backend.phase='train-qualification';backend.set_output_root(output_root);return backend


def freeze_binding(out):
 value=public_binding();return {'binding_file_sha256':world.write(out,value),'binding_sha256':value['binding_sha256'],
  'native_policy_sha256':guard_policy.POLICY_SHA,'runtime_sha256':runtime_sha256(),'model_calls':0}


def runtime_sha256():
 with source_scope():return selection.runtime_sha256()


def adapter_sha256():
 with source_scope():return selection.adapter_sha256()


def train_worker(**kwargs):
 with source_scope():worker=_TrainFactory(**kwargs)
 original=worker.run_episode
 def run_episode(**episode):
  with source_scope():return original(**episode)
 worker.run_episode=run_episode;return worker


def selection_worker(**kwargs):
 with source_scope():worker=_SelectionFactory(**kwargs)
 original_attempt=worker.run_attempt
 def run_attempt(**attempt):
  with source_scope():return original_attempt(**attempt)
 worker.run_attempt=run_attempt
 # All calls to the episode helper retain the source scope, including shared base.
 method=worker._task_episode
 def task_episode(**episode):
  with source_scope():return method(**episode)
 worker._task_episode=task_episode
 require_frozen=worker._require_frozen
 def frozen(session,started):
  with source_scope():return require_frozen(session,started)
 worker._require_frozen=frozen;return worker


class GitLabUniformFinalWorker(final_worker.GitLabFullGitFinalWorker):
 def _common_binding(self):
  scope=dict(final_worker.GitLabFullGitFinalWorker._common_binding.__globals__);scope['COMMON_MODULE']=__name__
  function=FunctionType(final_worker.GitLabFullGitFinalWorker._common_binding.__code__,scope)
  return function(self)
 def __init__(self,**kwargs):
  with source_scope():super().__init__(**kwargs)
 def run_once(self,command,output_dir):
  with source_scope():return super().run_once(command,output_dir)


def final_worker_factory(*,gate,full_git_binding_path,full_git_binding_file_sha256,final_output_root,cohort_freeze_path,enable_live=False):
 return GitLabUniformFinalWorker(gate=gate,binding_path=full_git_binding_path,binding_file_sha256=full_git_binding_file_sha256,
  final_output_root=final_output_root,cohort_freeze_path=cohort_freeze_path,enable_live=enable_live)


def run_gitlab_shared_base(study,usage_reconciler,**kwargs):
 from . import full_git_shared_base_execution_v1 as base
 with source_scope(),patch.object(common,'selection_worker',selection_worker):return base.run_gitlab_shared_base(study,usage_reconciler,**kwargs)


private_json=common.private_json
_verify_saved_proof=common._verify_saved_proof
_audit_episode_output=common._audit_episode_output
execution_verdict=common.execution_verdict


def main():
 import argparse
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['freeze-source','check-source'])
 parser.add_argument('--out',type=Path);parser.add_argument('--binding',type=Path);args=parser.parse_args()
 if args.mode=='freeze-source':result=freeze_binding(args.out)
 else:
  value=validate_binding(private_json(args.binding));result={'binding_sha256':value['binding_sha256'],'model_calls':0}
 print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
