"""Read-only source-bound Magento saved performance with unknown billing."""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
from cursibench import full_study_final_dispatch_v1 as files
from cursibench import native_surface_guard_policy_v1 as policy
from native_desktop_factory.deadline_model_transport_v21 import checked_deadline_proof
from . import verify


def require(value,code):
    if not value:raise policy.GuardError(code)


def audit_episode(root,row,*,provider_close_required=True):
    root=Path(root)
    from .native_surface_workers_v1 import public_binding
    require(row['native_source_binding_sha256']==public_binding()['binding_sha256'],'magento_source_changed_after_episode')
    require(root.is_dir() and not root.is_symlink() and root.stat().st_mode&0o077==0,'magento_private_episode_required')
    def read_ref(ref):
        relative=Path(ref['path']);require(not relative.is_absolute() and '..' not in relative.parts,'magento_native_evidence_outside_episode')
        path=root/relative;require(path.resolve().is_relative_to(root.resolve()),'magento_native_evidence_outside_episode');raw=path.read_bytes()
        require(not path.is_symlink() and path.stat().st_mode&0o077==0 and sha256(raw).hexdigest()==ref['sha256'],
            'magento_native_evidence_changed');return raw
    def read(name):
        path=root/name;require(path.is_file() and not path.is_symlink() and path.stat().st_mode&0o077==0,'magento_raw_evidence_missing')
        return json.loads(path.read_bytes())
    saved=read('saved-state.private.json');verifier=read('verifier.private.json');reset=read('reset.private.json')
    original=verify.score_saved_state(verifier['case'],verifier['baseline'],saved['snapshot'])
    require(original==verifier['verdict'] and row['score']==int(original['score']==1.0),'magento_saved_score_not_original_rederivation')
    verify.check_material_reset(verifier['baseline'],reset['restored_snapshot'])
    require(all(reset.get(k) is True for k in ('fresh_clone_reset_passed','different_app_container_ids',
        'different_search_container_ids','no_host_mounts','both_pairs_removed')),'magento_fresh_clone_cleanup_unproved')
    require(saved.get('native_save_observed') is True,'magento_saved_readback_unproved')
    if 'full_native_readback_image' in saved:read_ref(saved['full_native_readback_image']);read_ref(saved['full_native_readback_context'])
    frames=read('frames.private.json')['frames'];actions=read('actions.private.json')['actions']
    require(row['turn_count']==len(frames) and row['action_count']==sum(r['status']=='applied' for r in actions) and
        len(frames)<=90,'magento_action_budget_or_trace_count_changed')
    for frame in frames:
        read_ref(frame['frame']);envelope=json.loads(read_ref(frame['native_envelope']));policy.validate_envelope(envelope)
        native=json.loads(read_ref(envelope['raw_envelope']));held=json.loads(read_ref(envelope['lease']['evidence']))
        require(envelope['owned_surface'] is True and envelope['frame_id']==frame['frame_id'] and envelope['step']==frame['step'] and
            envelope['task_id']==row['task_id'] and envelope['task_binding_sha256']==row['package_sha256'] and
            envelope['raw_image']['sha256']==frame['frame']['sha256'] and native['account_witness']['visible_count']==1 and
            native['native_username']==native['account_witness']['username'] and native['visible'] is True and native['top_window'] is True and
            native['app_shell'] is True and native['native_window_sha256']==envelope['lease']['window_sha256'] and
            sha256(native['native_username'].encode()).hexdigest()==held['native_username_sha256']==envelope['lease']['account_sha256'],
            'magento_actual_observed_owned_frame_changed')
    nonces=set()
    for action in actions:
        capsule=json.loads(read_ref(action['contract']['native_surface_guard']))
        require(capsule['action']==action['action'] and capsule['action']['frame_id'] not in nonces,
            'magento_current_frame_action_or_nonce_changed');nonces.add(capsule['action']['frame_id'])
        from .native_surface_guard_v1 import NativeAdapter
        from urllib.parse import urlsplit
        for envelope in (capsule['observed'],capsule['current']):
            policy.validate_envelope(envelope);read_ref(envelope['raw_image'])
            native=json.loads(read_ref(envelope['raw_envelope']));held=json.loads(read_ref(envelope['lease']['evidence']))
            parsed=urlsplit(native['physical_url']);origin=parsed.scheme+'://'+parsed.netloc
            focus=(native['focus'] or {}).get('ref','body')
            require(envelope['targets']==NativeAdapter.targets(None,native) and envelope['viewport']==native['viewport'] and
                envelope['context_id']==policy.digest(native['physical_url']) and envelope['focus_id']==focus and
                envelope['modal_id']==('owned-dialog' if native['modals'] else 'none') and
                envelope['owned_surface'] is True and origin==held['origin'] and
                (parsed.path=='/admin' or parsed.path.startswith('/admin/')) and native['top_window'] is True and
                native['visible'] is True and native['app_shell'] is True and
                native['account_witness']['visible_count']==1 and native['account_witness']['username']==native['native_username'] and
                sha256(native['native_username'].encode()).hexdigest()==held['native_username_sha256']==envelope['lease']['account_sha256'] and
                native['native_window_sha256']==envelope['lease']['window_sha256'],
                'magento_native_surface_not_rederived')
        check=capsule['lease_check'];policy.validate_lease_check(check,policy.validate_lease(capsule['observed']['lease']))
        raw_check=json.loads(read_ref(check['evidence']))
        require(raw_check['active'] is True and raw_check['app']['Mounts']==[] and raw_check['search']['Mounts']==[] and
            raw_check['app']['State']['Running'] is True and raw_check['search']['State']['Running'] is True and
            sha256(raw_check['app']['Id'].encode()).hexdigest()==held['app_id_sha256'] and
            sha256(raw_check['search']['Id'].encode()).hexdigest()==held['search_id_sha256'] and
            raw_check['app']['Image']==held['app_image_sha256'] and raw_check['search']['Image']==held['search_image_sha256'],
            'magento_native_clone_lease_not_rederived')
        decided=policy.decision(capsule['observed'],capsule['current'],capsule['action'],
            lease_check=lambda _lease:capsule['lease_check'],now=capsule['audit_clock'])
        require(decided==capsule['decision'],'magento_native_guard_not_rederived')
        receipt=policy.validate_receipt(capsule['receipt'])
        if receipt['driver_evidence'] is not None:
            driver=json.loads(read_ref(capsule['receipt']['driver_evidence']))
            require(driver['returned'] is True and driver['actual_calls'],'magento_applied_without_actual_io')
    clock=read('actor-clock/end.private.json')
    require(clock['actor_deadline_monotonic']-clock['actor_started_monotonic']==720 and
        clock['native_actions_after_deadline']==0 and clock['evaluation_outside_actor_clock'] is True,
        'magento_actual_actor_clock_unproved')
    for event in clock['native_io']:
        read_ref(event['intent']);read_ref(event['completion'])
        require(event['status']=='returned' and event['started_monotonic']<=event['completed_monotonic']<=clock['actor_deadline_monotonic'],
            'magento_native_io_unknown_or_late')
    lifecycle=read('lifecycle.private.json')
    require(lifecycle['reset_cleanup_ended_monotonic']>=clock['raw_end_acknowledged_monotonic'] and
        lifecycle['owned_lease_seconds_limit']==1200 and lifecycle['provider_close_not_inferred'] is True and
        lifecycle['reset_cleanup_ended_monotonic']-lifecycle['started_monotonic']<=1200,
        'magento_owned_lifecycle_unproved')
    samples=read('samples.private.json')['samples']
    require(samples==row['samples'],'magento_actual_samples_changed')
    for sample in samples:
        intent=json.loads(read_ref(sample['intent']))
        require(intent['task_id']==row['task_id'] and intent['package_sha256']==row['package_sha256'] and
            intent['paid_attempt_id']==sample['paid_attempt_id'] and intent['same_request_replay_authorized'] is False,
            'magento_actual_paid_intent_changed')
        if sample['status']=='control_action':
            require(not provider_close_required and sample['raw_result']['model_call_performed'] is False,'control_cannot_be_model_response')
        elif sample['status']=='completed':
            require(sample['result'] is not None and json.loads(read_ref(sample['result']))==sample['raw_result'] and
                sample['raw_result']['status']=='completed' and sample['raw_result']['new_dispatch'] is True and
                not sample['raw_result'].get('reused') and sample['request_id']==intent['request_id'],
                'magento_completed_model_response_not_reopened')
        elif sample['status']=='actor_deadline_proven':
            require(sample['result'] is None and sample['deadline_evidence'] is not None,'magento_unknown_result_cannot_be_completed')
            deadline=json.loads(read_ref(sample['deadline_evidence']))
            require(deadline['sampling_failure']==sample['raw_result'] and deadline['request_id']==sample['request_id']==intent['request_id'] and
                deadline['frame_id']==intent['frame_id'] and deadline['frame_sha256']==intent['frame_sha256'] and
                deadline['gui_applied'] is False and deadline['same_request_replay_authorized'] is False,
                'magento_actual_deadline_sample_changed')
            checked_deadline_proof(deadline['actor_deadline_proof'],clock['actor_deadline_monotonic'])
        else:raise policy.GuardError('magento_unproved_model_or_control_result')
    require(row['actor_wall_time_ms']==round(clock['actor_elapsed_seconds']*1000) and
        0<=row['actor_wall_time_ms']<=720000,'magento_actor_measurement_changed')
    close=None
    if provider_close_required:
        close=json.loads(read_ref(row['provider_close_ref']))
        require(close['status']=='acknowledged' and close['real_close_call_returned'] is True and
            row['complete_lifecycle_wall_time_ms']<=1200000,'magento_real_owned_provider_close_missing')
    return {'samples':samples,'saved':saved,'verifier':verifier,'reset':reset,'clock':clock,'actions':actions,'frames':frames,'close':close}


def prepare_budget_performance(*,command,output,episode,row,sample_paid_attempt_id=None,prefix='budget',study=None):
    from .native_surface_workers_v1 import write
    audited=audit_episode(episode,row)
    task=write(output,prefix+'-task.private.json',{'attempt_id':command['attempt_id'],'task_id':command['task_id'],
        'package_sha256':command['package_sha256'],'owner_slot':command['owner_slot'],'checkpoint_sha256':command['checkpoint_sha256']})
    arguments={'schema':'magento-budget-performance-input-v1','episode_root':str(episode),
        'output_root':str(output),'native_row':files.reference(output,episode/'native-row.private.json'),
        'task':task,'sample_paid_attempt_id':sample_paid_attempt_id or command['attempt_id']}
    module_path=Path(__file__)
    descriptor={'adapter':{'module':'magento_catalog_factory.native_surface_budget_performance_v1',
        'function':'verify_budget_performance','source_sha256':sha256(module_path.read_bytes()).hexdigest()},'arguments':arguments}
    input_ref=write(output,prefix+'-performance-input.private.json',arguments)
    if study is None:return {'receipt':input_ref,'verification':descriptor}
    checked=verify_budget_performance(study=study,owner_slot=command['owner_slot'],verification=arguments)
    receipt=write(output,prefix+'-performance.private.json',{'receipt':checked,'verification':descriptor})
    return receipt


def verify_budget_performance(*,study,owner_slot,verification):
    require(type(verification) is dict and set(verification)=={'schema','episode_root','output_root','native_row','task','sample_paid_attempt_id'} and
        verification['schema']=='magento-budget-performance-input-v1','magento_budget_descriptor_changed')
    output=Path(verification['output_root']);root=Path(verification['episode_root'])
    require(output.resolve().is_relative_to((study.repo_root/'work').resolve()) and root.parent.resolve()==output.resolve(),
        'magento_budget_outside_owned_work')
    _path,raw=files.private_reference(output,verification['native_row'],'actual_magento_native_row');row=json.loads(raw)
    _path,raw=files.private_reference(output,verification['task'],'actual_magento_task');task=json.loads(raw)
    require(task['owner_slot']==owner_slot and task['task_id']==row['task_id'] and task['package_sha256']==row['package_sha256'],
        'magento_budget_owner_or_task_changed')
    audited=audit_episode(root,row);clock=audited['clock']
    stop=json.loads((root/'actor-clock/budget-stop.private.json').read_bytes())
    proof=checked_deadline_proof(stop['actor_deadline_proof'],clock['actor_deadline_monotonic'])
    require(clock['deadline_proof']==proof.receipt() and stop['gui_applied'] is False and
        stop['same_request_replay_authorized'] is False and stop['paid_attempt_id']==verification['sample_paid_attempt_id'],
        'magento_typed_deadline_paid_request_unbound')
    # Reopen the actual durable SDK request cache. A typed declaration alone
    # cannot establish whether a request was dispatched or completed.
    import sqlite3
    from urllib.parse import quote
    sdk=root/'sampling-journal/requests.sqlite3'
    require(sdk.is_file() and not sdk.is_symlink() and sdk.stat().st_mode&0o077==0,'magento_actual_sdk_request_journal_missing')
    with sqlite3.connect('file:'+quote(str(sdk.resolve()))+'?mode=ro',uri=True) as connection:
        record=connection.execute('SELECT state,result FROM requests WHERE id=?',(stop['request_id'],)).fetchone()
    require(record is not None and record[0]=='complete' and record[1] is not None,'magento_actual_sdk_terminal_request_missing')
    sdk_result=json.loads(record[1]);pending=[r for r in row['samples'] if r['status']=='actor_deadline_proven']
    require(len(pending)==1 and pending[0]['request_id']==stop['request_id'] and
        pending[0]['paid_attempt_id']==verification['sample_paid_attempt_id'] and sdk_result==pending[0]['raw_result'] and
        sdk_result['status']!='completed' and sdk_result['new_dispatch'] is True and not sdk_result.get('reused') and
        sdk_result['usage']['output_tokens'] is None,'magento_actual_sdk_uncertain_result_changed')
    inference=('not_submitted_before_actor_deadline' if not proof.model_dispatch_may_have_occurred else
        'late_completed_withheld_from_gui' if proof.model_completion_known else 'completion_unknown_after_actor_deadline')
    names={'saved-state.private.json':root/'saved-state.private.json','verifier.private.json':root/'verifier.private.json',
        'reset.private.json':root/'reset.private.json','actor-clock.private.json':root/'actor-clock/end.private.json',
        'actor-budget-stop.private.json':root/'actor-clock/budget-stop.private.json','task.private.json':output/verification['task']['path']}
    return {'schema':'cua-verified-budget-performance-with-unknown-billing-v22','task_id':task['task_id'],
        'package_sha256':task['package_sha256'],'owner_slot':owner_slot,'checkpoint_sha256':task['checkpoint_sha256'],
        'performance':{'status':'independently_saved_scored_and_reset','score':row['score']},
        'inference':{'status':inference,'unknown_response_is_completed':False,'request_replayed':False,
            'completed_model_response_count':sum(r['status']=='completed' for r in row['samples'])},
        'billing':{'actual_usd':None},'provider_close_acknowledged':True,'sample_paid_attempt_id':verification['sample_paid_attempt_id'],
        'evidence_sha256':{name:sha256(path.read_bytes()).hexdigest() for name,path in names.items()},
        'amendment_sha256':study.amendment_sha256,'performance_coverage_eligible':True,'formal_registration_performed':False}
