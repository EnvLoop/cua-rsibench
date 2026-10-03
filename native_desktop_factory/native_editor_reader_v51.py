"""Uniform supported slide-selector eligibility and safe denial serialization."""
import hashlib,time,warnings
from pathlib import Path
from types import FunctionType
if __package__:
 from . import native_editor_reader_v50 as previous
 from . import native_impress_selector_capability_v51 as capability
 from .native_hit_identity_diagnostic_v33 import identity
else:
 import native_editor_reader_v50 as previous
 import native_impress_selector_capability_v51 as capability
 from native_hit_identity_diagnostic_v33 import identity
SCHEMA='cua-native-Impress-selector-probe-v51'
BASE_SHA='f59805ffd2c1e0f7c6376a275a318fcc6f5a7f2805d7a17bda1f84f9588b5782'
if hashlib.sha256(Path(previous.__file__).read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('Frozen V50 reader changed')

def compatible_record(reader,Atspi,node,window,*,pid,uid,viewport,ancestry):
 record,fact=previous.previous.compatible_record(reader,Atspi,node,window,pid=pid,uid=uid,viewport=viewport,ancestry=ancestry)
 flags=fact.get('native_flags',{});source=getattr(reader,'_v42_evidence',{})
 if record['enabled'] or fact.get('role')!='panel' or flags.get('EDITABLE') is not False or source.get('unavailable'):return record,fact
 try:
  if not str(source.filename).endswith('.pptx') or 'libreoffice-impress' not in source.x11['wm_class']:return record,fact
  chain=ancestry(node,window)
  if len(chain)<2 or chain[1].get_role_name()!='document frame' or node.get_child_count()!=0:return record,fact
  document=chain[1];name=document.get_name();description=document.get_description()
  if name!='Slides View' or description!='This is where you sort slides.':return record,fact
  source.refresh();states=[(parent.get_role_name(),reader.state_flags(Atspi,parent)) for parent in chain]
  count=document.get_child_count()
  with warnings.catch_warnings(record=True) as captured:
   warnings.simplefilter('always')
   selection=document.get_selection_iface()
  getter_warnings=[]
  for warning in captured:
   if warning.category is not DeprecationWarning or str(warning.message)!='Atspi.Accessible.get_selection_iface is deprecated':raise ValueError('Unexpected selection getter warning')
   getter_warnings.append({'category':'DeprecationWarning','message':str(warning.message),'getter':'get_selection_iface'})
  node_state=node.get_state_set();document_state=document.get_state_set()
  box=reader.geometry(Atspi,node,viewport)
  if box is None:raise ValueError('Slide-selector geometry unavailable')
  hit,depth=reader.physical_hit(Atspi,window,[box[0]+box[2]//2,box[1]+box[3]//2],pid=pid,viewport=viewport,ancestry=ancestry)
  node_id=identity(node);hit_id=identity(hit);document_id=identity(document)
  if not node_id.get('available') or not document_id.get('available') or node_id!=hit_id or hit.get_child_count()!=0:raise ValueError('Current slide-selector physical identity differs')
  selector={'name':name,'description':description,'role':'document frame','identity':document_id,'child_count':count,'selection_interface_available':selection is not None,'supported_getter_warnings':getter_warnings,
   **{key:bool(document_state.contains(getattr(Atspi.StateType,key))) for key in ('ACTIVE','SELECTABLE','FOCUSABLE','MULTISELECTABLE')}}
  proof=capability.selector_capability(build=source['build'],raw_flags=flags,ancestors=states,selector=selector,mode=source['mode'],
   context={'document_binding_sha256':source['binding'],'owned_current_principal':pid==source['native_pid'] and uid==source['native_uid'],
    'same_current_impress_document':True,'strict_zero_child_shape':True,'strict_physical_leaf_identity_proved':True,'unobscured':True,
    'original_file_writable':source['medium']['original_file_writable'],'original_medium_writable':source['medium']['original_medium_writable'],'current_application_is_writable':source['medium'].get('application_is_readonly') is False,
    'current_selection_interface_read':selection is not None,**{'shape_'+key.lower():bool(node_state.contains(getattr(Atspi.StateType,key))) for key in ('ACTIVE','SELECTABLE','FOCUSABLE')}},now=time.monotonic())
 except (AttributeError,KeyError,ValueError) as error:return record,{**fact,'Impress_selector_capability_refusal':{'error_class':type(error).__name__,'error':str(error)}}
 return {**record,'enabled':True,'obscured':False,'keyboard':False,'actions':['click']},{**fact,'Impress_selector_capability_evidence':proof,'native_flags':flags,'point_hit_ownership_checked':True,'native_actions_authorized':True,'strict_physical_leaf_identity':node_id,'physical_hit_depth':depth}

def scoped_reader():
 fn=previous.previous.old.original.scoped_reader
 namespace={**fn.__globals__,'__file__':__file__,'SCHEMA':SCHEMA,'base':previous.scoped_base,'current_evidence':previous.previous.old.current_evidence,'compatible_record':compatible_record}
 run,main=FunctionType(fn.__code__,namespace,fn.__name__,fn.__defaults__,fn.__closure__)()
 def guarded_run(**kwargs):return capability.actionable_metadata(run(**kwargs))
 main.__globals__['guarded_run']=guarded_run
 return guarded_run,main
if __name__=='__main__':scoped_reader()[1]()
