"""Self-contained fake-filesystem tests; no browser/Docker/model constructor."""
import unittest,tempfile,copy,json,sys,os,hashlib,importlib
from pathlib import Path
from unittest.mock import patch
from odoo_reference.loader import activate,RUNTIME,source_binding
from odoo_reference.config import Config,canonical,digest
from odoo_reference.control import validate_result,CLEANUP_KEYS,write,Journal,fill,select_all_key
SCOPE=Path(tempfile.mkdtemp(prefix='public-odoo-source-test-'))
(factory,lease,verify,reset,Adapter)=activate(SCOPE/'worker')
from odoo_reference import observer,observer_audit
from probe_fixture import exercise
class PackageTests(unittest.TestCase):
 def setUp(self):self.dir=Path(tempfile.mkdtemp(dir=SCOPE));self.dir.chmod(0o700)
 def score_fixture(self):
  order={'id':1,'name':'PUBLIC-TRAIN-001','origin':'PUBLIC-TRAIN-DEMO'};other={'id':2,'name':'PUBLIC-WRONG-002'}
  line={'id':11,'order_id':1,'product_id':5,'name':'public','qty':'5','price':'17','date':'2025-05-01'};wrong={**line,'id':12,'order_id':2,'product_id':6,'price':'18'}
  base={'global_business_identity':{'orders':[1,2],'lines':[11,12]},'orders':[order,other],'lines':[line,wrong],'attachments':[],'products':[]}
  gold={'order_id':1,'lines':[{'line_id':11,'product_id':5,'expected':{'qty':5,'price':12,'date':'2025-05-01'}}]}
  good=copy.deepcopy(base);good['lines'][0]['price']='12';return base,gold,good
 def test_import_closure_and_source_binding(self):
  with patch('subprocess.Popen',side_effect=AssertionError('native_constructor_forbidden')),patch('playwright.sync_api.sync_playwright',side_effect=AssertionError('native_constructor_forbidden')),patch('xmlrpc.client.ServerProxy',side_effect=AssertionError('RPC_forbidden')):
   for file in RUNTIME.rglob('*.py'):
    if file.name=='__init__.py':continue
    name=str(file.relative_to(RUNTIME)).removesuffix('.py').replace('/','.')
    if name.startswith('src.'):name=name[4:]
    importlib.import_module(name)
   from enterprise_fallback.odoo18.odoo_v066_native_surface_adapter_v14 import public_binding
   value=public_binding();self.assertEqual(value['max_actions'],90);self.assertEqual(value['wall_seconds'],720)
   self.assertIn('compose_sha256',source_binding());self.assertEqual(factory.PRIVATE,(SCOPE/'worker/private').resolve())
 def test_score_trio_and_absent_target(self):
  base,gold,good=self.score_fixture();wrong=copy.deepcopy(base);wrong['lines'][1]['price']='13'
  self.assertEqual([verify.evaluate('public',gold,base,x)['reward'] for x in (base,good,wrong)],[0,1,0])
  for missing in ('orders','lines'):
   empty=copy.deepcopy(good);empty[missing]=[];self.assertEqual(verify.evaluate('public',gold,empty,empty)['reward'],0)
  bad=copy.deepcopy(good);bad['lines'][0]['order_id']=2;self.assertEqual(verify.evaluate('public',gold,base,bad)['reward'],0)
  bad=copy.deepcopy(good);bad['lines'][0]['price']='12.000001';self.assertEqual(verify.evaluate('public',gold,base,bad)['reward'],0)
  bad=copy.deepcopy(good);bad['global_business_identity']={};self.assertEqual(verify.evaluate('public',gold,base,bad)['reward'],0)
 def test_duplicate_or_nonfinite_comparators_refuse(self):
  base,gold,good=self.score_fixture()
  for mutate in ('duplicate','empty','nan'):
   g=copy.deepcopy(gold)
   if mutate=='duplicate':g['lines']*=2
   elif mutate=='empty':g['lines']=[]
   else:g['lines'][0]['expected']['price']='NaN'
   with self.assertRaises(ValueError):verify.evaluate('public',g,base,good)
  good['lines']*=2
  with self.assertRaises(ValueError):verify.evaluate('public',gold,base,good)
 def test_protected_source_bytes_and_store_path(self):
  b={'attachments':[{'id':1,'checksum':'a'*40}]};files={'filestore/bench/aa/'+'a'*40:'h'}
  self.assertEqual(verify.protected_source_file_differences(b,files,files),[])
  self.assertTrue(verify.protected_source_file_differences(b,files,{}))
  self.assertTrue(verify.protected_source_store_path_differences(b,{'1':'changed'}))
 def test_cleanup_exact_schema(self):
  good={'schema':'public-odoo-reference-result-v1','scores':[0,1,0],'initial_failure':None,'cleanup':{k:True for k in CLEANUP_KEYS},'models':0,'training':False,'formal_admissions':0};self.assertTrue(validate_result(good))
  for c in ({'failed':True,'type':'RuntimeError','message':'unsafe'}, {k:1 for k in CLEANUP_KEYS},{k:True for k in CLEANUP_KEYS if k!='SQL_exact'},{**good['cleanup'],'extra':True}):
   bad=copy.deepcopy(good);bad['cleanup']=c
   with self.assertRaises(RuntimeError):validate_result(bad)
  bad=copy.deepcopy(good);bad['scores']=[False,True,False]
  with self.assertRaises(RuntimeError):validate_result(bad)
 def test_actual_probe_real_store_repeated_conflicts_and_audit3(self):
  with patch('playwright.sync_api.sync_playwright',side_effect=AssertionError('native_constructor_forbidden')),patch('xmlrpc.client.ServerProxy',side_effect=AssertionError('RPC_forbidden')):
   for mode in ('transient','finalconflict','persistent'):
    attempt=self.dir/mode;value=exercise(attempt,mode);self.assertTrue(value['diagnostic_names_unique']);self.assertEqual(value['native_dispatches'],0)
    for name,phase in [('actions/step-000-intent.private.json','positive')]:write(attempt/name,{'phase':phase,'normalized_action':{'type':'click'}})
    if mode!='persistent':
     proof=observer_audit.audit3(attempt);self.assertTrue(proof['strict_conditional_final_and_stability_verified']);self.assertTrue(proof['additive_selector_prefix_proof']['all_prefixes_equal'])
     first=next(attempt.glob('*-indicator-styles-before-selector-000.private.json'));value=json.loads(first.read_bytes());value['native_elements'][0]['element_id']='tampered';first.write_bytes(canonical(value))
     with self.assertRaises(RuntimeError):observer_audit.selector_prefix_audit(attempt)
 def test_prepare_and_exact_approval_gate_no_native(self):
  from odoo_reference.cli import prepare,review_contract,run
  stage=self.dir/'prepared';summary=prepare(stage,self.dir/'fresh-worker',19998);self.assertEqual(summary['native_calls'],0)
  plan=json.loads((stage/'plan.json').read_bytes());review_contract(plan);write(stage/'unapproved.json',{'approved':True})
  with patch('subprocess.Popen',side_effect=AssertionError('native_constructor_forbidden')),patch('playwright.sync_api.sync_playwright',side_effect=AssertionError('native_constructor_forbidden')):
   with self.assertRaises(ValueError):run(stage/'plan.json',stage/'unapproved.json',hashlib.sha256((stage/'unapproved.json').read_bytes()).hexdigest())
  self.assertFalse((self.dir/'fresh-worker').exists());self.assertFalse((stage/'approval-consumed.json').exists())
 def test_atomic_store_and_immutable_reader(self):
  file=self.dir/'one.json';write(file,{'a':1})
  with self.assertRaises(FileExistsError):write(file,{'a':2})
  read=observer_audit.ImmutableSavedReader();read.raw(file);file.write_bytes(canonical({'a':3}))
  with self.assertRaises(RuntimeError):read.raw(file)
 def test_deadline_and_fixed_keys(self):
  from enterprise_fallback.odoo18.odoo_actor_clock_v1 import ActorClock
  from native_desktop_factory.actor_deadline_future_v21 import ActorDeadlineReached
  clock=ActorClock(task_id='public',package_sha256='a'*64,started=0,clock=lambda:720)
  with self.assertRaises(ActorDeadlineReached):clock.check('before_any_native_io')
  from cursibench.scale_action_contract import _ALLOWED_KEYS
  self.assertIn('Meta+A',_ALLOWED_KEYS);self.assertIn('Control+A',_ALLOWED_KEYS)
  calls=[]
  class Recorder:
   def act(self,*args,**kwargs):calls.append((args,kwargs))
  fill(None,Recorder(),object(),'public','positive');self.assertEqual([x[0][0] for x in calls],['click','key','type']);self.assertEqual(calls[-1][1]['mode'],'insert')
 def test_actual_actor_clock_files_and_tamper(self):
  from enterprise_fallback.odoo18.odoo_actor_clock_v1 import ActorClock
  from enterprise_fallback.odoo18.odoo_native_surface_evidence_v13 import EvidenceStore
  from odoo_reference.audit import audit_actor_clock
  root=self.dir/'actor';root.mkdir(mode=0o700);store=EvidenceStore(root);tick=[0.0];clock=ActorClock(task_id='public',package_sha256='a'*64,started=0,clock=lambda:tick[0]);clock.bind(store)
  tick[0]=1;clock.before_io('mouse.click');tick[0]=2;clock.after_io('mouse.click',returned=True);tick[0]=3;clock.end('public_reference_control_complete')
  proof=audit_actor_clock(observer_audit.ImmutableSavedReader(),root);self.assertEqual(proof['native_io_count'],1)
  file=root/'actor-clock/end.private.json';original=file.read_bytes()
  for key,value in [('actor_elapsed_seconds',1),('actor_ended_monotonic',721),('raw_end_acknowledged_monotonic',float('inf'))]:
   bad=json.loads(original);bad[key]=value;file.write_bytes(json.dumps(bad).encode())
   with self.assertRaises(RuntimeError):audit_actor_clock(observer_audit.ImmutableSavedReader(),root)
  file.write_bytes(original);bad=json.loads(original);bad['native_io'][0]['status']='unknown';file.write_bytes(canonical(bad))
  with self.assertRaises(RuntimeError):audit_actor_clock(observer_audit.ImmutableSavedReader(),root)
  file.write_bytes(original);intent=root/'actor-clock/io-000-intent.private.json';intent.write_bytes(b'{}')
  with self.assertRaises(RuntimeError):audit_actor_clock(observer_audit.ImmutableSavedReader(),root)
 def test_foreign_namespace_and_runtime_tamper(self):
  from types import ModuleType
  from odoo_reference import loader
  sentinel=ModuleType('cursibench.foreign_sentinel');sentinel.__file__=str(self.dir/'sentinel.py');sys.modules[sentinel.__name__]=sentinel
  try:
   with self.assertRaises(RuntimeError):activate(self.dir/'fresh')
  finally:sys.modules.pop(sentinel.__name__,None)
  import shutil
  copied=self.dir/'runtime-copy';shutil.copytree(RUNTIME,copied);file=copied/'enterprise_fallback/odoo18/factory.py';file.write_text(file.read_text()+'# changed\n')
  with patch.object(loader,'RUNTIME',copied):
   with self.assertRaises(RuntimeError):source_binding()
 def test_bootstrap_refuses_orphan_volume_without_native_creation(self):
  from odoo_reference.infra import bootstrap
  from types import SimpleNamespace
  calls=[];config=Config(str(self.dir/'fresh-native'),'odoo-ref-demo-abcdef123456',19997).public()
  def fake_run(argv,**kwargs):
   calls.append(argv);return SimpleNamespace(stdout=b'orphan' if argv[1:3]==['volume','ls'] else b'')
  with patch('subprocess.run',side_effect=fake_run),patch('subprocess.Popen',side_effect=AssertionError('native_constructor_forbidden')):
   with self.assertRaises(RuntimeError):bootstrap(config)
  self.assertFalse((self.dir/'fresh-native').exists());self.assertTrue(all('up' not in x and 'run' not in x for x in calls))
 def test_wrong_object_zero_alone_does_not_prove_commit(self):
  base,gold,good=self.score_fixture();wrong_gold={'order_id':2,'lines':[{'line_id':12,'product_id':6,'expected':{'qty':5,'price':13,'date':'2025-05-01'}}]}
  wrong=copy.deepcopy(base);wrong['lines'][1]['price']='13'
  self.assertEqual(verify.evaluate('target',gold,base,base)['reward'],0)
  self.assertEqual(verify.evaluate('wrong',wrong_gold,base,base)['reward'],0)
  self.assertEqual(verify.evaluate('target',gold,base,wrong)['reward'],0)
  self.assertEqual(verify.evaluate('wrong',wrong_gold,base,wrong)['reward'],1)
 def test_bootstrap_refuses_unlabelled_reserved_volume(self):
  from odoo_reference.infra import bootstrap
  from types import SimpleNamespace
  config=Config(str(self.dir/'fresh-native'),'odoo-ref-demo-abcdef123456',19996).public();calls=[]
  def fake_run(argv,**kwargs):
   calls.append(argv);return SimpleNamespace(stdout=b'',returncode=0 if argv[1:3]==['volume','inspect'] else 1)
  with patch('subprocess.run',side_effect=fake_run),patch('subprocess.Popen',side_effect=AssertionError('native_constructor_forbidden')):
   with self.assertRaises(RuntimeError):bootstrap(config)
  self.assertFalse((self.dir/'fresh-native').exists());self.assertTrue(all('up' not in x and 'run' not in x for x in calls))
 def test_public_attachment_bytes_independent_rederivation(self):
  from odoo_reference.fixture import cases,document
  from odoo_reference.audit import audit_public_sources
  rows=[];gold={};files={}
  for i,case in enumerate(cases(),1):
   raw=document(case);checksum=hashlib.sha1(raw).hexdigest();path=checksum[:2]+'/'+checksum
   rows.append({'id':i,'res_model':'purchase.order','res_id':i,'name':case['id']+'-source.pdf','checksum':checksum,'file_size':len(raw),'store_fname':path});gold[case['id']]={'order_id':i};files['filestore/bench/'+path]=hashlib.sha256(raw).hexdigest()
  self.assertEqual(audit_public_sources({'attachments':rows},files,gold)['public_source_PDFs'],2)
  bad=copy.deepcopy(rows);bad[0]['store_fname']='foreign';
  with self.assertRaises(RuntimeError):audit_public_sources({'attachments':bad},files,gold)
  files[next(iter(files))]='tampered'
  with self.assertRaises(RuntimeError):audit_public_sources({'attachments':rows},files,gold)
 def test_only_public_synthetic_documents(self):
  from odoo_reference.fixture import cases,document
  self.assertEqual(len(cases()),2)
  for case in cases():self.assertTrue(document(case).startswith(b'%PDF-'));self.assertTrue(case['id'].startswith('PUBLIC-'))
if __name__=='__main__':unittest.main()
