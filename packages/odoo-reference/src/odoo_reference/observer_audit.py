"""Saved-only public successor audit3. No constructors, GUI, RPC or Docker."""
import hashlib,json,math,io
from pathlib import Path
from PIL import Image
from cursibench.scale_action_contract import ContractLimits
from .config import canonical,digest
from .observer_probe import POLICY
class ImmutableSavedReader:
 def __init__(self):self.seen={}
 def raw(self,path):
  p=Path(path)
  if p.is_symlink() or not p.is_file() or p.stat().st_mode & 0o077:raise RuntimeError('private_regular_evidence_required')
  raw=p.read_bytes();key=str(p.resolve());h=hashlib.sha256(raw).hexdigest()
  if key in self.seen and self.seen[key]!=h:raise RuntimeError('saved_evidence_changed_between_reads')
  self.seen[key]=h;return raw
 def value(self,path):
  raw=self.raw(path);return json.loads(raw),raw
 def ref(self,ref,root):
  if set(ref)!={'path','sha256'}:raise RuntimeError('saved_ref_shape_invalid')
  p=Path(ref['path']);p=p if p.is_absolute() else Path(root)/p
  if not p.resolve().is_relative_to(Path(root).resolve()):raise RuntimeError('saved_ref_scope_escape')
  raw=self.raw(p)
  if hashlib.sha256(raw).hexdigest()!=ref['sha256']:raise RuntimeError('saved_ref_hash_changed')
  return p,raw
 def unchanged(self):
  for p in list(self.seen):self.raw(p)

def require(ok,code):
    if not ok:raise RuntimeError(code)

def sha(raw):return hashlib.sha256(raw).hexdigest()

def opacity_visible(control):
    box=control['rect']
    visible=control['connected'] and control['same_document'] and box['width']>0 and box['height']>0
    for node in control['full_ancestor_style_chain']:
        if (node['hidden'] or node['inert'] or node['aria_hidden']=='true' or node['display']=='none'
            or node['visibility'] in ('hidden','collapse') or float(node['opacity'])==0):visible=False
    return bool(visible)

def _pair(read,attempt,path,url_sha,step):
    pair,_=read.value(path)
    boundary,_=read.value(attempt/'surface-guard/lease-boundary.private.json')
    envelope,_=read.value(attempt/f'surface-guard/turn-{step-1:03d}/observation-envelope.private.json')
    lease=envelope['lease']
    actor,_=read.value(attempt/'actor-clock/start.private.json')
    stem=path.name.removesuffix('-pair.private.json')
    for suffix,key in (('-context-before','context_before'),('-context-after','context_after')):
        raw,_=read.value(attempt/(stem+suffix+'.private.json'))
        require(raw==pair[key],'observer9_pair_context_differs_from_raw_capture')
    for index,which in enumerate(('before','after')):
        raw,_=read.value(attempt/(stem+'-indicator-'+which+'.private.json'))
        require(raw==pair['indicators'][index],'observer9_pair_indicator_differs_from_raw_read')
    require(pair['two_reads_not_atomic'] is True and pair['gui_input_performed'] is False,
            'observer9_pair_cannot_claim_atomicity_or_input')
    contexts=(pair['context_before'],pair['context_after']);png_count=0
    for context in contexts:
        require(context['owned_original_surface'] is True and context['held_lease_error'] is None and not context['capture_errors'],
                'observer9_owned_surface_unproven')
        native=context['native']
        require(native['visible'] is True and native['top_window'] is True and native['app_shell'] is True and
            native['focus_owned_app'] is True and sha(native['physical_url'].encode())==url_sha,
            'observer9_native_context_or_document_changed')
        raw_context=context['raw_context']
        require(context['capture_started_monotonic']<=native['native_capture_monotonic']<=context['capture_ended_monotonic'] and
            sha(raw_context['document_url'].encode())==url_sha and raw_context['document_visible']=='visible' and
            raw_context['top_window'] is True and raw_context['document_has_focus'] is True,
            'observer9_raw_document_focus_or_capture_timing_changed')
        require(type(context['pid']) is int and type(context['page_python_identity']) is int and
            type(context['context_python_identity']) is int,'observer9_native_identity_missing')
        native_ref=context['native_image_ref']
        require(set(native_ref)=={'schema','path','sha256','size','kind'} and
            native_ref['schema']=='native-guard-artifact-ref-v1' and native_ref['kind']=='raw_observation_image',
            'observer9_native_image_full_reference_invalid')
        _,raw=read.ref({'path':native_ref['path'],'sha256':native_ref['sha256']},attempt)
        require(len(raw)==native_ref['size'],'observer9_native_image_reference_size_changed')
        import io
        with Image.open(io.BytesIO(raw)) as image:
            require(image.format=='PNG' and image.width>0 and image.height>0,'observer9_native_PNG_invalid')
            image.verify()
        png_count+=1
        held=context['held_binding_readonly_proof'];tick=held['checked_monotonic']
        require(held['schema']=='observer9-held-binding-readonly-proof-v1' and held['verified'] is True and
            held['lease_events_appended']==0 and held['errors']==[] and
            held['expected_lock_sha256']==held['actual_lock_sha256'] and
            held['expected_credentials_sha256']==held['actual_credentials_sha256'] and
            held['lease_descriptor_sha256']==held['expected_lease_descriptor_sha256'] and
            context['capture_started_monotonic']<=context['capture_ended_monotonic']<=tick and
            tick<min(held['actor_deadline_monotonic'],held['lease_deadline_monotonic'],held['observer_deadline_monotonic']) and
            tick-context['capture_started_monotonic']<=held['original_frame_ttl_seconds'] and
            held['expected_document_url_sha256']==url_sha and held['expected_window_sha256']==native['native_window_sha256'],
            'observer9_held_binding_or_original_capture_freshness_unproven')
        require(held['expected_lock_sha256']==boundary['lock_sha256'] and
            held['expected_credentials_sha256']==boundary['credential_file_sha256'] and
            held['expected_window_sha256']==boundary['window_sha256'] and
            held['lease_descriptor_sha256']==sha(canonical(lease)) and
            context['pid']==boundary['lock_owner']['pid'], 'observer9_held_binding_differs_from_original_native_lease')
        require(held['actor_deadline_monotonic']==actor['actor_deadline_monotonic'] and
            held['lease_deadline_monotonic']==lease['expires_at'] and
            held['original_frame_ttl_seconds']==ContractLimits(max_step=90).frame_ttl_seconds,
            'observer9_additive_deadlines_or_freshness_not_original')
    require(contexts[0]['pid']==contexts[1]['pid'] and
        contexts[0]['page_python_identity']==contexts[1]['page_python_identity'] and
        contexts[0]['context_python_identity']==contexts[1]['context_python_identity'],
        'observer9_native_process_page_or_context_changed')
    require(pair['sample_started_monotonic']<=pair['sample_ended_monotonic'] and
        pair['same_original_document'] is True and pair['known_form_state'] is True and
        pair['owned_original_surface'] is True and not pair['errors'],'observer9_native_pair_invalid')
    indicators=pair['indicators'];require(len(indicators)==2,'observer9_pair_requires_two_native_indicator_reads')
    saved=True
    for value in indicators:
        native=value['native']
        require(value['started_monotonic']<=value['ended_monotonic'] and native['kind']=='form' and
            native['connected_current_document'] is True and native['root_visible'] is True and
            native['buttons_count']==1 and native['invalid_visible'] is False and sha(native['url'].encode())==url_sha,
            'observer9_positive_current_indicator_unproven')
        mode=('saved' if native['invisible_class'] and not native['buttons_visible'] else
              'dirty' if not native['invisible_class'] and native['buttons_visible'] else None)
        require(mode is not None and mode==native['mode'],'observer9_original_native_indicator_semantics_changed')
        saved=saved and mode=='saved'
    control_count=native_visible=outside=0
    for index,control in enumerate(pair['real_current_Save_role_control_list'],1):
        raw,_=read.value(attempt/(stem+f'-control-{index:03d}.private.json'))
        require(raw==control,'observer9_pair_control_differs_from_raw_read')
        require(control['selected_exact_role_name'] in ('Save','Save manually') and control['connected'] is True and
            control['same_document'] is True and sha(control['document_url'].encode())==url_sha,
            'observer9_real_Save_control_identity_changed')
        require(control['identity_is_native_path_not_immutable_backend_ID'] is True and
            type(control['handle_python_identity']) is int and control['native_path'] and control['full_ancestor_style_chain'],
            'observer9_control_identity_or_full_styles_missing')
        require(opacity_visible(control)==control['native_V5_chain_visible'],'observer9_original_opacity_chain_fact_changed')
        native_visible+=control['native_V5_chain_visible'];control_count+=1
        outside+=control['original_Playwright_visible'] and not control['inside_current_form']
    # Reopen actual original V7 filtered role-list files, not the derived flag.
    exact_visible=0
    for name in ('Save','Save-manually'):
        facts,_=read.value(attempt/(stem+'-exact-V7-visible-'+name+'.private.json'))
        require(facts['count']==len(facts['native_element_facts']) and
            facts['query_started_monotonic']<=facts['query_ended_monotonic'], 'observer9_original_visible_role_query_changed')
        for control in facts['native_element_facts']:
            require(control['selected_by_original_V7_visible_query'] is True and control['connected'] is True and
                control['same_document'] is True and sha(control['document_url'].encode())==url_sha,
                'observer9_original_visible_role_handle_not_current')
            require(opacity_visible(control)==control['native_V5_chain_visible'],
                    'observer9_exact_visible_handle_style_fact_changed')
        exact_visible+=facts['count']
    require(pair['exact_original_V7_visible_query_retained'] is True and pair['original_Playwright_visible_Save_count']==exact_visible and
        pair['native_V5_opacity_chain_visible_Save_count']==native_visible and pair['visible_Save_outside_current_form_count']==outside==0,
        'observer9_predicates_silently_aligned_or_count_changed')
    agree=saved and exact_visible==0
    require(pair['positive_saved_before_and_after']==saved and pair['saved_and_zero_original_visible_Save_agree']==agree,
            'observer9_positive_agreement_flags_changed')
    require(pair['indicator_native_identity_and_style_chains'],'observer9_indicator_styles_not_retained')
    before_paths=sorted(attempt.glob(stem+'-indicator-styles-before-selector-*.private.json'))
    after_paths=sorted(attempt.glob(stem+'-indicator-styles-after-selector-*.private.json'))
    require(len(before_paths)==len(after_paths)==2,'observer9_each_indicator_selector_style_capture_required')
    before_records=[read.value(p)[0] for p in before_paths];after_records=[read.value(p)[0] for p in after_paths]
    raw_before=before_records[-1];raw_after=after_records[-1]
    require(len(before_records[0]['native_elements'])==1 and len(raw_before['native_elements'])==2 and
        len(after_records[0]['native_elements'])==3 and len(raw_after['native_elements'])==4,
        'observer9_indicator_selector_capture_sequence_changed')
    styles=pair['indicator_native_identity_and_style_chains']
    require(raw_before['same_time_as_indicator_evaluation'] is False and raw_after['same_time_as_indicator_evaluation'] is False and
        raw_after['native_elements']==styles and raw_before['native_elements']==[s for s in styles if s['indicator_read_phase']=='before'],
        'observer9_pair_indicator_styles_differ_from_raw_capture')
    for style in styles:
        require(style['same_document'] is True and style['connected'] is True and sha(style['document_url'].encode())==url_sha and
            opacity_visible(style)==style['native_V5_chain_visible'],'observer9_native_indicator_style_chain_changed')
    difference=any(c['original_Playwright_visible']!=c['native_V5_chain_visible']
                   for c in pair['real_current_Save_role_control_list'])
    require(pair['visibility_predicate_difference_observed']==difference,
            'observer9_predicate_difference_flag_changed')
    return {'pair':pair,'agree':agree,'png_count':png_count,'real_control_count':control_count}

def audit_saved_observer(*,attempt):
    attempt=Path(attempt);read=ImmutableSavedReader()
    # This is exactly the old saved-only Reference7 manual Save + viewport proof.
    manual={"manual_Save_audited_separately":True}
    paths=sorted(attempt.glob('reference-priority-autosave-v9-draft-*-intent.private.json'))
    require(len(paths)==1,'public_observer_one_phase_proof_required')
    phases=set();pairs=pngs=controls=conflicts=0;provenance=[]
    for path in paths:
        intent,_=read.value(path);stem=path.name.removesuffix('-intent.private.json')
        result,_=read.value(attempt/(stem+'-result.private.json'))
        require(intent['policy']==result['policy']==POLICY and intent['phase']==result['phase'] and
            intent['phase'] in ('positive','negative') and intent['gui_input_authorized'] is False and
            intent['same_action_retry_authorized'] is False and intent['draft_not_qualification_credit'] is True,
            'observer9_original_observer_policy_or_phase_changed')
        phase=intent['phase'];require(phase not in phases,'observer9_priority_phase_repeated');phases.add(phase)
        step=intent['actor_action_count_before'];trigger=intent['trigger_action_step']
        require(type(step) is int and step>0 and trigger==step-1 and result['actor_action_count_before']==result['actor_action_count_after']==step,
            'observer9_original_priority_action_or_no_input_proof_changed')
        action,_=read.value(attempt/f'actions/step-{trigger:03d}-intent.private.json')
        require(action['phase']==phase and action['normalized_action']['type'] in ('click','key'),'observer9_trigger_not_original_guarded_click')
        start,end=result['started_monotonic'],result['ended_monotonic'];stable=result['stable_since_monotonic']
        require(start==intent['started_monotonic'] and all(type(t) in (int,float) and math.isfinite(t) for t in (start,end,stable)) and
            0<=end-start<=30 and start<=stable<=end and end-stable>=.25 and result['stable_saved_seconds']==.25 and
            result['gui_input_performed'] is False and result['same_action_retry_performed'] is False and
            result['positive_current_saved_and_zero_original_visible_Save_verified'] is True and
            result['original_Reference7_Save_reload_SQL_reset_still_required'] is True and result['draft_not_qualification_credit'] is True,
            'observer9_original_fixed_budget_or_final_positive_proof_changed')
        pair_paths=sorted(attempt.glob(stem+'-*-pair.private.json'))
        require(pair_paths,'observer9_retained_native_pairs_missing')
        rows=[]
        for pair_path in pair_paths:
            checked=_pair(read,attempt,pair_path,intent['document_url_sha256'],step);pair=checked['pair']
            require(start<=pair['sample_started_monotonic']<=pair['sample_ended_monotonic']<=end,'observer9_sample_outside_original_wait')
            rows.append((pair['sample_ended_monotonic'],pair_path,checked));pairs+=1;pngs+=checked['png_count'];controls+=checked['real_control_count']
        rows.sort(key=lambda x:x[0]);finals=[r for r in rows if '-conditional-final-capture-' in r[1].name]
        require(finals and finals[-1][2]['agree'] is True,'observer9_conditional_final_positive_agreement_missing')
        since=[r for r in rows if r[0]>=stable]
        require(since and all(r[2]['agree'] for r in since) and since[-1][0]-stable>=.25,
                'observer9_conflict_or_dirty_state_during_final_stable_interval')
        bad=[r for r in rows if not r[2]['agree']];conflicts+=len(bad)
        for conflict_time,pair_path,checked in bad:
            if '-post-conflict-' in pair_path.name or '-post-final-conflict-' in pair_path.name:continue
            require(any('-post-conflict-' in x[1].name or '-post-final-conflict-' in x[1].name
                for x in rows if x[0]>=conflict_time),'observer9_post_conflict_reread_not_retained')
        provenance.append({'phase':phase,'intent_sha256':sha(read.raw(path)),
            'result_sha256':sha(read.raw(attempt/(stem+'-result.private.json'))),'native_pair_count':len(rows)})
    require(len(phases)==1,'public_one_phase_required')
    read.unchanged()
    manifest=[{'path':p,'sha256':h} for p,h in sorted(read.seen.items())]
    return {'schema':'odoo-reference9-diagnostic-saved-provenance-v2','reference_binding_sha256':digest(POLICY),
        'manual_reference7_and_viewport_provenance':manual,'priority_phase_count':len(phases),'retained_native_pair_count':pairs,
        'native_PNGs_reopened':pngs,'real_current_Save_controls_reopened':controls,'observed_nonagreement_pair_count':conflicts,
        'original_predicates_kept_separate':True,'strict_conditional_final_and_stability_verified':True,
        'GUI_input_performed':False,'same_action_retry_performed':False,'source_visual_review_verified':False,
        'qualification_granted':False,'old_control_credit':0,'full100_credit':0,'formal_admission_credit':0,'phases':provenance,
        'reopened_original_evidence_manifest':manifest,
        'reopened_original_evidence_manifest_sha256':sha(json.dumps(manifest,sort_keys=True,separators=(',',':')).encode())}

def selector_prefix_audit(attempt):
    attempt=Path(attempt);read=ImmutableSavedReader();rows=[]
    for pair in sorted(attempt.glob('*-pair.private.json')):
        stem=pair.name.removesuffix('-pair.private.json')
        for phase,count in (('before',1),('after',3)):
            a=attempt/(stem+'-indicator-styles-'+phase+'-selector-000.private.json')
            b=attempt/(stem+'-indicator-styles-'+phase+'-selector-001.private.json')
            first,_=read.value(a);full,_=read.value(b)
            require(first['native_elements']==full['native_elements'][:count],
                'observer9_first_selector_prefix_differs_from_complete_capture')
            rows.append({'first_path':str(a),'first_sha256':read.seen[str(a.resolve())],
                         'complete_path':str(b),'complete_sha256':read.seen[str(b.resolve())],'prefix_equal':True})
    require(rows,'observer9_selector_prefix_evidence_missing');read.unchanged()
    return {'selector_prefix_checks':len(rows),'prefix_refs_reopened':len(rows)*2,'all_prefixes_equal':True,'rows':rows}

def audit3(attempt):
 result=audit_saved_observer(attempt=attempt);return {**result,"additive_selector_prefix_proof":selector_prefix_audit(attempt)}
