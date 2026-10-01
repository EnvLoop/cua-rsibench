"""Read-only bounded X11 client/native frame inventory; no ownership guesses."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess

SCHEMA='cua-native-window-inventory-diagnostic-v34'
V33_SHA='f4f254efd6773ba55b9a3cebfac8dcdf2c07ef212c3fb0755daf598f437c9109'
MAX_CLIENTS=64;MAX_FRAMES=64;MAX_APPS=64;MAX_ANCESTORS=32
PRIVATE_PATH=Path('/tmp/envloop-native-window-v34-facts.private.jsonl')

def sha(raw):return hashlib.sha256(raw).hexdigest()
def require(ok,code):
 if not ok:raise ValueError(code)
def peer():
 path=Path(__file__).with_name('native_hit_identity_diagnostic_v33.py');require(sha(path.read_bytes())==V33_SHA,'Pinned V33 diagnostic changed')
 spec=importlib.util.spec_from_file_location('envloop_window_inventory_v34_peer',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def client_ids(raw):
 match=re.fullmatch(r'_NET_CLIENT_LIST\(WINDOW\): window id #\s*(.*)',raw.strip());require(match is not None,'Actual EWMH client list unavailable')
 tokens=[n.strip() for n in match[1].split(',') if n.strip()];require(len(tokens)<=MAX_CLIENTS,'Actual X11 client count exceeds bound')
 require(all(re.fullmatch(r'0x[0-9a-fA-F]+',n) for n in tokens),'Actual X11 client ID invalid');ids=[int(n,16) for n in tokens]
 require(len(set(ids))==len(ids) and all(n>0 for n in ids),'Actual X11 client ID duplicate or null');return ids

def x_geometry(raw):
 keys={'Absolute upper-left X':'x','Absolute upper-left Y':'y','Width':'width','Height':'height'};values={}
 for key,name in keys.items():
  matches=re.findall(r'^\s*'+re.escape(key)+r':\s*(-?[0-9]+)\s*$',raw,re.M);require(len(matches)==1,'Actual X11 geometry missing or ambiguous');values[name]=int(matches[0])
 require(values['width']>0 and values['height']>0,'Actual X11 geometry invalid');return [values[n] for n in ['x','y','width','height']]

def command(args,*,runner=subprocess.run,sink=None):
 result=runner(args,capture_output=True,text=True,timeout=5)
 if sink is not None:sink({'kind':'readonly_x11_command','command':args,'returncode':result.returncode,'stdout_sha256':sha(result.stdout.encode()),'stderr_sha256':sha(result.stderr.encode()),'stdout_bytes':len(result.stdout.encode()),'stderr_bytes':len(result.stderr.encode())})
 require(result.returncode==0 and not result.stderr and len(result.stdout.encode())<=32768,'Read-only X11 command failed or exceeded bound');return result.stdout.strip()

def physical_window(xid,*,query=command,proc_root=Path('/proc')):
 row={'xid':xid,'pid':None,'uid':None,'exe_sha256':None,'exe_path':None,'title_sha256':None,'geometry':None,'map_state':None,'wm_class':None,'field_errors':{}}
 for name,args,parse in [('pid',['xdotool','getwindowpid',str(xid)],lambda s:int(s) if re.fullmatch(r'[1-9][0-9]*',s) else None),('title_sha256',['xdotool','getwindowname',str(xid)],lambda s:sha(s.encode())),('geometry',['xwininfo','-id',str(xid),'-stats'],x_geometry),('wm_class',['xprop','-id',str(xid),'WM_CLASS'],lambda s:s)]:
  try:
   raw=query(args);row[name]=parse(raw)
   if name=='geometry':
    maps=re.findall(r'^\s*Map State:\s*(IsViewable|IsUnMapped|IsUnviewable)\s*$',raw,re.M);require(len(maps)==1,'Actual X11 map state unavailable');row['map_state']=maps[0]
  except Exception as error:row['field_errors'][name]=type(error).__name__
 if row['pid'] is not None:
  try:
   proc=Path(proc_root)/str(row['pid']);status=(proc/'status').read_text();match=re.search(r'^Uid:\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)',status,re.M);require(match is not None,'Native process UID unavailable');uids=[int(n) for n in match.groups()];require(len(set(uids))==1,'Native process UID identity ambiguous');row['uid']=uids[0]
   exe=Path(os.readlink(proc/'exe'));row['exe_path']=str(exe);row['exe_sha256']=sha(exe.read_bytes())
  except Exception as error:row['field_errors']['process_identity']=type(error).__name__
 return row

def frame_facts(node,owned,Atspi,*,structural,source):
 row=structural(node,owned,Atspi);row['inventory_source']=source;row['title_sha256']=None;row['native_states']={};row['native_attributes']=[]
 try:row['title_sha256']=sha(node.get_name().encode())
 except Exception as error:row['field_errors']['frame_title']=type(error).__name__
 try:
  state=node.get_state_set();row['native_states']={name:bool(state.contains(getattr(Atspi.StateType,name))) for name in ['ACTIVE','VISIBLE','SHOWING','DEFUNCT','STALE','MODAL']}
 except Exception as error:row['field_errors']['native_states']=type(error).__name__
 try:
  attributes=node.get_attributes();require(type(attributes) is dict and len(attributes)<=32,'Native frame attribute set exceeds bound')
  for key,value in sorted(attributes.items()):
   require(type(key) is str and type(value) is str and len(key.encode())<=1024 and len(value.encode())<=4096,'Native frame attribute type or size invalid')
   row['native_attributes'].append({'key_sha256':sha(key.encode()),'value_sha256':sha(value.encode())})
 except Exception as error:row['field_errors']['native_attributes']=type(error).__name__
 try:
  parent=node.get_parent();row['parent_identity']=None if parent is None else structural(parent,owned,Atspi)['identity']
 except Exception as error:row['field_errors']['native_parent']=type(error).__name__
 return row

def exact_candidates(frames,windows,*,owned_pid,owned_uid,owned_exe_sha256):
 result=[]
 for frame in frames:
  ids=[]
  states=frame.get('native_states',{});geometry_meaningful=states.get('VISIBLE') is True and states.get('SHOWING') is True and states.get('DEFUNCT') is False and states.get('STALE') is False
  if geometry_meaningful and frame.get('native_pid')==owned_pid and frame.get('title_sha256') is not None and frame.get('geometry') is not None:
   ids=[w['xid'] for w in windows if w.get('map_state')=='IsViewable' and w.get('pid')==owned_pid and w.get('uid')==owned_uid and w.get('exe_sha256')==owned_exe_sha256 and w.get('title_sha256')==frame['title_sha256'] and w.get('geometry')==frame['geometry']]
  result.append({'native_identity_sha256':frame['identity']['identity_sha256'],'exact_metadata_candidate_xids':ids,'status':'no_exact_candidate' if not ids else 'unique_exact_metadata_candidate' if len(ids)==1 else 'ambiguous_exact_metadata_candidates','native_ownership_authorized':False,'same_pid_shortcut_used':False,'native_geometry_meaningful':geometry_meaningful})
 return result

def run(*,filename,viewport,loader=peer,facts_path=PRIVATE_PATH):
 diagnostic=loader();reader=diagnostic.load();old=reader.namespace['peer']();owner=old.owner_module();frozen,x11,wrapped=old.owned_window(owner,filename);owned=wrapped.value
 import gi
 gi.require_version('Atspi','2.0');from gi.repository import Atspi
 writer=diagnostic.PrivateFacts(facts_path);windows=[];frames=[];identities=set()
 try:
  query=lambda args:command(args,sink=writer.append)
  ids=client_ids(query(['xprop','-root','_NET_CLIENT_LIST']));require(int(x11['window_id']) in ids,'Owned X11 window is absent from actual client list')
  for xid in ids:
   row=physical_window(xid,query=query);windows.append(row);writer.append({'kind':'x11_client_window','facts':row})
  desktop=Atspi.get_desktop(0);require(desktop.get_child_count()<=MAX_APPS,'Native desktop application count exceeds bound')
  def add(node,source):
   row=frame_facts(node,owned,Atspi,structural=diagnostic.structural_facts,source=source);key=row['identity']['identity_sha256']
   # Missing identity is never deduplicated as if it were the same native node.
   if key is None or key not in identities:
    require(len(frames)<MAX_FRAMES,'Native frame inventory exceeds bound');frames.append(row);writer.append({'kind':'native_frame','facts':row})
    if key is not None:identities.add(key)
  for index in range(desktop.get_child_count()):
   app=desktop.get_child_at_index(index)
   if app.get_process_id()!=x11['pid']:continue
   count=app.get_child_count();require(count<=MAX_FRAMES,'Native application top-level count exceeds bound')
   for number in range(count):
    node=app.get_child_at_index(number)
    if node.get_role_name() in ['frame','window','dialog','alert']:add(node,'application_top_level')
  # Include the exact offending center hit's parent frames if not advertised
  # by the app root, while preserving the original V31 ancestry refusal.
  box=reader.geometry(Atspi,owned,viewport);require(box is not None,'Owned native geometry unavailable');point=[box[0]+box[2]//2,box[1]+box[3]//2];capture=[]
  def ancestry(node,window):
   try:return old.ancestors(node,window)
   except Exception:
    cursor=node
    for ordinal in range(MAX_ANCESTORS):
     if cursor is None:break
     record=diagnostic.structural_facts(cursor,window,Atspi);capture.append(record);writer.append({'kind':'refused_hit_parent','facts':record})
     if cursor.get_role_name() in ['frame','window','dialog','alert']:add(cursor,'refused_point_parent_chain')
     if ordinal+1==MAX_ANCESTORS:break
     cursor=cursor.get_parent()
    raise
  try:reader.physical_hit(Atspi,owned,point,pid=x11['pid'],viewport=viewport,ancestry=ancestry);refusal=False
  except Exception as error:refusal=True;refusal_hash=sha(str(error).encode())
  require(client_ids(query(['xprop','-root','_NET_CLIENT_LIST']))==ids and frozen.x11()==x11,'Native/X11 inventory changed during read-only diagnostic')
  owned_physical=next(w for w in windows if w['xid']==int(x11['window_id']));require(owned_physical['pid']==x11['pid'] and owned_physical['uid']==x11['uid'] and owned_physical['exe_sha256']==owner.ATTESTED_EXE_SHA,'Actual physical owned window identity differs')
  mappings=exact_candidates(frames,windows,owned_pid=x11['pid'],owned_uid=x11['uid'],owned_exe_sha256=owner.ATTESTED_EXE_SHA)
 finally:writer.close()
 return {'schema':SCHEMA,'status':'readonly_native_window_inventory_unqualified','source_sha256':sha(Path(__file__).read_bytes()),'pinned_v33_sha256':V33_SHA,'owned_xid':int(x11['window_id']),'owned_pid':x11['pid'],'owned_uid':x11['uid'],'x11_windows':windows,'native_frames':frames,'exact_metadata_candidates':mappings,'original_refusal_preserved':True,'original_refusal_observed':refusal,'original_refusal_sha256':refusal_hash if refusal else None,'refused_hit_parent_facts':capture,'private_facts_file':writer.reference(),'standardized_native_xid_attribute_assumed':False,'native_qualification_passed':False,'native_actions_authorized':False,'actor_actions':0,'model_calls':0,'native_mutations':0}

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--filename',required=True);parser.add_argument('--width',type=int,default=1280);parser.add_argument('--height',type=int,default=800);args=parser.parse_args()
 try:value=run(filename=args.filename,viewport=[args.width,args.height])
 except Exception as error:
  value={'schema':SCHEMA,'status':'native_window_inventory_unavailable_unqualified','error_class':type(error).__name__,'error_message_sha256':sha(str(error).encode()),'native_qualification_passed':False,'native_mutations':0}
  if PRIVATE_PATH.exists():raw=PRIVATE_PATH.read_bytes();value['partial_private_facts']={'sha256':sha(raw),'bytes':len(raw),'mode':PRIVATE_PATH.stat().st_mode&0o777}
 print(json.dumps(value,sort_keys=True,separators=(',',':')))

if __name__=='__main__':main()
