"""Uniform owned queue service and passive timing witness for every role."""
from __future__ import annotations
import asyncio,base64,json,time
from contextlib import asynccontextmanager
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch
from cursibench import native_surface_guard_policy_v1 as policy
from enterprise_fallback.odoo18.odoo_native_surface_evidence_v6 import EvidenceStore
from tools import magento_dedicated_train_lane_v066 as original
from . import native_queue_profile_v2 as profile
from .native_surface_actor_v1 import Runtime as OriginalRuntime,run_task as original_run_task
from .native_surface_guard_v1 import NATIVE_JS as ORIGINAL_JS
from .native_surface_adapter_v2 import NATIVE_JS as CURRENT_JS


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

class NativeQueue:
 def __init__(self,active,root,started):
  self.active=active;self.root=Path(root);self.store=EvidenceStore(self.root);self.started=started;self.deadline=started+1200
  self.scope=sha256(str(self.root.resolve()).encode()).hexdigest()[:24];self.sequence=0;self.owner=None;self.probes=[];self.baseline=None;self.reset=None;self.closing=False
 def command(self,args,*,mutating=False,timeout=30):
  remaining=self.deadline-time.monotonic();profile.require(self.closing or remaining>0,'Native queue lifecycle deadline expired; no replay')
  label=f'p0_native_queue_{self.sequence:04d}';self.sequence+=1
  return self.active.manager.journal.run(label,tuple(args),mutating=mutating,timeout=timeout if self.closing else max(1,min(timeout,int(remaining))))
 def php(self,code):
  value=self.command(('exec',self.active.spec.app,'php','-r',code))
  profile.require(type(value) is str and 0<len(value)<2_000_000,'Native queue read missing/unbounded')
  result=json.loads(value);profile.require(type(result) is dict,'Native queue object required');return result
 def state(self):return profile.validate_queue(self.php(profile.QUEUE_READ_PHP))
 async def start(self):
  self.baseline=await asyncio.to_thread(self.state)
  profile.require(self.baseline['pending']==0 and self.baseline['failed']==0,'Preexisting pending/failed channel cannot be consumed')
  self.store.json('queue/baseline.private.json',self.baseline,'native_observation_envelope')
  intent={'schema':'magento-native-owned-queue-setup-v2','scope_token':self.scope,'topic':profile.TOPIC,'argv':profile.ARGV,'before_native_launch':True,'all_seven_roles_same_profile':True,'no_task_data_in_service_command':True,'lifecycle_deadline_monotonic':self.deadline}
  self.store.json('queue/start-intent.private.json',intent,'action_intent')
  wall=time.time()+max(0,self.deadline-time.monotonic())
  await asyncio.to_thread(self.command,('exec','--detach',self.active.spec.app,'php','-r',profile.SUPERVISOR_PHP,'--',self.scope,format(wall,'.6f')),mutating=True)
  # One launch. Missing owner-file reads may settle; process calls are not replayed.
  until=min(self.deadline,time.monotonic()+10)
  last=None
  while time.monotonic()<until:
   actual=await asyncio.to_thread(self.php,profile.owner_read_php(self.scope))
   if actual.get('owner_available') is False:
    last='owner_file_not_yet_retained';await asyncio.sleep(.1);continue
   self.owner=profile.validate_owner(actual,self.scope);break
  profile.require(self.owner is not None,'Detached acknowledgement does not prove native consumer startup: '+str(last))
  self.store.json('queue/startup.private.json',{'native':actual,'scope_token':self.scope,'profile':profile.PROFILE,'observed_monotonic':time.monotonic()},'native_observation_envelope')
 async def observe(self,metadata):
  # Internal harness evidence only; returned native metadata is unchanged.
  actual=await asyncio.to_thread(self.php,profile.owner_read_php(self.scope));profile.validate_owner(actual,self.scope)
  state=await asyncio.to_thread(self.state);observed=time.monotonic()
  row={'schema':'magento-native-passive-queue-observation-v2','native_context_sha256':policy.digest(metadata),'observed_monotonic':observed,'native_process':actual,'queue':state,'actor_tool_output_modified':False,'service_mutation_performed':False}
  ref=self.store.json(f'queue/probe-{len(self.probes):04d}.private.json',row,'native_observation_envelope');self.probes.append({'reference':ref,'observed_monotonic':observed})
 async def close(self):
  self.closing=True
  profile.require(self.owner is not None,'Unproved consumer owner cannot receive close request')
  actual=await asyncio.to_thread(self.php,profile.owner_read_php(self.scope));profile.validate_owner(actual,self.scope)
  self.store.json('queue/close-intent.private.json',{'scope_token':self.scope,'owner':self.owner,'before_owned_close_request':True,'replay_authorized':False},'action_intent')
  result=await asyncio.to_thread(self.php,profile.close_request_php(self.scope));profile.require(result.get('close_request_written') is True,'Owned queue close request unknown')
  until=time.monotonic()+10;ack=None
  while time.monotonic()<until:
   value=await asyncio.to_thread(self.php,profile.exit_read_php(self.scope))
   if value.get('exit_available') and value.get('supervisor_pid_absent'):
    ack=profile.validate_exit(value,self.owner);break
   await asyncio.sleep(.1)
  profile.require(ack is not None,'Native consumer exit/parent absence unavailable; no close inferred')
  for name,key in [('stdout','stdout'),('stderr','stderr')]:
   raw=base64.b64decode(value[key],validate=True);profile.require(sha256(raw).hexdigest()==ack[name+'_sha256'],'Native consumer exit stream changed')
   original_fd=__import__('os').open(self.root/f'queue/consumer.{name}.private.bin',__import__('os').O_WRONLY|__import__('os').O_CREAT|__import__('os').O_EXCL,0o600)
   with __import__('os').fdopen(original_fd,'wb') as stream:stream.write(raw);stream.flush();__import__('os').fsync(stream.fileno())
  self.store.json('queue/close.private.json',{'exit':ack,'supervisor_pid_absent':True,'observed_monotonic':time.monotonic()},'driver_result')

class PassivePage:
 def __init__(self,page,queue):self._native_page=page;self._queue=queue
 def __getattr__(self,key):return getattr(self._native_page,key)
 async def evaluate(self,script,arg=None):
  result=await self._native_page.evaluate(script,arg)
  if script in (ORIGINAL_JS,CURRENT_JS):await self._queue.observe(result)
  return result

class Runtime(OriginalRuntime):
 @asynccontextmanager
 async def open_case(self,case,out_dir):
  started=time.monotonic();queue=None;active=None;cleanup=original.DedicatedCloneManager.cleanup
  def check_reset(manager,spec):
   if spec.index==1 and queue is not None and queue.baseline is not None:
    try:
     raw=manager._exec('p1_native_queue_reset_read',spec.app,'php','-r',profile.QUEUE_READ_PHP,timeout=30)
     restored=profile.validate_queue(json.loads(raw))
     queue.reset={'schema':'magento-fresh-native-queue-reset-v2','restored':restored,'baseline':queue.baseline,'full_channel_exact':restored==queue.baseline,'fresh_app_b_before_original_cleanup':True}
     queue.store.json('queue/reset.private.json',queue.reset,'native_observation_envelope')
    except BaseException as error:
     queue.store.json('queue/reset-unavailable.private.json',{'error_type':type(error).__name__,'reset_acceptance_inferred':False,'original_owned_cleanup_still_required':True},'native_observation_envelope')
   return cleanup(manager,spec)
  with patch.object(original.DedicatedCloneManager,'cleanup',check_reset):
   async with super().open_case(case,out_dir) as active:
    queue=NativeQueue(active,out_dir,started);active.native_queue=queue
    try:
     await queue.start();active.page=PassivePage(active.page,queue)
     yield active
    finally:
     try:
      if queue.owner is not None:await queue.close()
     finally:queue.store.json('queue/probes.private.json',{'probes':queue.probes},'native_observation_envelope')
  profile.require(queue is not None and queue.reset is not None and queue.reset['full_channel_exact'] is True and time.monotonic()-started<=1200,'Native queue reset or total lifecycle1200 unproved')
  queue.store.json('queue/lifecycle.private.json',{'started_monotonic':started,'ended_monotonic':time.monotonic(),'seconds_limit':1200,'original_clone_reset_completed':True},'native_observation_envelope')


def _read(root,name):
 path=Path(root)/name;profile.require(path.is_file() and not path.is_symlink() and path.stat().st_mode&0o077==0,'Private queue evidence missing/unsafe');return json.loads(path.read_bytes())

def queue_verdict(root):
 root=Path(root);clock=_read(root,'actor-clock/end.private.json');end=clock['actor_ended_monotonic'];probes=_read(root,'queue/probes.private.json')['probes']
 eligible=[p for p in probes if p['observed_monotonic']<=end];profile.require(eligible,'No actual queue observation before actor end')
 last=eligible[-1];ref=last['reference'];policy.verify_artifact(root,ref);state=_read(root,ref['path'])
 profile.validate_owner(state['native_process'],state['native_process']['owner']['token']);profile.validate_queue(state['queue'])
 actions=_read(root,'actions.private.json')['actions']
 if actions and actions[-1]['action']['type']=='finish':
  capsule=_read(root,actions[-1]['contract']['native_surface_guard']['path']);meta=_read(root,capsule['current']['raw_envelope']['path']);meta.pop('native_window_sha256',None)
  profile.require(policy.digest(meta)==state['native_context_sha256'],'Finish queue state not tied to actual predispatch native metadata')
 else:
  mutations=[e['completed_monotonic'] for e in clock['native_io'] if e['operation'] in {'mouse.click','keyboard.insert_text','keyboard.press'}]
  if mutations and state['observed_monotonic']<max(mutations):return {'schema':'magento-independent-queue-clock-verdict-v2','score':0,'reason':'latest_native_mutation_not_followed_by_in_budget_queue_read','actor_end_monotonic':end}
 return {'schema':'magento-independent-queue-clock-verdict-v2','score':int(state['queue']['pending']==0 and state['queue']['failed']==0),'reason':'native_queue_complete_before_actor_end' if state['queue']['pending']==0 and state['queue']['failed']==0 else 'known_native_queue_pending_or_failed_at_actor_end','actor_end_monotonic':end,'queue_reference':ref}

async def run_task(**kwargs):
 row=await original_run_task(**kwargs)
 verdict=queue_verdict(kwargs['output']);store=EvidenceStore(kwargs['output']);reference=store.json('queue/verifier.private.json',verdict,'native_observation_envelope')
 return {**row,'original_sql_score':row['score'],'score':int(row['score']==1 and verdict['score']==1),'queue_clock_verdict':reference,'native_queue_profile':profile.PROFILE}
