"""Separate original selection20 provenance join; exact V3 physical workflow."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import time
import traceback
from . import v066_selection_reference_controls_v3 as original

REPO = Path(__file__).resolve().parents[1]
PRIOR = REPO/'work/gitlab-original-selection20-reference-v3-root-20261003.private'
DIAGNOSTIC = REPO/'work/gitlab-kas-single-cold-start-diagnostic-root-20261003.private'
STAGE = REPO/'work/gitlab-original-selection20-continuation-v1-root-20261004.private'
SCHEMA = 'gitlab-original-selection20-reference-continuation-authority-v1'
RESULT_SCHEMA = 'gitlab-original-selection20-reference-continuation-result-v1'
ROOT_APPROVAL_NAME = 'root-continuation-review-approved.private.json'
NATIVE_BINDING = '07c1520799c160d4394f9f943601a83f18da825f0ce87b2faa776c66878608be'
V3_BINDING = 'de62971cf123f92789c147cff1a973bd6c26e6d3e0a8866ca39a5f4cc906a883'
OLD_REVIEW_SHA = '1229eb743f35762f10bab85e9ace10bdeb8e0313f67f30a08f6dcfa2aec8e96d'
OLD_TERMINAL_SHA = '09f733f5cf0547012c7c325fbbd69b25bbe5aeac7d5afe28c78551e6d55a46ff'
OLD_TRIO_AUDIT_SHA = 'ee5f363918327bf01ac00499ec54297b8b94992fe4318b1c4463539e5d11648f'
DIAGNOSTIC_AUDIT_SHA = '925dafd51c7cb8912d74525b50f493123df743ec0b8cf1af2756d23fbd99a727'
HOST_SECONDS, CLEANUP_GRACE_SECONDS, CASE_RESERVE_SECONDS = 86400, 1500, 1260
FILES = ('gitlab_world/v066_selection_reference_continuation_v1.py',
         'tools/supervise_gitlab_selection_reference_continuation_v1.py',
         'tests/test_gitlab_selection_reference_continuation_v1.py',
         'tests/test_gitlab_selection_reference_continuation_supervisor_v1.py')
world, models, require, private, ref = original.world, original.models, original.require, original.private, original.ref
MODES, workflow = original.MODES, original.workflow


class HostDeadline(BaseException):
    """Host cancellation unwinds the unchanged BaseException-safe V15 cleanup."""


def source_binding():
    value = {'schema':'gitlab-selection20-continuation-source-v1',
        'source_sha256s':{name:sha256((REPO/name).read_bytes()).hexdigest() for name in FILES},
        'original_controller_binding':original.source_binding(),
        'native_binding_sha256':models.public_binding()['binding_sha256'],
        'workflow_uri_csv_guard_oracle_reset_budgets_unchanged':True,
        'reference_only':True, 'model_or_final_authority':False}
    return value|{'binding_sha256':models.common.digest(models.common.canonical(value))}


def _original_authority():
    value = original._check_authority(PRIOR/'root-selection-only-review-approved.private.json', OLD_REVIEW_SHA)
    require(value['controller_binding']['binding_sha256']==V3_BINDING and
            value['controller_binding']==original.source_binding() and
            models.public_binding()['binding_sha256']==NATIVE_BINDING,
            'continuation_original_v3_native146_changed')
    require(private(PRIOR/'controls.private/intent.private.json')==value,
            'continuation_original_consumed_intent_changed')
    return value


def audit_trio(directory, ordinal, identity, binding, plan_path):
    """No aggregate/failure receipt can substitute for three actual saved cases."""
    row = private(directory/'trio.private.json')
    require(row['ordinal']==ordinal and row['identity']==identity and
        [entry['mode'] for entry in row['modes']]==[mode for mode,_ in MODES],
        'continuation_original_order_identity_or_whole_trio_changed')
    audits=[]
    for entry,(mode,score) in zip(row['modes'],MODES):
        folder=directory/mode
        require(entry['expected']==score and entry['result_ref']==ref(folder/'result.private.json'),
                'continuation_case_provenance_ref_changed')
        actual=original._audit_case(folder,identity,binding,plan_path)
        require(actual==private(folder/'result.private.json') and actual['score']==score and
                actual['reset_exact'] is True and actual['model_calls']==0,
                'continuation_actual_original_saved_case_changed')
        audits.append({'mode':mode,'expected':score,'audit':actual})
    return {'ordinal':ordinal,'identity':identity,'trio_ref':ref(directory/'trio.private.json'),'audited_cases':audits}


def artifact_namespace_ref(root):
    """Bind all original transitive evidence without copying it into fresh output."""
    root=Path(root);require(root.resolve()==root and root.is_dir() and not root.is_symlink() and
        not root.stat().st_mode&0o077,'continuation_original_private_namespace_required')
    entries=[]
    for path in sorted(root.rglob('*')):
        info=path.lstat();require(not stat.S_ISLNK(info.st_mode),'continuation_original_evidence_symlink_refused')
        row={'path':str(path.relative_to(root)),'mode':stat.S_IMODE(info.st_mode),'uid':info.st_uid,'gid':info.st_gid}
        if stat.S_ISDIR(info.st_mode):row['kind']='directory'
        else:
            require(stat.S_ISREG(info.st_mode),'continuation_original_evidence_special_file_refused')
            raw=path.read_bytes();row.update(kind='file',bytes=len(raw),sha256=sha256(raw).hexdigest())
        entries.append(row)
    return {'root':str(root),'manifest_sha256':models.common.digest(models.common.canonical(entries)),
        'file_count':sum(row['kind']=='file' for row in entries),'copied_or_relabeled_as_fresh':False}


def _restored_single(native):
    before=private(native/'original-before.private.json');after=private(native/'original-resumed.private.json')
    require(after['same_identity'] is True and after['healthy'] is True and after['exact_business_snapshot'] is True and
        before['identity']==after['identity'] and before['snapshot']==after['snapshot'] and
        len(before['full_git_trees'])==len(after['full_git_trees'])==33 and
        world.cold.tree_digests(before['full_git_trees'])==world.cold.tree_digests(after['full_git_trees']),
        'continuation_startup_original_restoration_changed')
    for trees in (before['full_git_trees'],after['full_git_trees']):
        for refs in trees.values():
            for row in refs.values():
                p=native/row['raw_ref']['path'];raw=p.read_bytes()
                require(p.parent==native and p.is_file() and not p.is_symlink() and raw.endswith(b'\0') and
                    sha256(raw).hexdigest()==row['tree_sha256']==row['raw_ref']['sha256'],
                    'continuation_startup_raw_git_ref_changed')
    for group in ('protected','seed'):
        require(world.cold.source.private(native/(group+'-before.private.json'))==
                world.cold.source.private(native/(group+'-exit.private.json')),
                'continuation_startup_protected_seed_changed')
    require(private(native/'parent-teardown.private.json')['owned_parent_absent'] and
        all(private(native/'cycle-0-teardown.private.json')[key] for key in
            ('owned_container_absent','owned_overlay_mounts_absent','owned_vm_subtree_absent')) and
        not any(native.glob('cycle-1-*')), 'continuation_startup_owned_cleanup_or_retry_changed')
    life=private(native/'owned-lifecycle-end.private.json')
    require(life['within_limit'] and life['seconds_limit']==1200, 'continuation_startup_lifecycle_changed')
    return life['elapsed_seconds']


def _saved_evidence(old):
    failure=private(PRIOR/'controls.private/failure.private.json')
    terminal=private(PRIOR/'independent-terminal-partial-boot-audit.private.json',OLD_TERMINAL_SHA)
    require(failure=={'status':'terminal_preserved_no_retry','error_type':'ValueError',
        'completed_count':1,'model_calls':0,'formal_admissions':0} and terminal['process_absent'] and
        terminal['completed_original_whole_tasks']==1 and terminal['failed_original_ordinal']==1 and
        terminal['failed_mode']=='baseline' and terminal['failed_baseline_native_actor_receipts']==0 and
        terminal['original_identity_sql_full33git_seed_protected_exact_restored'] and
        terminal['model_tinker_calls']==terminal['formal_admissions']==0,
        'continuation_exact_partial_startup_failure_required')
    for evidence in terminal['native_evidence_refs'].values():
        require(ref(evidence['path'])==evidence,'continuation_failed_startup_raw_evidence_changed')
    first=private(PRIOR/'independent-case000-trio-audit.private.json',OLD_TRIO_AUDIT_SHA)
    binding=models.validate_binding(private(old['native_binding_ref']['path'],old['native_binding_ref']['sha256']))
    retained=audit_trio(PRIOR/'controls.private/task-000',0,old['ordered_selection20'][0],binding,Path(old['plan_ref']['path']))
    require(first['original_ordinal']==0 and first['scores']==[score for _,score in MODES] and
        first['controller_binding']==original.source_binding() and
        first['completed_modes']==[{'mode':case['mode'],'expected_score':case['expected'],'audit':case['audit']}
                                  for case in retained['audited_cases']],
        'continuation_retained_trio_independent_proof_changed')
    failed_native=PRIOR/'controls.private/task-001/baseline/artifacts/native-runtime'
    failed_seconds=_restored_single(failed_native)
    require(not (failed_native.parent/'saved-artifact.private.json').exists() and
        not any((failed_native.parent/'native-safety').glob('turn-*/receipt.private.json')) and
        not (PRIOR/'controls.private/task-001/trio.private.json').exists(),
        'continuation_failed_baseline_cannot_be_retained')
    diag=private(DIAGNOSTIC/'independent-terminal-cold-start-audit-20261004.private.json',DIAGNOSTIC_AUDIT_SHA)
    diag_terminal=private(diag['terminal_ref']['path'],diag['terminal_ref']['sha256'])
    require(diag['process_absent'] and diag['startup_returned'] and diag['native_attempt_count']==1 and
        diag['native_source146_unchanged'] and diag['current_v3_controller_binding_unchanged'] and
        diag['actor_inputs']==diag['model_tinker_calls']==diag['control_qualification_credit']==0 and
        diag_terminal['startup_returned'] and not diag_terminal['successful_start_means_logger_fix_proven'],
        'continuation_unscored_startup_evidence_changed')
    diag_seconds=_restored_single(DIAGNOSTIC/'diagnostic.private/native-runtime')
    diag_native=DIAGNOSTIC/'diagnostic.private/native-runtime'
    for key in ('startup_ref','native_lifecycle_ref','observer_ref'):
        require(ref(diag[key]['path'])==diag[key],'continuation_unscored_raw_evidence_changed')
    state=private(diag_native/'cycle-0-state.private.json')
    require(state['Running'] and state['Health']['Status']=='healthy' and not state['OOMKilled'],
            'continuation_unscored_native_boot_state_changed')
    world.cold.validate_attributes(private(diag_native/'cycle-0-native-attributes.private.json'),started_at=state['StartedAt'])
    wait=world.cold.profile.validate_witness(world.cold.source.private(diag_native/'cycle-0-effective-wait-witness.private.jsonl'),started_at=state['StartedAt'])
    require(wait==private(diag_native/'cycle-0-effective-wait-result.private.json') and wait['actual_effective_wait_seconds']==60,
            'continuation_unscored_effective_wait_changed')
    retained['provenance']='preserved_audited_original_v3_task000';retained['fresh_in_continuation']=False
    retained['artifact_namespace_ref']=artifact_namespace_ref(PRIOR/'controls.private/task-000')
    return retained,{'failed_task001_baseline':{'terminal_ref':ref(PRIOR/'independent-terminal-partial-boot-audit.private.json'),
        'failure_ref':ref(PRIOR/'controls.private/failure.private.json'),'native_lifecycle_seconds':failed_seconds,
        'artifact_namespace_ref':artifact_namespace_ref(PRIOR/'controls.private/task-001/baseline'),
        'case_credit':0,'failed_case_reused':False},
        'unscored_success':{'audit_ref':ref(DIAGNOSTIC/'independent-terminal-cold-start-audit-20261004.private.json'),
        'artifact_namespace_ref':artifact_namespace_ref(DIAGNOSTIC/'diagnostic.private/native-runtime'),
        'terminal_ref':diag['terminal_ref'],'native_lifecycle_seconds':diag_seconds,'case_credit':0},
        'kas_fix_or_underlying_permission_resource_cause_proven':False}


def review_contract(output=STAGE/'controls.private'):
    old=_original_authority();retained,boundaries=_saved_evidence(old);output=Path(output).absolute()
    require(output==STAGE/'controls.private' and output.resolve()==output,
            'continuation_fresh_owned_stage_required')
    rows=old['ordered_selection20']
    require(len(rows)==20 and len({row['task_id'] for row in rows})==20,
            'continuation_exact_original_selection20_required')
    return {'schema':SCHEMA,'old_authority_ref':ref(PRIOR/'root-selection-only-review-approved.private.json'),
        **{key:old[key] for key in ('plan_ref','native_binding_ref','train_accept_ref','source_review_ref')},
        'ordered_selection20':rows,'ordered_roster_sha256':old['ordered_roster_sha256'],
        'retained_trio':retained,'fresh_ordered_suffix':rows[1:],'fresh_ordinals':list(range(1,20)),
        'modes':[[mode,score] for mode,score in MODES],'output_root':str(output),
        'controller_binding':source_binding(),'startup_evidence_without_case_credit':boundaries,
        'native_source146':world.source_hashes(),'actor_limits':{'max_actions':90,'wall_seconds':720},
        'native_lifecycle_seconds':1200,'native_readiness_seconds':900,'effective_svwait_seconds':60,
        'host_worker_seconds':HOST_SECONDS,'host_cleanup_grace_seconds':CLEANUP_GRACE_SECONDS,
        'host_new_case_reserve_seconds':CASE_RESERVE_SECONDS,'one_worker_only':True,
        'host_expiry_sigterm_once_then_grace_sigkill_cleanup_uncertain':True,
        'automatic_worker_or_startup_retries':0,'native_profile_or_workflow_changed':False,
        'paid_model_tinker_authority':False,'final_task_substitution_authorized':False,
        'model_calls':0,'tinker_calls':0,'formal_admissions':0,'reference_only':True}


def check_authority(review_path,review_sha256):
    value=private(review_path,review_sha256)
    require(value.get('schema')==SCHEMA and value==review_contract(value['output_root']),
            'continuation_exact_current_root_authority_required')
    return value


def check_worker_parent(stage,supervisor_intent_sha256):
    intent=private(stage/'supervisor-start.private.json',supervisor_intent_sha256)
    require(intent['pid']==os.getppid() and intent['one_worker_only'] is True,
            'continuation_exact_supervisor_parent_required')
    lease=stage/'supervisor-lease.private.lock'
    fd=os.open(lease,os.O_RDWR|os.O_NOFOLLOW)
    try:
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return intent
        else:
            fcntl.flock(fd,fcntl.LOCK_UN)
            raise ValueError('continuation_live_supervisor_kernel_lease_required')
    finally:os.close(fd)


@contextmanager
def host_cancellation():
    previous=signal.getsignal(signal.SIGTERM)
    def stop(_signal,_frame):raise HostDeadline('continuation_host_deadline_requested_no_retry')
    signal.signal(signal.SIGTERM,stop)
    try:yield
    finally:signal.signal(signal.SIGTERM,previous)


def host_reserve(deadline,clock=time.monotonic):
    require(deadline-clock()>=CASE_RESERVE_SECONDS,'continuation_insufficient_host_reserve_no_new_case')


def exception_evidence(error):
    chain=[];seen=set()
    while error is not None and id(error) not in seen and len(chain)<8:
        seen.add(id(error));chain.append({'error_type':type(error).__name__,'error':str(error)})
        error=error.__cause__ if error.__cause__ is not None else error.__context__
    return {'raised_exception':chain[0],'original_primary_exception':chain[-1],
            'separate_outer_or_cleanup_exceptions':chain[:-1],'chain_raised_to_primary':chain}


def run_case(folder,identity,mode,score,binding,plan_path,permit,*,worker_context):
    """Exact V3 physical path; no actor, native reset, selector or score changes."""
    folder.mkdir(mode=0o700);(folder/'artifacts').mkdir(mode=0o700)
    world.write(folder/'fresh-case-intent.private.json',{'schema':'gitlab-continuation-fresh-case-intent-v1',
        'identity':identity,'mode':mode,'worker_pid':os.getpid(),'worker_ref':worker_context['worker_ref'],
        'authority_ref':worker_context['authority_ref'],'started_monotonic':time.monotonic()})
    with models.source_scope():
        backend=models.FullGitBackend(original.selection.RealGitLabSelectionBackend(),partition='selection',
            binding=binding,cohort_freeze_path=plan_path)
    backend.phase,backend.permit_path='train-qualification',permit;backend.set_output_root(folder)
    with models.source_scope(),backend.open(identity) as active:
        active.loop.call(workflow(active,active.original_task,mode,folder))
        original._budget(active);observation=active.observe(memory='')
        active.dispatch(original.reference.normalize_model_action('{"type":"finish","memory":""}',observation,
            current_frame_id=observation.frame_id))
        saved=active.read_saved_state();require(saved['independent_score']['reward']==score,'continuation_original_control_score_changed')
        world.write(folder/'artifacts/baseline.private.json',active.baseline_semantic)
        world.write(folder/'artifacts/saved-artifact.private.json',saved)
    require(active.post_restore_exact and active.environment_terminated,'continuation_actual_reset_not_complete')
    audited=original._audit_case(folder,identity,binding,plan_path)
    require(audited['score']==score,'continuation_saved_control_score_changed')
    world.write(folder/'result.private.json',audited)
    native=folder/'artifacts/native-runtime'
    world.write(folder/'fresh-case-completed.private.json',{'schema':'gitlab-continuation-fresh-case-completed-v1',
        'intent_ref':ref(folder/'fresh-case-intent.private.json'),'worker_ref':worker_context['worker_ref'],
        'native_start_ref':ref(native/'owned-lifecycle-start.private.json'),
        'native_end_ref':ref(native/'owned-lifecycle-end.private.json'),
        'completed_monotonic':time.monotonic(),'worker_pid':os.getpid()})
    return {'mode':mode,'expected':score,'result_ref':ref(folder/'result.private.json'),
        'fresh_provenance_ref':ref(folder/'fresh-case-completed.private.json')}


def audit_fresh_provenance(folder,entry,identity,mode,stage,seen_clone_ids):
    require(entry.get('fresh_provenance_ref')==ref(folder/'fresh-case-completed.private.json'),
            'continuation_fresh_process_provenance_ref_required')
    completed=private(entry['fresh_provenance_ref']['path'],entry['fresh_provenance_ref']['sha256'])
    require(completed['schema']=='gitlab-continuation-fresh-case-completed-v1' and
        completed['intent_ref']==ref(folder/'fresh-case-intent.private.json') and
        completed['worker_ref']==ref(stage/'worker-process-start.private.json'),
        'continuation_fresh_case_owner_ref_changed')
    intent=private(completed['intent_ref']['path'],completed['intent_ref']['sha256'])
    worker=private(completed['worker_ref']['path'],completed['worker_ref']['sha256'])
    supervisor=private(worker['supervisor_ref']['path'],worker['supervisor_ref']['sha256'])
    spawned=private(stage/'worker-start.private.json')
    require(intent['schema']=='gitlab-continuation-fresh-case-intent-v1' and intent['identity']==identity and
        intent['mode']==mode and intent['worker_ref']==completed['worker_ref'] and
        intent['worker_pid']==completed['worker_pid']==worker['pid']==spawned['pid'] and
        worker['ppid']==spawned['supervisor_pid']==supervisor['pid'] and
        intent['authority_ref']==worker['authority_ref']==supervisor['authority_ref'],
        'continuation_fresh_case_actual_worker_identity_changed')
    native=folder/'artifacts/native-runtime'
    require(completed['native_start_ref']==ref(native/'owned-lifecycle-start.private.json') and
        completed['native_end_ref']==ref(native/'owned-lifecycle-end.private.json'),
        'continuation_fresh_native_lifecycle_ref_changed')
    start=private(completed['native_start_ref']['path'],completed['native_start_ref']['sha256'])
    end=private(completed['native_end_ref']['path'],completed['native_end_ref']['sha256'])
    require(supervisor['worker_started_monotonic']<=worker['started_monotonic']<=intent['started_monotonic']<=
        start['started_monotonic']<=end['ended_monotonic']<=completed['completed_monotonic']<=
        supervisor['worker_deadline_monotonic'] and end['started_monotonic']==start['started_monotonic'],
        'continuation_old_artifacts_or_fresh_worker_time_boundary_changed')
    ids=[private(native/f'cycle-{index}-startup-proof.private.json')['identity']['container_id_sha256'] for index in (0,1)]
    require(len(set(ids))==2 and not set(ids)&seen_clone_ids,'continuation_fresh_clone_identity_reused')
    seen_clone_ids.update(ids)


def join_rows(authority,new_rows):
    require(len(new_rows)==19,'continuation_exact_nineteen_fresh_whole_trios_required')
    rows=[{'ordinal':0,'identity':authority['ordered_selection20'][0],
        'provenance':'preserved_audited_original_v3_task000','fresh_in_continuation':False,
        'trio_ref':authority['retained_trio']['trio_ref']}]
    for ordinal,row in enumerate(new_rows,1):
        require(row['ordinal']==ordinal and row['identity']==authority['ordered_selection20'][ordinal] and
            row['provenance']=='fresh_original_suffix_trio' and row['fresh_in_continuation'] is True and
            row['trio_ref']['path']==str(Path(authority['output_root'])/f'task-{ordinal:03d}/trio.private.json'),
            'continuation_fresh_order_identity_or_provenance_changed')
        rows.append(row)
    return rows


def run(*,review_path,review_sha256,supervisor_intent_sha256,execute=False):
    require(execute is True,'continuation_explicit_execution_required')
    authority=check_authority(review_path,review_sha256);out=Path(authority['output_root']);stage=out.parent
    require(Path(review_path).resolve()==stage/ROOT_APPROVAL_NAME,'continuation_root_approved_path_required')
    supervisor=check_worker_parent(stage,supervisor_intent_sha256)
    require(supervisor['authority_ref']==ref(review_path) and not out.exists() and not out.is_symlink(),
            'continuation_exact_supervisor_and_fresh_output_required')
    deadline=supervisor['worker_deadline_monotonic'];host_reserve(deadline)
    world.write(stage/'worker-process-start.private.json',{'pid':os.getpid(),'ppid':os.getppid(),
        'started_monotonic':time.monotonic(),
        'supervisor_ref':ref(stage/'supervisor-start.private.json'),'authority_ref':ref(review_path),'one_worker_only':True})
    out.mkdir(mode=0o700);world.write(out/'intent.private.json',authority)
    plan_path=Path(authority['plan_ref']['path']);plan,_=world.checked_plan(plan_path)
    binding=models.validate_binding(private(authority['native_binding_ref']['path'],authority['native_binding_ref']['sha256']))
    permit=out/'selection-only-native-permit.private.json'
    world.write(permit,{'schema':'envloop-gitlab-uniform-task-permit-v15','plan_sha256':ref(plan_path)['sha256'],
        'source_sha256s':plan['source_sha256s'],'phase':'train-qualification','accepted':True,'uniform_all_slots':True,
        'no_historical_credit':True,'note':'Explicit separately reviewed original selection continuation; retained trio remains original provenance.',
        'selection_only_root_authority_ref':ref(review_path)})
    completed=[];case_refs=[];ordinal=None;mode=None
    try:
        with host_cancellation():
            for ordinal,identity in enumerate(authority['fresh_ordered_suffix'],1):
                directory=out/f'task-{ordinal:03d}';directory.mkdir(mode=0o700);modes=[]
                for mode,score in MODES:
                    host_reserve(deadline)
                    require(check_authority(review_path,review_sha256)==authority,'continuation_authority_changed_before_case')
                    entry=run_case(directory/mode,identity,mode,score,binding,plan_path,permit,
                        worker_context={'worker_ref':ref(stage/'worker-process-start.private.json'),'authority_ref':ref(review_path)})
                    modes.append(entry);case_refs.append({'ordinal':ordinal,'identity':identity,**entry})
                    world.write(directory/(mode+'-completed.private.json'),case_refs[-1])
                trio={'ordinal':ordinal,'identity':identity,'modes':modes};world.write(directory/'trio.private.json',trio)
                completed.append({'ordinal':ordinal,'identity':identity,'provenance':'fresh_original_suffix_trio',
                    'fresh_in_continuation':True,'trio_ref':ref(directory/'trio.private.json')})
                world.write(out/f'complete-prefix-{ordinal:03d}.private.json',{'new_whole_trios':completed,'new_completed_case_refs':case_refs})
            require(check_authority(review_path,review_sha256)==authority,'continuation_authority_changed_after_cases')
            result={'schema':RESULT_SCHEMA,'authority_ref':ref(review_path),'controller_binding':source_binding(),
                'rows':join_rows(authority,completed),'tasks':20,'cases':60,'retained_original_cases':3,'fresh_cases':57,
                'startup_evidence_without_case_credit':authority['startup_evidence_without_case_credit'],
                'source_visual_review_pending':True,'reference_only':True,'model_calls':0,'tinker_calls':0,'formal_admissions':0}
            world.write(out/'result.private.json',result)
            verified=audit(review_path=review_path,review_sha256=review_sha256)
            world.write(out/'aggregate-audit.private.json',verified)
            return verified
    except BaseException as error:
        world.write(out/'failure.private.json',{'status':'terminal_continuation_failure_no_retry','error_type':type(error).__name__,
            'error':str(error),'traceback':traceback.format_exc(),'current_ordinal':ordinal,'current_mode':mode,
            'separate_exception_evidence':exception_evidence(error),
            'retained_trio_ref':authority['retained_trio']['trio_ref'],'new_whole_trio_refs':completed,
            'new_completed_case_refs':case_refs,'partial_cases_are_whole_trios':False,
            'automatic_retry_authorized':False,'model_calls':0,'tinker_calls':0,'formal_admissions':0})
        raise


def audit(*,review_path,review_sha256):
    authority=check_authority(review_path,review_sha256);out=Path(authority['output_root'])
    require(not (out/'failure.private.json').exists() and private(out/'intent.private.json')==authority,
            'continuation_failed_or_wrong_intent_cannot_qualify')
    result=private(out/'result.private.json')
    require(result['schema']==RESULT_SCHEMA and result['authority_ref']==ref(review_path) and
        result['controller_binding']==source_binding() and result['tasks']==20 and result['cases']==60 and
        result['retained_original_cases']==3 and result['fresh_cases']==57 and result['source_visual_review_pending'] is True and
        result['model_calls']==result['tinker_calls']==result['formal_admissions']==0,
        'continuation_exact_complete20_60_result_required')
    expected=join_rows(authority,result['rows'][1:])
    require(result['rows']==expected and result['startup_evidence_without_case_credit']==authority['startup_evidence_without_case_credit'],
            'continuation_retained_provenance_or_cost_boundaries_changed')
    binding=models.validate_binding(private(authority['native_binding_ref']['path'],authority['native_binding_ref']['sha256']))
    receipts=0;seen_clone_ids=set()
    for mode,_ in MODES:
        for index in (0,1):
            seen_clone_ids.add(private(PRIOR/f'controls.private/task-000/{mode}/artifacts/native-runtime/cycle-{index}-startup-proof.private.json')['identity']['container_id_sha256'])
    seen_clone_ids.add(private(DIAGNOSTIC/'diagnostic.private/native-runtime/cycle-0-startup-proof.private.json')['identity']['container_id_sha256'])
    for ordinal,row in enumerate(result['rows']):
        directory=Path(row['trio_ref']['path']).parent
        require(row['trio_ref']==ref(directory/'trio.private.json'),'continuation_trio_ref_changed')
        actual=audit_trio(directory,ordinal,authority['ordered_selection20'][ordinal],binding,Path(authority['plan_ref']['path']))
        if ordinal>0:
            trio=private(directory/'trio.private.json')
            for entry,(mode,_score) in zip(trio['modes'],MODES):
                audit_fresh_provenance(directory/mode,entry,authority['ordered_selection20'][ordinal],mode,out.parent,seen_clone_ids)
        receipts+=sum(case['audit']['native_receipts'] for case in actual['audited_cases'])
    return {'status':'original_selection20_60_real_saved_cases_verified_visual_review_pending','tasks':20,'cases':60,
        'retained_original_cases':3,'fresh_cases':57,'native_receipts':receipts,'result_ref':ref(out/'result.private.json'),
        'startup_attempts_outside_cases':2,'model_calls':0,'tinker_calls':0,'formal_admissions':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare-review');p.add_argument('--review-output',required=True)
    for command in ('run','audit'):
        p=sub.add_parser(command);p.add_argument('--review-path',required=True);p.add_argument('--review-sha256',required=True)
        if command=='run':p.add_argument('--supervisor-intent-sha256',required=True);p.add_argument('--execute',action='store_true')
    args=vars(parser.parse_args());command=args.pop('command')
    if command=='prepare-review':
        path=Path(args['review_output']);world.write(path,review_contract());value={'proposal_ref':ref(path),'native_calls':0}
    elif command=='run':value=run(**args)
    else:value=audit(**args)
    print(json.dumps(value,sort_keys=True))


if __name__=='__main__':main()
