"""Known Writer state omission; pointer activation never fabricates focus."""
from copy import deepcopy
if __package__:
 from . import native_editor_capability_v42 as base
else:
 import native_editor_capability_v42 as base

def writer_capability(*,build,role,raw_flags,ancestors,mode,context,now):
 if build!=base.BUILD or role!='paragraph':raise ValueError('Unsupported exact Writer build/role')
 if type(raw_flags) is not dict or any(type(raw_flags.get(k)) is not bool for k in base.FLAGS):raise ValueError('Raw paragraph flags unknown')
 if raw_flags['SENSITIVE'] is not False or not all(raw_flags[k] for k in ('ENABLED','EDITABLE','VISIBLE','SHOWING')) or raw_flags['STALE'] or raw_flags['DEFUNCT']:raise ValueError('Protected/disabled/stale paragraph')
 required=('owned_current_principal','same_current_writer_document','strict_zero_child_leaf','original_strict_point_hit_proved','unobscured','original_file_writable','original_medium_writable')
 if not all(context.get(k) is True for k in required):raise ValueError('Current owned writable Writer leaf proof missing')
 if sum(r=='document text' for r,f in ancestors)!=1:raise ValueError('Original Writer document ancestor missing/ambiguous')
 for role,flags in ancestors:
  if not all(flags.get(k) is True for k in ('ENABLED','VISIBLE','SHOWING')) or flags.get('STALE') is not False or flags.get('DEFUNCT') is not False:raise ValueError('Current Writer ancestor unsafe')
  if flags.get('SENSITIVE') is False:
   if role not in ('paragraph','document text') or flags.get('EDITABLE') is not True:raise ValueError('Unsupported insensitive/protected ancestor')
  elif flags.get('SENSITIVE') is not True:raise ValueError('Ancestor sensitivity unknown')
 proof=base.checked_edit_mode(mode,document_binding_sha256=context['document_binding_sha256'],now=now)
 return {'schema':'owned-writer-pointer-state-capability-v49','capability':'source_proved_Writer_sensitive_state_omission','effective_pointer_eligible':True,
  'effective_keyboard_eligible':raw_flags['FOCUSED'],'raw_native_flags':deepcopy(raw_flags),'raw_native_flags_preserved':True,'raw_sensitive_value':False,
  'native_focused_override':False,'actual_focus_required_by_unchanged_keyboard_guard':True,
  'actual_lease_required_by_unchanged_native_dispatch_guard':True,'current_edit_mode_evidence':proof}
