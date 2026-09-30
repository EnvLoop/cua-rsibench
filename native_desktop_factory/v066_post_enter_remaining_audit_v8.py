"""Independent immutable v7 terminal audit and exact v8 continuation permit.

Visual adjudication is a separate hash-bound observation. The original frozen
modal classifier, stopped run, intents and receipts are never changed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import admit
from . import v066_post_enter_near_negative_v7 as old
from . import v066_post_enter_near_negative_audit_v7 as prior
from . import v066_post_enter_remaining_v8 as runner
from .reconcile_interrupted_sweep import active_hashes
from .v066_storage_budget import audit as storage_audit


VISUAL_SCHEMA = 'cua-native-wdi-v066-save-modal-visual-adjudication-private-v1'
TERMINAL_SCHEMA = 'cua-native-wdi-v066-three-intent-terminal-audit-private-v8'
REVIEW_SCHEMA = 'cua-native-wdi-v066-remaining-train-review-private-v8'
PERMIT_SCHEMA = 'cua-native-wdi-v066-remaining-train-permit-private-v8'
RECONCILIATION_SHA256 = '9c0a6cc8a1cc7d4383f3a39c9ddf2da01c55ba52f2248ecbf942e3ce3b3f1039'


def _old_records(*, old_freeze: Path, old_run: Path) -> tuple[dict, dict, list[dict]]:
    value, run = runner.old_bindings(old_freeze=old_freeze, old_run=old_run)
    prior.checked_permit(freeze_path=old_freeze, permit_path=Path(run['permit_path']), value=value)
    root = Path(value['output_root']); records = []; ids = set()
    if len(list(root.glob('*/intent.json')))!=3:
        raise ValueError('Old terminal root must contain exactly three consumed intents')
    expected = [('wrong-target','case'),('wrong-target','cold-reset'),('modal-stop','case')]
    sources = {s['case']:s for s in value['cases']}
    for ordinal,(case,attempt) in enumerate(expected):
        source = sources[case]; out = root/f'{ordinal:02d}-{case}-{attempt}'
        intent_raw=old._private(out/'intent.json'); intent=json.loads(intent_raw)
        receipt_raw=old._private(out/'receipt.json'); receipt=json.loads(receipt_raw)
        journal=run['attempts'][ordinal]
        if (intent.get('schema') != old.INTENT_SCHEMA or receipt.get('schema') != old.RECEIPT_SCHEMA or
                intent.get('status') != 'recorded_before_provider_create' or
                intent.get('freeze_sha256') != runner.OLD_FREEZE_SHA256 or intent.get('permit_sha256') != runner.OLD_PERMIT_SHA256 or
                intent.get('same_intent_replay_authorized') is not False or receipt.get('intent_sha256') != old.digest(intent_raw) or
                receipt.get('provider_kind') != 'e2b_desktop' or journal.get('receipt_sha256') != old.digest(receipt_raw) or
                journal.get('ordinal') != ordinal or journal.get('case') != case or journal.get('attempt') != attempt or
                journal.get('status') != receipt.get('status') or
                any(v.get('split') != 'train' or v.get('case') != case or v.get('attempt') != attempt or
                    v.get('ordinal') != ordinal or v.get('package_sha256') != source['row']['package_sha256'] or
                    v.get('input_sha256') != source['row']['input_sha256'] or v.get('lease_seconds') != old.LEASE_SECONDS or
                    v.get('official_final_admissions') != 0 for v in [intent,receipt]) or
                receipt.get('guest_content_attested') is not True or receipt.get('fresh_profile_absent') is not True or
                receipt.get('kill_returned') is not True or receipt.get('is_running_after_kill') is not False or
                receipt.get('official_model_results') != 0):
            raise ValueError('Immutable three-intent source, receipt, lease or cleanup changed')
        sid=receipt.get('sandbox_id_sha256')
        if type(sid) is not str or len(sid)!=64 or sid in ids: raise ValueError('Three old TRAIN guest identities are not distinct')
        ids.add(sid)
        directory,baseline,oracle=admit._package(Path(value['candidate_root']),source['row'])
        prior._audit_profile(root=root,receipt=receipt,reference_path=Path(value['scoped_reference']))
        if attempt=='cold-reset':
            if (receipt.get('status')!='cold_reset_observed' or receipt.get('actor_steps')!=[] or
                    prior.bound(root,receipt['restored_artifact'])!=baseline):
                raise ValueError('Old fresh source reset bytes changed')
            prior.bound(root,receipt['cold_observation'])
        else:
            prior._audit_actions(root=root,receipt=receipt,source=source,oracle=oracle,
                instruction=(directory/'actor_task.txt').read_text())
            if case=='wrong-target':
                score=prior.wrong_target_score(baseline,prior.bound(root,receipt['saved_artifact']),oracle)
                if receipt.get('status')!='wrong_target_saved_score_zero' or receipt.get('independent_saved_score')!=score:
                    raise ValueError('Old independent saved wrong-target score changed')
            else:
                _check_stimulus(root=root,out=out,receipt=receipt,source=source)
                classification=prior.audit_samples(root=root,out=out,filename=source['filename'],document_id=receipt['document_window_id'])
                if (receipt.get('status')!='stopped_for_reconciliation' or receipt.get('error_type')!='ValueError' or
                        receipt.get('probe_classification')!=classification or
                        classification['classification']!='other_window_boundary_stop_inconclusive' or
                        classification['raw_samples']!=1 or receipt['probe'].get('stop')!='window_boundary_stop'):
                    raise ValueError('Old frozen modal title mismatch/terminal stop changed')
        records.append({'source':source,'out':out,'intent':intent,'receipt':receipt,
                        'intent_sha256':old.digest(intent_raw),'receipt_sha256':old.digest(receipt_raw)})
    return value,run,records


def _check_stimulus(*, root: Path, out: Path, receipt: dict, source: dict) -> list[dict]:
    stimulus=receipt.get('trusted_negative_stimulus',{})
    rows=[json.loads(line) for line in old._private(out/'samples.ndjson').splitlines()]
    if (stimulus.get('key')!=old.TRUSTED_STIMULI[source['case']] or stimulus.get('status')!='applied' or
            stimulus.get('actor_step_count_before')!=len(receipt['actor_steps']) or
            receipt.get('probe',{}).get('actor_actions_during_or_after_probe')!=0 or
            type(stimulus.get('dispatch_before_monotonic_ns')) is not int or
            type(stimulus.get('dispatch_after_monotonic_ns')) is not int or
            stimulus['dispatch_after_monotonic_ns']<stimulus['dispatch_before_monotonic_ns'] or not rows or
            rows[0]['probe_start_monotonic_ns']<stimulus['dispatch_after_monotonic_ns'] or
            receipt['actor_steps'][-1]['dispatch_after_monotonic_ns']>stimulus['dispatch_before_monotonic_ns'] or
            receipt['probe'].get('sample_ledger_sha256')!=old.digest(old._private(out/'samples.ndjson')) or
            receipt['probe'].get('raw_samples')!=len(rows)):
        raise ValueError('Restricted evaluator stimulus/raw probe/no subsequent actor boundary changed')
    prior.bound(root,stimulus['before_frame'])
    return rows


def _visual_binding(*, value: dict, record: dict) -> dict:
    root=Path(value['output_root']); out=record['out']; receipt=record['receipt']
    rows=_check_stimulus(root=root,out=out,receipt=receipt,source=record['source'])
    if len(rows)!=1: raise ValueError('Exact one modal-boundary sample required')
    sample=rows[0]; raw=prior.bound(root,sample['frame'])
    if (sample['window_title_before']!='Save' or sample['window_title_after']!='Save' or
            sample['window_id_before']!=sample['window_id_after'] or sample['window_id_before']==receipt['document_window_id'] or
            sample['document_window_stable'] is not False):
        raise ValueError('Exact native Save window identity boundary changed')
    return {'old_freeze_sha256':runner.OLD_FREEZE_SHA256,'old_run_sha256':runner.OLD_RUN_SHA256,
        'old_permit_sha256':runner.OLD_PERMIT_SHA256,'modal_intent_sha256':record['intent_sha256'],
        'modal_receipt_sha256':record['receipt_sha256'],'sample_ledger_sha256':old.digest(old._private(out/'samples.ndjson')),
        'raw_frame_sha256':old.digest(raw),'application_frame_sha256':sample['application_frame_sha256'],
        'window_title_before_sha256':sample['window_title_before_sha256'],
        'window_title_after_sha256':sample['window_title_after_sha256'],
        'window_id_before_sha256':sample['window_id_before_sha256'],'window_id_after_sha256':sample['window_id_after_sha256'],
        'first_probe_after_stimulus':True,'actor_actions_during_or_after_probe':0,
        'original_v7_terminal_status':'stopped_for_reconciliation','original_modal_classifier_passed':False}


def record_visual_adjudication(*, old_freeze: Path, old_run: Path, out_path: Path,
        independent_visual_inspection_accepted: bool=False, visual_observations: list[str]|None=None) -> dict:
    if independent_visual_inspection_accepted is not True or not visual_observations or len(visual_observations)<3:
        raise ValueError('Independent inspection of the original PNG and concrete visual observations required')
    value,_,records=_old_records(old_freeze=old_freeze,old_run=old_run)
    binding=_visual_binding(value=value,record=records[2])
    record={**binding,'schema':VISUAL_SCHEMA,'recorded_utc':old._now(),
        'decision':'native_file_save_dialog_visually_confirmed_at_window_boundary_stop',
        'basis':'independent_original_png_visual_inspection','visual_observations':visual_observations,
        'old_source_or_terminal_record_modified':False,'same_intent_replay_authorized':False,
        'official_final_admissions':0,'official_model_results':0}
    sha=old._write_new(out_path,record)
    return {'status':'separate_modal_visual_adjudication_written','private_record_sha256':sha,
            'original_v7_terminal_status':'stopped_for_reconciliation','official_final_admissions':0}


def check_visual(*, value: dict, record: dict, visual_adjudication: Path) -> dict:
    visual=json.loads(old._private(visual_adjudication)); binding=_visual_binding(value=value,record=record)
    if (visual.get('schema')!=VISUAL_SCHEMA or visual.get('decision')!='native_file_save_dialog_visually_confirmed_at_window_boundary_stop' or
            visual.get('basis')!='independent_original_png_visual_inspection' or
            len(visual.get('visual_observations',[]))<3 or visual.get('old_source_or_terminal_record_modified') is not False or
            visual.get('same_intent_replay_authorized') is not False or visual.get('official_final_admissions')!=0 or
            visual.get('official_model_results')!=0 or any(visual.get(k)!=v for k,v in binding.items())):
        raise ValueError('Separate independent modal visual adjudication binding changed')
    return visual


def _terminal_payload(*, old_freeze: Path, old_run: Path, visual_adjudication: Path,
                      reconciliation: Path) -> dict:
    value,run,records=_old_records(old_freeze=old_freeze,old_run=old_run)
    check_visual(value=value,record=records[2],visual_adjudication=visual_adjudication)
    rec_raw=old._private(reconciliation); rec=json.loads(rec_raw)
    ledger=storage_audit(Path(value['output_root']),verify_all_bytes=True)
    if (old.digest(rec_raw)!=RECONCILIATION_SHA256 or rec.get('schema')!='envloop-desktop-v7-poststop-reconciliation-private-v1' or
            rec.get('run_sha256')!=runner.OLD_RUN_SHA256 or rec.get('source_freeze_sha256')!=runner.OLD_FREEZE_SHA256 or
            rec.get('provider_active')!=0 or rec.get('unresolved_writes')!=0 or rec.get('retained_file_count')!=ledger['retained_file_count'] or
            rec.get('receipts')!=[{'cleanup_confirmed':True,'ordinal':i,'receipt_sha256':r['receipt_sha256']} for i,r in enumerate(records)] or
            rec.get('same_intent_replay_authorized') is not False or rec.get('model_calls')!=0 or rec.get('official_final_admissions')!=0 or
            ledger['unresolved_write_count']!=0):
        raise ValueError('Independent provider/storage poststop reconciliation changed')
    return {'schema':TERMINAL_SCHEMA,'status':'three_terminal_train_intents_independently_audited_old_stop_preserved',
        'old_freeze_sha256':runner.OLD_FREEZE_SHA256,'old_run_sha256':runner.OLD_RUN_SHA256,'old_permit_sha256':runner.OLD_PERMIT_SHA256,
        'old_receipt_sha256s':[r['receipt_sha256'] for r in records],'old_intent_sha256s':[r['intent_sha256'] for r in records],
        'visual_adjudication_sha256':old.digest(old._private(visual_adjudication)),
        'reconciliation_path':str(reconciliation),'reconciliation_sha256':RECONCILIATION_SHA256,
        'original_v7_terminal_status':'stopped_for_reconciliation','original_modal_classifier_passed':False,
        'saved_wrong_target_score_zero':1,'fresh_original_byte_resets':1,'separate_visual_modal_adjudications':1,
        'actor_actions_before_modal_stimulus':6,'actor_actions_during_or_after_modal_probe':0,
        'distinct_guests':3,'full_lease_intents_charged':3,'full_lease_seconds':1800,
        'provider_active_at_independent_reconciliation':0,'retained_raw_files_verified':ledger['retained_file_count'],
        'unresolved_writes':0,'same_intent_replay_authorized':False,'official_final_admissions':0,'official_model_results':0}


def write_terminal_audit(*, old_freeze: Path, old_run: Path, visual_adjudication: Path,
                        reconciliation: Path, private_path: Path, public_path: Path) -> dict:
    payload=_terminal_payload(old_freeze=old_freeze,old_run=old_run,visual_adjudication=visual_adjudication,reconciliation=reconciliation)
    sha=old._write_new(private_path,payload)
    public={k:v for k,v in payload.items() if k not in ['old_intent_sha256s','reconciliation_path']}
    public.update(schema='cua-native-wdi-v066-three-intent-terminal-audit-public-v8',private_audit_sha256=sha)
    old._write_new(public_path,public,public=True)
    return public


def validate_terminal_records(*, old_freeze: Path, old_run: Path,
        terminal_audit: Path, visual_adjudication: Path) -> dict:
    record=json.loads(old._private(terminal_audit))
    expected=_terminal_payload(old_freeze=old_freeze,old_run=old_run,visual_adjudication=visual_adjudication,
                               reconciliation=Path(record['reconciliation_path']))
    if record!=expected: raise ValueError('Immutable independent three-intent terminal audit changed')
    return record


def review(*, freeze_path: Path, review_path: Path, permit_path: Path,
        independent_root_review_accepted: bool=False, review_note: str='', active_probe=active_hashes) -> dict:
    if independent_root_review_accepted is not True or not review_note.strip():
        raise ValueError('Exact independent root acceptance and rationale required')
    value=runner.validate_source(freeze_path); root=Path(value['output_root'])
    if (root.exists() or root.is_symlink() or review_path==permit_path or
            any(not p.is_absolute() or p.exists() or p.is_symlink() for p in [review_path,permit_path])):
        raise ValueError('Exclusive unused remaining-only review/permit/output required')
    active,count=active_probe()
    if active or count: raise ValueError('Provider not active-zero before remaining-only root review')
    if storage_audit(root.parent)['dispatch_storage_ready'] is not True:
        raise ValueError('Remaining-only raw storage unavailable at root review')
    binding={'freeze_sha256':old.digest(old._private(freeze_path)),'source_sha256s':value['source_sha256s'],
        'output_root':value['output_root'],'guest_maximum':runner.MAX_GUESTS,'lease_seconds_each':old.LEASE_SECONDS,
        'old_run_sha256':runner.OLD_RUN_SHA256,'terminal_audit_sha256':value['terminal_audit_sha256'],
        'visual_adjudication_sha256':value['visual_adjudication_sha256'],
        'prior_full_lease_accounting':value['prior_full_lease_accounting'],'same_intent_replay_authorized':False,
        'official_final_admissions':0,'official_model_results':0}
    reviewed={**binding,'schema':REVIEW_SCHEMA,'status':'root_reviewed_exact_three_remaining_train_guests_no_create',
        'private_root_review_note':review_note,'provider_active_at_review':0,'storage_ready_at_review':True}
    review_sha=old._write_new(review_path,reviewed)
    permit={**binding,'schema':PERMIT_SCHEMA,'status':'root_reviewed_exact_three_remaining_train_guests',
        'review_path':str(review_path),'review_sha256':review_sha,'dispatch_authorized':True}
    permit_sha=old._write_new(permit_path,permit)
    return {'status':'private_remaining_train_permit_written_without_create','review_sha256':review_sha,
        'permit_sha256':permit_sha,'official_final_admissions':0}


def checked_permit(*, freeze_path: Path, permit_path: Path, value: dict) -> dict:
    permit=json.loads(old._private(permit_path)); review_path=Path(permit.get('review_path',''))
    if not review_path.is_absolute(): raise ValueError('Exact independent remaining-only review path missing')
    raw=old._private(review_path); reviewed=json.loads(raw)
    fields={'freeze_sha256':old.digest(old._private(freeze_path)),'source_sha256s':value['source_sha256s'],
        'output_root':value['output_root'],'guest_maximum':runner.MAX_GUESTS,'lease_seconds_each':old.LEASE_SECONDS,
        'old_run_sha256':runner.OLD_RUN_SHA256,'terminal_audit_sha256':value['terminal_audit_sha256'],
        'visual_adjudication_sha256':value['visual_adjudication_sha256'],
        'prior_full_lease_accounting':value['prior_full_lease_accounting'],'same_intent_replay_authorized':False,
        'official_final_admissions':0,'official_model_results':0}
    if (permit.get('schema')!=PERMIT_SCHEMA or permit.get('status')!='root_reviewed_exact_three_remaining_train_guests' or
            permit.get('dispatch_authorized') is not True or permit.get('review_sha256')!=old.digest(raw) or
            reviewed.get('schema')!=REVIEW_SCHEMA or reviewed.get('status')!='root_reviewed_exact_three_remaining_train_guests_no_create' or
            not reviewed.get('private_root_review_note','').strip() or reviewed.get('provider_active_at_review')!=0 or
            reviewed.get('storage_ready_at_review') is not True or any(permit.get(k)!=v or reviewed.get(k)!=v for k,v in fields.items())):
        raise ValueError('Exact three-intent remaining-only permit binding changed')
    return permit


def audit(*, freeze_path: Path, run_path: Path, active_probe=active_hashes) -> dict:
    value=runner.validate_source(freeze_path); root=Path(value['output_root']); run=json.loads(old._private(run_path))
    if (run_path!=root/'run-receipt.json' or run.get('schema')!=runner.RUN_SCHEMA or
            run.get('freeze_sha256')!=old.digest(old._private(freeze_path)) or run.get('source_sha256s')!=value['source_sha256s'] or
            run.get('guest_count_maximum')!=runner.MAX_GUESTS or len(run.get('attempts',[]))!=runner.MAX_GUESTS or
            run.get('original_v7_planned_ordinals')!=[3,4,5] or
            run.get('same_intent_replay_authorized') is not False or run.get('official_final_admissions')!=0 or
            run.get('official_model_results')!=0):
        raise ValueError('One-use remaining-only run journal changed')
    permit_path=Path(run.get('permit_path',''))
    if not permit_path.is_absolute() or old.digest(old._private(permit_path))!=run.get('permit_sha256'):
        raise ValueError('Remaining-only run exact permit bytes changed')
    checked_permit(freeze_path=freeze_path,permit_path=permit_path,value=value)
    old_value,_,old_records=_old_records(old_freeze=Path(value['old_freeze_path']),old_run=Path(value['old_run_path']))
    ids={r['receipt']['sandbox_id_sha256'] for r in old_records}; classifications=[]
    for ordinal,planned in enumerate(value['sequence']):
        source=planned['source']; attempt=planned['attempt']; out=root/f'{ordinal:02d}-{source["case"]}-{attempt}'
        intent_raw=old._private(out/'intent.json'); intent=json.loads(intent_raw)
        receipt_raw=old._private(out/'receipt.json'); receipt=json.loads(receipt_raw)
        journal=run['attempts'][ordinal]
        ancestry_raw=old._private(root/f'intent-ancestry-{ordinal:02d}.private.json')
        ancestry=json.loads(ancestry_raw)
        expected_ancestry=runner.ancestry_payload(value=value,planned=planned,ordinal=ordinal,
            freeze_sha=run['freeze_sha256'],permit_sha=run['permit_sha256'])
        if (journal.get('original_v7_planned_ordinal')!=ordinal+3 or journal.get('ancestry_sha256')!=old.digest(ancestry_raw) or
                {k:v for k,v in ancestry.items() if k!='created_utc'}!=expected_ancestry or
                type(ancestry.get('created_utc')) is not str or ancestry['created_utc']>intent.get('created_utc','')):
            raise ValueError('Original planned ordinal3/4/5 pre-create ancestry changed')
        if (intent.get('schema')!=old.INTENT_SCHEMA or receipt.get('schema')!=old.RECEIPT_SCHEMA or
                intent.get('status')!='recorded_before_provider_create' or intent.get('freeze_sha256')!=run['freeze_sha256'] or
                intent.get('permit_sha256')!=run['permit_sha256'] or intent.get('same_intent_replay_authorized') is not False or
                receipt.get('intent_sha256')!=old.digest(intent_raw) or journal.get('receipt_sha256')!=old.digest(receipt_raw) or
                journal.get('ordinal')!=ordinal or journal.get('case')!=source['case'] or
                journal.get('attempt')!=attempt or journal.get('status')!=receipt.get('status') or
                receipt.get('provider_kind')!='e2b_desktop' or
                any(v.get('split')!='train' or v.get('case')!=source['case'] or v.get('attempt')!=attempt or
                    v.get('ordinal')!=ordinal or v.get('package_sha256')!=source['row']['package_sha256'] or
                    v.get('input_sha256')!=source['row']['input_sha256'] or v.get('lease_seconds')!=old.LEASE_SECONDS or
                    v.get('official_final_admissions')!=0 for v in [intent,receipt]) or
                receipt.get('guest_content_attested') is not True or receipt.get('fresh_profile_absent') is not True or
                receipt.get('kill_returned') is not True or receipt.get('is_running_after_kill') is not False or
                receipt.get('official_model_results')!=0):
            raise ValueError('New remaining-only intent, source, raw receipt or cleanup changed')
        sid=receipt.get('sandbox_id_sha256')
        if type(sid) is not str or len(sid)!=64 or sid in ids: raise ValueError('Old/new TRAIN guests must all be distinct')
        ids.add(sid)
        directory,baseline,oracle=admit._package(Path(value['candidate_root']),source['row'])
        prior._audit_profile(root=root,receipt=receipt,reference_path=Path(value['scoped_reference']))
        if attempt=='cold-reset':
            if receipt.get('status')!='cold_reset_observed' or receipt.get('actor_steps')!=[] or prior.bound(root,receipt['restored_artifact'])!=baseline:
                raise ValueError('Remaining original-byte cold reset failed')
            prior.bound(root,receipt['cold_observation'])
        else:
            prior._audit_actions(root=root,receipt=receipt,source=source,oracle=oracle,instruction=(directory/'actor_task.txt').read_text())
            _check_stimulus(root=root,out=out,receipt=receipt,source=source)
            classification=prior.audit_samples(root=root,out=out,filename=source['filename'],document_id=receipt['document_window_id'])
            if (receipt.get('status')!='no_action_probe_audited' or receipt.get('probe_classification')!=classification or
                    classification['classification'] not in ['real_material_oscillation_stop',
                        'caret_only_probe_material_oscillation_inconclusive','no_material_oscillation_observed_inconclusive']):
                raise ValueError('Remaining no-action probe classification changed')
            classifications.append(classification['classification'])
    ledger=storage_audit(root,verify_all_bytes=True); active,count=active_probe()
    if active or count or ledger['unresolved_write_count']: raise ValueError('Remaining raw evidence/provider cleanup incomplete')
    oscillation=classifications==['real_material_oscillation_stop']
    return {'schema':'cua-native-wdi-v066-post-enter-remaining-audit-public-v8',
        'status':'remaining_train_controls_and_material_oscillation_audited' if oscillation else 'remaining_train_resets_audited_material_oscillation_inconclusive',
        'old_run_sha256':runner.OLD_RUN_SHA256,'original_v7_terminal_status':'stopped_for_reconciliation',
        'saved_wrong_target_score_zero':1,'separate_visual_modal_adjudications':1,'combined_original_byte_resets':3,
        'new_original_byte_resets':2,'new_full_lease_intents_charged':3,'combined_full_lease_intents_charged':6,
        'original_v7_planned_ordinals_completed':[3,4,5],
        'combined_distinct_guests':len(ids),'no_action_probe_classifications':classifications,
        'material_oscillation_proven':oscillation,'provider_active_after':0,'same_intent_replay_authorized':False,
        'official_final_admissions':0,'official_model_results':0}


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['review','audit']); parser.add_argument('--freeze',type=Path,required=True)
    parser.add_argument('--review-out',type=Path); parser.add_argument('--permit-out',type=Path); parser.add_argument('--run',type=Path)
    parser.add_argument('--accept-independent-root-review',action='store_true'); parser.add_argument('--private-review-note',default='')
    args=parser.parse_args()
    if args.mode=='review':
        if args.review_out is None or args.permit_out is None: raise ValueError('Exact private review/permit paths required')
        result=review(freeze_path=args.freeze,review_path=args.review_out,permit_path=args.permit_out,
            independent_root_review_accepted=args.accept_independent_root_review,review_note=args.private_review_note)
    else:
        if args.run is None: raise ValueError('Exact remaining-only run journal required')
        result=audit(freeze_path=args.freeze,run_path=args.run)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__': main()
