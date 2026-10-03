"""Reference5 saved-only split qualification; no old controls promoted."""
from .native_compat_source_loader_v1 import load_source
import math
import json

_impl=load_source('enterprise_fallback/odoo18/native_reference_split_finalizer_v3.py',
    'enterprise_fallback.odoo18._native_reference_split_finalizer_v5',
    '93732b4d4185352a9f92b439a4857323f6a45c5a636dd6607456f6c1210f9d49',
    (('v13','v14',3),('v3','v5',33)))
_impl.__file__=__file__
_prior_provenance=_impl._v5_action_provenance

def _v5_action_provenance(read,attempt,receipt,audit,reference):
    result=_prior_provenance(read,attempt,receipt,audit,reference)
    paths=sorted(attempt.glob('reference-save-*-intent.private.json'))
    _impl.require(paths,'Reference5 completed case lacks mandatory native save proof')
    _,raw=read.ref(receipt['refs']['gui_trace'],attempt);trace=json.loads(raw)['actions']
    for path in paths:
        intent,_=read.value(path)
        proof,_=read.value(path.with_name(path.name.replace('-intent.private.json','-result.private.json')))
        _impl.require(intent['schema']=='odoo-reference-native-save-intent-v5' and
            intent['one_guarded_click_required'] is True and intent['same_action_replay_authorized'] is False and
            proof['schema']=='odoo-reference-native-save-result-v5' and proof['status']=='saved_native_indicator' and
            proof['one_native_save_click'] is True and proof['original_native14_guard_used'] is True and
            proof['skip_performed'] is False and proof['same_action_replay_performed'] is False and
            proof['selected_name']==intent['selected_name'] and proof['phase']==intent['phase'],
            'Reference5 native save identity/proof changed')
        start,end=proof['save_action_start_step'],proof['save_action_end_step']
        _impl.require(type(start) is int and type(end) is int and 0<=start<=end<len(trace),
            'Reference5 save action span changed')
        for index in range(start,end+1):
            files=list((attempt/'actions').glob(f'step-{index:03d}*-intent.private.json'))
            _impl.require(len(files)==1,'Reference5 save action intent ambiguous')
            action,_=read.value(files[0]);kind=action['normalized_action']['type']
            _impl.require(kind==('click' if index==end else 'scroll') and action['phase']==proof['phase'],
                'Reference5 save span contains unexpected input')
        times=(proof['started_monotonic'],proof['ended_monotonic'],proof['maximum_wait_seconds'])
        _impl.require(all(type(t) in (int,float) and math.isfinite(t) for t in times) and
            0<=times[1]-times[0]<=times[2]<=30 and proof['samples'] and
            proof['samples'][-1]['native']['mode']=='saved',
            'Reference5 bounded saved indicator missing')
        for sample in proof['samples']:
            native=sample['native'];stamp=sample['monotonic']
            _impl.require(type(stamp) in (int,float) and math.isfinite(stamp) and times[0]<=stamp<=times[1] and
                native['connected_current_document'] is True and
                _impl.digest(native['url'].encode())==intent['document_url_sha256'] and
                native['mode'] in ('saved','dirty'),'Reference5 saved current-document sample changed')
            if native['kind']=='form':
                _impl.require(native['root_visible'] is True and native['buttons_count']==1 and
                    native['invalid_visible'] is False and native['invisible_class']==(native['mode']=='saved') and
                    native['buttons_visible']==(native['mode']=='dirty'),'Reference5 form indicator changed')
            else:
                _impl.require(native['kind']=='list' and native['current_visible_list_count']==1 and
                    native['save_count']==native['discard_count']==int(native['mode']=='dirty'),
                    'Reference5 list indicator changed')
    return {**result,'v5_mandatory_native_save_provenance_verified':True,
        'reference_native_save_count':len(paths)}

_impl._v5_action_provenance=_v5_action_provenance
def __getattr__(name):return getattr(_impl,name)
if __name__=='__main__':_impl.main()
