"""Original SQL/reset oracle with the exact V3 native process evidence decoder."""
from hashlib import sha256
from pathlib import Path
from types import ModuleType
import json
from . import native_surface_budget_performance_v2 as original

source=Path(original.__file__).read_bytes()
if sha256(source).hexdigest()!='4fba00c2872d6d656433b040e2177d68e6e5eb53a65ad676368cc8f50aa9a749':
    raise ValueError('Frozen queue verdict source changed')
text=source.decode()
for before,after,count in [('native_queue_profile_v2 as profile,native_queue_runtime_v2 as runtime',
    'native_queue_profile_v5 as profile,native_queue_runtime_v10 as runtime',1),
    ('magento_catalog_factory/native_surface_budget_performance_v2.py','magento_catalog_factory/native_surface_budget_performance_v10.py',1),
    ('magento_catalog_factory/native_queue_profile_v2.py','magento_catalog_factory/native_queue_profile_v5.py',1),
    ('magento_catalog_factory/native_queue_runtime_v2.py','magento_catalog_factory/native_queue_runtime_v10.py',1),
    ('magento_catalog_factory.native_surface_budget_performance_v2','magento_catalog_factory.native_surface_budget_performance_v10',1)]:
    if text.count(before)!=count:raise ValueError('Checked native queue verdict counterpart changed')
    text=text.replace(before,after)
_impl=ModuleType('magento_catalog_factory._native_surface_budget_performance_v10')
_impl.__package__='magento_catalog_factory';_impl.__file__=str(Path(__file__).resolve())
exec(compile(text,str(Path(original.__file__)),'exec'),_impl.__dict__)
from types import FunctionType
_method=_impl.original_audit
if _method.__code__.co_names.count('native_surface_workers_v1')!=1:raise ValueError('Checked original saved auditor source import changed')
_code=_method.__code__.replace(co_names=tuple('native_surface_workers_v10' if name=='native_surface_workers_v1' else name for name in _method.__code__.co_names))
_scoped=FunctionType(_code,dict(_method.__globals__),_method.__name__,_method.__defaults__,_method.__closure__)
_scoped.__kwdefaults__=_method.__kwdefaults__
_impl.original_audit=_scoped
_original_queue_audit=_impl.audit_episode

def audit_episode(root,row,*,provider_close_required=True):
    from .native_principal_header_v2 import valid_witness
    result=_original_queue_audit(root,row,provider_close_required=provider_close_required)
    root=Path(root)
    def read_ref(reference):
        _impl.policy.verify_artifact(root,reference)
        return json.loads((root/reference['path']).read_bytes())
    held=json.loads((root/'guard/held-lease.private.json').read_bytes())
    for frame in result['frames']:
        envelope=read_ref(frame['native_envelope']);native=read_ref(envelope['raw_envelope'])
        username=native.get('native_username')
        _impl.profile.require(valid_witness(native,username) and sha256(username.encode()).hexdigest()==held['native_username_sha256'],
            'Saved exact current-document principal witness changed')
    for action in result['actions']:
        capsule=read_ref(action['contract']['native_surface_guard'])
        for envelope in (capsule['observed'],capsule['current']):
            native=read_ref(envelope['raw_envelope']);username=native.get('native_username')
            _impl.profile.require(valid_witness(native,username) and sha256(username.encode()).hexdigest()==held['native_username_sha256'],
                'Saved predispatch principal witness changed')
    return result

_impl.audit_episode=audit_episode

def verifier_sha256():
    names=('verify.py','native_queue_profile_v5.py','native_queue_runtime_v10.py',
        'native_surface_budget_performance_v10.py','native_principal_header_v2.py',
        'native_surface_adapter_v4.py','native_surface_lease_v2.py')
    root=Path(__file__).resolve().parents[1]
    payload={'magento_catalog_factory/'+name:sha256((root/'magento_catalog_factory'/name).read_bytes()).hexdigest() for name in names}
    return sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()

_impl.verifier_sha256=verifier_sha256

def __getattr__(name):return getattr(_impl,name)
