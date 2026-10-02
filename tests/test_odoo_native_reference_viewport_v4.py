"""Ref4 source binding and native V14 recorder checks; no live services."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
from types import CodeType
import unittest
from unittest.mock import patch

from enterprise_fallback.odoo18 import native_reference_viewport_v3 as historical_reference
from enterprise_fallback.odoo18 import native_reference_viewport_v4 as reference
from enterprise_fallback.odoo18 import native_surface_workers_v14 as workers
from tools import odoo_v066_native_reference_qualification_v4 as qualification
from tools import odoo_v066_scale_recipes_v5 as recipes
from test_odoo_native_surface_expiry_v14 import held_fixture
from test_odoo_native_surface_qualification_v14 import metadata_fixture


class Handle:
    def __init__(self, box):
        self.box = box
        self.disposed = False

    def bounding_box(self):
        return self.box

    def dispose(self):
        self.disposed = True


class Locator:
    def __init__(self, handles):
        self.handles = handles

    @property
    def first(self):
        return self

    def element_handles(self):
        return self.handles

    def bounding_box(self, *_args, **_kwargs):
        raise AssertionError("Locator auto-wait is forbidden")


def train_control_fixture(binding):
    nonce = "1" * 32
    return {
        "schema": workers.TRAIN_CONTROL_SCHEMA, "status": workers.TRAIN_CONTROL_STATUS,
        "split": "train", "family": "purchase", "run_nonce_hex": nonce,
        "run_nonce_sha256": sha256(nonce.encode()).hexdigest(),
        "native_adapter_binding_sha256": binding["native_adapter_binding"]["binding_sha256"],
        "native_worker_binding_sha256": binding["binding_sha256"],
        "independent_baseline_reward": 0.0, "independent_positive_reward": 1.0,
        "independent_wrong_object_reward": 0.0, "source_visual_review_pending": False,
        **{key: True for key in (
            "full_pre_web_filestore_reset_exact", "protected_post_web_source_bytes_equal",
            "source_attachment_readback", "original_services_restored",
            "source_visual_review_verified", "native_service_readiness_verified")},
        **{key: "f" * 64 for key in (
            "attempt_sha256", "audit_sha256", "plan_sha256", "source_review_sha256",
            "source_frame_sha256", "source_asset_sha256",
            "native_service_readiness_receipt_sha256")},
        **{key: 0 for key in (
            "old_positive_credit", "model_attempts", "official_final_tasks_admitted")},
    }


class NativeReferenceViewportV4Tests(unittest.TestCase):
    def recorder(self):
        return reference.recorder_module(workers.public_binding(), reference.reference_binding())

    def test_ref3_viewport_algorithm_and_recorder_payload_are_exactly_retained(self):
        def algorithm(code):
            # The checked loader inherits future-annotation compiler flags.
            # Compare executable content recursively, including comprehensions.
            return (code.co_code, code.co_names, code.co_varnames,
                    tuple(algorithm(value) if isinstance(value, CodeType) else value
                          for value in code.co_consts))

        self.assertIsNot(reference._impl, historical_reference)
        for name in ("resolve_optional_native_facet", "resolve_native_candidate_payload"):
            current, historical = getattr(reference, name), getattr(historical_reference, name)
            self.assertEqual(algorithm(current.__code__), algorithm(historical.__code__))
        for name in ("SELECTOR", "_SIGNATURE", "_NEW_SIGNATURE", "_PAYLOAD", "_NEW_PAYLOAD",
                     "_INTENT", "_NEW_INTENT", "_RETURN", "_NEW_RETURN",
                     "MAX_SCROLL_ACTIONS_PER_CANDIDATE"):
            self.assertEqual(getattr(reference, name), getattr(historical_reference, name))
        self.assertIs(reference.core, workers)

    def test_reference_binding_is_fresh_v14_and_rejects_ref3_or_old_credit(self):
        binding = workers.public_binding()
        actual = reference.reference_binding()
        reference.validate_reference_binding(actual)
        self.assertEqual(actual["schema"], "odoo-native-viewport-reference-source-v4")
        self.assertEqual(actual["native_actor_profile"], "native-owned-surface-safety-envelope-v14")
        self.assertEqual(actual["native_actor_binding_sha256"], binding["binding_sha256"])
        self.assertTrue(actual["same_v14_adapter_actor_scorer_reset"])
        self.assertEqual(actual["old_reference_control_credit"], 0)
        self.assertEqual((actual["max_actions"], actual["actor_seconds"]), (90, 720))
        self.assertFalse(actual["direct_locator_scroll_permitted"])
        self.assertFalse(actual["coordinate_clamping_permitted"])
        for path in ("enterprise_fallback/odoo18/native_reference_viewport_v4.py",
                     "tools/odoo_v066_native_reference_qualification_v4.py"):
            self.assertIn(path, actual["source_sha256s"])
        for changed in ({**actual, "schema": "odoo-native-viewport-reference-source-v3"},
                        {**actual, "old_reference_control_credit": 1}):
            with self.assertRaisesRegex(ValueError, "native_viewport_reference_source_changed"):
                reference.validate_reference_binding(changed)

    def test_metadata_prepare_keeps_20_20_100_and_ref4_native14_plans(self):
        for split, count in (("train", 20), ("selection", 20), ("official_hidden", 100)):
            with self.subTest(split=split):
                metadata = metadata_fixture(split)
                plan, public = qualification.prepare(metadata)
                qualification.validate_plan(plan)
                self.assertEqual(plan["schema"], "odoo-native-reference-qualification-plan-v4")
                native = plan["native_core_plan"]
                self.assertEqual(native["tasks"], metadata["tasks"])
                self.assertEqual(native["schema"], "envloop-odoo-v066-native-surface-qualification-plan-v14")
                self.assertEqual(public["task_count"], count)
                self.assertEqual(plan["historical_reference_credit"], 0)
                self.assertEqual(native["old_positive_credit"], 0)
                self.assertEqual(native["official_final_tasks_admitted"], 0)
                self.assertFalse(plan["formal_registration_performed"])
                self.assertFalse(native["automatic_replay_authorized"])
                old = {**plan, "schema": "odoo-native-reference-qualification-plan-v3"}
                with self.assertRaisesRegex(ValueError, "native_reference_epoch_plan_invalid"):
                    qualification.validate_plan(old)

    def test_candidate_and_qualification_facades_do_not_mutate_native_globals(self):
        binding = workers.public_binding()
        ref = reference.reference_binding()
        original = workers.evaluator_module(binding)
        original_journal, original_recipes = original.HoldoutJournal, original.recipes
        candidate = reference.candidate_module(binding, ref)
        self.assertIs(original.HoldoutJournal, original_journal)
        self.assertIs(original.recipes, original_recipes)
        self.assertIsNot(candidate.HoldoutJournal, original_journal)
        self.assertIs(candidate.recipes, recipes)
        self.assertEqual(candidate._native_reference_binding, ref)
        old_worker = qualification.core.run.__globals__["workers"]
        facade = qualification._facade(ref)
        self.assertIs(qualification.core.run.__globals__["workers"], old_worker)
        self.assertIsNot(facade.run.__globals__["workers"], old_worker)
        self.assertEqual(workers.public_binding(), binding)

    def test_control_eligibility_keeps_exact_0_1_0_and_rejects_v13_credit(self):
        binding = workers.public_binding()
        control = train_control_fixture(binding)
        self.assertIs(workers.validate_train_control(control, binding), control)
        for field, value in (("independent_baseline_reward", 1.0),
                             ("independent_positive_reward", 0.0),
                             ("independent_wrong_object_reward", 1.0),
                             ("old_positive_credit", 1),
                             ("schema", "envloop-odoo-v066-native-surface-train-control-v13")):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "fresh_native_train_control_required"):
                    workers.validate_train_control({**control, field: value}, binding)

    def test_optional_absent_facet_uses_actual_v14_wait_and_current_receipt(self):
        with held_fixture() as (adapter, page, _private, root):
            page.locator = lambda _selector: Locator([])
            journal = self.recorder().ActionJournal(adapter, page, root)
            journal.act("click", phase="positive", optional_facet=True)
            intent = json.loads((root / "actions/step-000-intent.private.json").read_bytes())
            self.assertEqual(intent["normalized_action"]["type"], "wait")
            self.assertEqual(intent["normalized_action"]["duration_ms"], 100)
            self.assertTrue(intent["optional_native_facet_resolution"]["actual_wait_selected_before_intent"])
            self.assertEqual(adapter.step, 1)
            self.assertEqual(page.calls, [])
            capsule = json.loads(workers.native_ref_bytes(root, journal.trace[0]["contract_receipt"]["native_surface_guard"]))
            self.assertEqual(capsule["receipt"]["status"], "applied")
            self.assertEqual(capsule["receipt"]["driver_result"], "succeeded")

    def test_guarded_scroll_then_fresh_observation_keeps_original_candidate(self):
        with held_fixture() as (adapter, page, _private, root):
            box = {"x": 765, "y": 986, "width": 70, "height": 40}
            events = []

            class CurrentHandle:
                def bounding_box(self):
                    events.append(("resolve", adapter.step))
                    return dict(box)

                def dispose(self):
                    events.append(("dispose", adapter.step))

            wheel = page.mouse.wheel

            def scroll(dx, dy):
                wheel(dx, dy)
                box["x"] -= dx
                box["y"] -= dy

            page.mouse.wheel = scroll
            observe = adapter.observe_for_model

            def current(**kwargs):
                events.append(("observe", adapter.step))
                return observe(**kwargs)

            adapter.observe_for_model = current
            journal = self.recorder().ActionJournal(adapter, page, root)
            journal.act("click", phase="positive", locator=Locator([CurrentHandle()]))
            intents = [json.loads((root / f"actions/step-{index:03d}-intent.private.json").read_bytes())
                       for index in range(2)]
            self.assertEqual([item["normalized_action"]["type"] for item in intents], ["scroll", "click"])
            self.assertEqual(intents[0]["normalized_action"]["target"], {"x": 720, "y": 500})
            self.assertEqual(intents[1]["normalized_action"]["target"], {"x": 800, "y": 526})
            self.assertNotEqual(intents[0]["frame_id"], intents[1]["frame_id"])
            self.assertEqual(events, [("observe", 0), ("resolve", 0), ("dispose", 0),
                                      ("observe", 1), ("resolve", 1), ("dispose", 1)])
            self.assertEqual(page.calls, [("move", (720, 500)), ("wheel", (0, 480)), ("click", 800, 526)])

    def test_eight_scroll_bound_and_missing_candidate_never_choose_other_control(self):
        with held_fixture() as (adapter, page, _private, root):
            journal = self.recorder().ActionJournal(adapter, page, root)
            with self.assertRaisesRegex(RuntimeError, "scroll_bound_exhausted"):
                journal.act("click", phase="positive", locator=Locator([
                    Handle({"x": 765, "y": 986, "width": 70, "height": 40})]))
            self.assertEqual(sum(call[0] == "wheel" for call in page.calls), 8)
            self.assertEqual(len(journal.trace), 8)
            self.assertFalse(any(call[0] == "click" for call in page.calls))
            self.assertFalse((root / "actions/step-008-intent.private.json").exists())
        with held_fixture() as (adapter, page, _private, root):
            journal = self.recorder().ActionJournal(adapter, page, root)
            with self.assertRaisesRegex(ValueError, "candidate_missing_or_duplicate"):
                journal.act("click", phase="positive", locator=Locator([]))
            self.assertEqual(page.calls, [])
            self.assertFalse((root / "actions/step-000-intent.private.json").exists())

    def test_reference_intent_is_v14_and_second_attempt_is_consumed_after_preflight_stop(self):
        plan, _public = qualification.prepare(metadata_fixture("selection"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            path = root / "plan.private.json"
            path.write_bytes(workers.canonical(plan))
            path.chmod(0o600)
            facade = qualification._facade(plan["reference_binding"])
            with patch.object(facade, "run", side_effect=RuntimeError("synthetic preflight stop")), \
                 patch.object(qualification._impl, "_facade", return_value=facade):
                with self.assertRaisesRegex(RuntimeError, "synthetic preflight stop"):
                    qualification.run(plan_path=path, worker_dir=root / "worker",
                                      run_dir=root / "unused", execute=True)
            nonce = plan["native_core_plan"]["run_nonce_hex"]
            intent = json.loads((root / f"{nonce}-reference-intent.private.json").read_bytes())
            self.assertEqual(intent["schema"], "odoo-native-reference-dispatch-intent-v4")
            self.assertEqual(intent["native_actor_epoch"], "v14")
            self.assertFalse(intent["same_episode_replay_authorized"])
            self.assertTrue(intent["native_scorer_reset_unchanged"])
            with self.assertRaisesRegex(ValueError, "native_qualification_refuses_overwrite"):
                qualification.run(plan_path=path, worker_dir=root / "worker",
                                  run_dir=root / "unused", execute=True)


if __name__ == "__main__":
    unittest.main()
