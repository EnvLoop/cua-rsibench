"""Await the installed CRM priority widget's native automatic save.

This reference-only observer performs no input. The original priority click,
Native14 guard, subsequent Reference7 save and reload/SQL verifier stay intact.
"""
import math
import time
from hashlib import sha256
from . import native_reference_save_v7 as save

POLICY={'schema':'odoo-reference-priority-autosave-policy-v8',
    'installed_priority_field_sha256':'ef204300cfac3e1a069fa9d44e81f6ab43d1863fa8d9fac7559ea195683ae15b',
    'installed_crm_view_sha256':'55c7a213bacd6cab3e0ff23a54c0c5b19408a814e0dc92a4686d5b625e67844b',
    'installed_priority_autosave_default':True,'positive_current_saved_indicator_required':True,
    'maximum_wait_seconds':30,'gui_input_performed':False,'same_action_retry_permitted':False,
    'unchanged_reference7_manual_save_reload_and_sql_readback_still_required':True}


def wait_positive_priority_autosave(page,journal,phase,*,timeout_seconds=30,poll_seconds=.1,stable_seconds=.25):
    save.require(all(type(x) in (int,float) and math.isfinite(x) for x in
        (timeout_seconds,poll_seconds,stable_seconds)) and 0<poll_seconds<=.25 and
        0<stable_seconds<=2 and max(poll_seconds,stable_seconds)<=timeout_seconds<=30,
        'native_priority_autosave_wait_bounds_invalid')
    step=len(getattr(journal,'trace',[]));save.require(step>0,'native_priority_autosave_requires_prior_action')
    expected_url=page.url;started=time.monotonic();deadline=started+timeout_seconds
    stem=f'reference-priority-autosave-{step:03d}';samples=[];stable_since=None
    save._impl._store(journal,stem+'-intent',{'schema':'odoo-reference-priority-autosave-intent-v8',
        'phase':phase,'trigger_action_step':step-1,'actor_action_count_before':step,
        'document_url_sha256':sha256(expected_url.encode()).hexdigest(),'started_monotonic':started,
        'gui_input_authorized':False,'same_action_retry_authorized':False,'policy':POLICY})
    while True:
        save._impl._clock(journal,'before_priority_autosave_indicator_read')
        now=time.monotonic();save.require(now<deadline,'native_priority_autosave_timeout')
        native=save._impl.read_saved_indicator(page,expected_url,'Save manually')
        save._impl._clock(journal,'after_priority_autosave_indicator_read')
        save.require(native['kind']=='form' and native['mode'] in ('dirty','saved'),
            'native_priority_autosave_requires_current_form_indicator')
        save.require(len(getattr(journal,'trace',[]))==step,'native_priority_autosave_observer_performed_input')
        if native['mode']=='saved':
            save._no_visible_save_controls(page,journal)
            if stable_since is None:stable_since=now
        else:stable_since=None
        samples.append({'monotonic':now,'native':native})
        if stable_since is not None and now-stable_since>=stable_seconds:break
        save._impl._clock(journal,'before_priority_autosave_poll_wait')
        page.wait_for_timeout(min(poll_seconds,max(0,deadline-time.monotonic()))*1000)
        save._impl._clock(journal,'after_priority_autosave_poll_wait')
    save.require(time.monotonic()<=deadline,'native_priority_autosave_timeout')
    save.require(page.url==expected_url and len(getattr(journal,'trace',[]))==step,
        'native_priority_autosave_document_or_input_changed')
    proof={'schema':'odoo-reference-priority-autosave-result-v8','status':'positive_current_priority_autosave_verified',
        'phase':phase,'trigger_action_step':step-1,'actor_action_count_before':step,'actor_action_count_after':step,
        'document_url_sha256':sha256(expected_url.encode()).hexdigest(),'started_monotonic':started,
        'ended_monotonic':time.monotonic(),'maximum_wait_seconds':timeout_seconds,
        'stable_saved_seconds':stable_seconds,'gui_input_performed':False,'same_action_retry_performed':False,
        'unchanged_reference7_save_reload_and_independent_sql_readback_still_required':True,'samples':samples}
    save._impl._store(journal,stem+'-result',proof)
    return proof
