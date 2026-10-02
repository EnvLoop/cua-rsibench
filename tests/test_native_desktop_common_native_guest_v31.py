"""Actual additive setup/episode call paths with offline synthetic providers."""
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from native_desktop_factory import common_native_guest_v31 as native
from native_desktop_factory import common_native_episode_v31 as engine
from native_desktop_factory.factory import digest
from tests.test_native_desktop_uniform_model_transport_v11 import FakeModelGuest,FakeSampler
from tests.test_native_desktop_selection_worker_v066 import source_case

class CommonGuestTests(unittest.TestCase):
 def test_bootstrap_precedes_original_prepare_and_actual_child_env_for_all_seven_paths(self):
  manifest=native.source_manifest()
  for actor_path in native.ACTOR_PATHS:
   with self.subTest(actor_path=actor_path),tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);root.chmod(0o700);out=root/'fixture'/'actor';out.mkdir(parents=True,mode=0o700);events=[];files={}
    bootstrap={'status':'official_typelib_installed_offline','task_files_modified':False,'gui_configuration_changed':False}
    native_value={'schema':native.PROBE_SCHEMA,'status':'observed','probe_source_sha256':digest(native.PROBE_SOURCE.read_bytes()),'native_mutations':0,'raster_equality_used':False,'recursive_collection_query_called':False,'focus_from_selection':False}
    def command(cmd,**bounds):
     events.append((cmd,bounds))
     if cmd.startswith('mkdir '):return SimpleNamespace(exit_code=0,stdout='',stderr='')
     if cmd.endswith(' namespace'):return SimpleNamespace(exit_code=0,stdout=json.dumps({'namespace_available':True,'native_tree_qualified':False}),stderr='')
     if ' apply ' in cmd:
      files[native.bootstrap.PREFIX+'/result.private.json']=json.dumps(bootstrap).encode();files[native.bootstrap.PREFIX+'/Atspi-2.0.typelib']=files[native.REMOTE+'/Atspi-2.0.typelib']
     return SimpleNamespace(exit_code=0,stdout=json.dumps(native_value if ' --filename ' in cmd else bootstrap),stderr='')
    sandbox=SimpleNamespace(sandbox_id='offline-owned-'+actor_path,files=SimpleNamespace(write=lambda name,data:files.__setitem__(name,data),read=lambda name,**kwargs:files[name]),commands=SimpleNamespace(run=command))
    factory=native.CommonGuestFactory(manifest=manifest);actor=factory.wrap_owned_guest(sandbox,root=root,out=out,filename='fixture.xlsx',lease_started_monotonic=time.monotonic())
    def original_prepare(self,**kwargs):
     events.append(('original-prepare',{}));native.exclusive(self.out/'guest-probe-command-v16.private.json',json.dumps({'stdout':json.dumps({'content_tree_sha256':'a'*64})}).encode());self.native_probe('prepared');self.receipt={'original_prepare_called':True}
    with patch.object(native.previous.SemanticModelGuest,'prepare',original_prepare):actor.prepare(source=b'actual-fixture',guest_reference={},profile_reference=root/'profile')
    commands=[r[0] for r in events];self.assertLess(next(i for i,c in enumerate(commands) if ' apply ' in c),commands.index('original-prepare'))
    self.assertLess(next(i for i,c in enumerate(commands) if c.endswith(' namespace')),commands.index('original-prepare'))
    probe=next(r for r in events if ' --filename ' in r[0]);self.assertTrue(probe[0].startswith('GI_TYPELIB_PATH=/tmp/envloop-atspi-v25 '));self.assertEqual(probe[1],{'timeout':45,'request_timeout':55})
    epoch=json.loads((out/'native-supplemental-epoch.private.json').read_bytes());self.assertEqual(epoch['base_content_tree_sha256'],'a'*64);self.assertEqual(epoch['source_manifest_sha256'],digest(native.canonical(manifest)));self.assertFalse(epoch['native_tree_qualified']);self.assertEqual(actor.receipt['native_common_actor_paths'],list(native.ACTOR_PATHS))
 def test_unqualified_factory_worker_teacher_and_runtime_fail_before_provider(self):
  factory=native.CommonGuestFactory(manifest=native.source_manifest());self.assertIsNone(factory.qualification)
  with self.assertRaisesRegex(ValueError,'qualification'):factory.create_guest(root=Path('/unused'),out=Path('/unused'),filename='fixture.xlsx')
  with self.assertRaisesRegex(ValueError,'qualification'):
   with native.runtime_context(factory):self.fail('Unqualified context must not enter')
  worker=engine.DesktopCommonNativeWorker(study=None,admissions_path=Path('/unused'),proposal_path=Path('/unused'),native_factory=factory)
  with self.assertRaisesRegex(ValueError,'qualification'):worker._gate()
  self.assertIs(engine.DesktopCommonNativeWorker._create.__globals__['transport'],native);self.assertIs(engine.DesktopCommonNativeWorker._episode.__globals__['transport'],native);self.assertIs(engine.CommonNativeTeacherEpisode._episode,engine.DesktopCommonNativeWorker._episode)
 def test_early_bootstrap_failure_cannot_open_task_or_query_native_focus(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);out=root/'fixture'/'actor';out.mkdir(parents=True);calls=[]
   sandbox=SimpleNamespace(sandbox_id='offline-failed',commands=SimpleNamespace(run=lambda *a,**kw:SimpleNamespace(exit_code=1,stdout='',stderr='fixed failure')),files=SimpleNamespace(write=lambda *a:calls.append(a)))
   actor=native.CommonGuestFactory(manifest=native.source_manifest()).wrap_owned_guest(sandbox,root=root,out=out,filename='fixture.xlsx',lease_started_monotonic=time.monotonic())
   with patch.object(native.previous.SemanticModelGuest,'prepare',side_effect=AssertionError('Task must remain unopened')):
    with self.assertRaisesRegex(ValueError,'setup command'):actor.prepare(source=b'original',guest_reference={},profile_reference=root/'profile')
   self.assertEqual(calls,[]);self.assertFalse(actor.bootstrap_completed)
 def test_actual_current_episode_keeps_saved_scorer_and_distinct_reset_for_all_five_slots(self):
  source,_,positive,oracle,ext=source_case('calc-growth');factory=native.CommonGuestFactory(manifest=native.source_manifest())
  for owner in ['shared-base','astra','sol56','sol6','luna6']:
   with self.subTest(owner=owner),tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);root.chmod(0o700);reference=root/'guest.json';reference.write_text('{}');mapping=root/'map.json';engine.current.write(mapping,{'variant_salt':'offline-only-'*4})
    identity={'task_id':'fixture','package_sha256':'a'*64};package={'identity':identity,'source':source,'oracle':oracle,'filename':'train'+ext,'instruction':'Visible fixture task','guest_reference_path':str(reference)};admitted={'guest_public':str(reference),'scoped_reference':str(root/'profile'),'private_map':str(mapping)};made=[]
    class Model(engine.DesktopCommonNativeWorker):
     def _create(self,**kwargs):
      out=kwargs['gui_root']/identity['task_id']/kwargs['phase'];out.mkdir(parents=True,mode=0o700);guest=FakeModelGuest(kwargs['gui_root'],out,package['filename'],source,positive,kwargs['phase'],identity);made.append(guest);return guest
     def _audit_episode(self,**kwargs):pass
    class Paid:
     attempt_id='offline-'+owner
     def invoke(self,**kwargs):
      result=kwargs['provider'](kwargs['request']);return result,digest(engine.current.integration.canonical(result)),'actual-fixture-'+kwargs['suffix']
    model=Model(study=None,admissions_path=Path('/unused'),proposal_path=Path('/unused'),native_factory=factory)
    result,out,trace,elapsed,outcome=model._episode(admitted=admitted,package=package,ordinal=0,batch=root,paid=Paid(),sampler=FakeSampler())
    self.assertEqual(result['score'],1);self.assertEqual(outcome,'finished');self.assertEqual(len(made),2);self.assertTrue(all(g.killed for g in made));self.assertNotEqual(made[0].sandbox.sandbox_id,made[1].sandbox.sandbox_id)
    reset=json.loads((out/'reset.private.json').read_bytes());self.assertEqual(reset['initial_state_sha256'],digest(source));self.assertEqual(reset['restored_state_sha256'],digest(source))

import tests.test_native_desktop_semantic_native_transport_v23 as semantic_fixtures
class CommonNativeDispatchTests(semantic_fixtures.SemanticTests):
 def setUp(self):
  super().setUp();self.actor.__class__=native.CommonNativeModelGuest;self.actor.bootstrap_completed=True;self.actor.requested_points=[];self.actor.last_native_point=None;self.actor.native_manifest_sha256='f'*64;self.actor.source_root=Path(__file__).resolve().parents[1];self.actor.native_manifest=native.source_manifest()
  self.meta.update(schema=native.PROBE_SCHEMA,probe_source_sha256=digest(native.PROBE_SOURCE.read_bytes()),recursive_collection_query_called=False,focus_from_selection=False,actual_native_focus_proof=True)
 def test_actual_model_point_is_in_native_predispatch_query_without_retarget(self):
  obs=self.observation();_,evidence=self.actor.dispatch_model('{"type":"click","target":{"x":40,"y":40}}',obs,actor_deadline=time.monotonic()+720)
  self.assertEqual(evidence['native_status'],'applied');self.assertEqual(self.native_calls,[('click',(40,40))]);self.assertEqual(self.actor.last_native_point,[40,40])
  receipts=[json.loads(p.read_bytes()) for p in self.out.glob('native-probe-*.private.json')];self.assertTrue(any(r['phase']=='predispatch-before' for r in receipts));self.assertEqual(self.actor.requested_points,[])
 def test_declared_editable_focus_without_native_focused_proof_is_refused(self):
  self.meta['actual_native_focus_proof']=False
  with self.assertRaisesRegex(ValueError,'focused object proof'):self.observation()
  self.assertEqual(self.native_calls,[])

 def test_saved_actual_deprecation_warning_is_retained_with_successful_typed_native_output(self):
  from tests.test_native_desktop_atspi_warning_policy_v32 import ACTUAL_WARNING
  self.sandbox.commands.run=lambda *args,**kwargs:SimpleNamespace(exit_code=0,stdout=json.dumps(self.meta),stderr=ACTUAL_WARNING)
  self.observation()
  commands=[json.loads(p.read_bytes()) for p in self.out.glob('native-probe-*.private.json')]
  self.assertTrue(commands);self.assertTrue(all(r['stderr']==ACTUAL_WARNING for r in commands))
  classifications=[json.loads(p.read_bytes()) for p in self.out.glob('native-stderr-*.private.json')]
  self.assertTrue(all(r['status']=='known_atspi_getter_deprecations' and not r['native_success_inferred'] for r in classifications));self.assertEqual(self.native_calls,[])
 def test_known_warning_cannot_promote_failed_native_output_or_unrelated_stderr(self):
  from tests.test_native_desktop_atspi_warning_policy_v32 import ACTUAL_WARNING
  self.meta['status']='unavailable_or_unsafe';self.sandbox.commands.run=lambda *args,**kwargs:SimpleNamespace(exit_code=0,stdout=json.dumps(self.meta),stderr=ACTUAL_WARNING)
  with self.assertRaisesRegex(ValueError,'metadata unavailable'):self.observation()
  self.meta['status']='observed';self.sandbox.commands.run=lambda *args,**kwargs:SimpleNamespace(exit_code=0,stdout=json.dumps(self.meta),stderr=ACTUAL_WARNING+'RuntimeError: unknown native failure\n')
  with self.assertRaisesRegex(ValueError,'stderr'):self.observation()
  self.assertEqual(self.native_calls,[])

class CreationBoundaryTests(unittest.TestCase):
 def test_actual_creation_journals_raw_handle_before_wrapper_and_closes_once_on_constructor_failure(self):
  import sys
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);out=root/'fixture'/'actor';out.mkdir(parents=True);calls=[]
   raw=SimpleNamespace(files=SimpleNamespace(),commands=SimpleNamespace(),sandbox_id='synthetic-private-raw',kill=lambda:calls.append('kill') or True,is_running=lambda **kwargs:calls.append('status') or False)
   factory=native.CommonGuestFactory(manifest=native.source_manifest())
   def wrap(*args,**kwargs):
    journal=json.loads((out/'native-raw-created-v31.private.json').read_bytes());self.assertEqual(journal['sandbox_id'],raw.sandbox_id);calls.append('wrapper');raise RuntimeError('synthetic constructor error')
   def create(**kwargs):calls.append('create');self.assertEqual(kwargs['timeout'],1200);return raw
   with patch.object(factory,'require_activation',return_value={'offline_fixture_only':True}),patch.object(factory,'wrap_owned_guest',side_effect=wrap),patch.dict(sys.modules,{'e2b_desktop':SimpleNamespace(Sandbox=SimpleNamespace(create=create))}),patch('native_desktop_factory.reconcile_interrupted_sweep.active_hashes',return_value=([],0)):
    with self.assertRaisesRegex(RuntimeError,'synthetic constructor'):factory.create_guest(root=root,out=out,filename='fixture.xlsx')
   self.assertEqual(calls,['create','wrapper','kill','status']);cleanup=json.loads((out/'native-constructor-cleanup-v31.private.json').read_bytes());self.assertTrue(cleanup['kill_acknowledged']);self.assertFalse(cleanup['sandbox_running_after_kill']);self.assertEqual(cleanup['automatic_retries'],0)
 def test_consumed_intent_and_invalid_filename_refuse_before_actual_create(self):
  import sys
  for name in ['../unowned.xlsx','fixture.xlsx']:
   with self.subTest(name=name),tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);out=root/'fixture'/'actor';out.mkdir(parents=True);calls=[];native.exclusive(out/'native-create-intent-v31.private.json',b'prior immutable intent');factory=native.CommonGuestFactory(manifest=native.source_manifest())
    with patch.object(factory,'require_activation',return_value={'offline_fixture_only':True}),patch.dict(sys.modules,{'e2b_desktop':SimpleNamespace(Sandbox=SimpleNamespace(create=lambda **kwargs:calls.append('create')))}),patch('native_desktop_factory.reconcile_interrupted_sweep.active_hashes',return_value=([],0)):
     with self.assertRaises((ValueError,FileExistsError)):factory.create_guest(root=root,out=out,filename=name)
    self.assertEqual(calls,[]);self.assertEqual((out/'native-create-intent-v31.private.json').read_bytes(),b'prior immutable intent')

if __name__=='__main__':unittest.main()
