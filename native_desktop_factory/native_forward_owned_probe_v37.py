"""Fresh bounded forward-edge ownership with preserved native state/hit rules."""
from __future__ import annotations
import argparse,hashlib,importlib.util,json
from pathlib import Path
from types import FunctionType,SimpleNamespace

V31_SHA='55f0c01a57afa4795b5c8c6b02ba25892266f6963cb4d60ccba873627b48d8fa'
V33_SHA='f4f254efd6773ba55b9a3cebfac8dcdf2c07ef212c3fb0755daf598f437c9109'
SCHEMA='cua-native-forward-owned-probe-v37'
MAX_GRAPH_NODES=48;MAX_GRAPH_CHILDREN=64;MAX_GRAPH_DEPTH=3;MAX_ANCESTORS=32

def sha(raw):return hashlib.sha256(raw).hexdigest()
def require(ok,message):
 if not ok:raise ValueError(message)
def load(name,expected):
 path=Path(__file__).with_name(name);require(sha(path.read_bytes())==expected,'Pinned native peer changed')
 spec=importlib.util.spec_from_file_location('envloop_forward_owned_v37_'+path.stem,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

class ForwardOwnedPaths:
 """A catalogue is fresh per probe; every accepted forward path is reopened."""
 def __init__(self,window,pid,identity):
  self.window=window;self.pid=pid;self.identity=identity;self.paths={};self.proofs=[];self.deferred=[]
  pending=[(window,[])];visited=set();nodes=0
  while pending and nodes<MAX_GRAPH_NODES:
   node,path=pending.pop(0);key=self.key(node)
   if key in visited:continue
   visited.add(key);nodes+=1;require(node.get_process_id()==pid,'Forward graph process differs')
   self.paths[key]=path
   count=node.get_child_count();require(type(count) is int and count>=0,'Native forward child count unavailable')
   if count>MAX_GRAPH_CHILDREN or len(path)>=MAX_GRAPH_DEPTH:
    self.deferred.append({'identity_sha256':key,'actual_child_count':count,'depth':len(path)});continue
   for index in range(count):
    if nodes+len(pending)>=MAX_GRAPH_NODES:break
    child=node.get_child_at_index(index);require(child is not None,'Actual forward child unavailable')
    child_key=self.key(child);pending.append((child,path+[{'parent_identity_sha256':key,'child_index':index,'child_identity_sha256':child_key}]))
 def key(self,node):
  require(node is not None,'Native node unavailable');value=self.identity(node)
  require(value.get('available') is True and isinstance(value.get('identity_sha256'),str),'Native bus/object identity unavailable')
  return value['identity_sha256']
 def reopen(self,key):
  path=self.paths[key];cursor=self.window;chain=[cursor]
  for edge in path:
   require(self.key(cursor)==edge['parent_identity_sha256'] and cursor.get_process_id()==self.pid,'Forward parent changed')
   count=cursor.get_child_count();require(type(count) is int and edge['child_index']<count<=MAX_GRAPH_CHILDREN,'Forward child set changed')
   child=cursor.get_child_at_index(edge['child_index']);require(self.key(child)==edge['child_identity_sha256'] and child.get_process_id()==self.pid,'Forward child identity changed')
   require(child.get_index_in_parent()==edge['child_index'],'Native child index does not match actual forward edge')
   chain.append(child);cursor=child
  self.proofs.append({'matched_identity_sha256':key,'actual_forward_edges_reopened':path,'same_pid_alone_used':False})
  return list(reversed(chain))
 def ancestors(self,node,window):
  require(self.key(window)==self.key(self.window),'Different ownership root')
  reverse=[];cursor=node;seen=set()
  for _ in range(MAX_ANCESTORS):
   key=self.key(cursor);require(key not in seen,'Native reverse ancestor cycle');seen.add(key)
   require(cursor.get_process_id()==self.pid,'Native ancestor process differs')
   if key in self.paths:
    forward=self.reopen(key)
    require(len(reverse)+len(forward)<=MAX_ANCESTORS,'Native joined ownership path unbounded')
    return reverse+forward
   reverse.append(cursor);cursor=cursor.get_parent()
  raise ValueError('Native node not connected to owned forward graph')

def run(*,filename,viewport,points=()):
 reader=load('native_visible_surface_probe_v31.py',V31_SHA);identity=load('native_hit_identity_diagnostic_v33.py',V33_SHA).identity
 old=reader.namespace['peer']();state={}
 def owned_window(owner,name):
  result=old.owned_window(owner,name);_,x11,wrapped=result;state['resolver']=ForwardOwnedPaths(wrapped.value,x11['pid'],identity);return result
 def ancestors(node,window):
  require('resolver' in state,'Owned root missing');return state['resolver'].ancestors(node,window)
 proxy=SimpleNamespace(owner_module=old.owner_module,owned_window=owned_window,ancestors=ancestors,OWNER_SHA=old.OWNER_SHA)
 namespace={**reader.namespace,'__file__':__file__,'SCHEMA':SCHEMA}
 runner=FunctionType(reader.run.__code__,namespace,reader.run.__name__,reader.run.__defaults__,reader.run.__closure__)
 runner.__kwdefaults__=reader.run.__kwdefaults__
 result=runner(filename=filename,viewport=viewport,points=points,loader=lambda:proxy)
 resolver=state['resolver']
 return {**result,'native_ownership_policy':'fresh_exact_forward_edges_plus_bounded_reverse_chain',
  'native_forward_path_proofs':resolver.proofs,'native_forward_graph_deferred':resolver.deferred,
  'same_pid_or_geometry_shortcut_used':False,'native_qualification_passed':False}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--filename',required=True);p.add_argument('--width',type=int,default=1280);p.add_argument('--height',type=int,default=800);p.add_argument('--points-json',default='[]');a=p.parse_args()
 try:value=run(filename=a.filename,viewport=[a.width,a.height],points=json.loads(a.points_json))
 except Exception as error:value={'schema':SCHEMA,'status':'unavailable_or_unsafe','error_class':type(error).__name__,'error_message_sha256':sha(str(error).encode()),'native_qualification_passed':False,'native_mutations':0}
 print(json.dumps(value,sort_keys=True,separators=(',',':')))
if __name__=='__main__':main()
