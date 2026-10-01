"""Owned X11/AT-SPI action transport using the shared semantic native policy.

Raw full screenshots are retained and returned unchanged. Readiness and action
admission use native identity/state/geometry, never pixel equality or answers.
Original guest setup/attestation/save IO and scoring remain evaluator-owned.
"""
from __future__ import annotations
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import shlex
import time
from cursibench import native_surface_guard_policy_v1 as guard
from cursibench.scale_action_contract import ContractLimits,make_observation,ContractError
from cursibench.scale_action_output_v066 import normalize_model_action
from . import deadline_model_transport_v21 as legacy
from .native_accessibility_probe_v23 import SCHEMA as PROBE_SCHEMA
from .v066_storage_budget import reserve_and_write
from .factory import digest
from .qwen_v066_adapter import dispatch as native_dispatch
from .post_enter_control_proxy_v9 import SAMPLE_DELAYS_MS as ENTER_DELAYS_MS

MAX_ACTIONS=90;ACTOR_WALL_SECONDS=720;LEASE_SECONDS=1200
SAMPLE_DELAYS_MS=(0,250,250,500,500,500,500)
PROBE_PATH='/tmp/envloop-native-accessibility-v23.py'
PROBE_SOURCE=Path(__file__).with_name('native_accessibility_probe_v23.py')
POLICY_SHA=guard.POLICY_SHA
ModelSampler=legacy.ModelSampler
checked_deadline_proof=legacy.checked_deadline_proof
RENDERER=legacy.RENDERER;PROCESSOR=legacy.PROCESSOR;MODEL=legacy.MODEL

def require(ok,code):
 if not ok:raise ValueError(code)
def canonical(value):return guard.canonical(value)
def put(root,path,raw):
 ref=reserve_and_write(root,path,raw)
 return {'schema':'native-guard-artifact-ref-v1','path':str(path.relative_to(root)),'sha256':digest(raw),'size':len(raw),'kind':'dispatch_receipt'}
def json_put(root,path,value):return put(root,path,canonical(value))

def stable_metadata(meta):
 return {k:meta[k] for k in ['window_id_sha256','native_pid','native_uid','owned_document_window','owned_native_application','view_id','context_id','modal_id','focus_id','targets']}

class SemanticInputProxy:
 def __init__(self,actor):self.actor=actor;self.sandbox=actor.sandbox;self.enter_count=0;self.current_actor_step=None
 def __getattr__(self,key):return getattr(self.sandbox,key)
 def press(self,key):
  if str(key).lower() not in ['enter','return'] or not self.actor.filename.endswith('.xlsx'):return self.sandbox.press(key)
  require(self.enter_count<90 and type(self.current_actor_step) is int,'Semantic native Enter bound/step missing')
  self.actor.native_probe('before-enter');result=self.sandbox.press(key);ordinal=self.enter_count;self.enter_count+=1;started=time.monotonic();states=[]
  for sample,delay in enumerate(ENTER_DELAYS_MS):
   if delay:time.sleep(delay/1000)
   image,meta=self.actor.capture('post-enter');states.append(stable_metadata(meta))
   json_put(self.actor.root,self.actor.out/f'semantic-enter-{ordinal:03d}-{sample:02d}.private.json',{'preceding_actor_step':self.current_actor_step,'delay_ms':delay,
    'captured_at':time.monotonic(),'native':states[-1],'image':put(self.actor.root,self.actor.out/f'semantic-enter-{ordinal:03d}-{sample:02d}.png',image),'pixel_equality_required':False})
  require(states[-1]==states[-2] and time.monotonic()-started<=60,'Native post-Enter state failed to settle')
  self.actor.pending=True;return result

class SemanticModelGuest(legacy.ModelGuest):
 def __init__(self,*args,lease_started_monotonic=None,**kwargs):
  super().__init__(*args,**kwargs);self.lease_started=lease_started_monotonic or time.monotonic();self.last_observation=None;self.last_envelope=None;self.pending=False;self.native_sequence=0;self.consumed=set();self.quarantined=False;self.proxy=SemanticInputProxy(self)
 def prepare(self,**kwargs):
  super().prepare(**kwargs)
  self.sandbox.files.write(PROBE_PATH,PROBE_SOURCE.read_bytes())
  meta=self.native_probe('prepared')
  require(meta['owned_document_window'] and meta['owned_native_application'] and meta['modal_id']=='none','Semantic native owned document not ready')
  evidence=json_put(self.root,self.out/'semantic-lease.private.json',{'sandbox_id_sha256':digest(self.sandbox.sandbox_id.encode()),'native_window_sha256':meta['window_id_sha256'],'native_account_sha256':meta['account_sha256'],'lease_started_monotonic':self.lease_started,'expires_at':self.lease_started+1200,'probe_sha256':digest(PROBE_SOURCE.read_bytes())});evidence['kind']='lease_evidence'
  self.lease={'schema':'native-surface-lease-v1','lease_id':digest(self.sandbox.sandbox_id.encode())[:32],'cell_id':'desktop-native','account_sha256':meta['account_sha256'],'workspace_sha256':digest(self.sandbox.sandbox_id.encode()),
   'window_sha256':meta['window_id_sha256'],'owner_sha256':digest((meta['window_id_sha256']+meta['account_sha256']).encode()),'issued_at':self.lease_started,'expires_at':self.lease_started+1200,'evidence':evidence}
  guard.validate_lease(self.lease)
 def native_probe(self,phase):
  command='python3 '+shlex.quote(PROBE_PATH)+' --filename '+shlex.quote(self.filename)+' --width 1280 --height 800'
  result=self.sandbox.commands.run(command,request_timeout=12)
  raw={'schema':'cua-native-guest-probe-command-v23','phase':phase,'exit_code':result.exit_code,'stdout':result.stdout,'stderr':result.stderr,'command_sha256':digest(command.encode())}
  json_put(self.root,self.out/f'native-probe-{self.native_sequence:03d}.private.json',raw);self.native_sequence+=1
  require(result.exit_code==0 and len(result.stdout)<=262144 and not result.stderr,'Native accessibility probe failed')
  meta=json.loads(result.stdout);require(meta.get('schema')==PROBE_SCHEMA and meta.get('status')=='observed' and meta['probe_source_sha256']==digest(PROBE_SOURCE.read_bytes()) and meta['native_mutations']==0 and meta['raster_equality_used'] is False,'Actual trusted native metadata unavailable or changed')
  return meta
 def capture(self,phase):
  before=self.native_probe(phase+'-before');image=bytes(self.sandbox.screenshot());after=self.native_probe(phase+'-after')
  require(stable_metadata(before)==stable_metadata(after),'Native context changed across screenshot capture')
  return image,after
 def lease_check(self,lease):
  now=time.monotonic();running=self.sandbox.is_running(request_timeout=12)
  ref=json_put(self.root,self.out/f'lease-check-{self.native_sequence:03d}.private.json',{'sandbox_id_sha256':digest(self.sandbox.sandbox_id.encode()),'is_running':running,'checked_at':now});self.native_sequence+=1;ref['kind']='lease_check'
  return {'schema':'native-surface-lease-check-v1','lease_sha256':guard.digest(lease),'status':'active' if running and not self.killed and now<self.lease['expires_at'] else 'inactive','checked_at':now,'expires_at':min(self.lease['expires_at'],now+10),'evidence':ref}
 def envelope(self,phase,observation,image,meta):
  stem=f'semantic-{observation.step:03d}-{phase}'
  image_ref=put(self.root,self.out/(stem+'.png'),image);image_ref['kind']='raw_'+phase+'_image'
  native_ref=json_put(self.root,self.out/(stem+'-native.private.json'),meta);native_ref['kind']='native_'+phase+'_envelope'
  value={'schema':'native-surface-envelope-v1','policy_sha256':guard.POLICY_SHA,'phase':phase,'lease':self.lease,'task_id':observation.task_id,'task_binding_sha256':observation.task_binding_sha256,
   'frame_id':observation.frame_id,'step':observation.step,'captured_at':time.monotonic(),'expires_at':observation.expires_at,'viewport':meta['viewport'],'view_id':meta['view_id'],'context_id':meta['context_id'],'modal_id':meta['modal_id'],'focus_id':meta['focus_id'],
   'allowed_views':[meta['view_id']],'allowed_modals':['none'],'allowed_focus':self.last_envelope['allowed_focus'] if phase=='predispatch' else list(dict.fromkeys([meta['focus_id']]+[t['ref'] for t in meta['targets'] if t['keyboard']])),
   'owned_surface':meta['owned_document_window'] and meta['owned_native_application'] and meta['account_sha256']==self.lease['account_sha256'] and meta['window_id_sha256']==self.lease['window_sha256'],
   'targets':meta['targets'],'raw_image':image_ref,'raw_envelope':native_ref}
  guard.validate_envelope(value);json_put(self.root,self.out/(stem+'-envelope.private.json'),value);return value
 def observe(self,*,identity,instruction,step,previous=None,memory=''):
  require(not self.quarantined and not self.killed,'Semantic native actor is terminal')
  captures=[]
  for sample,delay in enumerate(SAMPLE_DELAYS_MS if self.pending else (0,)):
   if delay:time.sleep(delay/1000)
   image,meta=self.capture('observation');captures.append((image,meta))
   if self.pending:json_put(self.root,self.out/f'semantic-readiness-{step:03d}-{sample:02d}.private.json',{'delay_ms':delay,'native':stable_metadata(meta),'image':put(self.root,self.out/f'semantic-readiness-{step:03d}-{sample:02d}.png',image),'pixel_equality_required':False})
  if self.pending:require(all(stable_metadata(m)==stable_metadata(captures[-1][1]) for _,m in captures[-4:]),'Native readiness state not stable')
  self.pending=False;image,meta=captures[-1]
  observation=make_observation(task_id=identity['task_id'],task_binding_sha256=identity['package_sha256'],instruction=instruction,step=step,screenshot_bytes=image,previous_action_result=previous,memory=memory,limits=ContractLimits(max_step=90))
  self.last_envelope=self.envelope('observation',observation,image,meta);self.last_observation=observation;return observation
 def native_input(self,action,predispatch):
  kind=action['type']
  if kind not in ['type','key']:return native_dispatch(self.proxy,action)
  if 'target' in action:
   target=action['target'];require(set(target)=={'x','y'},'Native keyboard target must be observed coordinates')
   self.proxy.left_click(target['x'],target['y'])
  focus=self.native_probe('verified-keyboard-focus')
  require(focus['owned_document_window'] and focus['window_id_sha256']==predispatch['window_id_sha256'] and focus['context_id']==predispatch['context_id'] and focus['focus_editable'],
   'Actual native editable focus must be verified after pointer before keyboard')
  if 'target' in action:
   target=action['target'];candidates=[t for t in focus['targets'] if t['keyboard'] and t['visible'] and t['enabled'] and not t['obscured'] and t['bounds'][0]<=target['x']<t['bounds'][0]+t['bounds'][2] and t['bounds'][1]<=target['y']<t['bounds'][1]+t['bounds'][3]]
   candidates.sort(key=lambda t:t['bounds'][2]*t['bounds'][3]);require(candidates and candidates[0]['ref']==focus['focus_id'],'Native targeted keyboard focus changed')
  if kind=='type' and action['mode']=='fill':
   require(focus['focus_fill_scope_verified'],'Native fill requires actual editable field scope')
   self.proxy.press(['ctrl','a']);self.proxy.write(action['text']);return kind
  projected={k:v for k,v in action.items() if k!='target'}
  return native_dispatch(self.proxy,projected)
 def dispatch_model(self,raw,observation,*,actor_deadline):
  require(time.monotonic()<actor_deadline and observation is self.last_observation and observation.frame_id not in self.consumed,'Current semantic native frame/clock required')
  action=normalize_model_action(raw,observation,current_frame_id=observation.frame_id)
  image,meta=self.capture('predispatch');current=self.envelope('predispatch',observation,image,meta)
  decision=guard.decision(self.last_envelope,current,action,lease_check=self.lease_check);self.consumed.add(observation.frame_id)
  decision_ref=json_put(self.root,self.out/f'semantic-{observation.step:03d}-decision.private.json',decision)
  json_put(self.root,self.out/f'semantic-{observation.step:03d}-nonce.private.json',{'frame_id':observation.frame_id,'consumed':True})
  status=decision['status'];intent=None;driver=None;driver_result='not_attempted'
  if status=='accepted':
   require(time.monotonic()<actor_deadline,'Semantic actor deadline before native IO')
   intent=json_put(self.root,self.out/f'semantic-{observation.step:03d}-intent.private.json',{'decision_sha256':guard.digest(decision),'action':action});intent['kind']='action_intent'
   try:
    self.proxy.current_actor_step=observation.step
    # This is the same documented low-level GUI driver; strict/caret parsing
    # is deliberately not called. No action is retargeted or replayed.
    kind=self.native_input(action,meta)
    require(time.monotonic()<=actor_deadline,'Native IO completed after actor deadline')
    status='applied';driver_result='succeeded'
    driver=json_put(self.root,self.out/f'semantic-{observation.step:03d}-driver.private.json',{'returned_action_type':kind,'native_io_completed_monotonic':time.monotonic()});driver['kind']='driver_result'
   except BaseException:
    status='failed';driver_result='unknown';self.quarantined=True;driver=json_put(self.root,self.out/f'semantic-{observation.step:03d}-driver.private.json',{'status':'uncertain_no_retry'});driver['kind']='driver_result'
  if status=='hard_stop':self.quarantined=True
  receipt={'schema':'native-surface-dispatch-receipt-v1','policy_sha256':guard.POLICY_SHA,'decision_sha256':guard.digest(decision),'action_sha256':guard.digest(action),'frame_id':observation.frame_id,'step':observation.step,
   'status':status,'reason':decision['reason'] if status in ['rejected','hard_stop'] else 'native_driver_succeeded' if status=='applied' else 'native_driver_uncertain','turn_consumed':True,'nonce_invalidated':True,'intent':intent,'driver_result':driver_result,'driver_evidence':driver}
  guard.validate_receipt(receipt);ref=json_put(self.root,self.out/f'semantic-{observation.step:03d}-receipt.private.json',receipt)
  if self.quarantined:raise guard.GuardError(receipt['reason'])
  self.pending=self.pending or status=='applied' and (legacy.readiness.needs_readiness(action))
  return action,{'observation':self.last_envelope['raw_image'],'predispatch':current['raw_image'],'caret_resamples':[],'frame_id_sha256':digest(observation.frame_id.encode()),'action_type':action['type'],'native_status':status,'native_dispatch_receipt':ref}

def create_guest(*,root,out,filename):
 from .reconcile_interrupted_sweep import active_hashes
 active,count=active_hashes();require(not active and count==0,'Semantic native create requires active-zero')
 started=time.monotonic();old=legacy.create_guest(root=root,out=out,filename=filename)
 return SemanticModelGuest(old.sandbox,root=root,out=out,filename=filename,lease_started_monotonic=started)
