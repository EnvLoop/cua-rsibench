"""Prospective control trios through the identical native guarded backend.

Reference selectors choose visible targets; mutations are unchanged normalized
GUI primitives dispatched by the teacher/student native safety gate.
"""
from __future__ import annotations
import argparse,json,inspect,textwrap,asyncio,time
from playwright.async_api import Error as PlaywrightError
from contextlib import contextmanager
from unittest.mock import patch
from hashlib import sha256
from pathlib import Path
from cursibench.scale_action_output_v066 import normalize_model_action
from . import bootstrap,verify,gui_controls,gui_workflows
from . import prospective_final_controls_v066 as legacy_controls
from . import full_git_final_worker_v1 as final
from . import v066_uniform_task_runtime_v14 as world
from . import v066_uniform_model_workers_v14 as models

_TRANSIENT_READ_ERRORS = (
 'Execution context was destroyed',
 'Cannot find context with specified id',
 'Element is not attached to the DOM',
)
_PAINTED = """el=>{
 const r=el.getBoundingClientRect(),s=getComputedStyle(el),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
 return el.isConnected&&!el.disabled&&r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'&&!!hit&&(hit===el||el.contains(hit));
}"""

async def wait_painted_reference(page,locator,*,timeout_seconds=30.0,poll_seconds=0.1,stable_seconds=2.0):
 """Wait for the requested native field to stay painted after hydration."""
 deadline=time.monotonic()+timeout_seconds;previous=None;stable_since=None
 async def current_painted():
  handles=await locator.element_handles()
  world.require(len(handles)<=1,'Reference native target ambiguous')
  if not handles:return None
  return await handles[0].evaluate("""el=>{
   const r=el.getBoundingClientRect(),s=getComputedStyle(el),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
   const painted=el.isConnected&&!el.disabled&&r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'&&!!hit&&(hit===el||el.contains(hit));
   return painted?{bounds:[r.x,r.y,r.width,r.height],tag:el.tagName,role:el.getAttribute('role'),type:el.getAttribute('type'),documentReady:document.readyState}:null;
  }""")
 while True:
  remaining=deadline-time.monotonic()
  if remaining<=0:raise ValueError('Reference native target did not become stable within30 seconds')
  sample=None
  try:sample=await asyncio.wait_for(current_painted(),timeout=remaining)
  except PlaywrightError as error:
   if not any(message in str(error) for message in _TRANSIENT_READ_ERRORS):raise
  except TimeoutError:raise ValueError('Reference native target did not become stable within30 seconds') from None
  tick=time.monotonic()
  if sample is None or sample.get('documentReady')!='complete':previous=None;stable_since=None
  elif sample!=previous:previous=sample;stable_since=tick
  elif stable_since is not None and tick-stable_since>=stable_seconds:return
  await asyncio.sleep(min(poll_seconds,max(0,deadline-time.monotonic())))

class Locator:
 def __init__(self,original,active):self.original,self.active=original,active
 @property
 def first(self):return Locator(self.original.first,self.active)
 @property
 def last(self):return Locator(self.original.last,self.active)
 def __getattr__(self,key):
  value=getattr(self.original,key)
  if key in ['locator','get_by_role','get_by_text','get_by_placeholder','filter','nth']:
   return lambda *a,**kw:Locator(value(*a,**kw),self.active)
  return value
 async def action(self,kind,**fields):
  guard=self.active.guard
  await wait_painted_reference(self.active.page,self.original)
  frame=await guard.observe('')
  handles=await self.original.element_handles();world.require(len(handles)==1,'Reference target must be one current native element')
  box=await handles[0].bounding_box();world.require(box is not None,'Reference target missing current geometry')
  # Unlabelled native fields have no model-visible control ref. Choose the
  # same actual coordinate primitive available to screenshot-only actors.
  ref=await handles[0].get_attribute('data-envloop-native-ref')
  # A labelled current native ref uses the identical model-visible primitive.
  # Unlabelled fields keep the observed physical coordinate fallback.
  refs={row.ref for row in frame.observation.controls if row.visible and row.enabled}
  target={'ref':ref} if ref in refs else {'x':round(box['x']+box['width']/2),'y':round(box['y']+box['height']/2)}
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
  if key in ['locator','get_by_role','get_by_text','get_by_placeholder']:return lambda *a,**kw:Locator(value(*a,**kw),self.active)
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
 if family=='cross_record_issue_triage':
  source=textwrap.dedent(inspect.getsource(gui_controls._gui_issue_triage))
  needle='    await labels.get_by_role("option").filter(has_text=label).click()'
  world.require(source.count(needle)==1,'Frozen reference issue-label branch changed')
  source=source.replace(needle,'    await labels.get_by_placeholder("Search", exact=True).fill(label)\n    await labels.get_by_role("option", name=label, exact=True).click()')
  assignee_needle='    await assignee.get_by_role("option").filter(has_text="@" + user).click()'
  world.require(source.count(assignee_needle)==1,'Frozen reference assignee branch changed')
  source=source.replace(assignee_needle,'    await assignee.get_by_role("combobox").fill(user)\n'+assignee_needle)
  namespace={};exec(compile(source,'<gitlab-current-reference-label-search-v18>','exec'),dict(gui_controls._gui_issue_triage.__globals__),namespace)
  return await namespace['_gui_issue_triage'](page,project,progress,task,variant,folder)
 if family=='release_milestone_coordination':return await gui_workflows.milestone(page,project,progress,folder,wrong_due=variant=='wrong_due')
 if family=='approved_merge_request_merge':return await gui_workflows.merge_request(page,project,progress,folder,wrong_mr=variant=='stale')
 if family=='least_privilege_access_handoff':return await gui_workflows.access_handoff(page,project,progress,folder,overprivileged=variant=='overprivileged')
 if family=='ci_and_runbook_reconciliation':return await gui_workflows.ci_and_runbook(page,project,progress,folder,partial_negative=variant=='partial')
 raise ValueError('Unsupported unchanged final workflow')


def run(*,plan_path,permit,binding_path,out,controller_review,controller_review_sha256,first_index=0,maximum=100,execute=False):
 world.require(execute is True,'Reviewed final control execution required')
 plan,_=world.checked_plan(plan_path);binding=models.validate_binding(models.private_json(binding_path))
 raw_review=world.cold.source.private(controller_review);review=json.loads(raw_review)
 world.require(sha256(raw_review).hexdigest()==controller_review_sha256 and
  review.get('schema')=='gitlab-additive-reference-source-review-v19' and review.get('root_reviewed') is True and
  review.get('plan_sha256')==sha256(world.cold.source.private(plan_path)).hexdigest() and
  review.get('native_binding_sha256')==binding['binding_sha256'] and
  review.get('reference_source_sha256')==sha256(Path(__file__).read_bytes()).hexdigest() and
  review.get('native_runtime_epoch')=='v14_effective_svwait60','Exact additional reference source review required')
 world.require(type(first_index) is int and type(maximum) is int and 0<=first_index<100 and 0<maximum<=100-first_index,'Bounded unchanged roster range required')
 out.mkdir(mode=0o700,exist_ok=False);world.write(out/'intent.private.json',{'plan_sha256':world.cold.source.sha(world.cold.source.private(plan_path)),
  'first_index':first_index,'count':maximum,'whole_source_binding_sha256':binding['binding_sha256'],'reference_source_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),'native_runtime_epoch':'v14_effective_svwait60','model_calls':0,'historical_credit':0})
 roster=plan['rosters']['final_candidate_unsealed'];rows=[]
 try:
  for ordinal in range(first_index,first_index+maximum):
   ledger=plan_path.parent/'final-control-intents-v19';ledger.mkdir(mode=0o700,exist_ok=True)
   world.write(ledger/f'control-{ordinal:03d}.private.json',{'ordinal':ordinal,'plan_sha256':world.cold.source.sha(world.cold.source.private(plan_path)),'output_root':str(out),'one_use':True})
   identity=roster[ordinal];directory=out/f'task-{ordinal:03d}';directory.mkdir(mode=0o700)
   task_results=[]
   # Each case uses the same physical backend/guard/full-Git oracle as every slot.
   for case_index,(name,variant,expected) in enumerate(legacy_controls.CASES[models.private_json(plan_path.parent/'cohort-plan.private.json')['task_roster'][ordinal]['template_group']]):
    folder=directory/f'case-{case_index:02d}-{name}';folder.mkdir(mode=0o700);(folder/'artifacts').mkdir(mode=0o700)
    with models.source_scope():backend=models.FullGitBackend(final._SealedFinalBackend(roster),partition='final_candidate_unsealed',binding=binding,cohort_freeze_path=plan_path)
    backend.permit_path=permit;backend.phase='final-controls';backend.set_output_root(folder)
    with models.source_scope(),backend.open(identity) as active:
     task=active.original_task
     try:active.loop.call(workflow(active,task,variant,folder))
     except BaseException:
      world.cold.write_raw(folder/'reference-failure-native.png',active.loop.call(active.page.screenshot(type='png')))
      world.write(folder/'reference-failure-native.private.json',active.loop.call(active.guard.meta()))
      raise
     observation=active.observe(memory='');active.dispatch(normalize_model_action('{"type":"finish","memory":""}',observation,current_frame_id=observation.frame_id))
     saved=active.read_saved_state();world.require(saved['independent_score']['reward']==expected,'Prospective control score changed')
     world.write(folder/'artifacts'/'baseline.private.json',active.baseline_semantic);world.write(folder/'artifacts'/'saved-artifact.private.json',saved)
    world.require(active.post_restore_exact and active.environment_terminated,'Prospective control cold reset failed')
    record={'case':name,'score':expected,'full_git_tree_verified':True,'cold_reset_exact':True,'whole_source_binding_sha256':binding['binding_sha256'],'model_calls':0}
    world.write(folder/'result.private.json',record);task_results.append(record)
   record={'ordinal':ordinal,'cases':task_results,'historical_credit':0,'official_final_admitted':0}
   world.write(directory/'trio.private.json',record);rows.append(record)
  result={'reference_source_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),'native_runtime_epoch':'v14_effective_svwait60','status':'new_uniform_original_controls_completed','completed_count':len(rows),'rows':rows,'model_calls':0,'official_final_admitted':0}
  world.write(out/'result.private.json',result);return {'status':result['status'],'completed_count':len(rows),'result_sha256':world.cold.source.sha(world.cold.source.private(out/'result.private.json'))}
 except BaseException as error:
  world.write(out/'failure.private.json',{'status':'terminal_uniform_control_failure_no_retry','completed_count':len(rows),'error_type':type(error).__name__,'model_calls':0});raise


def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['plan','permit','binding','out']:p.add_argument('--'+name,required=True,type=Path)
 p.add_argument('--controller-review',required=True,type=Path);p.add_argument('--controller-review-sha256',required=True)
 p.add_argument('--first-index',type=int,default=0);p.add_argument('--maximum',type=int,default=100);p.add_argument('--execute',action='store_true');a=p.parse_args()
 print(json.dumps(run(plan_path=a.plan,permit=a.permit,binding_path=a.binding,out=a.out,controller_review=a.controller_review,controller_review_sha256=a.controller_review_sha256,first_index=a.first_index,maximum=a.maximum,execute=a.execute),sort_keys=True))

if __name__=='__main__':main()
