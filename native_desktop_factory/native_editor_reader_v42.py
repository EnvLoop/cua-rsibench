"""Source-bound Calc capability with preserved native flags and guard rules."""
import hashlib,inspect,json,time
from pathlib import Path
from types import FunctionType
if __package__:
 from . import native_window_current_reader as base
 from . import native_editor_evidence_v42 as evidence
 from . import native_editor_capability_v42 as capability
else:
 import native_window_current_reader as base
 import native_editor_evidence_v42 as evidence
 import native_editor_capability_v42 as capability

BASE_SHA='b43e00e117115a895cba20c923708e84238f5d05986154519a2665301503850d'
SCHEMA='cua-native-editor-capability-probe-v42'
if hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('Frozen V41 reader changed')

def current_evidence(reader,filename):
 try:reader._v42_evidence=evidence.evidence(filename)
 except Exception as error:reader._v42_evidence={'unavailable':True,'error_class':type(error).__name__,'error':str(error)}
 return reader._v42_evidence

def compatible_record(reader,Atspi,node,window,*,pid,uid,viewport,ancestry):
 record,fact=base.editable_record(reader,Atspi,node,window,pid=pid,uid=uid,viewport=viewport,ancestry=ancestry)
 flags=reader.state_flags(Atspi,node);role=node.get_role_name();source=getattr(reader,'_v42_evidence',{})
 if record['enabled'] or role not in capability.ROLES or flags['SENSITIVE'] or source.get('unavailable'):return record,fact
 chain=ancestry(node,window);editor=None;chain_flags=[]
 for parent in chain:
  f=reader.state_flags(Atspi,parent);r=parent.get_role_name();chain_flags.append((r,f))
  if r=='table' and f['FOCUSED'] and f['EDITABLE']:editor=f
 if editor is None or fact.get('point_hit_ownership_checked') is not True:return record,fact
 if any(not f['ENABLED'] or not f['VISIBLE'] or not f['SHOWING'] or f['STALE'] or f['DEFUNCT'] or
  not f['SENSITIVE'] and r not in capability.ROLES for r,f in chain_flags):return record,fact
 try:
  proof=capability.editor_capability(build=source['build'],role=role,raw_flags=flags,
   editor={k.lower():editor[k] for k in ('ENABLED','EDITABLE','FOCUSED','VISIBLE','SHOWING','STALE','DEFUNCT')},
   edit_mode=source['mode'],context={'document_binding_sha256':source['binding'],'owned_current_principal':pid==source['native_pid'] and uid==source['native_uid'],
    'lease_active':True,'strict_current_leaf_hit_proved':True,'same_current_editor':True,
    'original_file_writable':source['medium']['original_file_writable'],'original_medium_writable':source['medium']['original_medium_writable']},now=time.monotonic())
 except (KeyError,ValueError):return record,fact
 # enabled is an eligibility projection; raw states remain verbatim in facts.
 record={**record,'enabled':True,'keyboard':flags['EDITABLE']}
 return record,{**fact,'sensitivity_capability_evidence':proof,'native_flags':flags}

def scoped_reader():
 def install(reader,state):
  result=base.install_coordinate_scope(reader,state)
  result._current_editor_evidence_loader=lambda filename:current_evidence(result,filename)
  return result
 def finalise(text):
  text=base.finalise_source(text)
  old="  state['resolver']=RecordedPaths(wrapped.value,x11['pid'],identity)"
  if text.count(old)!=1:raise ValueError('Owned editor evidence hook changed')
  return text.replace(old,old+"\n  state['editor_evidence']=reader._current_editor_evidence_loader(name)").replace("'native_coordinate_projection':state['projection'],","'native_coordinate_projection':state['projection'],\n  'current_application_editor_evidence':state['editor_evidence'],")
 original=base.scoped_reader
 ns={**vars(base),'__file__':__file__,'SCHEMA':SCHEMA,'install_coordinate_scope':install,
  'editable_record':compatible_record,'finalise_source':finalise}
 return FunctionType(original.__code__,ns,original.__name__,original.__defaults__,original.__closure__)()

if __name__=='__main__':scoped_reader()[1]()
