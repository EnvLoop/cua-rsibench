"""Offline owned focused-leaf boundaries, without real qualification credit."""
from copy import deepcopy
import inspect,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from native_desktop_factory import native_impress_focus_v52 as focus
from native_desktop_factory import native_editor_reader_v52 as reader
from native_desktop_factory import native_editor_runtime_v52 as runtime
from native_desktop_factory import native_editor_runtime_v51 as old
from native_desktop_factory import native_visible_surface_probe_v30 as walker
from tests.test_native_desktop_impress_selector_v51 import flags,mode
from native_desktop_factory import native_editor_capability_v42 as capability
ROOT=Path(__file__).resolve().parents[1]

class Node:
 def __init__(self,n,role,children=(),focused=True,editable=True):
  self.path='/org/a11y/atspi/accessible/'+str(n);self.app=SimpleNamespace(bus_name=':1.10');self.role=role;self.children=list(children);self.parent=None;self.pid=1
  self.flags=flags(focused=focused);self.flags['EDITABLE']=editable;self.box=[10,10,100,100]
  for child in self.children:child.parent=self
 def get_process_id(self):return self.pid
 def get_role_name(self):return self.role
 def get_child_count(self):return len(self.children)
 def get_child_at_index(self,i):return self.children[i]
 def get_component_iface(self):return self
 def get_index_in_parent(self):return self.parent.children.index(self) if self.parent else 0

class Focus(unittest.TestCase):
 def setUp(self):
  self.leaf=Node(3,'paragraph');self.document=Node(2,'document presentation',[self.leaf]);self.window=Node(1,'frame',[self.document],focused=False,editable=False)
  class Evidence(dict):
   filename='fixture.pptx';x11={'wm_class':'libreoffice-impress'}
   def refresh(self):return self
  self.evidence=Evidence(build=deepcopy(capability.BUILD),native_pid=1,native_uid=1000,mode=mode(),binding='a'*64,medium={'original_medium_writable':True,'original_file_writable':True,'application_is_readonly':False})
  self.reader=SimpleNamespace(_v42_evidence=self.evidence,_v52_query_started=1.,state_flags=lambda A,n:n.flags,geometry=lambda A,n,v:n.box,physical_hit=lambda *a,**k:(self.leaf,3))
  self.seen={focus.checked_identity(n)['identity_sha256'] for n in (self.window,self.document,self.leaf)}
  self.rebuild()
 def ancestry(self,n,w):
  rows=[]
  while n is not None:rows.append(n);n=n.parent
  return rows
 def record(self,n):return {'ref':focus.current_ref(n,self.window,self.ancestry),'bounds':n.box,'enabled':True,'visible':True,'obscured':False,'keyboard':True,'actions':['click','key','type']}
 def rebuild(self):
  self.records=[(self.record(self.document),'document presentation'),(self.record(self.leaf),'paragraph')]
  self.nodes={r['ref']:n for (r,role),n in zip(self.records,(self.document,self.leaf))}
 def invoke(self):
  with patch.object(focus.time,'monotonic',return_value=2.):return focus.resolve_focus(self.reader,None,self.window,pid=1,uid=1000,viewport=[1280,800],ancestry=self.ancestry,focused=self.records,focus_nodes=self.nodes,seen=self.seen)
 def test_exact_leaf_and_verified_passive_document_preserve_flags_rows_targets(self):
  before=deepcopy(self.records);raw=[deepcopy(n.flags) for n in (self.document,self.leaf)]
  result=self.invoke();self.assertEqual(result,[self.records[1]])
  self.assertEqual(self.records,before);self.assertEqual([n.flags for n in (self.document,self.leaf)],raw)
  proof=self.reader._v52_focus_evidence
  self.assertTrue(proof['visible_document_subtree_complete']);self.assertFalse(proof['global_tree_complete_claimed'])
  self.assertEqual(len(proof['all_raw_recorded_global_focus_nodes']),2);self.assertEqual(len(proof['all_raw_focused_document_nodes']),2)
 def test_unrelated_or_multiple_focused_leaves_refuse(self):
  other=Node(4,'paragraph');self.document.children.append(other);other.parent=self.document
  r=self.record(other);self.records.append((r,'paragraph'));self.nodes[r['ref']]=other
  with self.assertRaises(ValueError):self.invoke()
  self.records.pop();self.nodes.pop(r['ref']);self.window.children.append(other);other.parent=self.window
  r=self.record(other);self.records.append((r,'paragraph'));self.nodes[r['ref']]=other
  with self.assertRaises(ValueError):self.invoke()
 def test_managed_deferred_node_budget_duplicate_or_child_cap_refuse(self):
  self.document.flags['MANAGES_DESCENDANTS']=True
  with self.assertRaisesRegex(ValueError,'managed'):self.invoke()
  self.document.flags['MANAGES_DESCENDANTS']=False
  self.seen={'unseen-'+str(i) for i in range(512)}
  with self.assertRaisesRegex(ValueError,'node budget'):self.invoke()
  self.seen={focus.checked_identity(n)['identity_sha256'] for n in (self.window,self.document,self.leaf)}
  self.document.children.extend([self.leaf]*65)
  with self.assertRaisesRegex(ValueError,'child'):self.invoke()
 def test_hidden_noneditable_disabled_stale_foreign_or_identity_missing_refuse(self):
  for key,value in (('VISIBLE',False),('EDITABLE',False),('ENABLED',False),('SENSITIVE',False),('STALE',True),('FOCUSED',False)):
   old_value=self.leaf.flags[key];self.leaf.flags[key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):self.invoke()
   self.leaf.flags[key]=old_value
  self.leaf.pid=99
  with self.assertRaisesRegex(ValueError,'foreign'):self.invoke()
  self.leaf.pid=1;self.leaf.path=None
  with self.assertRaisesRegex(ValueError,'identity'):self.invoke()
 def test_wrong_current_role_ref_build_medium_mode_or_whole_query_clock_refuses(self):
  self.leaf.role='text'
  with self.assertRaisesRegex(ValueError,'role/ref'):self.invoke()
  self.leaf.role='paragraph';self.records[1][0]['ref']='stale-ref';self.nodes['stale-ref']=self.leaf
  with self.assertRaisesRegex(ValueError,'role/ref'):self.invoke()
  self.rebuild()
  for field in ('original_medium_writable','original_file_writable'):
   self.evidence['medium'][field]=False
   with self.assertRaises(ValueError):self.invoke()
   self.evidence['medium'][field]=True
  self.evidence['medium']['application_is_readonly']=True
  with self.assertRaises(ValueError):self.invoke()
  self.evidence['medium']['application_is_readonly']=False;self.evidence['build']={}
  with self.assertRaises(ValueError):self.invoke()
  self.evidence['build']=deepcopy(capability.BUILD);self.evidence['mode']['checked']=False
  with self.assertRaises(ValueError):self.invoke()
  self.evidence['mode']['checked']=True;self.reader._v52_query_started=-29.
  with self.assertRaisesRegex(ValueError,'total time'):self.invoke()
 def test_scope_discovers_unrecorded_second_focus_leaf_and_physical_mismatch(self):
  extra=Node(5,'paragraph');extra.parent=self.document;self.document.children.append(extra)
  with self.assertRaisesRegex(ValueError,'Unrelated'):self.invoke()
  self.document.children.pop();self.reader.physical_hit=lambda *a,**k:(self.document,2)
  with self.assertRaisesRegex(ValueError,'physical leaf'):self.invoke()
 def test_scoped_source_constructs_and_original_walk_caps_remain(self):
  run,main=reader.scoped_reader();self.assertTrue(callable(run));self.assertTrue(callable(main))
  source=inspect.getsource(walker.bounded_surface).replace('seen=[]','seen=set()')
  result=focus.walk_source(source)
  for field in ('depth<=MAX_DEPTH','count>MAX_CHILDREN','len(targets)<MAX_TARGETS'):self.assertIn(field,result)
  self.assertIn('resolve_focus(',result)
 def test_all21_constructors_original_input_code_and_old96_source_globals_unchanged(self):
  raw=Path(old.__file__).read_bytes();attributes=dict(vars(old));manifest=old.source_manifest(ROOT);prior=old.factory(manifest=manifest,source_root=ROOT)
  new_manifest=runtime.source_manifest(ROOT);factory=runtime.factory(manifest=new_manifest,source_root=ROOT)
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   for role in new_manifest['actor_paths']:
    for extension in ('xlsx','docx','pptx'):
     out=root/role/extension;out.mkdir(parents=True)
     actor=factory.wrap_owned_guest(SimpleNamespace(sandbox_id='offline-'+role,files=SimpleNamespace(),commands=SimpleNamespace()),root=root,out=out,filename='fixture.'+extension,lease_started_monotonic=time.monotonic())
     self.assertIs(type(actor),factory.actor_class)
  for method in ('capture','envelope','native_input','lease_check','dispatch_model'):
   a=getattr(factory.actor_class,method).__code__;b=getattr(prior.actor_class,method).__code__;self.assertEqual(a.co_code,b.co_code);self.assertEqual(a.co_consts,b.co_consts)
  self.assertEqual(Path(old.__file__).read_bytes(),raw);self.assertEqual(dict(vars(old)),attributes);self.assertEqual(old.source_manifest(ROOT),manifest)
  for name,digest in manifest['source_sha256s'].items():self.assertEqual(runtime.parent.digest((ROOT/name).read_bytes()),digest)
  self.assertEqual(new_manifest['task_policy'],manifest['task_policy']);self.assertFalse(runtime.public_binding(ROOT)['native_qualification_passed'])
  with self.assertRaises(ValueError):factory.require_activation()
if __name__=='__main__':unittest.main()
