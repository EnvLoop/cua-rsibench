"""Reviewed reference-only two-mode continuation, unchanged native worker9.

Retain the already verified baseline and retired ambiguous-label attempt.
Only evaluator target selection changes; every mutation still goes through
the same current native actor/guard/scorer/reset/queue source.
"""
from pathlib import Path
from hashlib import sha256
import asyncio,json,os
from . import native_surface_workers_v9 as workers,native_surface_budget_performance_v9 as audit
from . import native_saved_baseline_migration_v2 as migration,native_reference_bulk_price_v6 as reference
require,private_json,write=workers.require,workers.private_json,workers.write

def reference_binding():
    value={'schema':'magento-native-reference-current-visible-safe-scroll-controls-v6','native_binding_sha256':workers.public_binding()['binding_sha256'],
        'reference_source_sha256':sha256(Path(reference.__file__).read_bytes()).hexdigest(),
        'reference_ancestor_sha256s':{name:sha256((Path(__file__).resolve().parents[1]/name).read_bytes()).hexdigest() for name in ('magento_catalog_factory/native_reference_bulk_price_v2.py','magento_catalog_factory/native_reference_bulk_price_v3.py','magento_catalog_factory/native_reference_bulk_price_v4.py','magento_catalog_factory/native_reference_bulk_price_v5.py')},
        'continuation_source_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
        'target_selection_only_changed':True,'native_actor_scorer_reset_changed':False}
    return {**value,'binding_sha256':sha256(workers.final.canonical(value)).hexdigest()}

def run(*,inputs_path,migration_path,migration_sha256,retired_terminal_path,retired_terminal_sha256,
        root_review_path,root_review_sha256,output,execute=False):
    require(execute is True,'Reviewed reference-only native continuation required')
    inputs=workers.Inputs(**private_json(inputs_path),control_preparation_only=True)
    identity=inputs.roster['splits']['train'][0];saved=private_json(migration_path,migration_sha256)
    baseline={'score':0,'episode_root':saved['episode_root'],'native_row_sha256':saved['original_row_sha256']}
    migration_ref={'path':str(Path(migration_path).resolve()),'sha256':migration_sha256}
    migration.checked(migration_ref,current_binding=inputs.binding,identity=identity,baseline_proof=baseline)
    terminal=private_json(retired_terminal_path,retired_terminal_sha256)
    require(terminal['exit_code']==1 and terminal['automatic_restarts']==terminal['model_calls']==0,'Retired actual reference failure required')
    try:os.kill(terminal['pid'],0)
    except ProcessLookupError:pass
    else:raise ValueError('Retired reference worker still live')
    ref=reference_binding();review=private_json(root_review_path,root_review_sha256)
    require(review=={'schema':'magento-native-reference-two-mode-root-review-v6','native_binding_sha256':inputs.binding['binding_sha256'],
        'reference_binding_sha256':ref['binding_sha256'],'migration_sha256':migration_sha256,
        'retired_terminal_sha256':retired_terminal_sha256,'identity':identity,'baseline_replay_authorized':False,
        'positive_and_wrong_variant_only_authorized':True,'target_selection_only_change_reviewed':True,
        'native_actor_scorer_reset_unchanged_reviewed':True,'automatic_restart_authorized':False,'formal_registration_authorized':False},
        'Exact new reference source and retired attempt root review required')
    output=Path(output);require(not output.exists() and not output.is_symlink(),'Fresh current reference output required')
    output.mkdir(mode=0o700,parents=True)
    write(output.parent,'reference-'+root_review_sha256+'-consumed.private.json',{'review_sha256':root_review_sha256,
        'original_baseline_replayed':False,'automatic_restart_authorized':False,'model_calls':0})
    trio={'baseline':baseline};case=inputs.load(identity,'train')
    for mode,expected in [('positive',1),('wrong_variant',0)]:
        require(inputs.binding==workers.public_binding() and reference_binding()==ref,'Native or reference source changed')
        folder=output/'attempt-000'/mode;folder.mkdir(mode=0o700,parents=True)
        row=asyncio.run(workers.run_task(case=case,task=identity,output=folder,runtime=inputs.runtime(),
            sampler=reference.sampler(case,mode),username=inputs.username(),attempt_id='control-000-'+mode,paid_attempt_id=None))
        write(folder,'native-row.private.json',row);audit.audit_episode(folder,row,provider_close_required=False)
        require(row['score']==expected and row['native_source_binding_sha256']==inputs.binding['binding_sha256'],
            'Genuine current score and source required')
        trio[mode]={'score':row['score'],'episode_root':str(folder.resolve()),'native_row_sha256':sha256((folder/'native-row.private.json').read_bytes()).hexdigest()}
    summary={'schema':'magento-native-surface-control-set-v1','source_binding_sha256':inputs.binding['binding_sha256'],
        'split':'train','task_count':1,'tasks':[{**identity,'trio':trio}],'model_calls':0,'formal_registration_performed':False,
        'old_development_control_credit':0,'baseline_source_migration_ref':migration_ref,'original_baseline_replayed':False,
        'reference_binding':ref,'retired_reference_terminal_ref':{'path':str(Path(retired_terminal_path).resolve()),'sha256':retired_terminal_sha256},
        'root_reference_review_ref':{'path':str(Path(root_review_path).resolve()),'sha256':root_review_sha256}}
    write(output,'controls.private.json',summary)
    return summary
