"""Exact current-readiness baseline migration across reader metadata imports."""
from pathlib import Path
from hashlib import sha256
from types import FunctionType
from . import native_surface_workers_v8 as old_workers,native_surface_workers_v9 as current_workers
from . import native_surface_actor_v4 as old_actor,native_surface_actor_v5 as actor
from . import native_queue_runtime_v8 as old_runtime,native_queue_runtime_v9 as runtime
from . import native_surface_budget_performance_v8 as old_auditor
from .native_surface_workers_v1 import private_json,require

def equivalence():
    a,b=old_actor.run_task.__code__,actor.run_task.__code__
    require(a.co_code==b.co_code and a.co_consts==b.co_consts and
        b.co_names==tuple('native_surface_workers_v9' if n=='native_surface_workers_v8' else n for n in a.co_names),
        'Only actor current source metadata import may change')
    for name in ('__init__','command','php','state','start','observe','close'):
        a,b=getattr(old_runtime.NativeQueue,name).__code__,getattr(runtime.NativeQueue,name).__code__
        require((a.co_code,a.co_consts,a.co_names)==(b.co_code,b.co_consts,b.co_names),'Native queue behavior changed')
    require(old_runtime.NavigationRuntime is runtime.NavigationRuntime and old_runtime._impl.profile is runtime._impl.profile,
        'Startup readiness or native queue profile changed')
    return {'same_actor_bytecode_and_constants':True,'only_actor_source_metadata_import_changed':True,
        'same_native_queue_methods':True,'same_startup_runtime_class':True,'same_queue_profile_object':True}

def _audit_original(episode,row):
    auditor=old_auditor.audit_episode;original=auditor.__globals__['original_audit']
    require(original.__code__.co_names.count('native_surface_workers_v1')==1,'Known original reader import defect required')
    code=original.__code__.replace(co_names=tuple('native_surface_workers_v8' if n=='native_surface_workers_v1' else n for n in original.__code__.co_names))
    reader=FunctionType(code,dict(original.__globals__),original.__name__,original.__defaults__,original.__closure__);reader.__kwdefaults__=original.__kwdefaults__
    audit=FunctionType(auditor.__code__,{**auditor.__globals__,'original_audit':reader},auditor.__name__,auditor.__defaults__,auditor.__closure__);audit.__kwdefaults__=auditor.__kwdefaults__
    return audit(episode,row,provider_close_required=False)

def audit_original_baseline(receipt):
    episode=Path(receipt['episode_root']);row=private_json(episode/'native-row.private.json',receipt['original_row_sha256'])
    return _audit_original(episode,row)

def inspect(*,current_binding,identity,episode,old_binding_path,old_launch_path,old_terminal_path):
    require(current_binding==current_workers.public_binding(),'Only exact current decoder source may use migration')
    binding=private_json(old_binding_path);launch=private_json(old_launch_path);terminal=private_json(old_terminal_path)
    require(binding==old_workers.public_binding() and launch['source_binding_sha256']==binding['binding_sha256'] and
        terminal['exit_code']==1 and terminal['automatic_restarts']==terminal['model_calls']==0,
        'Original exact current-readiness source and terminal required')
    episode=Path(episode).resolve();raw=(episode/'native-row.private.json').read_bytes();row=private_json(episode/'native-row.private.json')
    require({key:row[key] for key in identity}==identity and row['score']==row['original_sql_score']==0 and
        row['native_source_binding_sha256']==binding['binding_sha256'],'Original baseline current source stamp/score required')
    for name,expected in binding['source_sha256s'].items():
        require(sha256((old_workers.ROOT/name).read_bytes()).hexdigest()==expected,'Original exact source bytes changed')
    result=_audit_original(episode,row)
    require(result['score']==0 and (episode/'native-row.private.json').read_bytes()==raw,'Original saved result changed')
    def ref(path):return {'path':str(Path(path).resolve()),'sha256':sha256(Path(path).read_bytes()).hexdigest()}
    return {'schema':'magento-native-current-readiness-baseline-migration-v2','identity':identity,
        'current_binding_sha256':current_binding['binding_sha256'],'old_native_launch_binding_sha256':binding['binding_sha256'],
        'episode_root':str(episode),'original_row_sha256':sha256(raw).hexdigest(),'original_row_source_stamp':row['native_source_binding_sha256'],
        'equivalence':equivalence(),'independent_saved_baseline_score':0,'original_row_relabelled':False,'new_native_execution_claimed':False,
        'old_binding_ref':ref(old_binding_path),'old_launch_ref':ref(old_launch_path),'old_terminal_ref':ref(old_terminal_path),
        'new_model_calls':0,'new_native_calls':0,'formal_task_admissions':0}

def checked(reference,*,current_binding,identity,baseline_proof):
    receipt=private_json(reference['path'],reference['sha256'])
    actual=inspect(current_binding=current_binding,identity=identity,episode=receipt['episode_root'],
        old_binding_path=receipt['old_binding_ref']['path'],old_launch_path=receipt['old_launch_ref']['path'],old_terminal_path=receipt['old_terminal_ref']['path'])
    require(actual==receipt and baseline_proof=={'score':0,'episode_root':actual['episode_root'],
        'native_row_sha256':actual['original_row_sha256']},'Exact original saved baseline migration changed')
    return receipt
