"""Fresh reviewed three-mode controls for the rendered-principal native epoch.

No saved baseline migration, model/provider dispatch or automatic restart.
The existing trusted reference recipe uses unchanged guarded native actions.
"""
import argparse
import asyncio
import json
from hashlib import sha256
from pathlib import Path
from . import native_surface_workers_v10 as workers
from . import native_surface_budget_performance_v10 as audit
from . import native_reference_bulk_price_v6 as reference

MODES=(('baseline',0),('positive',1),('wrong_variant',0))
require,private_json,write=workers.require,workers.private_json,workers.write

def reference_binding():
    root=Path(__file__).resolve().parents[1]
    names=tuple('magento_catalog_factory/native_reference_bulk_price_v'+str(version)+'.py' for version in range(2,7))
    value={'schema':'magento-native-fresh-rendered-principal-reference-binding-v7',
        'native_binding_sha256':workers.public_binding()['binding_sha256'],
        'qualification_source_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
        'reference_source_sha256s':{name:sha256((root/name).read_bytes()).hexdigest() for name in names},
        'fresh_baseline_positive_wrong_variant_required':True,
        'old_baseline_promotion_allowed':False,'model_calls':0,
        'native_target_predicates_sql_scorer_reset_changed':False}
    return {**value,'binding_sha256':sha256(workers.final.canonical(value)).hexdigest()}

def review_contract(*,inputs_path,inputs_sha256,train_index,output):
    """Metadata only; never constructs a runtime or opens task bodies."""
    require(type(train_index) is int and 0<=train_index<20,'Explicit current TRAIN ordinal required')
    values=private_json(inputs_path,inputs_sha256)
    inputs=workers.Inputs(**values,control_preparation_only=True)
    return {'schema':'magento-native-fresh-rendered-principal-root-review-v7',
        'inputs_ref':{'path':str(Path(inputs_path).resolve()),'sha256':inputs_sha256},
        'native_binding_sha256':inputs.binding['binding_sha256'],
        'reference_binding_sha256':reference_binding()['binding_sha256'],
        'train_index':train_index,'identity':inputs.roster['splits']['train'][train_index],
        'output_root':str(Path(output).resolve()),'modes':[mode for mode,_ in MODES],
        'fresh_three_modes_authorized':True,'old_baseline_promotion_authorized':False,
        'current_document_rendered_principal_change_reviewed':True,
        'viewport_targets_origin_window_pid_exe_budgets_sql_reset_unchanged_reviewed':True,
        'automatic_restart_authorized':False,'model_calls_authorized':0,
        'formal_registration_authorized':False}

def run(*,inputs_path,inputs_sha256,train_index,output,root_review_path,root_review_sha256,execute=False):
    require(execute is True,'Explicit root-reviewed fresh control execution required')
    expected=review_contract(inputs_path=inputs_path,inputs_sha256=inputs_sha256,train_index=train_index,output=output)
    review=private_json(root_review_path,root_review_sha256)
    require(review==expected,'Exact current fresh three-mode root review required')
    inputs=workers.Inputs(**private_json(inputs_path,inputs_sha256),control_preparation_only=True)
    ref=reference_binding();identity=expected['identity'];output=Path(output)
    require(not output.exists() and not output.is_symlink(),'Fresh three-mode namespace required')
    output.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    # Exclusive claim persists even when an actual native run fails. It cannot
    # authorize automatic replay or silently reuse a partially attempted mode.
    write(output.parent,'fresh-trio-'+root_review_sha256+'-consumed.private.json',
        {'review_sha256':root_review_sha256,'modes':expected['modes'],
         'old_baseline_promoted':False,'automatic_restarts':0,'model_calls':0})
    output.mkdir(mode=0o700)
    case=inputs.load(identity,'train');trio={}
    for mode,score in MODES:
        require(inputs.binding==workers.public_binding() and reference_binding()==ref,'Current native/reference source changed')
        folder=output/'attempt-000'/mode;folder.mkdir(mode=0o700,parents=True)
        row=asyncio.run(workers.run_task(case=case,task=identity,output=folder,runtime=inputs.runtime(),
            sampler=reference.sampler(case,mode),username=inputs.username(),
            attempt_id='control-000-'+mode,paid_attempt_id=None))
        write(folder,'native-row.private.json',row)
        audit.audit_episode(folder,row,provider_close_required=False)
        require(row['score']==score and row['native_source_binding_sha256']==inputs.binding['binding_sha256'],
            'Fresh native control score/source mismatch')
        trio[mode]={'score':row['score'],'episode_root':str(folder.resolve()),
            'native_row_sha256':sha256((folder/'native-row.private.json').read_bytes()).hexdigest()}
    summary={'schema':'magento-native-surface-control-set-v1','source_binding_sha256':inputs.binding['binding_sha256'],
        'split':'train','task_count':1,'tasks':[{**identity,'trio':trio}],'model_calls':0,
        'formal_registration_performed':False,'old_development_control_credit':0,
        'old_principal_epoch_qualification_credit':0,'original_baseline_promoted':False,
        'fresh_three_modes_completed':True,'reference_binding':ref,
        'root_reference_review_ref':{'path':str(Path(root_review_path).resolve()),'sha256':root_review_sha256}}
    write(output,'controls.private.json',summary)
    return summary

def main():
    parser=argparse.ArgumentParser()
    for name in ('inputs-path','inputs-sha256','output','root-review-path','root-review-sha256'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--train-index',type=int,required=True)
    parser.add_argument('--execute',action='store_true')
    result=run(**vars(parser.parse_args()))
    print(json.dumps({'status':'fresh_source_bound_trio_complete','task_count':result['task_count'],
        'source_binding_sha256':result['source_binding_sha256']}))

if __name__=='__main__':main()
