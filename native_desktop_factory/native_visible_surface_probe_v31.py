"""Additive native point certainty and ancestor-state fix; V30 is preserved."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
from types import FunctionType

SCHEMA='cua-native-visible-surface-probe-v31'
V30_SHA='9a5583b2fd54149465f16d60eea56058665c35d09b67d59a07f4721e867cbefb'
path=Path(__file__).with_name('native_visible_surface_probe_v30.py')
if hashlib.sha256(path.read_bytes()).hexdigest()!=V30_SHA:raise ValueError('Pinned bounded native V30 source changed')
spec=importlib.util.spec_from_file_location('envloop_bounded_peer_v31',path);previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
require=previous.require;state_flags=previous.state_flags;geometry=previous.geometry
MAX_DEPTH=previous.MAX_DEPTH;MAX_CHILDREN=previous.MAX_CHILDREN

def physical_hit(Atspi,window,point,*,pid,viewport,ancestry):
 require(type(point) in (list,tuple) and len(point)==2 and all(type(n) is int for n in point) and 0<=point[0]<viewport[0] and 0<=point[1]<viewport[1],'Requested native point invalid')
 cursor=window;seen=[]
 for _ in range(MAX_DEPTH):
  require(cursor is not None and cursor.get_process_id()==pid,'Native hit process ownership changed')
  ancestry(cursor,window);require(cursor not in seen,'Native physical hit cycle');seen.append(cursor)
  box=geometry(Atspi,cursor,viewport);require(box is not None and box[0]<=point[0]<box[0]+box[2] and box[1]<=point[1]<box[1]+box[3],'Native point outside actual component')
  flags=state_flags(Atspi,cursor);require(flags['VISIBLE'] and flags['SHOWING'] and not flags['DEFUNCT'] and not flags['STALE'],'Native hit state unavailable or unsafe')
  hit=cursor.get_component_iface().get_accessible_at_point(point[0],point[1],Atspi.CoordType.SCREEN)
  if hit is None or hit==cursor:
   # A root miss is unknown. A virtual/large container miss is unknown. Only
   # an actual preceding parent hit plus a native zero-child leaf is terminal.
   require(len(seen)>1,'Native root point hit unavailable')
   require(not flags['MANAGES_DESCENDANTS'],'Native deferred point hit unavailable')
   count=cursor.get_child_count();require(type(count) is int and count==0,'Native terminal point is not a proved leaf')
   return cursor,len(seen)
  cursor=hit
 raise ValueError('Native physical hit depth unbounded')

def native_record(Atspi,node,window,*,pid,uid,viewport,ancestry):
 chain=ancestry(node,window);require(node.get_process_id()==pid,'Native object process ownership changed')
 flags=state_flags(Atspi,node);box=geometry(Atspi,node,viewport);require(box is not None,'Native object outside observed viewport')
 ancestor_flags=[state_flags(Atspi,ancestor) for ancestor in chain]
 require(all(ancestor.get_process_id()==pid for ancestor in chain),'Native ancestor process ownership changed')
 path=[n.get_index_in_parent() for n in reversed(chain[:-1])];role=node.get_role_name()
 import re
 name=node.get_name() if role in ['menu item','push button','link','check menu item','radio menu item'] else ''
 unsafe=role=='link' or bool(re.match(r'^(open|new|print|export|send|share|delete|close|quit|account)\b',name,re.I))
 chain_safe=all(f['VISIBLE'] and f['SHOWING'] and f['ENABLED'] and f['SENSITIVE'] and not f['DEFUNCT'] and not f['STALE'] for f in ancestor_flags)
 enabled=chain_safe and not unsafe
 hit,_=physical_hit(Atspi,window,[box[0]+box[2]//2,box[1]+box[3]//2],pid=pid,viewport=viewport,ancestry=ancestry)
 unobscured=node in ancestry(hit,window)
 sha=previous.sha
 record={'ref':'ax-'+sha(json.dumps(path,separators=(',',':')).encode())[:24],'bounds':box,'visible':flags['VISIBLE'] and flags['SHOWING'],'enabled':enabled,'obscured':not unobscured,
  'keyboard':flags['EDITABLE'] and enabled,'actions':['click','double_click','scroll','drag']+(['type','key'] if flags['EDITABLE'] else [])}
 return record,{'native_uid':uid,'native_pid':pid,'role':role,'ancestor_indices_sha256':sha(json.dumps(path).encode()),'native_flags':flags,'ancestor_native_flags':ancestor_flags,'ancestor_states_checked':True,'point_hit_ownership_checked':True}

# Bind the preserved bounded walk and typed metadata projection into a fresh
# namespace. No previous source module or live frozen runtime is mutated.
namespace={**previous.__dict__,'__file__':__file__,'SCHEMA':SCHEMA,'physical_hit':physical_hit,'native_record':native_record}
bounded_surface=FunctionType(previous.bounded_surface.__code__,namespace,previous.bounded_surface.__name__,previous.bounded_surface.__defaults__,previous.bounded_surface.__closure__)
bounded_surface.__kwdefaults__=previous.bounded_surface.__kwdefaults__;namespace['bounded_surface']=bounded_surface
run=FunctionType(previous.run.__code__,namespace,previous.run.__name__,previous.run.__defaults__,previous.run.__closure__);run.__kwdefaults__=previous.run.__kwdefaults__;namespace['run']=run
PRIVATE_ERROR_PATH=Path('/tmp/envloop-visible-v31-errors.private.json')

def diagnostic_run(*,filename,viewport,points=(),runner=run,error_path=PRIVATE_ERROR_PATH):
 import os
 first_failed=None;trace=[];errors=[];originals={}
 def instrument(name,function):
  def wrapped(*args,**kwargs):
   nonlocal first_failed
   row={'stage':name,'status':'started'};trace.append(row)
   try:value=function(*args,**kwargs);row['status']='completed';return value
   except Exception as error:
    if first_failed is None:first_failed=name
    row['status']='failed';row['error_class']=type(error).__name__
    errors.append({'stage':name,'error_class':type(error).__name__,'error_domain':getattr(error,'domain',None),'error_code':getattr(error,'code',None),'raw_error_string':str(error),'raw_error_sha256':previous.sha(str(error).encode())});raise
  return wrapped
 for name in ['bounded_surface','native_record','physical_hit']:
  originals[name]=(namespace[name],globals().get(name));wrapped=instrument(name,namespace[name]);namespace[name]=wrapped;globals()[name]=wrapped
 original_peer=namespace['peer']
 def owned_peer():
  module=original_peer()
  for name in ['owner_module','owned_window']:setattr(module,name,instrument(name,getattr(module,name)))
  return module
 try:
  value=runner(filename=filename,viewport=viewport,points=points,loader=owned_peer)
 except Exception as error:
  if not errors:errors.append({'stage':first_failed or 'native_run','error_class':type(error).__name__,'error_domain':getattr(error,'domain',None),'error_code':getattr(error,'code',None),'raw_error_string':str(error),'raw_error_sha256':previous.sha(str(error).encode())})
  raw=json.dumps({'schema':'cua-native-private-errors-v31','errors':errors,'actor_access_authorized':False,'public_release_authorized':False},sort_keys=True,separators=(',',':')).encode()
  fd=os.open(error_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
  with os.fdopen(fd,'wb') as file:file.write(raw);file.flush();os.fsync(file.fileno())
  value={'schema':SCHEMA,'status':'unavailable_or_unsafe','first_failed_stage':first_failed or 'native_run','error_class':type(error).__name__,'error_message_sha256':previous.sha(str(error).encode()),'private_error_file':{'sha256':previous.sha(raw),'bytes':len(raw),'mode':0o600},'native_mutations':0,'native_qualification_passed':False}
 finally:
  for name,(old_namespace,old_global) in originals.items():namespace[name]=old_namespace;globals()[name]=old_global
 return {**value,'native_stage_trace':trace}

def main():
 import argparse
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--filename',required=True);parser.add_argument('--width',type=int,default=1280);parser.add_argument('--height',type=int,default=800);parser.add_argument('--points-json',default='[]');args=parser.parse_args()
 print(json.dumps(diagnostic_run(filename=args.filename,viewport=[args.width,args.height],points=json.loads(args.points_json)),sort_keys=True,separators=(',',':')))

if __name__=='__main__':main()
