"""Reference6 saved-only split qualification; no old controls promoted."""
from .native_compat_source_loader_v1 import load_source
import math
import json

_impl=load_source('enterprise_fallback/odoo18/native_reference_split_finalizer_v3.py',
    'enterprise_fallback.odoo18._native_reference_split_finalizer_v6',
    '93732b4d4185352a9f92b439a4857323f6a45c5a636dd6607456f6c1210f9d49',
    (('v13','v14',3),('v3','v6',33)))
_impl.__file__=__file__
_prior_provenance=_impl._v6_action_provenance

def _v6_action_provenance(read,attempt,receipt,audit,reference):
    result=_prior_provenance(read,attempt,receipt,audit,reference)
    paths=sorted(attempt.glob('reference-save-*-intent.private.json'))
    _impl.require(paths,'Reference6 completed case lacks mandatory native save proof')
    dirty_count=already_saved_count=0
    _,raw=read.ref(receipt['refs']['gui_trace'],attempt);trace=json.loads(raw)['actions']
    for path in paths:
        intent,_=read.value(path)
        proof,_=read.value(path.with_name(path.name.replace('-intent.private.json','-result.private.json')))
        _impl.require(intent['schema']=='odoo-reference-native-save-intent-v6' and
            intent['same_action_replay_authorized'] is False and
            proof['schema']=='odoo-reference-native-save-result-v6' and
            proof['skip_performed'] is False and proof['same_action_replay_performed'] is False and
            proof['selected_name']==intent['selected_name'] and proof['phase']==intent['phase'],
            'Reference6 native save identity/proof changed')
        start,end=proof['save_action_start_step'],proof['save_action_end_step']
        if proof['status']=='saved_native_indicator':
            dirty_count+=1
            _impl.require(intent['one_guarded_click_required'] is True and
                proof['one_native_save_click'] is True and proof['original_native14_guard_used'] is True and
                type(start) is int and type(end) is int and 0<=start<=end<len(trace),
                'Reference6 dirty save action span changed')
            for index in range(start,end+1):
                files=list((attempt/'actions').glob(f'step-{index:03d}*-intent.private.json'))
                _impl.require(len(files)==1,'Reference6 save action intent ambiguous')
                action,_=read.value(files[0]);kind=action['normalized_action']['type']
                _impl.require(kind==('click' if index==end else 'scroll') and action['phase']==proof['phase'],
                    'Reference6 save span contains unexpected input')
        else:
            already_saved_count+=1
            _impl.require(proof['status']=='already_saved_native_indicator' and
                intent['one_guarded_click_required'] is False and intent['already_saved_native_proof_required'] is True and
                intent['native_indicator_before']['mode']=='saved' and proof['one_native_save_click'] is False and
                proof['already_saved_before_operation'] is True and proof['positive_current_saved_indicator_verified'] is True and
                proof['visible_save_controls_absent_verified'] is True and proof['gui_input_performed'] is False and
                proof['required_dirty_commit_click_skipped'] is False and
                proof['original_post_reload_and_independent_sql_readback_still_required'] is True and
                type(start) is int and type(end) is int and 0<=start<=len(trace) and end==start-1 and
                proof['actor_action_count_before']==proof['actor_action_count_after']==start,
                'Reference6 already-saved current proof/action counts changed')
            _impl.require(all(sample['native']['mode']=='saved' for sample in proof['samples']),
                'Reference6 already-saved proof became dirty')
            _impl.require(len(proof['samples'])>=2 and type(proof['stable_saved_seconds']) in (int,float) and
                math.isfinite(proof['stable_saved_seconds']) and 0<proof['stable_saved_seconds']<=2 and
                proof['ended_monotonic']-proof['started_monotonic']>=proof['stable_saved_seconds'],
                'Reference6 already-saved stability interval changed')
        times=(proof['started_monotonic'],proof['ended_monotonic'],proof['maximum_wait_seconds'])
        _impl.require(all(type(t) in (int,float) and math.isfinite(t) for t in times) and
            0<=times[1]-times[0]<=times[2]<=30 and proof['samples'] and
            proof['samples'][-1]['native']['mode']=='saved',
            'Reference6 bounded saved indicator missing')
        for sample in proof['samples']:
            native=sample['native'];stamp=sample['monotonic']
            _impl.require(type(stamp) in (int,float) and math.isfinite(stamp) and times[0]<=stamp<=times[1] and
                native['connected_current_document'] is True and
                _impl.digest(native['url'].encode())==intent['document_url_sha256'] and
                native['mode'] in ('saved','dirty'),'Reference6 saved current-document sample changed')
            if native['kind']=='form':
                _impl.require(native['root_visible'] is True and native['buttons_count']==1 and
                    native['invalid_visible'] is False and native['invisible_class']==(native['mode']=='saved') and
                    native['buttons_visible']==(native['mode']=='dirty'),'Reference6 form indicator changed')
            else:
                _impl.require(native['kind']=='list' and native['current_visible_list_count']==1 and
                    native['save_count']==native['discard_count']==int(native['mode']=='dirty'),
                    'Reference6 list indicator changed')
    return {**result,'v6_native_commit_or_proved_saved_provenance_verified':True,
        'reference_native_save_count':dirty_count,'reference_already_saved_no_input_count':already_saved_count,
        'reference_native_commit_proof_count':len(paths)}

_impl._v6_action_provenance=_v6_action_provenance
def __getattr__(name):return getattr(_impl,name)
if __name__=='__main__':_impl.main()
