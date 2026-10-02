"""Cell-generic native Office action gate with shared immutable policy.

The native host supplies current UI metadata and cropped bytes. This module
uses no task answers, values, Graph operation or screenshot equality test.
"""
from __future__ import annotations
import json,time,os
from pathlib import Path
from dataclasses import replace
from cursibench import native_surface_guard_policy_v1 as policy
from cursibench.scale_action_contract import ContractLimits,make_observation
from cursibench.scale_action_contract_v066 import validate_action
from tools.office_owned_folder_runtime_v2 import require,sha,canonical,write_new

class OwnedNativeActor:
 def __init__(self,host,*,actor_task,item,lease,artifact_root,clock=time.monotonic):
  self.host,self.task,self.item,self.lease=host,actor_task,item,lease;self.root=Path(artifact_root);self.root.mkdir(mode=0o700,exist_ok=False)
  self.clock=clock;self.step=0;self.frame=None;self.envelope=None;self.previous=None;self.finished=False;self.quarantined=False
  self.native_policy_sha256=policy.POLICY_SHA;self.consumed=set();policy.validate_lease(lease)
 def put(self,name,raw,kind):
  path=self.root/name;path.parent.mkdir(mode=0o700,parents=True,exist_ok=True);write_new(path,raw)
  return {'schema':'native-guard-artifact-ref-v1','path':name,'sha256':sha(raw),'size':len(raw),'kind':kind}
 def json(self,name,value,kind):return self.put(name,policy.canonical(value),kind)
 def owned(self,meta):
  return (meta.get('account_principal_sha256')==self.lease['account_sha256'] and meta.get('folder_scope_sha256')==self.lease['workspace_sha256'] and
   meta.get('document_identity_sha256')==self.item['item_identity_sha256'] and meta.get('window_sha256')==self.lease['window_sha256'] and
   meta.get('owned_document_editing') is True and meta.get('private_header_excluded') is True)
 def collect(self,phase,observation,capture=None):
  capture=capture or self.host.current_native_surface(self.item,phase=phase);image=capture['cropped_image_bytes'];meta=capture['native_metadata']
  prefix=f'turn-{self.step:03d}/{phase}';image_ref=self.put(prefix+'.image',image,'raw_'+phase+'_image')
  native_ref=self.json(prefix+'-native.private.json',meta,'native_'+phase+'_envelope')
  targets=meta['targets'];focus=meta['focus_id'];tick=self.clock()
  value={'schema':'native-surface-envelope-v1','policy_sha256':policy.POLICY_SHA,'phase':phase,'lease':self.lease,
   'task_id':observation.task_id,'task_binding_sha256':observation.task_binding_sha256,'frame_id':observation.frame_id,'step':self.step,
   'captured_at':tick,'expires_at':observation.expires_at,'viewport':meta['viewport'],'view_id':self.task['cell_id']+'-document',
   'context_id':meta['native_context_id'],'modal_id':meta['modal_id'],'focus_id':focus,
   'allowed_views':[self.task['cell_id']+'-document'],'allowed_modals':['none','owned-editor-dialog'],
   'allowed_focus':self.envelope['allowed_focus'] if self.envelope else list(dict.fromkeys([focus]+[t['ref'] for t in targets if t['keyboard']])),
   'owned_surface':self.owned(meta),'targets':targets,'raw_image':image_ref,'raw_envelope':native_ref}
  policy.validate_envelope(value);self.json(prefix+'-envelope.private.json',value,'native_'+phase+'_envelope');return value,image
 def observe(self,*,memory=''):
  require(not self.quarantined and not self.finished,'Native actor cannot observe after terminal state')
  capture=self.host.current_native_surface(self.item,phase='observation')
  image=capture['cropped_image_bytes'];meta=capture['native_metadata'];require(self.owned(meta),'Native Office lease/document lost')
  previous=self.previous
  if previous and previous['status']=='rejected':previous={'status':'rejected','code':'invalid_action'}
  obs=make_observation(task_id=self.task['task_id'],task_binding_sha256=self.task['package_sha256'],instruction=self.task['visible_instruction'],step=self.step,
   screenshot_bytes=image,memory=memory,previous_action_result=previous,limits=ContractLimits(max_step=90))
  # The host-returned single capture is consumed exactly once; no image-equality
  # retry or second observation snapshot decides correctness.
  self.envelope,_=self.collect('observation',obs,capture)
  self.frame=obs;return obs
 def current_frame_id(self):return self.frame.frame_id if self.frame and not self.quarantined and self.clock()<=self.frame.expires_at else 'stale'
 def reject_model_output(self,text):
  require(self.frame is not None and not self.quarantined and type(text) is str,'Native current frame required for invalid output')
  current,_=self.collect('predispatch',self.frame)
  decision=policy.decision(self.envelope,current,{},lease_check=self.host.check_native_lease)
  require(decision['status'] in ['rejected','hard_stop'],'Invalid model output must not authorize driver')
  self.json(f'turn-{self.step:03d}/decision.private.json',decision,'dispatch_receipt')
  self.put(f'turn-{self.step:03d}/invalid-model-output.private.txt',text.encode(),'dispatch_receipt')
  require(self.frame.frame_id not in self.consumed,'Native Office nonce replay');self.consumed.add(self.frame.frame_id)
  self.json(f'turn-{self.step:03d}/nonce.private.json',{'frame_id':self.frame.frame_id,'consumed':True},'dispatch_receipt')
  receipt={'schema':'native-surface-dispatch-receipt-v1','policy_sha256':policy.POLICY_SHA,'decision_sha256':policy.digest(decision),'action_sha256':sha(text.encode()),
   'frame_id':self.frame.frame_id,'step':self.step,'status':decision['status'],'reason':decision['reason'],'turn_consumed':True,'nonce_invalidated':True,
   'intent':None,'driver_result':'not_attempted','driver_evidence':None}
  policy.validate_receipt(receipt);self.json(f'turn-{self.step:03d}/receipt.private.json',receipt,'dispatch_receipt')
  self.step+=1;self.frame=None;self.envelope=None;self.previous={'status':'rejected','code':'invalid_action'}
  if decision['status']=='hard_stop':self.quarantined=True;raise policy.GuardError(decision['reason'])
  return self.previous
 def dispatch(self,action):
  require(self.frame is not None and not self.quarantined,'Native Office frame missing')
  checked=validate_action(action,self.frame,current_frame_id=self.frame.frame_id);current,_=self.collect('predispatch',self.frame)
  decision=policy.decision(self.envelope,current,checked,lease_check=self.host.check_native_lease)
  self.json(f'turn-{self.step:03d}/decision.private.json',decision,'dispatch_receipt')
  require(self.frame.frame_id not in self.consumed,'Native Office nonce replay');self.consumed.add(self.frame.frame_id)
  self.json(f'turn-{self.step:03d}/nonce.private.json',{'frame_id':self.frame.frame_id,'consumed':True},'dispatch_receipt')
  intent=None;driver=None;driver_result='not_attempted';status=decision['status'];reason=decision['reason']
  if status=='accepted':
   # Resolve accepted refs lazily. A native rerender must never retarget or wait
   # for an unrelated control advertised in the observation.
   resolved=self.host.resolve_current_action_targets(self.item,checked,current)
   require(resolved.get('status') in ['current','missing'],'Native target resolution uncertain')
   if resolved['status']=='missing':status='rejected';reason='target_not_current_and_safe'
   else:
    intent=self.json(f'turn-{self.step:03d}/intent.private.json',{'action':checked,'decision_sha256':policy.digest(decision)},'action_intent')
    try:
     result=self.host.dispatch_native_primitive(self.item,checked,resolved)
     require(result.get('status')=='applied' and result.get('focus_verified_before_keyboard',checked['type'] not in ['type','key']) is True,
      'Actual native driver success/focus not proved')
     status='applied';reason='native_driver_succeeded';driver_result='succeeded'
    except BaseException:
     status='failed';reason='native_driver_uncertain';driver_result='unknown';self.quarantined=True
    driver=self.json(f'turn-{self.step:03d}/driver.private.json',{'driver_result':driver_result},'driver_result')
  if status=='hard_stop':self.quarantined=True
  receipt={'schema':'native-surface-dispatch-receipt-v1','policy_sha256':policy.POLICY_SHA,'decision_sha256':policy.digest(decision),
   'action_sha256':policy.digest(checked),'frame_id':self.frame.frame_id,'step':self.step,'status':status,'reason':reason,
   'turn_consumed':True,'nonce_invalidated':True,'intent':intent,'driver_result':driver_result,'driver_evidence':driver}
  policy.validate_receipt(receipt);self.json(f'turn-{self.step:03d}/receipt.private.json',receipt,'dispatch_receipt')
  self.step+=1;self.frame=None;self.envelope=None;self.previous={'status':'applied','code':'ok'} if status=='applied' else {'status':'rejected','code':'invalid_action'}
  if status=='applied' and checked['type']=='finish':self.finished=True
  if self.quarantined:raise policy.GuardError(reason)
  return self.previous
