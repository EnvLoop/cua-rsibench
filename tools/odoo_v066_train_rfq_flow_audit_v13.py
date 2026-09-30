"""Independently reopen complete RFQ flow guards using the retained v12 RGB reader."""
from __future__ import annotations
from urllib.parse import urlsplit
from tools import audit_odoo_v066_train_attachment_calibration_v10 as prior
from tools import odoo_v066_scale_protocol_v1 as protocol
from tools.odoo_v066_train_border_material_audit_v12 import independent_material

PROFILE='train-calibrated-finite-border-rfq-edit-flow-2026-09-30-v13'


def flow_guard(out,action,intent,result,case,wrong,baseline,samples):
 receipt=action['contract_receipt'];parse=receipt.get('rfq_flow_parse_guard');dispatch=receipt.get('rfq_flow_dispatch_guard')
 if parse is None and dispatch is None:return set(),0
 normalized=intent['normalized_action'];raw=(__import__('json').dumps(normalized,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode()
 prior.require(type(parse) is type(dispatch) is dict and normalized['type'] in ('key','type','click','wait') and
               action.get('route_kind')=='generic_rfq' and receipt==result['contract_receipt'],
               'v13_flow_route_or_original_receipt_invalid')
 context=parse.get('context');observed_context=parse.get('observed_context')
 relevant=case if action['phase']=='positive' else wrong
 orders=[r for r in baseline['orders'] if r.get('name')==relevant['id']]
 prior.require(len(orders)==1 and type(context) is dict and context==dispatch.get('context') and
               type(observed_context) is dict and observed_context==dispatch.get('observed_context') and
               {**context,'target':None}==observed_context and context.get('rfq_id')==relevant['id'] and
               context.get('route_path')==f"/odoo/purchase/{orders[0]['id']}" and
               context.get('modal_absent') is context.get('viewer_absent') is True and
               (context.get('focus_in_form') is True or context.get('focus_is_body') is True) and
               type(context.get('focus')) is dict and context['focus'].get('disabled') is False,
               'v13_observed_focus_or_rfq_context_invalid')
 if normalized['type']=='type' and 'target' not in normalized:
  prior.require(context['focus'].get('tag') in ('input','textarea') and context['focus'].get('readonly') is False and
                context.get('focus_in_form') is True,'v13_focused_insertion_identity_invalid')
 if normalized['type']=='key' and normalized.get('key') in ('Control+A','Meta+A'):
  prior.require(context['focus'].get('tag') in ('input','textarea') and context['focus'].get('readonly') is False and
                context.get('focus_in_form') is True,'v13_select_all_not_focused_editable')
 if normalized.get('target'):
  target=normalized['target'];control=context.get('target');bounds=None if control is None else control.get('bounds')
  prior.require(type(bounds) is list and len(bounds)==4 and bounds[0]<=target['x']<=bounds[2] and bounds[1]<=target['y']<=bounds[3] and
                len([c for c in intent.get('observation_controls',[]) if c.get('ref')==control.get('ref') and c.get('visible') and c.get('enabled')])==1,
                'v13_visible_target_bounds_or_control_binding_invalid')
 observed=prior._ref(out,action['frame'],image=True)[1];material=independent_material(observed);refs=set()
 frame_id=protocol.digest(intent['frame_id'].encode())
 for item,stage in ((parse,'parse'),(dispatch,'dispatch')):
  prior.require(item.get('profile')==PROFILE and item.get('stage')==stage and
                item.get('classification')=='two_final_material_frames_confirmed' and
                item.get('observed_frame_sha256')==action['frame']['sha256'] and item.get('observed_frame_id_sha256')==frame_id and
                item.get('action_sha256')==protocol.digest(raw) and item.get('observed_material')==material and
                item.get('canonical_material_sha256')==material['canonical_material_sha256'] and
                item.get('observed_url')==item.get('physical_url')==intent['observed_url'] and
                urlsplit(intent['observed_url']).path==context['route_path'],
                'v13_flow_frame_action_or_material_binding_invalid')
  records=item.get('sampled_material_frames');phase=[s for s in samples if s.get('step')==action['step'] and s.get('stage')==stage+'_rfq_flow_material']
  prior.require(type(records) is list and len(records)==len(phase)==3 and [s.get('sample') for s in phase]==[0,1,2],
                'v13_all_three_flow_samples_required')
  for record,sample in zip(records,phase):
   path,raw_png=prior._ref(out,record['frame_ref'],image=True);refs.add(str(path));actual=independent_material(raw_png)
   prior.require(record.get('raw_frame_sha256')==protocol.digest(raw_png) and record.get('material')==actual and
                 actual['canonical_material_sha256']==material['canonical_material_sha256'] and
                 sample.get('sampled_frame_ref')==record['frame_ref'] and sample.get('classification')=='material_confirmed' and
                 sample.get('canonical_material_sha256')==actual['canonical_material_sha256'] and
                 sample.get('border_state_class')==actual['state_class'],
                 'v13_flow_body_pixel_or_raw_state_forgery')
 return refs,1
