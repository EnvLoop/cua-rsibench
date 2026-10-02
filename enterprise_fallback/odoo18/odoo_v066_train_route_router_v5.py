"""Compose finite border material identity across a complete RFQ edit flow."""
from __future__ import annotations
import json
from urllib.parse import urlsplit
from cursibench.scale_action_contract import ContractError
from cursibench.scale_action_contract_v066 import validate_action
from cursibench.scale_action_output_v066 import normalize_model_action
from .odoo_native_adapter import _digest
from .odoo_v066_train_adapter import OdooV066TrainAdapter
from .odoo_v066_train_route_router_v1 import _canonical
from .odoo_v066_train_route_router_v4 import OdooV066TrainRouteRouterV4,border_material,TOP_POINTS,BOTTOM_POINTS

PROFILE="train-calibrated-finite-border-rfq-edit-flow-2026-09-30-v13"
FLOW_CONTEXT_JS=r"""({rfq_id,route_path,target}) => {
 const visible=el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return r.width>2&&r.height>2&&s.display!=='none'&&s.visibility!=='hidden';};
 if(location.pathname!==route_path||document.querySelector('iframe.o-FileViewer-view'))return null;
 const form=document.querySelector('.o_form_view');
 if(!form||!visible(form)||!((form.innerText||'').match(/[A-Z0-9-]+/g)||[]).includes(rfq_id))return null;
 if(Array.from(document.querySelectorAll('.modal.show,.o_dialog,[role="dialog"],dialog[open],[aria-modal="true"]')).some(visible))return null;
 const active=document.activeElement;if(!active)return null;
 const identity=el=>{const r=el.getBoundingClientRect();return {tag:el.tagName.toLowerCase(),type:el.type||'',name:el.getAttribute('name')||'',
   ref:el.getAttribute('data-envloop-ref')||'',value:typeof el.value==='string'?el.value:null,disabled:!!el.disabled,readonly:!!el.readOnly,
   bounds:[r.left,r.top,r.right,r.bottom]};};
 const focused=identity(active);
 const hit=target?document.elementFromPoint(target.x,target.y):null;
 const targetEl=hit?hit.closest('[data-envloop-ref]'):null;
 if(target&&(!targetEl||!visible(targetEl)||targetEl.disabled))return null;
 return {rfq_id,route_path,modal_absent:true,viewer_absent:true,focus:focused,
   focus_in_form:form.contains(active),focus_is_body:active===document.body,target:targetEl?identity(targetEl):null};
}"""


def valid_context(raw):
 return (type(raw) is dict and set(raw)=={'rfq_id','route_path','modal_absent','viewer_absent','focus','focus_in_form','focus_is_body','target'} and
         raw.get('modal_absent') is raw.get('viewer_absent') is True and
         (raw.get('focus_in_form') is True or raw.get('focus_is_body') is True) and
         type(raw.get('focus')) is dict and set(raw['focus'])=={'tag','type','name','ref','value','disabled','readonly','bounds'} and
         raw['focus'].get('disabled') is False and type(raw['focus'].get('bounds')) is list and len(raw['focus']['bounds'])==4)


class OdooV066TrainRouteRouterV5(OdooV066TrainRouteRouterV4):
 def __init__(self,*args,**kwargs):
  super().__init__(*args,**kwargs);self.observed_flow_context=None;self.observed_flow_frame_id=None
  self._flow_action=None;self._flow_context=None;self._flow_parse_guard=None;self._flow_dispatch_guard=None

 def _context(self,target=None):
  selected=self.current_price_target
  if selected is None:return None
  raw=self.page.evaluate(FLOW_CONTEXT_JS,{'rfq_id':selected['rfq_id'],'route_path':selected['route_path'],'target':target})
  return raw if valid_context(raw) else None

 def observe_for_model(self,*,memory=''):
  observation,rendered=super().observe_for_model(memory=memory)
  self.observed_flow_context=self._context();self.observed_flow_frame_id=observation.frame_id
  return observation,rendered

 def _eligible(self,action):
  if action['type'] not in ('key','type','click','wait'):return False
  if self.observed_flow_context is None or border_material(self.latest.screenshot_bytes) is None:return False
  if action['type']=='type' and 'target' not in action:
   f=self.observed_flow_context['focus']
   if f['tag'] not in ('input','textarea') or f['readonly'] is not False or not self.observed_flow_context['focus_in_form']:return False
  if action['type']=='key' and action.get('key') in ('Control+A','Meta+A'):
   f=self.observed_flow_context['focus']
   if f['tag'] not in ('input','textarea') or f['readonly'] is not False or not self.observed_flow_context['focus_in_form']:return False
  if action['type']=='click':
   context=self._context(action.get('target'));target=None if context is None else context['target']
   if target is None:return False
   save=any(c.ref==target['ref'] and c.label=='Save' and c.visible and c.enabled for c in self.latest.controls)
   if target['name']!='price_unit' and not save:return False
  return True

 def _flow_identity_current(self,observation):
  action=self._flow_action
  if (action is None or self.latest is not observation or self.observed_flow_frame_id!=observation.frame_id or
      observation.task_id!=self.task_id or observation.task_binding_sha256!=self.task_binding_sha256 or
      action.get('task_id')!=self.task_id or action.get('task_binding_sha256')!=self.task_binding_sha256 or
      action.get('frame_id')!=observation.frame_id or self.page.url!=self.latest_url):return False
  current=self._context(action.get('target'))
  return current is not None and current==self._flow_context

 def _frame_current(self,observation,*,stage):
  if self._flow_action is None:return super()._frame_current(observation,stage=stage)
  if stage not in ('parse','dispatch') or not self._flow_identity_current(observation):return False
  observed=border_material(observation.screenshot_bytes)
  if observed is None:return False
  records=[]
  for sample in range(3):
   if not self._flow_identity_current(observation):return False
   raw=self.page.screenshot(type='png');material=border_material(raw)
   accepted=material is not None and material['canonical_material_sha256']==observed['canonical_material_sha256']
   ref=self._save_price_frame(observation,stage+'_rfq_flow_material',sample,raw,'material_confirmed' if accepted else 'unknown_border_or_material_rejected')
   self.frame_guard_samples[-1].update(border_state_class=None if material is None else material['state_class'],
                                      canonical_material_sha256=None if material is None else material['canonical_material_sha256'])
   records.append({'frame_ref':ref,'raw_frame_sha256':_digest(raw),'material':material})
   if not accepted or not self._flow_identity_current(observation):return False
  guard={'profile':PROFILE,'stage':stage,'observed_frame_sha256':observation.screenshot['sha256'],
   'observed_frame_id_sha256':_digest(observation.frame_id.encode()),'action_sha256':_digest(_canonical(self._flow_action)),
   'observed_url':self.latest_url,'physical_url':self.page.url,'observed_material':observed,
   'observed_context':self.observed_flow_context,'context':self._flow_context,'sampled_material_frames':records,'canonical_material_sha256':observed['canonical_material_sha256'],
   'classification':'two_final_material_frames_confirmed'}
  if stage=='parse':self._flow_parse_guard=guard
  else:self._flow_dispatch_guard=guard
  return True

 def parse_current_action(self,raw):
  observation=self.latest
  if observation is None:raise ContractError('stale_frame')
  action=normalize_model_action(raw,observation,current_frame_id=observation.frame_id)
  if not self._eligible(action):return super().parse_current_action(raw)
  context=self._context(action.get('target'))
  if context is None or {**context,'target':None}!=self.observed_flow_context:raise ContractError('stale_frame')
  target=action.get('target')
  if target and any(abs(target['x']-x)<=8 and abs(target['y']-y)<=8 for x,y in (*TOP_POINTS,*BOTTOM_POINTS)):raise ContractError('stale_frame')
  if target:
   current=context['target'];bounds=None if current is None else current.get('bounds')
   matches=[] if current is None else [c for c in observation.controls if c.ref==current.get('ref') and c.visible and c.enabled]
   if (len(matches)!=1 or type(bounds) is not list or len(bounds)!=4 or
       not (bounds[0]<=target['x']<=bounds[2] and bounds[1]<=target['y']<=bounds[3])):raise ContractError('stale_frame')
  self._flow_action=action;self._flow_context=context;self._flow_parse_guard=None
  if not self._frame_current(observation,stage='parse'):
   self._flow_action=None;self._flow_context=None
   self._decision(observation,action,route_kind='generic_rfq',status='nonclaim',reason_code='finite_flow_material_or_focus_rejected')
   raise ContractError('stale_frame')
  self._decision(observation,action,route_kind='generic_rfq',status='claimed',reason_code='claimed')
  return action

 def dispatch(self,raw_action,*,route_token):
  if self._flow_action is None:return super().dispatch(raw_action,route_token=route_token)
  observation=self.latest;claim=self.parsed_route_claim
  if observation is None or claim is None or claim.get('route_token')!=route_token:raise ContractError('stale_frame')
  action=validate_action(raw_action,observation,current_frame_id=observation.frame_id)
  if action!=self._flow_action or claim.get('action_sha256')!=_digest(_canonical(action)):raise ContractError('stale_frame')
  try:
   self._flow_dispatch_guard=None
   applied=OdooV066TrainAdapter.dispatch(self,action)
   if self._flow_dispatch_guard is None:raise ContractError('stale_frame')
   receipt=applied['public_contract_receipt'];receipt.update(rfq_flow_parse_guard=self._flow_parse_guard,
      rfq_flow_dispatch_guard=self._flow_dispatch_guard,route_kind='generic_rfq',route_token_sha256=_digest(route_token.encode()),
      route_claim_ref_sha256=self.parsed_route_claim_ref['sha256'])
   return applied
  finally:
   self._flow_action=None;self._flow_context=None;self._flow_parse_guard=None;self._flow_dispatch_guard=None
   self.parsed_route_claim=None;self.parsed_route_claim_ref=None


__all__=['OdooV066TrainRouteRouterV5','PROFILE','FLOW_CONTEXT_JS','valid_context']
