"""Bounded visible Writer children; other managed descendants remain deferred."""
import time
if __package__:
 from . import native_current_inventory as inventory
 from . import native_editor_capability_v42 as capability
else:
 import native_current_inventory as inventory
 import native_editor_capability_v42 as capability

def current_document_count(reader,Atspi,node,window,*,pid,uid,ancestry,role,flags):
 if role!='document text' or flags['MANAGES_DESCENDANTS'] is not True:return None
 if not all(flags.get(k) is True for k in ('ENABLED','EDITABLE','VISIBLE','SHOWING')) or flags.get('STALE') is not False or flags.get('DEFUNCT') is not False:return None
 source=getattr(reader,'_v42_evidence',{})
 try:
  if source.get('unavailable') or source['build']!=capability.BUILD or not source.filename.endswith('.docx') or 'libreoffice-writer' not in source.x11['wm_class']:return None
  if pid!=source['native_pid'] or uid!=source['native_uid'] or node.get_process_id()!=pid:return None
  chain=ancestry(node,window)
  if not all(n.get_process_id()==pid for n in chain):return None
  for parent in chain:
   state=reader.state_flags(Atspi,parent);name=parent.get_role_name()
   if not all(state[k] for k in ('ENABLED','VISIBLE','SHOWING')) or state['STALE'] or state['DEFUNCT']:return None
   if not state['SENSITIVE'] and name!='document text':return None
  if not flags['EDITABLE']:return None
  source.refresh()
  if source['medium']['original_medium_writable'] is not True or source['medium']['original_file_writable'] is not True:return None
  capability.checked_edit_mode(source['mode'],document_binding_sha256=source['binding'],now=time.monotonic())
  count=node.get_child_count()
  if type(count) is not int or not 0<=count<=64:return None
  return count
 except (AttributeError,KeyError,ValueError):return None

def breadth_first_source(function):
 source=inventory.breadth_first_source(function)
 old="  if flags['MANAGES_DESCENDANTS']:\n   row['deferred']=True;row['reason']='native_manages_descendants';return\n  count=node.get_child_count();require(type(count) is int and count>=0,'Native child count invalid');row['child_count']=count"
 new="  writer_count=writer_document_count(Atspi,node,window,pid,uid,ancestry,role,flags) if flags['MANAGES_DESCENDANTS'] else None\n  if flags['MANAGES_DESCENDANTS'] and writer_count is None:\n   row['deferred']=True;row['reason']='native_manages_descendants';return\n  count=writer_count if writer_count is not None else node.get_child_count();require(type(count) is int and count>=0,'Native child count invalid');row['child_count']=count"
 if source.count(old)!=1:raise ValueError('Frozen managed-descendant branch changed')
 source=source.replace(old,new)
 old="   pending.append((node.get_child_at_index(index),depth+1))"
 new="   child=node.get_child_at_index(index)\n   if writer_count is not None:\n    if child.get_process_id()!=pid:raise ValueError('Current Writer child foreign process')\n    ancestry(child,window)\n    child_flags=state_flags(Atspi,child)\n    if child.get_role_name()!='paragraph' or not child_flags['VISIBLE'] or not child_flags['SHOWING'] or child_flags['STALE'] or child_flags['DEFUNCT'] or geometry(Atspi,child,viewport) is None:continue\n    require(child.get_child_count()==0,'Writer paragraph no longer strict zero-child leaf')\n    pending.insert(index,(child,depth+1))\n   else:pending.append((child,depth+1))"
 if source.count(old)!=1:raise ValueError('Frozen bounded BFS frontier changed')
 return source.replace(old,new)
