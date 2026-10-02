"""Executable selection/base bridge for witnessed v22 paid/performance policy.

The v21 actor, scorer, transport and reset stay source qualified. A new clean
sampler is scoped to each task; a consumed uncertain request is never retried.
"""
from pathlib import Path
import json
from cursibench import full_study_runtime_v2 as policy_runtime
from cursibench import full_study_performance_coverage_v2 as coverage
from . import prospective_model_worker_v21 as model
from . import model_transport_integration_v21 as integration
from . import deadline_model_transport_v21 as transport
from .factory import digest


def verification_descriptor(study,*,batch,evaluator,package,checkpoint_sha256,sampler_process):
    root=Path(batch);name=evaluator.parent.name
    folder=root/'budget-verification'/name;folder.mkdir(mode=0o700,parents=True)
    source=folder/('source'+Path(package['filename']).suffix)
    policy_runtime.campaign._private_write_new(source,package['source'])
    description={k:v for k,v in package.items() if k!='source'}
    description['source_ref']={'path':str(source.resolve()),'sha256':digest(package['source'])}
    package_path=folder/'package.private.json';policy_runtime.campaign._private_write_new(package_path,integration.canonical(description))
    salt_path=Path(study._desktop_v11_private_map) if hasattr(study,'_desktop_v11_private_map') else None
    if salt_path is None:raise ValueError('source_bound_private_salt_reference_required')
    return {'batch':str(root.resolve()),'evaluator':str(evaluator.resolve()),
        'package_ref':{'path':str(package_path.resolve()),'sha256':digest(package_path.read_bytes())},
        'salt_ref':{'path':str(salt_path.resolve()),'sha256':digest(salt_path.read_bytes())},
        'checkpoint_sha256':checkpoint_sha256,'sampler_process':str(Path(sampler_process).resolve())}


def current_episode_module():
    # The uniform actual-paid-ID source hook is an explicit new dependency.
    # Missing hook refuses before a provider/native actor is constructed.
    from . import current_episode_paid_id_v22
    return current_episode_paid_id_v22


def run_selection(*,worker,session,started,checkpoint_path,output_dir,base=False):
    engine=current_episode_module()
    study=session.study
    if type(study) is not policy_runtime.FrozenStudy or worker.study is not study:
        raise ValueError('real_v22_study_and_owned_worker_required')
    with integration.runtime_context(),policy_runtime.runtime_context(study):
        admitted=worker._gate();cell,training,sampling,quote=worker._policy()
        study._desktop_v11_private_map=admitted['private_map']
        identities=list(study.task_views('desktop-native')['selection'])
        if started['task_count']!=20 or [{k:r[k] for k in ('task_id','package_sha256')} for r in started['selection_tasks']]!=[{k:r[k] for k in ('task_id','package_sha256')} for r in identities]:
            raise ValueError('same_twenty_selection_identities_required')
        checkpoint=started['checkpoint_path_sha256'];owner=session.intent['researcher_id']
        if base:
            if owner!='shared-base' or checkpoint_path is not None or checkpoint!=integration.proposal()['base_checkpoint_sha256']:raise ValueError('exact_base_checkpoint_required')
        else:
            events=[r for r in session._events('tinker_checkpoint') if r['data']['checkpoint_path_sha256']==checkpoint]
            if owner not in integration.matrix.RESEARCHERS or len(events)!=1 or session.checkpoint_result(events[0])['checkpoint_path']!=checkpoint_path:raise ValueError('actual_trained_checkpoint_lineage_required')
        root=Path(output_dir).absolute()
        if root.exists() or root.is_symlink() or not root.parent.resolve().is_relative_to(study.repo_root/'work'):raise ValueError('fresh_owned_selection_output_required')
        root.mkdir(mode=0o700,parents=True)
        paid=engine.PaidCalls(attempt_id=started['attempt_id'],checkpoint=checkpoint,identities=identities,output_dir=root,
            runtime=integration.proposal()['worker_runtime_sha256'],quote=quote,session=session)
        packages=worker._packages(admitted,identities,'selection');rows=[];budget_receipts=[]
        try:
            for ordinal,package in enumerate(packages):
                journal=root/('sampler-process-'+str(ordinal).zfill(3))
                sampler=transport.ModelSampler(repo_root=study.repo_root,journal_root=journal,plan_sha256=study.plan_sha256)
                success=False
                try:
                    paid.invoke(suffix='sampler-setup-'+str(ordinal).zfill(3),category='tinker',
                        request={'kind':'sampler_setup','task_ordinal':ordinal,'sampling_kind':'base' if base else 'checkpoint'},
                        provider=lambda _:sampler.start(checkpoint_path=checkpoint_path,checkpoint_sha256=checkpoint,
                            seed=sampling['seed'],max_output_tokens=sampling['max_output_tokens'],attempt_id=started['attempt_id']+'-'+str(ordinal)))
                    row,out,trace,elapsed,outcome=engine.DesktopProspectiveModelWorker._episode(worker,admitted=admitted,package=package,ordinal=ordinal,batch=root,paid=paid,sampler=sampler)
                    success=True
                finally:sampler.close(success)
                terminal=json.loads(integration.controls.private(journal/'child-terminal.private.json'))
                if terminal['provider_shutdown_acknowledged'] is not True or terminal['forced_termination'] is not False:raise ValueError('owned_provider_close_ack_required_before_next_task')
                if (out/'actor-budget-stop.private.json').exists():
                    descriptor=verification_descriptor(study,batch=root,evaluator=out,package=package,checkpoint_sha256=checkpoint,sampler_process=journal)
                    receipt=policy_runtime.verify_budget_artifacts(study,owner,descriptor)
                    session.authorize_verified_budget_stop(receipt['sample_paid_attempt_id'],verification=descriptor)
                    budget_receipts.append(receipt)
                rows.append(row)
            calls=[]
            for identifier in paid.ids:
                request=json.loads(integration.controls.private(root/'paid'/(identifier+'.request.private.json')))
                path=root/'paid'/(identifier+'.result.private.json');result=json.loads(integration.controls.private(path)) if path.exists() else None
                calls.append({'attempt_id':identifier,'category':json.loads(integration.controls.private(root/'paid'/(identifier+'.intent.private.json')))['category'],
                    'request':request,'result_present':result is not None,'result_status':None if result is None else result.get('status')})
            checked=coverage.validate(plan=study.parent.plan,amendment=study.amendment,cell_id='desktop-native',owner_slot=owner,
                attempt_id=started['attempt_id'],checkpoint_sha256=checkpoint,selection_tasks=identities,
                paid_calls=calls,related_paid_attempt_ids=set(paid.ids),budget_performance_receipts=budget_receipts)
            result={'schema':'cua-full-study-selection-saved-result-v1','cell_id':'desktop-native','checkpoint_sha256':checkpoint,
                'evaluator_isolated':True,'tasks':rows}
            result_ref=model.write(root/'selection-result.private.json',result)
            ledger_ref=model.write(root/'task-ledger.private.json',{'schema':'cua-native-desktop-selection-performance-ledger-v22',
                'tasks':rows,'paid_attempt_ids':paid.ids,'coverage':checked,'amendment_sha256':study.amendment_sha256})
            return {'status':'scored','result':result,'result_sha256':result_ref['sha256'],'paid_attempt_ids':paid.ids,
                'task_ledger_path':str(root/'task-ledger.private.json'),'task_ledger_sha256':ledger_ref['sha256'],
                'performance_coverage':checked,'actual_cost_usd':None,'invoice_complete':False}
        except BaseException as exc:
            model.write(root/'invalid.private.json',{'status':'infrastructure_invalid_no_score_inference',
                'exception_type':type(exc).__name__,'completed_task_count':len(rows),'paid_attempt_ids':paid.ids,
                'same_intent_replay_authorized':False})
            raise


def admit_shared_base(*,study,worker,session,native_result,usage_reconciler):
    if native_result.get('status')!='scored' or session.study is not study or session.owner!='desktop-native:shared-base':
        raise ValueError('actual_twenty_task_shared_base_result_required')
    refs=session.reconcile_all(usage_reconciler)
    records=study.budget.owner_attempts(session.owner)
    if set(native_result['paid_attempt_ids'])!=set(records):raise ValueError('shared_base_retained_paid_set_changed')
    root=session.directory;native=Path(native_result['task_ledger_path']).parent
    receipt={'schema':'cua-native-desktop-v22-shared-base-performance','plan_sha256':study.plan_sha256,
        'amendment_sha256':study.amendment_sha256,'checkpoint_sha256':session.started['checkpoint_path_sha256'],
        'worker_runtime_sha256':integration.proposal()['worker_runtime_sha256'],
        'admissions_ref':{'path':str(study._desktop_v11_admissions_path),'sha256':digest(study._desktop_v11_admissions_path.read_bytes())},
        'proposal_ref':{'path':str(study._desktop_v11_proposal_path),'sha256':digest(study._desktop_v11_proposal_path.read_bytes())},
        'result_ref':{'path':str((native/'selection-result.private.json').relative_to(root)),'sha256':native_result['result_sha256']},
        'ledger_ref':{'path':str((native/'task-ledger.private.json').relative_to(root)),'sha256':native_result['task_ledger_sha256']},
        'paid_attempt_refs':refs,'paid_attempt_ids':native_result['paid_attempt_ids'],'official_final_tasks_observed':0}
    path=policy_runtime.shared_receipt_path(study,'desktop-native');model.write(path,receipt)
    result,digest_value=verify_shared_receipt(study,study.budget,'desktop-native',path,require_registry=False)
    policy_runtime.campaign._private_write_new(root/'accepted.private.json',integration.canonical({
        'schema':policy_runtime.shared.REGISTRY_SCHEMA,'cell_id':'desktop-native','receipt_sha256':digest_value}))
    return {'task_count':20,'wins':sum(row['score'] for row in result['tasks']),'receipt_sha256':digest_value,
        'actual_cost_usd':None,'invoice_complete':False}


def verify_shared_receipt(study,budget,cell_id,source,*,require_registry=True):
    root=policy_runtime.shared_receipt_path(study,cell_id).parent
    receipt,raw=policy_runtime.private(source,root)
    if receipt.get('schema')!='cua-native-desktop-v22-shared-base-performance' or receipt.get('plan_sha256')!=study.plan_sha256 or receipt.get('amendment_sha256')!=study.amendment_sha256 or receipt.get('official_final_tasks_observed')!=0 or budget.amendment_sha256!=study.amendment_sha256:
        raise ValueError('native_shared_base_policy_binding_changed')
    refs={}
    for key in ('admissions_ref','proposal_ref'):
        reference=receipt[key];value,content=policy_runtime.private(reference['path'],study.repo_root/'work')
        if digest(content)!=reference['sha256']:raise ValueError('qualified_native_model_metadata_changed')
        refs[key]=Path(reference['path'])
    with integration.runtime_context(),policy_runtime.runtime_context(study):
        admitted=integration.bind_frozen_study(study,admissions_path=refs['admissions_ref'],proposal_path=refs['proposal_ref'])
        identities=list(study.task_views(cell_id)['selection'])
        result,_=policy_runtime.shared._json_ref(root,receipt['result_ref']);ledger,_=policy_runtime.shared._json_ref(root,receipt['ledger_ref'])
        if ledger.get('amendment_sha256')!=study.amendment_sha256 or result.get('checkpoint_sha256')!=receipt['checkpoint_sha256'] or result.get('evaluator_isolated') is not True or len(result.get('tasks',[]))!=20:
            raise ValueError('actual_twenty_saved_base_tasks_required')
        worker=model.DesktopProspectiveModelWorker(study=study,admissions_path=refs['admissions_ref'],proposal_path=refs['proposal_ref'])
        packages=worker._packages(admitted,identities,'selection');salt=json.loads(integration.controls.private(Path(admitted['private_map'])))['variant_salt']
        native=(root/receipt['result_ref']['path']).parent
        frames={}
        for package,row in zip(packages,result['tasks']):
            if any(row[k]!=package['identity'][k] for k in ('task_id','package_sha256')):raise ValueError('native_base_task_identity_changed')
            out=native/'gui'/row['task_id']/'evaluator';task=json.loads(integration.controls.private(out/'task.private.json'))
            if any(task[k]!=row[k] for k in row):raise ValueError('native_base_saved_score_changed')
            trace=json.loads(integration.controls.private(out/'actions.private.json'))
            worker._audit_episode(batch=native,out=out,package=package,salt=salt,actions=[r['action'] for r in trace if r.get('status')=='applied'])
            for field,name in [('saved_state_sha256','saved-state.private.json'),('verifier_receipt_sha256','verifier.private.json'),('reset_receipt_sha256','reset.private.json')]:
                if row[field]!=digest(integration.controls.private(out/name)):raise ValueError('native_base_private_saved_reset_hash_changed')
            frames[row['task_id']]={r['sampled_frame']['sha256'] for r in trace}
        records={k:v for k,v in budget.owner_attempts(cell_id+':shared-base').items() if v['category']!='shared_base_final'}
        if set(records)!=set(receipt['paid_attempt_ids']) or len(receipt['paid_attempt_refs'])!=len(records):raise ValueError('all_native_base_paid_intents_required')
        calls=[];stops=[];seen=set();leases={r['task_id']:set() for r in identities}
        for ref in receipt['paid_attempt_refs']:
            identifier=ref['attempt_id']
            if identifier not in records or identifier in seen:raise ValueError('native_base_paid_duplicate_or_missing')
            seen.add(identifier);record=records[identifier]
            request,request_raw=policy_runtime.shared._json_ref(root,ref['request_ref'])
            body,body_raw=policy_runtime.shared._json_ref(root,request['worker_request_ref'])
            if digest(request_raw)!=record['request_sha256'] or body!=json.loads(integration.controls.private(native/'paid'/(identifier+'.request.private.json'))):raise ValueError('native_base_exact_paid_request_changed')
            outcome=None
            if ref['result_ref'] is not None:
                normalized,_=policy_runtime.shared._json_ref(root,ref['result_ref']);outcome,_=policy_runtime.shared._json_ref(root,normalized['worker_result_ref'])
                if outcome!=json.loads(integration.controls.private(native/'paid'/(identifier+'.result.private.json'))):raise ValueError('native_base_actual_provider_response_changed')
            else:
                stop,_=policy_runtime.shared._json_ref(root,ref['budget_performance_ref']);verified=policy_runtime.verify_budget_artifacts(study,'shared-base',stop['verification'])
                if stop['receipt']!=verified or verified['sample_paid_attempt_id']!=identifier or record['status']!='uncertain':raise ValueError('native_base_budget_uncertainty_not_verified')
                stops.append(verified)
            if ref['usage_ref'] is None:
                if record['actual_usd'] is not None or record['status'] not in {'dispatched','uncertain'}:raise ValueError('unknown_native_base_usage_was_settled')
            else:
                usage,usage_raw=policy_runtime.shared._json_ref(root,ref['usage_ref'])
                if record['status']!='settled' or digest(usage_raw)!=record['evidence_sha256'] or usage['actual_usd']!=record['actual_usd']:raise ValueError('native_base_authentic_usage_changed')
                policy_runtime.shared._reference(root,usage['source_ref'])
            task=body.get('task_id')
            if task is not None:
                if task not in frames or body['checkpoint_path_sha256']!=receipt['checkpoint_sha256']:raise ValueError('native_base_paid_task_or_checkpoint_changed')
                if ref['category']=='e2b':
                    if body.get('lease_seconds')!=1200 or body.get('phase') not in ('actor','reset'):raise ValueError('native_base_exact_reset_lease_required')
                    leases[task].add(body['phase'])
                elif body.get('frame_sha256') not in frames[task] or (outcome is not None and outcome.get('status')!='completed'):raise ValueError('native_base_current_frame_or_response_changed')
            calls.append({'attempt_id':identifier,'category':ref['category'],'request':request,'result_present':outcome is not None,'result_status':None if outcome is None else outcome.get('status')})
        if not all(v=={'actor','reset'} for v in leases.values()):raise ValueError('all_actual_distinct_reset_leases_required')
        checked=coverage.validate(plan=study.parent.plan,amendment=study.amendment,cell_id=cell_id,owner_slot='shared-base',
            attempt_id='base-selection-desktop-native',checkpoint_sha256=receipt['checkpoint_sha256'],selection_tasks=identities,
            paid_calls=calls,related_paid_attempt_ids=set(records),budget_performance_receipts=stops)
        if checked!=ledger['coverage']:raise ValueError('native_base_coverage_changed')
    if require_registry:
        marker,_=policy_runtime.private(root/'accepted.private.json',root)
        if marker!={'schema':policy_runtime.shared.REGISTRY_SCHEMA,'cell_id':cell_id,'receipt_sha256':digest(raw)}:raise ValueError('native_base_registry_changed')
    return result,digest(raw)
