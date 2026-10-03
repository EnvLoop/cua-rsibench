"""Offline proof clock boundaries; synthetic fixtures carry no native credit."""
import hashlib, json, math, tempfile, time, unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
from native_desktop_factory import native_editor_capability_v42 as capability
from native_desktop_factory import native_editor_evidence_v45 as old_evidence
from native_desktop_factory import native_editor_evidence_v47 as evidence
from native_desktop_factory import native_editor_runtime_v47 as runtime
from native_desktop_factory import native_guarded_observation_runtime_v46 as old_runtime
ROOT=Path(__file__).resolve().parents[1]

def proof(start,expiry):
 return {'schema':'owned-current-edit-mode-evidence-v42','document_binding_sha256':'a'*64,'observed_at':start,'expires_at':expiry,
  'visible_initial_native_proof':True,'same_native_node_reopened':True,'current_native_state_read':True,'unique_current_command':True,
  'command':'.uno:EditDoc','name':'Edit Mode','parent_menu':'Edit','checked':True,'enabled':True,'sensitive':True,
  'stale':False,'defunct':False,'node_identity_sha256':'b'*64}

class ConservativeExpiry(unittest.TestCase):
 def test_actual_numeric_rounding_boundary_without_relaxing_validator(self):
  start=247.602700332;up=start+10
  self.assertGreater(up-start,10)
  with self.assertRaisesRegex(ValueError,'stale/uncertain clock'):
   capability.checked_edit_mode(proof(start,up),document_binding_sha256='a'*64,now=start+.001)
  down=evidence.bounded_expiry(start)
  self.assertLessEqual(down-start,10);self.assertLess(down,up)
  self.assertTrue(capability.checked_edit_mode(proof(start,down),document_binding_sha256='a'*64,now=start+.001))
 def test_representative_monotonic_magnitudes_never_extend_lifetime(self):
  for start in (0.,.1,1.,31.99999999999999,247.602700332,254.98518291,337968.034159458,1e6,2.**40):
   end=evidence.bounded_expiry(start)
   self.assertGreater(end,start);self.assertLessEqual(end-start,10);self.assertLessEqual(end,start+10)
 def test_expired_future_and_false_mode_still_refused(self):
  start=247.602700332;end=evidence.bounded_expiry(start)
  for current in (start-.001,end,end+.001):
   with self.assertRaisesRegex(ValueError,'stale/uncertain clock'):
    capability.checked_edit_mode(proof(start,end),document_binding_sha256='a'*64,now=current)
  for key,value in [('checked',False),('enabled',False),('sensitive',False),('stale',True),('defunct',True),('same_native_node_reopened',False),('document_binding_sha256','c'*64)]:
   item=proof(start,end);item[key]=value
   with self.assertRaises(ValueError):capability.checked_edit_mode(item,document_binding_sha256='a'*64,now=start+.001)
 def test_nonfinite_clock_not_promoted(self):
  for now in (math.nan,math.inf,-math.inf):
   with self.assertRaises(ValueError):capability.checked_edit_mode(proof(now,evidence.bounded_expiry(now)),document_binding_sha256='a'*64,now=now)
 def test_disabled_readonly_and_foreign_capability_still_refused(self):
  start=247.602700332;flags={k:True for k in capability.FLAGS};flags.update(SENSITIVE=False,STALE=False,DEFUNCT=False)
  editor={'enabled':True,'editable':True,'focused':True,'visible':True,'showing':True,'stale':False,'defunct':False}
  context={'document_binding_sha256':'a'*64,'owned_current_principal':True,'lease_active':True,'strict_current_leaf_hit_proved':True,'same_current_editor':True,'original_file_writable':True,'original_medium_writable':True}
  args=dict(build=capability.BUILD,role='table',raw_flags=flags,editor=editor,edit_mode=proof(start,evidence.bounded_expiry(start)),context=context,now=start+.001)
  self.assertTrue(capability.editor_capability(**args)['effective_input_eligible'])
  for field in ('original_file_writable','original_medium_writable','owned_current_principal','lease_active','strict_current_leaf_hit_proved','same_current_editor'):
   bad={**args,'context':{**context,field:False}}
   with self.assertRaises(ValueError):capability.editor_capability(**bad)
  for field,value in [('ENABLED',False),('EDITABLE',False),('STALE',True),('DEFUNCT',True)]:
   with self.assertRaises(ValueError):capability.editor_capability(**{**args,'raw_flags':{**flags,field:value}})
 def test_all_roles_same_factory_and_original_transport_native_guard(self):
  old_manifest=old_runtime.source_manifest(ROOT);new_manifest=runtime.source_manifest(ROOT)
  old=old_runtime.factory(manifest=old_manifest,source_root=ROOT);new=runtime.factory(manifest=new_manifest,source_root=ROOT)
  self.assertEqual(new_manifest['actor_paths'],old_manifest['actor_paths']);self.assertEqual(len(new_manifest['actor_paths']),7)
  for name in ('capture','envelope','native_input','dispatch_model','lease_check'):
   left=getattr(new.actor_class,name).__code__;right=getattr(old.actor_class,name).__code__
   self.assertEqual(left.co_code,right.co_code);self.assertEqual(left.co_consts,right.co_consts);self.assertEqual(left.co_names,right.co_names)
  self.assertEqual(new_manifest['native_policy_sha256'],old_manifest['native_policy_sha256'])
  self.assertEqual(new_manifest['observation_policy'],old_manifest['observation_policy'])
  self.assertEqual(new_manifest['native_reader_schema'],'cua-native-editor-capability-probe-v47')
  self.assertFalse(runtime.public_binding(ROOT)['native_qualification_passed'])
  with self.assertRaises(ValueError):new.require_activation()
 def test_all_21_owned_offline_constructors_share_uniform_source(self):
  factory=runtime.factory(manifest=runtime.source_manifest(ROOT),source_root=ROOT);actors=[]
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary)
   for role in factory.manifest['actor_paths']:
    for filename in ('fixture.xlsx','fixture.docx','fixture.pptx'):
     out=root/role/Path(filename).suffix[1:];out.mkdir(mode=0o700,parents=True)
     actor=factory.wrap_owned_guest(SimpleNamespace(sandbox_id='offline-no-credit-'+role,commands=SimpleNamespace(),files=SimpleNamespace()),root=root,out=out,filename=filename,lease_started_monotonic=time.monotonic())
     actors.append(actor);self.assertIs(type(actor),factory.actor_class);self.assertEqual(actor.native_manifest,factory.manifest)
  self.assertEqual(len(actors),21)
 def test_actual_initial_and_refresh_producers_use_conservative_expiry_offline(self):
  now=247.602700332;binding='a'*64;x11={'pid':1,'uid':1000};mode={'checked':True};seed={'pipe_name':'offline-no-credit','document_binding_sha256':binding,'visible_initial_native_proof':True,'native_forward_path':[]}
  fake_seed=SimpleNamespace(read_bytes=lambda:json.dumps(seed).encode())
  with patch.dict(evidence.evidence.__globals__,SEED=fake_seed,current_mode_path=lambda *a:(mode,binding,x11),medium_metadata=lambda *a:{'original_medium_writable':True},actual_build=lambda *a:capability.BUILD,time=SimpleNamespace(monotonic=lambda:now)):
   current=evidence.evidence('offline.xlsx')
  self.assertIsInstance(current,evidence.CurrentEvidence);self.assertLessEqual(current['mode']['expires_at']-current['mode']['observed_at'],10)
  states=SimpleNamespace(contains=lambda key:key in ('checked','enabled','sensitive'))
  node=SimpleNamespace(clear_cache=lambda:None,get_state_set=lambda:states,get_process_id=lambda:1)
  current.hooks={'window':object(),'identity':object(),'Atspi':SimpleNamespace(StateType=SimpleNamespace(CHECKED='checked',ENABLED='enabled',SENSITIVE='sensitive',STALE='stale',DEFUNCT='defunct'))}
  with patch.dict(evidence.CurrentEvidence.refresh.__globals__,reopen_mode_path=lambda *a:(node,[]),medium_metadata=lambda *a:{'original_medium_writable':True},time=SimpleNamespace(monotonic=lambda:now)):
   self.assertIs(current.refresh(),current)
  self.assertTrue(current['mode']['checked']);self.assertFalse(current['mode']['stale']);self.assertLessEqual(current['mode']['expires_at']-now,10)
 def test_old_sources_and_evidence_globals_unchanged(self):
  names=('native_editor_evidence_v45.py','native_editor_reader_v45.py','native_editor_runtime_v45.py','native_guarded_observation_runtime_v46.py','native_editor_capability_v42.py')
  before={n:hashlib.sha256((ROOT/'native_desktop_factory'/n).read_bytes()).hexdigest() for n in names}
  refresh=old_evidence.CurrentEvidence.refresh;namespace=dict(refresh.__globals__)
  runtime.factory(manifest=runtime.source_manifest(ROOT),source_root=ROOT)
  self.assertIs(old_evidence.CurrentEvidence.refresh,refresh);self.assertEqual(refresh.__globals__,namespace)
  self.assertEqual(before,{n:hashlib.sha256((ROOT/'native_desktop_factory'/n).read_bytes()).hexdigest() for n in names})

if __name__=='__main__':unittest.main()
