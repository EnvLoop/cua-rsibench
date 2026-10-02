"""Runnable original Magento controls with the source-bound CMS setup repair."""
from pathlib import Path
from hashlib import sha256
from types import ModuleType
from . import native_surface_facade_v1 as ancestor

ROOT=Path(__file__).resolve().parents[1]
PARENT='magento_catalog_factory/native_surface_facade_v1.py'
PARENT_SHA='c9b4706e7e2225755d8c5d41dcef1823abc21bee7d66227999c36afc3b0a331b'
source=(ROOT/PARENT).read_bytes()
if sha256(source).hexdigest()!=PARENT_SHA:raise ValueError('Frozen Magento controls source changed')
text=source.decode()
for before,after in [('from .native_surface_workers_v1 import','from .native_surface_workers_v9 import'),
 ('from .native_queue_runtime_v2 import run_task','from .native_queue_runtime_v9 import run_task'),
 ('from .native_surface_budget_performance_v2 import audit_episode','from .native_surface_budget_performance_v9 import audit_episode')]:
    if text.count(before)!=1:raise ValueError('Checked Magento controls runtime source changed')
    text=text.replace(before,after)
_impl=ModuleType('magento_catalog_factory._native_surface_facade_v9')
_impl.__package__='magento_catalog_factory';_impl.__file__=str(Path(__file__).resolve())
exec(compile(text,str(ROOT/PARENT),'exec'),_impl.__dict__)
# Reuse the identical original evaluator-only sampler class accepted by the
# frozen actor. Its native mutations and source are unchanged and hash-bound.
_impl.ReferenceSampler=ancestor.ReferenceSampler

def complete_saved_baseline_trio(*,inputs_path,migration_path,migration_sha256,root_review_path,root_review_sha256,output,execute=False):
    """Import exact reviewed zero baseline and execute only two missing modes."""
    import asyncio,json
    from . import native_saved_baseline_migration_v2 as migration
    require=_impl.require;private_json=_impl.private_json;write=_impl.write
    require(execute is True,'Explicit current native control continuation required')
    inputs=_impl.Inputs(**private_json(inputs_path),control_preparation_only=True)
    identity=inputs.roster['splits']['train'][0]
    saved=private_json(migration_path,migration_sha256)
    baseline={'score':0,'episode_root':saved['episode_root'],'native_row_sha256':saved['original_row_sha256']}
    migration_ref={'path':str(Path(migration_path).resolve()),'sha256':migration_sha256}
    migration.checked(migration_ref,current_binding=inputs.binding,identity=identity,baseline_proof=baseline)
    review=private_json(root_review_path,root_review_sha256)
    require(review=={'schema':'magento-current-saved-baseline-control-continuation-root-review-v1',
        'source_binding_sha256':inputs.binding['binding_sha256'],'migration_sha256':migration_sha256,
        'identity':identity,'original_baseline_replay_authorized':False,'original_baseline_row_relabelled':False,
        'positive_and_wrong_variant_only_authorized':True,'same_native_actor_scorer_reset_reviewed':True,
        'automatic_restart_authorized':False,'formal_registration_authorized':False},
        'Exact source migration and two-mode continuation root review required')
    output=Path(output)
    require(not output.exists() and not output.is_symlink(),'Fresh reviewed native control continuation required')
    output.mkdir(mode=0o700,parents=True)
    claim=Path(migration_path).parent/('control-continuation-'+migration_sha256+'-consumed.private.json')
    write(claim.parent,claim.name,{'migration_sha256':migration_sha256,'new_output_root':str(output.resolve()),
        'original_baseline_replayed':False,'automatic_restart_authorized':False,'model_calls':0})
    trio={'baseline':baseline};case=inputs.load(identity,'train')
    for mode,expected in [('positive',1),('wrong_variant',0)]:
        require(inputs.binding==_impl.public_binding(),'Current native source changed before next control')
        folder=output/'attempt-000'/mode;folder.mkdir(mode=0o700,parents=True)
        sampler=_impl.ReferenceSampler(case,mode)
        row=asyncio.run(_impl.run_task(case=case,task=identity,output=folder,runtime=inputs.runtime(),sampler=sampler,
            username=inputs.username(),attempt_id='control-000-'+mode,paid_attempt_id=None))
        write(folder,'native-row.private.json',row);_impl.audit_episode(folder,row,provider_close_required=False)
        require(row['score']==expected and row['native_source_binding_sha256']==inputs.binding['binding_sha256'],
            'Genuine current control score and source stamp required')
        trio[mode]={'score':row['score'],'episode_root':str(folder.resolve()),
            'native_row_sha256':sha256((folder/'native-row.private.json').read_bytes()).hexdigest()}
    summary={'schema':'magento-native-surface-control-set-v1','source_binding_sha256':inputs.binding['binding_sha256'],
        'split':'train','task_count':1,'tasks':[{**identity,'trio':trio}],'model_calls':0,
        'formal_registration_performed':False,'old_development_control_credit':0,
        'baseline_source_migration_ref':migration_ref,'root_continuation_review_ref':
        {'path':str(Path(root_review_path).resolve()),'sha256':root_review_sha256},'original_baseline_replayed':False}
    write(output,'controls.private.json',summary)
    return summary


def __getattr__(name):return getattr(_impl,name)
if __name__=='__main__':_impl.main()
