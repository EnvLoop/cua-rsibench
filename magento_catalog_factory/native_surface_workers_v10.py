"""Uniform current-document principal epoch across all seven native roles.

No earlier viewport-principal control qualifies this new source epoch.
Targets, actor budgets, native queue, SQL scorer and reset stay unchanged.
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
    'from .native_queue_runtime_v10 import Runtime,run_task',1),
    ('native_surface_budget_performance_v2','native_surface_budget_performance_v10',6),
    ('from .native_surface_shared_base_v1 import admit_shared_base',
     'from .native_surface_shared_base_v8 import admit_shared_base',1)]:
    if text.count(before)!=count:raise ValueError('Checked complete Magento counterpart import changed')
    text=text.replace(before,after)
_impl=ModuleType('magento_catalog_factory._native_surface_workers_v10')
_impl.__package__='magento_catalog_factory';_impl.__file__=str(Path(__file__).resolve())
exec(compile(text,str(ROOT/PARENT),'exec'),_impl.__dict__)
_impl.SOURCES=tuple(dict.fromkeys((*_impl.SOURCES,
    'magento_catalog_factory/native_surface_workers_v10.py','magento_catalog_factory/native_surface_facade_v10.py',
    'magento_catalog_factory/native_surface_teacher_v8.py','magento_catalog_factory/native_surface_shared_base_v8.py',
    'magento_catalog_factory/native_quote_navigation_v2.py','magento_catalog_factory/native_queue_runtime_v10.py',
    'magento_catalog_factory/native_queue_profile_v5.py','magento_catalog_factory/native_surface_budget_performance_v10.py',
    'magento_catalog_factory/native_queue_profile_v3.py','magento_catalog_factory/native_queue_profile_v4.py','magento_catalog_factory/native_surface_actor_v6.py',
    'magento_catalog_factory/native_startup_readiness_v3.py','magento_catalog_factory/native_startup_readiness_v4.py','magento_catalog_factory/native_principal_header_v2.py','magento_catalog_factory/native_surface_adapter_v4.py','magento_catalog_factory/native_surface_lease_v2.py',
    'magento_catalog_factory/native_reference_bulk_price_v3.py','magento_catalog_factory/native_reference_bulk_price_v4.py',
    'magento_catalog_factory/native_reference_bulk_price_v5.py','magento_catalog_factory/native_reference_bulk_price_v6.py')))
_base_binding=_impl.public_binding

def public_binding():
    value=_base_binding();value.pop('binding_sha256')
    value.update(schema='magento-native-five-slot-source-binding-v10',
        current_document_rendered_principal_epoch='v2',viewport_target_predicates_unchanged=True,old_principal_epoch_qualification_credit=0,
        saved_baseline_from_different_startup_profile_allowed=False,
        evaluator_quote_navigation='single_click_and_explicit_editor_heading_v2',
        native_principal_source_changed=True,native_target_predicates_sql_scorer_reset_changed=False,
        old_setup_epoch_qualification_credit=0,
        native_queue_service_profile='magento-native-single-attribute-consumer-v5-bounded-native-exec-transition',
        exact_native_process_transport_decoding=True,raw_process_argv_retained=True,
        all_lazy_auditors_and_teacher_shared_base_bridges_current=True,
        teacher_adapter_module='magento_catalog_factory.native_surface_teacher_v8',
        shared_base_verifier_module='magento_catalog_factory.native_surface_shared_base_v8',
        budget_performance_module='magento_catalog_factory.native_surface_budget_performance_v10')
    return {**value,'binding_sha256':_impl.digest(_impl.final.canonical(value))}

_impl.public_binding=public_binding
def __getattr__(name):return getattr(_impl,name)
