"""Offline actual-WDI-package GUI teacher episodes; no E2B or model calls."""

from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

from cursibench import full_study_teacher_adapter_v1 as teacher
from cursibench.scale_action_contract import make_observation
from cursibench.scale_action_contract_v066 import validate_action
from native_desktop_factory.teacher_episode_worker_v066 import (
    DesktopEpisodeError, DesktopGuest, DesktopTrainEpisodeWorker,
    _impress_geometry_valid, _semantic_input, adapter_sha256,
    audit_episode_private,
    runtime_sha256, verifier_sha256,
)
from native_desktop_factory.v066_final_freeze import digest
from native_desktop_factory.v066_final_freeze import source_hashes
from tests.test_full_study_teacher_adapter_v1 import FakeSession, write_private


ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "work/native-desktop/candidates-v2-distinct-d"
PRIVATE_MAP = ROOT / "work/native-desktop/private-map.json"
GUEST_IDENTITY = ROOT / "docs/evidence/native-wdi-guest-content-identity-2026-09-27.json"


def fake_png() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (1280, 800), (243, 245, 248)).save(output, "PNG")
    return output.getvalue()


class FakeGuest(DesktopGuest):
    def __init__(self, backend, phase, sandbox_id):
        super().__init__(sandbox_id=sandbox_id)
        self.backend = backend
        self.phase = phase
        self.frame = fake_png()
        self.dispatched = []
        self.stale = False
        self.neutral_source = None

    def prepare(self, *, source, filename, oracle, guest_identity):
        suffix = Path(filename).suffix
        if suffix == ".pptx":
            self.neutral_input = (
                ROOT / "native_desktop_factory/dev-fixtures/"
                "wdi-native-mex-impress-deck-normalized/"
                "wdi-native-mex-impress-deck-normalized.pptx").read_bytes()
        else:
            self.neutral_input = source
        assert _semantic_input(self.neutral_input, suffix) == _semantic_input(source, suffix)
        self.raw_input_sha256 = digest(source)
        self.provider_shape_attested = True
        self.fresh_profile_absent = True
        self.guest_content_sha256 = guest_identity["static_content_sha256"]
        self.profile_sha256 = ("f" * 64 if self.phase == "reset" and
                               self.backend.profile_drift else "a" * 64)
        self.neutral_source = source

    def observe(self, *, task, step, previous, memory):
        self._latest = make_observation(
            task_id=task["task_id"],
            task_binding_sha256=task["package_sha256"],
            instruction=task["visible_instruction"],
            step=step, screenshot_bytes=self.frame,
            previous_action_result=previous, memory=memory)
        return self._latest

    def current_frame_id(self):
        return "stale" if self.stale else self._latest.frame_id

    def predispatch_frame(self):
        return self.frame

    def dispatch(self, action):
        assert validate_action(action, self._latest,
                               current_frame_id=self.current_frame_id()) == action
        self.dispatched.append(action["type"])

    def read_saved(self):
        if self.phase == "reset":
            return self.neutral_input
        if self.backend.wrong_saved:
            return self.neutral_input
        assert "click" in self.dispatched and "finish" in self.dispatched
        return self.backend.saved_positive

    def close(self):
        self.killed = True
        return True


class FakeBackend:
    is_fake = True

    def __init__(self, saved_positive: bytes):
        self.saved_positive = saved_positive
        self.created = []
        self.profile_drift = False
        self.wrong_saved = False
        self.reuse_sandbox = False

    def create(self, phase, lease_seconds):
        assert lease_seconds == 600
        sandbox_id = "fake-actor" if phase == "actor" or self.reuse_sandbox else "fake-reset"
        guest = FakeGuest(self, phase, sandbox_id)
        self.created.append(guest)
        return guest


@unittest.skipUnless((CANDIDATES / "candidate-inventory.json").is_file(),
                     "evaluator-private Desktop corpus is not in this checkout")
class DesktopWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="desktop-teacher-test-")
        self.addCleanup(self.temp.cleanup)
        self.private_root = Path(self.temp.name) / "private"
        self.private_root.mkdir(mode=0o700)
        self.rows = json.loads((CANDIDATES / "candidate-inventory.json").read_bytes())["tasks"]
        self.sampled = []
        self.leases = []

    def case(self, workflow):
        row = next(r for r in self.rows if r["split"] == "train"
                   and r["workflow"] == workflow and "mex" in r["task_id"])
        package = CANDIDATES / "train" / row["task_id"]
        positive_paths = {
            "calc-growth": ROOT / "work/native-desktop/gui/mex-calc-positive-1/saved.xlsx",
            "impress-deck": ROOT / "work/native-desktop/gui/mex-impress-normalized-positive-1/saved.pptx",
            "writer-brief": ROOT / "work/native-desktop/gui/mex-writer-positive-1/saved.docx",
        }
        task = {"task_id": row["task_id"],
                "package_sha256": row["package_sha256"],
                "visible_instruction": (package / "actor_task.txt").read_text()}
        return task, positive_paths[workflow].read_bytes()

    def worker(self, saved):
        backend = FakeBackend(saved)
        worker = DesktopTrainEpisodeWorker(
            candidate_root=CANDIDATES, private_map=PRIVATE_MAP,
            guest_identity_public=GUEST_IDENTITY,
            private_output_root=self.private_root,
            expected_runtime_sha256=runtime_sha256(),
            expected_verifier_sha256=verifier_sha256(),
            expected_inventory_sha256=digest(
                (CANDIDATES / "candidate-inventory.json").read_bytes()),
            expected_guest_identity_sha256=digest(GUEST_IDENTITY.read_bytes()),
            backend=backend)
        # Synthetic tests bypass only this gate. Production always rejects a
        # fake backend and requires the actual six-cell private ratification.
        worker._require_live_freeze = lambda: None
        return worker, backend

    def episode_dir(self):
        path = self.private_root / "episode-001"
        path.mkdir(mode=0o700)
        (path / "frames").mkdir(mode=0o700)
        return path

    def dispatch_e2b(self, *, phase, lease_seconds, reserve_usd, provider):
        self.assertIn(phase, ("actor", "reset"))
        self.assertEqual(lease_seconds, 600)
        self.assertEqual(reserve_usd, "0.166666667")
        result = provider({"phase": phase})
        attempt_id = "e2b-teacher-r001-e001" + ("-reset" if phase == "reset" else "")
        self.leases.append((phase, attempt_id, result["sandbox_id"]))
        return {"attempt_id": attempt_id, "result": result}

    def sample_teacher(self, observation, current_frame_id):
        self.assertEqual(current_frame_id(), observation.frame_id)
        kind = "click" if observation.step == 0 else "finish"
        minimal = ({"type": "click", "target": {"x": 500, "y": 400}}
                   if kind == "click" else {"type": "finish"})
        full = {"version": "scale-computer-use-v0.6",
                "task_id": observation.task_id,
                "task_binding_sha256": observation.task_binding_sha256,
                "step": observation.step, "frame_id": observation.frame_id,
                "memory": observation.memory, **minimal}
        action = validate_action(full, observation,
                                 current_frame_id=current_frame_id())
        trace = {"step": observation.step,
                 "frame_id": observation.frame_id,
                 "frame_sha256": digest(observation.screenshot_bytes),
                 "observation": {"task_id": observation.task_id,
                                 "task_binding_sha256": observation.task_binding_sha256,
                                 "instruction": observation.instruction,
                                 "a11y_text": observation.a11y_text,
                                 "dom_text": observation.dom_text,
                                 "controls": [],
                                 "previous_action_result": observation.previous_action_result,
                                 "memory": observation.memory,
                                 "issued_at": observation.issued_at},
                 "action": action,
                 "teacher_result_sha256": "e" * 64}
        self.sampled.append({"observation": observation, "action": action,
                             "trace_row": trace, "teacher_result_sha256": "e" * 64})
        return {"action": action, "trace_row": trace,
                "teacher_result_sha256": "e" * 64}

    def test_real_train_packages_across_calc_impress_writer_fake_provider(self):
        for workflow in ("calc-growth", "impress-deck", "writer-brief"):
            with self.subTest(workflow=workflow):
                self.sampled.clear()
                self.leases.clear()
                task, saved = self.case(workflow)
                worker, backend = self.worker(saved)
                episode = self.episode_dir()
                result = worker.run_episode(
                    task=task, out_dir=episode,
                    sample_teacher=self.sample_teacher,
                    dispatch_e2b=self.dispatch_e2b)
                self.assertEqual([phase for phase, *_ in self.leases],
                                 ["actor", "reset"])
                self.assertEqual(len({guest.sandbox_id for guest in backend.created}), 2)
                self.assertTrue(all(guest.killed for guest in backend.created))
                self.assertEqual(len(list((episode / "frames").glob("predispatch-*.png"))), 2)
                self.assertEqual(audit_episode_private(episode), {
                    "raw_observation_frames": 2,
                    "raw_predispatch_frames": 2,
                    "distinct_guest_sandboxes": 2,
                })
                self.assertEqual(teacher._verify_episode(
                    episode, result, cell_id=worker.cell_id, task=task,
                    runtime_sha=worker.runtime_sha256,
                    adapter_sha=worker.adapter_sha256,
                    verifier_sha=worker.verifier_sha256,
                    turns=self.sampled,
                    e2b_attempt_ids=[row[1] for row in self.leases],
                    requires_e2b=True,
                    requires_fresh_e2b_reset=True),
                    result["episode_receipt_sha256"])
                import shutil
                shutil.rmtree(episode)

    def test_native_impress_train_baseline_has_valid_visible_geometry(self):
        path = (ROOT / "native_desktop_factory/dev-fixtures/"
                "wdi-native-mex-impress-deck-normalized/"
                "wdi-native-mex-impress-deck-normalized.pptx")
        self.assertTrue(_impress_geometry_valid(path.read_bytes()))

    def test_selection_and_final_rejected_before_any_provider(self):
        task, saved = self.case("calc-growth")
        worker, backend = self.worker(saved)
        for split in ("selection", "final_candidate"):
            row = next(r for r in self.rows if r["split"] == split)
            package = CANDIDATES / split / row["task_id"]
            forbidden = {"task_id": row["task_id"],
                         "package_sha256": row["package_sha256"],
                         "visible_instruction": (package / "actor_task.txt").read_text()}
            with self.subTest(split=split), self.assertRaisesRegex(
                    DesktopEpisodeError, "desktop_source_not_train_only"):
                worker.run_episode(task=forbidden, out_dir=self.episode_dir(),
                                   sample_teacher=self.sample_teacher,
                                   dispatch_e2b=self.dispatch_e2b)
            self.assertEqual(backend.created, [])
            import shutil
            shutil.rmtree(self.private_root / "episode-001")

    def test_inventory_and_guest_identity_drift_reject_before_provider(self):
        task, saved = self.case("calc-growth")
        for field, reason in (
                ("expected_inventory_sha256",
                 "desktop_train_inventory_binding_changed"),
                ("expected_guest_identity_sha256",
                 "desktop_guest_identity_binding_changed")):
            worker, backend = self.worker(saved)
            setattr(worker, field, "0" * 64)
            with self.subTest(field=field), self.assertRaisesRegex(
                    DesktopEpisodeError, reason):
                worker.run_episode(task=task, out_dir=self.episode_dir(),
                                   sample_teacher=self.sample_teacher,
                                   dispatch_e2b=self.dispatch_e2b)
            self.assertEqual(backend.created, [])
            import shutil
            shutil.rmtree(self.private_root / "episode-001")

    def test_wrong_saved_artifact_stops_before_reset_lease(self):
        task, saved = self.case("writer-brief")
        worker, backend = self.worker(saved)
        backend.wrong_saved = True
        with self.assertRaisesRegex(DesktopEpisodeError,
                                    "desktop_actor_saved_ooxml_not_positive"):
            worker.run_episode(task=task, out_dir=self.episode_dir(),
                               sample_teacher=self.sample_teacher,
                               dispatch_e2b=self.dispatch_e2b)
        self.assertEqual([phase for phase, *_ in self.leases], ["actor"])
        self.assertTrue(backend.created[0].killed)
        self.assertTrue((self.private_root / "episode-001/failure.private.json").is_file())

    def test_fresh_guest_profile_drift_and_id_reuse_reject(self):
        for fault in ("profile_drift", "reuse_sandbox"):
            self.sampled.clear()
            self.leases.clear()
            task, saved = self.case("calc-growth")
            worker, backend = self.worker(saved)
            setattr(backend, fault, True)
            with self.subTest(fault=fault), self.assertRaises(DesktopEpisodeError):
                worker.run_episode(task=task, out_dir=self.episode_dir(),
                                   sample_teacher=self.sample_teacher,
                                   dispatch_e2b=self.dispatch_e2b)
            self.assertTrue(all(guest.killed for guest in backend.created))
            self.assertFalse((self.private_root / "episode-001/episode.private.json").exists())
            import shutil
            shutil.rmtree(self.private_root / "episode-001")

    def test_real_backend_is_blocked_without_six_cell_freeze(self):
        task, _saved = self.case("calc-growth")
        worker = DesktopTrainEpisodeWorker(
            candidate_root=CANDIDATES, private_map=PRIVATE_MAP,
            guest_identity_public=GUEST_IDENTITY,
            private_output_root=self.private_root)
        with self.assertRaisesRegex(DesktopEpisodeError,
                                    "desktop_live_episode_requires_frozen_bindings"):
            worker.run_episode(task=task, out_dir=self.episode_dir(),
                               sample_teacher=self.sample_teacher,
                               dispatch_e2b=self.dispatch_e2b)
        self.assertEqual(self.leases, [])

    def test_injected_fake_backend_is_rejected_without_test_bypass(self):
        task, saved = self.case("calc-growth")
        worker, backend = self.worker(saved)
        with patch.object(worker, "_require_live_freeze",
                          DesktopTrainEpisodeWorker._require_live_freeze.__get__(worker)):
            with self.assertRaisesRegex(
                    DesktopEpisodeError,
                    "desktop_fake_backend_cannot_admit_training"):
                worker.run_episode(task=task, out_dir=self.episode_dir(),
                                   sample_teacher=self.sample_teacher,
                                   dispatch_e2b=self.dispatch_e2b)
        self.assertEqual(backend.created, [])

    def test_tampered_raw_predispatch_frame_is_independently_rejected(self):
        task, saved = self.case("calc-growth")
        worker, _backend = self.worker(saved)
        episode = self.episode_dir()
        worker.run_episode(task=task, out_dir=episode,
                           sample_teacher=self.sample_teacher,
                           dispatch_e2b=self.dispatch_e2b)
        frame = episode / "frames/predispatch-000.png"
        frame.write_bytes(b"tampered")
        with self.assertRaisesRegex(DesktopEpisodeError,
                                    "desktop_private_evidence_hash_changed"):
            audit_episode_private(episode)

    def test_shared_collector_accepts_two_reserved_fake_leases_and_train_only_dataset(self):
        task, saved = self.case("calc-growth")
        source = source_hashes()
        profiles = {
            cell: {"common_source_sha256s": source,
                   "adapter_sha256": adapter_sha256() if cell == "desktop-native"
                   else "b" * 64}
            for cell in teacher.matrix.CELLS}
        ratification = {
            "schema": "cua-six-cell-action-profile-v066-ratification-v1",
            "status": "ratified_pre_result",
            "ratified_utc": datetime.now(timezone.utc).isoformat(),
            "action_profile": teacher.ACTION_PROFILE_VERSION,
            "common_source_sha256s": source,
            "cell_profiles": profiles,
            "base_and_selected_identical": True,
            "hidden_final_model_attempts_before_ratification": 0,
        }
        repo_root = Path(self.temp.name)
        (repo_root / "work").mkdir(exist_ok=True, mode=0o700)
        ratification_path = repo_root / "ratification.private.json"
        write_private(ratification_path, ratification)
        session = FakeSession(repo_root, ratification_path, ratification)
        session.intent["cell_id"] = "desktop-native"
        session.views["train"] = ({"task_id": task["task_id"],
                                     "package_sha256": task["package_sha256"]},)
        session.proposal["train_task_ids"] = [task["task_id"]]
        session.proposal_sha = write_private(
            session.proposal_path.with_name("proposal-rebuilt.private.json"),
            session.proposal)
        session.proposal_path.write_bytes(
            session.proposal_path.with_name("proposal-rebuilt.private.json").read_bytes())
        session.proposal_path.chmod(0o600)
        session.study.plan["cells"][2]["matched_bindings"] = {
            "runtime": runtime_sha256(),
            "verifier": verifier_sha256(),
        }
        context = repo_root / "work/context.private.json"
        write_private(context, {"tasks": [task]})
        session.context_sha = digest(context.read_bytes())
        destination = repo_root / "work/teacher-round-001"
        worker = DesktopTrainEpisodeWorker(
            candidate_root=CANDIDATES, private_map=PRIVATE_MAP,
            guest_identity_public=GUEST_IDENTITY,
            private_output_root=destination,
            expected_runtime_sha256=runtime_sha256(),
            expected_verifier_sha256=verifier_sha256(),
            expected_inventory_sha256=digest(
                (CANDIDATES / "candidate-inventory.json").read_bytes()),
            expected_guest_identity_sha256=digest(GUEST_IDENTITY.read_bytes()),
            backend=FakeBackend(saved))
        worker._require_live_freeze = lambda: None

        def provider(request):
            self.assertEqual(request["train_task_id"], task["task_id"])
            action = ({"type": "click", "target": {"x": 500, "y": 400}}
                      if request["step"] == 0 else {"type": "finish"})
            return {"text": json.dumps(action),
                    "receipt": {"reported_model": teacher.matrix.TEACHER,
                                "status": "completed",
                                "response_id": "fake-desktop-" + str(request["step"]),
                                "usage": {"input_tokens": 100,
                                          "output_tokens": 10}}}

        def render(cell_id, task_ids, episode_shas, turns, _vision):
            self.assertEqual(cell_id, "desktop-native")
            self.assertEqual(task_ids, [task["task_id"]])
            self.assertEqual(len(turns), 2)
            receipt = {"schema": teacher.RENDER_SCHEMA,
                       "cell_id": cell_id,
                       "action_profile": teacher.ACTION_PROFILE_VERSION,
                       "model": teacher.MODEL,
                       "train_task_ids": task_ids,
                       "episode_receipt_sha256s": episode_shas,
                       "datum_token_lengths": [20, 20],
                       "prompt_token_lengths": [10, 10]}
            return teacher.RenderedTrainBatch(
                [SimpleNamespace(model_input=SimpleNamespace(length=20))
                 for _ in turns],
                [SimpleNamespace(length=10) for _ in turns], receipt)

        with patch.object(teacher, "_load_renderer", return_value=object()), \
             patch.object(teacher, "_render_turns", side_effect=render):
            result = teacher.collect_train_batch(
                session, 1, context, destination, worker,
                teacher_provider=provider)
        self.assertEqual([row["category"] for row in session.calls],
                         ["e2b", "teacher_rollout", "teacher_rollout", "e2b"])
        manifest = json.loads(result.dataset_manifest_path.read_bytes())
        self.assertEqual(manifest["train_task_ids"], [task["task_id"]])
        self.assertEqual(manifest["selection_task_count"], 0)
        self.assertEqual(manifest["final_task_count"], 0)


if __name__ == "__main__":
    unittest.main()
