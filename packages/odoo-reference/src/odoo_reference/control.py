"""Public known-answer GUI controls. Every actor mutation uses the native guard."""
from pathlib import Path
import json,hashlib,os,sys
from .config import canonical
CLEANUP_KEYS={'SQL_exact','protected_filestore_exact','protected_store_paths_exact','physical_before_web_restart_exact','business_before_web_restart_exact','services_restored','checkpoint_bytes_unchanged'}
def validate_result(value):
 if set(value)!={'schema','scores','initial_failure','cleanup','models','training','formal_admissions'}:raise RuntimeError('public_result_schema_invalid')
 if value['schema']!='public-odoo-reference-result-v1' or value['initial_failure'] is not None:raise RuntimeError('public_initial_failure_present')
 if any(type(x) is not int for x in value['scores']) or value['scores']!=[0,1,0]:raise RuntimeError('public_score_trio_invalid')
 c=value['cleanup']
 if not isinstance(c,dict) or set(c)!=CLEANUP_KEYS or any(c[k] is not True for k in CLEANUP_KEYS):raise RuntimeError('public_cleanup_not_exact_verified')
 if type(value['models']) is not int or value['models']!=0 or value['training'] is not False or type(value['formal_admissions']) is not int or value['formal_admissions']!=0:raise RuntimeError('public_no_model_no_training_contract_changed')
 return True

def write(path,value):
 path=Path(path);raw=value if isinstance(value,bytes) else canonical(value);path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
 if path.parent.is_symlink():raise RuntimeError('private_evidence_parent_symlink')
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 return {'path':str(path.absolute()),'sha256':hashlib.sha256(raw).hexdigest()}
def failure(error,phase):
 return {'phase':phase,'type':type(error).__name__,'message_sha256':hashlib.sha256(str(error).encode()).hexdigest(),'same_action_retry_authorized':False}
class Journal:
 def __init__(self,adapter,page,out):self.adapter=adapter;self.page=page;self.out=Path(out);self.trace=[]
 def act(self,kind,phase,locator=None,capture_control=False,**fields):
  if len(self.trace)>=90:raise RuntimeError('original90_action_limit')
  obs,_=self.adapter.observe_for_model(memory='');payload={'type':kind,**fields};selected=None
  if locator is not None:
   handles=locator.element_handles()
   try:
    if len(handles)!=1:raise RuntimeError('current_native_locator_not_unique')
    box=handles[0].bounding_box()
    if capture_control:
     from .focus import control_script,valid_tab
     selected=handles[0].evaluate(control_script())
     if not valid_tab(selected) or selected['element_ref'] not in [c.ref for c in obs.controls]:raise RuntimeError('public_v3_tab_not_in_current_native_observation')
   finally:
    for handle in handles:handle.dispose()
   if not box or box['width']<=0 or box['height']<=0:raise RuntimeError('current_native_locator_not_visible')
   w,h=obs.screenshot['width'],obs.screenshot['height']
   if box['x']<0 or box['y']<0 or box['x']+box['width']>w or box['y']+box['height']>h:raise RuntimeError('candidate_outside_original_viewport_no_clamp')
   payload['target']={'x':int(box['x']+box['width']/2),'y':int(box['y']+box['height']/2)}
  action=self.adapter.parse_current_action(json.dumps(payload));step=len(self.trace)
  frame=write(self.out/f'frames/step-{step:03d}.png',obs.screenshot_bytes)
  intent=write(self.out/f'actions/step-{step:03d}-intent.private.json',{'phase':phase,'normalized_action':action,'frame_ref':frame,**({'selected_native_control':selected} if selected is not None else {})})
  result=self.adapter.dispatch(action)
  if result.get('status')!='applied':raise RuntimeError('native_driver_not_applied')
  write(self.out/f'actions/step-{step:03d}-result.private.json',{'intent_ref':intent,'dispatch':result})
  self.trace.append({'step':step,'phase':phase,'frame':frame,'contract':result['public_contract_receipt']});return frame

def select_all_key():return 'Meta+A' if sys.platform=='darwin' else 'Control+A'
def fill(page,journal,locator,text,phase):
 journal.act('click',phase,locator=locator);journal.act('key',phase,key=select_all_key());journal.act('type',phase,text=str(text),mode='insert')
def open_order(page,journal,name,phase):
 search=page.get_by_role('searchbox');search.wait_for();fill(page,journal,search,name,phase);journal.act('key',phase,key='Enter')
 row=page.get_by_role('cell',name=name,exact=True);row.wait_for();journal.act('click',phase,locator=row);page.wait_for_url('**/odoo/purchase/*')
def show_source(page,journal,case,phase):
 button=page.locator('button.o-mail-Chatter-attachFiles');button.wait_for();journal.act('click',phase,locator=button)
 source=page.get_by_text(case['id']+'-source.pdf',exact=True);source.wait_for();journal.act('click',phase,locator=source)
 page.locator('iframe.o-FileViewer-view').wait_for();frame=journal.act('wait',phase,duration_ms=100)
 write(journal.out/'source-frame-ref.json',frame);close=page.locator('[title="Close (Esc)"]');journal.act('click',phase,locator=close);close.wait_for(state='hidden')
def edit_price(page,journal,case,phase):
 form=page.locator('.o_form_view').filter(visible=True);cell=form.locator('tr').filter(has_text=case['sku']).locator('td[name="price_unit"]').filter(visible=True);cell.wait_for();journal.act('click',phase,locator=cell)
 editor=form.locator('td[name="price_unit"] input').filter(visible=True);editor.wait_for();fill(page,journal,editor,case['expected_price'],phase);journal.act('key',phase,key='Tab')
 from enterprise_fallback.odoo18.native_reference_save_v7 import save_original_form
 manual_save=save_original_form(page,journal,phase)
 from .focus import restore_owned_focus
 restore_owned_focus(page,journal,phase,manual_save)
 from .observer import instrumented_observer
 instrumented_observer().wait_positive_priority_autosave(page,journal,phase)

def services(workspace):
 from .infra import compose
 return sorted(compose(workspace,'ps','--status','running','--services').stdout.decode().split())
def readback(factory,verify,reset,out,baseline):
 cfg=factory.local_config();snap=verify.snapshot();files=reset.filestore_manifest(cfg['ODOO_PROJECT']+'_filestore');paths=verify.attachment_store_paths(baseline)
 write(out/'sql.json',snap);write(out/'filestore.json',files);write(out/'store-paths.json',paths);return snap,files,paths

def run_gui(workspace,out,expected_binding):
 from .loader import activate,source_binding
 from .fixture import cases
 factory,lease,verify,reset,Adapter=activate(workspace);cfg=factory.local_config();port=int(cfg['ODOO_PORT']);out=Path(out);out.mkdir(mode=0o700)
 from playwright.sync_api import sync_playwright
 from enterprise_fallback.odoo18.odoo_v066_native_surface_adapter_v14 import VIEWPORT
 baseline=json.loads((factory.PRIVATE/'baseline_snapshot.json').read_bytes());frozen=json.loads((factory.PRIVATE/'baseline-filestore-manifest.json').read_bytes());gold=json.loads((factory.PRIVATE/'development_gold.json').read_bytes())
 target,wrong=cases();scores=[];phase='baseline';initial=None;cleanup=None
 def check_binding():
  if source_binding()!=expected_binding:raise RuntimeError('public_source_binding_changed_during_execution')
 def score(snapshot,files,paths,case=target):
  value=verify.evaluate(case['id'],gold[case['id']],baseline,snapshot);codes=verify.protected_source_file_differences(baseline,frozen,files)+verify.protected_source_store_path_differences(baseline,paths)
  if codes:value['reward']=0;value['difference_codes']=sorted(set(value['difference_codes']+codes))
  return value
 with lease.exclusive_worker_operation('public_known_answer_control'):
  before_services=services(workspace);write(out/'services-before.json',before_services)
  checkpoint={name:hashlib.sha256((factory.PRIVATE/name).read_bytes()).hexdigest() for name in ('baseline.pgcustom','baseline-filestore.tgz','baseline-filestore-manifest.json','baseline_snapshot.json','checkpoint_receipt.json','development_gold.json')};write(out/'checkpoint-bindings.json',checkpoint)
  try:
   check_binding();pre=reset.restore(evidence_dir=out/'baseline-cold');write(out/'baseline-restore.json',pre)
   snap,files,paths=readback(factory,verify,reset,out/'baseline',baseline);scores.append(score(snap,files,paths)['reward'])
   if scores!=[0]:raise RuntimeError('baseline_not_failed_known_answer')
   # Each original control starts from the same cold baseline, with its own 90/720 actor.
   for phase,case in (('positive',target),('negative',wrong)):
    check_binding();phase_out=out/phase;phase_out.mkdir(mode=0o700);restore=reset.restore(evidence_dir=phase_out/'cold');write(phase_out/'before-restore.json',restore)
    before=verify.snapshot();write(phase_out/'before-sql.json',before)
    if before!=baseline:raise RuntimeError('control_phase_not_at_original_baseline')
    with sync_playwright() as pw:
     browser=pw.chromium.launch(headless=True)
     try:
      page=browser.new_page(viewport=VIEWPORT)
      # Trusted fixture login and route occur before adapter construction.
      page.goto(f'http://127.0.0.1:{port}/web/login');page.locator('[name="login"]').fill('admin');page.locator('[name="password"]').fill(cfg['ODOO_ADMIN_PASSWORD']);page.get_by_role('button',name='Log in').click();page.wait_for_url('**/odoo/**');page.goto(f'http://127.0.0.1:{port}/odoo/purchase')
      adapter=Adapter(page,task_id=target['id'],task_binding_sha256=hashlib.sha256(canonical(target)).hexdigest(),instruction='Reconcile PUBLIC-TRAIN-001 against its public supplier confirmation. Preserve every unrelated record.')
      adapter.bind_guard(root=phase_out,worker_private=factory.PRIVATE);journal=Journal(adapter,page,phase_out)
      try:
       open_order(page,journal,case['id'],phase)
       if phase=='positive':show_source(page,journal,case,phase)
       edit_price(page,journal,case,phase);adapter.actor_clock.end('public_reference_control_complete')
      except BaseException as error:
       if adapter.actor_clock.ended is None:
        from native_desktop_factory.actor_deadline_future_v21 import ActorDeadlineReached
        try:adapter.actor_clock.end('public_reference_failed',deadline_exception=error if type(error) is ActorDeadlineReached else None)
        except BaseException as end_error:write(phase_out/'actor-end-error.json',failure(end_error,phase))
       raise
      finally:write(phase_out/'gui-trace.json',journal.trace)
      # Evaluator readback starts strictly after durable actor end.
      page.reload();page.wait_for_load_state('domcontentloaded');snap,files,paths=readback(factory,verify,reset,phase_out/'after',baseline);scores.append(score(snap,files,paths)['reward'])
      if scores[-1]!=(1 if phase=='positive' else 0):raise RuntimeError('persisted_control_score_mismatch_stop')
      if phase=='negative':
       wrong_proof=score(snap,files,paths,wrong);write(phase_out/'wrong-object-saved-score.json',wrong_proof)
       if wrong_proof['reward']!=1:raise RuntimeError('wrong_object_change_not_committed')
     finally:browser.close()
    check_binding()
  except BaseException as error:initial=failure(error,phase)
  finally:
   try:
    post=reset.restore(evidence_dir=out/'restored-cold');write(out/'post-restore.json',post);restored,files,paths=readback(factory,verify,reset,out/'restored',baseline)
    after_services=services(workspace);write(out/'services-after.json',after_services)
    cleanup={'SQL_exact':restored==baseline,'protected_filestore_exact':verify.protected_source_file_differences(baseline,frozen,files)==[],
     'protected_store_paths_exact':verify.protected_source_store_path_differences(baseline,paths)==[],
     'physical_before_web_restart_exact':post['physical_filestore_equal_before_web_restart'] is True,'business_before_web_restart_exact':post['business_snapshot_equal'] is True,
     'services_restored':after_services==before_services,'checkpoint_bytes_unchanged':all(hashlib.sha256((factory.PRIVATE/n).read_bytes()).hexdigest()==h for n,h in checkpoint.items())}
    check_binding()
   except BaseException as error:cleanup={'failed':True,**failure(error,'cleanup')}
  result={'schema':'public-odoo-reference-result-v1','scores':scores,'initial_failure':initial,'cleanup':cleanup,'models':0,'training':False,'formal_admissions':0};write(out/'result.json',result);validate_result(result)
 return result
