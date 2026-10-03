"""Uniform original reader plus scoped source-proved Writer pointer eligibility."""
import hashlib,time
from pathlib import Path
from types import FunctionType
if __package__:
 from . import native_editor_reader_v47 as old
 from . import native_writer_pointer_capability_v49 as writer
else:
 import native_editor_reader_v47 as old
 import native_writer_pointer_capability_v49 as writer
SCHEMA='cua-native-writer-pointer-probe-v49'
BASE_SHA='71803858bfa9bfa24a55301d77c628205f75da600ef179a9a4594b3a680efe9e'
if hashlib.sha256(Path(old.__file__).read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('Frozen V47 reader changed')

def compatible_record(reader,Atspi,node,window,*,pid,uid,viewport,ancestry):
 record,fact=old.original.compatible_record(reader,Atspi,node,window,pid=pid,uid=uid,viewport=viewport,ancestry=ancestry)
 flags=fact.get('native_flags',{});source=getattr(reader,'_v42_evidence',{})
 if record['enabled'] or fact.get('role')!='paragraph' or flags.get('SENSITIVE') is not False or source.get('unavailable'):return record,fact
 # Original forward ownership and strict physical leaf proof remain required.
 if fact.get('point_hit_ownership_checked') is not True or record['obscured'] or node.get_child_count()!=0:return record,fact
 chain=ancestry(node,window);states=[(parent.get_role_name(),reader.state_flags(Atspi,parent)) for parent in chain]
 try:
  if not str(source.filename).endswith('.docx') or 'libreoffice-writer' not in source.x11['wm_class']:raise ValueError('Current document is not original Writer')
  source.refresh()
  proof=writer.writer_capability(build=source['build'],role='paragraph',raw_flags=flags,ancestors=states,mode=source['mode'],
   context={'document_binding_sha256':source['binding'],'owned_current_principal':pid==source['native_pid'] and uid==source['native_uid'],
    'same_current_writer_document':True,'strict_zero_child_leaf':True,'original_strict_point_hit_proved':True,'unobscured':True,
    'original_file_writable':source['medium']['original_file_writable'],'original_medium_writable':source['medium']['original_medium_writable']},now=time.monotonic())
 except (AttributeError,KeyError,ValueError) as error:return record,{**fact,'writer_pointer_capability_refusal':{'error_class':type(error).__name__,'error':str(error)}}
 return {**record,'enabled':True,'keyboard':proof['effective_keyboard_eligible']},{**fact,'writer_pointer_capability_evidence':proof,'native_flags':flags}

def scoped_reader():
 fn=old.original.scoped_reader
 namespace={**fn.__globals__,'__file__':__file__,'SCHEMA':SCHEMA,'current_evidence':old.current_evidence,'compatible_record':compatible_record}
 return FunctionType(fn.__code__,namespace,fn.__name__,fn.__defaults__,fn.__closure__)()

if __name__=='__main__':scoped_reader()[1]()
