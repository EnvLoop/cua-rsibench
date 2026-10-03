"""Offline captured-shape Writer boundaries; no native qualification credit."""
import tempfile,time,unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from native_desktop_factory import native_writer_pointer_capability_v49 as capability
from native_desktop_factory import native_editor_reader_v49 as reader
from native_desktop_factory import native_editor_runtime_v49 as runtime
from native_desktop_factory import native_editor_runtime_v48 as old
from native_desktop_factory import native_editor_capability_v42 as base
ROOT=Path(__file__).resolve().parents[1]

def flags(focused=False,sensitive=False):
 return {'ENABLED':True,'EDITABLE':True,'VISIBLE':True,'SHOWING':True,'SENSITIVE':sensitive,'FOCUSED':focused,'STALE':False,'DEFUNCT':False}
def mode():
 return {'schema':'owned-current-edit-mode-evidence-v42','document_binding_sha256':'a'*64,'observed_at':1.,'expires_at':10.9,'visible_initial_native_proof':True,'same_native_node_reopened':True,'current_native_state_read':True,'unique_current_command':True,'command':'.uno:EditDoc','name':'Edit Mode','parent_menu':'Edit','checked':True,'enabled':True,'sensitive':True,'stale':False,'defunct':False,'node_identity_sha256':'b'*64}
def args():
 f=flags();return dict(build=base.BUILD,role='paragraph',raw_flags=f,ancestors=[('paragraph',f),('document text',f),('frame',{**flags(True,True),'EDITABLE':False})],mode=mode(),context={'document_binding_sha256':'a'*64,**{k:True for k in ('owned_current_principal','same_current_writer_document','strict_zero_child_leaf','original_strict_point_hit_proved','unobscured','original_file_writable','original_medium_writable')}},now=2.)
class WriterPointer(unittest.TestCase):
 def test_exact_captured_shape_pointer_does_not_assert_sensitive_or_focus(self):
  a=args();snapshot=deepcopy(a);v=capability.writer_capability(**a)
  self.assertTrue(v['effective_pointer_eligible']);self.assertFalse(v['effective_keyboard_eligible']);self.assertFalse(v['raw_sensitive_value']);self.assertFalse(v['native_focused_override']);self.assertEqual(a,snapshot)
  self.assertTrue(v['actual_lease_required_by_unchanged_native_dispatch_guard'])
 def test_only_actual_focused_flag_permits_keyboard_eligibility(self):
  a=args();a['raw_flags']['FOCUSED']=True;self.assertTrue(capability.writer_capability(**a)['effective_keyboard_eligible'])
 def test_every_missing_current_leaf_principal_medium_gate_refuses(self):
  for key,value in args()['context'].items():
   if value is True:
    a=args();a['context'][key]=False
    with self.assertRaises(ValueError):capability.writer_capability(**a)
 def test_unknown_role_build_and_insensitive_ancestor_refuse(self):
  for change in ({'role':'text'},{'build':{}},{'ancestors':[('paragraph',flags()),('frame',flags())]}):
   with self.assertRaises(ValueError):capability.writer_capability(**{**args(),**change})
  a=args();a['ancestors'].insert(1,('unknown',flags()))
  with self.assertRaises(ValueError):capability.writer_capability(**a)
 def test_disabled_protected_stale_readonly_foreign_proofs_refuse(self):
  for key,value in [('ENABLED',False),('EDITABLE',False),('STALE',True),('DEFUNCT',True)]:
   a=args();a['raw_flags'][key]=value
   with self.assertRaises(ValueError):capability.writer_capability(**a)
  for key,value in [('checked',False),('document_binding_sha256','c'*64),('expires_at',1.5),('same_native_node_reopened',False)]:
   a=args();a['mode'][key]=value
   with self.assertRaises(ValueError):capability.writer_capability(**a)
 def test_actual_record_delegate_once_and_foreign_nonleaf_record_preserved(self):
  class Evidence(dict):
   filename='fixture.docx';x11={'wm_class':'libreoffice-writer'}
   def refresh(self):return self
  f=flags();record={'enabled':False,'keyboard':False,'obscured':False};fact={'role':'paragraph','native_flags':f,'point_hit_ownership_checked':True}
  evidence=Evidence(build=base.BUILD,mode=mode(),binding='a'*64,native_pid=10,native_uid=1000,medium={'original_file_writable':True,'original_medium_writable':True})
  paragraph=SimpleNamespace(get_role_name=lambda:'paragraph',get_child_count=lambda:0);document=SimpleNamespace(get_role_name=lambda:'document text');frame=SimpleNamespace(get_role_name=lambda:'frame')
  chain=[paragraph,document,frame];state=lambda A,n:{**f,'SENSITIVE':True,'EDITABLE':False} if n is frame else f
  subject=SimpleNamespace(_v42_evidence=evidence,state_flags=state)
  with patch.object(reader.old.original,'compatible_record',return_value=(record,fact)) as delegated,patch.object(reader.time,'monotonic',return_value=2.):
   v,proof=reader.compatible_record(subject,None,paragraph,frame,pid=10,uid=1000,viewport=[1280,800],ancestry=lambda *a:chain)
   self.assertEqual(delegated.call_count,1);self.assertTrue(v['enabled']);self.assertFalse(v['keyboard']);self.assertFalse(proof['native_flags']['SENSITIVE'])
   v,_=reader.compatible_record(subject,None,paragraph,frame,pid=99,uid=1000,viewport=[1280,800],ancestry=lambda *a:chain);self.assertIs(v,record)
   paragraph.get_child_count=lambda:1
   v,_=reader.compatible_record(subject,None,paragraph,frame,pid=10,uid=1000,viewport=[1280,800],ancestry=lambda *a:chain);self.assertIs(v,record)
 def test_all_21_constructors_guard_executables_and_old48_unchanged(self):
  snapshot=(Path(old.__file__).read_bytes(),dict(vars(old)));old_manifest=old.source_manifest(ROOT);previous=old.factory(manifest=old_manifest,source_root=ROOT);manifest=runtime.source_manifest(ROOT);factory=runtime.factory(manifest=manifest,source_root=ROOT);actors=[]
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary)
   for role in manifest['actor_paths']:
    for filename in ('fixture.xlsx','fixture.docx','fixture.pptx'):
     out=root/role/Path(filename).suffix[1:];out.mkdir(mode=0o700,parents=True)
     actor=factory.wrap_owned_guest(SimpleNamespace(sandbox_id='offline-'+role,commands=SimpleNamespace(),files=SimpleNamespace()),root=root,out=out,filename=filename,lease_started_monotonic=time.monotonic());actors.append(actor);self.assertIs(type(actor),factory.actor_class)
  self.assertEqual(len(actors),21)
  for name in ('capture','native_input','envelope','lease_check','dispatch_model'):
   a=getattr(factory.actor_class,name).__code__;b=getattr(previous.actor_class,name).__code__;self.assertEqual(a.co_code,b.co_code);self.assertEqual(a.co_consts,b.co_consts)
  self.assertEqual(Path(old.__file__).read_bytes(),snapshot[0]);self.assertEqual(dict(vars(old)),snapshot[1]);self.assertEqual(old.source_manifest(ROOT),old_manifest)
  self.assertEqual(manifest['native_policy_sha256'],old_manifest['native_policy_sha256']);self.assertEqual(manifest['task_policy'],{'max_actions':90,'actor_seconds':720,'lease_seconds':1200});self.assertFalse(runtime.public_binding(ROOT)['native_qualification_passed'])
  with self.assertRaises(ValueError):factory.require_activation()
if __name__=='__main__':unittest.main()
