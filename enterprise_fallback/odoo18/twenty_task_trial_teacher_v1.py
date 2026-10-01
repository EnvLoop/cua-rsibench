"""Actual train-only teacher endpoint for the human-requested Odoo20 trial.

This has its own checked single-cell authority. It does not claim or construct
the six-cell study authority. Original native actor/scorer/reset sources stay
unchanged; the original full-study campaign gate is not modified.
"""
from pathlib import Path
from hashlib import sha256
from types import FunctionType,SimpleNamespace
import argparse,base64,json,os,time
from collections import Counter
from cursibench import full_study_teacher_adapter_v1 as teacher,http_transport
from cursibench import scale_action_output_v066 as output
from . import native_surface_workers_v13 as workers

def digest(raw):return sha256(raw).hexdigest()
def write(path,value):
 path=Path(path);fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'w') as f:json.dump(value,f,sort_keys=True,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
def checked_trial(plan_path,plan_sha):
 plan=workers.private_json(plan_path,plan_sha)
 workers.require(plan['schema']=='envloop-single-environment-twenty-task-trial-v1' and plan['cell_id']=='odoo-community' and
  plan['final_task_count']==20 and plan['selection_task_count']==20 and plan['train_task_count']==20 and
  plan['native_binding_sha256']==workers.public_binding()['binding_sha256'] and
  plan['models']['student']=='Qwen/Qwen3.8-27B' and plan['models']['teacher']=='gpt-6.1-sol' and
  plan['models']['initial_researcher']=='gpt-6.1-sol' and
  plan['full_six_environment_publication_claim'] is False and len(plan['final_tasks_metadata'])==20 and
  len({r['task_id'] for r in plan['final_tasks_metadata']})==20 and
  Counter(r['family'] for r in plan['final_tasks_metadata'])==Counter({'purchase':5,'inventory':5,'sales':5,'crm':5}),
  'actual_odoo20_trial_authority_required')
 return plan

def checked_proposal(path,expected,model):
 """An older model's proposal cannot enter the requested Sol 6.1 epoch."""
 path=Path(path);proposal=workers.private_json(path,expected)
 receipt=workers.private_json(path.parent/'provider-result.private.json')
 response=workers.private_json(path.parent/'raw-response.private.json',receipt['response_sha256'])
 workers.require(receipt['reported_model']==response.get('model')==model and
  receipt['provider_status']==response.get('status')=='completed' and
  bool(receipt['response_id']) and receipt['response_id']==response.get('id'),
  'actual_requested_researcher_model_completion_required')
 text='\n'.join(part['text'] for item in response.get('output',[]) if item.get('type')=='message'
  for part in item.get('content',[]) if part.get('type')=='output_text')
 workers.require(digest(text.encode())==receipt['proposal_text_sha256'] and
  json.loads(text)==proposal,'proposal_differs_from_actual_researcher_return')
 return proposal

def scoped_model_modules(binding,model):
 """Bind receipt metadata on a fresh native class, preserving shared history."""
 modules=workers._model_modules(binding);training=modules[0]
 method=training.OdooTrainEpisodeWorker.run_episode
 historical=method.__globals__['teacher']
 local_matrix=SimpleNamespace(**vars(historical.matrix))
 local_matrix.TEACHER=model
 local_teacher=SimpleNamespace(**{**vars(historical),'matrix':local_matrix})
 scoped=FunctionType(method.__code__,{**method.__globals__,'teacher':local_teacher},
  method.__name__,method.__defaults__,method.__closure__)
 scoped.__kwdefaults__=method.__kwdefaults__
 local_class=type('TrialOdooTrainEpisodeWorker',
  (training.OdooTrainEpisodeWorker,),{'run_episode':scoped})
 local_training=SimpleNamespace(**{**vars(training),'OdooTrainEpisodeWorker':local_class})
 return (local_training,*modules[1:])

def verify_trial_episode(episode,result,task,turns,active,model):
 """Reopen raw evidence using the original verifier and this trial's model."""
 verifier=teacher._verify_episode
 matrix=SimpleNamespace(**vars(teacher.matrix));matrix.TEACHER=model
 scoped=FunctionType(verifier.__code__,{**verifier.__globals__,'matrix':matrix},
  verifier.__name__,verifier.__defaults__,verifier.__closure__)
 scoped.__kwdefaults__=verifier.__kwdefaults__
 return scoped(episode,result,cell_id='odoo-community',task=task,
  runtime_sha=active.runtime_sha256,adapter_sha=active.adapter_sha256,
  verifier_sha=active.verifier_sha256,turns=turns,e2b_attempt_ids=[],
  requires_e2b=False,requires_fresh_e2b_reset=False)

def run(*,plan_path,plan_sha,worker_dir,native_binding_path,native_binding_sha,train_control_path,train_control_sha,proposal_path,proposal_sha,task_id,output_root,execute=False):
 workers.require(execute is True,'explicit_one_trial_teacher_dispatch_required')
 plan=checked_trial(plan_path,plan_sha);proposal_raw=checked_proposal(proposal_path,proposal_sha,plan['models']['initial_researcher'])
 workers.require(set(proposal_raw)=={'hypothesis','train_task_ids','teacher_request'} and task_id in proposal_raw['train_task_ids'] and
  len(set(proposal_raw['train_task_ids']))==len(proposal_raw['train_task_ids'])<=4,'actual_train_only_researcher_proposal_required')
 worker=Path(worker_dir).resolve();workers.require(worker.name=='train','teacher_public_train_partition_required')
 world=workers.private_json(worker/'private/partition_cases.json');cases={c['id']:c for group in world['cases'].values() for c in group}
 workers.require(len(cases)==20 and set(proposal_raw['train_task_ids'])<=set(cases),'proposal_outside_public_twenty_train_tasks')
 case=cases[task_id];task={'task_id':task_id,'package_sha256':next(r['package_sha256'] for r in workers.private_json(worker/'private/task_set_manifest.json')['train'] if r['task_id']==task_id),'visible_instruction':case['prompt']}
 out=Path(output_root).resolve();workers.require(out.is_relative_to(Path(__file__).resolve().parents[2]/'work') and not out.exists(),'fresh_owned_trial_teacher_namespace_required');out.mkdir(mode=0o700,parents=True)
 (out/'frames').mkdir(mode=0o700)
 # The existing source-pinned factory keeps its native/TRAIN and output checks.
 # Only its separately named campaign authority is selected for this trial.
 original=workers.train_worker
 def trial_authority(binding,path,expected):
  workers.require(Path(path).resolve()==Path(plan_path).resolve() and expected==plan_sha,'trial_authority_reference_changed')
  checked_trial(path,expected);workers.require(binding['binding_sha256']==plan['native_binding_sha256'],'trial_native_source_changed')
 namespace={**original.__globals__,'_require_campaign_ratification':trial_authority,
  '_model_modules':lambda binding:scoped_model_modules(binding,plan['models']['teacher'])}
 factory=FunctionType(original.__code__,namespace,original.__name__,original.__defaults__,original.__closure__);factory.__kwdefaults__=original.__kwdefaults__
 active=factory(native_binding_path=Path(native_binding_path),native_binding_file_sha256=native_binding_sha,
  train_control_path=Path(train_control_path),train_control_sha256=train_control_sha,
  campaign_ratification_path=Path(plan_path),campaign_ratification_sha256=plan_sha,
  worker_dir=worker,private_output_root=out.parent,enable_live=True,
  expected_runtime_sha256=plan['native_binding_sha256'],
  expected_verifier_sha256=workers.public_binding()['source_sha256s']['enterprise_fallback/odoo18/verify.py'])
 write(out.parent/(out.name+'-paid-intent.private.json'),{'schema':'envloop-odoo20-train-only-teacher-intent-v1','trial_plan_sha256':plan_sha,'task':task,'proposal_sha256':proposal_sha,'teacher_model':plan['models']['teacher'],'actual_cost_usd':None,'formal_large_study_credit':0,'same_request_replay_authorized':False})
 turns=[];counter=0
 def sample(observation,current_frame):
  nonlocal counter
  checked_trial(plan_path,plan_sha);workers.require(observation.task_id==task_id and observation.task_binding_sha256==task['package_sha256'],'teacher_observation_scope_changed')
  rendered=output.render_for_model(observation);step=observation.step;request={'model':plan['models']['teacher'],'reasoning_effort':'high','reasoning_mode':'standard','max_output_tokens':4096,
   'system_prompt':'Act only through the allowed GUI action JSON. Return exactly one JSON action. Keep a concise durable memory of values read from source documents, completed fields and next action. Never use APIs, SQL, filesystem or hidden expected answers.\n'+output.MODEL_ACTION_CONTRACT,
   'user_text':json.dumps({'instruction':rendered['instruction'],'visible_text':rendered['visible_text'],'researcher_teacher_request':proposal_raw['teacher_request']},sort_keys=True),
   'image_data_url':'data:image/png;base64,'+base64.b64encode(observation.screenshot_bytes).decode(),'image_detail':'high'}
  prefix=f'teacher-call-{counter:03d}';counter+=1;write(out/(prefix+'-request.private.json'),request);write(out/(prefix+'-intent.private.json'),{'step':step,'frame_id':observation.frame_id,'frame_sha256':observation.screenshot['sha256'],'task_id':task_id,'before_provider_post':True,'actual_cost_usd':None,'same_request_replay_authorized':False})
  started=time.monotonic();result=teacher._real_teacher_provider(request,120);write(out/(prefix+'-result.private.json'),result)
  workers.require(result['receipt'].get('status')=='completed' and result['receipt'].get('response_id') and result['receipt'].get('reported_model')==plan['models']['teacher'],'actual_teacher_provider_completion_unproved')
  action=output.normalize_model_action(result['text'],observation,current_frame_id=current_frame());result_sha=digest((out/(prefix+'-result.private.json')).read_bytes());trace={'step':step,'frame_id':observation.frame_id,'frame_sha256':observation.screenshot['sha256'],'action':action,'teacher_result_sha256':result_sha,'actual_response_id':result['receipt']['response_id'],'provider_latency_ms':round((time.monotonic()-started)*1000)}
  turns.append({'observation':observation,'action':action,'trace_row':trace,'teacher_result_sha256':result_sha})
  return {'action':action,'trace_row':trace,'teacher_result_sha256':result_sha}
 # Existing worker requires a frames-only episode folder; network evidence is
 # kept outside it so its pre-dispatch storage checks stay unchanged.
 episode=out/'episode.private';episode.mkdir(mode=0o700);(episode/'frames').mkdir(mode=0o700)
 try:
  result=active.run_episode(task=task,out_dir=episode,sample_teacher=sample,dispatch_e2b=lambda **_:(_ for _ in ()).throw(ValueError('Self-hosted Odoo never dispatches E2B')))
  write(out/'native-teacher-result.private.json',result)
  episode_sha=verify_trial_episode(episode,result,task,turns,active,plan['models']['teacher'])
  # Datums use actual teacher actions and exactly the student's vision recipe.
  vision=teacher._load_renderer();batch=teacher._render_turns('odoo-community',[task_id],[episode_sha],turns,vision)
  import pickle
  raw=pickle.dumps({'datums':batch.datums,'prompts':batch.prompts,'receipt':batch.receipt},protocol=5);path=out/'trusted-rendered-train.private.pkl';fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
  write(out/'rendered-train-receipt.private.json',{'schema':'envloop-odoo20-real-teacher-render-v1','task_id':task_id,'source_split':'train','teacher_turns':len(turns),'rendered_sha256':digest(raw),'renderer_receipt':batch.receipt,'trial_plan_sha256':plan_sha,'proposal_sha256':proposal_sha,'native_saved_state_checked':True,'formal_large_study_credit':0})
  return {'status':'actual_teacher_native_saved_reset_and_rendered','task_id':task_id,'teacher_turns':len(turns),'rendered_sha256':digest(raw)}
 finally:
  http_transport.close()
  write(out/'teacher-provider-close.private.json',{'close_function':'cursibench.http_transport.close','real_close_call_returned':True,'actual_cost_usd':None,'formal_large_study_credit':0})

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for field in ('plan-path','plan-sha','worker-dir','native-binding-path','native-binding-sha','train-control-path','train-control-sha','proposal-path','proposal-sha','task-id','output-root'):p.add_argument('--'+field,required=True)
 p.add_argument('--execute',action='store_true');a=vars(p.parse_args());print(json.dumps(run(**a),sort_keys=True))
if __name__=='__main__':main()
