"""Fresh v13 worker namespace; exact v6 worker mechanics and typed principal."""
from .native_compat_source_loader_v1 import load_source

_impl=load_source('enterprise_fallback/odoo18/native_surface_workers_v6.py',
 'enterprise_fallback.odoo18._native_surface_workers_v13_wrapper',
 '048e90f8d5c8e1a32193671405a29e17584eaaf939e2767d6504fcf8baed696f',(('v6','v13',9),))
_impl._impl.SOURCE_FILES=tuple(dict.fromkeys(_impl._impl.SOURCE_FILES+(
 'enterprise_fallback/odoo18/odoo_native_principal_witness_v7.py',
 'enterprise_fallback/odoo18/odoo_v066_native_surface_adapter_v6.py',
 'enterprise_fallback/odoo18/odoo_native_surface_evidence_v6.py',
 'enterprise_fallback/odoo18/native_surface_workers_v6.py',
 'tools/odoo_v066_native_surface_qualification_v6.py',
 'enterprise_fallback/odoo18/odoo_actor_clock_v1.py',
 'enterprise_fallback/odoo18/odoo_actor_transport_v1.py',
 'enterprise_fallback/odoo18/odoo_actor_model_modules_v1.py',
 'enterprise_fallback/odoo18/native_surface_budget_performance_v13.py',
 'native_desktop_factory/actor_deadline_future_v21.py',
 'native_desktop_factory/deadline_model_transport_v21.py',
 'tools/odoo_v066_scale_recipes_v2.py',
 'enterprise_fallback/odoo18/native_reference_facet_v2.py',
 'tools/odoo_v066_scale_recipes_v4.py',
 'tools/odoo_v066_native_reference_qualification_v2.py',
 'enterprise_fallback/odoo18/native_surface_final_worker_v1.py',
 'enterprise_fallback/odoo18/native_reference_split_finalizer_v2.py',
 'enterprise_fallback/odoo18/native_surface_shared_base_v1.py',
 'tools/odoo_native_surface_final_v1.py',)))

# The preserved recorder stops on actual rejection. Save its truthful receipt
# first and retain the exact native reason, rather than projecting it as applied.
_isolate=_impl._impl._isolated_module
_DISPATCH='            applied = self.adapter.dispatch(normalized)'
_RETAIN=_DISPATCH+'''
            if applied.get("status") == "rejected":
                contract = applied.get("public_contract_receipt", {})
                guard_ref = contract.get("native_surface_guard")
                native_reason = applied.get("code")
                if guard_ref is not None:
                    from enterprise_fallback.odoo18.odoo_native_surface_evidence_v13 import read_ref
                    capsule = json.loads(read_ref(self.adapter.store.root, guard_ref))
                    native_reason = capsule["decision"]["reason"]
                _write(self.out / "actions" / (prefix + "-rejected.private.json"), canonical({
                    "schema": "envloop-odoo-native-control-rejection-v13", "status": "rejected",
                    "reason": native_reason, "model_feedback_code": applied.get("code"),
                    "normalized_action": normalized, "contract_receipt": contract,
                    "gui_driver_called": False, "nonce_invalidated": True, "turn_consumed": True,
                    "applied_inferred": False, "trusted_control_stopped": True}))
                raise RecorderError(native_reason)
'''
_FAILURE='            "error_type": type(failure).__name__,'
_FAILURE_DETAIL=_FAILURE+'''
            "error_message": str(failure),
            "error_cause_type": type(failure.__cause__).__name__ if failure.__cause__ else None,
            "error_cause_message": str(failure.__cause__) if failure.__cause__ else None,
'''


def _isolated_module(relative,tag,binding,substitutions=()):
    additions=()
    if relative=='tools/record_odoo_v066_train_gui_v1.py':
        additions=((_DISPATCH,_RETAIN),)
    if relative=='tools/odoo_v066_current_candidate_case_v5.py':
        additions=((_FAILURE,_FAILURE_DETAIL),
            ('from tools import odoo_v066_scale_recipes_v1 as recipes','from tools import odoo_v066_scale_recipes_v2 as recipes'),
            ('            negative = verify.score(case["id"])',
             '            adapter.actor_clock.end("trusted_reference_controls_complete")\n            negative = verify.score(case["id"])'))
    module=_isolate(relative,tag,binding,substitutions+additions)
    if relative=='tools/record_odoo_v066_train_gui_v1.py':
        class NativeRecorderError(RuntimeError):
            def __init__(self,code):
                super().__init__(code);self.code=code
        module.RecorderError=NativeRecorderError
    return module


_impl._impl._isolated_module=_isolated_module

_impl._impl._actor_native_original_model_modules=_impl._impl._model_modules


def _model_modules(binding):
    from .odoo_actor_model_modules_v1 import load
    return load(__import__(__name__,fromlist=['_impl']),binding)


_impl._impl._model_modules=_model_modules


_base_public_binding=_impl.public_binding

def public_binding():
    value=dict(_base_public_binding())
    value.pop('binding_sha256')
    value['source_epoch']={'native':'v13','reference':'v2','historical_control_credit':0,
        'prior_full20_and_full100_prefix_credit':0,'fresh_train_full20_full100_required':True,
        'actor_clock_dependency':'odoo_actor_model_modules_v1',
        'owned_lifecycle_schema':'odoo-owned-complete-lifecycle-v12'}
    return {**value,'binding_sha256':_impl.digest(_impl.canonical(value))}

def policy_source_registration():
    """Source-only v22 registration. Qualification remains a separate gate."""
    from cursibench.full_study_native_counterparts_v22 import register
    current=public_binding()
    return register(_impl._ROOT,cell_id='odoo-community',
        native_source_sha256s=current['source_sha256s'],
        actor_clock_source_sha256=current['source_sha256s']['enterprise_fallback/odoo18/odoo_actor_clock_v1.py'],
        native_epoch_sha256=current['binding_sha256'],qualified=False)


_impl.public_binding=public_binding
_impl._impl.public_binding=public_binding


def __getattr__(name):return getattr(_impl,name)
