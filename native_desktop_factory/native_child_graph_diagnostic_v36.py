"""Bounded actual forward child edges; no ownership or actor qualification."""
from __future__ import annotations
import argparse,json,hashlib,importlib.util
from pathlib import Path

V35_SHA='1f90bd3e3c9ceac6bddbbb1b5d1bbb5a4be315575e04733e5036bb0c61b71648'
PRIVATE_PATH=Path('/tmp/envloop-native-child-v36-facts.private.jsonl')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def peer():
 path=Path(__file__).with_name('native_window_relation_diagnostic_v35.py')
 if sha(path.read_bytes())!=V35_SHA:raise ValueError('Pinned V35 source changed')
 spec=importlib.util.spec_from_file_location('envloop_child_graph_v36_peer',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def capture(root,needles,*,identity,limit=48,max_children=64,max_depth=3,sink=None):
 if not 1<=limit<=48 or not 1<=max_children<=64 or not 0<=max_depth<=3:raise ValueError('Diagnostic bounds required')
 todo=[(root,[])];seen=set();nodes=[];edges=[];matches={key:[] for key in needles};deferred=[]
 while todo and len(nodes)<limit:
  node,path=todo.pop(0);native=identity(node);key=native.get('identity_sha256')
  if not native.get('available') or key is None:
   deferred.append({'reason':'native_identity_unknown','path':path});continue
  if key in seen:continue
  seen.add(key)
  row={'native_identity':native,'depth':len(path),'native_role':None,'native_pid':None,'child_count':None,'field_errors':{}}
  for field,read in [('native_role',node.get_role_name),('native_pid',node.get_process_id),('child_count',node.get_child_count)]:
   try:row[field]=read()
   except Exception as error:row['field_errors'][field]=type(error).__name__
  nodes.append(row)
  if sink:sink({'kind':'actual_forward_graph_node','facts':row})
  if key in matches:matches[key].append(path)
  count=row['child_count']
  if type(count) is not int or count<0 or count>max_children or len(path)>=max_depth:
   deferred.append({'reason':'unknown_large_or_depth_bounded_children','native_identity_sha256':key,'actual_child_count':count});continue
  for index in range(count):
   if len(todo)+len(nodes)>=limit:
    deferred.append({'reason':'node_budget_exhausted','native_identity_sha256':key,'next_child_index':index});break
   try:
    child=node.get_child_at_index(index)
    if child is None:raise ValueError('Actual child unavailable')
    child_id=identity(child);child_key=child_id.get('identity_sha256')
    edge={'parent_identity_sha256':key,'native_child_index':index,'returned_child_identity':child_id,'actual_forward_query_returned':True}
    edges.append(edge)
    if sink:sink({'kind':'actual_forward_child_edge','facts':edge})
    if child_id.get('available') and child_key is not None:todo.append((child,path+[edge]))
    else:deferred.append({'reason':'child_identity_unknown','edge':edge})
   except Exception as error:deferred.append({'reason':'child_query_unavailable','parent_identity_sha256':key,'native_child_index':index,'error_class':type(error).__name__})
 return {'nodes':nodes,'edges':edges,'exact_forward_paths_to_requested_identities':matches,'deferred':deferred,'unvisited_queued_nodes':len(todo),'node_limit':limit,'child_limit':max_children,'depth_limit':max_depth,'complete_tree_claimed':False,'native_ownership_authorized':False}

def run(*,filename,viewport):
 relations=peer();inventory=relations.peer();diag=inventory.peer();reader=diag.load();old=reader.namespace['peer']();owner=old.owner_module();frozen,x11,wrapped=old.owned_window(owner,filename);owned=wrapped.value
 import gi
 gi.require_version('Atspi','2.0');from gi.repository import Atspi
 writer=diag.PrivateFacts(PRIVATE_PATH);needles={diag.identity(owned)['identity_sha256']};refused=[];refusal=None
 try:
  box=reader.geometry(Atspi,owned,viewport)
  if box is None:raise ValueError('Owned native geometry unavailable')
  point=[box[0]+box[2]//2,box[1]+box[3]//2]
  def ancestry(node,window):
   try:return old.ancestors(node,window)
   except Exception:
    cursor=node
    for index in range(32):
     if cursor is None:break
     facts=diag.structural_facts(cursor,window,Atspi);refused.append(facts);writer.append({'kind':'preserved_refused_parent','facts':facts})
     if facts['identity']['available']:needles.add(facts['identity']['identity_sha256'])
     if index+1==32:break
     cursor=cursor.get_parent()
    raise
  try:reader.physical_hit(Atspi,owned,point,pid=x11['pid'],viewport=viewport,ancestry=ancestry)
  except Exception as error:refusal={'error_class':type(error).__name__,'message_sha256':sha(str(error).encode())}
  graph=capture(owned,needles,identity=diag.identity,sink=writer.append)
  if frozen.x11()!=x11:raise ValueError('Owned window changed during forward graph read')
 finally:writer.close()
 return {'schema':'cua-native-forward-child-graph-diagnostic-v36','status':'readonly_actual_forward_edges_unqualified','source_sha256':sha(Path(__file__).read_bytes()),'pinned_v35_sha256':V35_SHA,'original_refusal':refusal,'refused_parent_facts':refused,'actual_forward_graph':graph,'private_facts_file':writer.reference(),'actor_actions':0,'model_calls':0,'native_mutations':0,'native_qualification_passed':False}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--filename',required=True);p.add_argument('--width',type=int,default=1280);p.add_argument('--height',type=int,default=800);a=p.parse_args()
 try:value=run(filename=a.filename,viewport=[a.width,a.height])
 except Exception as error:
  value={'schema':'cua-native-forward-child-graph-diagnostic-v36','status':'forward_graph_unavailable_unqualified','error_class':type(error).__name__,'native_qualification_passed':False}
  if PRIVATE_PATH.exists():raw=PRIVATE_PATH.read_bytes();value['partial_private_facts']={'sha256':sha(raw),'bytes':len(raw),'mode':PRIVATE_PATH.stat().st_mode&0o777}
 print(json.dumps(value,sort_keys=True,separators=(',',':')))
if __name__=='__main__':main()
