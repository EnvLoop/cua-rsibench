"""Fresh Reference8 save controls through unchanged Native14 actors."""
from hashlib import sha256
from pathlib import Path
from enterprise_fallback.odoo18.native_compat_source_loader_v1 import load_source

_impl=load_source('tools/odoo_v066_native_reference_qualification_v3.py',
    'tools._odoo_native_reference_qualification_v8',
    'bf23cd7bf9e9d774cd05f88254a2c01a2401f65d882bba8945899998b3fd575a',
    (('v13','v14',4),('v3','v8',5)))
_run=_impl.run
_finalize_train=_impl.finalize_train_control

def _reference8_train(path,expected_sha256,reference):
    path=Path(path)
    control=_impl.workers.validate_train_control(_impl.workers.private_json(path,expected_sha256),
        _impl.workers.public_binding())
    proof=_impl.workers.private_json(path.parent/'reference8-train-provenance.private.json')
    _impl.workers.require(proof.get('schema')=='odoo-reference8-fresh-train-provenance-v1' and
        proof.get('train_control_sha256')==expected_sha256 and
        proof.get('native_binding_sha256')==control['native_worker_binding_sha256'] and
        proof.get('reference_binding_sha256')==reference['reference_binding_sha256'] and
        proof.get('old_reference_credit')==0,'Fresh Reference8 TRAIN provenance required')
    saved=proof['reference_run_result_ref']
    result=_impl.workers.private_json(saved['path'],saved['sha256'])
    _impl.workers.require(result.get('schema')=='odoo-native-reference-run-result-v8' and
        result.get('reference_binding_sha256')==reference['reference_binding_sha256'] and
        result.get('formal_registration_performed') is False and result.get('old_reference_control_credit')==0 and
        result['native_core_result']['split']=='train','Actual Reference8 TRAIN run required')
    candidate=_impl.workers.private_json(path.parent/'train-control-candidate.private.json',
        result['native_core_result']['train_candidate_sha256'])
    _impl.workers.require(all(candidate[key]==control[key] for key in
        ('run_nonce_sha256','plan_sha256','attempt_sha256','audit_sha256','task_id','package_sha256')),
        'Reference8 TRAIN result and finalized control differ')
    source=proof['source_review_ref']
    _impl.workers.private_json(source['path'],source['sha256'])
    _impl.workers.require(source['sha256']==control['source_review_sha256'],
        'Reference8 TRAIN source review differs')
    _impl.workers.require(candidate['family']=='crm',
        'Fresh original public CRM TRAIN required to exercise installed priority widget')
    priority=proof['priority_autosave_provenance_ref']
    actual=_impl.workers.private_json(priority['path'],priority['sha256'])
    _impl.workers.require(actual['v8_priority_autosave_zero_input_provenance_verified'] is True and
        actual['reference_priority_autosave_wait_count']>=1,
        'Actual original public CRM priority autosave proof required')
    return proof

def run(*,plan_path,worker_dir,run_dir,execute=False,train_task_id=None,
        train_control_path=None,train_control_sha256=None):
    _impl.workers.require(execute is True,'Explicit fresh Reference8 execution required')
    plan=_impl.validate_plan(_impl.workers.private_json(plan_path))
    if plan['native_core_plan']['split']=='train':
        original_crm=next(row for row in plan['native_core_plan']['tasks'] if row['family']=='crm')
        _impl.workers.require(train_task_id==original_crm['task_id'],
            'Explicit original first public CRM TRAIN task required')
    if plan['native_core_plan']['split']!='train':
        _impl.workers.require(train_control_path is not None and type(train_control_sha256) is str,
            'Fresh Reference8 TRAIN required before full split')
        _reference8_train(train_control_path,train_control_sha256,plan['reference_binding'])
    return _run(plan_path=plan_path,worker_dir=worker_dir,run_dir=run_dir,execute=execute,
        train_task_id=train_task_id,train_control_path=train_control_path,train_control_sha256=train_control_sha256)

def finalize_train_control(*,plan_path,worker_dir,run_dir,source_review_path,source_review_sha256):
    from enterprise_fallback.odoo18 import native_reference_split_finalizer_v8 as saved_finalizer
    plan=_impl.validate_plan(_impl.workers.private_json(plan_path));core=plan['native_core_plan']
    attempt=Path(run_dir)/'attempt-000'
    receipt=_impl.workers.private_json(attempt/'attempt.private.json')
    audit=_impl.workers.private_json(attempt/'independent-audit.private.json')
    _impl.workers.require(receipt['family']=='crm' and receipt['task_id']==next(
        row['task_id'] for row in core['tasks'] if row['family']=='crm'),
        'Actual original first public CRM TRAIN required')
    autosave=saved_finalizer._v8_action_provenance(saved_finalizer.SavedReader(),attempt,receipt,audit,
        plan['reference_binding'])
    result=_finalize_train(plan_path=plan_path,worker_dir=worker_dir,run_dir=run_dir,
        source_review_path=source_review_path,source_review_sha256=source_review_sha256)
    plan=_impl.validate_plan(_impl.workers.private_json(plan_path));core=plan['native_core_plan']
    _impl.workers.require(core['split']=='train','Only genuine Reference8 TRAIN can supply prerequisite')
    path=Path(run_dir)/'train-control.private.json';control=_impl.workers.private_json(path)
    _impl.workers.validate_train_control(control,core['native_worker_binding'])
    _impl.workers.require(control['family']=='crm',
        'Only actual original public CRM TRAIN can qualify Reference8')
    saved=Path(plan_path).parent/(core['run_nonce_hex']+'-reference-result.private.json')
    value=_impl.workers.private_json(saved)
    _impl.workers.require(value['schema']=='odoo-native-reference-run-result-v8' and
        value['reference_binding_sha256']==plan['reference_binding']['reference_binding_sha256'],
        'Current actual Reference8 run result required')
    autosave_path=Path(run_dir)/'reference8-priority-autosave-train-provenance.private.json'
    _impl.core._write_new(autosave_path,autosave)
    proof={'schema':'odoo-reference8-fresh-train-provenance-v1',
        'train_control_sha256':sha256(path.read_bytes()).hexdigest(),
        'native_binding_sha256':core['native_worker_binding_sha256'],
        'reference_binding_sha256':plan['reference_binding']['reference_binding_sha256'],
        'reference_run_result_ref':{'path':str(saved.resolve()),'sha256':sha256(saved.read_bytes()).hexdigest()},
        'source_review_ref':{'path':str(Path(source_review_path).resolve()),'sha256':source_review_sha256},
        'priority_autosave_provenance_ref':{'path':str(autosave_path.resolve()),
            'sha256':sha256(autosave_path.read_bytes()).hexdigest()},
        'old_reference_credit':0,'formal_admissions':0,'model_calls':0}
    _impl.core._write_new(Path(run_dir)/'reference8-train-provenance.private.json',proof)
    return result

def boundary_review_contract(*,plan_path,worker_dir,run_dir,train_control_path,train_control_sha256):
    """Metadata-only authority for the existing failed CRM case; no new roster."""
    plan=_impl.validate_plan(_impl.workers.private_json(plan_path));core=plan['native_core_plan']
    _impl.workers.require(core['split']=='official_hidden' and len(core['tasks'])==100,
        'Original full100 metadata required for bounded CRM regression')
    ordinal=77
    _impl.workers.require(core['tasks'][ordinal]['family']=='crm',
        'Original failed CRM ordinal77 must remain unchanged')
    _reference8_train(train_control_path,train_control_sha256,plan['reference_binding'])
    return {'schema':'odoo-reference8-original-failed-crm-boundary-root-review-v1',
        'plan_ref':{'path':str(Path(plan_path).resolve()),'sha256':sha256(Path(plan_path).read_bytes()).hexdigest()},
        'native_binding_sha256':core['native_worker_binding_sha256'],
        'reference_binding_sha256':plan['reference_binding']['reference_binding_sha256'],
        'original_ordinal':ordinal,'original_case_identity':core['tasks'][ordinal],
        'original_worker_dir':str(Path(worker_dir).resolve()),'fresh_run_dir':str(Path(run_dir).resolve()),
        'train_control_ref':{'path':str(Path(train_control_path).resolve()),'sha256':train_control_sha256},
        'whole_original_case_0_1_0_regression_authorized':True,'negative_only_or_partial_skip_authorized':False,
        'task_roster_mutation_authorized':False,'original_full100_intent_consumption_authorized':False,
        'formal_or_full100_control_credit_authorized':False,'same_failed_case_replay_authorized':False,
        'automatic_restart_authorized':False,'model_calls_authorized':False}

def run_boundary(*,plan_path,worker_dir,run_dir,train_control_path,train_control_sha256,
        root_review_path,root_review_sha256,execute=False):
    """One separately reviewed whole-task diagnostic under unchanged Native14."""
    _impl.workers.require(execute is True,'Exact bounded original CRM regression execution required')
    contract=boundary_review_contract(plan_path=plan_path,worker_dir=worker_dir,run_dir=run_dir,
        train_control_path=train_control_path,train_control_sha256=train_control_sha256)
    _impl.workers.require(_impl.workers.private_json(root_review_path,root_review_sha256)==contract,
        'Exact independent original CRM regression review required')
    plan=_impl.validate_plan(_impl.workers.private_json(plan_path));core=plan['native_core_plan']
    worker=Path(worker_dir).resolve();run=Path(run_dir).resolve()
    _impl.workers.require(run.parent==worker/'private/v066_reference8_boundary_controls' and
        not run.exists() and not run.is_symlink(),'Fresh separately owned boundary namespace required')
    facade=_impl._facade(plan['reference_binding']);world,private=facade._live_preflight(core,worker)
    from tools import odoo_v066_scale_controller_v1 as controller
    modules=controller._modules(worker);lease=modules[-1]
    run.parent.mkdir(mode=0o700,exist_ok=True)
    _impl.core._write_new(run.parent/('review-'+root_review_sha256+'-consumed.private.json'),
        {'review_sha256':root_review_sha256,'automatic_restarts':0,'full100_credit':0,'model_calls':0})
    run.mkdir(mode=0o700)
    _impl.core._write_new(run/'boundary-intent.private.json',contract)
    ordinal=contract['original_ordinal'];metadata=core['tasks'][ordinal];family=metadata['family']
    case=next(row for row in world['cases'][family] if row['id']==metadata['task_id'])
    wrong=next(row for row in world['cases'][family] if row['id']!=case['id'])
    row=facade._case_row(core,metadata,train_control_sha256)
    runner=_impl.reference.candidate_module(core['native_worker_binding'],plan['reference_binding'])
    try:
        with lease.exclusive_worker_operation(controller.LEASE_OPERATION):
            runner.execute_case(run_dir=run,ordinal=0,row=row,case=case,wrong=wrong,family=family,modules=modules)
        attempt=run/'attempt-000'
        audit=facade.audit_case(plan=core,row=row,attempt=attempt,worker_private=private)
        _impl.core._write_new(attempt/'independent-audit.private.json',audit)
        value={'schema':'odoo-reference8-original-failed-crm-boundary-result-v1','status':'actual_whole_case_saved_audit_verified',
            'original_ordinal':ordinal,'native_binding_sha256':core['native_worker_binding_sha256'],
            'reference_binding_sha256':plan['reference_binding']['reference_binding_sha256'],
            'scores':[audit['independent_baseline_reward'],audit['independent_positive_reward'],audit['independent_wrong_object_reward']],
            'reset_exact':audit['full_pre_web_filestore_reset_exact'],'services_restored':audit['original_services_restored'],
            'audit_sha256':sha256((attempt/'independent-audit.private.json').read_bytes()).hexdigest(),
            'original_full100_intent_consumed':False,'formal_admissions':0,'full100_control_credit':0,'model_calls':0}
        _impl.core._write_new(run/'boundary-result.private.json',value)
        return value
    except BaseException as error:
        _impl.core._write_new(run/'boundary-failure.private.json',{'status':'terminal_preserve_original_boundary_no_retry',
            'error_type':type(error).__name__,'original_full100_intent_consumed':False,'formal_admissions':0,
            'full100_control_credit':0,'model_calls':0})
        raise

_impl.run=run
_impl.finalize_train_control=finalize_train_control

def __getattr__(name):return getattr(_impl,name)
if __name__=='__main__':_impl.main()
