"""Reference7: prove a current saved form, or perform the unchanged dirty save.

Absence of a save control never establishes success. The saved branch requires
the installed native indicator, stable current-document state, zero visible
save controls and no GUI input. Original reload/SQL readback is still required.
"""
import math
import time
from hashlib import sha256
from .native_compat_source_loader_v1 import load_source

_impl=load_source('enterprise_fallback/odoo18/native_reference_save_v5.py',
    'enterprise_fallback.odoo18._native_reference_save_v7',
    'f8f2f9314d1375f6aaba04f3016d30172834dea0728a2da4f8d02b41cec0f053',(
        ('odoo-reference-native-save-policy-v5','odoo-reference-native-save-policy-v7',1),
        ('odoo-reference-native-save-intent-v5','odoo-reference-native-save-intent-v7',1),
        ('odoo-reference-native-save-result-v5','odoo-reference-native-save-result-v7',1)))
_dirty_save=_impl.save_original_form
POLICY={**_impl.POLICY,'one_unique_visible_enabled_native_save_click_required':False,
    'dirty_requires_one_unique_visible_enabled_native_save_click':True,
    'already_saved_requires_positive_stable_native_indicator_and_no_input':True,
    'original_post_reload_and_independent_sql_readback_still_required':True,
    'pre_click_saved_to_positive_dirty_reclassification_permitted':True,
    'post_click_retry_permitted':False}
_impl.POLICY=POLICY
require=_impl.require

def _indicator_kind(page):
    handles=page.locator('.o_form_status_indicator').element_handles()
    try:
        require(len(handles)<=1,'native_save_indicator_duplicate')
        if handles:return 'Save manually'
    finally:
        for handle in handles:handle.dispose()
    return 'Save'

def _no_visible_save_controls(page,journal):
    for name in _impl.SAVE_NAMES:
        _impl._clock(journal,'before_saved_control_absence_read')
        handles=page.get_by_role('button',name=name,exact=True).filter(visible=True).element_handles()
        try:require(not handles,'native_saved_indicator_disagrees_with_visible_save')
        finally:
            for handle in handles:handle.dispose()
        _impl._clock(journal,'after_saved_control_absence_read')

def save_original_form(page,journal,phase,*,timeout_seconds=30,poll_seconds=.1,stable_seconds=.25):
    require(all(type(x) in (int,float) and math.isfinite(x) for x in (timeout_seconds,poll_seconds,stable_seconds)) and
        0<poll_seconds<=.25 and 0<stable_seconds<=2 and max(poll_seconds,stable_seconds)<=timeout_seconds<=30,
        'native_save_wait_bounds_invalid')
    _impl._clock(journal,'before_initial_indicator_read')
    expected_url=page.url;name=_indicator_kind(page)
    before=_impl.read_saved_indicator(page,expected_url,name)
    _impl._clock(journal,'after_initial_indicator_read')
    if before['mode']=='dirty':
        require(page.url==expected_url,'native_save_current_document_changed')
        return _dirty_save(page,journal,phase,timeout_seconds=timeout_seconds,
            poll_seconds=poll_seconds,stable_seconds=stable_seconds)
    require(before['mode']=='saved','native_saved_indicator_unknown')
    started=time.monotonic();deadline=started+timeout_seconds
    step=len(getattr(journal,'trace',[]));stem=f'reference-save-{step:03d}';samples=[]
    while True:
        _impl._clock(journal,'before_indicator_read');now=time.monotonic()
        require(now<deadline,'native_already_saved_stability_timeout')
        current=_impl.read_saved_indicator(page,expected_url,name)
        _impl._clock(journal,'after_indicator_read')
        if current['mode']=='saved':
            try:_no_visible_save_controls(page,journal)
            except RuntimeError as error:
                if str(error)!='native_saved_indicator_disagrees_with_visible_save':raise
                # The same native toolbar may turn dirty between the two
                # read-only samples. Reopen its positive state before any IO;
                # a still-saved/unknown mismatch remains a refusal.
                _impl._clock(journal,'before_indicator_reclassification_read')
                current=_impl.read_saved_indicator(page,expected_url,name)
                _impl._clock(journal,'after_indicator_reclassification_read')
                require(current['mode']=='dirty','native_saved_indicator_disagrees_with_visible_save')
        if current['mode']=='dirty':
            require(len(getattr(journal,'trace',[]))==step,'native_pre_click_reclassification_performed_input')
            _impl._store(journal,stem+'-readiness',{'schema':'odoo-reference-pre-click-stabilization-v7',
                'initial_native_indicator':before,'reclassified_native_indicator':current,
                'document_url_sha256':sha256(expected_url.encode()).hexdigest(),
                'actor_action_count_before':step,'actor_action_count_after':step,
                'no_save_or_other_gui_input_performed':True,'current_positive_dirty_state_required':True,
                'same_action_retry_performed':False,'phase':phase,'samples':samples})
            remaining=deadline-time.monotonic()
            require(remaining>=max(poll_seconds,stable_seconds),'native_pre_click_stabilization_deadline')
            require(page.url==expected_url,'native_save_current_document_changed')
            return _dirty_save(page,journal,phase,timeout_seconds=remaining,
                poll_seconds=poll_seconds,stable_seconds=stable_seconds)
        require(current['mode']=='saved','native_saved_indicator_unknown')
        samples.append({'monotonic':now,'native':current})
        require(len(getattr(journal,'trace',[]))==step,'native_already_saved_branch_performed_input')
        if now-started>=stable_seconds:break
        _impl._clock(journal,'before_poll_wait')
        page.wait_for_timeout(min(poll_seconds,max(0,deadline-time.monotonic()))*1000)
        _impl._clock(journal,'after_poll_wait')
    _impl._store(journal,stem+'-intent',{'schema':'odoo-reference-native-save-intent-v7',
        'selected_name':name,'phase':phase,'started_monotonic':started,
        'one_guarded_click_required':False,'already_saved_native_proof_required':True,
        'document_url_sha256':sha256(expected_url.encode()).hexdigest(),
        'native_indicator_before':before,'same_action_replay_authorized':False})
    proof={'schema':'odoo-reference-native-save-result-v7','status':'already_saved_native_indicator',
        'selected_name':name,'one_native_save_click':False,'already_saved_before_operation':True,
        'positive_current_saved_indicator_verified':True,'visible_save_controls_absent_verified':True,
        'gui_input_performed':False,'required_dirty_commit_click_skipped':False,
        'skip_performed':False,'same_action_replay_performed':False,
        'original_post_reload_and_independent_sql_readback_still_required':True,'phase':phase,
        'save_action_start_step':step,'save_action_end_step':step-1,
        'actor_action_count_before':step,'actor_action_count_after':step,
        'started_monotonic':started,'ended_monotonic':time.monotonic(),
        'maximum_wait_seconds':timeout_seconds,'stable_saved_seconds':stable_seconds,'samples':samples}
    _impl._store(journal,stem+'-result',proof)
    return proof
