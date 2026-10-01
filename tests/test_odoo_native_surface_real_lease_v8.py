"""Real Unix lease + production adapter/auditor, with fake native UI only."""
from contextlib import contextmanager
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image
from cursibench import native_surface_guard_policy_v1 as policy
from enterprise_fallback.odoo18 import native_surface_workers_v8 as workers
from enterprise_fallback.odoo18 import odoo_v066_native_surface_adapter_v8 as native
import factory
import worker_lease


class NativePageFixture:
    viewport_size = {"width": 1440, "height": 1000}

    def __init__(self):
        self.url = "http://127.0.0.1:8069/odoo/purchase/42"
        self.focus = "price"
        self.uid = "res.partner:7"
        self.calls = []
        self.capture = 0
        import time
        self.tick = time.monotonic()
        self.events = {}
        self.busy = False
        self.disabled = False
        self.waits = 0
        self.when_wait = None
        self.mouse = SimpleNamespace(click=self.click, dblclick=self.click,
            move=lambda *args, **kwargs: self.calls.append(("move", args)),
            down=lambda: self.calls.append(("down",)), up=lambda: self.calls.append(("up",)),
            wheel=lambda *args: self.calls.append(("wheel", args)))
        self.keyboard = SimpleNamespace(press=lambda key: self.calls.append(("press", key)),
                                        insert_text=lambda text: self.calls.append(("insert_text", text)))

    def click(self, x, y):
        self.calls.append(("click", x, y))
        self.focus = "price" if x < 300 else "body"

    def on(self, name, callback):
        self.events[name] = callback

    def wait_for_timeout(self, duration):
        self.tick += duration / 1000
        self.waits += 1
        if self.when_wait: self.when_wait(self.waits)

    def screenshot(self, **kwargs):
        image = Image.new("RGB", (1440, 1000), "white")
        image.putpixel((1200, 900), (self.capture % 255, 20, 30))
        self.capture += 1
        buffer = BytesIO()
        image.save(buffer, "PNG")
        return buffer.getvalue()

    def evaluate(self, script, points=None):
        if script == native.BUSY_JS:
            return {"schema":"odoo-generic-native-loading-v8","document_ready":True,"action_view_count":1,"busy":[{"aria_busy":"true"}] if self.busy else []}
        if script == native.VISIBLE_CONTROLS_JS:
            return [{"ref": "price", "role": "input", "label": "Fixture price", "visible": True, "enabled": True},
                    {"ref": "save", "role": "button", "label": "Fixture save", "visible": True, "enabled": True}]
        if script != native.NATIVE_CONTEXT_JS:
            raise AssertionError("Unexpected native script in source-only fixture")
        price = {"ref": "price", "bounds": [20, 30, 200, 40], "visible": True, "enabled": True,
                 "obscured": False, "keyboard": True, "actions": ["click", "double_click", "type", "key", "scroll", "drag"],
                 "tag": "input", "type": "text", "name": "price_unit", "value": "17.5"}
        save = {"ref": "save", "bounds": [320, 30, 100, 40], "visible": True, "enabled": True,
                "obscured": False, "keyboard": False, "actions": ["click", "double_click", "scroll", "drag"],
                "tag": "button", "type": "button", "name": "", "value": None}
        save["enabled"] = not self.disabled
        hits = []
        for index, point in enumerate(points or []):
            base = price if point["x"] < 300 else save
            hits.append({**base, "ref": f"point-{index}", "bounds": [point["x"], point["y"], 1, 1]})
        focus = {"ref": self.focus, "tag": "input" if self.focus == "price" else "body",
                 "type": "text" if self.focus == "price" else "", "name": "price_unit" if self.focus == "price" else "",
                 "editable": self.focus == "price", "bounds": price["bounds"] if self.focus == "price" else [0, 0, 1440, 1000],
                 "value": "17.5" if self.focus == "price" else None}
        return {"schema": "odoo-current-native-surface-v8", "visible": True, "top_window": True,
                "app_shell": True, "account_principal": self.uid, "principal_witness": {"selector":".o_main_navbar .o_user_menu img.o_user_avatar","total":1,"visible_count":1,"nodes":[{"src":"http://127.0.0.1:8069/web/image/res.partner/7/avatar_128","current_src":"http://127.0.0.1:8069/web/image/res.partner/7/avatar_128","visible":True,"complete":True,"natural_width":28}]}, "route_path": __import__('urllib.parse',fromlist=['urlsplit']).urlsplit(self.url).path,
                "viewport": [1440, 1000], "focus": focus, "targets": [price, save], "hits": hits, "modals": []}


@contextmanager
def held_fixture():
    """Only PRIVATE/config are projected; lock implementation and PID are real."""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        root.chmod(0o700)
        private, artifacts = root / "private", root / "artifacts"
        private.mkdir(mode=0o700)
        artifacts.mkdir(mode=0o700)
        credentials = private / "actor_credentials.json"
        credentials.write_text(json.dumps({"login": "source-fixture-actor", "password": "synthetic-fixture"}))
        credentials.chmod(0o600)
        with patch.object(factory, "PRIVATE", private), patch.object(worker_lease, "PRIVATE", private), \
             patch.object(factory, "local_config", return_value={"ODOO_PORT": "8069", "ODOO_PROJECT": "source_fixture"}):
            with worker_lease.exclusive_worker_operation("source_fixture", root=private):
                page = NativePageFixture()
                adapter = native.OdooV066NativeSurfaceAdapter(page, task_id="source-fixture",
                    task_binding_sha256="a" * 64, instruction="Synthetic source-only worker fixture")
                adapter.clock = lambda: page.tick
                adapter._last_native_request=page.tick
                with patch('time.monotonic',lambda:page.tick):
                    adapter.bind_guard(root=artifacts, worker_private=private)
                    yield adapter, page, private, artifacts


class RealLeaseIntegrationTests(unittest.TestCase):
    def audit(self, root, observation, action, result):
        return workers.audit_native_contract(result["public_contract_receipt"], action,
            observation.screenshot_bytes, observation.step,
            {"task_id": "source-fixture", "package_sha256": "a" * 64}, root,
            observation_control_refs=sorted(control.ref for control in observation.controls if control.visible and control.enabled))

    def test_real_lease_binding_and_applied_driver_evidence_reopen(self):
        with held_fixture() as (adapter, page, private, root):
            worker_lease.require_worker_lease(root=private)
            lock = json.loads((private / "worker-operation.lock").read_bytes())
            bound = json.loads((root / "surface-guard/lease-boundary.private.json").read_bytes())
            self.assertEqual(bound["lock_owner"], lock)
            observation, _ = adapter.observe_for_model()
            action = adapter.parse_current_action('{"type":"click","target":{"x":50,"y":50}}')
            result = adapter.dispatch(action)
            self.assertEqual(result["status"], "applied")
            self.assertEqual(page.calls, [("click", 50, 50)])
            audited = self.audit(root, observation, action, result)
            self.assertEqual(audited["dispatch_status"], "applied")
            self.assertEqual(audited["guard_pngs_reopened"], 2)
            capsule = json.loads(workers.native_ref_bytes(root, result["public_contract_receipt"]["native_surface_guard"]))
            self.assertNotEqual(capsule["observed"]["raw_image"]["sha256"], capsule["current"]["raw_image"]["sha256"])
            self.assertTrue((root / "surface-guard/nonces" / (observation.frame_id + ".consumed.private.json")).is_file())

    def test_native_focus_rejection_new_turn_and_logical_finish(self):
        with held_fixture() as (adapter, page, private, root):
            observation, _ = adapter.observe_for_model()
            action = adapter.parse_current_action('{"type":"key","key":"Enter"}')
            page.focus = "body"
            result = adapter.dispatch(action)
            self.assertEqual(result["status"], "rejected")
            self.assertEqual(page.calls, [])
            self.assertEqual(self.audit(root, observation, action, result)["dispatch_status"], "rejected")
            next_observation, rendered = adapter.observe_for_model()
            self.assertEqual(next_observation.step, 1)
            self.assertNotEqual(next_observation.frame_id, observation.frame_id)
            self.assertEqual(next_observation.previous_action_result["status"], "rejected")
            self.assertIn('"status":"rejected"', rendered["instruction"])
            finish = adapter.parse_current_action('{"type":"finish"}')
            finished = adapter.dispatch(finish)
            self.assertEqual(finished["status"], "finished")
            self.assertEqual(self.audit(root, next_observation, finish, finished)["dispatch_status"], "finished")
            self.assertEqual(page.calls, [])

    def test_targeted_typing_checks_actual_focus_after_native_target_click(self):
        with held_fixture() as (adapter, page, private, root):
            page.focus = "body"
            observation, _ = adapter.observe_for_model()
            action = adapter.parse_current_action(
                '{"type":"type","target":{"x":50,"y":50},"mode":"fill","text":"19.25"}')
            result = adapter.dispatch(action)
            self.assertEqual(result["status"], "applied")
            self.assertEqual(page.calls, [("click", 50, 50), ("press", "Meta+A"), ("insert_text", "19.25")])
            self.assertEqual(self.audit(root, observation, action, result)["dispatch_status"], "applied")
            capsule = json.loads(workers.native_ref_bytes(root, result["public_contract_receipt"]["native_surface_guard"]))
            driver = json.loads(workers.native_ref_bytes(root, capsule["receipt"]["driver_evidence"]))
            keyboard = [row for row in driver["calls"] if row["operation"] in ("press", "insert_text")]
            self.assertEqual(len(keyboard), 2)
            for row in keyboard:
                evidence = json.loads(workers.native_ref_bytes(root, row["keyboard_scope"]))
                self.assertEqual(evidence["focus"]["ref"], "price")
                self.assertTrue(evidence["focus"]["editable"])

    def test_changed_real_lock_or_credentials_hard_stop_before_driver(self):
        for change in ("credentials", "lock"):
            with self.subTest(change=change), held_fixture() as (adapter, page, private, root):
                adapter.observe_for_model()
                action = adapter.parse_current_action('{"type":"click","target":{"x":50,"y":50}}')
                path = private / ("actor_credentials.json" if change == "credentials" else "worker-operation.lock")
                path.write_bytes(path.read_bytes() + b" ")
                with self.assertRaises(native.GuardHardStop):
                    adapter.dispatch(action)
                self.assertEqual(page.calls, [])
                capsule = json.loads((root / "surface-guard/turn-000/receipt.private.json").read_bytes())
                self.assertEqual(capsule["decision"]["status"], "hard_stop")
                self.assertEqual(capsule["receipt"]["driver_result"], "not_attempted")

    def test_missing_actual_registry_cannot_bind_from_lock_file_alone(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            private = root / "private"
            private.mkdir(mode=0o700)
            for name, payload in (("worker-operation.lock", {"pid": os.getpid(), "operation": "source_fixture"}),
                                  ("actor_credentials.json", {"login": "source-fixture-actor"})):
                path = private / name
                path.write_text(json.dumps(payload))
                path.chmod(0o600)
            with patch.object(factory, "PRIVATE", private), patch.object(worker_lease, "PRIVATE", private):
                adapter = native.OdooV066NativeSurfaceAdapter(NativePageFixture(), task_id="source-fixture",
                    task_binding_sha256="a" * 64, instruction="Synthetic source fixture")
                with self.assertRaises(worker_lease.WorkerBusyError):
                    adapter.bind_guard(root=root, worker_private=private)

    def test_saved_qualification_trace_reopens_actual_control_capsules(self):
        from tools import odoo_v066_native_surface_qualification_v8 as qualification
        with held_fixture() as (adapter, page, private, root):
            evaluator = workers.evaluator_module(workers.public_binding())
            journal = evaluator.HoldoutJournal(adapter, page, root)
            journal.act("wait", phase="positive", duration_ms=1)
            journal.act("wait", phase="negative", duration_ms=1)
            trace = {"native_surface_policy_sha256": policy.POLICY_SHA,
                     "pre_intent_rejections": [], "actions": journal.trace}
            audited = qualification.audit_native_trace(root, trace,
                {"task_id": "source-fixture", "package_sha256": "a" * 64})
            self.assertEqual(audited["native_guard_action_count"], 2)
            self.assertEqual(audited["native_guard_pngs_reopened"], 4)
            self.assertEqual(audited["native_surface_actual_applied_controls"], 2)
            self.assertEqual(audited["native_surface_logical_finishes"], 0)
            trace["actions"][1]["contract_receipt"]["native_surface_guard"] = trace["actions"][0]["contract_receipt"]["native_surface_guard"]
            with self.assertRaisesRegex(workers.NativeMaterialWorkerError, "native_surface_control_capsule_reused"):
                qualification.audit_native_trace(root, trace,
                    {"task_id": "source-fixture", "package_sha256": "a" * 64})


if __name__ == "__main__":
    unittest.main()
