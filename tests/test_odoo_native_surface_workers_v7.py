"""Offline source/orchestration checks; no runtime, provider, or task data."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
import hashlib
import importlib
from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

from enterprise_fallback.odoo18 import native_surface_workers_v7 as workers
from cursibench import native_surface_guard_policy_v1 as policy
from cursibench import scale_action_contract as contract
from cursibench.scale_action_output_v066 import normalize_model_action
from PIL import Image


class FakeAdapter:
    def __init__(self, *args, **kwargs):
        self.latest = SimpleNamespace(frame_id="fresh-nonce")
        self.status = "applied"
        self.finished = False
        self.bound = None

    def current_frame_id(self):
        return "fresh-nonce"

    def parse_current_action(self, action):
        return action

    def dispatch(self, action):
        self.finished = self.status == "finished"
        return {"status": self.status, "action": action, "finished": self.finished,
                "public_contract_receipt": {"native_adapter_profile": "native-owned-surface-safety-envelope-v7"}}

    def bind_guard(self, *, root, worker_private):
        self.bound = (root, worker_private)


def fake_binding():
    hashes = {name: hashlib.sha256((workers._ROOT / name).read_bytes()).hexdigest()
              for name in workers.SOURCE_FILES if (workers._ROOT / name).is_file()}
    hashes.setdefault(workers.ADAPTER_FILE, "a" * 64)
    return {"binding_sha256": hashlib.sha256(uuid.uuid4().bytes).hexdigest(), "source_sha256s": hashes}


def fake_adapter_module():
    value = ModuleType(workers.ADAPTER_MODULE)
    value.OdooV066NativeSurfaceAdapter = FakeAdapter
    value.PROFILE = "native-owned-surface-safety-envelope-v7"
    return value


class NativeSurfaceWorkerTests(unittest.TestCase):
    def test_real_plugin_binding_is_source_only_and_source_drift_rejected(self):
        binding = workers.public_binding()
        self.assertEqual(binding["native_surface_policy_sha256"], policy.POLICY_SHA)
        workers.validate_binding(binding)
        changed = {**binding, "native_surface_policy_sha256": "a" * 64}
        with self.assertRaisesRegex(workers.NativeMaterialWorkerError, "native_worker_whole_binding_changed"):
            workers.validate_binding(changed)
        teacher, selection = workers._model_modules(binding)
        self.assertIs(teacher.OdooV066TrainAdapter, workers.common_adapter_class())
        self.assertIs(selection.OdooV066TrainAdapter, workers.common_adapter_class())

    @contextmanager
    def loaded_models(self):
        binding = fake_binding()
        with patch.dict(sys.modules, {workers.ADAPTER_MODULE: fake_adapter_module()}), \
             patch.object(workers._impl._impl, "validate_binding", side_effect=lambda value, *_: value):
            yield workers._model_modules(binding), binding

    def test_isolated_model_sources_compile_and_use_same_adapter(self):
        from enterprise_fallback.odoo18 import teacher_episode_worker_v066 as old_teacher
        original = old_teacher.OdooV066TrainAdapter
        with self.loaded_models() as ((teacher, selection), binding):
            self.assertIs(teacher.OdooV066TrainAdapter, FakeAdapter)
            self.assertIs(selection.OdooV066TrainAdapter, FakeAdapter)
            self.assertIs(old_teacher.OdooV066TrainAdapter, original)
            self.assertEqual(teacher.runtime_sha256(), binding["binding_sha256"])

    def test_teacher_session_returns_rejection_truthfully_and_no_png_getter(self):
        with self.loaded_models() as ((teacher, _), _binding):
            page = SimpleNamespace(screenshot=lambda **_: self.fail("getter must not take raster"))
            adapter = FakeAdapter()
            session = teacher._RealOdooSession(
                page=page, adapter=adapter, case_id="opaque", baseline_semantic={},
                score=lambda _: {}, snapshot=lambda: {}, frozen_filestore_manifest_sha256="a" * 64)
            self.assertEqual(session.current_frame_id(), "fresh-nonce")
            action = {"type": "click", "step": 0}
            adapter.status = "rejected"
            result = session.dispatch(action)
            self.assertEqual(result["status"], "rejected")
            self.assertEqual(session.native_last_action_status, "rejected")
            self.assertFalse(adapter.finished)
            adapter.status = "finished"
            self.assertEqual(session.dispatch({"type": "finish"})["status"], "finished")

    def test_evaluator_binds_after_journal_and_requires_actual_control_status(self):
        binding = fake_binding()
        with patch.dict(sys.modules, {workers.ADAPTER_MODULE: fake_adapter_module()}), \
             patch.object(workers._impl._impl, "validate_binding", side_effect=lambda value, *_: value):
            evaluator = workers.evaluator_module(binding)
            code = Path(evaluator.__file__).read_text()
            self.assertIn("journal = HoldoutJournal(adapter, page, attempt)", code)
            # The exact source substitution is pinned and executed in isolation.
            import dis
            names = [instruction.argval for instruction in dis.get_instructions(evaluator.execute_case)
                     if instruction.opname in ("LOAD_METHOD", "LOAD_ATTR")]
            self.assertIn("bind_guard", names)
            self.assertEqual(evaluator._native_policy_sha256, policy.POLICY_SHA)
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                root.chmod(0o700)
                buffer = BytesIO()
                Image.new("RGB", (64, 48), "white").save(buffer, "PNG")
                observation = contract.make_observation(
                    task_id="opaque", task_binding_sha256="a" * 64, instruction="Synthetic fixture",
                    step=0, screenshot_bytes=buffer.getvalue())
                adapter = SimpleNamespace(
                    observe_for_model=lambda **_: (observation, contract.render_for_proxy(observation)),
                    parse_current_action=lambda raw: normalize_model_action(raw, observation,
                                                         current_frame_id=observation.frame_id),
                    dispatch=lambda action: {"status": "rejected", "action": action,
                                             "public_contract_receipt": {"screenshot": observation.screenshot}})
                page = SimpleNamespace()
                journal = evaluator.HoldoutJournal(adapter, page, root)
                with self.assertRaisesRegex(RuntimeError, "gui_dispatch_receipt_not_bound_to_frame"):
                    journal.act("wait", phase="positive", duration_ms=1)
                self.assertEqual(journal.trace, [])
                self.assertEqual(list((root / "actions").glob("*-result.private.json")), [])
                self.assertEqual(len(list((root / "actions").glob("*-intent.private.json"))), 1)

    def test_teacher_rejection_consumes_turn_and_finish_is_not_driver_success(self):
        with self.loaded_models() as ((teacher, _), binding):
            buffer = BytesIO()
            Image.new("RGB", (64, 48), "white").save(buffer, "PNG")
            image = buffer.getvalue()

            class LoopAdapter(FakeAdapter):
                def __init__(self):
                    super().__init__()
                    self.step = 0
                    self.previous = None

                def observe_for_model(self, **kwargs):
                    frame = contract.make_observation(
                        task_id="opaque", task_binding_sha256="a" * 64,
                        instruction="Synthetic source-only loop fixture", step=self.step,
                        screenshot_bytes=image, memory=kwargs.get("memory", ""),
                        previous_action_result=None if self.previous is None else
                        {"status": "rejected", "code": "invalid_action"})
                    if self.previous is not None:
                        frame = replace(frame, previous_action_result=self.previous)
                    self.latest = frame
                    return frame, contract.render_for_proxy(frame)

                def current_frame_id(self):
                    return self.latest.frame_id

                def dispatch(self, action):
                    result = super().dispatch(action)
                    self.step += 1
                    if result["status"] == "rejected":
                        self.previous = {"version": policy.FEEDBACK_VERSION, "status": "rejected",
                                         "code": "editable_focus_changed_or_unsafe"}
                    return result

            adapter = LoopAdapter()
            page = SimpleNamespace(reload=lambda **_: None, locator=lambda _: SimpleNamespace(wait_for=lambda: None),
                                   screenshot=lambda **_: image)
            session = teacher._RealOdooSession(
                page=page, adapter=adapter, case_id="opaque", baseline_semantic={},
                score=lambda _: {"reward": 1.0, "checks_passed": True, "difference_codes": []},
                snapshot=lambda: {}, frozen_filestore_manifest_sha256="a" * 64)

            class Backend:
                @contextmanager
                def open(self, task):
                    try:
                        yield session
                    finally:
                        session.reset_semantic = session.baseline_semantic
                        session.post_restore_exact = True
                        session.environment_terminated = True

            seen = []
            def sample(observation, getter):
                seen.append(observation)
                adapter.status = "rejected" if observation.step == 0 else "finished"
                normalized = normalize_model_action(
                    '{"type":"wait","duration_ms":1}' if observation.step == 0 else '{"type":"finish"}',
                    observation, current_frame_id=getter())
                return {"action": normalized, "teacher_result_sha256": "b" * 64,
                        "trace_row": {"action": normalized, "step": observation.step,
                                      "frame_id": observation.frame_id, "frame_sha256": observation.screenshot["sha256"],
                                      "teacher_result_sha256": "b" * 64}}

            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                root.chmod(0o700)
                out = root / "episode"
                out.mkdir(mode=0o700)
                (out / "frames").mkdir(mode=0o700)
                worker = teacher.OdooTrainEpisodeWorker(worker_dir=root / "train", private_output_root=root)
                worker._require_ratification = lambda: None  # Synthetic test only, no native backend.
                worker.backend = Backend()
                result = worker.run_episode(
                    task={"task_id": "opaque", "package_sha256": "a" * 64,
                          "visible_instruction": "Synthetic source-only loop fixture"},
                    out_dir=out, sample_teacher=sample, dispatch_e2b=lambda *_: self.fail("no cloud IO"))
                self.assertEqual([item.step for item in seen], [0, 1])
                self.assertEqual(seen[1].previous_action_result["status"], "rejected")
                self.assertNotEqual(seen[0].frame_id, seen[1].frame_id)
                self.assertEqual(len(json.loads((out / "actions.private.json").read_bytes())), 2)
                self.assertTrue(Path(result["episode_receipt_path"]).is_file())

    def test_v7_metadata_facade_keeps_20_and_100_without_live_execution(self):
        from tools import odoo_v066_native_surface_qualification_v7 as qualification
        self.assertEqual(qualification.SPLITS, {"train": (20, 5), "selection": (20, 5), "official_hidden": (100, 25)})
        self.assertEqual(qualification.PLAN_SCHEMA, "envloop-odoo-v066-native-surface-qualification-plan-v7")
        with self.assertRaises(workers.NativeMaterialWorkerError):
            qualification.run(plan_path=Path("missing"), worker_dir=Path("missing"),
                              run_dir=Path("missing"), execute=False)

    def test_preparation_is_metadata_only_and_selection_requires_fresh_train(self):
        from tools import odoo_v066_native_surface_qualification_v7 as qualification
        binding = {**fake_binding(), "native_adapter_binding": {"binding_sha256": "a" * 64},
                   "profile": "native-owned-surface-safety-envelope-v7"}
        def metadata(split):
            rows = [{"task_id": f"fixture-{split}-{family}-{index}", "family": family,
                     "package_sha256": hashlib.sha256(f"{family}-{index}".encode()).hexdigest(),
                     "task_binding_sha256": "c" * 64, "source_asset_sha256": "d" * 64,
                     "visible_instruction_sha256": "e" * 64, "source_label": "Synthetic source fixture"}
                    for family in qualification.FAMILIES for index in range(qualification.SPLITS[split][1])]
            return {"schema": qualification.ROSTER_SCHEMA, "split": split, "tasks": rows,
                    "checkpoint": {key: "f" * 64 for key in qualification.CHECKPOINT_FILES}}
        with patch.object(workers, "public_binding", return_value=binding), \
             patch.object(workers._impl._impl, "validate_binding", side_effect=lambda value, *_: value):
            plans = [qualification.prepare(metadata(split))[0] for split in qualification.SPLITS]
            self.assertEqual([plan["task_count"] for plan in plans], [20, 20, 100])
            self.assertEqual(len({plan["run_nonce_sha256"] for plan in plans}), 3)
            for plan in plans:
                qualification.validate_plan(plan)
                self.assertTrue(plan["fresh_run_directory_name"].startswith("native-v7-"))
                self.assertEqual(plan["official_final_tasks_admitted"], 0)
                self.assertFalse(plan["automatic_replay_authorized"])
            bad = metadata("train")
            bad["tasks"][0]["prompt"] = "Forbidden task body"
            with self.assertRaises(workers.NativeMaterialWorkerError):
                qualification.prepare(bad)
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                root.chmod(0o700)
                path = root / "plan.private.json"
                path.write_bytes(workers.canonical(plans[1]))
                path.chmod(0o600)
                with patch.object(qualification._impl._impl, "_live_preflight", side_effect=AssertionError("no worker/task read")):
                    with self.assertRaisesRegex(workers.NativeMaterialWorkerError,
                                               "native_full_split_requires_hash_bound_fresh_train_control"):
                        qualification.run(plan_path=path, worker_dir=root / "selection",
                                          run_dir=root / "not-used", execute=True)

    def test_historical_train_control_cannot_admit_v7_namespace(self):
        binding = fake_binding()
        with patch.object(workers._impl._impl, "validate_binding", side_effect=lambda value, *_: value):
            for version in (2, 3, 4, 5):
                with self.assertRaisesRegex(workers.NativeMaterialWorkerError, "fresh_native_train_control_required"):
                    workers.validate_train_control({"schema": f"envloop-odoo-v066-native-material-train-control-v{version}"}, binding)

    def test_private_evidence_reader_detects_modes_and_tampering(self):
        payload = b"raw evaluator evidence"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            path = root / "sample.private"
            path.write_bytes(payload)
            path.chmod(0o600)
            ref = {"schema": "native-guard-artifact-ref-v1", "path": path.name,
                   "sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload), "kind": "lease_check"}
            self.assertEqual(workers.native_ref_bytes(root, ref), payload)
            path.chmod(0o644)
            with self.assertRaises(workers.NativeMaterialWorkerError):
                workers.native_ref_bytes(root, ref)
            path.chmod(0o600)
            path.write_bytes(b"tampered evaluator bytes")
            with self.assertRaises(policy.GuardError):
                workers.native_ref_bytes(root, ref)


if __name__ == "__main__":
    unittest.main()
