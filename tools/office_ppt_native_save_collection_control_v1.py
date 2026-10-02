"""Accept one exact historical native PPT TRAIN collection for development.

This is an explicit saved-serialization policy, separate from the unchanged
strict Office auditor. It reopens real folder evidence and exact download
pairs, never uses scorer_factory, and grants no registration or model score.
The pinned human-save metadata is not a general student artifact policy.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ppt_wdi_factory import verify
from tools import office_single_account_train_pilot_v1 as manual
from tools import ppt_native_train_collection_proposal_v1 as proposal

POLICY_ID='ppt-native-save-one-frozen-train-collection-v1'
STATUS='passed_manual_folder_train_native_save_development_control'
REVIEW_SHA='5f9aa5380ff1ea8c6739501102252a523db8491cf89a9611bea2f4c64b8fbfb2'
ADVERSARIAL_AUDIT_SHA='1a567ca6e88edf602205197e9eeab5741daa8f5632b7bd34309ee1dff70238bd'
FOLDER_EVIDENCE_SHA='256abc6cba19b87414328dad3d4af3cc07ba4ad5b24f9dfdf4d6f7d32628c6bf'
CORRECTED_PROPOSAL_SOURCE_SHA='ceba4d7ef39ada9c79aaab7935a66dccd2f3eddfe50a0092d07480a018e4e91a'


def source_hashes() -> dict:
    root=Path(__file__).resolve().parents[1]
    return {name:manual._sha((root/name).read_bytes()) for name in (
        'tools/office_ppt_native_save_collection_control_v1.py',
        'tools/office_single_account_train_pilot_v1.py',
        'tools/ppt_native_train_collection_proposal_v1.py',
        'ppt_wdi_factory/verify.py',
        'ppt_wdi_factory/plan.py',
        'tools/audit_ppt_wdi_web_train_triad_v1.py')}


def reviewed_policy(adversarial_audit: Path, *, work_root: Path) -> dict:
    root=Path(__file__).resolve().parents[1]
    review_path=root/'docs/evidence/office-ppt-one-collection-independent-review-20260930.json'
    review_raw=review_path.read_bytes()
    manual._require(manual._sha(review_raw)==REVIEW_SHA,
                    'native_save_independent_review_changed')
    review=json.loads(review_raw)
    audit,audit_raw=manual._json(adversarial_audit,work_root)
    manual._require(manual._sha(audit_raw)==ADVERSARIAL_AUDIT_SHA and
        audit['schema']=='ppt-native-one-collection-proposal-audit-private-v1' and
        audit['rejected_adversarial_count']==46 and audit['equivalent_controls_passed']==2 and
        audit['historical_raw_score']['score']==0 and audit['registered'] is False and
        audit['model_calls']==0 and audit['official_final_credit']==0 and
        review['status']=='corrected_single_train_proposal_approved_offline_only' and
        review['corrected_adversarial_controls_rejected']==46 and
        review['corrected_equivalent_controls_passed']==2,
        'native_save_corrected_adversarial_evidence_required')
    hashes=source_hashes()
    manual._require(hashes['tools/ppt_native_train_collection_proposal_v1.py']==CORRECTED_PROPOSAL_SOURCE_SHA and
        hashes['ppt_wdi_factory/verify.py']==proposal.CORE_VERIFIER_SHA,
        'native_save_reviewed_proposal_or_strict_core_changed')
    return {'schema':'office-ppt-one-collection-native-save-policy-v1',
        'policy_id':POLICY_ID,'scope':'exact_historical_manual_train_collection_only',
        'collection_sha256':proposal.COLLECTION_SHA,
        'task_sha256':proposal.TASK_SHA,'source_sha256':proposal.SOURCE_SHA,
        'before_reset_sha256':proposal.BEFORE_SHA,'saved_sha256':proposal.SAVED_SHA,
        'truthful_folder_evidence_sha256':FOLDER_EVIDENCE_SHA,
        'independent_review_sha256':REVIEW_SHA,
        'corrected_adversarial_audit_sha256':ADVERSARIAL_AUDIT_SHA,
        'scoring_source_hashes':hashes,'raw_strict_scorer_unchanged':True,
        'exact_non_target_human_save_metadata_pinned':True,
        'generic_student_verifier_qualified':False,'registered':False,
        'selection_or_final_eligible':False,'official_final_credit':0}


class NativeSaveScorer:
    """Compose the strict source/reset scorer and reviewed one-collection policy."""
    def __init__(self, collection: Path, *, work_root: Path):
        self.proposal=proposal.FrozenTrainProposal(collection,work_root=work_root)
        self.spec,spec_raw=manual._json(Path(collection)/'spec.private.json',work_root)
        task,_=manual._ref(self.spec['task_ref'],work_root)
        source,_=manual._ref(self.spec['source_ref'],work_root)
        self.paths={'task':task,'source':source}
        self.strict=manual.OfficeTrainScorer(self.spec,self.paths)

    def baseline(self,path: Path) -> dict:
        manual._require(manual._sha(path.read_bytes())==proposal.BEFORE_SHA,
                        'native_save_exact_before_required')
        return self.strict.baseline(path)

    def saved(self,baseline: Path,candidate: Path) -> dict:
        manual._require(manual._sha(candidate.read_bytes())==proposal.SAVED_SHA,
                        'native_save_exact_historical_saved_required')
        raw=verify.verify(baseline,candidate,self.strict.ppt_oracle)
        canonical=self.proposal.score(candidate)
        manual._require(raw['score']==0 and raw['target_correct'] is True and
            raw['preservation_pass'] is False and len(raw['unexpected_parts'])==10 and
            canonical['score']==1 and canonical['target_correct'] is True and
            canonical['preservation_pass'] is True and canonical['normalization_applied'] is True,
            'native_save_historical_raw_or_canonical_score_changed')
        return {'score':1,'raw_strict_score':0,'canonical_score':1,'target_count':4,
            'raw_strict_result':raw,'one_collection_canonical_result':canonical,
            'raw_result_sha256':manual._sha(manual._canonical(raw)),
            'canonical_result_sha256':manual._sha(manual._canonical(canonical)),
            'generic_student_verifier_qualified':False}

    def reset(self,baseline: Path,candidate: Path) -> dict:
        manual._require(manual._sha(candidate.read_bytes())==proposal.BEFORE_SHA,
                        'native_save_exact_reset_required')
        return self.strict.reset(baseline,candidate)


def audit(collection: Path, adversarial_audit: Path, out: Path, *, work_root: Path) -> dict:
    root=Path(work_root).resolve()
    collection=Path(collection).resolve()
    policy=reviewed_policy(adversarial_audit,work_root=root)
    scorer=NativeSaveScorer(collection,work_root=root)
    spec=scorer.spec
    spec_raw=manual._private(collection/'spec.private.json',root)
    manual._require(spec['schema']==manual.SPEC_SCHEMA and spec['cell_id']=='powerpoint-web' and
        spec['split']=='train' and spec['official_final_credit']==0 and
        manual._train_package_path(scorer.paths['task'],'powerpoint-web') and
        scorer.paths['task'].parent.name==spec['task_id'] and
        scorer.paths['source']==scorer.paths['task'].parent/'source.pptx',
        'native_save_exact_train_package_required')
    evidence_path=collection/'folder-scope-evidence.private.json'
    evidence_raw=manual._private(evidence_path,root)
    manual._require(manual._sha(evidence_raw)==FOLDER_EVIDENCE_SHA,
                    'native_save_truthful_folder_evidence_changed')
    actor=manual._item(spec['actor_item'],'powerpoint-web')
    reset=manual._item(spec['reset_item'],'powerpoint-web')
    manual._require(actor['sourcedoc_sha256']!=reset['sourcedoc_sha256'],
                    'native_save_reset_document_not_distinct')
    evidence,files,gui=manual.inspect_manual_evidence(spec,spec_raw,evidence_path,root,
        actor,reset,scorer.paths,evidence_schema=manual.FOLDER_EVIDENCE_SCHEMA,
        account_scope=manual.EXISTING_FOLDER_SCOPE)
    baseline=scorer.baseline(files['before'])
    saved=scorer.saved(files['before'],files['saved'])
    neutral=scorer.reset(files['before'],files['reset'])
    manual._require(baseline['neutral_score']==0 and saved['score']==1 and neutral['score']==0,
                    'native_save_manual_control_scores_invalid')
    out=Path(out).absolute()
    manual._require(not out.exists() and not out.is_symlink() and
                    out.parent.resolve().is_relative_to(root),
                    'native_save_fresh_private_output_required')
    out.mkdir(mode=0o700)
    policy_sha=manual._write_new(out/'native-save-policy.private.json',manual._canonical(policy))
    saved_sha=manual._write_new(out/'saved-scores.private.json',manual._canonical(saved))
    source_hashes_value=policy['scoring_source_hashes']
    receipt={'schema':manual.PRIVATE_RECEIPT_SCHEMA,'status':STATUS,
        'cell_id':'powerpoint-web','task_id':spec['task_id'],'package_sha256':spec['package_sha256'],
        'spec_sha256':manual._sha(spec_raw),'evidence_sha256':manual._sha(evidence_raw),
        'collection_sha256':proposal.COLLECTION_SHA,'source_sha256':proposal.SOURCE_SHA,
        'before_sha256':proposal.BEFORE_SHA,'saved_sha256':proposal.SAVED_SHA,
        'reset_sha256':proposal.BEFORE_SHA,'scoring_policy_id':POLICY_ID,
        'native_save_policy_sha256':policy_sha,'scoring_source_hashes':source_hashes_value,
        'saved_score_receipt_sha256':saved_sha,'source_equivalence_sha256':baseline['source_equivalence_sha256'],
        'reset_verifier_sha256':neutral['verifier_result_sha256'],
        'raw_strict_saved_score':0,'one_collection_canonical_saved_score':1,
        'baseline_score':0,'fresh_reset_score':0,'target_count':4,
        'original_software_gui_operator_reviewed':True,'independent_scorer_executed':True,
        'download_count':6,'folder_inventory_count':4,
        'dedicated_folder_empty_after_cleanup':True,'account_scope':manual.EXISTING_FOLDER_SCOPE,
        'dedicated_test_account_operator_asserted':False,'account_wide_acl_independently_verified':False,
        'one_file_permission_independently_verified':False,'download_item_identity_independently_verified':False,
        'automated_model_scope_qualified':False,'generic_student_verifier_qualified':False,
        'exact_historical_collection_only':True,'model_calls':0,'provider_calls':0,
        'registered':False,'selection_or_final_admitted':False,'official_final_credit':0}
    receipt_sha=manual._write_new(out/'receipt.private.json',manual._canonical(receipt))
    return {'schema':'office-ppt-native-save-one-collection-control-public-v1','status':STATUS,
        'receipt_sha256':receipt_sha,'native_save_policy_sha256':policy_sha,
        'scoring_source_hashes':source_hashes_value,'collection_sha256':proposal.COLLECTION_SHA,
        'corrected_adversarial_audit_sha256':ADVERSARIAL_AUDIT_SHA,
        'raw_strict_saved_score':0,'one_collection_canonical_saved_score':1,
        'baseline_score':0,'fresh_reset_score':0,'target_count':4,
        'source_slides_checked':7,'chart_cache_values_checked':26,
        'download_pairs':3,'folder_inventories':4,'folder_empty_after_cleanup':True,
        'account_scope':manual.EXISTING_FOLDER_SCOPE,'dedicated_test_account_asserted':False,
        'exact_historical_collection_only':True,'generic_student_verifier_qualified':False,
        'original_raw_failed_receipt_unchanged':True,'scorer_factory_used':False,
        'live_browser_actions':0,'provider_calls':0,'model_calls':0,'registered':False,
        'selection_admissions':0,'final_admissions':0,'official_final_credit':0}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--collection',type=Path,required=True)
    p.add_argument('--adversarial-audit',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    print(json.dumps(audit(args.collection,args.adversarial_audit,args.out,
                          work_root=Path.cwd()/'work'),sort_keys=True))


if __name__=='__main__':main()
