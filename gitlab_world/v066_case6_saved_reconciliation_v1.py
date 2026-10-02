"""Read-only saved-phase reconciliation after a failed v6 cold reset.

No old exit, case completion, trio or journal is rewritten. The repeated
positive's saved SQL/full-Git verdict is audited separately from cleanup23.
No Docker, provider, native UI or reset call occurs in this module.
"""
from __future__ import annotations
import copy
import json
from pathlib import Path

from . import factory,gui_controls,verify
from . import v066_audit_only_continuation_v1 as prior
from . import v066_prospective_cohort_v6 as source
from . import v066_prospective_cohort_runtime_v6 as scoped
from . import v066_saved_git_oracle_v1 as saved_git
from . import v066_overlay_memory_maintenance_v1 as maintenance

SCHEMA='envloop-gitlab-v6-case6-saved-phase-reconciliation-v1'
PHYSICAL_SCHEMA='envloop-gitlab-spectator-physical-scheduling-private-v1'
INDEX=6


def require(ok,code):
    if not ok:raise ValueError(code)


def sha_private(path):return source.sha(source.private(path))


def snapshot(raw):
    value=json.loads(raw);body=copy.deepcopy(value);digest=body.pop('business_sha256',None)
    require(source.sha(factory.canonical(body))==digest,'Saved snapshot business digest changed')
    require(value.get('schema')==verify.SCHEMA and len(value.get('git',{}))==33,
        'Saved33-project snapshot schema/Git denominator changed');return value


def manifest(root):
    folders=[root/'controls',root/prior.NAMESPACE]
    files=[p for folder in folders for p in folder.rglob('*') if p.is_file()]
    files += [root/n for n in ['bootstrap-receipt.private.json','cohort-plan.private.json',
        'baseline-persisted-state.json','world-private.json','native-acl.private.json',
        'first-cold-readback.private.json','runtime.env','parent-archive-stop.private.json']]
    return {str(p.relative_to(root)):sha_private(p) for p in sorted(files)}


def audit_case6(*,parent_authority,entry_cow_state_path=None):
    doc,value,plan,plan_sha,baseline=prior.checked_authority(parent_authority)
    root=Path(value['epoch_root']);run=root/prior.NAMESPACE;rows=prior.read_journal(root)
    state=prior.journal_state(rows)
    require(state['terminal_failure'] is True and state['pending'] is None and state['next_index']==6 and
        [(r['kind'],r['task_index']) for r in rows]==[('intent',5),('terminal',5),('intent',6),('terminal',6)] and
        rows[1]['passed'] is True and rows[-1]['passed'] is False,'Exact consumed5/failed6 continuation required')
    prior.audit_prefix(parent_authority)  # Reopens original0..4 authority and the completed full-Git trio5.
    identity=plan['task_roster'][INDEX];task=None;phases=[]
    folder=run/'supervision';result_raw=source.private(folder/'006-result.private.json');result=json.loads(result_raw)
    child=result['child'];marker=json.loads(source.private(folder/'006-child-started.private.json'))
    intent=rows[2];terminal=rows[3];authority_sha=sha_private(parent_authority)
    require(result['schema']=='envloop-gitlab-v6-audit-only-supervised-private-v1' and result['index']==INDEX and
        result['passed'] is False and child['exit_code']==1 and child['child_terminated'] is True and
        child['process_group_terminated'] is True and child['timed_out'] is False and
        child['group_survivor_observed_after_child_wait'] is False and child['termination_unconfirmed'] is False and
        source.sha(result_raw)==terminal['supervisor_result_sha256'],'Original failed child terminal binding changed')
    require(marker['task_index']==INDEX and marker['child_pid']==child['child_pid'] and
        marker['parent_pid']==intent['supervisor_pid'] and marker['pending_intent_sha256']==intent['entry_sha256'] and
        marker['permit_sha256']==intent['permit_sha256'] and marker['authority_sha256']==intent['authority_sha256']==authority_sha and
        marker['old_intent_replay_authorized'] is False and intent['task_id']==identity['task_id'] and
        intent['package_sha256']==identity['package_sha256'] and intent['expected_entry_generation']==20,
        'Consumed case6 child/source/intent identity changed')
    for name,field in [('006-stdout.private.log','stdout_sha256'),('006-stderr.private.log','stderr_sha256')]:
        require(sha_private(folder/name)==child[field],'Original failed child raw log changed')
    attempt=run/'attempts/006'
    require(not (attempt/'trio-complete.private.json').exists() and
        not (folder/'006-child-result.private.json').exists() and
        not (attempt/'positive-2/case-complete.private.json').exists() and
        not (attempt/'positive-2/after-reset-persisted-state.json').exists(),
        'Missing original completion/reset was fabricated or phase replayed')
    with scoped.cohort_context(value):
        task=gui_controls._task(identity['task_id']);project,progress=verify._context(task)
        package={'world_sha256':plan['world_sha256'],'baseline_business_sha256':baseline['business_sha256'],
            'native_acl_sha256':plan['native_acl_sha256'],'task':task}
        require(source.sha(factory.canonical(task))==identity['task_object_sha256'] and
            source.sha(factory.canonical(package))==identity['package_sha256'],'Current source task/package changed')
        for number,(label,variant,score) in enumerate(prior.original.lane.CASES[identity['template_group']]):
            case=attempt/label;receipt_raw=source.private(case/'receipt.json');receipt=json.loads(receipt_raw)
            after_raw=source.private(case/'after-persisted-state.json');after=snapshot(after_raw)
            require(receipt['schema']=='envloop-gitlab-gui-control-attempt-v1' and receipt['task_id']==identity['task_id'] and
                receipt['case']==label and receipt['negative_variant']==variant and receipt['fresh_browser_context'] is True and
                receipt['scoped_non_admin_operator'] is True and receipt['model_calls']==0 and
                receipt['credential_retained_in_receipt'] is False and receipt['raw_har_retained'] is False,
                'Saved GUI phase source/context provenance changed')
            sidecar=json.loads(source.private(case/'git-sidecar.private.json'))
            oracle=saved_git.audit_formal_saved_task(task,baseline,after,project=project,progress=progress,
                captured_git=sidecar,read_ref=lambda ref,case=case:prior._read_ref(case,ref),
                captured_verdict=receipt['persisted_oracle'],
                expected_verifier_sha256=value['source_sha256s']['gitlab_world/verify.py'])
            verdict=oracle['verdict']
            require(verdict['score']==score and verdict['persisted_oracle'] is True and
                verdict['no_regression'] is (score==1.0) and oracle['full_git_tree_verified'] is True,
                'Independent saved SQL/full-Git phase verdict disagrees')
            screenshots={}
            for p in sorted(case.glob('*.png')):
                raw=source.private(p);require(raw.startswith(b'\x89PNG\r\n\x1a\n'),'Saved phase GUI capture is not PNG')
                screenshots[p.name]=source.sha(raw)
            require(len(screenshots)==5 and screenshots.get('policy.png')==receipt['gui']['policy_screenshot_sha256'] and
                screenshots.get('milestone-saved.png')==receipt['gui']['milestone_screenshot_sha256'] and
                receipt['gui']['saved_visible'] is True and receipt['gui']['issue_links_reload_verified'] is True,
                'Saved native milestone phase screenshots/GUI receipt changed')
            original_reset=None
            if number<2:
                complete=json.loads(source.private(case/'case-complete.private.json'))
                restored_raw=source.private(case/'after-reset-persisted-state.json')
                require(snapshot(restored_raw)==baseline and complete['schema']==prior.original.lane.CASE_SCHEMA and
                    complete['case']==label and complete['expected_score']==score and complete['plan_sha256']==plan_sha and
                    complete['task_id']==identity['task_id'] and complete['source_bundle_sha256']==plan['source_bundle_sha256'] and
                    complete['after_state_sha256']==source.sha(after_raw) and
                    complete['restored_state_sha256']==source.sha(restored_raw) and
                    complete['raw_receipt_sha256']==source.sha(receipt_raw) and
                    complete['all_gui_screenshot_sha256s']==screenshots,
                    'Completed first two case/reset bindings changed')
                original_reset=complete['reset_receipt']
                require(original_reset=={'cold_reset':True,'container_identity_changed':True,
                    'generation':21+number,'same_business_sha256':True},'First two original cold resets changed')
            phases.append({'phase_ordinal':number,'expected_score':score,'saved_state_sha256':source.sha(after_raw),
                'raw_receipt_sha256':source.sha(receipt_raw),'sidecar_sha256':sha_private(case/'git-sidecar.private.json'),
                'saved_git_oracle':oracle,'original_case_completion_present':number<2,
                'original_reset_receipt':original_reset,'gui_screenshot_sha256s':screenshots})
    cleanup_raw=source.private(folder/'006-cleanup-after-reset-persisted-state.private.json')
    cold_raw=source.private(entry_cow_state_path or root/'cow-reset-state.json');cold=json.loads(cold_raw)
    require(snapshot(cleanup_raw)==baseline and result['cleanup']['exact_baseline'] is True and
        result['cleanup']['restored_sql_git_sha256']==source.sha(cleanup_raw) and
        cold['clone_generation']==23 and cold['last_readback_equal'] is True and
        cold['last_clone_container_id_sha256']!=cold['first_clone_container_id_sha256'] and
        prior.original.cold_seed_binding(value,baseline)==doc['entry_cold_seed_binding'],
        'Separate terminal cleanup23 baseline/cold provenance changed')
    forensic=result['cleanup']['forensics'];matches=[]
    for directory in (root/'startup-forensics').glob('audit-continuation-terminal-6-*'):
        paths={'docker_logs_stdout':'docker-logs.stdout.private.log','docker_logs_stderr':'docker-logs.stderr.private.log',
            'docker_state_stdout':'docker-state.stdout.private.json','docker_state_stderr':'docker-state.stderr.private.log'}
        if all((directory/n).is_file() and sha_private(directory/n)==forensic['raw_file_sha256s'][k] for k,n in paths.items()):
            matches.append(directory)
    require(len(matches)==1 and forensic['state_exit_code']==1 and forensic['state_oom_killed'] is False,
        'Exact retained failed startup logs/State missing')
    state_row=json.loads(source.private(matches[0]/'docker-state.stdout.private.json'))
    require(state_row['ExitCode']==1 and state_row['OOMKilled'] is False,'Failed startup raw State disagrees')
    log=source.private(matches[0]/'docker-logs.stdout.private.log')+source.private(matches[0]/'docker-logs.stderr.private.log')
    require(b'postgres-exporter/log' in log and b'force-reload' in log and b'timeout' in log,
        'Retained proximate logger startup timeout changed')
    return {'schema':SCHEMA,'status':'saved_phases_reconciled_separate_cleanup23_exact_no_completion_rewrite',
        'parent_authority_sha256':authority_sha,'parent_authority_path':str(parent_authority),
        'original_freeze_sha256':doc['original_freeze_sha256'],'cohort_plan_sha256':plan_sha,
        'old_continuation_journal_sha256':sha_private(run/'journal.private.jsonl'),
        'old_continuation_terminal_head_sha256':state['head_sha256'],
        'original_child_exit_code':1,'original_terminal_passed':False,'original_result_sha256':source.sha(result_raw),
        'saved_phase_scores':[p['expected_score'] for p in phases],'saved_phase_audits':phases,
        'original_complete_phase_count':2,'original_trio_completion_present':False,
        'repeated_positive_original_reset_receipt_present':False,
        'separate_cleanup_generation':23,'separate_cleanup_sql_git_sha256':source.sha(cleanup_raw),
        'entry_cow_state_sha256':source.sha(cold_raw),'cleanup_reset_return_receipt_retained':False,
        'last_cold_readback_equal':True,'proximate_startup_error':'postgres-exporter/log force-reload timeout',
        'startup_raw_state_oom_killed':False,'underlying_root_cause_established':False,
        'preserved_artifact_sha256s':manifest(root),'first_untouched_index':7,'remaining_control_count':93,
        'first_future_reset_generations':[24,25,26],'final_expected_generation':302,
        'new_dispatch_authorized':False,'same_intent_replay_authorized':False,'model_calls':0,
        'provider_calls':0,'official_final_admitted':0,'control_credit':0}


def validate_physical_receipt(path,*,value):
    raw=source.private(path);doc=json.loads(raw);original=Path(value['evaluator_root'])
    plan=json.loads(source.private(original/'work/gitlab-overlay-memory-maintenance-root-20260930.private/plan.private.json'))
    require(doc.get('schema')==PHYSICAL_SCHEMA and
        doc.get('status')=='unused_original31_gracefully_stopped_no_profile_change' and
        all(doc.get(k) is True for k in ['root_authorized','no_active_lease_or_workers_verified',
            'spectator_running_before','spectator_id_unchanged','successor_running_after',
            'no_wait_config_monitoring_or_task_data_change']) and doc.get('spectator_running_after') is False and
        doc.get('graceful_stop_exit_code')==0 and
        all(doc.get(k)==0 for k in ['model_calls','provider_calls','official_final_admitted','control_credit']),
        'Physical scheduling receipt is absent or not bounded source/data-preserving stop')
    require(doc.get('spectator_container_id_sha256')==source.sha(plan['original_container_id'].encode()) and
        doc.get('source_freeze_sha256')==value['_freeze_sha256'],
        'Physical scheduling container/source identity changed')
    for key,expected in [('metadata_sha256s',plan['metadata_sha256s']),('core_source_sha256s',plan['core_source_sha256s']),
        ('frozen_bound_metadata_sha256s',value['bound_metadata_sha256s']),('seed_volume_identities',plan['original_seed_volume_identities'])]:
        require(doc.get(key+'_before')==doc.get(key+'_after')==expected,'Physical scheduling sealed metadata/core/seed identity changed')
    env_sha=sha_private(Path(value['epoch_root'])/'runtime.env')
    require(doc.get('successor_runtime_env_sha256_before')==doc.get('successor_runtime_env_sha256_after')==env_sha,
        'Physical scheduling successor runtime environment changed')
    before=doc.get('vm_path_stat_before');after=doc.get('vm_path_stat_after')
    def flatten(value):
        if type(value) is dict and set(value)==set(plan['overlay_recipe']):
            require(all(type(value[role]) is dict and set(value[role])==set(paths)
                for role,paths in plan['overlay_recipe'].items()),'Physical stat role/path set changed')
            return {path:value[role][kind] for role,paths in plan['overlay_recipe'].items() for kind,path in paths.items()}
        return value
    before=flatten(before);after=flatten(after)
    expected_paths={p for paths in plan['overlay_recipe'].values() for p in paths.values()}
    require(type(before) is dict and type(after) is dict and set(before)==set(after)==expected_paths,
        'Physical scheduling VM directory stat set changed')
    immutable={paths['lower'] for paths in plan['overlay_recipe'].values()}
    for p in expected_paths:
        a,b=before[p],after[p]
        fields={'inode','size','mode','uid','gid','mtime_ns'}
        require(set(a)==set(b) and set(a) in (fields,fields|{'path'}),'VM directory stat fields changed')
        if 'path' in a:require(a['path']==b['path']==p,'VM directory stat path binding changed')
        keys=set(a) if p in immutable else {'inode','mode','uid','gid'}
        require(all(a[k]==b[k] for k in keys),'Physical scheduling replaced/modified an immutable directory identity')
    refs=doc.get('raw_evidence_refs');require(type(refs) is list and len(refs)>=4,'Physical stop raw process/State/command evidence missing')
    for ref in refs:prior._read_ref(Path(path).parent,ref)
    return {'physical_scheduling_receipt_sha256':source.sha(raw),'original31_stop_not_logger_fix_proof':True,
        'source_profile_data_unchanged':True,'control_credit':0}
