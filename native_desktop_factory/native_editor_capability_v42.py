"""Explicit LibreOffice GTK capability evidence; raw states stay unchanged."""
from copy import deepcopy
import re

SCHEMA='owned-native-editor-capability-v42'
BUILD={
 'libreoffice_version':'1:7.3.7-0ubuntu0.22.04.11',
 'gtk_version':'3.24.33-1ubuntu2.2',
 'atspi_version':'2.44.0-3',
 'atk_version':'2.36.0-3build1',
 'atk_bridge_version':'2.38.0-3',
 'gtk_plugin_sha256':'6c86e9d5c6cbcde4f6556f4c646ebf196e9cf3407758918afa8f8ea33bf6f823',
 'executable_sha256':'65bab645455ca7fe2f38e61f5d36b84dc02c229594d6c0598b5078a819d4f43a',
}
ROLES=frozenset(('document spreadsheet','table','table cell'))
FLAGS=('VISIBLE','SHOWING','ENABLED','SENSITIVE','EDITABLE','FOCUSED','DEFUNCT','STALE')

def require(ok,message):
 if not ok:raise ValueError(message)

def checked_edit_mode(proof,*,document_binding_sha256,now):
 require(type(document_binding_sha256) is str and re.fullmatch(r'[0-9a-f]{64}',document_binding_sha256) is not None,'Current document binding missing')
 require(type(proof) is dict,'Current Edit Mode evidence missing')
 require(proof.get('schema')=='owned-current-edit-mode-evidence-v42','Edit Mode schema unsupported')
 require(proof.get('document_binding_sha256')==document_binding_sha256,'Edit Mode foreign document')
 require(type(now) in (int,float) and type(proof.get('observed_at')) in (int,float) and
  type(proof.get('expires_at')) in (int,float) and proof['observed_at']<=now<proof['expires_at'] and
  proof['expires_at']-proof['observed_at']<=10,'Edit Mode stale/uncertain clock')
 require(proof.get('visible_initial_native_proof') is True and proof.get('same_native_node_reopened') is True and
  proof.get('current_native_state_read') is True and proof.get('unique_current_command') is True,
  'Edit Mode current identity evidence missing/ambiguous')
 require(proof.get('command')=='.uno:EditDoc' and proof.get('name')=='Edit Mode' and proof.get('parent_menu')=='Edit',
  'Edit Mode command identity unsupported')
 require(proof.get('checked') is True and proof.get('enabled') is True and proof.get('sensitive') is True and
  proof.get('stale') is False and proof.get('defunct') is False,'Document UI read-only/disabled')
 require(type(proof.get('node_identity_sha256')) is str and re.fullmatch(r'[0-9a-f]{64}',proof['node_identity_sha256']) is not None,
  'Edit Mode native node identity missing')
 return deepcopy(proof)

def editor_capability(*,build,role,raw_flags,editor,edit_mode,context,now):
 require(build==BUILD,'Unsupported native application build')
 require(role in ROLES,'Unsupported sensitivity capability role')
 require(type(raw_flags) is dict and all(type(raw_flags.get(key)) is bool for key in FLAGS),'Native flags missing/unknown')
 require(raw_flags['SENSITIVE'] is False,'Sensitivity capability is only for preserved false native state')
 require(raw_flags['ENABLED'] and raw_flags['EDITABLE'] and raw_flags['VISIBLE'] and raw_flags['SHOWING'] and
  not raw_flags['STALE'] and not raw_flags['DEFUNCT'],'Disabled/protected/stale native editor node')
 require(type(context) is dict and context.get('owned_current_principal') is True and context.get('lease_active') is True and
  context.get('strict_current_leaf_hit_proved') is True and context.get('same_current_editor') is True,
  'Native current ownership/leaf/editor evidence missing')
 require(context.get('original_file_writable') is True and context.get('original_medium_writable') is True,
  'Original document medium/file read-only or unknown')
 require(type(editor) is dict and all(editor.get(key) is True for key in ('enabled','editable','focused','visible','showing')) and
  editor.get('stale') is False and editor.get('defunct') is False,'Actual current focused editable editor missing')
 proof=checked_edit_mode(edit_mode,document_binding_sha256=context.get('document_binding_sha256'),now=now)
 return {'schema':SCHEMA,'capability':'source_proved_calc_gtk_sensitive_state_omission',
  'raw_native_flags':deepcopy(raw_flags),'raw_sensitive_value':False,'raw_native_flags_preserved':True,'effective_input_eligible':True,
  'build':deepcopy(build),'role':role,'edit_mode_evidence':proof,
  'original_native_sensitive_asserted_true':False,'native_policy_override_for_unsupported_nodes':False}
