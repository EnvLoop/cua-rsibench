"""Execute original bounded walker with the narrow Writer source amendment."""
import hashlib,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from native_desktop_factory import native_writer_inventory_v50 as inventory
from native_desktop_factory import native_editor_reader_v50 as reader
from native_desktop_factory import native_editor_runtime_v50 as runtime
from native_desktop_factory import native_editor_runtime_v49 as old
from native_desktop_factory import native_visible_surface_probe_v30 as walker
from native_desktop_factory import native_editor_capability_v42 as capability
ROOT=Path(__file__).resolve().parents[1]
class Node:
 def __init__(self,role,children=(),managed=False,pid=1):self.role=role;self.children=list(children);self.managed=managed;self.pid=pid;self.calls=[]
 def get_role_name(self):return self.role
 def get_process_id(self):return self.pid
 def get_child_count(self):self.calls.append('count');return len(self.children)
 def get_child_at_index(self,i):self.calls.append(i);return self.children[i]
 def get_component_iface(self):return object()
class Inventory(unittest.TestCase):
 def run_walk(self,document,permission,hidden=None,absent_geometry=None):
  window=Node('frame',[document]);records=[]
  def flags(A,n):return {'VISIBLE':n is not hidden,'SHOWING':True,'ENABLED':True,'EDITABLE':True,'SENSITIVE':True,'FOCUSED':False,'STALE':False,'DEFUNCT':False,'MANAGES_DESCENDANTS':n.managed}
  def native(A,n,w,**kw):records.append(n.role);return {'enabled':True,'obscured':False,'ref':str(id(n))},{'native_flags':flags(A,n)}
  namespace={**walker.__dict__,'state_flags':flags,'geometry':lambda A,n,v:None if n is absent_geometry else [0,0,100,100],'native_record':native,'writer_document_count':lambda A,n,w,p,u,a,r,f:permission(n,r)}
  exec(compile(inventory.breadth_first_source(walker.bounded_surface),'offline_original_walker','exec'),namespace)
  result=namespace['bounded_surface'](None,window,pid=1,uid=1000,viewport=[1280,800],ancestry=lambda *a:[window])
  return result,records
 def test_actual_original_walker_observes_small_writer_paragraphs_without_points(self):
  paragraphs=[Node('paragraph') for _ in range(5)];doc=Node('document text',[*paragraphs,Node('heading'),Node('table',managed=True)],managed=True)
  result,records=self.run_walk(doc,lambda n,r:n.get_child_count() if r=='document text' else None)
  self.assertEqual(records.count('paragraph'),5);self.assertNotIn('heading',records);self.assertNotIn('table',records);self.assertEqual(doc.calls,['count',*range(7)])
 def test_calc_and_unknown_managed_nodes_remain_deferred_no_count_read(self):
  for role in ('table','unknown'):
   doc=Node(role,[Node('paragraph')],managed=True);result,records=self.run_walk(doc,lambda *a:None)
   self.assertEqual(doc.calls,[]);self.assertNotIn('paragraph',records);self.assertEqual(result[2][-1]['reason'],'native_manages_descendants')
 def test_foreign_and_nonleaf_visible_child_refuse(self):
  doc=Node('document text',[Node('paragraph',pid=99)],managed=True)
  with self.assertRaisesRegex(ValueError,'foreign process'):self.run_walk(doc,lambda n,r:1)
  doc=Node('document text',[Node('paragraph',[Node('text')])],managed=True)
  with self.assertRaisesRegex(ValueError,'zero-child'):self.run_walk(doc,lambda n,r:1)
 def test_original_child_and_node_caps_not_raised(self):
  source=inventory.breadth_first_source(walker.bounded_surface)
  for text in ('count>MAX_CHILDREN','len(seen)+len(pending)>=MAX_NODES','depth<=MAX_DEPTH','len(targets)<MAX_TARGETS'):self.assertIn(text,source)
  self.assertEqual((walker.MAX_CHILDREN,walker.MAX_NODES,walker.MAX_DEPTH,walker.MAX_TARGETS),(128,512,32,128))
 def test_invisible_or_absent_geometry_paragraph_not_added(self):
  leaf=Node('paragraph');doc=Node('document text',[leaf],managed=True)
  for kwargs in ({'hidden':leaf},{'absent_geometry':leaf}):
   result,records=self.run_walk(doc,lambda n,r:n.get_child_count(),**kwargs)
   self.assertNotIn('paragraph',records)
 def test_original_frontier_node_cap_exhaustion_never_overreads(self):
  children=[Node('panel',[Node('paragraph') for _ in range(128)]) for _ in range(128)]
  doc=Node('panel',children)
  with self.assertRaisesRegex(ValueError,'Native visible target cap'):
   self.run_walk(doc,lambda *a:None)
  self.assertLessEqual(sum(len(c.calls)-1 for c in children if c.calls),512)
 def test_direct_current_document_gate_known_count_and_denials(self):
  from tests.test_native_desktop_writer_pointer_v49 import flags as fflags,mode
  class Evidence(dict):
   filename='fixture.docx';x11={'wm_class':'libreoffice-writer'}
   def refresh(self):return self
  class Document(Node):
   def get_child_count(self):self.calls.append('count');return self.count
  doc=Document('document text',managed=True);doc.count=64;frame=Node('frame');state={**fflags(),'MANAGES_DESCENDANTS':True}
  proof=Evidence(build=capability.BUILD,native_pid=1,native_uid=1000,mode=mode(),binding='a'*64,medium={'original_medium_writable':True,'original_file_writable':True})
  subject=SimpleNamespace(_v42_evidence=proof,state_flags=lambda A,n:{**fflags(sensitive=True),'EDITABLE':False} if n is frame else state)
  def invoke():return inventory.current_document_count(subject,None,doc,frame,pid=1,uid=1000,ancestry=lambda *a:[doc,frame],role='document text',flags=state)
  with patch.object(inventory.time,'monotonic',return_value=2.):
   self.assertEqual(invoke(),64)
   for count in (65,-1,None,True):doc.count=count;self.assertIsNone(invoke())
   doc.count=9
   for key,value in [('ENABLED',False),('EDITABLE',False),('VISIBLE',False),('SHOWING',False),('STALE',True),('DEFUNCT',True)]:
    before=state[key];state[key]=value;self.assertIsNone(invoke());state[key]=before
   for key in ('original_medium_writable','original_file_writable'):
    proof['medium'][key]=False;self.assertIsNone(invoke());proof['medium'][key]=True
   proof['mode']['checked']=False;self.assertIsNone(invoke());proof['mode']['checked']=True
   proof.filename='foreign.xlsx';self.assertIsNone(invoke());proof.filename='fixture.docx'
   proof.x11={'wm_class':'foreign'};self.assertIsNone(invoke());proof.x11={'wm_class':'libreoffice-writer'}
   proof['build']={};self.assertIsNone(invoke());proof['build']=capability.BUILD
   doc.pid=99;self.assertIsNone(invoke());doc.pid=1;frame.pid=99;self.assertIsNone(invoke());frame.pid=1
   before=len(doc.calls)
   self.assertIsNone(inventory.current_document_count(subject,None,doc,frame,pid=1,uid=1000,ancestry=lambda *a:[doc,frame],role='table',flags=state));self.assertEqual(len(doc.calls),before)
 def test_scoped_reader_builds_without_modifying_frozen_base(self):
  base=reader.base41;raw=Path(base.__file__).read_bytes();namespace=dict(vars(base));guarded,_=reader.scoped_reader()
  self.assertEqual(guarded.__globals__['SCHEMA'],reader.SCHEMA);self.assertEqual(Path(base.__file__).read_bytes(),raw);self.assertEqual(dict(vars(base)),namespace)
 def test_all21_constructors_original_input_guards_and_old49_unchanged(self):
  raw=Path(old.__file__).read_bytes();attributes=dict(vars(old));old_manifest=old.source_manifest(ROOT);previous=old.factory(manifest=old_manifest,source_root=ROOT);manifest=runtime.source_manifest(ROOT);factory=runtime.factory(manifest=manifest,source_root=ROOT);actors=[]
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary)
   for role in manifest['actor_paths']:
    for filename in ('fixture.xlsx','fixture.docx','fixture.pptx'):
     out=root/role/Path(filename).suffix[1:];out.mkdir(mode=0o700,parents=True)
     actor=factory.wrap_owned_guest(SimpleNamespace(sandbox_id='offline-'+role,commands=SimpleNamespace(),files=SimpleNamespace()),root=root,out=out,filename=filename,lease_started_monotonic=time.monotonic());actors.append(actor);self.assertIs(type(actor),factory.actor_class)
  self.assertEqual(len(actors),21)
  for name in ('capture','native_input','envelope','lease_check','dispatch_model'):
   a=getattr(factory.actor_class,name).__code__;b=getattr(previous.actor_class,name).__code__;self.assertEqual(a.co_code,b.co_code);self.assertEqual(a.co_consts,b.co_consts)
  self.assertEqual(Path(old.__file__).read_bytes(),raw);self.assertEqual(dict(vars(old)),attributes);self.assertEqual(old.source_manifest(ROOT),old_manifest)
  self.assertEqual(manifest['native_policy_sha256'],old_manifest['native_policy_sha256']);self.assertEqual(manifest['task_policy'],old_manifest['task_policy']);self.assertFalse(runtime.public_binding(ROOT)['native_qualification_passed'])
  with self.assertRaises(ValueError):factory.require_activation()
if __name__=='__main__':unittest.main()
