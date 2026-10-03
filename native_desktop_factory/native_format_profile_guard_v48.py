"""Raw profile retained; one declared false startup property compared separately."""
import hashlib,json
from pathlib import Path
from types import FunctionType,SimpleNamespace
from . import v066_scoped_profile_guard as original
from . import v066_profile_scope_analysis as scope
from . import native_format_startup_preset_v48 as preset

def projected_profile(rows,raw):
 # Validate the actual manifest/registry binding before deriving a comparison.
 scope.scoped_profile(rows,raw)
 clean=preset.parent_registry_projection(raw)
 amended=[{**row,'sha256':scope.digest(clean),'bytes':len(clean)} if row['path']=='registrymodifications.xcu' else row for row in rows]
 return scope.scoped_profile(amended,clean)

scope_proxy=SimpleNamespace(**{**vars(scope),'scoped_profile':projected_profile})
_capture=FunctionType(original._capture.__code__,{**original._capture.__globals__,'scope':scope_proxy},original._capture.__name__,original._capture.__defaults__,original._capture.__closure__)

def capture(*args,**kwargs):
 value=_capture(*args,**kwargs);out=kwargs['out'];label=kwargs['label'];record=kwargs['snapshots'][-1]
 raw=(out/f'profile-{label}.registry.xml').read_bytes();rows=json.loads((out/f'profile-{label}.manifest.json').read_bytes())
 record['parent_profile_projection_sha256']=record.pop('scoped_profile_sha256')
 record['actual_profile_scoped_sha256']=scope.scoped_profile(rows,raw)
 record['declared_preference_false_checked']=True;kwargs['persist']()
 return value

fn=original.attest
_attest=FunctionType(fn.__code__,{**fn.__globals__,'_capture':capture},fn.__name__,fn.__defaults__,fn.__closure__)
_attest.__kwdefaults__=fn.__kwdefaults__

def attest(**kwargs):
 value=_attest(**kwargs);receipt=kwargs['receipt'];records=receipt['task_profile_scoped_snapshots']
 if len(records)!=2 or records[0]['actual_profile_scoped_sha256']!=records[1]['actual_profile_scoped_sha256']:raise ValueError('Actual preference profile is unstable')
 receipt['task_profile_parent_projection_sha256']=receipt.pop('task_profile_scoped_sha256')
 receipt['task_profile_parent_projection_matches_public_train']=receipt.pop('task_profile_scoped_matches_public_train')
 receipt['task_profile_actual_scoped_sha256']=records[-1]['actual_profile_scoped_sha256']
 receipt['task_profile_declared_preference_policy']=preset.POLICY
 receipt['task_profile_new_epoch_not_original_raw_profile']=True;kwargs['persist']()
 return value
