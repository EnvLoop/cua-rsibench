"""Fresh Reference6 save controls through unchanged Native14 actors."""
from hashlib import sha256
from pathlib import Path
from enterprise_fallback.odoo18.native_compat_source_loader_v1 import load_source

_impl=load_source('tools/odoo_v066_native_reference_qualification_v3.py',
    'tools._odoo_native_reference_qualification_v6',
    'bf23cd7bf9e9d774cd05f88254a2c01a2401f65d882bba8945899998b3fd575a',
    (('v13','v14',4),('v3','v6',5)))
_run=_impl.run
_finalize_train=_impl.finalize_train_control

def _reference6_train(path,expected_sha256,reference):
    path=Path(path)
    control=_impl.workers.validate_train_control(_impl.workers.private_json(path,expected_sha256),
        _impl.workers.public_binding())
    proof=_impl.workers.private_json(path.parent/'reference6-train-provenance.private.json')
    _impl.workers.require(proof.get('schema')=='odoo-reference6-fresh-train-provenance-v1' and
        proof.get('train_control_sha256')==expected_sha256 and
        proof.get('native_binding_sha256')==control['native_worker_binding_sha256'] and
        proof.get('reference_binding_sha256')==reference['reference_binding_sha256'] and
        proof.get('old_reference_credit')==0,'Fresh Reference6 TRAIN provenance required')
    saved=proof['reference_run_result_ref']
    result=_impl.workers.private_json(saved['path'],saved['sha256'])
    _impl.workers.require(result.get('schema')=='odoo-native-reference-run-result-v6' and
        result.get('reference_binding_sha256')==reference['reference_binding_sha256'] and
        result.get('formal_registration_performed') is False and result.get('old_reference_control_credit')==0 and
        result['native_core_result']['split']=='train','Actual Reference6 TRAIN run required')
    candidate=_impl.workers.private_json(path.parent/'train-control-candidate.private.json',
        result['native_core_result']['train_candidate_sha256'])
    _impl.workers.require(all(candidate[key]==control[key] for key in
        ('run_nonce_sha256','plan_sha256','attempt_sha256','audit_sha256','task_id','package_sha256')),
        'Reference6 TRAIN result and finalized control differ')
    source=proof['source_review_ref']
    _impl.workers.private_json(source['path'],source['sha256'])
    _impl.workers.require(source['sha256']==control['source_review_sha256'],
        'Reference6 TRAIN source review differs')
    return proof

def run(*,plan_path,worker_dir,run_dir,execute=False,train_task_id=None,
        train_control_path=None,train_control_sha256=None):
    _impl.workers.require(execute is True,'Explicit fresh Reference6 execution required')
    plan=_impl.validate_plan(_impl.workers.private_json(plan_path))
    if plan['native_core_plan']['split']!='train':
        _impl.workers.require(train_control_path is not None and type(train_control_sha256) is str,
            'Fresh Reference6 TRAIN required before full split')
        _reference6_train(train_control_path,train_control_sha256,plan['reference_binding'])
    return _run(plan_path=plan_path,worker_dir=worker_dir,run_dir=run_dir,execute=execute,
        train_task_id=train_task_id,train_control_path=train_control_path,train_control_sha256=train_control_sha256)

def finalize_train_control(*,plan_path,worker_dir,run_dir,source_review_path,source_review_sha256):
    result=_finalize_train(plan_path=plan_path,worker_dir=worker_dir,run_dir=run_dir,
        source_review_path=source_review_path,source_review_sha256=source_review_sha256)
    plan=_impl.validate_plan(_impl.workers.private_json(plan_path));core=plan['native_core_plan']
    _impl.workers.require(core['split']=='train','Only genuine Reference6 TRAIN can supply prerequisite')
    path=Path(run_dir)/'train-control.private.json';control=_impl.workers.private_json(path)
    _impl.workers.validate_train_control(control,core['native_worker_binding'])
    saved=Path(plan_path).parent/(core['run_nonce_hex']+'-reference-result.private.json')
    value=_impl.workers.private_json(saved)
    _impl.workers.require(value['schema']=='odoo-native-reference-run-result-v6' and
        value['reference_binding_sha256']==plan['reference_binding']['reference_binding_sha256'],
        'Current actual Reference6 run result required')
    proof={'schema':'odoo-reference6-fresh-train-provenance-v1',
        'train_control_sha256':sha256(path.read_bytes()).hexdigest(),
        'native_binding_sha256':core['native_worker_binding_sha256'],
        'reference_binding_sha256':plan['reference_binding']['reference_binding_sha256'],
        'reference_run_result_ref':{'path':str(saved.resolve()),'sha256':sha256(saved.read_bytes()).hexdigest()},
        'source_review_ref':{'path':str(Path(source_review_path).resolve()),'sha256':source_review_sha256},
        'old_reference_credit':0,'formal_admissions':0,'model_calls':0}
    _impl.core._write_new(Path(run_dir)/'reference6-train-provenance.private.json',proof)
    return result

_impl.run=run
_impl.finalize_train_control=finalize_train_control

def __getattr__(name):return getattr(_impl,name)
if __name__=='__main__':_impl.main()
