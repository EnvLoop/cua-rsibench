"""Additive public successor integration of reviewed read-only diagnostic probe."""
import hashlib,time
from types import FunctionType,ModuleType
from .config import digest
from .observer_probe import POLICY

def require(ok,code):
 if not ok:raise RuntimeError(code)
def clone_scope(module):
 fresh=ModuleType('odoo_reference._one_use_observer');fresh.__dict__.update(module.__dict__)
 for key,value in list(fresh.__dict__.items()):
  if isinstance(value,FunctionType) and value.__globals__ is module.__dict__:
   fn=FunctionType(value.__code__,fresh.__dict__,value.__name__,value.__defaults__,value.__closure__);fn.__kwdefaults__=value.__kwdefaults__;fresh.__dict__[key]=fn
 return fresh

def instrumented_observer():
    from . import observer_probe
    module=clone_scope(observer_probe);original=module._probe;counts={};original_put=module._put;waits={};stopped=[False];style_counts={}
    def put(journal,stem,value):
        if stem.endswith(('-indicator-styles-before','-indicator-styles-after')):
            index=style_counts.get(stem,0);style_counts[stem]=index+1
            stem=stem+'-selector-'+str(index).zfill(3)
        if stem.endswith('-intent') and value.get('policy')==module.POLICY:
            waits[value['actor_action_count_before']]={'deadline':value['started_monotonic']+30,
                'url_sha256':value['document_url_sha256'],'lease_descriptor_sha256':digest(journal.adapter.boundary.lease)}
        if 'owned_original_surface' in value and 'capture_started_monotonic' in value:
            value['held_binding_readonly_proof']=held_binding_proof(journal.adapter,value,waits[len(journal.trace)])
            value['owned_original_surface']=value['owned_original_surface'] and value['held_binding_readonly_proof']['verified']
            if not value['owned_original_surface']:stopped[0]=True
        original_put(journal,stem,value)
    module._put=put
    def probe(page,journal,stem,url):
        count=counts.get(stem,0);counts[stem]=count+1
        # The candidate bytes remain exact; each diagnostic capture is one-use.
        unique=stem+'-capture-'+str(count).zfill(3)
        try:return original(page,journal,unique,url)
        except BaseException as error:
            value={'error_class':type(error).__name__,'error_message_sha256':hashlib.sha256(str(error).encode()).hexdigest(),
                'gui_input_performed':False,'same_action_retry_performed':False}
            clock=journal.adapter.actor_clock
            held=journal.adapter.boundary;tick=time.monotonic();active=False
            try:
                from enterprise_fallback.odoo18.odoo_native_surface_evidence_v13 import private_bytes
                held.module.require_worker_lease(root=held.private)
                scope_ok=(not stopped[0] and tick<min(clock.deadline,held.lease['expires_at'],waits[len(journal.trace)]['deadline']) and
                    private_bytes(held.lock_path)==held.lock and hashlib.sha256(private_bytes(held.credentials_path)).hexdigest()==held.credentials_sha)
                meta=journal.adapter._meta() if scope_ok else None
                active=(bool(meta) and held.owns(page,meta) and meta.get('focus_owned_app') is True)
            except BaseException:active=False
            if active:
                try:value['post_exception_context']=module._context(page,journal,unique+'-exception-context')
                except BaseException as context_error:
                    value['context_capture_error_class']=type(context_error).__name__
                    value['context_capture_error_sha256']=hashlib.sha256(str(context_error).encode()).hexdigest()
            else:value['post_stop_native_capture_forbidden']=True
            module._put(journal,unique+'-exception',value)
            raise
    module._probe=probe
    return module

def held_binding_proof(adapter,context,wait):
    """Original boundary.check predicates without appending old lease events."""
    held=adapter.boundary;tick=time.monotonic();errors=[]
    lock_sha=credential_sha=None
    try:
        from enterprise_fallback.odoo18.odoo_native_surface_evidence_v13 import private_bytes
        held.module.require_worker_lease(root=held.private)
        lock=private_bytes(held.lock_path);lock_sha=hashlib.sha256(lock).hexdigest()
        require(lock==held.lock,'observer9_held_lock_bytes_drifted')
        credential_sha=hashlib.sha256(private_bytes(held.credentials_path)).hexdigest()
        require(credential_sha==held.credentials_sha,'observer9_held_credentials_drifted')
        require(digest(held.lease)==wait['lease_descriptor_sha256'],'observer9_held_lease_descriptor_drifted')
        tick=time.monotonic()
        require(context['capture_started_monotonic']<=context['capture_ended_monotonic']<=tick,
                'observer9_native_capture_times_invalid')
        require(tick<min(adapter.actor_clock.deadline,held.lease['expires_at'],wait['deadline']),
                'observer9_native_capture_outside_original_deadlines')
        require(tick-context['capture_started_monotonic']<=adapter.limits.frame_ttl_seconds,
                'observer9_native_capture_not_current')
        meta=context['native']
        raw=context['raw_context']
        require(context['capture_started_monotonic']<=meta['native_capture_monotonic']<=context['capture_ended_monotonic'] and
            raw['document_visible']=='visible' and raw['document_has_focus'] is True and raw['top_window'] is True and
            hashlib.sha256(raw['document_url'].encode()).hexdigest()==wait['url_sha256'],
            'observer9_raw_native_capture_timing_URL_or_focus_unknown')
        require(held.owns(held.page,meta) and meta.get('focus_owned_app') is True and
            meta.get('native_window_sha256')==held.window_sha and
            hashlib.sha256(meta['physical_url'].encode()).hexdigest()==wait['url_sha256'],
            'observer9_native_capture_focus_window_URL_or_owner_changed')
    except BaseException as error:
        errors.append({'class':type(error).__name__,'message_sha256':hashlib.sha256(str(error).encode()).hexdigest()})
    return {'schema':'observer9-held-binding-readonly-proof-v1','verified':not errors,'checked_monotonic':tick,
        'expected_lock_sha256':hashlib.sha256(held.lock).hexdigest(),'actual_lock_sha256':lock_sha,
        'expected_credentials_sha256':held.credentials_sha,'actual_credentials_sha256':credential_sha,
        'lease_descriptor_sha256':digest(held.lease),'expected_lease_descriptor_sha256':wait['lease_descriptor_sha256'],
        'actor_deadline_monotonic':adapter.actor_clock.deadline,
        'lease_deadline_monotonic':held.lease['expires_at'],'observer_deadline_monotonic':wait['deadline'],
        'original_frame_ttl_seconds':adapter.limits.frame_ttl_seconds,'expected_window_sha256':held.window_sha,
        'expected_document_url_sha256':wait['url_sha256'],'lease_events_appended':0,'errors':errors}
