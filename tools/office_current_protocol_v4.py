"""Explicit Office source epoch around real v22 study/session/final authorities.

No legacy file is rewritten. This context must wrap both pre-result policy
preparation/loading and execution, so the immutable witness binds this closure.
"""
from contextlib import contextmanager,ExitStack
from pathlib import Path
from unittest.mock import patch
from tools import office_owned_folder_runtime_v2 as office
from cursibench import full_study_runtime_v2 as runtime
from native_desktop_factory import qwen_sampler_process_v21 as rpc

_BASE_MANIFEST=runtime.source_manifest
_BASE_BUDGET=runtime.verify_budget_artifacts
_BASE_SHARED=runtime.verify_shared_receipt
_BASE_AUTHORIZE=runtime.CampaignSession.authorize_verified_budget_stop


def source_manifest(repo_root):
 from tools.office_current_authority_v4 import current_sources
 value=_BASE_MANIFEST(repo_root);value['source_sha256s'].update(current_sources(repo_root))
 value['office_current_source_epoch']='original-office-current-v4'
 value['office_native_qualification_claimed']=False
 return value


def require_epoch(study):
 office.require(type(study) is runtime.FrozenStudy,'Actual witnessed v22 study required')
 expected=runtime.policy.sha(runtime.policy.canonical(source_manifest(Path(runtime.__file__).resolve().parents[2])))
 office.require(study.policy_manifest['source_manifest_sha256']==expected,'Fresh pre-result Office current source epoch/witness required')


def verify_budget(study,owner_slot,verification):
 registered=verification.get('adapter',{}) if isinstance(verification,dict) else {}
 if registered.get('module')!='tools.office_current_budget_performance_v4':return _BASE_BUDGET(study,owner_slot,verification)
 require_epoch(study);name='tools/office_current_budget_performance_v4.py'
 expected=source_manifest(study.repo_root)['source_sha256s'][name]
 office.require(set(verification)=={'adapter','arguments'} and set(registered)=={'module','function','source_sha256'} and registered['function']=='verify_budget_performance' and registered['source_sha256']==expected,'Registered read-only Office counterpart/source required')
 from tools import office_current_budget_performance_v4 as reader
 office.require(Path(reader.__file__).resolve()==Path(runtime.__file__).resolve().parents[2]/name,'Office budget reader import identity changed')
 return reader.verify_budget_performance(study=study,owner_slot=owner_slot,verification=verification['arguments'])


def verify_shared(study,budget,cell_id,source,*,require_registry=True):
 value,_=runtime.private(source,study.repo_root/'work')
 if cell_id not in office.CELLS or value.get('schema')!='office-current-shared-base-performance-v4':return _BASE_SHARED(study,budget,cell_id,source,require_registry=require_registry)
 from tools.office_current_workers_v4 import verify_shared_receipt
 return verify_shared_receipt(study,budget,cell_id,source,require_registry=require_registry)


def authorize_budget(session,attempt_id,*,verification):
 record=session.budget.owner_attempts(session.owner).get(attempt_id)
 if not record or record['category']!='teacher_rollout':return _BASE_AUTHORIZE(session,attempt_id,verification=verification)
 # Teacher callback was already charged. Only actual saved/reset/close evidence
 # may clear its proven terminal deadline for NEW work; no data is admitted.
 session._check_time();session._audit_paid_files();receipt=verify_budget(session.study,session.intent['researcher_id'],verification)
 office.require(record['status']=='uncertain' and receipt['sample_paid_attempt_id']==attempt_id and not session._events('selection_frozen') and not any(r['data']['attempt_id']==attempt_id for r in session._events('budget_performance_closed_v2')),'Actual one-use uncertain teacher deadline required')
 path=session.directory/(attempt_id+'.budget-performance-v2.private.json');office.write_new(path,office.canonical(receipt))
 session.journal.append('budget_performance_closed_v2',{'attempt_id':attempt_id,'verification':verification,'receipt_sha256':office.sha(office.private(path)),'billing_settled':False,'epoch_seconds':int(session.now())})
 session._pending_budget_stops.pop(attempt_id,None)


@contextmanager
def epoch_context(study=None):
 with ExitStack() as stack:
  stack.enter_context(patch.object(runtime,'source_manifest',source_manifest))
  if study is not None:require_epoch(study);stack.enter_context(runtime.runtime_context(study))
  stack.enter_context(patch.object(runtime,'verify_budget_artifacts',verify_budget));stack.enter_context(patch.object(runtime,'verify_shared_receipt',verify_shared))
  stack.enter_context(patch.object(runtime._shared_proxy,'verify_receipt',verify_shared));stack.enter_context(patch.object(runtime.shared,'verify_receipt',verify_shared));stack.enter_context(patch.object(runtime.shared,'receipt_path',runtime.shared_receipt_path))
  stack.enter_context(patch.object(runtime.CampaignSession,'authorize_verified_budget_stop',authorize_budget))
  from cursibench import full_study_qwen_runtime_gate_v1 as gate
  stack.enter_context(patch.object(gate,'pre_dispatch',rpc.delegated_pre_dispatch))
  yield
