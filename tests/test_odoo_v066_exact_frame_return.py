from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from PIL import Image

from enterprise_fallback.odoo18.odoo_v066_scale_exact_return_adapter import (
    OdooV066ScaleExactReturnAdapter, _micro_raster_alternate,
)
from tools import odoo_v066_scale_audit_v1 as independent
from tools import odoo_v066_scale_controller_v1 as controller
from tools import odoo_v066_scale_protocol_v1 as protocol


def png(*, blue: int = 239, material: bool = False) -> bytes:
    image = Image.new("RGB", (1440, 1000), "white")
    for x in (41, 132):
        image.putpixel((x, 419), (235, 237, blue))
    if material:
        image.putpixel((800, 400), (0, 0, 0))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class FakePage:
    def __init__(self, frames: list[bytes]):
        self.frames = frames
        self.url = "http://localhost/odoo/purchase/1"
        self.waits = []

    def screenshot(self, *, type: str):
        assert type == "png"
        return self.frames.pop(0)

    def wait_for_timeout(self, ms: int):
        self.waits.append(ms)


def adapter(frames: list[bytes], observed: bytes):
    actor = object.__new__(OdooV066ScaleExactReturnAdapter)
    actor.page = FakePage(frames)
    actor.latest_url = actor.page.url
    actor.step = 3
    actor.task_id = "private-test-task"
    actor.task_binding_sha256 = "b" * 64
    actor.frame_guard_samples = []
    actor._guard_frame_id = None
    actor._alternate_sha256 = None
    actor.frame_guard_sink = lambda index, raw: {
        "path": f"frames/guard-{index:04d}.png",
        "sha256": sha256(raw).hexdigest(),
    }
    observation = SimpleNamespace(
        frame_id="frame-1", screenshot_bytes=observed,
        task_id=actor.task_id,
        task_binding_sha256=actor.task_binding_sha256,
        screenshot={"sha256": sha256(observed).hexdigest()})
    return actor, observation


class ExactFrameReturnTests(unittest.TestCase):
    def test_one_recurring_micro_frame_waits_until_exact_bytes(self):
        first, alternate = png(), png(blue=240)
        actor, observation = adapter([alternate, first, alternate, first], first)
        self.assertTrue(actor._frame_current(observation, stage="parse"))
        self.assertTrue(actor._frame_current(observation, stage="dispatch"))
        self.assertEqual([row["classification"] for row in
                          actor.frame_guard_samples], [
            "one_recurring_micro_raster_alternate", "exact_return",
            "one_recurring_micro_raster_alternate", "exact_return"])
        self.assertEqual(actor.page.waits, [40, 40])

    def test_third_or_material_frame_fails_before_exact_return(self):
        first, alternate, third = png(), png(blue=240), png(material=True)
        actor, observation = adapter([alternate, third, first], first)
        self.assertFalse(actor._frame_current(observation, stage="parse"))
        self.assertEqual(actor.frame_guard_samples[-1]["classification"],
                         "third_or_material_frame_rejected")
        self.assertEqual(len(actor.page.frames), 1)

    def test_no_exact_return_exhausts_bounded_samples(self):
        first, alternate = png(), png(blue=240)
        actor, observation = adapter([alternate] * 6, first)
        self.assertFalse(actor._frame_current(observation, stage="dispatch"))
        self.assertEqual(len(actor.frame_guard_samples), 6)
        self.assertEqual(actor.page.waits, [40] * 5)

    def test_url_change_blocks_sampling(self):
        first = png()
        actor, observation = adapter([first], first)
        actor.page.url = "http://localhost/odoo/purchase/2"
        self.assertFalse(actor._frame_current(observation, stage="parse"))
        self.assertEqual(actor.frame_guard_samples, [])

    def test_task_binding_change_blocks_sampling(self):
        first = png()
        actor, observation = adapter([first], first)
        observation.task_binding_sha256 = "c" * 64
        self.assertFalse(actor._frame_current(observation, stage="dispatch"))
        self.assertEqual(actor.frame_guard_samples, [])

    def test_material_change_not_classified_as_micro(self):
        self.assertTrue(_micro_raster_alternate(png(), png(blue=240)))
        self.assertFalse(_micro_raster_alternate(png(), png(material=True)))
        image = Image.open(BytesIO(png())).copy()
        image.putpixel((800, 400), (255, 255, 254))
        output = BytesIO()
        image.save(output, format="PNG")
        self.assertFalse(_micro_raster_alternate(png(), output.getvalue()))

    def test_independent_guard_chain_reopens_physical_samples(self):
        with tempfile.TemporaryDirectory() as scratch:
            attempt = Path(scratch)
            frames = attempt / "frames"
            frames.mkdir(mode=0o700)
            first, alternate = png(), png(blue=240)
            observed = frames / "observed.png"
            observed.write_bytes(first)
            observed.chmod(0o600)
            actions = attempt / "actions"
            actions.mkdir(mode=0o700)
            intent = actions / "step-000-intent.private.json"
            intent.write_bytes(protocol.canonical({"frame_id": "frame-1"}))
            intent.chmod(0o600)
            events = []
            for index, (stage, raw, classification) in enumerate((
                ("parse", alternate, "one_recurring_micro_raster_alternate"),
                ("parse", first, "exact_return"),
                ("dispatch", alternate,
                 "one_recurring_micro_raster_alternate"),
                ("dispatch", first, "exact_return"),
            )):
                path = frames / f"guard-{index:04d}.png"
                path.write_bytes(raw)
                path.chmod(0o600)
                events.append({
                    "step": 0, "stage": stage,
                    "sample": index % 2,
                    "observed_frame_sha256": sha256(first).hexdigest(),
                    "observed_frame_id_sha256":
                        sha256(b"frame-1").hexdigest(),
                    "sampled_frame_ref": {
                        "path": f"frames/guard-{index:04d}.png",
                        "sha256": sha256(raw).hexdigest()},
                    "classification": classification,
                })
            trace = {
                "actions": [{"step": 0, "frame": {
                    "path": "frames/observed.png",
                    "sha256": sha256(first).hexdigest()}}],
                "pre_intent_rejections": [],
                "exact_return_guard_samples": events,
            }
            independent._exact_return_chain(attempt, trace)
            trace["exact_return_guard_samples"][-1]["classification"] = (
                "one_recurring_micro_raster_alternate")
            with self.assertRaisesRegex(
                    independent.ScaleAuditError,
                    "scale_exact_return_alternate_not_micro"):
                independent._exact_return_chain(attempt, trace)


class SelectionRetryGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.worker = self.root / "selection"
        self.private = self.worker / "private"
        self.controls = self.private / "v066_scale_controls"
        self.old_run = self.controls / "controls-20260928-v1"
        self.attempt = self.old_run / "attempt-000"
        self.attempt.mkdir(parents=True, mode=0o700)
        for directory in (self.worker, self.private, self.controls,
                          self.old_run, self.attempt):
            directory.chmod(0o700)
        self.plan_path = self.root / "new-plan.private.json"
        self.freeze_path = self.root / "new-freeze.json"
        self.incident_path = self.root / "old-incident.json"
        self.gate_path = self.controls / \
            "selection-exact-return-retry-gate.private.json"
        self._save(self.plan_path, {"split": "selection"})
        self._save(self.freeze_path, {"status": "new"})
        self._save(self.attempt / "failure.private.json", {"status": "failed"})
        self._save(self.attempt / "gui_trace.json", {"actions": [1, 2, 3]})
        event = {"ordinal": 0, "task_id": "case-1",
                 "package_sha256": "a" * 64, "attempt_dir": "attempt-000"}
        controller._event(self.old_run / "journal.private.jsonl",
                          {"event": "case_started", **event})
        self.tail = controller._event(self.old_run / "journal.private.jsonl",
                                      {"event": "case_failed", **event})
        self._save(self.incident_path, {
            "journal_sha256": self._hash(
                self.old_run / "journal.private.jsonl"),
            "journal_tail_sha256": self.tail,
            "gui_trace_sha256": self._hash(
                self.attempt / "gui_trace.json"),
        })
        self._save(self.private / "baseline_snapshot.json", {"rows": [1]})
        self._save(self.private / "baseline-filestore-manifest.json",
                   {"files": ["x"]})
        self._save(self.controls / "selection-retry-current-sql.private.json",
                   {"rows": [1]})
        self._save(self.controls /
                   "selection-retry-current-filestore.private.json",
                   {"files": ["x"]})
        events = self.private / "worker-lease-events.jsonl"
        events.write_bytes(b'{"event":"released"}\n')
        events.chmod(0o600)
        self.plan = {"tasks": [{"task_id": "case-1",
                                 "package_sha256": "a" * 64}]}
        self._save(self.gate_path, {
            "schema": controller.SELECTION_RETRY_GATE_SCHEMA,
            "status": "old_failure_retained_current_baseline_exact_no_gui_replay",
            "new_private_plan_sha256": self._hash(self.plan_path),
            "new_source_freeze_sha256": self._hash(self.freeze_path),
            "selection_failure_public_sha256": self._hash(self.incident_path),
            "old_journal_sha256": self._hash(
                self.old_run / "journal.private.jsonl"),
            "old_journal_tail_sha256": self.tail,
            "old_failure_sha256": self._hash(
                self.attempt / "failure.private.json"),
            "old_gui_trace_sha256": self._hash(
                self.attempt / "gui_trace.json"),
            "old_step_three_intent_or_dispatch": False,
            "current_sql_sha256": self._hash(
                self.controls / "selection-retry-current-sql.private.json"),
            "current_filestore_sha256": self._hash(
                self.controls /
                "selection-retry-current-filestore.private.json"),
            "worker_lease_events_sha256": self._hash(events),
            "service_state_restored": True,
            "official_final_tasks_admitted": 0,
            "model_attempts": 0,
        })

    def _save(self, path: Path, value: dict):
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_bytes(protocol.canonical(value))
        path.chmod(0o600)

    @staticmethod
    def _hash(path: Path):
        return sha256(path.read_bytes()).hexdigest()

    def check(self):
        return controller._selection_retry_gate(
            gate_path=self.gate_path, worker=self.worker, plan=self.plan,
            private_plan_path=self.plan_path,
            source_freeze_path=self.freeze_path,
            old_run_dir=self.old_run,
            incident_public_path=self.incident_path,
            require_unchanged_lease_log=True)

    def test_gate_binds_original_failure_and_exact_saved_baseline(self):
        self.assertEqual(self.check()["status"],
                         "old_failure_retained_current_baseline_exact_no_gui_replay")
        self._save(self.attempt / "actions/step-003-intent.private.json", {})
        with self.assertRaisesRegex(controller.ScaleControlError,
                                    "scale_selection_retry_old_failure"):
            self.check()

    def test_gate_rejects_new_worker_activity(self):
        with (self.private / "worker-lease-events.jsonl").open("ab") as stream:
            stream.write(b'{"event":"acquired"}\n')
        with self.assertRaisesRegex(controller.ScaleControlError,
                                    "scale_selection_retry_gate_stale_worker_activity"):
            self.check()

    def test_gate_rejects_changed_current_filestore(self):
        self._save(self.controls /
                   "selection-retry-current-filestore.private.json",
                   {"files": ["x", "unexpected"]})
        with self.assertRaisesRegex(controller.ScaleControlError,
                                    "scale_selection_retry_live_baseline"):
            self.check()


if __name__ == "__main__":
    unittest.main()
