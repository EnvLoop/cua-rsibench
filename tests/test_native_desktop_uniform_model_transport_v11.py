"""Offline real-path parity/refusal tests; fake providers cannot admit a study."""
from __future__ import annotations
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from cursibench import full_study_campaign_dispatch_v1 as campaign
from cursibench import full_study_final_dispatch_v1 as final
from cursibench import full_study_shared_base_execution_v1 as base_execution
from cursibench import full_study_selection_paid_coverage_v1 as coverage
from cursibench import scale_action_output_v066 as output
from cursibench import scale_vision_proxy as vision
from cursibench.scale_action_contract import ContractLimits,make_observation
from native_desktop_factory import model_transport_integration_v11 as integration
from native_desktop_factory import prospective_model_worker_v11 as worker
from native_desktop_factory import uniform_model_transport_v11 as transport
from native_desktop_factory.factory import digest
from native_desktop_factory.v066_storage_budget import reserve_and_write
from tests.test_native_desktop_post_enter_train_probe_v1 import Guest,png
from tests.test_native_desktop_selection_worker_v066 import source_case


class FakeSampler:
 def __init__(self,**kwargs):self.backend=SimpleNamespace(identity={'sampling_kind':'base'});self.closed=[]
 def start(self,**kwargs):
  self.backend.identity['sampling_kind']='checkpoint' if kwargs['checkpoint_path'] else 'base'
  return {'status':'ready','checkpoint_path_sha256':kwargs['checkpoint_sha256']}
 def sample(self,**kwargs):
  step=kwargs['observation'].step
  return {'status':'completed','new_dispatch':True,'reused':False,'reported_model':vision.MODEL,
   'text':'{"type":"click","target":{"x":500,"y":400}}' if step==0 else '{"type":"finish"}',
   'usage':{'input_tokens':100,'image_tokens':12,'output_tokens':8},'elapsed_seconds':0}
 def close(self,success):self.closed.append(success)


class FakeModelGuest:
 def __init__(self,root,out,filename,source,positive,phase,identity):
  self.root=root;self.out=out;self.filename=filename;self.source=source;self.positive=positive;self.phase=phase
  self.sandbox=SimpleNamespace(sandbox_id='offline-'+identity['task_id']+'-'+phase,screenshot=lambda:png('white'),
                               get_current_window_id=lambda:'native',get_window_title=lambda _:filename)
  self.proxy=SimpleNamespace(enter_count=0);self.killed=False;self.clicked=False
  self.receipt={'sandbox_id_sha256':digest(self.sandbox.sandbox_id.encode()),'profile_application_kind':'calc'}
 def prepare(self,**kwargs):pass
 def observe(self,*,identity,instruction,step,previous=None,memory=''):
  from tests.test_desktop_focus_readiness_v12 import Clock
  clock=Clock();original=transport.readiness.passive_samples
  with transport.evidence_scope(self.root,self.out),patch.object(transport.readiness,'passive_samples',
       lambda sandbox,**kwargs:original(sandbox,clock=clock.clock,sleep=clock.sleep,**kwargs)):
   return transport.readiness.observe(self.sandbox,task_id=identity['task_id'],task_binding_sha256=identity['package_sha256'],instruction=instruction,
    step=step,previous_action_result=previous,memory=memory,max_actions=90)
 def dispatch_model(self,raw,observation,**kwargs):
  action=output.normalize_model_action(raw,observation,current_frame_id=observation.frame_id)
  observed=reserve_and_write(self.root,self.out/f'frame-{observation.step:02d}-0.png',observation.screenshot_bytes)
  pre=reserve_and_write(self.root,self.out/f'predispatch-{observation.step}.png',observation.screenshot_bytes)
  self.clicked|=action['type']=='click'
  if transport.readiness.needs_readiness(action):self.sandbox._v12_focus_pending=True
  return action,{'observation':observed,'predispatch':pre,'caret_resamples':[],
   'frame_id_sha256':digest(observation.frame_id.encode()),'action_type':action['type']}
 def read_saved(self):return self.positive if self.phase=='actor' and self.clicked else self.source
 def persist(self):
  (self.out/'guest.private.json').write_text(json.dumps(self.receipt));(self.out/'guest.private.json').chmod(0o600)
 def close(self):
  self.killed=True;self.receipt.update({'kill_returned':True,'is_running_after_kill':False});self.persist();return True


def fake_session(study,identities,checkpoint,path,base):
 cls=base_execution.SharedBaseSession if base else campaign.CampaignSession
 session=object.__new__(cls);session.study=study;session.calls=[]
 session.intent={'cell_id':'desktop-native','researcher_id':'shared-base' if base else 'astra'}
 attempt='base-selection-desktop-native' if base else 'offline-selection'
 session.started={'attempt_id':attempt,'checkpoint_path_sha256':checkpoint,'selection_tasks':identities,
                  'selection_identities_sha256':digest(integration.canonical(identities)),'task_count':20}
 session._check_time=lambda:None
 session._events=lambda kind:[{'data':{'attempt_id':attempt,'checkpoint_path_sha256':checkpoint}}]
 session._checkpoint_result=lambda event:{'sampler_path':path}
 def dispatch(**kwargs):
  result=kwargs['provider'](kwargs['request'])
  session.calls.append({'attempt_id':kwargs['attempt_id'],'category':kwargs['category'],'request':kwargs['request'],
                        'result_present':True,'result_status':result['status']})
  return {'result':result,'result_sha256':digest(integration.canonical(result))}
 session.dispatch_paid=dispatch
 session._selection_result=lambda result,**kwargs:{r['task_id']:r['score'] for r in result['tasks']}
 session._selection_paid_coverage=lambda **kwargs:coverage.validate(cell_id='desktop-native',attempt_id=attempt,
  checkpoint_sha256=checkpoint,selection_tasks=identities,selection_identities_sha256=session.started['selection_identities_sha256'],
  paid_calls=session.calls,related_paid_attempt_ids=set(kwargs['paid_attempt_ids']))
 return session


class TransportTests(unittest.TestCase):
 def test_target_error_and_preservation_error_are_reported_separately(self):
  self.assertTrue(worker.no_regression_passed({'errors':['target_formula_wrong:Review!B4']}))
  self.assertTrue(worker.no_regression_passed({'errors':[]}))
  self.assertFalse(worker.no_regression_passed({'errors':['target_missing:Review!B4']}))
  self.assertFalse(worker.no_regression_passed({'errors':['non_target_changed:Evidence!A2']}))

 def test_actual_model_observation_uses_unmasked_v12_focus_readiness_for_each_slot(self):
  from tests.test_desktop_focus_readiness_v12 import Native,Clock,png as readiness_png
  a,b=readiness_png(),readiness_png(tooltip=True)
  for owner in ['shared-base',*integration.matrix.RESEARCHERS]:
   with self.subTest(owner=owner),TemporaryDirectory() as directory:
    root=Path(directory);out=root/'fixture'/'actor';out.mkdir(parents=True)
    guest=Native([a,a,a,a,b,b,b,b,b]);model=transport.ModelGuest(guest,root=root,out=out,filename='train.xlsx')
    clock=Clock();original=transport.readiness.passive_samples
    identity={'task_id':'fixture','package_sha256':'a'*64}
    first=model.observe(identity=identity,instruction='visible task',step=0)
    model.dispatch_model('{"type":"click","target":{"x":52,"y":170}}',first,actor_deadline=10**12)
    with patch.object(transport.readiness,'passive_samples',lambda sb,**kwargs:
       original(sb,clock=clock.clock,sleep=clock.sleep,**kwargs)):
     next_frame=model.observe(identity=identity,instruction='visible task',step=1,previous={'status':'applied','code':'ok'})
    self.assertEqual(next_frame.screenshot_bytes,b)
    self.assertEqual(guest.inputs,[('click',52,170)])
    self.assertEqual(len((out/'pre-observation-readiness-v12.ndjson').read_text().splitlines()),7)

 def test_source_proposal_has_all_five_owners_one_policy_and_unchanged_control_sources(self):
  p=integration.proposal()
  self.assertEqual(p['configuration_owners'],['shared-base','astra','sol56','sol6','luna6'])
  self.assertEqual((p['max_actor_actions'],p['max_actor_wall_seconds'],p['lease_seconds_each']),(90,720,1200))
  self.assertEqual(p['required_new_control_trios'],120);self.assertFalse(p['dispatch_enabled'])
  for name,sha in integration.controls.source_hashes().items():self.assertEqual(p['source_sha256s'][name],sha)

 def test_disabled_worker_entries_reject_before_private_read_or_provider_import(self):
  w=worker.DesktopProspectiveModelWorker(study=None,admissions_path=Path('/absent'),proposal_path=Path('/absent'))
  with patch.object(integration,'bind_frozen_study',side_effect=AssertionError('private read')):
   for callback in [lambda:w.run_once({},Path('/absent')),
     lambda:w.run_selection(session=None,started={},checkpoint_path='opaque',out_dir=Path('/absent')),
     lambda:w.run_base_selection(session=SimpleNamespace(started={}),out_dir=Path('/absent'))]:
    with self.assertRaisesRegex(ValueError,'disabled'):callback()

 def test_real_sampler_uses_existing_clean_vision_backend_for_base_and_all_four_checkpoints(self):
  for owner in ['shared-base',*integration.matrix.RESEARCHERS]:
   path=None if owner=='shared-base' else 'tinker://offline/sampler_weights/'+owner
   checkpoint=vision.digest(vision.MODEL) if path is None else digest(path.encode())
   renderer=SimpleNamespace(identity={'model':vision.MODEL,'renderer':vision.RENDERER,'image_processor':vision.PROCESSOR})
   backend=SimpleNamespace(identity={**renderer.identity,'checkpoint_sha256':vision.digest(path or vision.MODEL),
      'sampling_kind':'checkpoint' if path else 'base'})
   service=Mock();client=Mock();client.get_base_model.return_value=vision.MODEL
   service.create_sampling_client.return_value=client
   with patch.dict('sys.modules',{'tinker':SimpleNamespace(ServiceClient=Mock(return_value=service)),
        'tinker.lib.retry_handler':SimpleNamespace(RetryConfig=lambda **kwargs:SimpleNamespace(**kwargs))}),\
        patch.object(vision.QwenVisionRenderer,'load',return_value=renderer),\
        patch.object(vision,'TinkerVisionBackend',return_value=backend) as connect:
    sampler=transport.CleanRuntimeSampler();sampler.start(checkpoint_path=path,checkpoint_sha256=checkpoint,seed=23,max_output_tokens=128,attempt_id='offline')
    connect.assert_called_once_with(client,renderer,checkpoint=path,seed=23)
    self.assertFalse(service.create_sampling_client.call_args.kwargs['retry_config'].enable_retry_logic)
    self.assertEqual(sampler.checkpoint_sha256,checkpoint)

 def test_actual_model_enter_dispatch_uses_five_neutral_samples_and_new_next_observation(self):
  for owner in ['shared-base',*integration.matrix.RESEARCHERS]:
   with self.subTest(owner=owner),TemporaryDirectory() as directory:
    root=Path(directory);out=root/'fixture'/'actor';out.mkdir(parents=True)
    guest=Guest([png('white')]*10);model=transport.ModelGuest(guest,root=root,out=out,filename='train.xlsx')
    clock=[0]
    def now():clock[0]+=1_000_000;return clock[0]
    def sleep(seconds):clock[0]+=int(seconds*1e9)
    model.proxy.clock=now;model.proxy.sleep=sleep
    identity={'task_id':'fixture','package_sha256':'a'*64}
    first=model.observe(identity=identity,instruction='visible task',step=0)
    action,evidence=model.dispatch_model('{"type":"key","key":"Enter"}',first,actor_deadline=10**12)
    next_frame=model.observe(identity=identity,instruction='visible task',step=1,previous={'status':'applied','code':'ok'})
    self.assertEqual(guest.actions,['enter']);self.assertEqual(model.proxy.enter_count,1)
    self.assertNotEqual(first.frame_id,next_frame.frame_id)
    self.assertEqual(len((out/'post-enter-samples.ndjson').read_text().splitlines()),5)

 def test_actual_model_enter_stops_modal_and_material_oscillation_without_next_action(self):
  a,b=png('white'),png('blue')
  for frames,titles in [([a,a,a,b,a,b,b],None),([a]*7,['train.xlsx - LibreOffice Calc']*3+['Save']*20)]:
   with TemporaryDirectory() as directory:
    root=Path(directory);out=root/'fixture'/'actor';out.mkdir(parents=True)
    guest=Guest(frames,titles=titles);model=transport.ModelGuest(guest,root=root,out=out,filename='train.xlsx')
    clock=[0]
    def now():clock[0]+=1_000_000;return clock[0]
    def sleep(seconds):clock[0]+=int(seconds*1e9)
    model.proxy.clock=now;model.proxy.sleep=sleep
    frame=model.observe(identity={'task_id':'fixture','package_sha256':'a'*64},instruction='visible task',step=0)
    with self.assertRaises(ValueError):model.dispatch_model('{"type":"key","key":"Enter"}',frame,actor_deadline=10**12)
    self.assertEqual(guest.actions,['enter'])

 def test_control_admissions_incomplete_stop_precedes_any_gold_audit(self):
  with TemporaryDirectory() as directory:
   root=Path(directory);proposal=root/'proposal.json';proposal.write_text('{}')
   with patch.object(integration,'proposal',return_value={}),\
        patch.object(integration.controls,'validate',return_value={'attempts_root':str(root/'not-run')}),\
        patch.object(integration.control_audit,'audit_trio',side_effect=AssertionError('gold opened')):
    with self.assertRaisesRegex(ValueError,'all120_terminal'):integration.prepare_admissions(control_freeze=root/'freeze',proposal_path=proposal,
        output=root/'admissions',enable_control_audit=True)

 def test_fake_six_cell_object_cannot_bind_live_worker(self):
  with patch.object(integration,'checked_admissions',side_effect=AssertionError('private read')):
   with self.assertRaisesRegex(ValueError,'real_six_cell'):integration.bind_frozen_study(SimpleNamespace(),admissions_path=Path('/absent'),proposal_path=Path('/absent'))

 def test_final_requires_actual_post_campaign_gate_before_final_package(self):
  w=worker.DesktopProspectiveModelWorker(study=None,admissions_path=Path('/absent'),proposal_path=Path('/absent'))
  with patch.object(w,'_gate',return_value={}),patch.object(w,'_policy',return_value=({}, {}, {}, '1')),\
       patch.object(w,'_packages',side_effect=AssertionError('final opened')):
   with self.assertRaisesRegex(ValueError,'post_campaign_final_gate'):w.run_once({},Path('/absent'))

 def test_durable_paid_intent_precedes_callback_and_same_call_cannot_repeat(self):
  with TemporaryDirectory() as directory:
   root=Path(directory);root.chmod(0o700);study=SimpleNamespace()
   identities=[{'task_id':'fixture','package_sha256':'a'*64}]
   session=fake_session(study,identities,'b'*64,'opaque',False)
   paid=worker.PaidCalls(attempt_id='offline',checkpoint='b'*64,identities=identities,output_dir=root,runtime='c'*64,quote='0.001',session=session)
   def provider(request):
    self.assertTrue((root/'paid/offline-e2b.intent.private.json').is_file())
    self.assertTrue((root/'paid/offline-e2b.dispatched.private.json').is_file())
    return {'status':'active'}
   paid.invoke(suffix='e2b',category='e2b',request={'lease_seconds':1200},provider=provider,identity=identities[0])
   with self.assertRaises(ValueError):paid.invoke(suffix='e2b',category='e2b',request={'lease_seconds':1200},provider=provider,identity=identities[0])
   self.assertEqual(len(session.calls),1)

 def test_all_five_model_slots_run_exact_twenty_saved_scored_reset_episodes_offline(self):
  source,_neutral,positive,oracle,extension=source_case('calc-growth')
  identities=[{'task_id':f'offline-{i:02d}','package_sha256':digest(str(i).encode()),'source_groups':['fixture'],
               'template_group':'fixture','instance_group':f'fixture-{i}'} for i in range(20)]
  for owner in ['shared-base',*integration.matrix.RESEARCHERS]:
   with self.subTest(owner=owner),TemporaryDirectory() as directory:
    root=Path(directory);root.chmod(0o700);guest_ref=root/'guest.json';guest_ref.write_text('{}')
    private_map=root/'map.json';private_map.write_text(json.dumps({'variant_salt':'offline-only-'*4}));private_map.chmod(0o600)
    admitted={'guest_public':str(guest_ref),'scoped_reference':str(root/'profile'),'private_map':str(private_map)}
    study=SimpleNamespace(task_views=lambda cell:{'selection':identities},repo_root=root,plan_sha256='c'*64)
    path=None if owner=='shared-base' else 'tinker://offline/sampler_weights/'+owner
    checkpoint=vision.digest(vision.MODEL) if path is None else digest(path.encode())
    session=fake_session(study,identities,checkpoint,path,path is None)
    if path is not None:session.intent['researcher_id']=owner
    w=worker.DesktopProspectiveModelWorker(study=study,admissions_path=root/'absent',proposal_path=root/'proposal')
    (root/'proposal').write_text('{}')
    packages=[{'identity':{k:r[k] for k in ['task_id','package_sha256']},'source':source,'oracle':oracle,
               'filename':'train'+extension,'instruction':'public TRAIN fixture'} for r in identities]
    made=[]
    def create_guest(**kwargs):
     identity=next(r for r in identities if r['task_id']==kwargs['out'].parent.name)
     guest=FakeModelGuest(kwargs['root'],kwargs['out'],kwargs['filename'],source,positive,kwargs['out'].name,identity)
     made.append(guest);return guest
    with patch.object(w,'_gate',return_value=admitted),patch.object(w,'_packages',return_value=packages),\
     patch.object(w,'_policy',return_value=({}, {}, {'seed':23,'max_output_tokens':128}, '0.001')),\
     patch.object(transport,'ModelSampler',FakeSampler),patch.object(transport,'create_guest',side_effect=create_guest),\
     patch('native_desktop_factory.reconcile_interrupted_sweep.active_hashes',return_value=([],0)):
     result=w.run_base_selection(session=session,out_dir=root/'batch') if path is None else w.run_selection(
       session=session,started=session.started,checkpoint_path=path,out_dir=root/'batch')
    self.assertEqual(result['status'],'scored');self.assertEqual(len(result['result']['tasks']),20)
    self.assertTrue(all(row['score']==1 for row in result['result']['tasks']))
    self.assertEqual(len(made),40);self.assertTrue(all(g.killed for g in made))
    environments=[r for r in session.calls if r['category']=='e2b']
    self.assertEqual(len(environments),40);self.assertEqual({r['request']['lease_seconds'] for r in environments},{1200})
    self.assertEqual(sum(r['category']=='tinker' for r in session.calls),41)

 def test_actual_final_worker_outcomes_are_accepted_by_existing_controller_for_all_five_slots(self):
  source,_neutral,positive,oracle,extension=source_case('calc-growth')
  identity={'task_id':'offline-final','package_sha256':'a'*64}
  package={'identity':identity,'source':source,'oracle':oracle,'filename':'train'+extension,'instruction':'public TRAIN fixture'}
  training={'prefill_usd_per_million_tokens':'1','sample_usd_per_million_tokens':'1','billing_multiplier_upper':'1'}
  sampling={'seed':23,'max_output_tokens':128,'temperature':0};bindings={'runtime':'b'*64}
  for owner in ['shared-base',*integration.matrix.RESEARCHERS]:
   with self.subTest(owner=owner),TemporaryDirectory() as directory:
    root=Path(directory);root.chmod(0o700);guest_ref=root/'guest.json';guest_ref.write_text('{}')
    private_map=root/'map.json';private_map.write_text(json.dumps({'variant_salt':'offline-only-'*4}));private_map.chmod(0o600)
    admitted={'guest_public':str(guest_ref),'scoped_reference':str(root/'profile'),'private_map':str(private_map)}
    study=SimpleNamespace(repo_root=root,plan_sha256='c'*64)
    path=None if owner=='shared-base' else 'tinker://offline/sampler_weights/'+owner
    checkpoint=vision.digest(vision.MODEL) if path is None else digest(path.encode())
    gate=object.__new__(final.FinalGate);gate.frozen=study;gate.last_selection_frozen_at=0
    gate.freezes={('desktop-native',owner):{'selected_checkpoint_sha256':checkpoint}}
    w=worker.DesktopProspectiveModelWorker(study=study,admissions_path=root/'absent',proposal_path=root/'proposal',final_gate=gate)
    command={'schema':final.COMMAND_SCHEMA,'cell_id':'desktop-native','owner_slot':owner,'max_actions':90,'max_wall_seconds':720,
     'sampling':sampling,'matched_bindings':bindings,'action_profile':'scale-action-profile-v0.6.6','sampler_path':path,
     'checkpoint_sha256':checkpoint,**identity,'expected_initial_state_sha256':digest(source),'attempt_id':'offline-final-'+owner,'reserve_usd':'1'}
    output_dir=root/'attempt';output_dir.mkdir(mode=0o700)
    def create_guest(**kwargs):return FakeModelGuest(kwargs['root'],kwargs['out'],kwargs['filename'],source,positive,kwargs['out'].name,identity)
    with patch.object(w,'_gate',return_value=admitted),patch.object(w,'_packages',return_value=[package]),\
     patch.object(w,'_policy',return_value=({'matched_bindings':bindings},training,sampling,'0.001')),\
     patch.object(transport,'ModelSampler',FakeSampler),patch.object(transport,'create_guest',side_effect=create_guest),\
     patch('native_desktop_factory.reconcile_interrupted_sweep.active_hashes',return_value=([],0)),\
     patch('native_desktop_factory.qwen_sampler_process_v11.delegated_pre_dispatch',return_value={}):
     outcome=w.run_once(command,output_dir)
    controller=object.__new__(final.FinalController);controller.gate=gate;controller.now=worker.time.time
    checked,_=controller._validate_outcome(outcome,command,output_dir,outcome['wall_time_ms']+1000)
    self.assertEqual(checked['value']['score'],1)
    self.assertEqual(checked['value']['action_count'],2)
    with patch.object(w,'_gate',return_value=admitted),patch.object(w,'_policy',return_value=({'matched_bindings':bindings},training,sampling,'0.001')):
     with self.assertRaisesRegex(ValueError,'consumed_no_replay'):w.run_once(command,output_dir)


if __name__=='__main__':unittest.main()
