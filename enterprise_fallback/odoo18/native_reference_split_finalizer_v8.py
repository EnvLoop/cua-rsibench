"""Saved-only Reference8 proof; original Reference7 save evidence is retained."""
from types import FunctionType
import math
from .native_compat_source_loader_v1 import load_source
from . import native_reference_split_finalizer_v7 as prior
from .native_reference_autosave_v8 import POLICY

_impl=load_source('enterprise_fallback/odoo18/native_reference_split_finalizer_v3.py',
    'enterprise_fallback.odoo18._native_reference_split_finalizer_v8',
    '93732b4d4185352a9f92b439a4857323f6a45c5a636dd6607456f6c1210f9d49',
    (('v13','v14',3),('v3','v8',33)))
_impl.__file__=__file__
_base_provenance=_impl._v8_action_provenance
_save_globals=dict(prior._v7_action_provenance.__globals__)
_save_globals.update(_impl=_impl,_prior_provenance=_base_provenance)
_save_provenance=FunctionType(prior._v7_action_provenance.__code__,_save_globals,
    '_unchanged_reference7_save_provenance',prior._v7_action_provenance.__defaults__,
    prior._v7_action_provenance.__closure__)


def _v8_action_provenance(read,attempt,receipt,audit,reference):
    result=_save_provenance(read,attempt,receipt,audit,reference)
    paths=sorted(attempt.glob('reference-priority-autosave-*-intent.private.json'))
    if receipt.get('family')=='crm':
        _impl.require(paths,'Reference8 CRM case lacks native priority autosave proof')
    negative=0
    for path in paths:
        intent,_=read.value(path)
        proof,_=read.value(path.with_name(path.name.replace('-intent.private.json','-result.private.json')))
        step=proof['actor_action_count_before'];trigger=proof['trigger_action_step']
        _impl.require(intent['schema']=='odoo-reference-priority-autosave-intent-v8' and
            intent['policy']==POLICY and intent['gui_input_authorized'] is False and
            intent['same_action_retry_authorized'] is False and
            proof['schema']=='odoo-reference-priority-autosave-result-v8' and
            proof['status']=='positive_current_priority_autosave_verified' and
            proof['phase']==intent['phase'] and proof['phase'] in ('positive','negative') and
            proof['document_url_sha256']==intent['document_url_sha256'] and
            proof['started_monotonic']==intent['started_monotonic'] and
            type(step) is int and step>0 and step==proof['actor_action_count_after']==intent['actor_action_count_before'] and
            type(trigger) is int and trigger==step-1==intent['trigger_action_step'] and
            proof['gui_input_performed'] is False and proof['same_action_retry_performed'] is False and
            proof['unchanged_reference7_save_reload_and_independent_sql_readback_still_required'] is True,
            'Reference8 priority autosave identity or zero-input proof changed')
        actions=list((attempt/'actions').glob(f'step-{trigger:03d}*-intent.private.json'))
        _impl.require(len(actions)==1,'Reference8 priority trigger intent ambiguous')
        action,_=read.value(actions[0])
        _impl.require(action['normalized_action']['type']=='click' and action['phase']==proof['phase'],
            'Reference8 priority autosave trigger is not original guarded click')
        start,end,limit=proof['started_monotonic'],proof['ended_monotonic'],proof['maximum_wait_seconds']
        stable=proof['stable_saved_seconds'];samples=proof['samples']
        _impl.require(all(type(t) in (int,float) and math.isfinite(t) for t in (start,end,limit,stable)) and
            0<=end-start<=limit<=30 and 0<stable<=2 and len(samples)>=2,
            'Reference8 priority autosave wait bounds changed')
        saved_since=None;previous=start
        for sample in samples:
            stamp=sample['monotonic'];native=sample['native']
            _impl.require(type(stamp) in (int,float) and math.isfinite(stamp) and previous<=stamp<=end and
                native['kind']=='form' and native['connected_current_document'] is True and
                _impl.digest(native['url'].encode())==intent['document_url_sha256'] and
                native['root_visible'] is True and native['buttons_count']==1 and native['invalid_visible'] is False and
                native['mode'] in ('dirty','saved') and native['invisible_class']==(native['mode']=='saved') and
                native['buttons_visible']==(native['mode']=='dirty'),
                'Reference8 priority autosave current native sample changed')
            previous=stamp
            if native['mode']=='saved':
                if saved_since is None:saved_since=stamp
            else:saved_since=None
        _impl.require(saved_since is not None and samples[-1]['monotonic']-saved_since>=stable,
            'Reference8 priority autosave stable saved interval missing')
        negative+=int(proof['phase']=='negative')
    if receipt.get('family')=='crm':
        _impl.require(negative==1,'Reference8 original CRM wrong-object priority wait missing or repeated')
    return {**result,'unchanged_reference7_save_provenance_verified':True,
        'v8_priority_autosave_zero_input_provenance_verified':True,'reference_priority_autosave_wait_count':len(paths)}

_impl._v8_action_provenance=_v8_action_provenance
def __getattr__(name):return getattr(_impl,name)
if __name__=='__main__':_impl.main()
