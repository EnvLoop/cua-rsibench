"""Supported Impress slide-selector clicks; raw state and keyboard rules remain."""
from copy import deepcopy
if __package__:
 from . import native_editor_capability_v42 as base
else:
 import native_editor_capability_v42 as base

def selector_capability(*,build,raw_flags,ancestors,selector,mode,context,now):
 if build!=base.BUILD:raise ValueError('Unsupported exact Impress build')
 if type(raw_flags) is not dict or any(type(raw_flags.get(k)) is not bool for k in base.FLAGS):raise ValueError('Slide shape raw flags unknown')
 if not all(raw_flags[k] for k in ('ENABLED','SENSITIVE','VISIBLE','SHOWING')) or raw_flags['STALE'] or raw_flags['DEFUNCT'] or raw_flags['EDITABLE']:raise ValueError('Disabled/protected/stale or editable slide selector')
 required=('owned_current_principal','same_current_impress_document','strict_zero_child_shape','strict_physical_leaf_identity_proved','unobscured','original_file_writable','original_medium_writable','current_application_is_writable','current_selection_interface_read')
 if not all(context.get(k) is True for k in required):raise ValueError('Current owned writable slide-selector proof missing')
 if selector.get('name')!='Slides View' or selector.get('description')!='This is where you sort slides.' or selector.get('role')!='document frame' or selector.get('selection_interface_available') is not True:raise ValueError('Exact administrative Slides View scope missing')
 if type(selector.get('child_count')) is not int or not 0<selector['child_count']<=64:raise ValueError('Slide-selector child bound')
 if not all(selector.get(k) is True for k in ('ACTIVE','SELECTABLE','FOCUSABLE','MULTISELECTABLE')):raise ValueError('Current Slides View native contract missing')
 if not all(context.get(k) is True for k in ('shape_active','shape_selectable','shape_focusable')):raise ValueError('Current shape native contract missing')
 if len(ancestors)<2 or ancestors[0][0]!='panel' or ancestors[1][0]!='document frame' or sum(role=='document frame' for role,flags in ancestors)!=1:raise ValueError('Slide-selector direct original document ancestry missing')
 for index,(role,flags) in enumerate(ancestors):
  if not all(flags.get(k) is True for k in ('ENABLED','VISIBLE','SHOWING')) or flags.get('STALE') is not False or flags.get('DEFUNCT') is not False:raise ValueError('Current selector ancestor unsafe')
  if index==1:
   if flags.get('SENSITIVE') is not False or flags.get('EDITABLE') is not False:raise ValueError('Unsupported document state omission')
  elif flags.get('SENSITIVE') is not True:raise ValueError('Other ancestor sensitivity unsafe')
 proof=base.checked_edit_mode(mode,document_binding_sha256=context.get('document_binding_sha256'),now=now)
 return {'schema':'owned-Impress-slide-selector-capability-v51','capability':'source_proved_SlideSorter_shape_and_document_state_contract',
  'allowed_actions':['click'],'effective_pointer_eligible':True,'effective_keyboard_eligible':False,
  'raw_native_flags':deepcopy(raw_flags),'raw_native_flags_preserved':True,'raw_document_sensitive_value':False,
  'native_focused_override':False,'original_keyboard_guard_unchanged':True,
  'actual_lease_required_by_unchanged_dispatch_guard':True,'current_edit_mode_evidence':proof,
  'administrative_selector':deepcopy(selector)}

def actionable_metadata(metadata):
 """Represent exact denials in valid wire form; all raw facts remain verbatim."""
 explicit={}
 for item in metadata.get('requested_point_facts',[]):
  target=item.get('actual_hit',{});fact=item.get('native_fact',{})
  if target.get('actions')==[] and target.get('enabled') is False and target.get('keyboard') is False and target.get('obscured') is True and fact.get('structural_inventory_only') is True and fact.get('native_actions_authorized') is False:
   explicit[target.get('ref')]=target
 targets=[];normalised=[]
 for target in metadata['targets']:
  if target.get('actions')==[]:
   if explicit.get(target.get('ref'))!=target:raise ValueError('Unknown malformed empty-action target')
   targets.append({**target,'actions':['click']});normalised.append(target['ref']);continue
  targets.append(target)
 return {**metadata,'targets':targets,'explicit_structural_denial_schema_projection_refs':normalised,
  'disabled_denial_bounds_and_flags_preserved':True,'denial_facts_preserved':True}
