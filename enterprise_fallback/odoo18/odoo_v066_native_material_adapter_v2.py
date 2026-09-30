"""Common native Odoo action adapter; no task/oracle-directed route setup.

Only current native geometry and accepted complete finite vectors canonicalize a purchase
RFQ form. Every remaining RGB pixel and native page/editor identity stays
exact. Other pages, modal and PDF viewer states keep exact screenshot guards.
"""
from __future__ import annotations
from hashlib import sha256
import json
import math
from pathlib import Path
from urllib.parse import urlsplit
from cursibench.scale_action_contract import ContractError,make_observation
from cursibench.scale_action_contract_v066 import validate_action
from cursibench.scale_action_output_v066 import normalize_model_action,render_for_model
from . import odoo_native_adapter as native
from .odoo_v066_train_adapter import OdooV066TrainAdapter
from .odoo_native_geometry_material_v2 import (border_material,near_border,valid_geometry,NATIVE_GEOMETRY_JS)

PROFILE='native-observed-context-geometry-finite-material-v2'
VIEWPORT=native.VIEWPORT
VISIBLE_CONTROLS_JS=native.VISIBLE_CONTROLS_JS.replace(
 "'button,a,input,textarea,[role=\"tab\"],td[name]'",
 "'button,a,input,textarea,[role=\"tab\"],td[name],[class*=\"Attachment\"]'")
# Read current rendered identities only. These are not actor tools and do not
# obtain business answers, database IDs, credentials, RPC, or hidden records.
NATIVE_CONTEXT_JS=r"""(target) => {
 const visible=el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return r.width>2&&r.height>2&&r.right>0&&r.bottom>0&&r.left<innerWidth&&r.top<innerHeight&&s.display!=='none'&&s.visibility!=='hidden';};
 const bounds=el=>{const r=el.getBoundingClientRect();return [r.left,r.top,r.right,r.bottom];};
 const identity=el=>el?{tag:el.tagName.toLowerCase(),type:el.type||'',name:el.getAttribute('name')||'',ref:el.getAttribute('data-envloop-ref')||'',
   label:(el.getAttribute('aria-label')||el.getAttribute('title')||el.getAttribute('placeholder')||el.innerText||el.getAttribute('name')||'').trim().replace(/\s+/g,' ').slice(0,220),
   value:typeof el.value==='string'?el.value:null,disabled:!!el.disabled,readonly:!!el.readOnly,bounds:bounds(el)}:null;
 const forms=Array.from(document.querySelectorAll('.o_form_view')).filter(visible),form=forms.length===1?forms[0]:null;
 const viewers=Array.from(document.querySelectorAll('iframe.o-FileViewer-view')).filter(visible);
 const modals=Array.from(document.querySelectorAll('.modal.show,.o_dialog,[role="dialog"],dialog[open],[aria-modal="true"]')).filter(visible);
"""+NATIVE_GEOMETRY_JS+r"""
 const focused=identity(document.activeElement);
 const hit=target?document.elementFromPoint(target.x,target.y):null;
 const selected=hit?(hit.closest('[data-envloop-ref]')||hit):null;
 const row=selected?selected.closest('tr'):null;
 const heading=form?Array.from(form.querySelectorAll('h1,h2,[name="name"]')).filter(visible).map(el=>(typeof el.value==='string'?el.value:el.innerText||'').trim()).filter(Boolean):[];
 const rowIdentity=row?{bounds:bounds(row),product:Array.from(row.querySelectorAll('td[name="product_id"]')).filter(visible).map(el=>(el.innerText||'').trim()),
   editor:identity(selected),row_visible:visible(row)}:null;
 return {native_geometry:nativeGeometry,route_path:location.pathname,document_visible:document.visibilityState==='visible',top_window:window===window.top,
   form_count:forms.length,form_heading:heading,rfq_form:!!form&&/^\/odoo\/purchase\/[0-9]+$/.test(location.pathname)&&(form.innerText||'').includes('Request for Quotation'),
   modal_count:modals.length,viewer_count:viewers.length,focus:focused,focus_in_form:!!form&&form.contains(document.activeElement),
   focus_is_body:document.activeElement===document.body,target:selected&&visible(selected)?identity(selected):null,row:rowIdentity};
}"""


def _canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def _digest(value):return sha256(value).hexdigest()
def _bounds(value):
 return type(value) is list and len(value)==4 and all(type(v) in (float,int) and math.isfinite(v) for v in value) and value[0]<value[2] and value[1]<value[3]
def _identity(value):
 return (type(value) is dict and set(value)=={'tag','type','name','ref','label','value','disabled','readonly','bounds'} and
  all(type(value[k]) is str for k in ('tag','type','name','ref','label')) and (value['value'] is None or type(value['value']) is str) and
  type(value['disabled']) is bool and type(value['readonly']) is bool and _bounds(value['bounds']))


def valid_context(raw):
 fields={'route_path','document_visible','top_window','form_count','form_heading','rfq_form','modal_count','viewer_count','focus','focus_in_form','focus_is_body','target','row','native_geometry'}
 return (type(raw) is dict and set(raw)==fields and valid_geometry(raw['native_geometry']) and raw['document_visible'] is raw['top_window'] is True and
  type(raw['route_path']) is str and type(raw['form_heading']) is list and all(type(s) is str for s in raw['form_heading']) and
  all(type(raw[k]) is int and raw[k]>=0 for k in ('form_count','modal_count','viewer_count')) and
  all(type(raw[k]) is bool for k in ('rfq_form','focus_in_form','focus_is_body')) and _identity(raw['focus']) and
  (raw['target'] is None or _identity(raw['target'])) and
  (raw['row'] is None or (type(raw['row']) is dict and set(raw['row'])=={'bounds','product','editor','row_visible'} and
   _bounds(raw['row']['bounds']) and type(raw['row']['product']) is list and all(type(s) is str for s in raw['row']['product']) and
   _identity(raw['row']['editor']) and raw['row']['row_visible'] is True)))


def material_eligible(context,action):
 return (context['rfq_form'] and context['form_count']==1 and context['modal_count']==0 and context['viewer_count']==0 and
  (context['focus_in_form'] or context['focus_is_body']) and action.get('type') in ('click','double_click','type','key','wait') and
  not (action.get('type') in ('type','key') and 'target' not in action and not context['focus_in_form']))


class OdooV066NativeMaterialAdapter(native.OdooNativeAdapter):
 """One unchanged adapter class for trusted controls and all model paths."""
 def __init__(self,*args,**kwargs):
  # No expected target, price, source filename, phase, split or oracle argument.
  super().__init__(*args,**kwargs)
  self.frame_guard_sink=None;self.frame_guard_samples=[]
  self._native_page=self.page;self._observed_context=None;self._parsed_action=None;self._pending_context=None;self._pending_targets=None
  self._parse_guard=None;self._dispatch_guard=None

 def _context(self,target=None):
  raw=self.page.evaluate(NATIVE_CONTEXT_JS,target)
  return raw if valid_context(raw) and raw['route_path']==urlsplit(self.page.url).path else None

 def observe_for_model(self,*,memory=''):
  self._within_budget()
  for _ in range(8):  # Preserve the original observation stability bound.
   controls=self.page.evaluate(VISIBLE_CONTROLS_JS);before_context=self._context();screenshot=self.page.screenshot(type='png')
   self.page.wait_for_timeout(120)
   if _digest(self.page.screenshot(type='png'))==_digest(screenshot) and before_context is not None and self._context()==before_context:break
  else:raise ContractError('invalid_observation')
  visible='\n'.join(f"{c['role']}: {c['label']}" for c in controls if c['label'])[:12000]
  observation=make_observation(task_id=self.task_id,task_binding_sha256=self.task_binding_sha256,instruction=self.instruction,
   step=self.step,screenshot_bytes=screenshot,a11y_text=visible,controls=controls,previous_action_result=self.previous_result,memory=memory,limits=self.limits)
  self.latest=observation;self.latest_url=self.page.url;self._observed_context=before_context
  self._parsed_action=None;self._pending_context=None
  if self._observed_context is None:raise ContractError('invalid_observation')
  return observation,render_for_model(observation)

 def _context_for_action(self,action):
  slots=[('target',action['target'])] if 'target' in action else [('from',action['from']),('to',action['to'])] if action['type']=='drag' else []
  context=self._context();targets=[]
  if context is None or context!=self._observed_context:return None
  for slot,target in slots:
   try:x,y=self._point(target)
   except (ContractError,KeyError,TypeError):return None
   point={'x':x,'y':y};current=self._context(point)
   if current is None or {**current,'target':None,'row':None}!=self._observed_context:return None
   control=current['target']
   if control is None or control['disabled']:return None
   b=control['bounds']
   if not (b[0]<=x<=b[2] and b[1]<=y<=b[3]):return None
   if near_border(point,current['native_geometry']):return None
   targets.append({'slot':slot,'point':point,'context':current})
  if targets:context=targets[0]['context']
  focused=context['target'] if 'target' in action and action['type'] in ('type','key') else context['focus']
  if action['type']=='type' or (action['type']=='key' and action['key'] in ('Control+A','Meta+A')):
   if focused['tag'] not in ('input','textarea') or focused['disabled'] or focused['readonly']:return None
  return context,targets

 def _current(self,observation):
  action=self._parsed_action
  return (self.page is self._native_page and self.latest is observation and self.page.url==self.latest_url and
   observation.task_id==self.task_id and observation.task_binding_sha256==self.task_binding_sha256 and
   action is not None and action.get('task_id')==self.task_id and action.get('task_binding_sha256')==self.task_binding_sha256 and
   action.get('frame_id')==observation.frame_id and self._context_for_action(action)==(self._pending_context,self._pending_targets))

 def _save_guard(self,observation,stage,sample,raw,material):
  if not callable(self.frame_guard_sink):raise ContractError('invalid_observation')
  ref=self.frame_guard_sink(len(self.frame_guard_samples),raw)
  if type(ref) is not dict or ref.get('sha256')!=_digest(raw):raise ContractError('invalid_observation')
  row={'step':self.step,'stage':stage,'sample':sample,'observed_frame_sha256':observation.screenshot['sha256'],
   'observed_frame_id_sha256':_digest(observation.frame_id.encode()),'sampled_frame_ref':ref,'raw_frame_sha256':_digest(raw),'material':material,'sample_native_context':self._context()}
  self.frame_guard_samples.append(row);return row

 def _frame_current(self,observation,*,stage):
  if stage not in ('parse','dispatch') or not self._current(observation):return False
  context=self._pending_context
  known_refs={c.ref for c in observation.controls if c.visible and c.enabled}
  eligible=material_eligible(context,self._parsed_action) and all(row['context']['target']['ref'] in known_refs for row in self._pending_targets)
  observed=border_material(observation.screenshot_bytes,context['native_geometry']) if eligible else None
  mode='finite_rfq_material' if observed is not None else 'exact_full_png'
  records=[]
  for sample in range(3):
   if not self._current(observation):return False
   raw=self.page.screenshot(type='png');material=border_material(raw,context['native_geometry']) if observed is not None else None
   records.append(self._save_guard(observation,stage,sample,raw,material))
   if (observed is None and raw!=observation.screenshot_bytes) or (observed is not None and (material is None or material['canonical_material_sha256']!=observed['canonical_material_sha256'])) or records[-1]['sample_native_context']!=self._observed_context or not self._current(observation):return False
  guard={'profile':PROFILE,'stage':stage,'mode':mode,'classification':'two_final_material_frames_confirmed' if observed is not None else 'two_final_exact_frames_confirmed',
   'observed_frame_sha256':observation.screenshot['sha256'],'observed_frame_id_sha256':_digest(observation.frame_id.encode()),
   'action_sha256':_digest(_canonical(self._parsed_action)),'action_type':self._parsed_action['type'],'action_has_target':'target' in self._parsed_action,'observed_url':self.latest_url,'physical_url':self.page.url,
   'observed_control_refs':sorted(known_refs),'observed_native_context':self._observed_context,'native_context':context,'native_target_contexts':self._pending_targets,'observed_material':observed,'sampled_frames':records}
  if stage=='parse':self._parse_guard=guard
  else:self._dispatch_guard=guard
  return True

 def parse_current_action(self,raw):
  self._within_budget();observation=self.latest
  if observation is None:raise ContractError('stale_frame')
  action=validate_action(raw,observation,current_frame_id=observation.frame_id) if type(raw) is dict else normalize_model_action(raw,observation,current_frame_id=observation.frame_id)
  derived=self._context_for_action(action)
  if derived is None:raise ContractError('stale_frame')
  self._parsed_action=action;self._pending_context,self._pending_targets=derived;self._parse_guard=None
  if not self._frame_current(observation,stage='parse'):
   self._parsed_action=None;self._pending_context=None;raise ContractError('stale_frame')
  return action

 def dispatch(self,raw_action,**kwargs):
  if kwargs:raise ContractError('invalid_action')
  observation=self.latest
  if observation is None or self._parsed_action is None or self._parse_guard is None:raise ContractError('stale_frame')
  action=validate_action(raw_action,observation,current_frame_id=observation.frame_id)
  if action!=self._parsed_action:raise ContractError('stale_frame')
  parse=self._parse_guard;self._dispatch_guard=None
  try:
   # Reuse only v0.6.6 action mechanics, not any TRAIN constructor or router.
   applied=OdooV066TrainAdapter.dispatch(self,action)
   if self._dispatch_guard is None:raise ContractError('stale_frame')
   applied['public_contract_receipt'].update(native_material_parse_guard=parse,native_material_dispatch_guard=self._dispatch_guard,native_adapter_profile=PROFILE)
   return applied
  finally:
   self._parsed_action=None;self._pending_context=None;self._parse_guard=None;self._dispatch_guard=None


def audit_guard(guard,observed_png,read_ref,action=None):
 """Re-derive every raw-sample membership/material claim from retained bytes."""
 if guard.get('profile')!=PROFILE or guard.get('stage') not in ('parse','dispatch') or guard.get('observed_frame_sha256')!=_digest(observed_png) or guard.get('observed_url')!=guard.get('physical_url'):
  raise ValueError('Native material guard observation/profile binding changed')
 context=guard.get('native_context');base=guard.get('observed_native_context')
 if not valid_context(context) or not valid_context(base) or {**context,'target':None,'row':None}!=base:
  raise ValueError('Native material guard form/focus/target identity changed')
 targets=guard.get('native_target_contexts')
 if type(targets) is not list:raise ValueError('Native target hit-test records missing')
 for target in targets:
  c=target.get('context');point=target.get('point')
  if not valid_context(c) or {**c,'target':None,'row':None}!=base or c['target'] is None or c['target']['disabled'] or type(point) is not dict or set(point)!={'x','y'} or any(type(v) is not int for v in point.values()):raise ValueError('Native target context changed')
  b=c['target']['bounds']
  if not (b[0]<=point['x']<=b[2] and b[1]<=point['y']<=b[3]) or near_border(point,c['native_geometry']):raise ValueError('Native target bounds or protected border hit changed')
 if (targets and context!=targets[0]['context']) or (not targets and context!=base):raise ValueError('Native target chain changed')
 if type(action) is not dict or type(action.get('frame_id')) is not str or guard.get('observed_frame_id_sha256')!=_digest(action['frame_id'].encode()) or guard.get('action_sha256')!=_digest(_canonical(action)) or action.get('type')!=guard.get('action_type') or ('target' in action)!=guard.get('action_has_target'):raise ValueError('Native exact normalized action required for guard audit')
 slots=[('target',action['target'])] if 'target' in action else [('from',action['from']),('to',action['to'])] if action['type']=='drag' else []
 if [r.get('slot') for r in targets]!=[slot for slot,_point in slots]:raise ValueError('Native action target slot/count changed')
 for saved,(_slot,endpoint) in zip(targets,slots):
  point=saved['point'];target=saved['context']['target']
  if set(endpoint)=={'x','y'}:
   if point!=endpoint:raise ValueError('Native action coordinate changed')
  elif set(endpoint)=={'ref'}:
   bounds=target['bounds']
   if endpoint['ref']!=target['ref'] or point!={'x':int((bounds[0]+bounds[2])/2),'y':int((bounds[1]+bounds[3])/2)}:raise ValueError('Native action reference or center changed')
  else:raise ValueError('Native action target shape changed')
 known=guard.get('observed_control_refs')
 if type(known) is not list or any(type(ref) is not str for ref in known):raise ValueError('Native observed control refs missing')
 eligible=material_eligible(context,action) and all(row['context']['target']['ref'] in known for row in targets)
 observed=border_material(observed_png,context['native_geometry']) if eligible else None
 mode='finite_rfq_material' if observed is not None else 'exact_full_png'
 classification='two_final_material_frames_confirmed' if observed is not None else 'two_final_exact_frames_confirmed'
 if guard.get('classification')!=classification or urlsplit(guard['observed_url']).path!=context['route_path'] or guard.get('mode')!=mode or guard.get('observed_material')!=observed:raise ValueError('Native guard material mode changed')
 rows=guard.get('sampled_frames')
 if type(rows) is not list or len(rows)!=3:raise ValueError('Three independently retained native frame samples required')
 for i,row in enumerate(rows):
  raw=read_ref(row['sampled_frame_ref']);material=border_material(raw,context['native_geometry']) if observed is not None else None
  if row.get('sample_native_context')!=base or row.get('step')!=action.get('step') or row.get('observed_frame_sha256')!=guard['observed_frame_sha256'] or row.get('observed_frame_id_sha256')!=guard['observed_frame_id_sha256'] or row.get('sample')!=i or row.get('stage')!=guard['stage'] or row.get('raw_frame_sha256')!=_digest(raw) or row.get('material')!=material or row['sampled_frame_ref'].get('sha256')!=_digest(raw):raise ValueError('Native raw PNG/frame claim changed')
  if (observed is None and raw!=observed_png) or (observed is not None and (material is None or material['canonical_material_sha256']!=observed['canonical_material_sha256'])):raise ValueError('Native raw pixels do not satisfy protected material equality')
 return {'profile':PROFILE,'mode':mode,'raw_guard_pngs_reopened':3,'native_targets_reopened':len(targets),'material_equality_verified':True}


def public_binding():
 root=Path(__file__).resolve().parents[2]
 names=['enterprise_fallback/odoo18/odoo_v066_native_material_adapter_v2.py','enterprise_fallback/odoo18/odoo_native_adapter.py',
  'enterprise_fallback/odoo18/odoo_v066_train_adapter.py','enterprise_fallback/odoo18/odoo_native_geometry_material_v2.py',
  'src/cursibench/scale_action_contract.py','src/cursibench/scale_action_contract_v066.py','src/cursibench/scale_action_output_v066.py',
  'src/cursibench/scale_action_output_v065.py','src/cursibench/scale_action_output_v062.py']
 bindings={name:_digest((root/name).read_bytes()) for name in names}
 return {'schema':'envloop-odoo-native-material-common-binding-v2','profile':PROFILE,'student_model':native.MODEL,
  'viewport':VIEWPORT,'max_actions':native.MAX_ACTIONS,'wall_seconds':native.WALL_SECONDS,'finite_border_pixels':9,'geometry_source':'current_visible_native_dom','native_device_pixel_ratio':1,
  'gold_directed_adapter_arguments':False,'bindings_sha256':bindings,'binding_sha256':_digest(_canonical(bindings))}

__all__=['OdooV066NativeMaterialAdapter','PROFILE','VIEWPORT','public_binding','audit_guard','valid_context','NATIVE_CONTEXT_JS']
