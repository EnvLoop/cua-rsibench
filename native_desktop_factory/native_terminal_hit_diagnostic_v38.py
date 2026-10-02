"""Retain exact native point refusal facts without changing the V37 verdict."""
from __future__ import annotations
import argparse,hashlib,importlib.util,inspect,json,re
from pathlib import Path
from types import FunctionType

V37_SHA='892d10fbe4e31183cfe6280a1d0108ff88a525caa25d4526626fee7e0c7d1626'
PRIVATE_PATH=Path('/tmp/envloop-native-terminal-v38-facts.private.jsonl')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def load():
 path=Path(__file__).with_name('native_forward_owned_probe_v37.py')
 if sha(path.read_bytes())!=V37_SHA:raise ValueError('Pinned V37 source changed')
 spec=importlib.util.spec_from_file_location('envloop_terminal_diagnostic_v38_peer',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def instrument(reader,identity,writer):
 original=reader.physical_hit;require=original.__globals__['require']
 def checked(condition,message):
  if not condition:
   local=inspect.currentframe().f_back.f_locals
   cursor=local.get('cursor');hit=local.get('hit');Atspi=local.get('Atspi');point=local.get('point')
   row={'kind':'actual_native_point_refusal','message':message,'physical_point':list(point) if point is not None else None,'native_hit_depth':len(local.get('seen',[])),'returned_hit_kind':'none' if hit is None else 'same_native_object' if cursor is not None and identity(hit)==identity(cursor) else 'different_native_object','native_child_count_already_returned':local.get('count'),'native_flags_already_returned':local.get('flags'),'node_identity':identity(cursor) if cursor is not None else None,'native_role':None,'native_geometry':None,'direct_children':[],'optional_errors':{}}
   # Mandatory original facts are durable before any optional native query.
   writer.append(row)
   if cursor is not None:
    try:row['native_role']=cursor.get_role_name()
    except Exception as error:row['optional_errors']['role']=type(error).__name__
    try:
     box=cursor.get_component_iface().get_extents(Atspi.CoordType.SCREEN);row['native_geometry']=[box.x,box.y,box.width,box.height]
    except Exception as error:row['optional_errors']['geometry']=type(error).__name__
    writer.append({'kind':'actual_native_terminal_structure','facts':row})
    count=local.get('count')
    if type(count) is int and 0<=count<=4:
     for index in range(count):
      try:
       child=cursor.get_child_at_index(index);facts={'index':index,'identity':identity(child),'role':child.get_role_name(),'pid':child.get_process_id(),'flags':reader.state_flags(Atspi,child)}
       box=child.get_component_iface().get_extents(Atspi.CoordType.SCREEN);facts['geometry']=[box.x,box.y,box.width,box.height];row['direct_children'].append(facts);writer.append({'kind':'actual_native_terminal_child','facts':facts})
      except Exception as error:row['optional_errors']['child-'+str(index)]=type(error).__name__
   # The preserved production predicate remains authoritative.
  return require(condition,message)
 namespace={**original.__globals__,'require':checked}
 physical=FunctionType(original.__code__,namespace,original.__name__,original.__defaults__,original.__closure__);physical.__kwdefaults__=original.__kwdefaults__
 record=FunctionType(reader.native_record.__code__,{**reader.native_record.__globals__,'physical_hit':physical},reader.native_record.__name__,reader.native_record.__defaults__,reader.native_record.__closure__);record.__kwdefaults__=reader.native_record.__kwdefaults__
 bounded=FunctionType(reader.bounded_surface.__code__,{**reader.bounded_surface.__globals__,'physical_hit':physical,'native_record':record},reader.bounded_surface.__name__,reader.bounded_surface.__defaults__,reader.bounded_surface.__closure__);bounded.__kwdefaults__=reader.bounded_surface.__kwdefaults__
 reader.namespace.update(physical_hit=physical,native_record=record,bounded_surface=bounded);reader.physical_hit=physical;reader.native_record=record;reader.bounded_surface=bounded
 return reader

def run(*,filename,viewport):
 peer=load();diag=peer.load('native_hit_identity_diagnostic_v33.py',peer.V33_SHA);writer=diag.PrivateFacts(PRIVATE_PATH);original=peer.load
 def current(name,expected):
  module=original(name,expected)
  return instrument(module,diag.identity,writer) if name=='native_visible_surface_probe_v31.py' else module
 peer.load=current
 try:
  try:value=peer.run(filename=filename,viewport=viewport)
  except Exception as error:value={'status':'preserved_native_refusal','error_class':type(error).__name__,'error_message_sha256':sha(str(error).encode())}
 finally:writer.close()
 return {'schema':'cua-native-terminal-hit-diagnostic-v38','status':value['status'],'preserved_v37_result':value,'private_facts_file':writer.reference(),'original_native_safety_rule_changed':False,'native_qualification_passed':False,'native_mutations':0,'actor_actions':0,'model_calls':0}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--filename',required=True);p.add_argument('--width',type=int,default=1280);p.add_argument('--height',type=int,default=800);p.add_argument('--guarded',action='store_true');p.add_argument('--points-json',default='[]');p.add_argument('--facts-path',type=Path,default=PRIVATE_PATH);a=p.parse_args()
 try:value=guarded_run(filename=a.filename,viewport=[a.width,a.height],points=json.loads(a.points_json),facts_path=a.facts_path) if a.guarded else run(filename=a.filename,viewport=[a.width,a.height])
 except Exception as error:value={'schema':'cua-native-terminal-hit-diagnostic-v38','status':'terminal_diagnostic_unavailable','error_class':type(error).__name__,'error_message':str(error),'native_qualification_passed':False}
 print(json.dumps(value,sort_keys=True,separators=(',',':')))

# Production-facing refinement for this unfrozen source. Structural nodes are
# inventory only: they never authorize native clicks, keyboard or drag actions.
STRUCTURAL_ROLES=frozenset(('frame','window','root pane','panel','filler','scroll pane','menu bar','layered pane'))

def structural_record(reader,Atspi,node,window,*,pid,uid,viewport,ancestry):
 role=node.get_role_name();flags=reader.state_flags(Atspi,node)
 count=None if flags['MANAGES_DESCENDANTS'] else node.get_child_count()
 structural=role in STRUCTURAL_ROLES or flags['MANAGES_DESCENDANTS'] or (type(count) is int and count>0)
 if not structural:
  try:return reader.native_record(Atspi,node,window,pid=pid,uid=uid,viewport=viewport,ancestry=ancestry)
  except ValueError as error:
   if str(error)!='Native terminal point is not a proved leaf':raise
   # A leaf's center can hit an owned non-leaf sidebar panel. Its target is
   # disabled; actor point hits still execute the original strict predicate.
   structural=True
 chain=ancestry(node,window)
 reader.require(node.get_process_id()==pid and all(parent.get_process_id()==pid for parent in chain),'Native structural ownership changed')
 box=reader.geometry(Atspi,node,viewport);reader.require(box is not None,'Native structural geometry unavailable')
 ancestor_flags=[reader.state_flags(Atspi,parent) for parent in chain]
 reader.require(all(f['VISIBLE'] and f['SHOWING'] and not f['DEFUNCT'] and not f['STALE'] for f in ancestor_flags),'Native structural ancestor unsafe')
 path=[parent.get_index_in_parent() for parent in reversed(chain[:-1])]
 record={'ref':'ax-'+sha(json.dumps(path,separators=(',',':')).encode())[:24],'bounds':box,
  'visible':True,'enabled':False,'obscured':True,'keyboard':False,'actions':[]}
 fact={'native_uid':uid,'native_pid':pid,'role':role,'ancestor_indices_sha256':sha(json.dumps(path).encode()),
  'native_flags':flags,'ancestor_native_flags':ancestor_flags,'ancestor_states_checked':True,
  'point_hit_ownership_checked':False,'actual_native_child_count':count,'structural_inventory_only':True,'native_actions_authorized':False}
 return record,fact

def forward_owned_paths(peer,writer):
 """Reopen exact current edges; reverse-parent bugs never prove ownership."""
 class CurrentForwardPaths(peer.ForwardOwnedPaths):
  def reopen(self,key):
   cursor=self.window;chain=[cursor];path=self.paths[key];relationships=[]
   for edge in path:
    peer.require(self.key(cursor)==edge['parent_identity_sha256'] and cursor.get_process_id()==self.pid,'Forward parent changed')
    count=cursor.get_child_count();peer.require(type(count) is int and 0<=edge['child_index']<count<=peer.MAX_GRAPH_CHILDREN,'Forward child set changed')
    child=cursor.get_child_at_index(edge['child_index'])
    peer.require(self.key(child)==edge['child_identity_sha256'] and child.get_process_id()==self.pid,'Forward child identity changed')
    actual_index=child.get_index_in_parent()
    if actual_index!=edge['child_index']:
     reverse=child.get_parent()
     row={'kind':'actual_forward_reverse_relationship','forward_edge':edge,'actual_child_index_in_parent':actual_index,
      'actual_parent_identity':self.identity(cursor),'actual_child_identity':self.identity(child),
      'actual_reverse_parent_identity':self.identity(reverse) if reverse is not None else None,
      'actual_child_pid':child.get_process_id(),'actual_reverse_parent_pid':reverse.get_process_id() if reverse is not None else None}
     writer.append(row)
     peer.require(reverse is not None and reverse.get_process_id()==self.pid and self.key(reverse)!=self.key(cursor),'Native child index mismatch without different owned reverse parent')
     # A second native read must reopen both the parent and this exact slot.
     peer.require(self.key(cursor)==edge['parent_identity_sha256'] and cursor.get_process_id()==self.pid,'Forward parent changed on reread')
     again=cursor.get_child_at_index(edge['child_index'])
     peer.require(self.key(again)==edge['child_identity_sha256'] and again.get_process_id()==self.pid,'Forward child identity changed on reread')
     relationships.append({**row,'actual_forward_slot_reopened_twice':True,'reverse_parent_used_for_ownership':False})
    chain.append(child);cursor=child
   proof={'matched_identity_sha256':key,'actual_forward_edges_reopened':path,
    'reverse_parent_inconsistencies':relationships,'same_pid_alone_used':False}
   self.actual_reopen_count=getattr(self,'actual_reopen_count',0)+1
   # Revalidate every call; retain each identical proof once so metadata stays
   # bounded. The private diagnostic journal keeps each reverse discrepancy.
   proof_sha=sha(json.dumps(proof,sort_keys=True,separators=(',',':')).encode())
   seen=getattr(self,'_retained_proof_sha256s',set())
   if proof_sha not in seen:self.proofs.append(proof);seen.add(proof_sha)
   self._retained_proof_sha256s=seen
   return list(reversed(chain))
 return CurrentForwardPaths

def bounded_runtime_journal(diag,path):
 """Diagnostic sampling cannot overflow a valid bounded inventory walk."""
 class Journal:
  def __init__(self):
   self.raw=diag.PrivateFacts(path);self.counts={};self.retained={};self.omitted=0;self.chain='0'*64;self.closed=False
  def append(self,row):
   kind=row.get('kind','unknown');encoded=diag.canonical(row)
   self.counts[kind]=self.counts.get(kind,0)+1;self.chain=sha(bytes.fromhex(self.chain)+encoded)
   if self.retained.get(kind,0)<8 and self.raw.count<80 and self.raw.bytes+len(encoded)<98304:
    self.raw.append(row);self.retained[kind]=self.retained.get(kind,0)+1
   else:self.omitted+=1
  def close(self):
   if not self.closed:
    self.raw.append({'kind':'bounded_runtime_diagnostic_summary','actual_record_counts':self.counts,
     'retained_sample_counts':self.retained,'omitted_diagnostic_samples':self.omitted,
     'all_record_hash_chain_sha256':self.chain,'native_predicates_skipped':0,'native_actions_authorized':False})
    self.raw.close();self.closed=True
  def reference(self):return self.raw.reference()
 return Journal()

def checked_inventory_visit(node,window,*,pid,ancestry,identity,seen,maximum,depth,branches,writer):
 """Bound inventory only; dedupe requires fresh exact owned identity proof."""
 value=identity(node);key=value.get('identity_sha256')
 if not value.get('available') or not isinstance(key,str):raise ValueError('Native inventory identity unavailable')
 if key in seen or len(seen)>=maximum:
  if node.get_process_id()!=pid:raise ValueError('Deferred native branch process ownership changed')
  ancestry(node,window)
  reason='reopened_owned_identity_duplicate' if key in seen else 'native_node_budget_cap'
  row={'deferred':True,'reason':reason,'depth':depth,'identity_sha256':key,'ownership_reopened':True}
  branches.append(row);writer.append({'kind':'actual_native_inventory_deferral',**row});return False
 seen.add(key);return True

def guarded_run(*,filename,viewport,points=(),facts_path=PRIVATE_PATH):
 """Same fresh X11/principal/forward paths, strict leaf hits for actor points."""
 peer=load();reader=peer.load('native_visible_surface_probe_v31.py',peer.V31_SHA)
 diag=peer.load('native_hit_identity_diagnostic_v33.py',peer.V33_SHA);identity=diag.identity
 reader.require(facts_path==PRIVATE_PATH or re.fullmatch(r'/tmp/envloop-native-terminal-v38-facts-[0-9]{6}\.private\.jsonl',str(facts_path)) is not None,'Native runtime facts namespace invalid')
 writer=bounded_runtime_journal(diag,facts_path);reader=instrument(reader,identity,writer)
 old=reader.namespace['peer']();state={}
 RecordedPaths=forward_owned_paths(peer,writer)
 def owned_window(owner,name):
  result=old.owned_window(owner,name);_,x11,wrapped=result
  state['resolver']=RecordedPaths(wrapped.value,x11['pid'],identity)
  return result
 def ancestors(node,window):return state['resolver'].ancestors(node,window)
 def record(*args,**kwargs):return structural_record(reader,*args,**kwargs)
 namespace={**reader.namespace,'__file__':__file__,'SCHEMA':'cua-native-visible-surface-probe-v38',
  'native_record':record,'physical_hit':reader.physical_hit,
  'inventory_visit':lambda node,window,pid,ancestry,seen,maximum,depth,branches:checked_inventory_visit(node,window,pid=pid,ancestry=ancestry,identity=identity,seen=seen,maximum=maximum,depth=depth,branches=branches,writer=writer)}
 import inspect,textwrap
 walk_source=textwrap.dedent(inspect.getsource(reader.previous.bounded_surface))
 original="   require(len(targets)<MAX_TARGETS,'Native visible target cap');targets.append(record);facts.append(fact)\n   if flags['FOCUSED']:focused.append((record,role))"
 replacement="   if record['enabled'] and not record['obscured']:\n    require(len(targets)<MAX_TARGETS,'Native visible target cap');targets.append(record);facts.append(fact)\n    if flags['FOCUSED']:focused.append((record,role))\n   else:row['inventory_only_nonactionable']=True"
 reader.require(walk_source.count(original)==1,'Native inventory projection source changed')
 cap="  require(node not in seen and len(seen)<MAX_NODES,'Native visible branch cycle or node cap');seen.append(node)"
 bounded="  if not inventory_visit(node,window,pid,ancestry,seen,MAX_NODES,depth,branches):return"
 reader.require(walk_source.count(cap)==1,'Native node budget source changed')
 reader.require(walk_source.count('seen=[]')==1,'Native visited inventory source changed')
 exec(compile(walk_source.replace(original,replacement).replace(cap,bounded).replace('seen=[]','seen=set()'),__file__,'exec'),namespace)
 runner=FunctionType(reader.run.__code__,namespace,reader.run.__name__,reader.run.__defaults__,reader.run.__closure__)
 proxy=__import__('types').SimpleNamespace(owner_module=old.owner_module,owned_window=owned_window,ancestors=ancestors,OWNER_SHA=old.OWNER_SHA)
 try:value=runner(filename=filename,viewport=viewport,points=points,loader=lambda:proxy)
 finally:writer.close()
 return {**value,'structural_containers_actionable':False,'same_pid_or_geometry_shortcut_used':False,
  'native_forward_path_proofs':state['resolver'].proofs,'native_forward_path_actual_reopen_count':getattr(state['resolver'],'actual_reopen_count',0),
  'native_forward_graph_deferred':state['resolver'].deferred,
  'private_native_facts_file':{'path':str(facts_path),**writer.reference()},
  'native_qualification_passed':False}

if __name__=='__main__':main()
