"""Public v3 explicit guarded focus on one existing active form tab.

No focus setter, body allowance, Save repeat or guard relaxation is present.
"""
import hashlib,time
from .config import digest
from .control import write
TAB_SELECTOR='.o_form_view .o_notebook [role="tab"].active'
# Original read-only chain predicate plus current native identity facts.
def control_script():
 from .observer_probe import _CONTROL
 return _CONTROL.replace('return {document_url:', 'return {element_ref:el.getAttribute("data-envloop-ref"),active_tab:el.classList.contains("active"),disabled:!!el.disabled,aria_disabled:el.getAttribute("aria-disabled"),focused_same_element:document.activeElement===el,document_url:')
def require(ok,code):
 if not ok:raise RuntimeError(code)
def valid_tab(fact):
 return (fact.get('role')=='tab' and fact.get('active_tab') is True and fact.get('disabled') is False and fact.get('aria_disabled')!='true' and fact.get('connected') is True and fact.get('same_document') is True and fact.get('inside_current_form') is True and fact.get('native_V5_chain_visible') is True)
def restore_owned_focus(page,journal,phase,manual_save):
 adapter=journal.adapter;adapter.actor_clock.check('before_public_v3_current_tab_capture');started=time.monotonic();url=page.url;step=len(journal.trace)
 require(manual_save['phase']==phase and manual_save['status'] in ('saved_native_indicator','already_saved_native_indicator'),'public_v3_original_Save_not_completed')
 require(url==manual_save['samples'][-1]['native']['url'],'public_v3_post_Save_document_changed')
 scope=adapter._meta();require(adapter.boundary.owns(page,scope) and scope['native_window_sha256']==adapter.boundary.window_sha,'public_v3_post_Save_surface_not_owned')
 lease_sha=digest(adapter.boundary.lease);held_before=held_binding(adapter,lease_sha)
 locator=page.locator(TAB_SELECTOR).filter(visible=True);handles=locator.element_handles();attempt={'schema':'public-v3-post-Save-owned-focus-attempt-v1','phase':phase,'step':step,'selector':TAB_SELECTOR,'selected_handle_count':len(handles),'started_monotonic':started,'original_Save_proof_sha256':digest(manual_save),'no_extra_Save_or_retry':True,'held_before':held_before}
 try:
  facts=[handle.evaluate(control_script()) for handle in handles[:16]];attempt['selected_native_facts']=facts;attempt['capture_truncated']=len(handles)>16;write(journal.out/'post-save-focus-attempt.private.json',attempt)
  require(len(handles)==1,'public_v3_current_active_form_tab_not_unique')
  handle=handles[0];before=facts[0]
  require(valid_tab(before) and before['document_url']==url,'public_v3_current_active_form_tab_not_owned_visible_enabled')
  # One ordinary Native14 guarded click; the same held DOM handle is read-only.
  journal.act('click',phase,locator=locator,capture_control=True)
  adapter.actor_clock.check('after_public_v3_guarded_tab_click')
  try:held_after_click=held_binding(adapter,lease_sha)
  except BaseException as error:
   write(journal.out/'post-save-focus-stop.private.json',{'stage':'after_guarded_click_before_native_reread','class':type(error).__name__,'message_sha256':hashlib.sha256(str(error).encode()).hexdigest(),'post_stop_native_capture_forbidden':True});raise
  before_native_metadata=handle.evaluate(control_script());native=adapter._meta();after_read_started=time.monotonic();after=handle.evaluate(control_script());after_read_ended=time.monotonic();held_after=held_binding(adapter,lease_sha);ended=time.monotonic()
  proof={'schema':'public-v3-post-Save-owned-focus-proof-v1','phase':phase,'action_step':step,'actor_action_count_before':step,'actor_action_count_after':len(journal.trace),'started_monotonic':started,'ended_monotonic':ended,'document_url_sha256':hashlib.sha256(url.encode()).hexdigest(),'original_Save_proof_sha256':digest(manual_save),'before_selection':before,'after_selection_before_native_metadata':before_native_metadata,'after_selection':after,'after_selection_read_started_monotonic':after_read_started,'after_selection_read_ended_monotonic':after_read_ended,'native_after':native,'no_extra_Save_or_retry':True,'strict_observer_follows':True,'held_after_click':held_after_click,'held_after_capture':held_after}
  write(journal.out/'post-save-focus-proof.private.json',proof)
  require(len(journal.trace)==step+1 and page.url==url,'public_v3_focus_action_count_or_document_changed')
  require(valid_tab(before_native_metadata) and before_native_metadata['focused_same_element'] is True and valid_tab(after) and after['focused_same_element'] is True and before['native_path']==before_native_metadata['native_path']==after['native_path'] and after['document_url']==url,'public_v3_same_current_tab_focus_not_proven')
  require(adapter.boundary.owns(page,native) and native['native_window_sha256']==adapter.boundary.window_sha and native.get('focus_owned_app') is True and native['focus']['tag'] not in ('body','html') and native['focus']['ref']==after['element_ref'] and native['physical_url']==url,'public_v3_native_eligible_owned_focus_not_proven')
  require(started<=native['native_capture_monotonic']<=after_read_started<=after_read_ended<=ended<min(adapter.actor_clock.deadline,adapter.boundary.lease['expires_at']),'public_v3_focus_capture_outside_original_clocks')
  adapter.actor_clock.check('after_public_v3_owned_focus_proof');return proof
 finally:
  for handle in handles:handle.dispose()

def held_binding(adapter,expected_lease):
 from enterprise_fallback.odoo18.odoo_native_surface_evidence_v13 import private_bytes
 held=adapter.boundary;held.module.require_worker_lease(root=held.private)
 lock=private_bytes(held.lock_path);credentials=private_bytes(held.credentials_path)
 require(lock==held.lock and hashlib.sha256(credentials).hexdigest()==held.credentials_sha and digest(held.lease)==expected_lease,'public_v3_held_binding_changed')
 tick=time.monotonic();require(tick<min(adapter.actor_clock.deadline,held.lease['expires_at']),'public_v3_held_scope_expired')
 return {'checked_monotonic':tick,'lock_sha256':hashlib.sha256(lock).hexdigest(),'credentials_sha256':hashlib.sha256(credentials).hexdigest(),'lease_descriptor_sha256':digest(held.lease),'actor_deadline_monotonic':adapter.actor_clock.deadline,'lease_deadline_monotonic':held.lease['expires_at'],'lease_events_appended':0}
