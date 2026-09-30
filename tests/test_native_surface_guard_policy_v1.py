import copy
from dataclasses import FrozenInstanceError, asdict
import hashlib
from pathlib import Path
import tempfile
import unittest

from cursibench import native_surface_guard_policy_v1 as guard


def ref(kind, path=None, payload=b"saved native evidence"):
    return {"schema": "native-guard-artifact-ref-v1", "path": path or f"evidence/{kind}.private",
            "sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload), "kind": kind}


def lease():
    return {"schema": "native-surface-lease-v1", "lease_id": "lease-1", "cell_id": "odoo-original",
            "account_sha256": "a" * 64, "workspace_sha256": "b" * 64,
            "window_sha256": "c" * 64, "owner_sha256": "d" * 64,
            "issued_at": 1.0, "expires_at": 200.0, "evidence": ref("lease_evidence")}


def envelope(phase):
    return {"schema": "native-surface-envelope-v1", "policy_sha256": guard.POLICY_SHA,
            "phase": phase, "lease": lease(), "task_id": "visible-task-1",
            "task_binding_sha256": "e" * 64, "frame_id": "nonce-123", "step": 3,
            "captured_at": 10.0 if phase == "observation" else 20.0, "expires_at": 100.0,
            "viewport": [1000, 700], "view_id": "purchase-form", "modal_id": "none",
            "focus_id": "field-1", "allowed_views": ["purchase-form", "product-form"],
            "allowed_modals": ["none", "save-format"], "allowed_focus": ["field-1", "field-2"],
            "owned_surface": True, "targets": [
                {"ref": "field-1", "bounds": [20, 30, 200, 40], "visible": True,
                 "enabled": True, "obscured": False, "keyboard": True,
                 "actions": ["click", "double_click", "type", "key", "scroll", "drag"]},
                {"ref": "field-2", "bounds": [300, 30, 200, 40], "visible": True,
                 "enabled": True, "obscured": False, "keyboard": True,
                 "actions": ["click", "type", "key"]}],
            "raw_image": ref(f"raw_{phase}_image"), "raw_envelope": ref(f"native_{phase}_envelope")}


def action(kind="click", **extra):
    result = {"version": "scale-computer-use-v0.6", "task_id": "visible-task-1",
              "task_binding_sha256": "e" * 64, "frame_id": "nonce-123", "step": 3,
              "type": kind, "memory": ""}
    if kind in ("click", "double_click"):
        result["target"] = {"x": 50, "y": 50}
    result.update(extra)
    return result


def active(bound_lease):
    return {"schema": "native-surface-lease-check-v1", "lease_sha256": guard.digest(bound_lease),
            "status": "active", "checked_at": 21.0, "expires_at": 50.0, "evidence": ref("lease_check")}


class NativeSurfaceGuardTests(unittest.TestCase):
    def setUp(self):
        self.obs = envelope("observation")
        self.cur = envelope("predispatch")

    def decide(self, value=None, check=active):
        return guard.decision(self.obs, self.cur, value or action(), lease_check=check, now=22.0)

    def test_different_raw_pixels_and_safe_wrong_target_are_accepted(self):
        self.cur["raw_image"] = ref("raw_predispatch_image", payload=b"different pixels and task values")
        proposed = action(target={"x": 350, "y": 50})
        saved = copy.deepcopy(proposed)
        result = self.decide(proposed)
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["action_sha256"], guard.digest(saved))
        self.assertEqual(proposed, saved)
        self.assertFalse(result["driver_called"])
        self.assertTrue(result["consume_turn"])
        self.assertTrue(result["invalidate_nonce"])
        self.assertNotEqual(result["evidence"]["observation_image"]["sha256"],
                            result["evidence"]["predispatch_image"]["sha256"])

    def test_policy_and_nested_validated_objects_are_immutable(self):
        with self.assertRaises(TypeError):
            guard.POLICY["retarget_action"] = True
        self.assertIsInstance(guard.POLICY["bindings"], tuple)
        parsed = guard.validate_envelope(self.obs)
        with self.assertRaises(FrozenInstanceError):
            parsed.step = 4
        self.obs["targets"][0]["bounds"][0] = 999
        self.assertEqual(parsed.targets[0].bounds[0], 20)
        self.assertEqual(guard.digest(parsed), guard.digest(asdict(parsed)))

    def test_nonce_task_package_and_step_changes_are_rejected(self):
        for key, value in (("frame_id", "old-nonce"), ("task_id", "other-task"),
                           ("task_binding_sha256", "f" * 64), ("step", 4), ("step", True)):
            with self.subTest(key=key, value=value):
                result = self.decide(action(**{key: value}))
                self.assertEqual(result["status"], "rejected")
                self.assertEqual(result["reason"], "stale_nonce_or_task")

    def test_expired_observation_rejects_without_dispatch(self):
        self.obs["expires_at"] = 21.5
        self.assertEqual(self.decide()["reason"], "expired_observation")

    def test_lost_ownership_or_changed_lease_hard_stops(self):
        for change in (lambda x: x.update(owned_surface=False),
                       lambda x: x["lease"].update(workspace_sha256="f" * 64),
                       lambda x: x["lease"].update(window_sha256="f" * 64),
                       lambda x: x["lease"].update(account_sha256="f" * 64)):
            self.cur = envelope("predispatch")
            change(self.cur)
            result = self.decide()
            self.assertEqual((result["status"], result["reason"]), ("hard_stop", "ownership_changed"))

    def test_real_callback_required_boolean_and_wrong_binding_fail(self):
        for check in (lambda _: True, lambda _: {"active": True},
                      lambda x: {**active(x), "lease_sha256": "f" * 64}):
            result = self.decide(check=check)
            self.assertEqual((result["status"], result["reason"]), ("hard_stop", "invalid_lease_check"))

    def test_inactive_stale_and_expired_callback_checks_fail(self):
        for values in ({"status": "inactive"}, {"checked_at": 19.0}, {"expires_at": 21.5}):
            result = self.decide(check=lambda x: {**active(x), **values})
            self.assertEqual(result["reason"], "lease_inactive_or_stale")

    def test_changed_allowed_scope_is_hard_stop(self):
        self.cur["allowed_views"].append("account-home")
        self.assertEqual(self.decide()["reason"], "policy_scope_changed")

    def test_disallowed_context_hard_stops_allowed_transition_rejects(self):
        self.cur["view_id"] = "account-home"
        self.assertEqual(self.decide()["status"], "hard_stop")
        self.cur["view_id"] = "product-form"
        self.assertEqual(self.decide()["reason"], "native_context_changed")
        self.cur["view_id"] = "purchase-form"
        self.cur["modal_id"] = "save-format"
        self.assertEqual(self.decide()["reason"], "native_context_changed")

    def test_focus_change_rejects_keyboard_but_not_safe_pointer(self):
        self.cur["focus_id"] = "field-2"
        self.assertEqual(self.decide()["status"], "accepted")
        self.assertEqual(self.decide(action("key", key="Enter"))["reason"], "editable_focus_changed_or_unsafe")

    def test_targeted_keyboard_uses_verified_editable_target_without_relocation(self):
        self.cur["focus_id"] = "field-2"
        for kind, extra in (("type", {"text": "model proposal", "mode": "fill"}),
                            ("key", {"key": "Enter"})):
            proposed = action(kind, target={"x": 50, "y": 50}, **extra)
            self.assertEqual(self.decide(proposed)["status"], "accepted")
            self.cur["targets"][0]["keyboard"] = False
            self.assertEqual(self.decide(proposed)["reason"], "target_not_current_and_safe")
            self.cur["targets"][0]["keyboard"] = True
        self.assertIn("focus_recheck", guard.POLICY["targeted_keyboard"])

    def test_unsafe_focus_and_disabled_editable_target_reject(self):
        for update in ({"enabled": False}, {"visible": False}, {"obscured": True}, {"keyboard": False}):
            self.cur = envelope("predispatch")
            self.cur["targets"][0].update(update)
            self.assertEqual(self.decide(action("type", text="model mistake", mode="insert"))["status"], "rejected")

    def test_coordinate_is_not_relocated_and_ref_must_stay_safe(self):
        self.cur["targets"][0]["bounds"] = [20, 100, 200, 40]
        self.assertEqual(self.decide()["reason"], "target_not_current_and_safe")
        self.cur["targets"][0]["enabled"] = False
        self.assertEqual(self.decide(action(target={"ref": "field-1"}))["reason"], "target_not_current_and_safe")

    def test_broad_canvas_cannot_override_unsafe_smaller_control(self):
        for env in (self.obs, self.cur):
            env["targets"].append({"ref": "canvas", "bounds": [0, 0, 1000, 700],
                                   "visible": True, "enabled": True, "obscured": False,
                                   "keyboard": False, "actions": ["click"]})
        for update in ({"enabled": False}, {"visible": False}, {"obscured": True},
                       {"actions": ["type"]}):
            with self.subTest(update=update):
                saved = copy.deepcopy(self.cur["targets"][0])
                self.cur["targets"][0].update(update)
                self.assertEqual(self.decide()["reason"], "target_not_current_and_safe")
                self.cur["targets"][0] = saved

    def test_ambiguous_equally_specific_coordinate_targets_fail_closed(self):
        other = copy.deepcopy(self.cur["targets"][0])
        other["ref"] = "overlay-same-bounds"
        self.cur["targets"].append(other)
        self.assertEqual(self.decide()["reason"], "target_not_current_and_safe")

    def test_drag_checks_both_endpoints_and_allowed_action(self):
        proposed = action("drag", **{"from": {"x": 50, "y": 50}, "to": {"x": 350, "y": 50}})
        self.assertEqual(self.decide(proposed)["status"], "rejected")
        for env in (self.obs, self.cur):
            env["targets"][1]["actions"].append("drag")
        self.assertEqual(self.decide(proposed)["status"], "accepted")

    def test_raw_paths_must_be_distinct_even_when_bytes_match(self):
        self.cur["raw_image"]["path"] = self.obs["raw_image"]["path"]
        self.assertEqual(self.decide()["reason"], "evidence_path_reused")

    def test_answer_label_value_extra_fields_are_rejected(self):
        for key in ("label", "value", "expected_answer", "gold"):
            env = copy.deepcopy(self.obs)
            env["targets"][0][key] = "private task answer"
            with self.assertRaises(guard.GuardError):
                guard.validate_envelope(env)

    def test_strict_envelope_rejects_booleans_duplicate_refs_and_nan(self):
        for mutate in (lambda x: x.update(step=True), lambda x: x.update(captured_at=float("nan")),
                       lambda x: x["viewport"].__setitem__(0, True),
                       lambda x: x["targets"].append(copy.deepcopy(x["targets"][0]))):
            env = copy.deepcopy(self.obs)
            mutate(env)
            with self.assertRaises(guard.GuardError):
                guard.validate_envelope(env)

    def test_artifact_content_reopened_and_tamper_detected(self):
        payload = b"full raw native image"
        value = ref("raw_observation_image", "image.private", payload)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "image.private"
            path.write_bytes(payload)
            self.assertEqual(guard.verify_artifact(tmp, value).sha256, value["sha256"])
            path.write_bytes(b"replaced same length")
            with self.assertRaises(guard.GuardError):
                guard.verify_artifact(tmp, value)

    def test_artifact_traversal_and_symlink_rejected(self):
        for path in ("../raw.png", "/tmp/raw.png", "a//b", "a/./b", "a\\b"):
            with self.assertRaises(guard.GuardError):
                guard.validate_artifact_ref(ref("raw_observation_image", path))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "target").write_bytes(b"saved native evidence")
            (root / "link").symlink_to(root / "target")
            with self.assertRaises(guard.GuardError):
                guard.verify_artifact(root, ref("raw_observation_image", "link"))

    def receipt(self, status="applied", driver="succeeded"):
        return {"schema": "native-surface-dispatch-receipt-v1", "policy_sha256": guard.POLICY_SHA,
                "decision_sha256": "a" * 64, "action_sha256": "b" * 64, "frame_id": "nonce-123",
                "step": 3, "status": status, "reason": "driver-returned", "turn_consumed": True,
                "nonce_invalidated": True, "intent": ref("action_intent"), "driver_result": driver,
                "driver_evidence": ref("driver_result")}

    def test_applied_needs_intent_nonce_turn_and_actual_driver_evidence(self):
        self.assertEqual(guard.validate_receipt(self.receipt())["status"], "applied")
        for update in ({"intent": None}, {"driver_result": "unknown"}, {"driver_result": "not_attempted"},
                       {"driver_evidence": None}, {"turn_consumed": False}, {"nonce_invalidated": False}):
            with self.assertRaises(guard.GuardError):
                guard.validate_receipt({**self.receipt(), **update})

    def test_rejection_never_claims_driver_or_intent_and_uncertainty_is_failed(self):
        rejected = {**self.receipt("rejected", "not_attempted"), "intent": None, "driver_evidence": None}
        self.assertEqual(guard.validate_receipt(rejected)["status"], "rejected")
        self.assertEqual(guard.validate_receipt(self.receipt("failed", "unknown"))["status"], "failed")
        with self.assertRaises(guard.GuardError):
            guard.validate_receipt({**rejected, "driver_result": "succeeded"})

    def test_recovery_feedback_is_truthful_versioned_and_not_a_success_projection(self):
        self.cur["focus_id"] = "field-2"
        result = self.decide(action("key", key="Enter"))
        feedback = guard.rejection_feedback(result)
        self.assertEqual(feedback, {"version": guard.FEEDBACK_VERSION, "status": "rejected",
                                    "code": "editable_focus_changed_or_unsafe"})
        for update in ({"status": "accepted"}, {"status": "hard_stop"}, {"driver_called": True},
                       {"consume_turn": False}, {"invalidate_nonce": False}, {"reason": "ok"}):
            with self.assertRaises(guard.GuardError):
                guard.rejection_feedback({**result, **update})


if __name__ == "__main__":
    unittest.main()
