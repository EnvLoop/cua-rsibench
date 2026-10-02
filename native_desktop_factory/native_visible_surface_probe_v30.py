"""Bounded native branches and lazy physical hits; no recursive Collection scan.

Nonshowing/offscreen branches are pruned before child enumeration. Managed or
large child sets remain explicitly deferred. Only actual native state, geometry,
process ownership and bounded ancestry can enable an action. Deferred focus is
unknown until a native FOCUSED object is actually observed; selection is unused.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

SCHEMA='cua-native-visible-surface-probe-v30'
V27_SHA='a91fa8664bc2c52c4d5d1232f502b9e91e2eacee8cad17ab6eb752c9f7c5a50e'
MAX_NODES=512
MAX_CHILDREN=128
MAX_DEPTH=32
MAX_TARGETS=128
MAX_POINTS=2

def sha(raw):return hashlib.sha256(raw).hexdigest()
def require(ok,code):
 if not ok:raise ValueError(code)
def peer():
 path=Path(__file__).with_name('native_visible_surface_probe_v27.py')
 require(sha(path.read_bytes())==V27_SHA,'Pinned native ownership/ancestry peer changed')
 spec=importlib.util.spec_from_file_location('envloop_visible_peer_v30',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def state_flags(Atspi,node):
 state=node.get_state_set()
 return {name:bool(state.contains(getattr(Atspi.StateType,name))) for name in ['VISIBLE','SHOWING','FOCUSED','ENABLED','SENSITIVE','EDITABLE','MANAGES_DESCENDANTS','DEFUNCT','STALE']}

def geometry(Atspi,node,viewport):
 component=node.get_component_iface()
 if component is None:return None
 box=component.get_extents(Atspi.CoordType.SCREEN)
 left,top=max(0,int(box.x)),max(0,int(box.y));right,bottom=min(viewport[0],int(box.x+box.width)),min(viewport[1],int(box.y+box.height))
 return [left,top,right-left,bottom-top] if right>left and bottom>top else None

def physical_hit(Atspi,window,point,*,pid,viewport,ancestry):
 require(type(point) in (list,tuple) and len(point)==2 and all(type(n) is int for n in point) and 0<=point[0]<viewport[0] and 0<=point[1]<viewport[1],'Requested native point invalid')
 cursor=window;seen=[]
 for _ in range(MAX_DEPTH):
  require(cursor is not None and cursor.get_process_id()==pid,'Native hit process ownership changed')
  ancestry(cursor,window);require(cursor not in seen,'Native physical hit cycle');seen.append(cursor)
  box=geometry(Atspi,cursor,viewport);require(box is not None and box[0]<=point[0]<box[0]+box[2] and box[1]<=point[1]<box[1]+box[3],'Native point outside actual component')
  flags=state_flags(Atspi,cursor);require(flags['VISIBLE'] and flags['SHOWING'] and not flags['DEFUNCT'] and not flags['STALE'],'Native hit state unavailable or unsafe')
  hit=cursor.get_component_iface().get_accessible_at_point(point[0],point[1],Atspi.CoordType.SCREEN)
  if hit is None or hit==cursor:return cursor,len(seen)
  cursor=hit
 raise ValueError('Native physical hit depth unbounded')

def native_record(Atspi,node,window,*,pid,uid,viewport,ancestry):
 chain=ancestry(node,window);require(node.get_process_id()==pid,'Native object process ownership changed')
 flags=state_flags(Atspi,node);box=geometry(Atspi,node,viewport);require(box is not None,'Native object outside observed viewport')
 path=[n.get_index_in_parent() for n in reversed(chain[:-1])];role=node.get_role_name()
 # Administrative labels can deny external navigation; no document/cell/text
 # names or values are retrieved or returned.
 import re
 name=node.get_name() if role in ['menu item','push button','link','check menu item','radio menu item'] else ''
 unsafe=role=='link' or bool(re.match(r'^(open|new|print|export|send|share|delete|close|quit|account)\b',name,re.I))
 enabled=flags['ENABLED'] and flags['SENSITIVE'] and not flags['DEFUNCT'] and not flags['STALE'] and not unsafe
 hit,_=physical_hit(Atspi,window,[box[0]+box[2]//2,box[1]+box[3]//2],pid=pid,viewport=viewport,ancestry=ancestry)
 unobscured=node in ancestry(hit,window)
 record={'ref':'ax-'+sha(json.dumps(path,separators=(',',':')).encode())[:24],'bounds':box,'visible':flags['VISIBLE'] and flags['SHOWING'],'enabled':enabled,'obscured':not unobscured,
  'keyboard':flags['EDITABLE'] and enabled,'actions':['click','double_click','scroll','drag']+(['type','key'] if flags['EDITABLE'] else [])}
 if unsafe:record['enabled']=False;record['keyboard']=False
 return record,{'native_uid':uid,'native_pid':pid,'role':role,'ancestor_indices_sha256':sha(json.dumps(path).encode()),'native_flags':flags,'point_hit_ownership_checked':True}

def bounded_surface(Atspi,window,*,pid,uid,viewport,ancestry):
 targets=[];facts=[];branches=[];focused=[];seen=[]
 def walk(node,depth):
  require(node is not None and depth<=MAX_DEPTH,'Native visible branch depth unavailable')
  require(node not in seen and len(seen)<MAX_NODES,'Native visible branch cycle or node cap');seen.append(node)
  require(node.get_process_id()==pid,'Native branch process ownership changed');ancestry(node,window)
  flags=state_flags(Atspi,node);role=node.get_role_name()
  row={'role':role,'flags':flags,'depth':depth,'child_count':None,'enumerated':False,'deferred':False};branches.append(row)
  # SHOWING includes ancestor exposure. No child count or children are read
  # from a hidden branch, or from an offscreen native component.
  if not flags['VISIBLE'] or not flags['SHOWING']:
   row['pruned']='native_hidden';return
  require(not flags['DEFUNCT'] and not flags['STALE'],'Native branch stale or defunct')
  box=geometry(Atspi,node,viewport);row['bounds']=box
  if node!=window and node.get_component_iface() is not None and box is None:
   row['pruned']='native_offscreen';return
  if box is not None:
   record,fact=native_record(Atspi,node,window,pid=pid,uid=uid,viewport=viewport,ancestry=ancestry)
   require(len(targets)<MAX_TARGETS,'Native visible target cap');targets.append(record);facts.append(fact)
   if flags['FOCUSED']:focused.append((record,role))
  if flags['MANAGES_DESCENDANTS']:
   row['deferred']=True;row['reason']='native_manages_descendants';return
  count=node.get_child_count();require(type(count) is int and count>=0,'Native child count invalid');row['child_count']=count
  if count>MAX_CHILDREN:
   row['deferred']=True;row['reason']='native_child_count_cap';return
  row['enumerated']=True
  for index in range(count):walk(node.get_child_at_index(index),depth+1)
 walk(window,0)
 require(len(focused)<=1,'Native focus ambiguous')
 return targets,facts,branches,focused[0] if focused else None

def run(*,filename,viewport,points=(),loader=peer):
 require(len(points)<=MAX_POINTS,'Native lazy point count exceeded')
 old=loader();owner=old.owner_module();frozen,x11,wrapped=old.owned_window(owner,filename);window=wrapped.value
 import gi
 gi.require_version('Atspi','2.0');from gi.repository import Atspi
 targets,facts,branches,focus=bounded_surface(Atspi,window,pid=x11['pid'],uid=x11['uid'],viewport=viewport,ancestry=old.ancestors)
 hits=[]
 for point in points:
  node,depth=physical_hit(Atspi,window,point,pid=x11['pid'],viewport=viewport,ancestry=old.ancestors)
  target,fact=native_record(Atspi,node,window,pid=x11['pid'],uid=x11['uid'],viewport=viewport,ancestry=old.ancestors)
  hits.append({'requested_point':list(point),'actual_hit':target,'native_fact':fact,'native_hit_depth':depth})
  if target['ref'] not in [t['ref'] for t in targets]:
   require(len(targets)<MAX_TARGETS,'Native lazy target cap');targets.append(target);facts.append(fact)
  if fact['native_flags']['FOCUSED']:
   require(focus is None or focus[0]['ref']==target['ref'],'Native lazy focus ambiguous');focus=(target,fact['role'])
 require(frozen.x11()==x11,'Native window changed during bounded query')
 suffix=Path(filename).suffix;require(suffix in ['.xlsx','.pptx','.docx'],'Owned native document suffix invalid')
 role=window.get_role_name();focus_ref=focus[0]['ref'] if focus else 'native-focus-unknown' if any(b['deferred'] for b in branches) else 'native-no-editable-focus'
 return {'schema':SCHEMA,'status':'observed','probe_source_sha256':sha(Path(__file__).read_bytes()),'ownership_source_sha256':old.OWNER_SHA,'native_api':'x11-and-gi-atspi-bounded-visible-physical-hit',
  'window_id_sha256':sha(x11['window_id'].encode()),'window_title_sha256':sha(x11['title'].encode()),'native_pid':x11['pid'],'native_uid':x11['uid'],'account_sha256':sha(str(x11['uid']).encode()),
  'owned_document_window':filename in x11['title'],'owned_native_application':True,'viewport':viewport,'view_id':{'.xlsx':'calc','.pptx':'impress','.docx':'writer'}[suffix],
  'context_id':sha((x11['window_id']+'|'+str(x11['pid'])).encode()),'modal_id':'none' if role in ['frame','window'] else 'unknown-native-dialog','focus_id':focus_ref,
  'focus_editable':bool(focus and focus[0]['keyboard']),'focus_fill_scope_verified':bool(focus and focus[0]['keyboard'] and focus[1] in ['text','entry','combo box','spin button']),
  'actual_native_focus_proof':focus is not None,'focus_from_selection':False,'targets':targets,'native_facts':facts,'branches':branches,'requested_point_facts':hits,
  'full_virtual_tree_enumerated':False,'recursive_collection_query_called':False,'task_values_read':False,'native_mutations':0,'raster_equality_used':False,'native_qualification_passed':False}

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--filename',required=True);parser.add_argument('--width',type=int,default=1280);parser.add_argument('--height',type=int,default=800);parser.add_argument('--points-json',default='[]');args=parser.parse_args()
 try:value=run(filename=args.filename,viewport=[args.width,args.height],points=json.loads(args.points_json))
 except Exception as error:value={'schema':SCHEMA,'status':'unavailable_or_unsafe','error_class':type(error).__name__,'error_message_sha256':sha(str(error).encode()),'native_mutations':0,'native_qualification_passed':False}
 print(json.dumps(value,sort_keys=True,separators=(',',':')))

if __name__=='__main__':main()
