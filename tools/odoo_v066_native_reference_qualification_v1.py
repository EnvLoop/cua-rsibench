"""Explicit reference epoch around frozen v12 TRAIN/full20/full100 controls."""
import argparse
import json
from pathlib import Path
from types import FunctionType,ModuleType
from enterprise_fallback.odoo18 import native_surface_workers_v12 as workers
from enterprise_fallback.odoo18 import native_reference_facet_v1 as reference
from tools import odoo_v066_native_surface_qualification_v12 as core

SCHEMA='odoo-native-reference-qualification-plan-v1'


def prepare(roster_metadata):
    native,public=core.prepare(roster_metadata)
    plan={'schema':SCHEMA,'native_core_plan':native,'reference_binding':reference.reference_binding(),
        'historical_reference_credit':0,'formal_registration_performed':False}
    return plan,{'schema':SCHEMA,'split':native['split'],'task_count':native['task_count'],
        'native_actor_profile':native['physical_dispatch_profile'],'native_actor_binding_sha256':native['native_worker_binding_sha256'],
        'reference_binding_sha256':plan['reference_binding']['reference_binding_sha256'],
        'private_plan_sha256':workers.digest(workers.canonical(plan)),'model_calls':0,'formal_registration_performed':False}


def validate_plan(value):
    workers.require(type(value) is dict and set(value)=={'schema','native_core_plan','reference_binding','historical_reference_credit','formal_registration_performed'} and
        value['schema']==SCHEMA and value['historical_reference_credit']==0 and value['formal_registration_performed'] is False,
        'native_reference_epoch_plan_invalid')
    reference.validate_reference_binding(value['reference_binding']);core.validate_plan(value['native_core_plan']);return value


def _facade(ref):
    old=ModuleType('core_facade');old.__dict__.update(core.run.__globals__)
    new=ModuleType('tools._odoo_optional_reference_qualification_v1');new.__dict__.update(old.__dict__)
    class NativeWorkerProxy:
        def __getattr__(self,name):return getattr(workers,name)
        def evaluator_module(self,binding):return reference.candidate_module(binding,ref)
    new.workers=NativeWorkerProxy()
    for key,value in list(new.__dict__.items()):
        if isinstance(value,FunctionType) and value.__globals__ is core.run.__globals__:
            clone=FunctionType(value.__code__,new.__dict__,value.__name__,value.__defaults__,value.__closure__)
            clone.__kwdefaults__=value.__kwdefaults__;clone.__annotations__=value.__annotations__;new.__dict__[key]=clone
    return new


def _write(path,value):
    path=Path(path);workers.require(path.parent.is_dir() and not path.parent.is_symlink() and path.parent.stat().st_mode&0o077==0,
        'native_reference_private_stage_required')
    return core._write_new(path,value)


def run(*,plan_path,worker_dir,run_dir,execute=False,train_task_id=None,train_control_path=None,train_control_sha256=None):
    plan_path=Path(plan_path);plan=validate_plan(workers.private_json(plan_path));native=plan['native_core_plan'];ref=plan['reference_binding']
    native_path=plan_path.parent/(native['run_nonce_hex']+'-core-plan.private.json')
    _write(native_path,native)
    # This intent consumes the declared reference namespace before any native
    # control. Its presence refuses a second call even after a preflight error.
    intent=plan_path.parent/(native['run_nonce_hex']+'-reference-intent.private.json')
    _write(intent,{'schema':'odoo-native-reference-dispatch-intent-v1','plan_sha256':workers.digest(plan_path.read_bytes()),
        'native_core_plan_sha256':workers.digest(native_path.read_bytes()),'reference_binding':ref,
        'same_episode_replay_authorized':False,'native_actor_scorer_reset_unchanged':True})
    facade=_facade(ref)
    result=facade.run(plan_path=native_path,worker_dir=Path(worker_dir),run_dir=Path(run_dir),execute=execute,
        train_task_id=train_task_id,train_control_path=train_control_path,train_control_sha256=train_control_sha256)
    reference.validate_reference_binding(ref)
    _write(plan_path.parent/(native['run_nonce_hex']+'-reference-result.private.json'),{'schema':'odoo-native-reference-run-result-v1',
        'reference_binding_sha256':ref['reference_binding_sha256'],'native_core_result':result,
        'formal_registration_performed':False,'old_reference_control_credit':0})
    return result


def finalize_train_control(*,plan_path,**kwargs):
    plan_path=Path(plan_path);plan=validate_plan(workers.private_json(plan_path));nonce=plan['native_core_plan']['run_nonce_hex']
    core_path=plan_path.parent/(nonce+'-core-plan.private.json')
    workers.require(workers.private_json(core_path)==plan['native_core_plan'],'native_reference_core_plan_changed')
    return _facade(plan['reference_binding']).finalize_train_control(plan_path=core_path,**kwargs)


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    prep=sub.add_parser('prepare');prep.add_argument('--legacy-metadata-plan',type=Path,required=True)
    prep.add_argument('--metadata-plan-sha256',required=True);prep.add_argument('--split',required=True,choices=('train','selection','official_hidden'))
    prep.add_argument('--private-plan',type=Path,required=True);prep.add_argument('--public-plan',type=Path,required=True);prep.add_argument('--native-binding',type=Path,required=True)
    run_parser=sub.add_parser('run')
    for name in ('plan','worker-dir','run-dir'):run_parser.add_argument('--'+name,type=Path,required=True)
    run_parser.add_argument('--execute',action='store_true');run_parser.add_argument('--train-task-id');run_parser.add_argument('--train-control',type=Path);run_parser.add_argument('--train-control-sha256')
    finalize=sub.add_parser('finalize-train')
    for name in ('plan','worker-dir','run-dir','source-review'):finalize.add_argument('--'+name,type=Path,required=True)
    finalize.add_argument('--source-review-sha256',required=True)
    args=vars(p.parse_args());command=args.pop('command')
    if command=='prepare':
        metadata=core.project_legacy_metadata(workers.private_json(args['legacy_metadata_plan'],args['metadata_plan_sha256']),args['split'])
        plan,public=prepare(metadata);_write(args['private_plan'],plan);_write(args['native_binding'],plan['native_core_plan']['native_worker_binding'])
        core._write_new(args['public_plan'],public,private=False);result=public
    elif command=='run':
        args['plan_path']=args.pop('plan');args['train_control_path']=args.pop('train_control');result=run(**args)
    else:
        args['plan_path']=args.pop('plan');args['source_review_path']=args.pop('source_review');result=finalize_train_control(**args)
    print(json.dumps(result,sort_keys=True))

if __name__=='__main__':main()
