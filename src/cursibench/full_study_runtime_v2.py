"""Explicit witnessed v2 runtime envelope around qualified immutable inputs.

No provider or final task is opened by construction. Historical nominal plans
remain parent evidence; v2 spending authority and performance are separate.
"""
from __future__ import annotations
import json
from pathlib import Path
import time
import hashlib
import argparse
from types import ModuleType
from types import SimpleNamespace

from . import full_study_campaign_dispatch_v1 as campaign
from . import full_study_policy_amendment_v2 as policy
from . import full_study_unlimited_budget_v2 as dollars
from . import full_study_performance_coverage_v2 as performance
from . import full_study_matrix_v1 as matrix
from . import full_study_selection_environment_v2 as environment
from . import scale_final_v06 as evidence
from . import full_study_shared_base_selection_v1 as shared
from contextlib import contextmanager
from unittest.mock import patch
from native_desktop_factory.actor_deadline_future_v21 import ActorDeadlineReached
import inspect
import textwrap

MANIFEST_SCHEMA='cua-full-study-witnessed-unlimited-performance-manifest-v2'
WITNESS_SCHEMA='cua-full-study-pre-result-policy-witness-v2'


def private(path,root):
    path=Path(path);root=Path(root).resolve()
    if path.is_symlink() or not path.resolve().is_relative_to(root) or path.stat().st_mode&0o077:
        raise ValueError('private_policy_runtime_reference_required')
    raw=path.read_bytes();return json.loads(raw),raw


def build_manifest(parent_plan,amendment,*,parent_protocol_sha256,ratification_sha256,source_manifest_sha256):
    digest=policy.validate(amendment,parent_plan)
    for value in [parent_protocol_sha256,ratification_sha256,source_manifest_sha256]:
        if not evidence.is_hash(value):raise ValueError('policy_manifest_binding_hash_required')
    return {'schema':MANIFEST_SCHEMA,'status':'frozen_before_official_results',
        'parent_plan_sha256':amendment['parent_plan_sha256'],'parent_protocol_sha256':parent_protocol_sha256,
        'amendment_sha256':digest,'ratification_sha256':ratification_sha256,
        'source_manifest_sha256':source_manifest_sha256,'campaign_count':24,
        'execution_policy_version':'uniform-90-720-1200-v22','actor_clock_excludes_native_lifecycle':True,
        'native_runtime_qualification_status':'not_claimed_by_source_policy',
        'distinct_official_task_identities':600,'initial_slot_task_results':3000,
        'configuration_slots':amendment['configuration_slots'],'compute_limits':amendment['retained_campaign_compute_limits'],
        'task_limits':amendment['retained_task_limits'],'dollar_ceiling_usd':None,
        'native_environment_by_cell':amendment['native_environment_by_cell'],
        'environment_policy_sha256':amendment['environment_policy_sha256'],
        'cost_completeness_separate_from_performance':True,'official_model_results_before_freeze':0}


def witness(manifest):
    return {'schema':WITNESS_SCHEMA,'manifest_sha256':policy.sha(policy.canonical(manifest)),
        'amendment_sha256':manifest['amendment_sha256'],'source_manifest_sha256':manifest['source_manifest_sha256'],
        'campaign_count':24,'distinct_official_task_identities':600,'initial_slot_task_results':3000,
        'official_model_results_before_freeze':0}


class FrozenStudy:
    def __init__(self,*,qualified_parent,amendment,manifest,witness_bytes):
        if type(qualified_parent) is not campaign.FrozenStudy:
            raise ValueError('real_600_qualified_parent_required')
        self.parent=qualified_parent;self.repo_root=qualified_parent.repo_root
        self.amendment=amendment;self.amendment_sha256=policy.validate(amendment,qualified_parent.plan)
        expected_manifest=build_manifest(qualified_parent.plan,amendment,parent_protocol_sha256=qualified_parent.manifest_sha256,
            ratification_sha256=qualified_parent.ratification_sha256,source_manifest_sha256=policy.sha(policy.canonical(source_manifest(Path(__file__).resolve().parents[2]))))
        if manifest!=expected_manifest:raise ValueError('full_policy_manifest_or_current_source_binding_changed')
        if (manifest.get('schema')!=MANIFEST_SCHEMA or manifest.get('amendment_sha256')!=self.amendment_sha256 or
            manifest.get('parent_plan_sha256')!=qualified_parent.plan_sha256 or
            manifest.get('parent_protocol_sha256')!=qualified_parent.manifest_sha256 or
            manifest.get('ratification_sha256')!=qualified_parent.ratification_sha256 or
            manifest.get('official_model_results_before_freeze')!=0 or
            json.loads(witness_bytes)!=witness(manifest)):
            raise ValueError('fresh_policy_witness_does_not_bind_qualified_parent')
        self.policy_manifest=manifest;self.manifest=qualified_parent.manifest;self.manifest_sha256=policy.sha(policy.canonical(manifest))
        self.plan={**qualified_parent.plan,'policy_version':2,'effective_policy_manifest_sha256':self.manifest_sha256,
            'effective_dollar_ceiling_usd':None,'effective_amendment_sha256':self.amendment_sha256}
        import copy
        self.plan['cells']=copy.deepcopy(self.plan['cells'])
        for cell in self.plan['cells']:
            cell['execution']={**cell['execution'],'max_actions_per_task':90,'max_wall_seconds_per_task':720}
        self.plan_sha256=self.manifest_sha256
        self.protocol_manifest_sha256=qualified_parent.manifest_sha256
        self.budget=dollars.StudyBudgetLedger(self.repo_root/'work/full-study-budget-v2.private.jsonl',qualified_parent.plan,amendment)
        self.ratification_sha256=qualified_parent.ratification_sha256
        self.public_witness_sha256=policy.sha(witness_bytes)
        self.intents=qualified_parent.intents

    def __getattr__(self,name):return getattr(self.parent,name)

    def task_views(self,cell_id):return self.parent.task_views(cell_id)
    def researcher_configuration(self,owner):return self.parent.researcher_configuration(owner)
    def student_training_configuration(self):return self.parent.student_training_configuration()

    def open_campaign(self,directory,*,cell_id,researcher_id,now=time.time):
        owner=(cell_id,researcher_id)
        if owner not in self.intents:raise ValueError('undeclared_campaign')
        verify_shared_receipt(self,self.budget,cell_id,shared_receipt_path(self,cell_id))
        target=Path(directory).absolute();work=self.repo_root/'work'
        if target.is_symlink() or not target.parent.resolve().is_relative_to(work.resolve()):
            raise ValueError('private_work_directory_required')
        target.mkdir(mode=0o700,parents=True,exist_ok=True);target.chmod(0o700)
        return CampaignSession(self,target,self.intents[owner],now=now)

    def admit_shared_base_selection(self,cell_id,source):
        value,_=private(source,self.repo_root/'work')
        if cell_id=='desktop-native' and value.get('schema')=='cua-native-desktop-v22-shared-base-performance':
            result,digest=verify_shared_receipt(self,self.budget,cell_id,source,require_registry=False)
            root=shared_receipt_path(self,cell_id).parent
            campaign._private_write_new(root/'accepted.private.json',policy.canonical({'schema':shared.REGISTRY_SCHEMA,'cell_id':cell_id,'receipt_sha256':digest}))
            return {'task_count':20,'wins':sum(v['score'] for v in result['tasks']),'receipt_sha256':digest}
        return _checked_shared_verifier(self).admit_receipt(self,self.budget,cell_id,source)


class CampaignSession(campaign.CampaignSession):
    def __init__(self,study,directory,intent,*,now=time.time):
        if type(study) is not FrozenStudy:raise ValueError('witnessed_v2_study_required')
        directory.mkdir(parents=True,exist_ok=True,mode=0o700)
        self._pending_budget_stops={}
        super().__init__(study,directory,intent,study.budget,now=now)

    def authorize_verified_budget_stop(self,attempt_id,*,verification):
        """A checked performance event permits new work, never replays old work."""
        self._check_time()
        if self._events('selection_frozen') or any(r['data']['attempt_id']==attempt_id for r in self._events('budget_performance_closed_v2')):raise ValueError('budget_receipt_already_closed_or_selection_frozen')
        self._audit_paid_files()
        receipt=verify_budget_artifacts(self.study,self.intent['researcher_id'],verification)
        state=self.budget.owner_attempts(self.owner).get(attempt_id)
        if (state is None or state['status']!='uncertain' or state['category']!='tinker' or receipt.get('sample_paid_attempt_id')!=attempt_id or
            receipt.get('amendment_sha256')!=self.study.amendment_sha256 or
            receipt.get('performance_coverage_eligible') is not True or receipt.get('provider_close_acknowledged') is not True or
            receipt['performance'].get('status')!='independently_saved_scored_and_reset' or
            receipt['inference'].get('request_replayed') is not False):
            raise ValueError('only_checked_owned_budget_stop_can_close_performance_failure')
        path=self.directory/(attempt_id+'.budget-performance-v2.private.json')
        campaign._private_write_new(path,policy.canonical(receipt))
        self.journal.append('budget_performance_closed_v2',{'attempt_id':attempt_id,'verification':verification,
            'receipt_sha256':policy.sha(path.read_bytes()),'billing_settled':False,'epoch_seconds':int(self.now())})
        self._pending_budget_stops.pop(attempt_id,None)

    def _unresolved_failure(self):
        unresolved={r['data']['attempt_id'] for r in self._events('paid_uncertain')}
        reconciled={r['data']['attempt_id'] for r in self._events('paid_reconciled')}
        verified=set()
        for row in self._events('budget_performance_closed_v2'):
            path=self.directory/(row['data']['attempt_id']+'.budget-performance-v2.private.json')
            receipt,raw=private(path,self.directory)
            if policy.sha(raw)!=row['data']['receipt_sha256'] or receipt.get('amendment_sha256')!=self.study.amendment_sha256:
                raise ValueError('budget_performance_private_file_hash_changed')
            fresh=verify_budget_artifacts(self.study,self.intent['researcher_id'],row['data']['verification'])
            if fresh!=receipt:raise ValueError('budget_performance_independent_recheck_changed')
            verified.add(row['data']['attempt_id'])
        return bool(unresolved-reconciled-verified)

    def dispatch_tinker_sft(self,**kwargs):
        # The inherited renderer, source/role checks and optimizer path stay
        # intact. Only the old quote-versus-dollar-cap comparison is removed.
        return _dispatch_tinker_sft_uncapped(self,**kwargs)

    def _selection_paid_coverage(self,*,attempt_id,checkpoint_sha256,paid_attempt_ids):
        self._audit_paid_files()
        starts=[r for r in self._events('selection_started') if r['data']['attempt_id']==attempt_id]
        if len(starts)!=1:raise ValueError('selection_paid_start_missing')
        related=[r for r in self._events('paid_intent') if r['data']['attempt_id'].startswith(attempt_id+'-')]
        if any(r['sequence']<=starts[0]['sequence'] for r in related) or set(paid_attempt_ids)!={r['data']['attempt_id'] for r in related}:
            raise ValueError('selection_paid_attempt_hidden_or_missing')
        completed={r['data']['attempt_id']:r['data'] for r in self._events('paid_result')}
        calls=[];receipts=[]
        for event in related:
            data=event['data'];identifier=data['attempt_id']
            request,raw=private(self.directory/(identifier+'.request.private.json'),self.directory)
            if policy.sha(raw)!=data['request_sha256']:raise ValueError('selection_paid_request_changed')
            result=None
            if identifier in completed:
                result,raw=private(self.directory/(identifier+'.result.private.json'),self.directory)
                if policy.sha(raw)!=completed[identifier]['result_sha256']:raise ValueError('selection_paid_result_changed')
            else:receipts.append(_read_checked_budget_receipt(self,identifier))
            calls.append({'attempt_id':identifier,'category':data['category'],'request':request,
                'result_present':result is not None,'result_status':None if result is None else result.get('status')})
        return performance.validate(plan=self.study.parent.plan,amendment=self.study.amendment,
            cell_id=self.intent['cell_id'],owner_slot=self.intent['researcher_id'],attempt_id=attempt_id,
            checkpoint_sha256=checkpoint_sha256,selection_tasks=self.views['selection'],paid_calls=calls,
            related_paid_attempt_ids=set(paid_attempt_ids),budget_performance_receipts=receipts)

    def _performance_billing_pending_allowed(self,state):
        completed={r['data']['attempt_id'] for r in self._events('paid_result')}
        return all(row['status'] in {'settled','cancelled'} or
            (row['status']=='dispatched' and identifier in completed) or
            (row['status']=='uncertain' and bool(_read_checked_budget_receipt(self,identifier)))
            for identifier,row in state.items())

    def freeze_performance_selection(self):
        # This runs the actual incumbent/no-regression promotion computation;
        # callers cannot choose checkpoint, lineage, scores, or freeze hashes.
        return self.freeze_selection()



class SharedBaseSession:
    def __new__(cls,study,cell_id,*,now=time.time):
        if type(study) is not FrozenStudy:raise ValueError('witnessed_shared_base_scope_required')
        module=_checked_shared_namespace(study)
        actual=type('CheckedSharedBaseV2',(module.SharedBaseSession,),{
            'authorize_verified_budget_stop':_shared_authorize_budget_stop,
            'reconcile_all':_shared_reconcile_all,
            'paid_references':_shared_paid_references,
            'dispatch_paid':_shared_dispatch,
            '_original_dispatch_paid':module.SharedBaseSession.dispatch_paid})
        instance=actual(study,cell_id)
        instance.policy_amendment_sha256=study.amendment_sha256
        instance.verified_budget_stops={}
        instance._pending_budget_stops={}
        return instance



class FinalGate:
    def __init__(self,study,*,matrix_manifest_path,prepared_matrix_dir,completion_index_path,
                 final_public_commit_sha1,policy_final_witness_bytes):
        if type(study) is not FrozenStudy:raise ValueError('witnessed_v2_study_required')
        envelope=json.loads(policy_final_witness_bytes)
        if set(envelope)!={'schema','amendment_sha256','policy_manifest_sha256','qualified_final_witness'} or envelope['schema']!='cua-full-study-policy-final-witness-v2' or envelope['amendment_sha256']!=study.amendment_sha256 or envelope['policy_manifest_sha256']!=study.manifest_sha256:
            raise ValueError('final_policy_witness_not_bound')
        # Rebuild actual 600 admissions, matched five-slot matrix, every one of
        # the 24 private campaign chains and immutable final witness. The only
        # removed tail is the old requirement that money already be settled.
        module=_checked_final_namespace()
        module.campaign=SimpleNamespace(**vars(campaign));module.campaign.FrozenStudy=FrozenStudy
        module.matrix=SimpleNamespace(**vars(matrix));module.matrix.build=lambda *args:effective_matrix_plan(matrix.build(*args),study)
        self.qualified=module.FinalGate(frozen=study,matrix_manifest_path=matrix_manifest_path,
            prepared_matrix_dir=prepared_matrix_dir,completion_index_path=completion_index_path,
            final_public_commit_sha1=final_public_commit_sha1,
            witness_fetcher=lambda _:policy.canonical(envelope['qualified_final_witness']))
        self.study=study;self.freezes=self.qualified.freezes;self.budget=study.budget
        self.frozen=study
        for name in ('plan','plan_sha256','manifest','work_root','matrix_manifest_path','prepared_matrix_dir',
                     'completion_index_path','completion_index_sha256','public_final_witness_sha256',
                     'last_selection_frozen_at','initial_state_by_task'):
            setattr(self,name,getattr(self.qualified,name))
        self.policy_final_witness_sha256=policy.sha(policy_final_witness_bytes)



def result_projection(outcomes):
    rows=list(outcomes)
    return {'schema':'cua-full-study-truthful-performance-and-usage-results-v2',
        'scored_performance_count':sum(v.get('performance_eligible') is True for v in rows),
        'model_completion_unknown_count':sum(v.get('inference',{}).get('status')=='completion_unknown_after_actor_deadline' for v in rows),
        'actual_total_usd':None if any(v.get('cost_usd') is None for v in rows) else
            str(sum(dollars.old._dollar(v['cost_usd'],'observed cost') for v in rows)),
        'provider_invoice_complete':all(v.get('invoice_complete') is True for v in rows),
        'dollar_policy':'no_programmatic_dollar_ceiling','campaign_hours_cap':16,
        'task_limits':{'max_actions':90,'actor_seconds':720,'lease_seconds':1200}}


def paper_budget_wording():
    return ('All five model slots use 16-hour campaigns with no programmatic dollar ceiling under the '
            'pre-result human authorization. Compute, task and 90-action/720-second/1200-second lease '
            'limits remain matched. Verified task performance is reported separately from uncertain '
            'inference completion and authentic usage; unknown costs are not estimated as zero.')


SOURCE_FILES=('src/cursibench/full_study_runtime_v2.py','src/cursibench/full_study_policy_amendment_v2.py',
    'src/cursibench/full_study_unlimited_budget_v2.py','src/cursibench/full_study_performance_coverage_v2.py',
    'native_desktop_factory/scored_budget_outcome_policy_v22.py','src/cursibench/full_study_final_performance_v2.py',
    'tools/full_study_campaign_dispatch_v2.py','src/cursibench/full_study_results_v2.py',
    'src/cursibench/full_study_native_counterparts_v22.py','src/cursibench/full_study_selection_environment_v2.py',
    'native_desktop_factory/policy_execution_v22.py')


def source_manifest(repo_root):
    root=Path(repo_root).resolve()
    from native_desktop_factory.model_transport_integration_v21 import proposal as desktop_proposal
    names=set(SOURCE_FILES)|set(desktop_proposal(root)['source_sha256s'])|{
        'src/cursibench/full_study_pre_campaign_v1.py','src/cursibench/full_study_matrix_v1.py',
        'src/cursibench/full_study_campaign_dispatch_v1.py','src/cursibench/full_study_shared_base_selection_v1.py',
        'src/cursibench/full_study_shared_base_execution_v1.py','src/cursibench/full_study_final_dispatch_v1.py',
        'src/cursibench/full_study_results_v1.py','tools/full_study_campaign_dispatch_v1.py'}
    for folder in ('enterprise_fallback/odoo18','gitlab_world','native_desktop_factory'):
        directory=root/folder
        if directory.is_dir():
            names.update(p.relative_to(root).as_posix() for p in directory.glob('*.py') if p.is_file() and not p.is_symlink())
    if (root/'tools/office_owned_folder_runtime_v2.py').is_file():
        from tools.office_owned_folder_runtime_v2 import SOURCE_FILES as office_sources
        names.update(office_sources)
    values={name:policy.sha((root/name).read_bytes()) for name in sorted(names)}
    return {'schema':'cua-full-study-policy-runtime-source-manifest-v2','source_sha256s':values,
        'legacy_final_gate_sha256':'70be662737d101e5a3f7d6712f359a3d47a758ea4537e56281d3717c717d9c76',
        'legacy_shared_base_sha256':'0e4a4e1fa8c93c38bb356c6eb248ac7e3afbe96204a5e97c494171b80d3911a1',
        'provider_dispatch_enabled':False,'official_model_results':0}


def prepare_policy_runtime(*,qualified_parent,amendment,output):
    root=Path(output).absolute()
    if root.exists() or root.is_symlink() or not root.parent.resolve().is_relative_to(qualified_parent.repo_root/'work'):raise ValueError('fresh_owned_v2_policy_namespace_required')
    sources=source_manifest(Path(__file__).resolve().parents[2])
    manifest=build_manifest(qualified_parent.plan,amendment,
        parent_protocol_sha256=qualified_parent.manifest_sha256,
        ratification_sha256=qualified_parent.ratification_sha256,
        source_manifest_sha256=policy.sha(policy.canonical(sources)))
    root.mkdir(parents=True,mode=0o700)
    for name,value in [('source-manifest.private.json',sources),('policy-amendment.private.json',amendment),
                       ('policy-manifest.private.json',manifest),('pre-result-witness.json',witness(manifest))]:
        campaign._private_write_new(root/name,policy.canonical(value))
    return {'status':'prepared_pre_result_uniform_runtime_v2','manifest_sha256':policy.sha(policy.canonical(manifest)),
            'amendment_sha256':manifest['amendment_sha256'],'provider_calls':0,'official_model_results':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['prepare','source-manifest'])
    parser.add_argument('--repo-root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    for name in ['parent-manifest','parent-prepared','ratification','parent-witness','amendment']:
        parser.add_argument('--'+name,type=Path)
    parser.add_argument('--parent-public-commit')
    args=parser.parse_args()
    if args.mode=='source-manifest':
        campaign._private_write_new(args.output,policy.canonical(source_manifest(args.repo_root)))
        value={'status':'source_manifest_only','provider_calls':0}
    else:
        parent=campaign.FrozenStudy(repo_root=args.repo_root,manifest_path=args.parent_manifest,
            prepared_dir=args.parent_prepared,ratification_path=args.ratification,
            public_commit_sha1=args.parent_public_commit,
            witness_fetcher=lambda _:args.parent_witness.read_bytes())
        value=prepare_policy_runtime(qualified_parent=parent,amendment=json.loads(args.amendment.read_bytes()),output=args.output)
    print(json.dumps(value,sort_keys=True))


# Source-checked function extraction preserves every real training gate.
import inspect
import textwrap
_sft_source=textwrap.dedent(inspect.getsource(campaign.CampaignSession.dispatch_tinker_sft))
_quote_check="""_require(Decimal(reserve) > 0 and Decimal(reserve) <=
             Decimal(self.intent['tinker_usd_cap']),"""
if _sft_source.count(_quote_check)!=1:raise ValueError('v2_training_quote_patch_source_changed')
_sft_source=_sft_source.replace(_quote_check,"_require(Decimal(reserve) > 0,")
_sft_globals=dict(campaign.CampaignSession.dispatch_tinker_sft.__globals__)
exec(compile(_sft_source,'checked-v2-training-gates','exec'),_sft_globals)
_dispatch_tinker_sft_uncapped=_sft_globals['dispatch_tinker_sft']


def _checked_final_namespace():
    path=Path(__file__).with_name('full_study_final_dispatch_v1.py');raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!='70be662737d101e5a3f7d6712f359a3d47a758ea4537e56281d3717c717d9c76':
        raise ValueError('immutable_final_gate_source_changed')
    source=raw.decode()
    begin="        budget_path = self.work_root / 'full-study-budget.jsonl'\n"
    end='\n\nclass TrustedFinalWorker(Protocol):'
    if source.count(begin)!=1 or source.count(end)!=1:raise ValueError('final_billing_tail_patch_not_exact')
    start=source.index(begin);finish=source.index(end,start)
    source=source[:start]+"        self.billing_status = 'separate_v2_unreconciled_allowed'\n"+source[finish:]
    source=source.replace('pre_plan_raw == frozen.plan_raw,','pre_plan_raw == frozen.parent.plan_raw,')
    module=ModuleType('cursibench._checked_final_performance_gate_v2')
    module.__package__='cursibench';module.__file__=str(path)
    exec(compile(source,'checked-final-performance-gate-v2','exec'),module.__dict__)
    return module


def _checked_shared_namespace(study):
    path=Path(__file__).with_name('full_study_shared_base_execution_v1.py');raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!='0e4a4e1fa8c93c38bb356c6eb248ac7e3afbe96204a5e97c494171b80d3911a1':
        raise ValueError('immutable_shared_base_source_changed')
    source=raw.decode()
    reserve_check='''        _require(committed + _money(reserve_usd) <= _money(
            self.cell["base_selection_cost_upper_bound_usd"]),
            "shared_base_selection_separate_reserve_exhausted")'''
    settle_check='''            _require(actual <= _money(item["reserve_usd"]),
                     "shared_base_paid_amount_over_reserved")'''
    for before in [reserve_check,settle_check]:
        if source.count(before)!=1:raise ValueError('shared_dollar_check_patch_not_exact')
        source=source.replace(before,'')
    module=ModuleType('cursibench._checked_shared_base_runtime_v2');module.__package__='cursibench';module.__file__=str(path)
    exec(compile(source,'checked-shared-base-runtime-v2','exec'),module.__dict__)
    module.shared=_checked_shared_verifier(study)
    module.environment=environment
    module.dollars=SimpleNamespace(ATTEMPT=dollars.old.ATTEMPT,
        StudyBudgetLedger=lambda *_:study.budget)
    return module




# This descriptor is evaluator-owned. It references existing private package
# and salt evidence; neither becomes model context or public policy evidence.
def verify_budget_artifacts(study,owner_slot,verification):
    if type(verification) is dict and set(verification)=={'adapter','arguments'}:
        return _portable_budget_verification(study,owner_slot,verification)
    from native_desktop_factory import scored_budget_outcome_policy_v22 as adapter
    fields={'batch','evaluator','package_ref','salt_ref','checkpoint_sha256'}
    if type(verification) is not dict or set(verification) not in (fields,fields|{'sampler_process'}):
        raise ValueError('evaluator_owned_budget_verification_descriptor_required')
    work=study.repo_root/'work'
    def reference(ref):
        if type(ref) is not dict or set(ref)!={'path','sha256'} or not evidence.is_hash(ref['sha256']):
            raise ValueError('private_verification_reference_required')
        path=Path(ref['path']).absolute();value,raw=private(path,work)
        if policy.sha(raw)!=ref['sha256']:raise ValueError('private_verification_bytes_changed')
        return value
    package=reference(verification['package_ref']);salt=reference(verification['salt_ref'])
    source_ref=package.pop('source_ref')
    source=Path(source_ref['path']).absolute()
    if source.is_symlink() or source.resolve()!=source or not source.is_relative_to(work.resolve()) or source.stat().st_mode&0o077 or policy.sha(source.read_bytes())!=source_ref['sha256']:
        raise ValueError('trusted_source_package_bytes_changed')
    package['source']=source.read_bytes()
    return adapter.verify(plan=study.parent.plan,amendment=study.amendment,owner_slot=owner_slot,
        batch=verification['batch'],evaluator=verification['evaluator'],package=package,
        private_salt=salt['variant_salt'],checkpoint_sha256=verification['checkpoint_sha256'],policy_manifest_sha256=study.plan_sha256,sampler_process=verification.get('sampler_process'))


def _read_checked_budget_receipt(session,identifier):
    events=[r for r in session._events('budget_performance_closed_v2') if r['data']['attempt_id']==identifier]
    if len(events)!=1:raise ValueError('uncertain_request_has_no_verified_budget_stop')
    event=events[0]['data'];path=session.directory/(identifier+'.budget-performance-v2.private.json')
    value,raw=private(path,session.directory)
    if policy.sha(raw)!=event['receipt_sha256'] or value!=verify_budget_artifacts(session.study,session.intent['researcher_id'],event['verification']):
        raise ValueError('checked_budget_performance_evidence_changed')
    return value


def _method(function,replacements=(),globals_extra=None):
    source=inspect.getsource(function)
    for item in replacements:
        before,after=item[:2];expected=item[2] if len(item)==3 else 1
        if source.count(before)!=expected:raise ValueError('immutable_method_patch_not_exact')
        source=source.replace(before,after)
    namespace=dict(function.__globals__);namespace.update(globals_extra or {})
    exec(compile(textwrap.dedent(source),'source-checked-policy-v2-'+function.__name__,'exec'),namespace)
    return namespace[function.__name__]


# Retain actual score validation, promotion, training lineage, round counters,
# completed selections and checkpoint lookup; remove only money completeness.
CampaignSession.record_selection_scored=_method(campaign.CampaignSession.record_selection_scored,[(
    "self._events('paid_result')} and",
    "self._events('paid_result')} | {row['data']['attempt_id'] for row in self._events('budget_performance_closed_v2')} and"),
    ("        current_checkpoint, incumbent = self._incumbent()",
     "        self._verify_budget_result_rows(result,paid_attempt_ids)\n        current_checkpoint, incumbent = self._incumbent()")],globals_extra={'selection_environment':environment})
CampaignSession.freeze_selection=_method(campaign.CampaignSession.freeze_selection,[(
    "all(row['status'] in {'settled', 'cancelled'} for row in\n                     state.values())",
    "self._performance_billing_pending_allowed(state)")])


def shared_receipt_path(study,cell_id):
    if cell_id not in matrix.CELLS:raise ValueError('undeclared_shared_base_cell')
    return study.repo_root/'work/shared-base-selection-v2'/cell_id/'receipt.private.json'


def verify_shared_receipt(study,budget,cell_id,source,*,require_registry=True):
    value,_=private(source,study.repo_root/'work')
    if cell_id=='desktop-native' and value.get('schema')=='cua-native-desktop-v22-shared-base-performance':
        from native_desktop_factory.policy_execution_v22 import verify_shared_receipt as native_verify
        return native_verify(study,budget,cell_id,source,require_registry=require_registry)
    return _checked_shared_verifier(study).verify_receipt(study,budget,cell_id,source,require_registry=require_registry)


_shared_proxy=SimpleNamespace(**vars(shared))
_shared_proxy.receipt_path=shared_receipt_path;_shared_proxy.verify_receipt=verify_shared_receipt
CampaignSession.record_base_selection=_method(campaign.CampaignSession.record_base_selection,globals_extra={'shared_base':_shared_proxy})
CampaignSession._checked_base_selection=_method(campaign.CampaignSession._checked_base_selection,globals_extra={'shared_base':_shared_proxy})


def _shared_authorize_budget_stop(self,attempt_id,*,verification):
    receipt=verify_budget_artifacts(self.study,'shared-base',verification)
    record=self.budget.owner_attempts(self.owner).get(attempt_id)
    if record is None or record['status']!='uncertain' or receipt['sample_paid_attempt_id']!=attempt_id:
        raise ValueError('shared_owned_uncertain_budget_request_required')
    path=self.directory/'paid'/(attempt_id+'.budget-performance.private.json')
    campaign._private_write_new(path,policy.canonical({'receipt':receipt,'verification':verification}))
    self.verified_budget_stops[attempt_id]={'path':'paid/'+path.name,'sha256':policy.sha(path.read_bytes())}
    self._pending_budget_stops.pop(attempt_id,None)
    return receipt


def _shared_paid_references(self):
    attempts=self.budget.owner_attempts(self.owner);refs=[]
    for identifier,row in attempts.items():
        if row['category']=='shared_base_final':continue
        prefix=self.directory/'paid'/identifier
        request=Path(str(prefix)+'.request.private.json')
        _,raw=private(request,self.directory)
        if policy.sha(raw)!=row['request_sha256']:raise ValueError('shared_exact_request_changed')
        def ref(path):return {'path':path.relative_to(self.directory).as_posix(),'sha256':policy.sha(path.read_bytes())}
        result=Path(str(prefix)+'.result.private.json');usage=Path(str(prefix)+'.usage.private.json')
        stop=Path(str(prefix)+'.budget-performance.private.json')
        if not result.exists() and not stop.exists():raise ValueError('earlier_provider_fault_is_not_performance')
        refs.append({'attempt_id':identifier,'category':row['category'],'request_ref':ref(request),
            'result_ref':ref(result) if result.exists() else None,'usage_ref':ref(usage) if usage.exists() else None,
            'budget_performance_ref':ref(stop) if stop.exists() else None})
    return refs


def _shared_reconcile_all(self,usage_reconciler):
    # None is an explicit unknown usage response. No settlement event, zero
    # charge or fabricated invoice is created. Known authentic amounts still
    # pass the original invoice/source checks, including above old estimates.
    if not callable(usage_reconciler):raise ValueError('trusted_usage_reconciler_required')
    for identifier,item in self.completed_paid.items():
        source=usage_reconciler(dict(item))
        if source is None:continue
        if type(source) is not dict or set(source)!={'actual_usd','invoice_basis','provider_invoice_usd','source_bytes'} or type(source['source_bytes']) is not bytes or not source['source_bytes']:
            raise ValueError('authentic_usage_source_required')
        dollars.old._dollar(source['actual_usd'],'authentic usage')
        basis='self_hosted_nominal_meter' if item['category']=='storage_application' else 'provider_invoice'
        if source['invoice_basis']!=basis or source['provider_invoice_usd']!=(None if basis=='self_hosted_nominal_meter' else source['actual_usd']):
            raise ValueError('authentic_invoice_basis_changed')
        source_path=self.directory/'paid'/(identifier+'.source.private.json')
        usage_path=self.directory/'paid'/(identifier+'.usage.private.json')
        usage={'schema':shared.USAGE_SCHEMA,'attempt_id':identifier,'category':item['category'],
            'actual_usd':source['actual_usd'],'invoice_basis':basis,'provider_invoice_usd':source['provider_invoice_usd'],
            'source_ref':{'path':'paid/'+source_path.name,'sha256':policy.sha(source['source_bytes'])}}
        for path,raw in [(source_path,source['source_bytes']),(usage_path,policy.canonical(usage))]:
            if path.exists():
                if path.is_symlink() or path.read_bytes()!=raw or path.stat().st_mode&0o077:raise ValueError('authentic_usage_source_changed')
            else:campaign._private_write_new(path,raw)
        self.budget.settle(identifier,source['actual_usd'],policy.sha(usage_path.read_bytes()))
    return _shared_paid_references(self)


def _verify_shared_paid_v2(study,budget,cell_id,root,receipt,selection,task_by_id):
    records={k:v for k,v in budget.owner_attempts(cell_id+':shared-base').items() if v['category']!='shared_base_final'}
    if set(records)!=set(receipt['paid_attempt_ids']) or len(records)!=len(receipt['paid_attempt_refs']):raise ValueError('shared_all_paid_intents_required')
    calls=[];stops=[];seen=set()
    module=shared
    for ref in receipt['paid_attempt_refs']:
        if set(ref)!={'attempt_id','category','request_ref','result_ref','usage_ref','budget_performance_ref'}:raise ValueError('shared_paid_reference_shape_changed')
        identifier=ref['attempt_id']
        if identifier in seen or identifier not in records:raise ValueError('shared_paid_duplicate')
        seen.add(identifier);row=records[identifier]
        request,raw=module._json_ref(root,ref['request_ref'])
        if row['category']!=ref['category'] or row['work_sha256']!=policy.sha(raw) or row['request_sha256']!=policy.sha(raw) or request.get('category')!=ref['category'] or request.get('split')!='selection' or request.get('base_model')!=matrix.STUDENT:
            raise ValueError('shared_paid_request_or_model_unbound')
        worker_request,_=module._json_ref(root,request['worker_request_ref'])
        task=request.get('task_id');item=task_by_id.get(task)
        if task is not None:
            if item is None or worker_request.get('task_id')!=task or worker_request.get('package_sha256')!=request.get('package_sha256'):
                raise ValueError('shared_worker_task_changed')
            if ref['category']=='tinker' and worker_request.get('frame_sha256') not in item['frame_shas']:raise ValueError('shared_sample_frame_changed')
        result=None
        if ref['result_ref'] is not None:
            result,_=module._json_ref(root,ref['result_ref']);worker_result,_=module._json_ref(root,result['worker_result_ref'])
            if result.get('attempt_id')!=identifier or result.get('category')!=ref['category'] or worker_result.get('status')!=result.get('status'):
                raise ValueError('shared_retained_result_changed')
            if task is not None and ref['category']=='tinker' and result.get('status')!='completed':raise ValueError('earlier_provider_fault_is_infrastructure_invalid')
        else:
            if row['status']!='uncertain' or ref['budget_performance_ref'] is None:raise ValueError('unproved_shared_uncertain_request')
            stop,_=module._json_ref(root,ref['budget_performance_ref'])
            verified=verify_budget_artifacts(study,'shared-base',stop['verification'])
            if stop['receipt']!=verified or verified['sample_paid_attempt_id']!=identifier or (root/'paid'/(identifier+'.result.private.json')).exists():
                raise ValueError('shared_budget_stop_changed_or_result_invented')
            stops.append(verified)
        if ref['usage_ref'] is None:
            if row['status'] not in {'dispatched','uncertain'} or row['actual_usd'] is not None:raise ValueError('unknown_usage_cannot_be_settled')
        else:
            usage,usage_raw=module._json_ref(root,ref['usage_ref'])
            basis='self_hosted_nominal_meter' if ref['category']=='storage_application' else 'provider_invoice'
            if row['status']!='settled' or row['evidence_sha256']!=policy.sha(usage_raw) or usage.get('actual_usd')!=row['actual_usd'] or usage.get('invoice_basis')!=basis or usage.get('provider_invoice_usd')!=(None if basis=='self_hosted_nominal_meter' else row['actual_usd']):
                raise ValueError('authentic_usage_invoice_unbound')
            module._reference(root,usage['source_ref'])
        calls.append({'attempt_id':identifier,'category':ref['category'],'request':request,
            'result_present':result is not None,'result_status':None if result is None else result.get('status')})
    value=performance.validate(plan=study.parent.plan,amendment=study.amendment,cell_id=cell_id,owner_slot='shared-base',
        attempt_id=receipt['selection_attempt'],checkpoint_sha256=receipt['base_checkpoint_sha256'],selection_tasks=selection,
        paid_calls=calls,related_paid_attempt_ids=set(records),budget_performance_receipts=stops)
    if value['coverage_sha256']!=receipt['paid_coverage_sha256']:raise ValueError('shared_performance_coverage_changed')
    return value


def _checked_shared_verifier(study):
    path=Path(shared.__file__);raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!='621631e9bf3393a1a8cc2576c493189bc9448cd646ebd926ebf324a0d78cf460':raise ValueError('immutable_shared_verifier_source_changed')
    source=raw.decode();start=source.index('    records = budget.owner_attempts(');end=source.index('    if require_registry:',start)
    source=source[:start]+'''    coverage = _verify_shared_paid_v2(study,budget,cell_id,root,receipt,selection,task_by_id)
'''+source[end:]
    source=source.replace('getattr(budget, "plan_sha256", None) == study.plan_sha256','getattr(budget, "plan_sha256", None) == study.parent.plan_sha256')
    module=ModuleType('cursibench._checked_shared_performance_verifier_v2');module.__package__='cursibench';module.__file__=str(path)
    module._verify_shared_paid_v2=_verify_shared_paid_v2
    exec(compile(source,'checked-shared-performance-verifier-v2','exec'),module.__dict__)
    module.environment=environment
    module.RECEIPT_SCHEMA='cua-full-study-shared-base-performance-receipt-v2'
    module.receipt_path=shared_receipt_path
    return module


@contextmanager
def runtime_context(study):
    """Explicit single-thread cell bridge; never makes a provider call itself."""
    if type(study) is not FrozenStudy:raise ValueError('witnessed_policy_runtime_required')
    with patch.object(shared,'verify_receipt',verify_shared_receipt),patch.object(shared,'receipt_path',shared_receipt_path),patch.object(campaign,'FrozenStudy',FrozenStudy),patch.object(campaign,'CampaignSession',CampaignSession):
        yield





def effective_matrix_plan(parent_plan,study):
    import copy
    result=copy.deepcopy(parent_plan)
    result.update(schema='cua-full-study-matrix-with-witnessed-policy-v2',
        parent_matrix_plan_sha256=policy.sha(evidence.json_bytes(parent_plan)),
        policy_manifest_sha256=study.manifest_sha256,amendment_sha256=study.amendment_sha256,
        effective_dollar_ceiling_usd=None,actor_clock_excludes_native_lifecycle=True)
    for cell in result['cells']:
        for slot in [cell['base'],*cell['researcher_plans'].values()]:
            slot['execution']={**slot['execution'],'max_actions_per_task':90,'max_wall_seconds_per_task':720}
    return result


def prepare_matrix(study,manifest_path,output):
    value,raw=private(Path(manifest_path),study.repo_root/'work')
    result=effective_matrix_plan(matrix.build(value,Path(manifest_path).parent,policy.sha(raw)),study)
    output=Path(output).absolute()
    if output.exists() or output.is_symlink():raise ValueError('fresh_v2_matrix_directory_required')
    output.mkdir(mode=0o700,parents=True)
    campaign._private_write_new(output/'matrix-plan.json',evidence.json_bytes(result))
    intent={'schema':matrix.INTENT_SCHEMA,'study_id':result['study_id'],
        'matrix_manifest_sha256':result['matrix_manifest_sha256'],'plan_sha256':policy.sha(evidence.json_bytes(result)),
        'cell_ids':list(matrix.CELLS),'campaign_count':24,'provider_dispatch_enabled':False,'scores_present':False}
    campaign._private_write_new(output/'intent.json',policy.canonical(intent))
    return result





def _allow_owned_reset(session,category,request):
    pending=list(session._pending_budget_stops.values())
    if len(pending)!=1 or category!='e2b' or type(request) is not dict or request.get('phase')!='reset' or request.get('lease_seconds')!=1200:
        return False
    item=pending[0]
    proof=item['proof']
    if item.get('reset_consumed') or request.get('task_id')!=item['request'].get('task_id') or request.get('package_sha256')!=item['request'].get('package_sha256') or proof.get('actor_deadline_reached') is not True or proof.get('late_gui_application_authorized') is not False:
        return False
    item['reset_consumed']=True
    return True


def _capture_deadline(session,identifier,request,exc):
    if type(exc) is not ActorDeadlineReached or not exc.proof.actor_deadline_reached:raise ValueError('typed_actual_deadline_required')
    session._pending_budget_stops[identifier]={'request':request,'proof':exc.proof.receipt(),'reset_consumed':False}


CampaignSession._allow_owned_deadline_reset=lambda self,category,request:_allow_owned_reset(self,category,request)
CampaignSession._dispatch_paid_locked=_method(campaign.CampaignSession._dispatch_paid_locked,[
    ("not self._unresolved_failure() and", "(self._allow_owned_deadline_reset(category,request) or not self._unresolved_failure()) and"),
    ("            raise DispatchError('paid_response_uncertain_reconcile_before_retry') from None",
     "            if type(exc) is ActorDeadlineReached:\n                _capture_deadline(self,attempt_id,request,exc)\n                raise\n            raise DispatchError('paid_response_uncertain_reconcile_before_retry') from None")],
    globals_extra={'ActorDeadlineReached':ActorDeadlineReached,'_capture_deadline':_capture_deadline})


def _shared_dispatch(self,**kwargs):
    records=self.budget.owner_attempts(self.owner)
    uncertain=[identifier for identifier,row in records.items() if row['status']=='uncertain']
    verified=set()
    for identifier in uncertain:
        path=self.directory/'paid'/(identifier+'.budget-performance.private.json')
        if path.exists():
            stop,_=private(path,self.directory)
            if stop['receipt']!=verify_budget_artifacts(self.study,'shared-base',stop['verification']):raise ValueError('shared_checked_budget_stop_changed')
            verified.add(identifier)
    if set(uncertain)-verified and not _allow_owned_reset(self,kwargs['category'],kwargs['request']):
        raise ValueError('earlier_or_unproved_provider_fault_blocks_new_work')
    # Preserve only the typed deadline raised by the actual v21 model path.
    # The original dispatcher still writes the uncertain ledger before this
    # wrapper re-raises the same object; it never re-invokes the provider.
    captured=[];provider=kwargs['provider']
    def actual(request):
        try:return provider(request)
        except ActorDeadlineReached as exc:
            captured.append(exc);raise
    kwargs['provider']=actual
    try:return self._original_dispatch_paid(**kwargs)
    except Exception:
        if captured:
            _capture_deadline(self,kwargs['attempt_id'],kwargs['request'],captured[0]);raise captured[0]
        raise





def _verify_budget_result_rows(self,result,paid_attempt_ids):
    completed={r['data']['attempt_id'] for r in self._events('paid_result')}
    rows={r['task_id']:r for r in result['tasks']}
    for identifier in set(paid_attempt_ids)-completed:
        receipt=_read_checked_budget_receipt(self,identifier);row=rows.get(receipt['task_id'])
        if row is None or row['score']!=receipt['performance']['score'] or any(row[field]!=receipt['evidence_sha256'][name] for field,name in [
            ('saved_state_sha256','saved-state.private.json'),('verifier_receipt_sha256','verifier.private.json'),('reset_receipt_sha256','reset.private.json')]):
            raise ValueError('selection_score_or_saved_reset_not_bound_to_budget_receipt')
CampaignSession._verify_budget_result_rows=_verify_budget_result_rows





def load_policy_study(*,repo_root,parent_manifest,parent_prepared,ratification,parent_public_commit,parent_witness,policy_dir,policy_public_commit,policy_witness_fetcher=None):
    parent=campaign.FrozenStudy(repo_root=repo_root,manifest_path=parent_manifest,prepared_dir=parent_prepared,
        ratification_path=ratification,public_commit_sha1=parent_public_commit,
        witness_fetcher=lambda _:Path(parent_witness).read_bytes())
    folder=Path(policy_dir);amendment,_=private(folder/'policy-amendment.private.json',parent.repo_root/'work')
    manifest,_=private(folder/'policy-manifest.private.json',parent.repo_root/'work')
    sources,raw=private(folder/'source-manifest.private.json',parent.repo_root/'work')
    if sources!=source_manifest(Path(__file__).resolve().parents[2]) or manifest['source_manifest_sha256']!=policy.sha(raw):
        raise ValueError('v22_source_manifest_or_frozen_policy_changed')
    _,witness_raw=private(folder/'pre-result-witness.json',parent.repo_root/'work')
    if campaign.HEX40.fullmatch(policy_public_commit) is None:raise ValueError('immutable_public_policy_commit_required')
    url='https://raw.githubusercontent.com/EnvLoop/cua-rsibench/'+policy_public_commit+'/docs/evidence/full-study-pre-result-policy-witness-v2.json'
    if campaign._fetch_immutable_witness(url,policy_witness_fetcher)!=witness_raw:raise ValueError('new_public_policy_witness_bytes_changed')
    return FrozenStudy(qualified_parent=parent,amendment=amendment,manifest=manifest,witness_bytes=witness_raw)





def _portable_budget_verification(study,owner_slot,descriptor):
    import importlib
    import re
    registered=descriptor['adapter']
    if type(registered) is not dict or set(registered)!={'module','function','source_sha256'} or registered['function']!='verify_budget_performance' or not re.fullmatch(r'enterprise_fallback\.odoo18\.native_surface_budget_performance_v[1-9][0-9]*',registered['module']):
        raise ValueError('registered_readonly_budget_counterpart_required')
    name=registered['module'].replace('.','/')+'.py'
    sources=source_manifest(Path(__file__).resolve().parents[2])['source_sha256s']
    if sources.get(name)!=registered['source_sha256']:raise ValueError('budget_counterpart_not_in_frozen_source_closure')
    module=importlib.import_module(registered['module'])
    if Path(module.__file__).resolve()!=Path(__file__).resolve().parents[2]/name:raise ValueError('budget_counterpart_import_identity_changed')
    value=module.verify_budget_performance(study=study,owner_slot=owner_slot,verification=descriptor['arguments'])
    if value.get('schema')!='cua-verified-budget-performance-with-unknown-billing-v22' or value.get('amendment_sha256')!=study.amendment_sha256 or value.get('owner_slot')!=owner_slot or value.get('performance_coverage_eligible') is not True or value.get('provider_close_acknowledged') is not True or value.get('formal_registration_performed') is not False or value['performance'].get('status')!='independently_saved_scored_and_reset' or type(value['performance'].get('score')) is not int or value['performance']['score'] not in (0,1) or value['inference'].get('status') not in {'completion_unknown_after_actor_deadline','late_completed_withheld_from_gui','not_submitted_before_actor_deadline'} or value['inference'].get('unknown_response_is_completed') is not False or value['inference'].get('request_replayed') is not False or value['billing'].get('actual_usd') is not None or set(value.get('evidence_sha256',{}))!={'saved-state.private.json','verifier.private.json','reset.private.json','actor-clock.private.json','actor-budget-stop.private.json','task.private.json'} or not all(evidence.is_hash(v) for v in value['evidence_sha256'].values()):
        raise ValueError('native_budget_counterpart_proof_contract_changed')
    return value


if __name__=='__main__':main()
