"""Fresh owned-application cache and bounded breadth-first native inventory.

Frozen V38 remains unchanged. Every action still uses its strict physical hit
and ancestor-state rules; no target is injected into an old observation.
"""
from __future__ import annotations
import hashlib,importlib.util,inspect,json,textwrap
from pathlib import Path
from types import FunctionType

V38_SHA='38261c7c31e6a647ef3e3397b9a7b04ca2679dc5c19545e4c0138ea91d16abf9'
SCHEMA='cua-native-current-inventory-probe-v39'

def load_base():
 path=Path(__file__).with_name('native_terminal_hit_diagnostic_v38.py')
 if hashlib.sha256(path.read_bytes()).hexdigest()!=V38_SHA:raise ValueError('Frozen V38 reader source changed')
 spec=importlib.util.spec_from_file_location('envloop_current_inventory_v39_base',path);base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base);return base

def cache_owned_application(reader,Atspi,window,*,pid,identity):
 app=window.get_application();app_id=identity(app);window_id=identity(window)
 reader.require(window.get_process_id()==pid and app is not None and app.get_process_id()==pid,'Native cache application process differs')
 reader.require(app_id.get('available') is True and window_id.get('available') is True and
  app_id.get('bus_name_sha256')==window_id.get('bus_name_sha256'),'Native cache application bus differs')
 # GNOME documents Cache.NONE for missing toolkit events. Clearing affects
 # cached client data only; it performs no GUI focus, selection or input.
 app.set_cache_mask(Atspi.Cache.NONE);window.clear_cache()
 reader.require(window.get_state_set().contains(Atspi.StateType.ACTIVE),'Native owned window no longer active after cache clear')
 return {'application_identity_sha256':app_id['identity_sha256'],'window_identity_sha256':window_id['identity_sha256'],
  'same_native_process_and_bus_checked':True,'cache_mask':'NONE','window_client_cache_cleared':True,'native_mutations':0}

def breadth_first_source(function):
 source=textwrap.dedent(inspect.getsource(function))
 initial='targets=[];facts=[];branches=[];focused=[];seen=[]'
 children='  for index in range(count):walk(node.get_child_at_index(index),depth+1)'
 start=' walk(window,0)'
 for text in (initial,children,start):
  if source.count(text)!=1:raise ValueError('Pinned bounded inventory traversal source changed')
 source=source.replace(initial,initial+';pending=[]')
 source=source.replace(children,"  for index in range(count):\n   if len(seen)+len(pending)>=MAX_NODES:\n    row['deferred']=True;row['reason']='native_frontier_budget_cap';row['remaining_child_count']=count-index;break\n   pending.append((node.get_child_at_index(index),depth+1))")
 return source.replace(start,' pending.append((window,0))\n while pending:\n  node,depth=pending.pop(0);walk(node,depth)')

def scoped_reader():
 base=load_base();namespace={**vars(base),'__file__':__file__,'cache_owned_application':cache_owned_application,'breadth_first_source':breadth_first_source}
 source=textwrap.dedent(inspect.getsource(base.guarded_run))
 traversal='walk_source=textwrap.dedent(inspect.getsource(reader.previous.bounded_surface))'
 callback="  result=old.owned_window(owner,name);_,x11,wrapped=result\n  state['resolver']=RecordedPaths(wrapped.value,x11['pid'],identity)"
 for text in (traversal,callback,"'SCHEMA':'cua-native-visible-surface-probe-v38'"):
  if source.count(text)!=1:raise ValueError('Frozen guarded reader scope changed')
 source=source.replace(traversal,'walk_source=breadth_first_source(reader.previous.bounded_surface)')
 source=source.replace(callback,"  result=old.owned_window(owner,name);_,x11,wrapped=result\n  from gi.repository import Atspi\n  state['cache']=cache_owned_application(reader,Atspi,wrapped.value,pid=x11['pid'],identity=identity)\n  reader.require(wrapped.value.get_name()==x11['title'],'Native owned window title changed after cache clear')\n  state['resolver']=RecordedPaths(wrapped.value,x11['pid'],identity)")
 source=source.replace("'SCHEMA':'cua-native-visible-surface-probe-v38'","'SCHEMA':SCHEMA")
 proof="'native_forward_graph_deferred':state['resolver'].deferred,"
 if source.count(proof)!=1:raise ValueError('Frozen native ownership proof projection changed')
 source=source.replace(proof,proof+"\n  'native_cache_current_receipt':state['cache'],")
 namespace['SCHEMA']=SCHEMA
 exec(compile(source,__file__,'exec'),namespace)
 original=namespace['guarded_run']
 def guarded_run(**kwargs):
  result=original(**kwargs)
  return {**result,'native_inventory_order':'bounded_breadth_first','application_cache_policy':'same_owned_process_and_bus_NONE',
   'old_results_reclassified':False}
 namespace['guarded_run']=guarded_run
 main=FunctionType(base.main.__code__,namespace,base.main.__name__,base.main.__defaults__,base.main.__closure__)
 return guarded_run,main

if __name__=='__main__':scoped_reader()[1]()
