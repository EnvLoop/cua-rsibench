import copy,json,os,tempfile,unittest
from pathlib import Path
from hashlib import sha256
from unittest.mock import patch
from types import SimpleNamespace
from enterprise_fallback.odoo18 import twenty_task_trial_teacher_v1 as trial

class AuthorityTests(unittest.TestCase):
 def plan(self):
  return {'schema':'envloop-single-environment-twenty-task-trial-v1','cell_id':'odoo-community','final_task_count':20,'selection_task_count':20,'train_task_count':20,'native_binding_sha256':'a'*64,'models':{'student':'Qwen/Qwen3.8-27B','teacher':'gpt-6.1-sol','initial_researcher':'gpt-6.1-sol'},'full_six_environment_publication_claim':False,'final_tasks_metadata':[{'task_id':f'{family}-{i}','family':family} for family in ('purchase','inventory','sales','crm') for i in range(5)]}
 def check(self,value):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'plan.json';raw=json.dumps(value).encode();path.write_bytes(raw);path.chmod(0o600)
   with patch.object(trial.workers,'public_binding',return_value={'binding_sha256':'a'*64}):return trial.checked_trial(path,sha256(raw).hexdigest())
 def test_actual_single_cell_shape_has_no_large_study_authority(self):self.assertFalse(self.check(self.plan())['full_six_environment_publication_claim'])
 def test_old_large_count_foreign_cell_and_source_refuse(self):
  for key,value in [('final_task_count',100),('cell_id','gitlab'),('native_binding_sha256','b'*64),('full_six_environment_publication_claim',True)]:
   plan=self.plan();plan[key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):self.check(plan)
 def test_duplicate_or_family_skew_cannot_be_counted_as_twenty(self):
  for mode in ('duplicate','family'):
   plan=self.plan()
   if mode=='duplicate':plan['final_tasks_metadata'][1]['task_id']=plan['final_tasks_metadata'][0]['task_id']
   else:plan['final_tasks_metadata'][1]['family']='sales'
   with self.assertRaises(ValueError):self.check(plan)

class NativeReceiptBindingTests(unittest.TestCase):
 def test_actual_source_scope_uses_sol61_without_mutating_historical_teacher(self):
  binding=trial.workers.public_binding()
  historical_model=trial.teacher.matrix.TEACHER
  training,_=trial.scoped_model_modules(binding,'gpt-6.1-sol')
  scoped=training.OdooTrainEpisodeWorker.run_episode
  self.assertEqual(scoped.__globals__['teacher'].matrix.TEACHER,'gpt-6.1-sol')
  self.assertEqual(trial.teacher.matrix.TEACHER,historical_model)
  fresh,_=trial.workers._model_modules(binding)
  self.assertEqual(fresh.OdooTrainEpisodeWorker.run_episode.__globals__['teacher'].matrix.TEACHER,historical_model)
  self.assertEqual(trial.workers.public_binding()['binding_sha256'],binding['binding_sha256'])

 def verify_fixture(self,tamper=None,model='gpt-6.1-sol'):
  # Synthetic test artifacts carry no actual task, teacher or training credit.
  from tests.test_full_study_teacher_adapter_v1 import FakeWorker,write_private
  with tempfile.TemporaryDirectory() as tmp:
   episode=Path(tmp)/'episode';episode.mkdir(mode=0o700);(episode/'frames').mkdir(mode=0o700)
   task={'task_id':'train-test','package_sha256':'a'*64,'visible_instruction':'Synthetic test'}
   turns=[]
   def sample(observation,current_frame):
    action=trial.output.normalize_model_action(json.dumps({'type':'click','target':{'ref':'c001'}} if observation.step==0 else {'type':'finish'}),observation,current_frame_id=current_frame())
    trace={'step':observation.step,'frame_id':observation.frame_id,'frame_sha256':observation.screenshot['sha256'],'action':action,'teacher_result_sha256':'c'*64}
    turns.append({'observation':observation,'action':action,'trace_row':copy.deepcopy(trace),'teacher_result_sha256':'c'*64})
    return {'action':action,'trace_row':trace,'teacher_result_sha256':'c'*64}
   worker=FakeWorker('e'*64,cell_id='odoo-community');worker.tamper=tamper
   result=worker.run_episode(task=task,out_dir=episode,sample_teacher=sample,dispatch_e2b=None)
   receipt_path=Path(result['episode_receipt_path']);receipt=json.loads(receipt_path.read_bytes());receipt['teacher_model']=model
   result['episode_receipt_sha256']=write_private(receipt_path,receipt)
   active=SimpleNamespace(runtime_sha256=worker.runtime_sha,adapter_sha256=worker.adapter_sha256,verifier_sha256=worker.verifier_sha)
   return trial.verify_trial_episode(episode,result,task,turns,active,'gpt-6.1-sol')

 def test_source_verifier_reopens_actual_fixture_artifacts_with_trial_model(self):
  self.assertEqual(len(self.verify_fixture()),64)

 def test_artifact_trace_reset_split_and_old_model_are_rejected(self):
  for tamper in ('frame','trace','saved_state','artifact','reset','split'):
   with self.subTest(tamper=tamper),self.assertRaises(ValueError):self.verify_fixture(tamper)
  with self.assertRaises(ValueError):self.verify_fixture(model='gpt-5.6-sol')

class ResearcherReturnTests(unittest.TestCase):
 def fixture(self,model='gpt-6.1-sol',changed=False):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);proposal={'hypothesis':'Synthetic test','train_task_ids':['test-train'],'teacher_request':'GUI only'}
   text=json.dumps(proposal);response={'model':model,'status':'completed','id':'synthetic-test-response','output':[{'type':'message','content':[{'type':'output_text','text':text}]}]}
   raw=json.dumps(response).encode();(root/'raw-response.private.json').write_bytes(raw);(root/'raw-response.private.json').chmod(0o600)
   trial.write(root/'provider-result.private.json',{'reported_model':model,'provider_status':'completed','response_id':response['id'],'response_sha256':sha256(raw).hexdigest(),'proposal_text_sha256':sha256(text.encode()).hexdigest()})
   if changed:proposal['hypothesis']='Changed after response'
   path=root/'validated-proposal.private.json';trial.write(path,proposal)
   return trial.checked_proposal(path,sha256(path.read_bytes()).hexdigest(),'gpt-6.1-sol')
 def test_exact_synthetic_model_receipt_and_proposal_match(self):self.assertEqual(self.fixture()['train_task_ids'],['test-train'])
 def test_old_model_or_changed_proposal_cannot_enter_new_epoch(self):
  with self.assertRaises(ValueError):self.fixture(model='gpt-6-sol')
  with self.assertRaises(ValueError):self.fixture(changed=True)
if __name__=='__main__':unittest.main()
