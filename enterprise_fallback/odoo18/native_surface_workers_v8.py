"""Fresh v8 worker namespace; exact v6 worker mechanics and typed principal."""
from .native_compat_source_loader_v1 import load_source

_impl=load_source('enterprise_fallback/odoo18/native_surface_workers_v6.py',
 'enterprise_fallback.odoo18._native_surface_workers_v8_wrapper',
 '048e90f8d5c8e1a32193671405a29e17584eaaf939e2767d6504fcf8baed696f',(('v6','v8',9),))
_impl._impl.SOURCE_FILES=tuple(dict.fromkeys(_impl._impl.SOURCE_FILES+(
 'enterprise_fallback/odoo18/odoo_native_principal_witness_v7.py',
 'enterprise_fallback/odoo18/odoo_v066_native_surface_adapter_v6.py',
 'enterprise_fallback/odoo18/odoo_native_surface_evidence_v6.py',
 'enterprise_fallback/odoo18/native_surface_workers_v6.py',
 'tools/odoo_v066_native_surface_qualification_v6.py',)))

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
                    from enterprise_fallback.odoo18.odoo_native_surface_evidence_v8 import read_ref
                    capsule = json.loads(read_ref(self.adapter.store.root, guard_ref))
                    native_reason = capsule["decision"]["reason"]
                _write(self.out / "actions" / (prefix + "-rejected.private.json"), canonical({
                    "schema": "envloop-odoo-native-control-rejection-v8", "status": "rejected",
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
        additions=((_FAILURE,_FAILURE_DETAIL),)
    module=_isolate(relative,tag,binding,substitutions+additions)
    if relative=='tools/record_odoo_v066_train_gui_v1.py':
        class NativeRecorderError(RuntimeError):
            def __init__(self,code):
                super().__init__(code);self.code=code
        module.RecorderError=NativeRecorderError
    return module


_impl._impl._isolated_module=_isolated_module


def __getattr__(name):return getattr(_impl,name)
