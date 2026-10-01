"""Reference-only optional native facet resolution after the actual observation."""
from hashlib import sha256
import json
import sys
from pathlib import Path
from types import FunctionType,ModuleType
from . import native_surface_workers_v13 as core

ROOT=Path(__file__).resolve().parents[2]
SELECTOR='.o_searchview .o_facet_remove'
REFERENCE_FILES=('enterprise_fallback/odoo18/native_reference_facet_v2.py',
 'tools/odoo_v066_scale_recipes_v4.py','tools/odoo_v066_native_reference_qualification_v2.py')
_SIGNATURE='''    def act(self, kind: str, *, phase: str, locator=None,
            ref: str | None = None, memory: str = "", **fields) -> dict:'''
_NEW_SIGNATURE='''    def act(self, kind: str, *, phase: str, locator=None,
            ref: str | None = None, memory: str = "", optional_facet: bool = False, **fields) -> dict:'''
_PAYLOAD='''            payload = {"type": kind, **fields}
            if ref is not None:'''
_NEW_PAYLOAD='''            payload = {"type": kind, **fields}
            optional_resolution = None
            if optional_facet:
                require(kind == "click" and locator is None and ref is None and not fields,
                        "optional_facet_reference_signature_invalid")
                box, optional_resolution = _resolve_optional_native_facet(self.page)
                if box is None:
                    payload = {"type": "wait", "duration_ms": 100}
                else:
                    payload["target"] = {"x": int(box["x"] + box["width"] / 2),
                                         "y": int(box["y"] + box["height"] / 2)}
            elif ref is not None:'''
_INTENT='''                "dispatch_state": "intent_durable_before_gui_action",'''
_NEW_INTENT=_INTENT+'''
                "optional_native_facet_resolution": optional_resolution,'''


def reference_binding():
    value={'schema':'odoo-native-optional-facet-reference-source-v2','native_actor_profile':core.public_binding()['profile'],
        'native_actor_binding_sha256':core.public_binding()['binding_sha256'],'same_v13_adapter_actor_scorer_reset':True,
        'native_selector':SELECTOR,'absent_candidate_action':{'type':'wait','duration_ms':100},
        'resolution_after_actual_observation_before_intent':True,'max_actions':90,'actor_seconds':720,
        'old_reference_control_credit':0,'source_sha256s':{p:sha256((ROOT/p).read_bytes()).hexdigest() for p in REFERENCE_FILES}}
    return {**value,'reference_binding_sha256':core.digest(core.canonical(value))}


def validate_reference_binding(value):
    core.require(value==reference_binding(),'native_optional_facet_reference_source_changed');return value


def resolve_optional_native_facet(page):
    """Immediate currently matching handles; no locator auto-wait or GUI IO."""
    handles=page.locator(SELECTOR).first.element_handles()
    core.require(len(handles)<=1,'native_optional_facet_duplicate_handle')
    if not handles:return None,{'status':'absent_after_observation','actual_wait_selected_before_intent':True,'matched_handles':0}
    handle=handles[0]
    try:box=handle.bounding_box()
    finally:handle.dispose()
    if box is None or box['width']<=0 or box['height']<=0:
        return None,{'status':'not_visible_after_observation','actual_wait_selected_before_intent':True,'matched_handles':1}
    return box,{'status':'native_current_unique_handle','actual_wait_selected_before_intent':False,'matched_handles':1,'bounds':box}


def recorder_module(binding,reference):
    core.validate_binding(binding);validate_reference_binding(reference)
    module=core._impl._impl._isolated_module('tools/record_odoo_v066_train_gui_v1.py','optional-facet-reference-v2',binding,
        ((core._impl._impl._surface_recorder_applied,core._impl._impl._surface_recorder_checked),
         (_SIGNATURE,_NEW_SIGNATURE),(_PAYLOAD,_NEW_PAYLOAD),(_INTENT,_NEW_INTENT)))
    module._resolve_optional_native_facet=resolve_optional_native_facet
    module.MAX_PRE_INTENT_STALE_OBSERVATIONS=1
    return module


def candidate_module(binding,reference):
    """Fresh source-pinned evaluator namespace; no existing globals changed."""
    core.validate_binding(binding);validate_reference_binding(reference)
    original=core.evaluator_module
    globals_copy=dict(original.__globals__)
    isolate=globals_copy['_isolated_module']
    def reference_isolate(relative,tag,actual_binding,substitutions=()):
        if relative=='tools/record_odoo_v066_train_gui_v1.py':
            return recorder_module(actual_binding,reference)
        if relative=='tools/odoo_v066_current_candidate_case_v5.py':
            old='from tools import odoo_v066_scale_recipes_v1 as recipes'
            # The exact v13 loader retains its v1->v2 replacement. The explicit
            # final import selects v4 in the fresh evaluator's globals.
            replacement=old+'\nfrom tools import odoo_v066_scale_recipes_v4 as recipes'
            return isolate(relative,'optional-facet-case-v2',actual_binding,substitutions+((old,replacement),))
        return isolate(relative,tag,actual_binding,substitutions)
    globals_copy['_isolated_module']=reference_isolate
    selected=FunctionType(original.__code__,globals_copy,original.__name__,original.__defaults__,original.__closure__)
    module=selected(binding)
    module._native_reference_binding=reference
    return module
