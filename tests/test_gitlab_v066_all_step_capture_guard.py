"""Dynamic-frame and dispatch-boundary tests for source-only GitLab guard."""

from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from cursibench.scale_action_contract import ContractError
from gitlab_world import teacher_episode_worker_v066 as worker
from gitlab_world import v066_all_step_capture_guard_v1 as guard


PLAN = "a" * 64


class AllStepCaptureGuardTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.root.chmod(0o700)
        for name in ("positive", "positive-provider"):
            (self.root / name).mkdir(mode=0o700)
        (self.root / "positive" / "frames").mkdir(mode=0o700)
        self.original_observe = worker._RealGitLabSession.observe
        self.original_dispatch = worker._RealGitLabSession.dispatch

    def tearDown(self):
        worker._RealGitLabSession.observe = self.original_observe
        worker._RealGitLabSession.dispatch = self.original_dispatch
        self.temporary.cleanup()

    @contextmanager
    def fake_methods(self, observe, dispatch):
        worker._RealGitLabSession.observe = observe
        worker._RealGitLabSession.dispatch = dispatch
        try:
            yield
        finally:
            worker._RealGitLabSession.observe = self.original_observe
            worker._RealGitLabSession.dispatch = self.original_dispatch

    def stage_paid_step(self, step):
        paths = guard.step_paths(self.root, "positive", step)
        for key in ("provider_intent", "provider_request",
                    "provider_response", "accepted_frame"):
            paths[key].write_bytes(key.encode())
            paths[key].chmod(0o600)
        return paths

    def test_dynamic_first_and_second_step_retry_only_before_each_intent(self):
        attempts = {0: 0, 1: 0}

        def fake_observe(session, *, memory):
            attempts[session.step] += 1
            if ((session.step == 0 and attempts[0] == 1) or
                    (session.step == 1 and attempts[1] <= 2)):
                raise ContractError("stale_frame")
            session.latest = SimpleNamespace(frame_id=f"frame-{session.step}")
            return session.latest

        def fake_dispatch(session, action):
            session.step += 1
            session.previous = {"status": "applied", "code": "ok"}
            session.latest = None

        session = SimpleNamespace(
            step=0, latest=None, previous=None,
            current_frame_id=lambda: f"frame-{session.step}")
        with self.fake_methods(fake_observe, fake_dispatch):
            with guard.install(self.root, plan_sha256=PLAN):
                first = worker._RealGitLabSession.observe(session, memory="")
                self.assertEqual(first.frame_id, "frame-0")
                self.assertEqual(attempts[0], 2)
                self.assertTrue((self.root /
                    "capture-reject-positive-step-000-attempt-01.private.json").is_file())
                paths = self.stage_paid_step(0)
                action = {"step": 0, "type": "click", "target": {"ref": "c001"}}
                worker._RealGitLabSession.dispatch(session, action)
                result = json.loads(paths["dispatch_result"].read_bytes())
                self.assertEqual(result["status"],
                                 "original_gui_dispatch_acknowledged_applied")
                self.assertEqual(session.step, 1)
                second = worker._RealGitLabSession.observe(session, memory="")
                self.assertEqual(second.frame_id, "frame-1")
                self.assertEqual(attempts[1], 3)
                self.assertTrue((self.root /
                    "capture-reject-positive-step-001-attempt-02.private.json").is_file())
                self.assertEqual(len(list(self.root.glob("capture-reject-*"))), 3)
            self.assertIs(worker._RealGitLabSession.observe, fake_observe)
            self.assertIs(worker._RealGitLabSession.dispatch, fake_dispatch)

    def test_provider_intent_blocks_capture_without_another_observation(self):
        calls = []

        def fake_observe(session, *, memory):
            calls.append(session.step)
            return SimpleNamespace(frame_id="f")

        def fake_dispatch(session, action):
            raise AssertionError("dispatch must not run")

        session = SimpleNamespace(step=1, latest=None, previous=None,
                                  current_frame_id=lambda: "f")
        path = guard.step_paths(self.root, "positive", 1)["provider_intent"]
        path.write_text("{}")
        with self.fake_methods(fake_observe, fake_dispatch):
            with guard.install(self.root, plan_sha256=PLAN):
                with self.assertRaisesRegex(
                        guard.GuardError, "retry_forbidden_after_step_intent"):
                    worker._RealGitLabSession.observe(session, memory="")
        self.assertEqual(calls, [])

    def test_uncertain_dispatch_retains_intent_and_disallows_reentry(self):
        def fake_observe(session, *, memory):
            session.latest = SimpleNamespace(frame_id="f")
            return session.latest

        def fake_dispatch(session, action):
            raise ContractError("stale_frame")

        session = SimpleNamespace(step=0, latest=None, previous=None,
                                  current_frame_id=lambda: "f")
        with self.fake_methods(fake_observe, fake_dispatch):
            with guard.install(self.root, plan_sha256=PLAN):
                worker._RealGitLabSession.observe(session, memory="")
                paths = self.stage_paid_step(0)
                with self.assertRaisesRegex(ContractError, "stale_frame"):
                    worker._RealGitLabSession.dispatch(
                        session, {"step": 0, "type": "click",
                                  "target": {"ref": "c001"}})
                self.assertTrue(paths["dispatch_intent"].is_file())
                self.assertEqual(json.loads(paths["dispatch_result"].read_bytes())[
                    "status"], "dispatch_outcome_uncertain_or_failed")
                with self.assertRaises(guard.GuardError):
                    worker._RealGitLabSession.observe(session, memory="")

    def test_five_unstable_captures_stop_without_provider_or_gui_action(self):
        calls = []

        def fake_observe(session, *, memory):
            calls.append(session.step)
            raise ContractError("stale_frame")

        def fake_dispatch(session, action):
            raise AssertionError("dispatch must not run")

        session = SimpleNamespace(step=3, latest=None, previous=None,
                                  current_frame_id=lambda: "stale")
        with self.fake_methods(fake_observe, fake_dispatch):
            with guard.install(self.root, plan_sha256=PLAN):
                with self.assertRaisesRegex(ContractError, "stale_frame"):
                    worker._RealGitLabSession.observe(session, memory="")
        self.assertEqual(len(calls), guard.MAX_CAPTURE_ATTEMPTS_PER_STEP)
        self.assertEqual(len(list(self.root.glob("capture-reject-*"))),
                         guard.MAX_CAPTURE_ATTEMPTS_PER_STEP)
        self.assertFalse(list((self.root / "positive-provider").iterdir()))


if __name__ == "__main__":
    unittest.main()
