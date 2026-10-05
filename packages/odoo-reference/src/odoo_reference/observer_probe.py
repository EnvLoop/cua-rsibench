"""Public vendored read-only diagnostic probe. No launch authority.

The existing Native14 guard and V7 manual Save/reload remain unchanged.
Both original visibility predicates are recorded and never silently aligned.
"""
import hashlib, os, time
from enterprise_fallback.odoo18 import native_reference_save_v7 as save
PRIOR_POLICY={"public_synthetic_nontraining_only":True,"native_guard_predicates_preserved":True}
POLICY={**PRIOR_POLICY,'schema':'odoo-reference-priority-autosave-diagnostic-policy-v9-draft',
 'fixed_timeout_seconds':30,'fixed_poll_seconds':.1,'fixed_stable_seconds':.25,
 'every_native_probe_retained_before_interpretation':True,'post_conflict_reread_required':True,
 'original_Playwright_visible_predicate_unchanged':True,'original_V5_opacity_chain_predicate_unchanged':True,
 'positive_saved_and_zero_original_visible_Save_required':True,'conflict_resets_stable_timer':True,
 'unknown_wrong_page_or_ownership_loss_hard_fail':True,'new_source_credit_from_old_controls':0}
_CONTROL=r"""el=>{
 const chain=[];let nativeVisible=el.isConnected&&el.ownerDocument===document;
 const box=el.getBoundingClientRect();nativeVisible=nativeVisible&&box.width>0&&box.height>0;
 let n=el;while(n&&n.nodeType===1){const s=getComputedStyle(n);chain.push({tag:n.tagName,id:n.id,
 class:n.className&&typeof n.className==='string'?n.className:'',display:s.display,visibility:s.visibility,
 opacity:s.opacity,hidden:n.hidden,inert:n.hasAttribute('inert'),aria_hidden:n.getAttribute('aria-hidden')});
 if(n.hidden||n.hasAttribute('inert')||n.getAttribute('aria-hidden')==='true'||s.display==='none'||s.visibility==='hidden'||s.visibility==='collapse'||Number(s.opacity)===0)nativeVisible=false;n=n.parentElement;}
 const path=[];n=el;while(n&&n.nodeType===1){let i=0;for(let p=n.previousElementSibling;p;p=p.previousElementSibling)i++;path.push({tag:n.tagName,index:i,id:n.id});n=n.parentElement;}
 const indicator=document.querySelectorAll('.o_form_status_indicator');const form=indicator.length===1?indicator[0].closest('.o_form_view'):null;
 return {document_url:document.URL,connected:el.isConnected,same_document:el.ownerDocument===document,
 tag:el.tagName,role:el.getAttribute('role'),element_id:el.id,native_path:path,
 inside_current_form:!!form&&form.contains(el),native_V5_chain_visible:nativeVisible,
 rect:{x:box.x,y:box.y,width:box.width,height:box.height},full_ancestor_style_chain:chain};} """
def _hash(value):return hashlib.sha256(str(value).encode()).hexdigest()
def _put(journal,stem,value):save._impl._store(journal,stem,value)
def _context(page,journal,stem):
 adapter=journal.adapter;started=time.monotonic();adapter.actor_clock.check('before_observer9_scope_capture')
 errors=[];meta={};image=None;raw_context={}
 try:
  raw_context=page.evaluate("""()=>({document_url:document.URL,document_visible:document.visibilityState,
   document_has_focus:document.hasFocus(),top_window:window.top===window,
   focused_tag:document.activeElement&&document.activeElement.tagName,
   focused_id:document.activeElement&&document.activeElement.id})""")
 except BaseException as error:errors.append({'operation':'raw_context','class':type(error).__name__,'message_sha256':_hash(error)})
 try:meta=adapter._meta()
 except BaseException as error:errors.append({'operation':'original_native_metadata','class':type(error).__name__,'message_sha256':_hash(error)})
 try:image=adapter.store.write(stem+'.png',page.screenshot(type='png'),'raw_observation_image')
 except BaseException as error:errors.append({'operation':'native_png','class':type(error).__name__,'message_sha256':_hash(error)})
 ended=time.monotonic()
 held=adapter.boundary;lease=held.lease
 # require_worker_lease only reopens the held lease. Do not append lease checks/events here.
 lease_error=None
 try:held.module.require_worker_lease(root=held.private)
 except BaseException as error:lease_error={'class':type(error).__name__,'message_sha256':_hash(error)}
 owned=not errors and held.owns(page,meta) and meta.get('focus_owned_app') is True and ended<lease['expires_at'] and lease_error is None
 value={'pid':os.getpid(),'page_python_identity':id(page),'context_python_identity':id(page.context),
 'capture_started_monotonic':started,'capture_ended_monotonic':ended,'native':meta,'raw_context':raw_context,'native_image_ref':image,'capture_errors':errors,
 'owned_original_surface':owned,'held_lease_error':lease_error,'gui_input_performed':False}
 _put(journal,stem,value)
 adapter.actor_clock.check('after_observer9_scope_capture')
 return value

def _probe(page,journal,stem,expected_url):
 """Retain exact separate samples; do not label their different times atomic."""
 before=_context(page,journal,stem+'-context-before');records=[];errors=[];indicators=[];exact_visible_count=0;indicator_styles=[]
 if not before['owned_original_surface']:
  result={'context_before':before,'same_original_document':False,'owned_original_surface':False,
   'known_form_state':False,'visible_Save_outside_current_form_count':0,'saved_and_zero_original_visible_Save_agree':False}
  _put(journal,stem+'-pair',result);return result
 same=page.url==expected_url and before['native'].get('physical_url')==expected_url
 for which in ('before','after'):
  if which=='after':
   for name in save._impl.SAVE_NAMES:
    query_start=time.monotonic()
    # This is the exact original V7 visible role query, retained before interpretation.
    visible_handles=page.get_by_role('button',name=name,exact=True).filter(visible=True).element_handles()
    exact_visible_count+=len(visible_handles)
    try:
     visible_facts=[]
     for handle in visible_handles:
      fact=handle.evaluate(_CONTROL);fact.update(selected_exact_role_name=name,selected_by_original_V7_visible_query=True,
       handle_python_identity=id(handle),snapshot_monotonic=time.monotonic());visible_facts.append(fact)
     _put(journal,stem+'-exact-V7-visible-'+name.replace(' ','-'),{'count':len(visible_handles),
       'query_started_monotonic':query_start,'query_ended_monotonic':time.monotonic(),'native_element_facts':visible_facts})
    finally:
     for handle in visible_handles:handle.dispose()
    handles=page.get_by_role('button',name=name,exact=True).element_handles()
    try:
     for handle in handles:
      started=time.monotonic();fact=handle.evaluate(_CONTROL);evaluated=time.monotonic();pw_visible=handle.is_visible();visible_end=time.monotonic()
      fact.update(selected_exact_role_name=name,handle_python_identity=id(handle),handle_created_in_current_probe=True,
        identity_is_native_path_not_immutable_backend_ID=True,element_snapshot_started_monotonic=started,
        element_snapshot_ended_monotonic=evaluated,original_Playwright_visible=pw_visible,
        Playwright_visibility_completed_monotonic=visible_end,role_query_started_monotonic=query_start)
      records.append(fact);_put(journal,stem+f'-control-{len(records):03d}',fact)
    except BaseException as error:errors.append({'operation':'real_Save_role_controls','class':type(error).__name__,'message_sha256':_hash(error)})
    finally:
     for handle in handles:handle.dispose()
  started=time.monotonic()
  try:
   native=save._impl.read_saved_indicator(page,expected_url,'Save manually')
   value={'started_monotonic':started,'ended_monotonic':time.monotonic(),'native':native}
  except BaseException as error:
   value={'started_monotonic':started,'ended_monotonic':time.monotonic(),'error_class':type(error).__name__,'error_sha256':_hash(error)}
   errors.append({'operation':'native_indicator_'+which,**value})
  indicators.append(value);_put(journal,stem+'-indicator-'+which,value)
  # Record original indicator root and buttons-container chains as separate timed facts.
  for selector in ('.o_form_status_indicator','.o_form_status_indicator .o_form_status_indicator_buttons'):
   handles=page.locator(selector).element_handles()
   try:
    for handle in handles:
     fact=handle.evaluate(_CONTROL);fact.update(selector=selector,indicator_read_phase=which,
       handle_python_identity=id(handle),snapshot_monotonic=time.monotonic());indicator_styles.append(fact)
    _put(journal,stem+'-indicator-styles-'+which,{'native_elements':indicator_styles,
      'same_time_as_indicator_evaluation':False})
   finally:
    for handle in handles:handle.dispose()
 after=_context(page,journal,stem+'-context-after')
 same=same and page.url==expected_url and after['native'].get('physical_url')==expected_url
 same=same and all(r['same_document'] and r['connected'] and r['document_url']==expected_url for r in records)
 known=not errors and len(indicators)==2 and all(v.get('native',{}).get('kind')=='form' and v['native'].get('mode') in ('saved','dirty') for v in indicators)
 original_visible=exact_visible_count
 native_visible=sum(r['native_V5_chain_visible'] for r in records)
 outside=sum(r['original_Playwright_visible'] and not r['inside_current_form'] for r in records)
 is_saved=known and all(v['native']['mode']=='saved' for v in indicators)
 owned=before['owned_original_surface'] and after['owned_original_surface']
 result={'sample_started_monotonic':before['capture_started_monotonic'],'sample_ended_monotonic':after['capture_ended_monotonic'],
 'indicators':indicators,'indicator_native_identity_and_style_chains':indicator_styles,'real_current_Save_role_control_list':records,'original_Playwright_visible_Save_count':original_visible,
 'native_V5_opacity_chain_visible_Save_count':native_visible,'visible_Save_outside_current_form_count':outside,
 'same_original_document':same,'owned_original_surface':owned,'known_form_state':known,'positive_saved_before_and_after':is_saved,
 'saved_and_zero_original_visible_Save_agree':is_saved and original_visible==0,
 'visibility_predicate_difference_observed':any(r['original_Playwright_visible']!=r['native_V5_chain_visible'] for r in records),'exact_original_V7_visible_query_retained':True,
 'context_before':before,'context_after':after,'errors':errors,'gui_input_performed':False,'two_reads_not_atomic':True}
 _put(journal,stem+'-pair',result)
 return result

def _hard_valid(probe):
 return probe['same_original_document'] and probe['owned_original_surface'] and probe['known_form_state'] and probe['visible_Save_outside_current_form_count']==0

def wait_positive_priority_autosave(page,journal,phase,*,timeout_seconds=30,poll_seconds=.1,stable_seconds=.25):
 save.require((timeout_seconds,poll_seconds,stable_seconds)==(30,.1,.25),'observer9_fixed_budget_changed')
 step=len(journal.trace);save.require(step>0,'observer9_prior_original_priority_action_required')
 url=page.url;started=time.monotonic();deadline=started+30;stable_since=None;index=0;conflicts=0
 stem=f'reference-priority-autosave-v9-draft-{step:03d}'
 _put(journal,stem+'-intent',{'policy':POLICY,'phase':phase,'started_monotonic':started,
  'document_url_sha256':_hash(url),'actor_action_count_before':step,'trigger_action_step':step-1,
  'gui_input_authorized':False,'same_action_retry_authorized':False,'draft_not_qualification_credit':True})
 def check_input():
  save.require(len(journal.trace)==step and page.url==url,'observer9_input_or_document_changed')
  journal.adapter.actor_clock.check('observer9_read_only_wait')
 while True:
  check_input();save.require(time.monotonic()<deadline,'observer9_positive_agreement_timeout')
  probe=_probe(page,journal,stem+f'-sample-{index:03d}',url);index+=1;check_input()
  save.require(_hard_valid(probe),'observer9_unknown_context_or_ownership_state')
  now=time.monotonic();save.require(now<=deadline,'observer9_positive_agreement_timeout')
  if probe['saved_and_zero_original_visible_Save_agree']:
   if stable_since is None:stable_since=now
   if now-stable_since>=.25:
    final=_probe(page,journal,stem+'-conditional-final',url);check_input()
    save.require(_hard_valid(final),'observer9_unknown_final_context_or_ownership_state')
    if final['saved_and_zero_original_visible_Save_agree'] and time.monotonic()<=deadline:
     proof={'policy':POLICY,'phase':phase,'actor_action_count_before':step,'actor_action_count_after':len(journal.trace),
      'started_monotonic':started,'ended_monotonic':time.monotonic(),'stable_since_monotonic':stable_since,
      'stable_saved_seconds':.25,'sample_count':index,'conflict_count':conflicts,'gui_input_performed':False,
      'same_action_retry_performed':False,'positive_current_saved_and_zero_original_visible_Save_verified':True,
      'original_Reference7_Save_reload_SQL_reset_still_required':True,'draft_not_qualification_credit':True}
     _put(journal,stem+'-result',proof);return proof
    stable_since=None;conflicts+=1
    reread=_probe(page,journal,stem+f'-post-final-conflict-{conflicts:03d}',url);check_input()
    save.require(_hard_valid(reread),'observer9_unknown_post_final_conflict_context_or_ownership_state')
  else:
   stable_since=None;conflicts+=1
   # Persist a post-conflict native reread, scope/focus/URL and PNG before refusal/poll.
   after_conflict=_probe(page,journal,stem+f'-post-conflict-{conflicts:03d}',url);check_input()
   save.require(_hard_valid(after_conflict),'observer9_unknown_post_conflict_context_or_ownership_state')
  save._impl._clock(journal,'before_observer9_poll_wait')
  remaining=deadline-time.monotonic();save.require(remaining>0,'observer9_positive_agreement_timeout')
  page.wait_for_timeout(min(.1,remaining)*1000)
  save._impl._clock(journal,'after_observer9_poll_wait')
