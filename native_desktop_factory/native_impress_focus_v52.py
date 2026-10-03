"""Resolve only a proved Impress focused leaf/passive document relationship."""
import hashlib,json,time
if __package__:
 from . import native_editor_capability_v42 as base
 from .native_hit_identity_diagnostic_v33 import identity
else:
 import native_editor_capability_v42 as base
 from native_hit_identity_diagnostic_v33 import identity

def safe(flags):
 return all(flags.get(k) is True for k in ('ENABLED','SENSITIVE','VISIBLE','SHOWING')) and flags.get('STALE') is False and flags.get('DEFUNCT') is False

def checked_identity(node):
 value=identity(node)
 if value.get('available') is not True or not isinstance(value.get('identity_sha256'),str):raise ValueError('Native focused identity unavailable')
 return value

def current_ref(node,window,ancestry):
 path=[n.get_index_in_parent() for n in reversed(ancestry(node,window)[:-1])]
 return 'ax-'+hashlib.sha256(json.dumps(path,separators=(',',':')).encode()).hexdigest()[:24]

def resolve_focus(reader,A,window,*,pid,uid,viewport,ancestry,focused,focus_nodes,seen):
 if len(focused)<=1:return focused
 started=getattr(reader,'_v52_query_started',None)
 if type(started) not in (int,float) or time.monotonic()-started>30:raise ValueError('Original native focus query total time bound')
 source=getattr(reader,'_v42_evidence',{})
 if source.get('unavailable') or not str(source.filename).endswith('.pptx') or 'libreoffice-impress' not in source.x11['wm_class']:raise ValueError('Native focus ambiguous outside supported Impress document')
 source.refresh()
 if source['build']!=base.BUILD or source['native_pid']!=pid or source['native_uid']!=uid or source['medium'].get('original_medium_writable') is not True or source['medium'].get('original_file_writable') is not True or source['medium'].get('application_is_readonly') is not False:raise ValueError('Native focus current owner/build/medium unsupported')
 mode=base.checked_edit_mode(source['mode'],document_binding_sha256=source['binding'],now=time.monotonic())
 leaves=[];global_rows=[]
 for record,role in focused:
  node=focus_nodes[record['ref']];flags=reader.state_flags(A,node);node_id=checked_identity(node)
  if node.get_role_name()!=role or current_ref(node,window,ancestry)!=record['ref']:raise ValueError('Current focused role/ref changed')
  global_rows.append({'ref':record['ref'],'identity':node_id,'role':role,'native_flags':flags,'target':record})
  if role=='paragraph' and record['enabled'] and record['keyboard'] and not record['obscured'] and safe(flags) and flags.get('FOCUSED') is True and flags.get('EDITABLE') is True and node.get_child_count()==0:leaves.append((record,node))
 if len(leaves)!=1:raise ValueError('Native focused editable leaf missing or ambiguous')
 record,leaf=leaves[0];chain=ancestry(leaf,window);leaf_id=checked_identity(leaf);ancestors={checked_identity(n)['identity_sha256'] for n in chain[1:]}
 docs=[n for n in chain[1:] if n.get_role_name()=='document presentation']
 if len(docs)!=1:raise ValueError('Native focused leaf original document missing/ambiguous')
 document=docs[0]
 for target,role in focused:
  node=focus_nodes[target['ref']];key=checked_identity(node)['identity_sha256']
  if target['ref']!=record['ref'] and (key not in ancestors or role!='document presentation'):raise ValueError('Unrelated raw focused native object')
 box=reader.geometry(A,leaf,viewport)
 if box is None:raise ValueError('Native focused leaf geometry unavailable')
 hit,_=reader.physical_hit(A,window,[box[0]+box[2]//2,box[1]+box[3]//2],pid=pid,viewport=viewport,ancestry=ancestry)
 if checked_identity(hit)!=leaf_id or hit.get_child_count()!=0:raise ValueError('Native focused physical leaf differs')
 # These nodes reuse the existing visible inventory's unique-ID budget.
 pending=[(document,len(ancestry(document,window))-1)];scope=set();rows=[];raw_focus=[]
 while pending:
  node,depth=pending.pop(0);value=checked_identity(node);key=value.get('identity_sha256')
  if not value.get('available') or depth>32 or time.monotonic()-started>30:raise ValueError('Native document focus scope identity/depth/time incomplete')
  if key in scope:raise ValueError('Native document focus scope duplicate/incomplete')
  scope.add(key)
  if key not in seen:
   if len(seen)>=512:raise ValueError('Native document focus scope original node budget incomplete')
   seen.add(key)
  path=ancestry(node,window)
  if node.get_process_id()!=pid or any(n.get_process_id()!=pid for n in path):raise ValueError('Native document focus scope foreign owner')
  flags=reader.state_flags(A,node)
  if flags['STALE'] or flags['DEFUNCT']:raise ValueError('Native document focus scope stale')
  if not flags['VISIBLE'] or not flags['SHOWING']:continue
  geometry=reader.geometry(A,node,viewport)
  if node.get_component_iface() is not None and geometry is None:continue
  if flags['MANAGES_DESCENDANTS']:raise ValueError('Native managed document focus scope incomplete')
  count=node.get_child_count()
  if type(count) is not int or not 0<=count<=64:raise ValueError('Native document focus child scope incomplete')
  row={'identity':value,'role':node.get_role_name(),'native_flags':flags,'bounds':geometry,'child_count':count}
  rows.append(row)
  if flags['FOCUSED']:
   raw_focus.append(row)
   if key!=leaf_id['identity_sha256'] and key not in ancestors:raise ValueError('Unrelated focused object in complete document scope')
   if key!=leaf_id['identity_sha256'] and row['role']!='document presentation':raise ValueError('Unsupported focused document ancestor')
  pending.extend((node.get_child_at_index(i),depth+1) for i in range(count))
 if time.monotonic()-started>30:raise ValueError('Original native focus query total time bound')
 if sum(row['identity']==leaf_id and row['role']=='paragraph' and row['child_count']==0 and safe(row['native_flags']) and row['native_flags']['FOCUSED'] and row['native_flags']['EDITABLE'] for row in raw_focus)!=1:raise ValueError('Complete document scope has no unique focused editable leaf')
 reader._v52_focus_evidence={'schema':'owned-Impress-focused-leaf-projection-v52','selected_leaf_ref':record['ref'],'selected_leaf_identity':leaf_id,
  'document_identity':checked_identity(document),'visible_document_subtree_complete':True,'document_subtree_nodes':rows,'all_raw_recorded_global_focus_nodes':global_rows,'original_global_inventory_unique_nodes':len(seen),
  'all_raw_focused_document_nodes':raw_focus,'raw_focus_flags_preserved':True,'passive_focused_ancestors_retained':True,
  'global_tree_complete_claimed':False,'original_mode_identity_sha256':mode['node_identity_sha256'],'document_binding_sha256':source['binding'],
  'original_node_depth_time_bounds_preserved':True,'native_input_and_keyboard_guard_unchanged':True}
 return [(record,'paragraph')]

def walk_source(source):
 markers=('focused=[];seen=set()',"if flags['FOCUSED']:focused.append((record,role))","require(len(focused)<=1,'Native focus ambiguous')")
 if any(source.count(marker)!=1 for marker in markers):raise ValueError('Frozen native focus walker source changed')
 return source.replace(markers[0],'focused=[];focus_nodes={};seen=set()').replace(markers[1],markers[1]+";focus_nodes[record['ref']]=node").replace(markers[2],'focused=resolve_focus(focused,focus_nodes,Atspi,window,pid,uid,viewport,ancestry,seen)')
