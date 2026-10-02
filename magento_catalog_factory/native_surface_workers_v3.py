"""All Magento model/control slots use the same additive quote setup repair."""
from pathlib import Path
from hashlib import sha256
from types import ModuleType

ROOT=Path(__file__).resolve().parents[1]
PARENT='magento_catalog_factory/native_surface_workers_v1.py'
PARENT_SHA='a51e21f74c7907d1cb1b3a3194fd11efc37988fc5fe3a1ac8a2289e40f2a2f7b'
source=(ROOT/PARENT).read_bytes()
if sha256(source).hexdigest()!=PARENT_SHA:raise ValueError('Frozen Magento worker source changed')
text=source.decode();before='from .native_queue_runtime_v2 import Runtime,run_task'
if text.count(before)!=1:raise ValueError('Checked Magento uniform runtime import changed')
_impl=ModuleType('magento_catalog_factory._native_surface_workers_v3')
_impl.__package__='magento_catalog_factory';_impl.__file__=str(Path(__file__).resolve())
text=text.replace(before,'from .native_queue_runtime_v4 import Runtime,run_task')
before='from .native_surface_budget_performance_v2 import verifier_sha256'
if text.count(before)!=1:raise ValueError('Checked native queue verifier import changed')
text=text.replace(before,'from .native_surface_budget_performance_v4 import verifier_sha256')
exec(compile(text,str(ROOT/PARENT),'exec'),_impl.__dict__)
_impl.SOURCES=tuple(dict.fromkeys((*_impl.SOURCES,'magento_catalog_factory/native_surface_workers_v3.py',
 'magento_catalog_factory/native_surface_facade_v1.py','magento_catalog_factory/native_surface_facade_v3.py',
 'magento_catalog_factory/native_quote_navigation_v2.py','magento_catalog_factory/native_queue_runtime_v4.py',
 'magento_catalog_factory/native_queue_profile_v4.py','magento_catalog_factory/native_surface_budget_performance_v4.py')))
_base_binding=_impl.public_binding

def public_binding():
    value=_base_binding();value.pop('binding_sha256')
    value.update(schema='magento-native-five-slot-source-binding-v3',
        evaluator_quote_navigation='single_click_and_explicit_editor_heading_v2',
        actor_sampler_scorer_reset_changed=False,old_setup_epoch_qualification_credit=0,
        native_queue_service_profile='magento-native-single-attribute-consumer-v4-dual-proc-view',
        exact_native_process_transport_decoding=True,raw_process_argv_retained=True)
    return {**value,'binding_sha256':_impl.digest(_impl.final.canonical(value))}

_impl.public_binding=public_binding
def __getattr__(name):return getattr(_impl,name)
