"""One actual TRAIN positive/negative/repeated-positive through uniform gate.

Model/provider calls are zero. The reference controller chooses a TRAIN label;
all physical actions use the same current native envelope as teacher/student.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
from cursibench.scale_action_output_v066 import normalize_model_action
from . import bootstrap,verify
from . import v066_uniform_task_runtime_v13 as world
from . import v066_uniform_model_workers_v13 as models



# Reference controls choose a painted native UI target; a hidden/clipped option
# cannot be replaced by the physically different footer underneath it.
async def wait_painted_reference(page,locator):
 for sample in range(300):
  handles=await locator.element_handles()
  world.require(len(handles)<=1,'Reference native target ambiguous')
  if handles:
   safe=await handles[0].evaluate("""el=>{
    const r=el.getBoundingClientRect(),s=getComputedStyle(el),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
    return el.isConnected&&!el.disabled&&r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'&&!!hit&&(hit===el||el.contains(hit));
   }""")
   if safe:return
  await page.wait_for_timeout(100)
 raise ValueError('Reference native target did not become painted within30 seconds')


def _task(plan):
 private=Path(plan['private_root']);data=json.loads(world.cold.source.private(private/'world-private.json'))
 rows=[r for r in bootstrap.all_tasks(data) if r['partition']=='train' and r['template_group']=='issue_label_from_alert']
 world.require(len(rows)==5,'TRAIN label corpus shape changed')
 task=sorted(rows,key=lambda r:r['task_id'])[0]
 return task,{'task_id':task['task_id'],'package_sha256':world.factory.sha256(world.factory.canonical(task)),'visible_instruction':task['prompt']}


def run(*,plan_path,permit,binding_path,out,execute=False):
 world.require(execute is True,'Exact reviewed TRAIN qualification execution required')
 plan,_=world.checked_plan(plan_path);binding=models.validate_binding(models.private_json(binding_path))
 world.write(plan_path.parent/'train-qualification-intent.private.json',{'qualification_out':str(out),'plan_sha256':world.cold.source.sha(world.cold.source.private(plan_path)),'one_use':True})
 world.require(not out.exists() and not out.is_symlink(),'Fresh one-use TRAIN qualification output required');out.mkdir(mode=0o700)
 world.write(out/'intent.private.json',{'plan_sha256':world.cold.source.sha(world.cold.source.private(plan_path)),
  'binding_sha256':binding['binding_sha256'],'cases':[1.0,0.0,1.0],'model_calls':0,'one_use':True})
 original,identity=_task(plan);results=[]
 try:
  for index,(name,issue_key,expected) in enumerate([('positive-1','active',1.0),('negative','historical_duplicate',0.0),('positive-2','active',1.0)]):
   folder=out/f'case-{index:02d}-{name}';folder.mkdir(mode=0o700);(folder/'artifacts').mkdir(mode=0o700)
   backend=models.qualification_backend(plan_path=plan_path,permit_path=permit,binding=binding,output_root=folder)
   with models.source_scope(),backend.open(identity) as active:
    project,progress=verify._context(original);page=active.page
    active.loop.call(page.goto(world.runtime.BASE+'/'+project['full_path']+'/-/issues/'+str(progress['issue_iids'][issue_key]),wait_until='domcontentloaded',timeout=90000))
    label=original['oracle']['expected_priority'];labels=page.locator('[data-testid="work-item-labels"]')
    def click(locator):
     # A reference action is chosen only after its native UI exists. Waiting
     # is observation-only, bounded, and does not mutate or score the world.
     active.loop.call(wait_painted_reference(active.page,locator))
     observation=active.observe(memory='')
     async def ref():
      handles=await locator.element_handles()
      world.require(len(handles)==1,'Reference control needs one current native element')
      box=await handles[0].bounding_box()
      world.require(box is not None and box['width']>0 and box['height']>0,'Reference control current native geometry missing')
      return {'x':round(box['x']+box['width']/2),'y':round(box['y']+box['height']/2)}
     target=active.loop.call(ref())
     action=normalize_model_action(json.dumps({'type':'click','target':target,'memory':''}),observation,current_frame_id=observation.frame_id)
     active.dispatch(action)
     world.require(active.guard.last_result=={'status':'applied','code':'ok'},'Reference control action rejected')
    click(labels.locator('[data-testid="edit-button"]'))
    search=labels.get_by_placeholder('Search',exact=True)
    active.loop.call(wait_painted_reference(page,search));observation=active.observe(memory='')
    box=active.loop.call(search.bounding_box());world.require(box is not None,'Reference search current geometry missing')
    target={'x':round(box['x']+box['width']/2),'y':round(box['y']+box['height']/2)}
    active.dispatch(normalize_model_action(json.dumps({'type':'type','target':target,'mode':'fill','text':label,'memory':''}),observation,current_frame_id=observation.frame_id))
    world.require(active.guard.last_result=={'status':'applied','code':'ok'},'Reference search action rejected')
    click(labels.get_by_role('option',name=label,exact=True))
    click(labels.locator('[data-testid="apply-button"]'))
    active.loop.call(labels.locator('.gl-spinner').wait_for(state='hidden',timeout=30000))
    active.loop.call(page.reload(wait_until='domcontentloaded',timeout=90000))
    active.loop.call(labels.locator('[data-testid="'+label+'"]').wait_for(timeout=30000))
    observation=active.observe(memory='');active.dispatch(normalize_model_action(json.dumps({'type':'finish','memory':''}),observation,current_frame_id=observation.frame_id))
    saved=active.read_saved_state();world.write(folder/'artifacts'/'baseline.private.json',active.baseline_semantic);world.write(folder/'artifacts'/'saved-artifact.private.json',saved);world.require(saved['independent_score']['reward']==expected,'New TRAIN control verdict changed')
   world.require(active.post_restore_exact and active.environment_terminated,'New TRAIN control failed cold reset')
   record={'case':name,'expected_score':expected,'actual_score':saved['independent_score']['reward'],
    'full_git_tree_verified':saved['full_git_tree_verified'],'cold_reset_exact':True,'native_policy_sha256':models.guard_policy.POLICY_SHA,
    'whole_source_binding_sha256':binding['binding_sha256'],'model_calls':0,'historical_credit':0}
   world.write(folder/'result.private.json',record);results.append(record)
  result={'schema':'envloop-gitlab-uniform-train-qualification-v13','status':'actual_train_1_0_1_uniform_runtime_and_native_safety',
   'plan_sha256':world.cold.source.sha(world.cold.source.private(plan_path)),'source_sha256s':plan['source_sha256s'],
   'whole_source_binding_sha256':binding['binding_sha256'],'cases':results,'selection_final_dispatched':0,'model_calls':0,'official_final_admitted':0}
  world.write(out/'result.private.json',result);return {'status':result['status'],'result_sha256':world.cold.source.sha(world.cold.source.private(out/'result.private.json'))}
 except BaseException as error:
  world.write(out/'failure.private.json',{'status':'terminal_train_qualification_failure_no_retry','error_type':type(error).__name__,
   'model_calls':0,'selection_final_dispatched':0,'official_final_admitted':0});raise


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mode',choices=['run','audit','accept'],default='run');p.add_argument('--accept-root-review',action='store_true');p.add_argument('--note',default='');p.add_argument('--plan',required=True,type=Path);p.add_argument('--permit',required=True,type=Path)
 p.add_argument('--binding',required=True,type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--execute',action='store_true');a=p.parse_args()
 if a.mode=='run':value=run(plan_path=a.plan,permit=a.permit,binding_path=a.binding,out=a.out,execute=a.execute)
 elif a.mode=='audit':value=audit(plan_path=a.plan,binding_path=a.binding,out=a.out)
 else:value=accept(plan_path=a.plan,binding_path=a.binding,out=a.out,accepted=a.accept_root_review,note=a.note)
 print(json.dumps(value,sort_keys=True))



def audit(*,plan_path,binding_path,out):
 from cursibench import native_surface_guard_policy_v1 as policy
 plan,_=world.checked_plan(plan_path);binding=models.validate_binding(models.private_json(binding_path))
 result=json.loads(world.cold.source.private(out/'result.private.json'))
 world.require(not (out/'failure.private.json').exists() and result['status']=='actual_train_1_0_1_uniform_runtime_and_native_safety' and
  result['plan_sha256']==world.cold.source.sha(world.cold.source.private(plan_path)) and result['source_sha256s']==plan['source_sha256s'] and
  result['whole_source_binding_sha256']==binding['binding_sha256'],'Native TRAIN result/source binding changed')
 original,identity=_task(plan);count=0
 for index,expected in enumerate([1.0,0.0,1.0]):
  record=result['cases'][index];folder=out/f"case-{index:02d}-{record['case']}"
  artifacts=folder/'artifacts';saved=models.private_json(artifacts/'saved-artifact.private.json');before=models.private_json(artifacts/'baseline.private.json')
  with models.source_scope():models._verify_saved_proof(artifacts,saved,identity,before['business_snapshot'],binding,
   cohort_source_file_sha256=world.cold.source.sha(world.cold.source.private(plan_path)))
  world.require(saved['independent_score']['reward']==record['actual_score']==expected and record['cold_reset_exact'] is True,'TRAIN saved verdict changed')
  local_count=0
  native=artifacts/'native-runtime'
  for group in ['protected','seed']:
   world.require(world.cold.source.private(native/(group+'-before.private.json'))==world.cold.source.private(native/(group+'-exit.private.json')),
    'TRAIN native protected source/seed exit changed')
  world.require(json.loads(world.cold.source.private(native/'parent-teardown.private.json'))['owned_parent_absent'] is True,
   'TRAIN owned VM parent remains')
  resumed=json.loads(world.cold.source.private(native/'original-resumed.private.json'))
  world.require(resumed['same_identity'] is True and resumed['exact_business_snapshot'] is True and resumed['healthy'] is True,
   'TRAIN original runtime was not restored')
  for generation in [0,1]:
   snapshot=json.loads(world.cold.source.private(native/f'cycle-{generation}-snapshot.private.json'))
   attrs=json.loads(world.cold.source.private(native/f'cycle-{generation}-native-attributes.private.json'))
   docker_state=json.loads(world.cold.source.private(native/f'cycle-{generation}-state.private.json'))
   world.cold.validate_attributes(attrs,started_at=docker_state['StartedAt'])
   world.require(snapshot==before['business_snapshot'] and attrs['effective_settings']==world.cold.EXPECTED_SETTINGS,
    'TRAIN task reset SQL/native profile changed')
  for path in sorted((artifacts/'native-safety').glob('turn-*/receipt.private.json')):
   receipt=policy.validate_receipt(json.loads(world.cold.source.private(path)));prefix=path.parent
   world.require(receipt['status']=='applied' and receipt['driver_result']=='succeeded','Reference control native action was not applied')
   for phase in ['observation','predispatch']:
    envelope=json.loads(world.cold.source.private(prefix/(phase+'-envelope.private.json')));policy.validate_envelope(envelope)
    for key in ['raw_image','raw_envelope']:
     ref=envelope[key];raw=world.cold.source.private(artifacts/'native-safety'/ref['path'])
     world.require(world.cold.source.sha(raw)==ref['sha256'],'Native TRAIN raw safety evidence changed')
   count+=1;local_count+=1
  world.require(local_count>0,'No native safety receipts retained')
 return {'status':'saved_train_1_0_1_uniform_native_proof_replayed','result_sha256':world.cold.source.sha(world.cold.source.private(out/'result.private.json')),
  'native_dispatch_receipts':count,'model_calls':0,'selection_final_dispatched':0}


def accept(*,plan_path,binding_path,out,accepted=False,note=''):
 world.require(accepted is True and note.strip(),'Independent exact native qualification review required')
 actual=audit(plan_path=plan_path,binding_path=binding_path,out=out);plan,_=world.checked_plan(plan_path)
 value={'accepted':True,'note':note,'plan_sha256':world.cold.source.sha(world.cold.source.private(plan_path)),
  'source_sha256s':plan['source_sha256s'],'binding_path':str(binding_path),'qualification_out':str(out),'result_sha256':actual['result_sha256'],
  'historical_credit':0,'model_calls':0}
 return {'acceptance_sha256':world.write(plan_path.parent/'train-qualification-root-accepted.private.json',value),'model_calls':0}


if __name__=='__main__':main()
