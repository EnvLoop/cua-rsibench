"""Original runtime/guard/paid-session call paths, OFFLINE surfaces only.

Qualification/package loading is mocked ONLY for the loop component fixture.
The separate authority suite exercises the real refusal boundary. These tests
never qualify a native Office profile or dispatch a real model/provider.
"""
import copy,json,os,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from tests.test_office_owned_folder_runtime_v2 import Host as FolderHost,FixturePackage,put
from tests.test_office_owned_folder_native_guard_v2 import Host as GuardHost
from tests import test_full_study_campaign_dispatch_v1 as campaign_fixture
from tests import v22_policy_runtime_fixture as v22
from tools import office_owned_folder_runtime_v2 as office
from tools.office_current_authority_v4 import Authority,current_sources
from tools.office_current_execution_v4 import TaskWorker
from tools.office_current_native_clock_v4 import Actor
from tools.office_current_paid_v4 import PaidSampler
from tools.office_current_evidence_v4 import reopen_task,task_projection
from tools.office_current_budget_performance_v4 import descriptor
from tools.office_current_protocol_v4 import epoch_context,verify_budget
from cursibench import full_study_runtime_v2 as protocol
from cursibench import full_study_qwen_runtime_gate_v1 as qwen_gate
from native_desktop_factory.actor_deadline_future_v21 import ActorDeadlineProof,ActorDeadlineReached

class Package(FixturePackage):
 def revalidate(self):pass

class Spool(FolderHost):
 package=None;instances=[]
 def __init__(self,root,*,source_admission):
  self.spool_root=Path(root);self.spool_root.mkdir(mode=0o700);self.admission=json.loads(office.private(source_admission));binding={'account_principal_sha256':self.admission['account_principal_sha256'],'folder_scope_sha256':self.admission['folder_scope_sha256']}
  super().__init__(Path(self.admission['native_evidence_root']),binding);self.guard=GuardHost();self.sequence=0;self.actor=None;self.baseline=self.package.paths['baseline'];self.saved=True;self.instances.append(self)
 def capabilities(self):return {'surface':'original-office-web','same_account':True,'graph':False,'qualified_native_operations':True,'offline_fixture':True}
 def rpc(self,operation,payload,result):
  if operation in ('native_surface','resolve_native_targets','dispatch_native_primitive'):payload={**payload,'actor_deadline_epoch_ms':self.actor_deadline_epoch_ms}
  directory=self.spool_root/f'operation-{self.sequence:04d}';directory.mkdir(mode=0o700)
  request={'schema':'office-owned-folder-operation-request-v2','sequence':self.sequence,'operation':operation,'payload':payload,'one_use':True}
  put(directory/'request.private.json',office.canonical(request));response={'schema':'office-owned-folder-operation-response-v2','sequence':self.sequence,'operation':operation,'request_sha256':office.sha(office.private(directory/'request.private.json')),'status':'completed','result':result}
  put(directory/'response.private.json',office.canonical(response));put(directory/'consumed.private.json',office.canonical({'response_sha256':office.sha(office.private(directory/'response.private.json')),'one_use':True}));self.sequence+=1;return result
 def owned_folder_inventory(self):return self.rpc('folder_inventory',{},super().owned_folder_inventory())
 def create_from_baseline(self,task,baseline,*,purpose):return self.rpc('create_document',{'purpose':purpose},super().create_from_baseline(task,baseline,purpose=purpose))
 def double_download(self,item,*,purpose):
  raw=self.baseline.read_bytes()
  if purpose=='saved_actor':raw=getattr(self.package,'candidate',None).read_bytes() if getattr(self.package,'candidate',None) else b'correct saved'
  refs=[put(self.root/f'download-{self.n}-{k}.pptx',raw) for k in range(2)]
  result=self.record('double_download',item_identity_sha256=item['item_identity_sha256'],download_refs=refs,download_surface='folder_toolbar')
  return self.rpc('double_download',{'purpose':purpose,'item':item},result)
 def actor_open(self,item,task,artifact_root,*,account_lease):
  self.account_lease=account_lease;self.item=item;tick=time.monotonic();raw=office.private(account_lease.path)
  lease={'schema':'native-surface-lease-v1','lease_id':account_lease.token,'cell_id':task['cell_id'],'account_sha256':self.binding['account_principal_sha256'],'workspace_sha256':self.binding['folder_scope_sha256'],'window_sha256':'c'*64,'owner_sha256':office.sha(raw),'issued_at':tick,'expires_at':tick+1200,
   'evidence':{'schema':'native-guard-artifact-ref-v1','path':'account-lease.private.json','sha256':office.sha(raw),'size':len(raw),'kind':'lease_evidence'}}
  self.actor=Actor(self,actor_task=task,item=item,lease=lease,artifact_root=artifact_root);put(self.actor.root/'account-lease.private.json',raw)
  self.rpc('actor_open',{}, {'owned_document_editing':True,'native_policy_sha256':office.safety.POLICY_SHA,'window_sha256':'c'*64});return self.actor
 def current_native_surface(self,item,*,phase):
  value=self.guard.current_native_surface(item,phase=phase);meta=value['native_metadata'];meta.update(account_principal_sha256=self.binding['account_principal_sha256'],folder_scope_sha256=self.binding['folder_scope_sha256'],document_identity_sha256=item['item_identity_sha256'])
  ref=put(self.root/f'capture-{self.sequence}.image',value['cropped_image_bytes']);self.rpc('native_surface',{'phase':phase},{'cropped_image_ref':ref,'native_metadata':meta});return value
 def check_native_lease(self,lease):
  office.require(self.account_lease.active(),'Actual offline lease lost');raw=office.private(self.account_lease.path);ref=self.actor.put(f'lease-check-{self.sequence}.private.json',raw,'lease_check');tick=time.monotonic()
  return {'schema':'native-surface-lease-check-v1','lease_sha256':office.safety.digest(lease),'status':'active','checked_at':tick,'expires_at':tick+10,'evidence':ref}
 def resolve_current_action_targets(self,item,action,current):return self.rpc('resolve_native_targets',{},self.guard.resolve_current_action_targets(item,action,current))
 def dispatch_native_primitive(self,item,action,resolved):
  result=self.guard.dispatch_native_primitive(item,action,resolved);now=int(time.time()*1000);result.update(actor_deadline_epoch_ms=self.actor_deadline_epoch_ms,native_driver_started_epoch_ms=now,native_driver_completed_epoch_ms=now)
  return self.rpc('dispatch_native_primitive',{},result)
 def close_document(self,item):return self.rpc('close_document',{'item':item},super().close_document(item))
 def remove_owned_item(self,item):return self.rpc('remove_document',{'item':item},super().remove_owned_item(item))

class Delegate:
 mode='complete';instances=[];clock=None
 def __init__(self,*,repo_root,journal_root,plan_sha256):self.root=Path(journal_root);self.root.mkdir(mode=0o700);self.plan=plan_sha256;self.proof=None;self.instances.append(self)
 def start(self,**kwargs):return {'status':'ready','checkpoint_path_sha256':kwargs['checkpoint_sha256']}
 def sample(self,**kwargs):
  if self.mode=='early':raise TimeoutError('offline earlier provider timeout')
  if self.mode=='deadline':
   absolute=kwargs['actor_deadline'];started=time.monotonic();self.clock[0]=absolute+.01;self.proof=ActorDeadlineProof(absolute,started,self.clock[0],min(120,absolute-started),'actor_deadline_reached_during_wait',True,False).receipt()
   request={'kind':'sample','plan_sha256':self.plan,'same_request_replay_authorized':False,'arguments':{'actor_deadline':absolute}};put(self.root/'000.request.private.json',office.canonical(request));put(self.root/'000.result.private.json',office.canonical({'status':'actor_deadline','request_sha256':office.sha(office.private(self.root/'000.request.private.json')),'actor_deadline_proof':self.proof}))
   raise ActorDeadlineReached(ActorDeadlineProof(**{k:v for k,v in self.proof.items() if k in ActorDeadlineProof.__dataclass_fields__}))
  return {'status':'completed','new_dispatch':True,'reused':False,'text':'{"type":"finish","memory":"Unicode 保留"}','usage':{'input_tokens':100,'image_tokens':10,'output_tokens':20},'elapsed_seconds':.1}
 def assert_deadline_stop(self,deadline):return self.proof
 def close(self,success):put(self.root/'child-terminal.private.json',office.canonical({'provider_shutdown_acknowledged':True,'forced_termination':False,'model_completion_uncertain':self.proof is not None}))

class LoopTests(unittest.TestCase):
 def setUp(self):
  self.f=campaign_fixture.FullStudyDispatchTests();self.f.setUp();self.addCleanup(self.f.tearDown)
  with epoch_context():self.study=v22.study(self.f.frozen())
  cell='powerpoint-web';v22.base_receipt(self.study,cell);self.session=self.study.open_campaign(self.study.repo_root/'work/current-loop',cell_id=cell,researcher_id='astra',now=lambda:self.f.clock[0])
  self.f.runtime_gate_mock.side_effect=None;self.f.runtime_gate_mock.return_value={'runtime_spec_sha256':'d'*64,'toy_public_receipt_sha256':'e'*64,'runtime_gate_source_sha256':'f'*64}
  with protocol.runtime_context(self.study):self.f.trained_candidate(self.session)
  started=self.session.start_selection_attempt(round_index=1,attempt_id='selection-current-office')
  self.authority=Authority(authority=self.study,cell_id=cell,owner_slot='astra',session=self.session,started=started)
  root=self.study.repo_root/'work/loop';root.mkdir(mode=0o700);self.root=root;self.evidence=root/'evidence';self.evidence.mkdir(mode=0o700)
  source=root/'source.pptx';put(source,b'neutral source');self.package=Package(source);Spool.package=self.package
  binding={'schema':office.SCHEMA,'single_account':True,'scope':'existing_account_dedicated_disposable_folder','source_sha256s':office.source_hashes(),'supplemental_source_sha256s':{k:v for k,v in current_sources(Path(__file__).resolve().parents[1]).items() if k.endswith('.mjs') and k not in office.SOURCE_FILES},'native_policy_sha256':office.safety.POLICY_SHA,'account_principal_sha256':office.sha(str(root).encode()),'folder_scope_sha256':'b'*64,'native_evidence_root':str(self.evidence),'cells':['powerpoint-web'],'splits':['train'],'max_wall_seconds':1200}
  self.binding=root/'binding.private.json';put(self.binding,office.canonical(binding));self.profile=root/'profile.private.json';put(self.profile,office.canonical({'download_surface':'folder_toolbar','source_reviewed':True}));self.metadata=root/'metadata.private.json';put(self.metadata,b'[]')
  self.code_root=Path(__file__).resolve().parents[1];Delegate.mode='complete';Delegate.instances=[];Spool.instances=[]
 def worker(self):
  factory=lambda **kw:PaidSampler(**kw,delegate_factory=Delegate)
  output=self.authority.session.directory/'native-current' if self.authority.owner=='shared-base' else self.root/'output'
  return TaskWorker(authority=self.authority,metadata_index=self.metadata,binding_path=self.binding,profile_path=self.profile,qualification_path=self.root/'absent-qualification',qualification_sha256='0'*64,output_root=output,operation_spool_factory=Spool,sampler_factory=factory)
 def run_fixture(self):
  with patch.object(Authority,'qualify',return_value={'offline_fixture_only':True}),patch.object(Authority,'load_package',return_value=self.package),patch('tools.office_current_execution_v4.current_sources',side_effect=lambda _:current_sources(self.code_root)),patch.object(qwen_gate,'pre_dispatch',return_value=self.f.runtime_gate_mock.return_value):
   return self.worker().run({'task_id':self.package.actor.task_id,'package_sha256':self.package.binding_sha256},quote='2000')
 def test_original_loop_paid_provenance_guard_saved_score_and_distinct_reset(self):
  result,root=self.run_fixture();checked=reopen_task(self.package,root)
  self.assertEqual(checked['score'],1);self.assertEqual(result['model_outcome'],'finished');self.assertEqual(len(Delegate.instances),1);self.assertEqual(Spool.instances[0].guard.calls.count('driver'),1)
  paid=[r['data'] for r in self.session._events('paid_intent') if r['data']['attempt_id'].startswith(self.authority.started['attempt_id']+'-')]
  self.assertEqual(len(paid),3);self.assertEqual([p['category'] for p in paid],['storage_application','tinker','tinker']);self.assertTrue(paid[-1]['attempt_id'].endswith('sample-000'))
  # Real campaign serializes newline and non-ASCII; local bytes remain EXACT.
  actual=self.session.directory/(paid[-1]['attempt_id']+'.result.private.json');self.assertEqual(actual.read_bytes(),(root/'sampler.private/sample-000.result.private.json').read_bytes())
  self.assertIsNone(result['actual_cost_usd']);self.assertFalse(result['invoice_complete']);self.assertFalse(Spool.instances[0].account_lease.path.exists())
 def test_earlier_provider_fault_is_unscored_retained_and_never_replayed(self):
  Delegate.mode='early'
  with self.assertRaises(ValueError):self.run_fixture()
  root=self.root/'output'/('000-'+self.package.actor.task_id);self.assertTrue((root/'invalid.private.json').exists());self.assertFalse((root/'task-result.private.json').exists());self.assertEqual(Spool.instances[0].guard.calls.count('driver'),0);self.assertFalse(Spool.instances[0].account_lease.path.exists())
  self.assertTrue(self.session._unresolved_failure())
 def test_uncertain_actor_deadline_saved_positive_is_not_forced_zero_no_late_gui(self):
  Delegate.mode='deadline';clock=[time.monotonic()];Delegate.clock=clock
  with patch('time.monotonic',side_effect=lambda:clock[0]):result,root=self.run_fixture()
  self.assertEqual(result['score'],1);self.assertTrue(result['model_completion_unknown']);self.assertEqual(result['actor_seconds'],720);self.assertEqual(Spool.instances[0].guard.calls.count('driver'),0)
  row=task_projection(self.package,root);self.assertEqual(row['score'],1);self.assertTrue(self.session._unresolved_failure())
  # The source/read-only reader is separately qualified; no forged future is
  # passed to formal admission in this component fixture.
 def test_private_saved_download_change_rejects_independent_reopen(self):
  _,root=self.run_fixture();record=json.loads(office.private(root/'native.private/operation-003-double_download.private.json')) if (root/'native.private/operation-003-double_download.private.json').exists() else None
  files=list(self.evidence.glob('download-*.pptx'));put(files[-1],b'changed')
  with self.assertRaises(ValueError):reopen_task(self.package,root)

@unittest.skipUnless(os.environ.get('ENVLOOP_PPT_TRAIN_PACKAGE'),'actual private TRAIN package not configured')
class ActualStrictLoopTests(LoopTests):
 def test_real_original_wdi_package_positive_nearmiss_and_collateral(self):
  from tools.office_current_package_v4 import Package as ActualPackage
  from ppt_wdi_factory import verify
  source=Path(os.environ['ENVLOOP_PPT_TRAIN_PACKAGE']);destination=self.root/'actual-package';destination.mkdir(mode=0o700)
  for name in ('source.pptx','task.private.json','source-snapshot.private.json','source-provenance.private.json','source-country.private.zip'):
   if (source/name).exists():put(destination/name,(source/name).read_bytes())
  task=json.loads((destination/'task.private.json').read_bytes());path=destination/'package.private.json';office.descriptor(cell_id='powerpoint-web',split=task['split'],task_id=task['task_id'],instruction=task['actor_task'],baseline=destination/'source.pptx',task_spec=destination/'task.private.json',out=path)
  package=ActualPackage(path,package_root=destination);changes={k:v['correct'] for k,v in package.oracle['targets'].items()}
  for name,edits,collateral,chart in [('positive',changes,False,False),('near',{},False,False),('collateral',changes,True,False),('chart',changes,False,True)]:
   candidate=destination/(name+'.pptx');verify._write_variant(package.paths['baseline'],candidate,edits,package.oracle,collateral=collateral,chart_damage=chart);self.assertEqual(package.strict_score(candidate)['score'],int(name=='positive'))
  package.candidate=destination/'positive.pptx';self.package=package;Spool.package=package
  binding=json.loads(office.private(self.binding));binding['splits']=[task['split']];put(self.binding,office.canonical(binding))
  result,root=self.run_fixture();self.assertEqual(reopen_task(package,root)['score'],1);self.assertEqual(result['raw_strict_saved_score'],1)

class SelectionTwentyTests(LoopTests):
 def test_real_campaign_twenty_task_paid_coverage_and_registration(self):
  from tools.office_current_workers_v4 import run_selection
  def load(a,identity,metadata):
   value=Package(self.package.paths['baseline']);value.actor=office.ActorTask(identity['task_id'],identity['package_sha256'],'powerpoint-web','selection','Visible task only','f'*64);value.binding_sha256=identity['package_sha256'];Spool.package=value;return value
  binding=json.loads(office.private(self.binding));binding['splits']=['selection'];put(self.binding,office.canonical(binding))
  with patch.object(Authority,'qualify',return_value={'offline_fixture_only':True}),patch.object(Authority,'load_package',load),patch('tools.office_current_execution_v4.current_sources',side_effect=lambda _:current_sources(self.code_root)),patch('tools.office_current_workers_v4.current_sources',side_effect=lambda _:current_sources(self.code_root)),patch.object(qwen_gate,'pre_dispatch',return_value=self.f.runtime_gate_mock.return_value),patch('native_desktop_factory.qwen_sampler_process_v21.delegated_pre_dispatch',return_value=self.f.runtime_gate_mock.return_value):
   worker=self.worker();value=run_selection(worker,quote='2000',register=True)
  self.assertEqual(value['coverage']['task_count'],20);self.assertEqual(value['coverage']['completed_model_response_count'],20);self.assertEqual(len(Delegate.instances),20);self.assertEqual(len(Spool.instances),20);self.assertEqual(len(value['paid_attempt_ids']),60)
  self.assertEqual(len(self.session._events('selection_scored')),1);self.assertIsNone(value['actual_cost_usd']);self.assertEqual(value['registration']['score_wins'],20)

 def test_real_shared_base_session_twenty_tasks_actual_paid_envelopes(self):
  from tools.office_current_workers_v4 import run_selection
  shared=protocol.SharedBaseSession(self.study,'excel-web')
  # Exact fake base identity is confined to this fixture; production always
  # hashes the real Qwen base model constant.
  with patch('tools.office_current_authority_v4.MODEL','excel-webshared-base'):
   authority=Authority(authority=self.study,cell_id='excel-web',owner_slot='shared-base',session=shared)
  self.authority=authority
  def load(a,identity,metadata):
   value=Package(self.package.paths['baseline']);value.actor=office.ActorTask(identity['task_id'],identity['package_sha256'],'excel-web','selection','Visible task only','f'*64);value.binding_sha256=identity['package_sha256'];Spool.package=value;return value
  binding=json.loads(office.private(self.binding));binding['splits']=['selection'];binding['cells']=['excel-web'];put(self.binding,office.canonical(binding))
  with patch.object(Authority,'qualify',return_value={'offline_fixture_only':True}),patch.object(Authority,'load_package',load),patch('tools.office_current_execution_v4.current_sources',side_effect=lambda _:current_sources(self.code_root)),patch('tools.office_current_workers_v4.current_sources',side_effect=lambda _:current_sources(self.code_root)),patch('native_desktop_factory.qwen_sampler_process_v21.delegated_pre_dispatch',return_value=self.f.runtime_gate_mock.return_value):
   value=run_selection(self.worker(),quote='2000')
  self.assertEqual(value['coverage']['task_count'],20);self.assertEqual(value['coverage']['completed_model_response_count'],20);self.assertEqual(len(shared.paid_references()),60);self.assertEqual(len(shared.budget.owner_attempts(shared.owner)),60)
  for ref in shared.paid_references():
   envelope=json.loads(office.private(shared.directory/ref['request_ref']['path']));self.assertEqual(envelope['category'],ref['category']);self.assertEqual(envelope['checkpoint_path_sha256'],authority.checkpoint)
  self.assertTrue(all(row['actual_usd'] is None for row in shared.budget.owner_attempts(shared.owner).values()))

class TeacherLoopTests(LoopTests):
 def test_actual_teacher_callback_ledger_same_native_loop_without_tinker_charge(self):
  from tools.office_current_teacher_v4 import TeacherTransport
  from cursibench.full_study_matrix_v1 import TEACHER
  from cursibench.scale_action_output_v066 import normalize_model_action
  authority=Authority(authority=self.study,cell_id='powerpoint-web',owner_slot='astra',session=self.session,teacher=True);self.authority=authority
  transport=TeacherTransport(self.root/'teacher-provider')
  def callback(observation,current):
   request={'cell_id':authority.cell,'train_task_id':observation.task_id,'package_sha256':observation.task_binding_sha256,'step':observation.step,'frame_sha256':office.sha(observation.screenshot_bytes)}
   value=self.session.dispatch_paid(attempt_id='teacher-current-offline-000',category='teacher_rollout',work=request,request=request,reserve_usd='2000',resource_reservation={'teacher_rollout_calls':'1','teacher_rollout_tokens':'200'},provider=lambda request:transport(request,lambda _: {'text':'{"type":"finish"}','receipt':{'reported_model':TEACHER,'status':'completed','response_id':'synthetic-offline-id','usage':{'input_tokens':100,'output_tokens':20}}}))
   action=normalize_model_action(value['result']['text'],observation,current_frame_id=current())
   return {'action':action,'trace_row':{'action':action,'teacher_result_sha256':value['result_sha256']},'teacher_result_sha256':value['result_sha256']}
  callback.bind_actor_clock=transport.bind_actor_clock
  before={r['data']['attempt_id'] for r in self.session._events('paid_intent')}
  with patch.object(Authority,'qualify',return_value={'offline_fixture_only':True}),patch.object(Authority,'load_package',return_value=self.package),patch('tools.office_current_execution_v4.current_sources',side_effect=lambda _:current_sources(self.code_root)):
   worker=TaskWorker(authority=authority,metadata_index=self.metadata,binding_path=self.binding,profile_path=self.profile,qualification_path=self.root/'absent-qualification',qualification_sha256='0'*64,output_root=self.root/'output',operation_spool_factory=Spool,teacher_callback=callback,teacher_close_callback=transport.close_evidence)
   result,root=worker.run({'task_id':self.package.actor.task_id,'package_sha256':self.package.binding_sha256},quote='2000')
  checked=reopen_task(self.package,root);self.assertEqual(checked['score'],1)
  categories=[r['data']['category'] for r in self.session._events('paid_intent') if r['data']['attempt_id'] not in before]
  self.assertEqual(categories,['storage_application','teacher_rollout']);self.assertEqual(result['sampler_paid_attempt_ids'],['teacher-current-offline-000']);self.assertFalse(Delegate.instances)
  self.assertTrue(transport.closed);self.assertTrue(all(f.done() for f in transport.futures));self.assertEqual(Spool.instances[0].guard.calls.count('driver'),1)

class BudgetReaderTests(LoopTests):
 def test_real_session_reader_authorizes_only_exact_retained_deadline_saved_reset(self):
  from tools import office_current_budget_performance_v4 as reader
  from tools import office_current_protocol_v4 as context
  identity=self.authority.identities()[0];self.package.actor=office.ActorTask(identity['task_id'],identity['package_sha256'],'powerpoint-web','selection','Visible task only','f'*64);self.package.binding_sha256=identity['package_sha256']
  self.package.root=self.root;self.package.descriptor=self.root/'synthetic-descriptor.private';put(self.package.descriptor,identity['task_id'].encode());self.assertEqual(office.sha(office.private(self.package.descriptor)),identity['package_sha256'])
  binding=json.loads(office.private(self.binding));binding['splits']=['selection'];put(self.binding,office.canonical(binding));Delegate.mode='deadline';clock=[time.monotonic()];Delegate.clock=clock
  with patch('time.monotonic',side_effect=lambda:clock[0]):result,root=self.run_fixture()
  task_projection(self.package,root);verification=descriptor(self.study,self.package,root)
  with patch.object(reader,'Package',return_value=self.package),patch.object(context,'source_manifest',side_effect=lambda _:context._BASE_MANIFEST(self.code_root)|{'source_sha256s':{**context._BASE_MANIFEST(self.code_root)['source_sha256s'],**current_sources(self.code_root)},'office_current_source_epoch':'original-office-current-v4','office_native_qualification_claimed':False}),epoch_context(self.study):
   receipt=verify_budget(self.study,'astra',verification);self.assertEqual(receipt['performance']['score'],1);self.assertEqual(receipt['inference']['completed_model_response_count'],0);self.assertEqual(receipt['inference']['status'],'completion_unknown_after_actor_deadline');self.assertIsNone(receipt['billing']['actual_usd'])
   self.session.authorize_verified_budget_stop(receipt['sample_paid_attempt_id'],verification=verification);self.assertFalse(self.session._unresolved_failure())
   stopped=json.loads(office.private(root/'sampler.private/actor-budget-stop.private.json'));stopped['sample_paid_attempt_id']='forged-paid-id';put(root/'sampler.private/actor-budget-stop.private.json',office.canonical(stopped))
   with self.assertRaises(ValueError):verify_budget(self.study,'astra',verification)
