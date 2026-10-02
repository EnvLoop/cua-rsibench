"""Fresh v6 TRAIN prerequisite and complete 20/100 owned-surface controls.

Preparation reads roster metadata and sources only. The original evaluator,
saved-state scorer, reset checks, budget and no-resume protocol remain pinned;
each accepted control must prove actual native driver success under policy v1.
"""
from __future__ import annotations

from pathlib import Path

from cursibench.native_surface_guard_policy_v1 import POLICY_SHA
from enterprise_fallback.odoo18 import native_surface_workers_v6 as workers
from enterprise_fallback.odoo18.native_compat_source_loader_v1 import load_source


_impl = load_source("tools/odoo_v066_native_material_qualification_v2.py",
    "tools._odoo_native_surface_qualification_v6",
    "391656e5aad08f9eee8975c5eb94d10970e74e44849d06383bdc8aa59e40bafb", (
        ("native_material_workers_v2", "native_surface_workers_v6", 1),
        ("envloop-odoo-v066-native-material", "envloop-odoo-v066-native-surface", 7),
        ('-v2"', '-v6"', 6),
        ("native-v2-", "native-v6-", 2),
        ("v066_native_material_controls_v2", "v066_native_surface_controls_v6", 2),
        ("native_material_saved_state_and_guard_semantics_verified_source_visual_review_pending",
         "native_surface_saved_state_and_driver_semantics_verified_source_visual_review_pending", 1),
        ("full_native_material_gui_control_semantics_verified_source_visual_review_pending",
         "full_native_surface_gui_control_semantics_verified_source_visual_review_pending", 1),
    ))


def audit_native_trace(attempt: Path, trace: dict, row: dict) -> dict:
    """Reopen the one-observation/one-current safety evidence for each control."""
    require = workers.require
    require(type(trace) is dict and trace.get("native_surface_policy_sha256") == POLICY_SHA and
            trace.get("pre_intent_rejections") == [] and
            "exact_return_guard_samples" not in trace and
            type(trace.get("actions")) is list and trace["actions"],
            "native_surface_control_trace_policy_or_rejections_invalid")
    paths, nonces = set(), set()
    images = applied = finishes = 0
    for step, item in enumerate(trace["actions"]):
        intents = sorted((Path(attempt) / "actions").glob(f"step-{step:03d}*-intent.private.json"))
        require(len(intents) == 1, "native_surface_control_intent_ambiguous")
        intent = workers.private_json(intents[0])
        action = intent.get("normalized_action")
        require(type(action) is dict and action.get("step") == step and
                type(action.get("step")) is int and intent.get("step") == step and
                intent.get("frame_id") == action.get("frame_id") and
                action["frame_id"] not in nonces,
                "native_surface_control_step_or_nonce_reused")
        nonces.add(action["frame_id"])
        controls = intent.get("observation_controls")
        require(type(controls) is list, "native_surface_control_observed_controls_missing")
        contract = item.get("contract_receipt")
        require(type(contract) is dict, "native_surface_control_contract_missing")
        capsule = contract.get("native_surface_guard")
        require(type(capsule) is dict and capsule.get("path") not in paths,
                "native_surface_control_capsule_reused")
        paths.add(capsule["path"])
        observed = workers.private_ref_bytes(attempt, item["frame"])
        result = workers.audit_native_contract(
            contract, action, observed, step, row, Path(attempt),
            observation_control_refs=sorted(control["ref"] for control in controls
                                            if control["visible"] is True and control["enabled"] is True))
        require(result.get("decision_status") == "accepted" and
                (result.get("dispatch_status") == "applied" or
                 (result.get("dispatch_status") == "finished" and action.get("type") == "finish")),
                "native_surface_control_requires_actual_applied_driver")
        images += result["guard_pngs_reopened"]
        applied += result["dispatch_status"] == "applied"
        finishes += result["dispatch_status"] == "finished"
    return {"native_guard_pngs_reopened": images,
            "native_guard_samples_retained": images,
            "native_guard_action_count": len(trace["actions"]),
            "native_surface_policy_sha256": POLICY_SHA,
            "native_surface_actual_applied_controls": applied,
            "native_surface_logical_finishes": finishes}


_impl.audit_native_trace = audit_native_trace


def __getattr__(name):
    return getattr(_impl, name)


if __name__ == "__main__":
    _impl.main()
