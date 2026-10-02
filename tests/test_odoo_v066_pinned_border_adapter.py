from __future__ import annotations

from contextlib import nullcontext
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from cursibench.scale_action_contract import Control
from enterprise_fallback.odoo18.odoo_v066_scale_pinned_border_adapter import (
    CLASSIFICATION, OdooV066ScalePinnedBorderAdapter,
    _target_outside_pinned_border,
)
from tools import odoo_v066_scale_audit_v1 as independent
from tools import odoo_v066_scale_controller_v1 as controller
from tools import odoo_v066_scale_protocol_v1 as protocol


def png(*, blue: int = 239, third: bool = False) -> bytes:
    image = Image.new("RGB", (1440, 1000), "white")
    for x in (41, 132):
        image.putpixel((x, 419), (235, 237, blue))
    if third:
        image.putpixel((800, 400), (0, 0, 0))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class FakePage:
    def __init__(self, frames, control=None):
        self.frames = list(frames)
        self.url = "http://localhost/odoo/purchase/1"
        self.control = control or {
            "ref": "c005", "role": "input", "label": "",
            "visible": True, "enabled": True,
            "purchase_rfq_view": True,
            "bounds": [500, 470, 520, 490],
        }
        self.waits = []

    def screenshot(self, *, type: str):
        assert type == "png"
        return self.frames.pop(0)

    def wait_for_timeout(self, ms: int):
        self.waits.append(ms)

    def evaluate(self, code: str, target: dict):
        return self.control


def adapter(frames, control=None):
    observed = png()
    actor = object.__new__(OdooV066ScalePinnedBorderAdapter)
    actor.page = FakePage(frames, control)
    actor.latest_url = actor.page.url
    actor.step = 8
    actor.task_id = "private-test-task"
    actor.task_binding_sha256 = "b" * 64
    actor.frame_guard_samples = []
    actor._guard_frame_id = None
    actor._alternate_sha256 = None
    actor._pending_dispatch_action = {
        "type": "double_click", "target": {"x": 508, "y": 479}}
    actor._physical_guard_receipt = None
    actor.observed_target_control = {
        "ref": "c005", "role": "input", "label": "",
        "visible": True, "enabled": True,
        "purchase_rfq_view": True,
        "bounds": [500, 470, 520, 490],
    }
    actor.frame_guard_sink = lambda index, raw: {
        "path": f"frames/guard-{index:04d}.png",
        "sha256": sha256(raw).hexdigest(),
    }
    observation = SimpleNamespace(
        task_id=actor.task_id,
        task_binding_sha256=actor.task_binding_sha256,
        frame_id="frame-8",
        screenshot_bytes=observed,
        screenshot={"sha256": sha256(observed).hexdigest()},
        controls=(Control("c005", "input", "", True, True),),
    )
    return actor, observation


class PinnedBorderTests(unittest.TestCase):
    def test_six_identical_pinned_alternates_allow_bound_target(self):
        alternate = png(blue=240)
        actor, observation = adapter([alternate] * 7)
        self.assertTrue(actor._frame_current(observation, stage="dispatch"))
        self.assertEqual(actor.frame_guard_samples[-1]["classification"],
                         CLASSIFICATION)
        self.assertEqual(actor._physical_guard_receipt[
            "physical_frame_ref"]["sha256"], sha256(alternate).hexdigest())
        self.assertEqual(actor.page.waits, [40] * 5)

    def test_parse_does_not_accept_equivalent_pixels(self):
        actor, observation = adapter([png(blue=240)] * 6)
        self.assertFalse(actor._frame_current(observation, stage="parse"))
        self.assertIsNone(actor._physical_guard_receipt)

    def test_third_frame_fails_closed(self):
        actor, observation = adapter([png(blue=240)] * 3 +
                                     [png(blue=240, third=True)])
        self.assertFalse(actor._frame_current(observation, stage="dispatch"))
        self.assertIsNone(actor._physical_guard_receipt)
        self.assertEqual(actor.frame_guard_samples[-1]["classification"],
                         "third_or_material_frame_rejected")

    def test_target_control_must_match_observed_ref_and_exclude_border(self):
        actor, observation = adapter([png(blue=240)] * 7,
                                     {"ref": "c999", "role": "input",
                                      "label": "", "visible": True,
                                      "enabled": True,
                                      "purchase_rfq_view": True,
                                      "bounds": [500, 470, 520, 490]})
        self.assertFalse(actor._frame_current(observation, stage="dispatch"))
        self.assertIsNone(actor._physical_guard_receipt)
        self.assertFalse(_target_outside_pinned_border(
            {"type": "double_click", "target": {"x": 508, "y": 479}},
            {"ref": "c005", "role": "input", "label": "",
             "visible": True, "enabled": True,
             "purchase_rfq_view": True,
             "bounds": [20, 400, 520, 490]},
            {"ref": "c005", "role": "input", "label": "",
             "visible": True, "enabled": True,
             "purchase_rfq_view": True,
             "bounds": [20, 400, 520, 490]},
            observation))

    def test_changed_url_or_task_binding_fails(self):
        actor, observation = adapter([png(blue=240)] * 6)
        actor.page.url = "http://localhost/odoo/purchase/2"
        self.assertFalse(actor._frame_current(observation, stage="dispatch"))
        actor, observation = adapter([png(blue=240)] * 6)
        observation.task_binding_sha256 = "c" * 64
        self.assertFalse(actor._frame_current(observation, stage="dispatch"))

    def test_wrong_view_and_non_pointer_actions_fail_closed(self):
        actor, observation = adapter([png(blue=240)] * 7)
        actor.page.url = actor.latest_url = "http://localhost/odoo/sales/1"
        self.assertFalse(actor._frame_current(observation, stage="dispatch"))
        for kind in ("key", "scroll", "drag", "finish"):
            actor, observation = adapter([png(blue=240)] * 7)
            actor._pending_dispatch_action = {
                "type": kind, "target": {"x": 508, "y": 479}}
            self.assertFalse(actor._frame_current(
                observation, stage="dispatch"), kind)

    def test_forged_label_role_disabled_or_changed_target_fails(self):
        for field, value in (("label", "forged"), ("role", "button"),
                             ("enabled", False), ("ref", "c999"),
                             ("purchase_rfq_view", False)):
            actor, observation = adapter([png(blue=240)] * 7)
            actor.page.control = {**actor.page.control, field: value}
            self.assertFalse(actor._frame_current(
                observation, stage="dispatch"), field)
        actor, observation = adapter([png(blue=240)] * 7)
        actor._pending_dispatch_action["target"] = {"x": 600, "y": 479}
        self.assertFalse(actor._frame_current(observation, stage="dispatch"))

    def test_final_post_dom_screenshot_must_be_same_alternate(self):
        actor, observation = adapter([png(blue=240)] * 6 +
                                     [png(blue=240, third=True)])
        self.assertFalse(actor._frame_current(observation, stage="dispatch"))
        self.assertIsNone(actor._physical_guard_receipt)
        self.assertEqual(actor.frame_guard_samples[-1]["classification"],
                         "third_or_material_frame_rejected")

    def test_independent_audit_reopens_equivalent_dispatch_pngs_and_target(self):
        with tempfile.TemporaryDirectory() as scratch:
            attempt = Path(scratch)
            frames = attempt / "frames"
            actions = attempt / "actions"
            frames.mkdir(mode=0o700)
            actions.mkdir(mode=0o700)
            first, alternate = png(), png(blue=240)
            observed = frames / "observed.png"
            observed.write_bytes(first)
            observed.chmod(0o600)
            visible = actions / "step-000-visible.txt"
            visible_payload = {
                "controls": [{"ref": "c005", "role": "input",
                              "label": "", "visible": True,
                              "enabled": True}],
                "screenshot": {"sha256": sha256(first).hexdigest()},
                "a11y_text": "", "dom_text": "",
            }
            visible.write_bytes(protocol.canonical(visible_payload))
            visible.chmod(0o600)
            intent = actions / "step-000-intent.private.json"
            intent.write_bytes(protocol.canonical({
                "frame_id": "frame-0",
                "visible_text_ref": {
                    "path": "actions/step-000-visible.txt",
                    "sha256": sha256(visible.read_bytes()).hexdigest()},
                "observed_url": "http://localhost/odoo/purchase/1",
                "observation_controls": [{
                    "ref": "c005", "role": "input", "label": "",
                    "visible": True, "enabled": True}],
                "observed_target_control": {
                    "ref": "c005", "role": "input", "label": "",
                    "visible": True, "enabled": True,
                    "purchase_rfq_view": True,
                    "bounds": [500, 470, 520, 490]},
                "normalized_action": {
                    "type": "double_click",
                    "target": {"x": 508, "y": 479}},
            }))
            intent.chmod(0o600)
            samples = []
            for index in range(8):
                raw = first if index == 0 else alternate
                path = frames / f"guard-{index:04d}.png"
                path.write_bytes(raw)
                path.chmod(0o600)
                samples.append({
                    "step": 0,
                    "stage": "parse" if index == 0 else "dispatch",
                    "sample": 0 if index == 0 else index - 1,
                    "observed_frame_sha256": sha256(first).hexdigest(),
                    "observed_frame_id_sha256": sha256(b"frame-0").hexdigest(),
                    "sampled_frame_ref": {
                        "path": f"frames/guard-{index:04d}.png",
                        "sha256": sha256(raw).hexdigest()},
                    "classification": (
                        "exact_return" if index == 0 else
                        CLASSIFICATION if index == 7 else
                        "one_recurring_micro_raster_alternate"),
                })
            physical = {
                "profile": protocol.PINNED_BORDER_PROFILE,
                "classification": CLASSIFICATION,
                "observed_frame_sha256": sha256(first).hexdigest(),
                "observed_frame_id_sha256": sha256(b"frame-0").hexdigest(),
                "observed_url": "http://localhost/odoo/purchase/1",
                "physical_url": "http://localhost/odoo/purchase/1",
                "target_point": {"x": 508, "y": 479},
                "physical_frame_ref": samples[-1]["sampled_frame_ref"],
                "target_control": {
                    "ref": "c005", "role": "input", "label": "",
                    "visible": True, "enabled": True,
                    "purchase_rfq_view": True,
                    "bounds": [500, 470, 520, 490]},
                "pinned_pixel_coordinates": [[41, 419], [132, 419]],
            }
            trace = {
                "actions": [{
                    "step": 0,
                    "frame": {"path": "frames/observed.png",
                              "sha256": sha256(first).hexdigest()},
                    "contract_receipt": {
                        "physical_dispatch_guard": physical,
                        "action_type": "double_click",
                        "frame_id_sha256": sha256(b"frame-0").hexdigest(),
                        "control_count": 1},
                }],
                "pre_intent_rejections": [],
                "exact_return_guard_samples": samples,
            }
            independent._exact_return_chain(
                attempt, trace, require_pinned_profile=True,
                family="purchase")
            pristine = deepcopy(trace)
            physical["target_control"]["bounds"] = [20, 400, 520, 490]
            with self.assertRaisesRegex(
                    independent.ScaleAuditError,
                    "scale_pinned_physical_dispatch_target_or_pixels_invalid"):
                independent._exact_return_chain(
                    attempt, trace, require_pinned_profile=True,
                    family="purchase")
            for field, value in (("ref", "c999"), ("role", "button"),
                                 ("label", "forged"), ("enabled", False),
                                 ("purchase_rfq_view", False)):
                forged = deepcopy(pristine)
                forged["actions"][0]["contract_receipt"][
                    "physical_dispatch_guard"]["target_control"][field] = value
                with self.assertRaises(independent.ScaleAuditError,
                                       msg=field):
                    independent._exact_return_chain(
                        attempt, forged, require_pinned_profile=True,
                        family="purchase")
            for field, value in (("target_point", {"x": 600, "y": 479}),
                                 ("physical_url", "http://localhost/odoo/sales/1"),
                                 ("classification", "exact_physical_frame")):
                forged = deepcopy(pristine)
                forged["actions"][0]["contract_receipt"][
                    "physical_dispatch_guard"][field] = value
                with self.assertRaises(independent.ScaleAuditError,
                                       msg=field):
                    independent._exact_return_chain(
                        attempt, forged, require_pinned_profile=True,
                        family="purchase")
            with self.assertRaisesRegex(
                    independent.ScaleAuditError,
                    "scale_pinned_physical_dispatch_target_or_pixels_invalid"):
                independent._exact_return_chain(
                    attempt, pristine, require_pinned_profile=True,
                    family="sales")
            interleaved = deepcopy(pristine)
            interleaved["exact_return_guard_samples"][2]["step"] = 1
            with self.assertRaises(independent.ScaleAuditError):
                independent._exact_return_chain(
                    attempt, interleaved, require_pinned_profile=True,
                    family="purchase")
            forged_visible = deepcopy(visible_payload)
            forged_visible["controls"][0]["label"] = "forged"
            visible.write_bytes(protocol.canonical(forged_visible))
            saved_intent = protocol.private_json(intent)
            saved_intent["visible_text_ref"]["sha256"] = sha256(
                visible.read_bytes()).hexdigest()
            intent.write_bytes(protocol.canonical(saved_intent))
            with self.assertRaisesRegex(
                    independent.ScaleAuditError,
                    "scale_model_visible_controls_action_or_frame_unbound"):
                independent._exact_return_chain(
                    attempt, pristine, require_pinned_profile=True,
                    family="purchase")


class PinnedRetryGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.worker = self.root / "selection"
        self.private = self.worker / "private"
        self.controls = self.private / "v066_scale_controls"
        self.old = self.controls / "controls-20260929-exact-return-01"
        self.attempt = self.old / "attempt-000"
        self.attempt.mkdir(parents=True, mode=0o700)
        for path in (self.worker, self.private, self.controls,
                     self.old, self.attempt):
            path.chmod(0o700)
        self.new_plan_path = self.root / "new-plan.private.json"
        self.freeze_path = self.root / "new-freeze.json"
        self.incident_path = self.root / "second-incident.json"
        self._save(self.new_plan_path, {"split": "selection"})
        self._save(self.freeze_path, {"status": "new"})
        self._save(self.old / "batch-intent.private.json", {"old": True})
        self._save(self.attempt / "failure.private.json", {"stage": "positive_gui"})
        self._save(self.attempt / "gui_trace.json", {
            "actions": [1],
            "exact_return_guard_samples": [
                {"sampled_frame_ref": {"path": "frames/dummy.png"}}
                for _ in range(23)],
        })
        self._save(self.attempt / "actions/step-008-intent.private.json",
                   {"step": 8})
        event = {"ordinal": 0, "task_id": "case-1",
                 "package_sha256": "a" * 64, "attempt_dir": "attempt-000"}
        controller._event(self.old / "journal.private.jsonl",
                          {"event": "case_started", **event})
        self.tail = controller._event(self.old / "journal.private.jsonl",
                                      {"event": "case_failed", **event})
        self._save(self.incident_path, {
            "status": "post_intent_exact_return_exhausted_before_double_click_dispatch",
            "post_intent_mouse_action_dispatched": False,
            "old_and_new_failed_attempts_preserved": True,
            "batch_intent_sha256": self._sha(
                self.old / "batch-intent.private.json"),
            "journal_sha256": self._sha(self.old / "journal.private.jsonl"),
            "journal_tail_sha256": self.tail,
            "private_failure_sha256": self._sha(
                self.attempt / "failure.private.json"),
            "private_gui_trace_sha256": self._sha(
                self.attempt / "gui_trace.json"),
            "private_step_eight_intent_sha256": self._sha(
                self.attempt / "actions/step-008-intent.private.json"),
        })
        self._save(self.private / "baseline_snapshot.json", {"rows": [1]})
        self._save(self.private / "baseline-filestore-manifest.json",
                   {"files": ["x"]})
        self.sql_path = self.controls / \
            "selection-pinned-border-current-sql.private.json"
        self.files_path = self.controls / \
            "selection-pinned-border-current-filestore.private.json"
        self._save(self.sql_path, {"rows": [1]})
        self._save(self.files_path, {"files": ["x"]})
        events = self.private / "worker-lease-events.jsonl"
        events.write_bytes(b'{"event":"released"}\n')
        events.chmod(0o600)
        self.gate_path = self.controls / \
            "selection-pinned-border-retry-gate.private.json"
        self._save(self.gate_path, {
            "schema": controller.PINNED_RETRY_GATE_SCHEMA,
            "status":
                "two_failed_attempts_retained_current_baseline_exact_no_gui_replay",
            "physical_dispatch_profile": protocol.PINNED_BORDER_PROFILE,
            "new_private_plan_sha256": self._sha(self.new_plan_path),
            "new_source_freeze_sha256": self._sha(self.freeze_path),
            "second_failure_public_sha256": self._sha(self.incident_path),
            "old_batch_intent_sha256": self._sha(
                self.old / "batch-intent.private.json"),
            "old_journal_sha256": self._sha(
                self.old / "journal.private.jsonl"),
            "old_journal_tail_sha256": self.tail,
            "old_failure_sha256": self._sha(
                self.attempt / "failure.private.json"),
            "old_gui_trace_sha256": self._sha(
                self.attempt / "gui_trace.json"),
            "old_step_eight_intent_sha256": self._sha(
                self.attempt / "actions/step-008-intent.private.json"),
            "old_step_eight_result_exists": False,
            "prior_failed_control_count": 2,
            "current_sql_sha256": self._sha(self.sql_path),
            "current_filestore_sha256": self._sha(self.files_path),
            "worker_lease_events_sha256": self._sha(events),
            "service_state_restored": True,
            "official_final_tasks_admitted": 0,
            "model_attempts": 0,
        })
        self.plan = {
            "physical_dispatch_profile": protocol.PINNED_BORDER_PROFILE,
            "tasks": [{"task_id": "case-1", "package_sha256": "a" * 64}],
        }

    @staticmethod
    def _save(path: Path, value: dict):
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_bytes(protocol.canonical(value))
        path.chmod(0o600)

    @staticmethod
    def _sha(path: Path):
        return sha256(path.read_bytes()).hexdigest()

    def check(self):
        return controller._pinned_selection_retry_gate(
            gate_path=self.gate_path, worker=self.worker,
            plan=self.plan, private_plan_path=self.new_plan_path,
            source_freeze_path=self.freeze_path,
            old_run_dir=self.old, incident_public_path=self.incident_path,
            require_unchanged_lease_log=True)

    def test_gate_binds_second_failed_attempt_and_current_baseline(self):
        self.assertEqual(self.check()["prior_failed_control_count"], 2)
        self._save(self.attempt / "actions/step-008-result.private.json", {})
        with self.assertRaisesRegex(
                controller.ScaleControlError,
                "scale_pinned_retry_prior_failure_or_authority_changed"):
            self.check()

    def test_gate_rejects_changed_current_filestore(self):
        self._save(self.files_path, {"files": ["unexpected"]})
        with self.assertRaisesRegex(
                controller.ScaleControlError,
                "scale_pinned_retry_current_baseline_not_exact"):
            self.check()

    def test_independent_gate_matches_batch_intent(self):
        batch = {"selection_retry_gate_sha256": self._sha(self.gate_path)}
        independent._pinned_retry_gate_independent(
            worker_private=self.private, plan=self.plan,
            batch_intent=batch, private_plan_path=self.new_plan_path,
            source_freeze_path=self.freeze_path,
            incident_public_path=self.incident_path,
            old_run_dir=self.old)
        batch["selection_retry_gate_sha256"] = "0" * 64
        with self.assertRaisesRegex(
                independent.ScaleAuditError,
                "scale_independent_pinned_retry_gate_unbound"):
            independent._pinned_retry_gate_independent(
                worker_private=self.private, plan=self.plan,
                batch_intent=batch, private_plan_path=self.new_plan_path,
                source_freeze_path=self.freeze_path,
                incident_public_path=self.incident_path,
                old_run_dir=self.old)

    def test_new_journal_requires_run_specific_batch_hash(self):
        run = self.controls / "future-pinned-run"
        run.mkdir(mode=0o700)
        self._save(run / "batch-intent.private.json", {"new": True})
        controller._event(run / "journal.private.jsonl", {
            "event": "case_started", "ordinal": 0,
            "task_id": "case-1", "package_sha256": "a" * 64,
            "attempt_dir": "attempt-000",
            "run_intent_sha256": "0" * 64,
        })
        with self.assertRaisesRegex(
                controller.ScaleControlError,
                "scale_pinned_journal_not_bound_to_run_intent"):
            controller.next_case_index(run, self.plan)

    def test_live_baseline_cannot_start_before_second_failure_audit(self):
        plan = {**self.plan,
                "frame_guard_amendment": protocol.EXACT_RETURN_AMENDMENT}
        with patch.dict(os.environ, {
                "ENVLOOP_ODOO_WORKER_DIR": str(self.worker.resolve())}), \
                patch.object(controller, "_preflight",
                             return_value=(plan, self.private)), \
                patch("tools.audit_odoo_v066_selection_post_intent_stale_v1.audit",
                      return_value={"status": "not_audited"}), \
                patch.object(controller, "_modules",
                             side_effect=AssertionError(
                                 "Docker modules must not load")):
            with self.assertRaisesRegex(
                    controller.ScaleControlError,
                    "scale_pinned_retry_second_failure_not_independently_unchanged"):
                controller.prepare_selection_retry_gate(
                    worker_dir=self.worker,
                    new_private_plan_path=self.new_plan_path,
                    new_public_plan_path=self.root / "new-public.json",
                    new_source_freeze_path=self.freeze_path,
                    old_run_dir=self.old,
                    old_private_plan_path=self.root / "old-plan.json",
                    old_public_plan_path=self.root / "old-public.json",
                    old_source_freeze_path=self.root / "old-freeze.json",
                    incident_public_path=self.incident_path,
                    new_run_dir=self.controls / "future-pinned-run")

    def test_fake_cold_baseline_writes_new_gate_without_gui(self):
        from types import SimpleNamespace
        self.gate_path.unlink()
        self.sql_path.unlink()
        self.files_path.unlink()
        published = protocol.public_json(self.incident_path)
        plan = {**self.plan,
                "frame_guard_amendment": protocol.EXACT_RETURN_AMENDMENT}
        fake_modules = (
            SimpleNamespace(local_config=lambda: {"ODOO_PROJECT": "test"}),
            None,
            SimpleNamespace(filestore_manifest=lambda _volume: {"files": ["x"]}),
            SimpleNamespace(snapshot=lambda: {"rows": [1]}),
            SimpleNamespace(exclusive_worker_operation=lambda _operation:
                            nullcontext()),
        )
        with patch.dict(os.environ, {
                "ENVLOOP_ODOO_WORKER_DIR": str(self.worker.resolve())}), \
                patch.object(controller, "_preflight",
                             return_value=(plan, self.private)), \
                patch("tools.audit_odoo_v066_selection_post_intent_stale_v1.audit",
                      return_value=published), \
                patch("tools.audit_odoo_v066_selection_post_intent_stale_v1._two_pinned_pixels",
                      return_value=True), \
                patch.object(controller, "_modules", return_value=fake_modules), \
                patch.object(controller, "_run_lock",
                             return_value=nullcontext()), \
                patch.object(controller, "_running_services_without_compose_blank",
                             return_value=set()), \
                patch.object(controller.train_recorder, "_compose") as compose:
            result = controller.prepare_selection_retry_gate(
                worker_dir=self.worker,
                new_private_plan_path=self.new_plan_path,
                new_public_plan_path=self.root / "new-public.json",
                new_source_freeze_path=self.freeze_path,
                old_run_dir=self.old,
                old_private_plan_path=self.root / "old-plan.json",
                old_public_plan_path=self.root / "old-public.json",
                old_source_freeze_path=self.root / "old-freeze.json",
                incident_public_path=self.incident_path,
                new_run_dir=self.controls / "future-pinned-run")
        self.assertEqual(result["status"],
                         "same_id_retry_preflight_ready_no_gui_dispatched")
        self.assertEqual(compose.call_count, 2)
        self.assertEqual(protocol.private_json(self.controls /
            "selection-pinned-border-retry-gate.private.json")
            ["prior_failed_control_count"], 2)


class ValidatorRunIdentityTests(unittest.TestCase):
    def test_nonce_and_failure_receipt_bind_new_failed_journal(self):
        with tempfile.TemporaryDirectory() as scratch:
            run = Path(scratch) / "run"
            attempt = run / "attempt-000"
            attempt.mkdir(parents=True, mode=0o700)
            for path in (run, attempt):
                path.chmod(0o700)
            batch_path = run / "batch-intent.private.json"
            batch_path.write_bytes(protocol.canonical({
                "run_nonce_hex": "a" * 32}))
            batch_path.chmod(0o600)
            failure_path = attempt / "failure.private.json"
            failure_path.write_bytes(protocol.canonical({"status": "failed"}))
            failure_path.chmod(0o600)
            batch_sha = sha256(batch_path.read_bytes()).hexdigest()
            case = {"ordinal": 0, "task_id": "case-1",
                    "package_sha256": "b" * 64,
                    "attempt_dir": "attempt-000",
                    "run_intent_sha256": batch_sha}
            controller._event(run / "journal.private.jsonl",
                              {"event": "case_started", **case})
            controller._event(run / "journal.private.jsonl", {
                "event": "case_failed", **case,
                "failure_receipt_sha256": sha256(
                    failure_path.read_bytes()).hexdigest()})
            plan = {"physical_dispatch_profile":
                    protocol.PINNED_BORDER_PROFILE,
                    "validator_amendment": protocol.VALIDATOR_V066_AMENDMENT,
                    "task_count": 1,
                    "tasks": [{"task_id": "case-1",
                               "package_sha256": "b" * 64}]}
            with self.assertRaisesRegex(
                    controller.ScaleControlError,
                    "scale_failed_case_requires_manual_reconciliation"):
                controller.next_case_index(run, plan)
            failure_path.write_bytes(protocol.canonical({"status": "changed"}))
            with self.assertRaisesRegex(
                    controller.ScaleControlError,
                    "scale_validator_failed_case_receipt_unbound"):
                controller.next_case_index(run, plan)
            batch_path.write_bytes(protocol.canonical({"run_nonce_hex": "bad"}))
            with self.assertRaisesRegex(
                    controller.ScaleControlError,
                    "scale_validator_run_nonce_missing"):
                controller.next_case_index(run, plan)


if __name__ == "__main__":
    unittest.main()
