"""Qualification-only CRM calibration for the unchanged Reference8 UI.

Native14's canonical TRAIN remains purchase. A CRM calibration is separately
reviewed whole-case evidence, never relabeled as a Native14 TRAIN control.
"""
from hashlib import sha256
from pathlib import Path
from enterprise_fallback.odoo18.native_compat_source_loader_v1 import load_source
from enterprise_fallback.odoo18 import native_reference_viewport_v8 as ui
from enterprise_fallback.odoo18.native_reference_save_v7 import POLICY as SAVE_POLICY
from enterprise_fallback.odoo18.native_reference_autosave_v8 import POLICY as AUTOSAVE_POLICY
from enterprise_fallback.odoo18 import native_reference_split_finalizer_v8 as saved_finalizer

reference=load_source('enterprise_fallback/odoo18/native_reference_viewport_v3.py',
    'enterprise_fallback.odoo18._reference8_ui_qualification9_scope',
    'f3f1ecd1096af2ca1005beefc0132c0fefe8402ffdb1c8d1095864ffe69cd755',(
        ('native_surface_workers_v13','native_surface_workers_v14',1),
        ('odoo-native-viewport-reference-source-v3','odoo-native-viewport-reference-source-v8',1),
        ('same_v13_adapter_actor_scorer_reset','same_v14_adapter_actor_scorer_reset',1),
        ('viewport-reference-v3','viewport-reference-v8',1),('viewport-case-v3','viewport-case-v8',1),
        ('from tools import odoo_v066_scale_recipes_v5 as recipes','from tools import odoo_v066_scale_recipes_v9 as recipes',1)))
reference.REFERENCE_FILES=(*ui._impl.REFERENCE_FILES,
    'tools/odoo_v066_native_reference_qualification_v9.py',
    'tests/test_odoo_native_reference_qualification_v9.py')
_base_binding=reference.reference_binding


def reference_binding():
    value=_base_binding();value.pop('reference_binding_sha256')
    value.update(native_save_policy=SAVE_POLICY,priority_autosave_wait_policy=AUTOSAVE_POLICY,
        unchanged_reference7_save_helper_used=True,dirty_native_save_click_required=True,
        ui_reference8_ancestor_binding_sha256=ui.reference_binding()['reference_binding_sha256'],
        qualifier_revision='reference8-ui-qualification9',canonical_native14_train_family='purchase',
        separate_original_public_crm_calibration_required=True,
        original_failed_crm77_boundary_required=True,old_reference_control_credit=0,
        prior_reference7_control_credit=0,prior_reference8_control_credit=0)
    return {**value,'reference_binding_sha256':reference.core.digest(reference.core.canonical(value))}


reference.reference_binding=reference_binding
_impl=load_source('tools/odoo_v066_native_reference_qualification_v3.py',
    'tools._odoo_reference8_qualification9',
    'bf23cd7bf9e9d774cd05f88254a2c01a2401f65d882bba8945899998b3fd575a',
    (('v13','v14',4),('v3','v8',5)))
_impl.reference=reference
_run=_impl.run
_finalize_train=_impl.finalize_train_control


def _ref(path):
    path=Path(path).resolve()
    return {'path':str(path),'sha256':sha256(path.read_bytes()).hexdigest()}


def _checked_case_source_proof(path,expected,reference_binding,kind):
    proof=_impl.workers.private_json(path,expected)
    _impl.workers.require(proof['schema']=='odoo-reference8-qualification9-case-source-qualified-v1' and
        proof['kind']==kind and proof['reference_binding_sha256']==reference_binding['reference_binding_sha256'] and
        proof['formal_admissions']==proof['canonical_native14_train_control_credit']==0,
        'Actual qualification9 separate CRM source proof required')
    result=_impl.workers.private_json(proof['actual_case_result_ref']['path'],proof['actual_case_result_ref']['sha256'])
    _impl.workers.require(result['scores']==[0,1,0] and result['reset_exact'] is True and
        result['services_restored'] is True and result['kind']==kind and
        result['reference_binding_sha256']==reference_binding['reference_binding_sha256'],
        'Actual qualification9 whole CRM control result required')
    _impl.workers.private_json(proof['independent_source_review_ref']['path'],
        proof['independent_source_review_ref']['sha256'])
    plan=_impl.validate_plan(_impl.workers.private_json(proof['plan_ref']['path'],proof['plan_ref']['sha256']))
    core=plan['native_core_plan'];run=Path(proof['run_dir']);worker=Path(proof['worker_dir'])
    _impl.workers.require(plan['reference_binding']==reference_binding,
        'Separate CRM proof actual source binding changed')
    expected_ordinal=(next(index for index,row in enumerate(core['tasks']) if row['family']=='crm')
        if kind=='original_public_crm_calibration' else 77)
    _impl.workers.require(result['original_ordinal']==expected_ordinal and
        core['tasks'][expected_ordinal]['family']=='crm' and
        core['split']==('train' if kind=='original_public_crm_calibration' else 'official_hidden') and
        result['native_binding_sha256']==core['native_worker_binding_sha256'],
        'Separate CRM proof original identity or native binding changed')
    declared=case_review_contract(plan_path=proof['plan_ref']['path'],worker_dir=worker,run_dir=run,kind=kind)
    _impl.workers.require(_impl.workers.private_json(run/'case-intent.private.json')==declared,
        'Separate CRM original whole-case declaration changed')
    metadata=core['tasks'][result['original_ordinal']]
    facade=_impl._facade(plan['reference_binding'])
    saved=_impl.workers.private_json(run/'attempt-000/independent-audit.private.json')
    actual=facade.audit_case(plan=core,row=facade._case_row(core,metadata,None),
        attempt=run/'attempt-000',worker_private=worker/'private')
    _impl.workers.require(actual==saved and _ref(run/'case-result.private.json')==proof['actual_case_result_ref'],
        'Separate CRM saved production audit or result changed')
    review=case_source_review_contract(plan_path=proof['plan_ref']['path'],worker_dir=worker,run_dir=run,kind=kind)
    _impl.workers.require(_impl.workers.private_json(proof['independent_source_review_ref']['path'],
        proof['independent_source_review_ref']['sha256'])==review,
        'Separate CRM source approval no longer matches exact current case')
    receipt=_impl.workers.private_json(run/'attempt-000/attempt.private.json')
    provenance=saved_finalizer._v8_action_provenance(saved_finalizer.SavedReader(),
        run/'attempt-000',receipt,actual,reference_binding)
    _impl.workers.require(_ref(run/'attempt-000/priority-autosave-provenance.private.json')==
        result['priority_autosave_provenance_ref'] and
        _impl.workers.private_json(result['priority_autosave_provenance_ref']['path'],
            result['priority_autosave_provenance_ref']['sha256'])==provenance and
        _ref(run/'attempt-000/independent-audit.private.json')==result['audit_ref'],
        'Separate CRM autosave provenance or audit ref changed')
    return proof


def _purchase_train(path,expected,reference_binding):
    control=_impl.workers.validate_train_control(_impl.workers.private_json(path,expected),
        _impl.workers.public_binding())
    proof=_impl.workers.private_json(Path(path).parent/'reference8-qualification9-purchase-train-provenance.private.json')
    _impl.workers.require(control['family']=='purchase' and proof['train_control_sha256']==expected and
        proof['reference_binding_sha256']==reference_binding['reference_binding_sha256'] and
        proof['old_control_credit']==0,'Fresh canonical purchase TRAIN for qualification9 required')
    result=_impl.workers.private_json(proof['reference_run_result_ref']['path'],
        proof['reference_run_result_ref']['sha256'])
    _impl.workers.require(result['schema']=='odoo-native-reference-run-result-v8' and
        result['reference_binding_sha256']==reference_binding['reference_binding_sha256'] and
        result['native_core_result']['split']=='train','Actual qualification9 purchase TRAIN result required')
    return proof


def run(*,plan_path,worker_dir,run_dir,execute=False,train_task_id=None,
        train_control_path=None,train_control_sha256=None,crm_calibration_path=None,
        crm_calibration_sha256=None,crm_boundary_path=None,crm_boundary_sha256=None):
    _impl.workers.require(execute is True,'Explicit reviewed qualification9 execution required')
    plan=_impl.validate_plan(_impl.workers.private_json(plan_path))
    if plan['native_core_plan']['split']!='train':
        _purchase_train(train_control_path,train_control_sha256,plan['reference_binding'])
        _checked_case_source_proof(crm_calibration_path,crm_calibration_sha256,
            plan['reference_binding'],'original_public_crm_calibration')
        _checked_case_source_proof(crm_boundary_path,crm_boundary_sha256,
            plan['reference_binding'],'original_failed_crm77_boundary')
        nonce=plan['native_core_plan']['run_nonce_hex']
        _impl.core._write_new(Path(plan_path).parent/(nonce+'-qualification9-prerequisites.private.json'),
            {'schema':'odoo-reference8-qualification9-fullsplit-prerequisites-v1',
                'plan_ref':_ref(plan_path),'purchase_train_ref':{'path':str(Path(train_control_path).resolve()),
                    'sha256':train_control_sha256},
                'crm_calibration_ref':{'path':str(Path(crm_calibration_path).resolve()),'sha256':crm_calibration_sha256},
                'crm_boundary_ref':{'path':str(Path(crm_boundary_path).resolve()),'sha256':crm_boundary_sha256},
                'old_control_credit':0,'model_calls':0})
    return _run(plan_path=plan_path,worker_dir=worker_dir,run_dir=run_dir,execute=execute,
        train_task_id=train_task_id,train_control_path=train_control_path,train_control_sha256=train_control_sha256)


def finalize_train_control(*,plan_path,worker_dir,run_dir,source_review_path,source_review_sha256):
    result=_finalize_train(plan_path=plan_path,worker_dir=worker_dir,run_dir=run_dir,
        source_review_path=source_review_path,source_review_sha256=source_review_sha256)
    plan=_impl.validate_plan(_impl.workers.private_json(plan_path));core=plan['native_core_plan']
    control=Path(run_dir)/'train-control.private.json'
    actual=_impl.workers.validate_train_control(_impl.workers.private_json(control),core['native_worker_binding'])
    _impl.workers.require(actual['family']=='purchase','Canonical Native14 TRAIN remains purchase')
    saved=Path(plan_path).parent/(core['run_nonce_hex']+'-reference-result.private.json')
    proof={'schema':'odoo-reference8-qualification9-purchase-train-provenance-v1',
        'train_control_sha256':_ref(control)['sha256'],
        'reference_binding_sha256':plan['reference_binding']['reference_binding_sha256'],
        'reference_run_result_ref':_ref(saved),'source_review_ref':{'path':str(Path(source_review_path).resolve()),
            'sha256':source_review_sha256},'old_control_credit':0,'formal_admissions':0}
    _impl.core._write_new(Path(run_dir)/'reference8-qualification9-purchase-train-provenance.private.json',proof)
    return result


def case_review_contract(*,plan_path,worker_dir,run_dir,kind):
    plan=_impl.validate_plan(_impl.workers.private_json(plan_path));core=plan['native_core_plan']
    if kind=='original_public_crm_calibration':
        _impl.workers.require(core['split']=='train' and len(core['tasks'])==20,'Original public20 metadata required')
        ordinal=next(index for index,row in enumerate(core['tasks']) if row['family']=='crm')
    else:
        _impl.workers.require(kind=='original_failed_crm77_boundary' and core['split']=='official_hidden' and
            len(core['tasks'])==100 and core['tasks'][77]['family']=='crm','Original100 failed CRM77 metadata required')
        ordinal=77
    return {'schema':'odoo-reference8-qualification9-separate-case-root-review-v1','kind':kind,
        'plan_ref':_ref(plan_path),'reference_binding_sha256':plan['reference_binding']['reference_binding_sha256'],
        'native_binding_sha256':core['native_worker_binding_sha256'],'original_ordinal':ordinal,
        'original_case_identity':core['tasks'][ordinal],'original_worker_dir':str(Path(worker_dir).resolve()),
        'fresh_run_dir':str(Path(run_dir).resolve()),'whole_original_case_0_1_0_only':True,
        'canonical_native14_train_control_credit':0,'full100_control_credit':0,'formal_admissions':0,
        'original_full100_or_purchase_train_intent_consumption_authorized':False,
        'old_control_promotion_authorized':False,'automatic_restart_authorized':False,'model_calls_authorized':False}


def run_case(*,plan_path,worker_dir,run_dir,kind,root_review_path,root_review_sha256,
        execute=False,crm_calibration_path=None,crm_calibration_sha256=None):
    _impl.workers.require(execute is True,'Exact separate whole CRM control execution required')
    contract=case_review_contract(plan_path=plan_path,worker_dir=worker_dir,run_dir=run_dir,kind=kind)
    _impl.workers.require(_impl.workers.private_json(root_review_path,root_review_sha256)==contract,
        'Exact separate whole CRM root review required')
    plan=_impl.validate_plan(_impl.workers.private_json(plan_path));core=plan['native_core_plan']
    if kind=='original_failed_crm77_boundary':
        _checked_case_source_proof(crm_calibration_path,crm_calibration_sha256,
            plan['reference_binding'],'original_public_crm_calibration')
    worker=Path(worker_dir).resolve();run=Path(run_dir).resolve()
    _impl.workers.require(run.parent==worker/'private/v066_reference8_qualification9_case_controls' and
        not run.exists() and not run.is_symlink(),'Fresh separately owned qualification9 case namespace required')
    facade=_impl._facade(plan['reference_binding']);world,private=facade._live_preflight(core,worker)
    from tools import odoo_v066_scale_controller_v1 as controller
    modules=controller._modules(worker);lease=modules[-1]
    run.parent.mkdir(mode=0o700,exist_ok=True)
    _impl.core._write_new(run.parent/('review-'+root_review_sha256+'-consumed.private.json'),
        {'review_sha256':root_review_sha256,'model_calls':0,'automatic_restarts':0})
    run.mkdir(mode=0o700);_impl.core._write_new(run/'case-intent.private.json',contract)
    metadata=core['tasks'][contract['original_ordinal']];family=metadata['family']
    case=next(row for row in world['cases'][family] if row['id']==metadata['task_id'])
    wrong=next(row for row in world['cases'][family] if row['id']!=case['id'])
    row=facade._case_row(core,metadata,None)
    runner=reference.candidate_module(core['native_worker_binding'],plan['reference_binding'])
    try:
        with lease.exclusive_worker_operation(controller.LEASE_OPERATION):
            runner.execute_case(run_dir=run,ordinal=0,row=row,case=case,wrong=wrong,family=family,modules=modules)
        attempt=run/'attempt-000';audit=facade.audit_case(plan=core,row=row,attempt=attempt,worker_private=private)
        _impl.core._write_new(attempt/'independent-audit.private.json',audit)
        receipt=_impl.workers.private_json(attempt/'attempt.private.json')
        provenance=saved_finalizer._v8_action_provenance(saved_finalizer.SavedReader(),attempt,receipt,audit,
            plan['reference_binding'])
        _impl.core._write_new(attempt/'priority-autosave-provenance.private.json',provenance)
        value={'schema':'odoo-reference8-qualification9-whole-crm-case-result-v1','kind':kind,
            'reference_binding_sha256':plan['reference_binding']['reference_binding_sha256'],
            'native_binding_sha256':core['native_worker_binding_sha256'],'original_ordinal':contract['original_ordinal'],
            'scores':[audit['independent_baseline_reward'],audit['independent_positive_reward'],audit['independent_wrong_object_reward']],
            'reset_exact':audit['full_pre_web_filestore_reset_exact'],'services_restored':audit['original_services_restored'],
            'original_full100_or_purchase_intent_consumed':False,'canonical_native14_train_control_credit':0,
            'full100_control_credit':0,'formal_admissions':0,'model_calls':0,
            'audit_ref':_ref(attempt/'independent-audit.private.json'),
            'priority_autosave_provenance_ref':_ref(attempt/'priority-autosave-provenance.private.json')}
        _impl.core._write_new(run/'case-result.private.json',value)
        return value
    except BaseException as error:
        _impl.core._write_new(run/'case-failure.private.json',{'status':'terminal_preserved_no_retry',
            'kind':kind,'error_type':type(error).__name__,'model_calls':0,'formal_admissions':0})
        raise


def case_source_review_contract(*,plan_path,worker_dir,run_dir,kind):
    plan=_impl.validate_plan(_impl.workers.private_json(plan_path));core=plan['native_core_plan']
    run=Path(run_dir).resolve();result=_impl.workers.private_json(run/'case-result.private.json')
    _impl.workers.require(result['kind']==kind and result['reference_binding_sha256']==
        plan['reference_binding']['reference_binding_sha256'] and result['scores']==[0,1,0] and
        result['reset_exact'] is True and result['services_restored'] is True,
        'Genuine whole CRM calibration or boundary result required before source review')
    metadata=core['tasks'][result['original_ordinal']];attempt=run/'attempt-000'
    receipt=_impl.workers.private_json(attempt/'attempt.private.json')
    frame=_impl.workers.private_ref_bytes(attempt,receipt['refs']['source_frame'])
    from enterprise_fallback.odoo18 import partition_factory
    worker=Path(worker_dir).resolve();world=_impl.workers.private_json(worker/'private/partition_cases.json')
    case=next(case for cases in world['cases'].values() for case in cases if case['id']==metadata['task_id'])
    asset=partition_factory.source_asset(case,world)
    _impl.workers.require(sha256(asset).hexdigest()==metadata['source_asset_sha256'] and
        receipt['task_id']==metadata['task_id'] and receipt['package_sha256']==metadata['package_sha256'],
        'Original CRM source and actual case identity changed')
    return {'schema':'odoo-reference8-qualification9-case-source-root-review-v1','kind':kind,
        'plan_ref':_ref(plan_path),'actual_case_result_ref':_ref(run/'case-result.private.json'),
        'reference_binding_sha256':plan['reference_binding']['reference_binding_sha256'],
        'native_binding_sha256':core['native_worker_binding_sha256'],'original_case_identity':metadata,
        'actual_frame_sha256':sha256(frame).hexdigest(),'exact_source_asset_sha256':sha256(asset).hexdigest(),
        'reviewer_independent_of_actor':True,'source_attachment_readable':True,'source_matches_package':True,
        'canonical_native14_train_control_credit':0,'formal_admissions':0}


def finalize_case_source(*,plan_path,worker_dir,run_dir,kind,source_review_path,source_review_sha256):
    contract=case_source_review_contract(plan_path=plan_path,worker_dir=worker_dir,run_dir=run_dir,kind=kind)
    _impl.workers.require(_impl.workers.private_json(source_review_path,source_review_sha256)==contract,
        'Exact independent current CRM native source review required')
    run=Path(run_dir).resolve()
    value={'schema':'odoo-reference8-qualification9-case-source-qualified-v1','kind':kind,
        'plan_ref':_ref(plan_path),'run_dir':str(run),'worker_dir':str(Path(worker_dir).resolve()),
        'actual_case_result_ref':_ref(run/'case-result.private.json'),
        'reference_binding_sha256':contract['reference_binding_sha256'],
        'independent_source_review_ref':{'path':str(Path(source_review_path).resolve()),'sha256':source_review_sha256},
        'canonical_native14_train_control_credit':0,'full100_control_credit':0,'formal_admissions':0}
    _impl.core._write_new(run/'case-source-qualified.private.json',value)
    return value


def finalize_full_split(*,plan_path,worker_dir,run_dir,source_review_path,source_review_sha256,output_path):
    """Exact saved Source8 finalizer in isolated qualification9 globals."""
    from types import ModuleType,FunctionType
    plan=_impl.validate_plan(_impl.workers.private_json(plan_path));core=plan['native_core_plan']
    prerequisite=_impl.workers.private_json(Path(plan_path).parent/
        (core['run_nonce_hex']+'-qualification9-prerequisites.private.json'))
    _impl.workers.require(prerequisite['plan_ref']==_ref(plan_path) and prerequisite['old_control_credit']==0,
        'Exact qualification9 fullsplit prerequisite receipt required')
    train=prerequisite['purchase_train_ref'];cal=prerequisite['crm_calibration_ref'];bound=prerequisite['crm_boundary_ref']
    _purchase_train(train['path'],train['sha256'],plan['reference_binding'])
    _checked_case_source_proof(cal['path'],cal['sha256'],plan['reference_binding'],'original_public_crm_calibration')
    _checked_case_source_proof(bound['path'],bound['sha256'],plan['reference_binding'],'original_failed_crm77_boundary')
    source=saved_finalizer._impl;scope=ModuleType('tools._reference8_saved_qualification9')
    scope.__dict__.update(vars(source));scope.qualification=_impl;scope.__file__=__file__
    for name,value in list(vars(source).items()):
        if isinstance(value,FunctionType) and value.__globals__ is vars(source):
            clone=FunctionType(value.__code__,vars(scope),value.__name__,value.__defaults__,value.__closure__)
            clone.__kwdefaults__=value.__kwdefaults__;clone.__annotations__=value.__annotations__;setattr(scope,name,clone)
    scope._v8_action_provenance=saved_finalizer._v8_action_provenance
    return scope.finalize(plan_path=plan_path,worker_dir=worker_dir,run_dir=run_dir,
        source_review_path=source_review_path,source_review_sha256=source_review_sha256,output_path=output_path)


_impl.run=run
_impl.finalize_train_control=finalize_train_control
def __getattr__(name):return getattr(_impl,name)


def main():
    import argparse,json,sys
    if len(sys.argv)<2 or sys.argv[1] not in ('run','calibrate-crm','crm-boundary'):
        return _impl.main()
    command=sys.argv[1]
    parser=argparse.ArgumentParser(description='Reference8 UI / qualification9: canonical purchase plus separately reviewed CRM evidence')
    for name in ('plan','worker-dir','run-dir'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--execute',action='store_true')
    if command=='run':
        parser.add_argument('--train-task-id')
        for name in ('train-control','crm-calibration-path','crm-boundary-path'):parser.add_argument('--'+name,type=Path)
        for name in ('train-control-sha256','crm-calibration-sha256','crm-boundary-sha256'):parser.add_argument('--'+name)
    else:
        parser.add_argument('--root-review',type=Path,required=True)
        parser.add_argument('--root-review-sha256',required=True)
        if command=='crm-boundary':
            parser.add_argument('--crm-calibration-path',type=Path,required=True)
            parser.add_argument('--crm-calibration-sha256',required=True)
    args=vars(parser.parse_args(sys.argv[2:]));args['plan_path']=args.pop('plan')
    if command=='run':
        args['train_control_path']=args.pop('train_control');result=run(**args)
    else:
        args['root_review_path']=args.pop('root_review')
        args['kind']='original_public_crm_calibration' if command=='calibrate-crm' else 'original_failed_crm77_boundary'
        result=run_case(**args)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
