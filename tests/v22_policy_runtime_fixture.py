"""Synthetic v22 construction; no old native or campaign receipt is rewritten."""
import copy
import json
from unittest.mock import patch
from cursibench import full_study_runtime_v2 as r
from cursibench import full_study_policy_amendment_v2 as p
from cursibench import full_study_shared_base_selection_v1 as shared
from cursibench import full_study_performance_coverage_v2 as coverage
from cursibench import full_study_final_dispatch_v1 as final
from tests import shared_base_selection_fixture as base


def study(parent):
    amendment=p.build(parent.plan,user_authorization_sha256='a'*64,pre_result_review_sha256='b'*64)
    manifest=r.build_manifest(parent.plan,amendment,parent_protocol_sha256=parent.manifest_sha256,
        ratification_sha256=parent.ratification_sha256,source_manifest_sha256=r.policy.sha(r.policy.canonical(r.source_manifest(__import__('pathlib').Path(r.__file__).resolve().parents[2]))))
    return r.FrozenStudy(qualified_parent=parent,amendment=amendment,manifest=manifest,
        witness_bytes=p.canonical(r.witness(manifest)))


def base_receipt(study,cell):
    with patch.object(shared,'receipt_path',r.shared_receipt_path),patch.object(shared,'RECEIPT_SCHEMA','cua-full-study-shared-base-performance-receipt-v2'),patch.object(base.environment,'category',r.environment.category):
        path=base.build(study,study.budget,cell)
    value=json.loads(path.read_bytes());calls=[]
    for ref in value['paid_attempt_refs']:
        ref['budget_performance_ref']=None
        request,_=shared._json_ref(path.parent,ref['request_ref']);result,_=shared._json_ref(path.parent,ref['result_ref'])
        calls.append({'attempt_id':ref['attempt_id'],'category':ref['category'],'request':request,
            'result_present':True,'result_status':result['status']})
    checked=coverage.validate(plan=study.parent.plan,amendment=study.amendment,cell_id=cell,owner_slot='shared-base',
        attempt_id=value['selection_attempt'],checkpoint_sha256=value['base_checkpoint_sha256'],
        selection_tasks=study.task_views(cell)['selection'],paid_calls=calls,
        related_paid_attempt_ids=set(value['paid_attempt_ids']),budget_performance_receipts=[])
    value['paid_coverage_sha256']=checked['coverage_sha256'];path.write_bytes(p.canonical(value))
    study.admit_shared_base_selection(cell,path)
    return path


def final_gate(f):
    st=study(f.frozen);prepared=f.work/'prepared-matrix-v2'
    plan=r.prepare_matrix(st,f.matrix_path,prepared);completions=[]
    for entry in f.completions:
        # A fresh synthetic chain uses the new immutable policy header.
        old_path=f.work/entry['campaign_journal']['path']
        rows=[json.loads(line) for line in old_path.read_bytes().splitlines()]
        target=f.work/'fresh-synthetic-v2-campaigns'/entry['cell_id']/entry['researcher_id'];target.mkdir(mode=0o700,parents=True)
        old_freeze=f.work/entry['selection_freeze']['path'];freeze=target/'selection-freeze.private.json'
        final.private_write_new(freeze,old_freeze.read_bytes())
        header={k:v for k,v in rows[0].items() if k not in {'hash','previous'}}
        header['plan_sha256']=st.plan_sha256;header['public_witness_sha256']=st.public_witness_sha256
        journal=r.campaign.CampaignJournal(target/'campaign.jsonl',header)
        for row in rows[1:]:journal.append(row['kind'],row['data'])
        completions.append({'cell_id':entry['cell_id'],'researcher_id':entry['researcher_id'],
            'selection_freeze':final.reference(f.work,freeze),'campaign_journal':final.reference(f.work,journal.path)})
    index=f.work/'completion-v2.private.json'
    payload={'schema':final.GATE_SCHEMA,'study_id':plan['study_id'],'matrix_plan_sha256':p.sha(r.evidence.json_bytes(plan)),
        'retry_rule_sha256':final.RETRY_RULE_SHA256,'campaigns':completions}
    final.private_write_new(index,p.canonical(payload))
    witness=copy.deepcopy(f.public_final_witness);witness['pre_campaign_public_witness_sha256']=st.public_witness_sha256
    witness['matrix_plan_sha256']=payload['matrix_plan_sha256'];witness['completion_index_sha256']=p.sha(index.read_bytes())
    envelope={'schema':'cua-full-study-policy-final-witness-v2','amendment_sha256':st.amendment_sha256,
        'policy_manifest_sha256':st.manifest_sha256,'qualified_final_witness':witness}
    gate=r.FinalGate(st,matrix_manifest_path=f.matrix_path,prepared_matrix_dir=prepared,completion_index_path=index,
        final_public_commit_sha1='c'*40,policy_final_witness_bytes=p.canonical(envelope))
    return gate,envelope,index
