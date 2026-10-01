"""Read-only native relation targets and explicit X11 frame/tree witnesses."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re

SCHEMA='cua-native-window-relation-diagnostic-v35'
V34_SHA='6682b1cd06323cb976fe07ca3d8d8ac0263c578f3b128d5a9cf1bf090e32dd25'
MAX_RELATIONS=16;MAX_TARGETS_PER_RELATION=8;MAX_TOTAL_TARGETS=64;MAX_X11_CHILDREN=64
PRIVATE_PATH=Path('/tmp/envloop-native-window-v35-facts.private.jsonl')

def sha(raw):return hashlib.sha256(raw).hexdigest()
def require(ok,code):
 if not ok:raise ValueError(code)
def peer():
 path=Path(__file__).with_name('native_window_inventory_diagnostic_v34.py');require(sha(path.read_bytes())==V34_SHA,'Pinned V34 diagnostic changed')
 spec=importlib.util.spec_from_file_location('envloop_native_relation_v35_peer',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def frame_extents(raw):
 match=re.search(r'^_NET_FRAME_EXTENTS\(CARDINAL\)\s*=\s*([0-9]+),\s*([0-9]+),\s*([0-9]+),\s*([0-9]+)\s*$',raw,re.M)
 if match is None:return {'available':False,'value':None,'unknown_not_zero':True}
 values=[int(n) for n in match.groups()];require(all(n<=16384 for n in values),'Actual X11 frame extents exceed bound');return {'available':True,'value':values,'unknown_not_zero':False}

def decorated_geometry(client,extents):
 if not extents['available']:return None
 left,right,top,bottom=extents['value'];x,y,width,height=client
 return [x-left,y-top,width+left+right,height+top+bottom]

def transient(raw):
 match=re.search(r'^WM_TRANSIENT_FOR\(WINDOW\): window id #\s*(0x[0-9a-fA-F]+)\s*$',raw,re.M)
 return {'available':match is not None,'xid':int(match[1],16) if match else None,'not_ownership_authority':True}

def direct_tree(raw):
 root=re.search(r'^\s*Root window id:\s*(0x[0-9a-fA-F]+)',raw,re.M);parent=re.search(r'^\s*Parent window id:\s*(0x[0-9a-fA-F]+)',raw,re.M);count=re.search(r'^\s*([0-9]+) children?[.:]\s*$',raw,re.M)
 require(root is not None and parent is not None and count is not None,'Actual direct X11 tree unavailable');number=int(count[1]);require(number<=MAX_X11_CHILDREN,'Direct X11 child count exceeds bound')
 children=re.findall(r'^\s+(0x[0-9a-fA-F]+)\s+',raw[count.end():],re.M);require(len(children)==number,'Actual direct X11 child IDs incomplete');ids=[int(n,16) for n in children];require(len(ids)==len(set(ids)),'Actual direct X11 child IDs duplicated')
 return {'root_xid':int(root[1],16),'parent_xid':int(parent[1],16),'child_xids':ids,'recursive_tree_enumerated':False}

def relation_facts(node,owned,Atspi,*,structural,sink=None):
 result={'node_identity':structural(node,owned,Atspi)['identity'],'relations':[],'relation_errors':{},'reported_relation_count':None,'native_ownership_authorized':False};targets=0
 try:
  relations=node.get_relation_set();result['reported_relation_count']=len(relations) if type(relations) in (list,tuple) else None;require(type(relations) in (list,tuple) and len(relations)<=MAX_RELATIONS,'Native relation count exceeds bound')
 except Exception as error:result['relation_errors']['get_relation_set']=type(error).__name__;return result
 for relation in relations:
  row={'native_relation_type':None,'targets':[],'error_class':None};result['relations'].append(row)
  try:
   row['native_relation_type']=int(relation.get_relation_type());count=relation.get_n_targets();row['reported_target_count']=count;require(type(count) is int and 0<=count<=MAX_TARGETS_PER_RELATION and targets+count<=MAX_TOTAL_TARGETS,'Native relation target count exceeds bound');targets+=count
   if sink is not None:sink({'kind':'native_relation_header','facts':row})
   for index in range(count):
    target=relation.get_target(index);require(target is not None,'Actual native relation target unavailable');facts=structural(target,owned,Atspi);row['targets'].append(facts)
    if sink is not None:sink({'kind':'native_relation_target','facts':facts})
  except Exception as error:row['error_class']=type(error).__name__
 return result

def run(*,filename,viewport,loader=peer,facts_path=PRIVATE_PATH):
 inventory=loader();diagnostic=inventory.peer();reader=diagnostic.load();old=reader.namespace['peer']();owner=old.owner_module();frozen,x11,wrapped=old.owned_window(owner,filename);owned=wrapped.value
 import gi
 gi.require_version('Atspi','2.0');from gi.repository import Atspi
 writer=diagnostic.PrivateFacts(facts_path);refusal=None;frames=[owned];point_parent_facts=[]
 try:
  query=lambda args:inventory.command(args,sink=writer.append);xid=int(x11['window_id']);physical=inventory.physical_window(xid,query=query);require(physical['pid']==x11['pid'] and physical['uid']==x11['uid'] and physical['exe_sha256']==owner.ATTESTED_EXE_SHA,'Actual physical source identity differs')
  properties=query(['xprop','-id',str(xid),'_NET_FRAME_EXTENTS','WM_TRANSIENT_FOR','_NET_WM_WINDOW_TYPE']);extents=frame_extents(properties);tree=direct_tree(query(['xwininfo','-id',str(xid),'-children']));x11_facts={'client':physical,'frame_extents':extents,'derived_decorated_geometry':decorated_geometry(physical['geometry'],extents),'transient_for':transient(properties),'direct_tree':tree,'property_output_sha256':sha(properties.encode()),'coordinate_tolerance_used':False};writer.append({'kind':'explicit_x11_frame_witness','facts':x11_facts})
  # Query actual parent-frame/child geometries; no recursive tree traversal or
  # assumption that an X11 child belongs to an AT-SPI node.
  related=[]
  ids=[tree['parent_xid'],*tree['child_xids']];require(len(ids)<=MAX_X11_CHILDREN+1,'X11 related-window count exceeds bound')
  for related_xid in ids:
   raw=query(['xwininfo','-id',str(related_xid),'-stats']);row={'xid':related_xid,'actual_geometry':inventory.x_geometry(raw)};related.append(row);writer.append({'kind':'actual_x11_parent_or_child_geometry','facts':row})
  box=reader.geometry(Atspi,owned,viewport);require(box is not None,'Actual owned component geometry unavailable');point=[box[0]+box[2]//2,box[1]+box[3]//2]
  def ancestry(node,window):
   try:return old.ancestors(node,window)
   except Exception:
    cursor=node
    for index in range(32):
     if cursor is None:break
     row=diagnostic.structural_facts(cursor,window,Atspi);point_parent_facts.append(row);writer.append({'kind':'preserved_refused_parent','facts':row})
     if cursor.get_role_name() in ['frame','window','dialog','alert'] and cursor not in frames:frames.append(cursor)
     if index+1==32:break
     cursor=cursor.get_parent()
    raise
  try:reader.physical_hit(Atspi,owned,point,pid=x11['pid'],viewport=viewport,ancestry=ancestry)
  except Exception as error:refusal={'error_class':type(error).__name__,'error_message_sha256':sha(str(error).encode())}
  require(len(frames)<=32,'Native relation frame count exceeds bound');native=[]
  for frame in frames:
   row={'structural':diagnostic.structural_facts(frame,owned,Atspi),'relations':relation_facts(frame,owned,Atspi,structural=diagnostic.structural_facts,sink=writer.append)};native.append(row);writer.append({'kind':'native_frame_relations','facts':row})
  require(frozen.x11()==x11,'Owned native window changed during relation diagnostic')
 finally:writer.close()
 return {'schema':SCHEMA,'status':'readonly_relation_witness_unqualified','source_sha256':sha(Path(__file__).read_bytes()),'pinned_v34_sha256':V34_SHA,'x11_frame_witness':x11_facts,'x11_related_geometry':related,'native_frame_relations':native,'refused_parent_facts':point_parent_facts,'original_reader_refusal':refusal,'private_facts_file':writer.reference(),'coordinate_mode':'SCREEN','window_coordinate_substitution_used':False,'native_qualification_passed':False,'native_actions_authorized':False,'actor_actions':0,'model_calls':0,'native_mutations':0}

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--filename',required=True);parser.add_argument('--width',type=int,default=1280);parser.add_argument('--height',type=int,default=800);args=parser.parse_args()
 try:value=run(filename=args.filename,viewport=[args.width,args.height])
 except Exception as error:
  value={'schema':SCHEMA,'status':'native_relation_diagnostic_unavailable_unqualified','error_class':type(error).__name__,'error_message_sha256':sha(str(error).encode()),'native_qualification_passed':False,'native_mutations':0}
  if PRIVATE_PATH.exists():raw=PRIVATE_PATH.read_bytes();value['partial_private_facts']={'sha256':sha(raw),'bytes':len(raw),'mode':PRIVATE_PATH.stat().st_mode&0o777}
 print(json.dumps(value,sort_keys=True,separators=(',',':')))

if __name__=='__main__':main()
