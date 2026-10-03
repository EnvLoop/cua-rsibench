"""Evaluator-only native save selection and bounded current saved indicator.

One actual guarded click is mandatory. No task contents, SQL, application API,
DOM mutation, pixel edit, control retry or actor predicate is introduced.
"""
import json
import math
import os
from pathlib import Path
import time
from hashlib import sha256

SAVE_NAMES=('Save manually','Save')
POLICY={'schema':'odoo-reference-native-save-policy-v5','save_names':list(SAVE_NAMES),
    'one_unique_visible_enabled_native_save_click_required':True,
    'no_absent_save_skip_or_fixed_delay_fallback':True,'saved_native_indicator_required':True,
    'maximum_wait_seconds':30,'same_current_document_url_required':True,
    'original_native14_guard_and_budgets_unchanged':True,
    'installed_form_template_sha256':'b336b4066fc875883347b27150577a1541e4efaa6158636d516ddf44cb7400a0',
    'installed_form_logic_sha256':'e6df512823276372b248fb11b91e767a72e93eea6c73939d9f6f677cf93a7f31',
    'installed_list_template_sha256':'e31f5ec691e9a379fa3817154b9129c25a9f2df5695da6ed0a3de8c56e9e948c'}

def require(value,code):
    if not value:raise RuntimeError(code)

def _clock(journal,phase):
    journal.adapter.actor_clock.check('reference_save_'+phase)

def _save_candidate(page):
    candidates=[]
    for name in SAVE_NAMES:
        locator=page.get_by_role('button',name=name,exact=True).filter(visible=True)
        handles=locator.element_handles()
        try:
            require(len(handles)<=1,'native_save_candidate_duplicate')
            if handles:
                require(handles[0].is_enabled(),'native_save_candidate_disabled')
                candidates.append((name,locator))
        finally:
            for handle in handles:handle.dispose()
    require(len(candidates)==1,'native_save_candidate_missing_or_ambiguous')
    return candidates[0]

_FORM=r'''el=>{
 const visible=n=>{const r=n.getBoundingClientRect();if(!n.isConnected||n.ownerDocument!==document||!(r.width>0&&r.height>0))return false;
  for(let p=n;p&&p.nodeType===1;p=p.parentElement){const s=getComputedStyle(p);if(p.hidden||p.hasAttribute('inert')||p.getAttribute('aria-hidden')==='true'||s.display==='none'||s.visibility==='hidden'||s.visibility==='collapse'||Number(s.opacity)===0)return false;}return true;};
 const b=Array.from(el.querySelectorAll('.o_form_status_indicator_buttons'));
 const invalid=Array.from(el.querySelectorAll('.text-danger,[data-tooltip="Unable to save. Correct the issue or discard all changes"]')).some(visible);
 return {kind:'form',url:document.URL,connected_current_document:el.isConnected&&el.ownerDocument===document,
 root_visible:visible(el),buttons_count:b.length,invisible_class:b.length===1&&b[0].classList.contains('invisible'),
 buttons_visible:b.length===1&&visible(b[0]),invalid_visible:invalid};}'''
_LIST=r'''el=>{
 const visible=n=>{const r=n.getBoundingClientRect(),s=getComputedStyle(n);return n.isConnected&&n.ownerDocument===document&&r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'&&s.visibility!=='collapse';};
 const saves=Array.from(el.querySelectorAll('.o_list_button_save'));
 const discards=Array.from(el.querySelectorAll('.o_list_button_discard'));
 const views=Array.from(document.querySelectorAll('.o_list_view')).filter(visible);
 return {kind:'list',url:document.URL,connected_current_document:el.isConnected&&el.ownerDocument===document,
 current_visible_list_count:views.length,save_count:saves.length,discard_count:discards.length,
 save_visible:saves.length===1&&visible(saves[0]),discard_visible:discards.length===1&&visible(discards[0])};}'''

def read_saved_indicator(page,expected_url,selected_name):
    require(page.url==expected_url,'native_save_current_document_changed')
    handles=page.locator('.o_form_status_indicator').element_handles()
    try:
        require(len(handles)<=1,'native_save_indicator_duplicate')
        if handles:
            value=handles[0].evaluate(_FORM)
            require(value['connected_current_document'] and value['url']==expected_url and value['root_visible'],
                    'native_save_indicator_not_current_visible')
            require(value['buttons_count']==1,'native_save_indicator_buttons_missing_or_duplicate')
            require(not value['invalid_visible'],'native_save_indicator_invalid')
            if value['invisible_class'] and not value['buttons_visible']:mode='saved'
            elif not value['invisible_class'] and value['buttons_visible']:mode='dirty'
            else:raise RuntimeError('native_save_indicator_class_visibility_disagree')
            return {**value,'mode':mode}
    finally:
        for handle in handles:handle.dispose()
    require(selected_name=='Save','native_save_indicator_missing')
    # Original ListView.Buttons renders Save/Discard exactly while editedRecord
    # exists. Their removal is its native commit indicator; no silent skip.
    handles=page.locator('.o_list_buttons').element_handles()
    try:
        require(len(handles)==1,'native_save_list_indicator_missing_or_duplicate')
        value=handles[0].evaluate(_LIST)
    finally:
        for handle in handles:handle.dispose()
    require(value['connected_current_document'] and value['url']==expected_url and value['current_visible_list_count']==1,
            'native_save_list_indicator_not_current_visible')
    if value['save_count']==value['discard_count']==0:mode='saved'
    elif value['save_count']==value['discard_count']==1 and value['save_visible'] and value['discard_visible']:mode='dirty'
    else:raise RuntimeError('native_save_list_indicator_unknown')
    return {**value,'mode':mode}

def _store(journal,stem,value):
    if not hasattr(journal,'out'):return
    path=Path(journal.out)/(stem+'.private.json')
    raw=json.dumps(value,sort_keys=True,separators=(',',':')).encode()
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as file:file.write(raw)

def save_original_form(page,journal,phase,*,timeout_seconds=30,poll_seconds=.1,stable_seconds=.25):
    require(all(type(x) in (int,float) and math.isfinite(x) for x in (timeout_seconds,poll_seconds,stable_seconds)) and
        0<poll_seconds<=.25 and 0<stable_seconds<=2 and max(poll_seconds,stable_seconds)<=timeout_seconds<=30,
        'native_save_wait_bounds_invalid')
    _clock(journal,'before_candidate')
    name,locator=_save_candidate(page);expected_url=page.url
    _clock(journal,'before_initial_indicator_read')
    before=read_saved_indicator(page,expected_url,name)
    _clock(journal,'after_initial_indicator_read')
    require(before['mode']=='dirty','native_save_dirty_control_required_before_click')
    started=time.monotonic();start_step=len(getattr(journal,'trace',[]));stem=f'reference-save-{start_step:03d}'
    _store(journal,stem+'-intent',{'schema':'odoo-reference-native-save-intent-v5','selected_name':name,
        'phase':phase,'started_monotonic':started,'one_guarded_click_required':True,
        'document_url_sha256':sha256(expected_url.encode()).hexdigest(),'native_indicator_before':before,
        'same_action_replay_authorized':False})
    _clock(journal,'before_native_click')
    journal.act('click',phase=phase,locator=locator)
    _clock(journal,'after_click');deadline=started+timeout_seconds;stable_since=None;samples=[]
    while True:
        _clock(journal,'before_indicator_read')
        now=time.monotonic();require(now<deadline,'native_save_dirty_timeout_after_single_click')
        value=read_saved_indicator(page,expected_url,name);samples.append({'monotonic':now,'native':value})
        _clock(journal,'after_indicator_read')
        if value['mode']=='saved':
            if stable_since is None:stable_since=now
            if now-stable_since>=stable_seconds:break
        else:stable_since=None
        _clock(journal,'before_poll_wait')
        page.wait_for_timeout(min(poll_seconds,max(0,deadline-time.monotonic()))*1000)
        _clock(journal,'after_poll_wait')
    proof={'schema':'odoo-reference-native-save-result-v5','status':'saved_native_indicator',
        'selected_name':name,'one_native_save_click':True,'original_native14_guard_used':True,
        'skip_performed':False,'same_action_replay_performed':False,'phase':phase,
        'save_action_start_step':start_step,'save_action_end_step':len(getattr(journal,'trace',[]))-1,
        'started_monotonic':started,'ended_monotonic':time.monotonic(),
        'maximum_wait_seconds':timeout_seconds,'stable_saved_seconds':stable_seconds,'samples':samples}
    _store(journal,stem+'-result',proof)
    return proof
