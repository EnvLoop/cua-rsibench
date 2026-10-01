"""Additive effective SVWAIT60 startup witness; old neutral proofs are frozen."""
from __future__ import annotations
import argparse,json,re,time
from contextlib import contextmanager,ExitStack
from pathlib import Path
from types import FunctionType
from unittest.mock import patch
from . import v066_neutral_telemetry_coldboot_v5 as previous
from . import v066_effective_svwait_profile_v2 as profile
from . import full_git_model_workers_v1 as common_source
from .v066_neutral_telemetry_coldboot_v5 import source,runtime,factory,require,parse_services,tree_digests,EXPECTED_SETTINGS,write_raw,known_absence,validate_attributes,status_semantics
legacy=previous.legacy
SCHEMA='envloop-gitlab-neutral-effective-svwait-coldboot-plan-v6'
_NEW_ROOTS=('gitlab_world/v066_effective_svwait_profile_v2.py','gitlab_world/v066_neutral_telemetry_coldboot_v6.py','gitlab_world/v066_uniform_task_runtime_v14.py','gitlab_world/v066_uniform_model_workers_v14.py','gitlab_world/v066_uniform_train_qualification_v14.py','gitlab_world/v066_uniform_reference_controls_v19.py','tests/test_gitlab_effective_svwait_v6.py','tests/test_gitlab_uniform_effective_wait_v14.py','docs/GITLAB_EFFECTIVE_SVWAIT_V6_2026-10-01.md','tests/test_gitlab_native_header_dom_v13.py','tests/test_gitlab_native_surface_adapter_v13.py','tests/test_gitlab_reference_controls_v18.py','tests/test_gitlab_uniform_model_workers_v13.py','tests/test_gitlab_uniform_task_runtime_v13.py')
# AST-only import closure freezes the same actor/teacher/provider/final roots
# in the neutral prerequisite; it reads no task body and creates no runtime.
with patch.object(common_source,'FILES',tuple(dict.fromkeys(common_source.FILES+_NEW_ROOTS))):
 SOURCE_FILES=tuple(dict.fromkeys(previous.SOURCE_FILES+common_source.closed_source_files()))
NATIVE_PATTERNS=previous.NATIVE_PATTERNS+(r'cycle-[012]-effective-wait-(intent|witness|result|unavailable)\.private\.(json|jsonl)',r'command-\d+-bounded-(intent|result|unavailable)\.private\.json',r'owned-lifecycle-(start|end)\.private\.json')
PINNED_V5='12e61ab9a00e4580a6879df39aec8c497a588090f0ea1ef61e7d9c6d34c6640a'

def raw_refs(out):
 result={}
 for path in sorted(out.iterdir()):
  require(path.is_file() and not path.is_symlink(),'Native output contains a directory/link')
  if path.name in {'result.private.json','failure.private.json','manifest.private.json'}:continue
  require(path.name in previous.previous.previous.previous.NATIVE_INPUTS|previous.previous.previous.previous.NATIVE_FIXED or any(re.fullmatch(p,path.name) for p in NATIVE_PATTERNS),'Unowned native output filename')
  result[path.name]=source.sha(source.private(path))
 return result

@contextmanager
def version_scope():
 require(source.sha(Path(previous.__file__).read_bytes())==PINNED_V5,'Frozen V5 source changed')
 with previous.version_scope(),ExitStack() as stack:
  for name,value in [('SCHEMA',SCHEMA),('SOURCE_FILES',SOURCE_FILES),('raw_refs',raw_refs),('profile',profile)]:stack.enter_context(patch.object(legacy,name,value))
  yield

def prepare(**kwargs):
 with version_scope():return legacy.prepare(**kwargs)

def checked_plan(path):
 with version_scope():value=legacy.checked_plan(path)
 require(value[0]['profile']==profile.VERSION,'New effective-wait profile required')
 return value

def review(**kwargs):
 with version_scope():return legacy.review(**kwargs)

class NativeBackend(previous.NativeBackend):
 def __init__(self,doc,out):
  super().__init__(doc,out)
  self.started=time.monotonic();self.limit=doc.get('owned_lifecycle_seconds',7200)
  require(self.limit in {1200,7200},'Unknown owned native lifecycle limit')
  self.deadline=self.started+self.limit;self._rollback=False;self._closing=False
  self.record('owned-lifecycle-start.private.json',{'schema':'gitlab-owned-native-lifecycle-v6','started_monotonic':self.started,'deadline_monotonic':self.deadline,'seconds_limit':self.limit,'neutral_batch':self.limit==7200})
 def command(self,args,*,timeout=120):
  started=time.monotonic();remaining=self.deadline-started
  require(self._rollback or self._closing or remaining>0,'Owned native lifecycle expired before command; no retry')
  bounded=timeout if self._rollback or self._closing else min(timeout,max(.001,remaining))
  number=self.seq;prefix=f'command-{number:03d}-bounded'
  self.record(prefix+'-intent.private.json',{'schema':'gitlab-owned-native-command-v6','command_sha256':source.sha(factory.canonical(args)),'started_monotonic':started,'absolute_lifecycle_deadline':self.deadline,'process_timeout_seconds':bounded,'rollback_or_closing':self._rollback or self._closing,'one_new_process_call':True,'replay_authorized':False})
  try:value=super().command(args,timeout=bounded)
  except BaseException as error:
   self.record(prefix+'-unavailable.private.json',{'error_type':type(error).__name__,'returned_monotonic':time.monotonic(),'process_success_inferred':False,'replay_authorized':False});raise
  ended=time.monotonic();self.record(prefix+'-result.private.json',{'returned_monotonic':ended,'returned':True,'past_lifecycle_deadline':ended>self.deadline,'rollback_or_closing':self._rollback or self._closing})
  require(self._rollback or self._closing or ended<=self.deadline,'Native command returned after owned deadline; no credit')
  return value
 def teardown(self,index):
  previous_rollback=self._rollback;self._rollback=True
  try:return super().teardown(index)
  finally:self._rollback=previous_rollback
 def release_parent(self):
  self._closing=True
  return super().release_parent()
 def resume_original(self,before):
  self._closing=True
  return super().resume_original(before)
 def finish_lifecycle(self):
  ended=time.monotonic();self.record('owned-lifecycle-end.private.json',{'schema':'gitlab-owned-native-lifecycle-v6','started_monotonic':self.started,'ended_monotonic':ended,'elapsed_seconds':ended-self.started,'seconds_limit':self.limit,'within_limit':ended<=self.deadline,'rollback_still_completed_if_deadline_expired':True})
  require(ended<=self.deadline,'Owned native lifecycle exceeded absolute limit; restoration does not grant control credit')
 def boot(self,index):
  require(not self._closing and time.monotonic()<self.deadline,'No new boot after owned lifecycle closing/expiry')
  self.record(f'cycle-{index}-effective-wait-intent.private.json',{'schema':'envloop-native-effective-wait-startup-intent-v6','cycle':index,'profile':profile.VERSION,'effective_wait_seconds':60,'one_new_native_boot':True,'startup_retry_authorized':False})
  try:
   def wait_cohort():
    deadline=min(time.monotonic()+900,self.deadline)
    while time.monotonic()<deadline:
     inspected=runtime.inspect(runtime.WORLD);state=inspected['State']
     require([s for s in inspected.get('Config',{}).get('Env',[]) if s.startswith('SVWAIT=')]==['SVWAIT=60'] and inspected.get('Image')==runtime.IMAGE_ID,'Actual clone environment/image changed')
     require(state.get('Running'),'New clone exited during one-shot startup')
     if state.get('Health',{}).get('Status')=='healthy' and runtime._http_ready():return runtime.proof(runtime.WORLD)
     time.sleep(min(5,max(0,deadline-time.monotonic())))
    raise TimeoutError('Bounded native readiness expired; no retry')
   with version_scope(),patch.object(legacy.scoped,'wait_cohort',wait_cohort):result=super().boot(index)
   name=self.doc['container_prefix']+'-'+str(index)
   raw=self.docker('exec',name,'/opt/gitlab/embedded/bin/ruby','-e',profile.witness_reader_ruby(),timeout=30).encode()
   self.record_witness(index,raw)
   state=json.loads(source.private(self.out/f'cycle-{index}-state.private.json'))
   proof=profile.validate_witness(raw,started_at=state['StartedAt'])
   self.record(f'cycle-{index}-effective-wait-result.private.json',proof)
   return result|{'effective_wait_witness':proof}
  except BaseException as error:
   self.record(f'cycle-{index}-effective-wait-unavailable.private.json',{'schema':'envloop-native-effective-wait-startup-unavailable-v6','cycle':index,'error_type':type(error).__name__,'actual_error_sha256':source.sha(str(error).encode()),'boot_or_witness_success_inferred':False,'startup_retry_authorized':False})
   raise
 def record_witness(self,index,raw):
  return write_raw(self.out/f'cycle-{index}-effective-wait-witness.private.jsonl',raw)

def run(*,plan,permit,execute=False,backend_factory=NativeBackend):
 raw_refs(plan.parent)
 with version_scope():return legacy.run(plan=plan,permit=permit,execute=execute,backend_factory=backend_factory)

def audit(*,plan,permit):
 # Reuse the unchanged production V5 saved SQL/Git/reset/restore decoder with
 # V6 plan/source/filename bindings, then require native helper process proof.
 reader=FunctionType(previous.audit.__code__,{**previous.audit.__globals__,'checked_plan':checked_plan,'raw_refs':raw_refs,'profile':profile},previous.audit.__name__)
 value=reader(plan=plan,permit=permit)
 result=json.loads(source.private(plan.parent/'result.private.json'))
 calls=0
 for index in [0,1,2]:
  raw=source.private(plan.parent/f'cycle-{index}-effective-wait-witness.private.jsonl')
  state=json.loads(source.private(plan.parent/f'cycle-{index}-state.private.json'))
  proof=profile.validate_witness(raw,started_at=state['StartedAt'])
  require(proof==json.loads(source.private(plan.parent/f'cycle-{index}-effective-wait-result.private.json')) and proof==result['cycles'][index]['effective_wait_witness'],'Native effective wait proof changed')
  calls+=proof['actual_nginx_logger_wait_calls_verified']
 return value|{'status':'saved_three_neutral_v6_effective_wait_native_cycles_independently_replayed','effective_wait_seconds':60,'actual_startup_helper_calls_verified':calls,'native_effective_wait_verified':True,'old_neutral_v5_credit':0}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['prepare','review','run','audit']);p.add_argument('--freeze',type=Path);p.add_argument('--upstream-bindings',type=Path);p.add_argument('--out',type=Path);p.add_argument('--plan',type=Path);p.add_argument('--permit',type=Path);p.add_argument('--port',type=int,default=8026);p.add_argument('--accept-root-review',action='store_true');p.add_argument('--note',default='');p.add_argument('--execute',action='store_true');a=p.parse_args()
 if a.mode=='prepare':v=prepare(freeze=a.freeze,out=a.out,upstream_bindings=a.upstream_bindings,port=a.port)
 elif a.mode=='review':v=review(plan=a.plan,permit=a.permit,accepted=a.accept_root_review,note=a.note)
 elif a.mode=='audit':v=audit(plan=a.plan,permit=a.permit)
 else:v=run(plan=a.plan,permit=a.permit,execute=a.execute)
 print(json.dumps(v,sort_keys=True))
if __name__=='__main__':main()
