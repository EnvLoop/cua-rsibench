"""Reopen one genuine baseline with an explicit source-stamp defect, no replay.

This is a reviewed same-native-code migration, not a new native episode. The
old row keeps its original stamp. Current admission must reopen its complete
saved oracle/reset/queue/process evidence and exact runtime/actor equivalence.
"""
from pathlib import Path
from hashlib import sha256
import json
from . import native_surface_actor_v1 as old_actor,native_surface_actor_v2 as actor
from . import native_queue_runtime_v5 as old_runtime,native_queue_runtime_v6 as runtime
from . import native_surface_workers_v5 as old_workers,native_surface_budget_performance_v6 as auditor
from .native_surface_workers_v1 import private_json,require,write

def equivalence():
    before=old_actor.run_task.__code__;after=actor.run_task.__code__
    expected=tuple('native_surface_workers_v6' if name=='native_surface_workers_v1' else name for name in before.co_names)
    require(before.co_code==after.co_code and before.co_consts==after.co_consts and after.co_names==expected,
        'Exact unchanged actor bytecode except source metadata import required')
    for name in ('__init__','command','php','state','start','observe','close'):
        a=getattr(old_runtime.NativeQueue,name).__code__;b=getattr(runtime.NativeQueue,name).__code__
        require((a.co_code,a.co_consts,a.co_names)==(b.co_code,b.co_consts,b.co_names),'Native queue behavior changed')
    a=old_runtime._impl.Runtime.open_case.__wrapped__.__code__;b=runtime._impl.Runtime.open_case.__wrapped__.__code__
    require((a.co_code,a.co_consts,a.co_names)==(b.co_code,b.co_consts,b.co_names) and
        old_runtime._impl.profile is runtime._impl.profile,'Native lifecycle or queue profile changed')
    return {'actor_bytecode_and_constants_identical':True,'only_actor_source_metadata_import_changed':True,
        'native_queue_methods_and_open_case_identical':True,'same_profile_object':True,
        'original_actor_sha256':sha256(Path(old_actor.__file__).read_bytes()).hexdigest(),
        'current_actor_counterpart_sha256':sha256(Path(actor.__file__).read_bytes()).hexdigest()}

def inspect(*,current_binding,identity,episode,old_binding_path,old_launch_path,old_terminal_path):
    episode=Path(episode).resolve();binding=private_json(old_binding_path);launch=private_json(old_launch_path);terminal=private_json(old_terminal_path)
    require(binding==old_workers.public_binding() and launch['source_binding_sha256']==binding['binding_sha256'] and
        terminal['exit_code']==1 and terminal['automatic_restarts']==terminal['model_calls']==0,
        'Original consumed source and failed post-episode auditor terminal required')
    row=private_json(episode/'native-row.private.json')
    require({k:row[k] for k in identity}==identity and row['score']==0 and row['original_sql_score']==0 and
        row['native_source_binding_sha256']=='c6dddc008803c1552108dd493bed755e6383d749560c15185e908299454466f2',
        'Actual original zero baseline and explicit old source-stamp defect required')
    for name,expected in binding['source_sha256s'].items():
        require(sha256((old_workers.ROOT/name).read_bytes()).hexdigest()==expected,'Original launch source changed')
    actual=auditor.audit_episode(episode,row,provider_close_required=False)
    require(actual['score']==0,'Original independent baseline oracle changed')
    proof=equivalence()
    return {'schema':'magento-native-saved-baseline-source-migration-v1','identity':identity,
        'old_native_launch_binding_sha256':binding['binding_sha256'],'current_binding_sha256':current_binding['binding_sha256'],
        'original_row_source_stamp':row['native_source_binding_sha256'],'original_row_relabelled':False,
        'new_native_execution_claimed':False,'independent_saved_baseline_score':0,'equivalence':proof,
        'episode_root':str(episode),'original_row_sha256':sha256((episode/'native-row.private.json').read_bytes()).hexdigest(),
        'old_binding_ref':{'path':str(Path(old_binding_path).resolve()),'sha256':sha256(Path(old_binding_path).read_bytes()).hexdigest()},
        'old_launch_ref':{'path':str(Path(old_launch_path).resolve()),'sha256':sha256(Path(old_launch_path).read_bytes()).hexdigest()},
        'old_terminal_ref':{'path':str(Path(old_terminal_path).resolve()),'sha256':sha256(Path(old_terminal_path).read_bytes()).hexdigest()},
        'new_model_calls':0,'new_native_calls':0,'formal_task_admissions':0}

def checked(receipt_ref,*,current_binding,identity,baseline_proof):
    receipt=private_json(receipt_ref['path'],receipt_ref['sha256'])
    actual=inspect(current_binding=current_binding,identity=identity,episode=receipt['episode_root'],
        old_binding_path=receipt['old_binding_ref']['path'],old_launch_path=receipt['old_launch_ref']['path'],
        old_terminal_path=receipt['old_terminal_ref']['path'])
    require(receipt==actual and baseline_proof=={'score':0,'episode_root':actual['episode_root'],
        'native_row_sha256':actual['original_row_sha256']},'Saved baseline migration or original row reference changed')
    return receipt
