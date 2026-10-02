"""Prospective control trios through the identical native guarded backend.

Reference selectors choose visible targets; mutations are unchanged normalized
GUI primitives dispatched by the teacher/student native safety gate.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
from cursibench.scale_action_output_v066 import normalize_model_action
from . import bootstrap,verify,gui_controls,gui_workflows
from . import prospective_final_controls_v066 as legacy_controls
from . import full_git_final_worker_v1 as final
from . import v066_uniform_task_runtime_v12 as world
from . import v066_uniform_model_workers_v12 as models

class Locator:
 def __init__(self,original,active):self.original,self.active=original,active
 @property
 def first(self):return Locator(self.original.first,self.active)
 @property
 def last(self):return Locator(self.original.last,self.active)
 def __getattr__(self,key):
  value=getattr(self.original,key)
  if key in ['locator','get_by_role','get_by_text','filter','nth']:
   return lambda *a,**kw:Locator(value(*a,**kw),self.active)
  return value
 async def action(self,kind,**fields):
  guard=self.active.guard;frame=await guard.observe('')
  handle=await self.original.element_handle();ref=await handle.get_attribute('data-envloop-native-ref')
  if ref is not None:target={'ref':ref}
  else:
   box=await handle.bounding_box();world.require(box is not None,'Reference target missing current geometry')
   target={'x':round(box['x']+box['width']/2),'y':round(box['y']+box['height']/2)}
  action=normalize_model_action(json.dumps({'type':kind,'target':target,'memory':'',**fields}),frame.observation,current_frame_id=frame.observation.frame_id)
  result=await guard.dispatch(action);world.require(result=={'status':'applied','code':'ok'},'Reference action rejected by uniform policy')
 async def click(self,**kwargs):await self.action('click')
 async def dblclick(self,**kwargs):await self.action('double_click')
 async def fill(self,text,**kwargs):await self.action('type',text=text,mode='fill')
 async def press(self,key,**kwargs):await self.action('key',key=key)

class Keyboard:
 def __init__(self,active):self.active=active
 async def press(self,key):
  guard=self.active.guard;frame=await guard.observe('')
  action=normalize_model_action(json.dumps({'type':'key','key':key,'memory':''}),frame.observation,current_frame_id=frame.observation.frame_id)
  world.require(await guard.dispatch(action)=={'status':'applied','code':'ok'},'Reference keyboard action rejected')

class Page:
 def __init__(self,active):self.active,self.original=active,active.page;self.keyboard=Keyboard(active)
 def __getattr__(self,key):
  value=getattr(self.original,key)
  if key in ['locator','get_by_role','get_by_text']:return lambda *a,**kw:Locator(value(*a,**kw),self.active)
  if key=='goto':
   async def goto(url,**kwargs):
    world.require(url.startswith(world.runtime.BASE+self.active.project_path+'/'),'Reference navigation left owned project')
    return await value(url,**kwargs)
   return goto
  if key=='screenshot':
   async def screenshot(**kwargs):
    path=kwargs.pop('path',None);raw=await value(**kwargs)
    if path is not None:world.cold.write_raw(Path(path),raw)
    return raw
   return screenshot
  return value

async def workflow(active,task,variant,folder):
 project,progress=verify._context(task);page=Page(active);family=task['template_group']
 if family=='cross_record_issue_triage':return await gui_controls._gui_issue_triage(page,project,progress,task,variant,folder)
 if family=='release_milestone_coordination':return await gui_workflows.milestone(page,project,progress,folder,wrong_due=variant=='wrong_due')
 if family=='approved_merge_request_merge':return await gui_workflows.merge_request(page,project,progress,folder,wrong_mr=variant=='stale')
 if family=='least_privilege_access_handoff':return await gui_workflows.access_handoff(page,project,progress,folder,overprivileged=variant=='overprivileged')
 if family=='ci_and_runbook_reconciliation':return await gui_workflows.ci_and_runbook(page,project,progress,folder,partial_negative=variant=='partial')
 raise ValueError('Unsupported unchanged final workflow')


def run(*,plan_path,permit,binding_path,out,first_index=0,maximum=100,execute=False):
 world.require(execute is True,'Reviewed final control execution required')
 plan,_=world.checked_plan(plan_path);binding=models.validate_binding(models.private_json(binding_path))
 world.require(type(first_index) is int and type(maximum) is int and 0<=first_index<100 and 0<maximum<=100-first_index,'Bounded unchanged roster range required')
 out.mkdir(mode=0o700,exist_ok=False);world.write(out/'intent.private.json',{'plan_sha256':world.cold.source.sha(world.cold.source.private(plan_path)),
  'first_index':first_index,'count':maximum,'whole_source_binding_sha256':binding['binding_sha256'],'model_calls':0,'historical_credit':0})
 roster=plan['rosters']['final_candidate_unsealed'];rows=[]
 try:
  for ordinal in range(first_index,first_index+maximum):
   ledger=plan_path.parent/'final-control-intents';ledger.mkdir(mode=0o700,exist_ok=True)
   world.write(ledger/f'control-{ordinal:03d}.private.json',{'ordinal':ordinal,'plan_sha256':world.cold.source.sha(world.cold.source.private(plan_path)),'output_root':str(out),'one_use':True})
   identity=roster[ordinal];directory=out/f'task-{ordinal:03d}';directory.mkdir(mode=0o700)
   task_results=[]
   # Each case uses the same physical backend/guard/full-Git oracle as every slot.
   for case_index,(name,variant,expected) in enumerate(legacy_controls.CASES[models.private_json(plan_path.parent/'cohort-plan.private.json')['task_roster'][ordinal]['template_group']]):
    folder=directory/f'case-{case_index:02d}-{name}';folder.mkdir(mode=0o700);(folder/'artifacts').mkdir(mode=0o700)
    with models.source_scope():backend=models.FullGitBackend(final._SealedFinalBackend(roster),partition='final_candidate_unsealed',binding=binding,cohort_freeze_path=plan_path)
    backend.permit_path=permit;backend.phase='final-controls';backend.set_output_root(folder)
    with models.source_scope(),backend.open(identity) as active:
     task=active.original_task;active.loop.call(workflow(active,task,variant,folder))
     observation=active.observe(memory='');active.dispatch(normalize_model_action('{"type":"finish","memory":""}',observation,current_frame_id=observation.frame_id))
     saved=active.read_saved_state();world.require(saved['independent_score']['reward']==expected,'Prospective control score changed')
     world.write(folder/'artifacts'/'baseline.private.json',active.baseline_semantic);world.write(folder/'artifacts'/'saved-artifact.private.json',saved)
    world.require(active.post_restore_exact and active.environment_terminated,'Prospective control cold reset failed')
    record={'case':name,'score':expected,'full_git_tree_verified':True,'cold_reset_exact':True,'whole_source_binding_sha256':binding['binding_sha256'],'model_calls':0}
    world.write(folder/'result.private.json',record);task_results.append(record)
   record={'ordinal':ordinal,'cases':task_results,'historical_credit':0,'official_final_admitted':0}
   world.write(directory/'trio.private.json',record);rows.append(record)
  result={'status':'new_uniform_original_controls_completed','completed_count':len(rows),'rows':rows,'model_calls':0,'official_final_admitted':0}
  world.write(out/'result.private.json',result);return {'status':result['status'],'completed_count':len(rows),'result_sha256':world.cold.source.sha(world.cold.source.private(out/'result.private.json'))}
 except BaseException as error:
  world.write(out/'failure.private.json',{'status':'terminal_uniform_control_failure_no_retry','completed_count':len(rows),'error_type':type(error).__name__,'model_calls':0});raise


def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['plan','permit','binding','out']:p.add_argument('--'+name,required=True,type=Path)
 p.add_argument('--first-index',type=int,default=0);p.add_argument('--maximum',type=int,default=100);p.add_argument('--execute',action='store_true');a=p.parse_args()
 print(json.dumps(run(plan_path=a.plan,permit=a.permit,binding_path=a.binding,out=a.out,first_index=a.first_index,maximum=a.maximum,execute=a.execute),sort_keys=True))

if __name__=='__main__':main()
