"""Closed current runtime across controls, teacher, base, CPs and final audit.

All lazy verifier/shared-base imports select the same V4 queue decoder. Frozen
worker3 native controls retain their original source; this is a new interface
binding and does not retrospectively qualify any task or model result.
"""
from pathlib import Path
from hashlib import sha256
from types import ModuleType

ROOT=Path(__file__).resolve().parents[1]
PARENT='magento_catalog_factory/native_surface_workers_v1.py'
PARENT_SHA='a51e21f74c7907d1cb1b3a3194fd11efc37988fc5fe3a1ac8a2289e40f2a2f7b'
source=(ROOT/PARENT).read_bytes()
if sha256(source).hexdigest()!=PARENT_SHA:raise ValueError('Frozen original Magento worker source changed')
text=source.decode()
for before,after,count in [('from .native_queue_runtime_v2 import Runtime,run_task',
    'from .native_queue_runtime_v6 import Runtime,run_task',1),
    ('native_surface_budget_performance_v2','native_surface_budget_performance_v6',6),
    ('from .native_surface_shared_base_v1 import admit_shared_base',
     'from .native_surface_shared_base_v4 import admit_shared_base',1)]:
    if text.count(before)!=count:raise ValueError('Checked complete Magento counterpart import changed')
    text=text.replace(before,after)
_impl=ModuleType('magento_catalog_factory._native_surface_workers_v6')
_impl.__package__='magento_catalog_factory';_impl.__file__=str(Path(__file__).resolve())
_validate_source="        source_images=[]"
if text.count(_validate_source)!=1:raise ValueError('Checked admission source migration boundary changed')
text=text.replace(_validate_source,"        if control.get('baseline_source_migration_ref') is not None:\n            from .native_saved_baseline_migration_v1 import checked\n            checked(control['baseline_source_migration_ref'],current_binding=self.binding,identity=identity,baseline_proof=control['tasks'][0]['trio']['baseline'])\n"+_validate_source)
exec(compile(text,str(ROOT/PARENT),'exec'),_impl.__dict__)
_impl.SOURCES=tuple(dict.fromkeys((*_impl.SOURCES,
    'magento_catalog_factory/native_surface_workers_v6.py','magento_catalog_factory/native_surface_facade_v6.py',
    'magento_catalog_factory/native_surface_teacher_v4.py','magento_catalog_factory/native_surface_shared_base_v4.py',
    'magento_catalog_factory/native_quote_navigation_v2.py','magento_catalog_factory/native_queue_runtime_v6.py',
    'magento_catalog_factory/native_queue_profile_v5.py','magento_catalog_factory/native_surface_budget_performance_v6.py',
    'magento_catalog_factory/native_queue_profile_v3.py','magento_catalog_factory/native_queue_profile_v4.py','magento_catalog_factory/native_surface_actor_v2.py',
    'magento_catalog_factory/native_saved_baseline_migration_v1.py')))
_base_binding=_impl.public_binding

def public_binding():
    value=_base_binding();value.pop('binding_sha256')
    value.update(schema='magento-native-five-slot-source-binding-v6',
        evaluator_quote_navigation='single_click_and_explicit_editor_heading_v2',
        actor_sampler_scorer_reset_changed=False,old_setup_epoch_qualification_credit=0,
        native_queue_service_profile='magento-native-single-attribute-consumer-v5-bounded-native-exec-transition',
        exact_native_process_transport_decoding=True,raw_process_argv_retained=True,
        all_lazy_auditors_and_teacher_shared_base_bridges_current=True,
        teacher_adapter_module='magento_catalog_factory.native_surface_teacher_v4',
        shared_base_verifier_module='magento_catalog_factory.native_surface_shared_base_v4',
        budget_performance_module='magento_catalog_factory.native_surface_budget_performance_v6')
    return {**value,'binding_sha256':_impl.digest(_impl.final.canonical(value))}

_impl.public_binding=public_binding
def __getattr__(name):return getattr(_impl,name)
