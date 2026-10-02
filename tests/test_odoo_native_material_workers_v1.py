"""Source/fake coverage only: no Odoo, Docker, model, provider, or task body."""

from __future__ import annotations

import copy
from contextlib import contextmanager
from datetime import datetime, timezone
import dis
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from types import ModuleType
import sys
import unittest
from unittest.mock import patch

from cursibench.scale_action_contract import ContractError
from enterprise_fallback.odoo18 import native_material_workers_v1 as workers


def fixture():
    path = Path(__file__).with_name("test_odoo_v066_native_material_adapter_v1.py")
    spec = importlib.util.spec_from_file_location("_native_fake_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path, value):
    path.write_bytes(workers.canonical(value))
    path.chmod(0o600)
    return workers.digest(path.read_bytes())


def fake_train_proof(binding):
    nonce = "1" * 32
    return {
        "schema": workers.TRAIN_CONTROL_SCHEMA, "status": workers.TRAIN_CONTROL_STATUS,
        "split": "train", "family": "purchase", "run_nonce_hex": nonce,
        "run_nonce_sha256": workers.digest(nonce.encode()),
        "native_adapter_binding_sha256": binding["native_adapter_binding"]["binding_sha256"],
        "native_worker_binding_sha256": binding["binding_sha256"],
        "independent_baseline_reward": 0.0, "independent_positive_reward": 1.0,
        "independent_wrong_object_reward": 0.0,
        "full_pre_web_filestore_reset_exact": True,
        "protected_post_web_source_bytes_equal": True,
        "source_attachment_readback": True, "original_services_restored": True,
        "source_visual_review_verified": True, "source_visual_review_pending": False,
        "native_service_readiness_verified": True,
        "native_service_readiness_receipt_sha256": "9" * 64,
        "attempt_sha256": "a" * 64, "audit_sha256": "b" * 64, "plan_sha256": "c" * 64,
        "source_review_sha256": "d" * 64, "source_frame_sha256": "e" * 64,
        "source_asset_sha256": "f" * 64,
        "old_positive_credit": 0, "model_attempts": 0, "official_final_tasks_admitted": 0,
    }


def fake_campaign(binding):
    """Synthetic source-only receipt accepted by the unchanged real validator."""
    from native_desktop_factory import v066_final_freeze as freeze
    common = freeze.source_hashes()
    profiles = {cell: {"common_source_sha256s": common, "adapter_sha256": "a" * 64}
                for cell in freeze.CELLS}
    profiles["desktop-native"]["adapter_sha256"] = freeze.digest(Path(freeze.qwen_v066_adapter.__file__).read_bytes())
    profiles["odoo-community"]["adapter_sha256"] = binding["source_sha256s"][workers.ADAPTER_FILE]
    return {"schema": "cua-six-cell-action-profile-v066-ratification-v1", "status": "ratified_pre_result",
            "ratified_utc": datetime.now(timezone.utc).isoformat(),
            "action_profile": "scale-action-profile-v0.6.6", "common_source_sha256s": common,
            "cell_profiles": profiles, "base_and_selected_identical": True,
            "hidden_final_model_attempts_before_ratification": 0}


class WorkerBindingTests(unittest.TestCase):
    def test_whole_binding_drift_and_historical_train_proof_rejected(self):
        binding = workers.public_binding()
        workers.validate_binding(binding)
        for key in ("profile", "native_adapter_binding", "source_sha256s"):
            bad = copy.deepcopy(binding)
            if key == "profile":
                bad[key] = "old-profile"
            else:
                bad[key][next(iter(bad[key]))] = "0" * 64
            with self.subTest(key=key), self.assertRaises(workers.NativeMaterialWorkerError):
                workers.validate_binding(bad)
        proof = fake_train_proof(binding)
        workers.validate_train_control(proof, binding)
        for key, value in (
            ("schema", "envloop-odoo-v066-complete-train-route-v13-outcome"),
            ("status", "actualpassed"), ("native_worker_binding_sha256", "0" * 64),
            ("run_nonce_sha256", "0" * 64), ("old_positive_credit", 1),
            ("model_attempts", 1), ("official_final_tasks_admitted", 1),
            ("source_attachment_readback", False), ("original_services_restored", False),
            ("source_visual_review_verified", False), ("source_visual_review_pending", True),
            ("independent_positive_reward", True), ("model_attempts", False),
            ("independent_positive_reward", 0.0), ("independent_wrong_object_reward", 1.0),
        ):
            with self.subTest(key=key), self.assertRaises(workers.NativeMaterialWorkerError):
                workers.validate_train_control({**proof, key: value}, binding)

    def test_all_paths_use_singleton_class_and_old_modules_unchanged(self):
        from enterprise_fallback.odoo18 import teacher_episode_worker_v066 as old_teacher
        from enterprise_fallback.odoo18 import selection_worker_v066 as old_selection
        old_class = old_teacher.OdooV066TrainAdapter
        binding = workers.public_binding()
        teacher, selection = workers._model_modules(binding)
        self.assertIs(teacher.OdooV066TrainAdapter, workers.common_adapter_class())
        self.assertIs(selection.OdooV066TrainAdapter, workers.common_adapter_class())
        self.assertIs(old_teacher.OdooV066TrainAdapter, old_class)
        self.assertIs(old_selection.OdooV066TrainAdapter, old_class)
        self.assertEqual(teacher.runtime_sha256(), binding["binding_sha256"])
        self.assertEqual(selection.runtime_sha256(), binding["binding_sha256"])

    def test_teacher_session_parses_full_bound_action_and_reopens_guards(self):
        f = fixture()
        binding = workers.public_binding()
        teacher, _ = workers._model_modules(binding)
        page, adapter, _ = f.setup("purchase")
        page.alt = True
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            (root / "frames").mkdir(mode=0o700)

            def sink(index, raw):
                path = root / "frames" / f"guard-{index:04d}.png"
                path.write_bytes(raw)
                path.chmod(0o600)
                return {"path": "frames/" + path.name, "sha256": workers.digest(raw)}

            adapter.frame_guard_sink = sink
            session = teacher._RealOdooSession(
                page=page, adapter=adapter, case_id="opaque-task", baseline_semantic={},
                score=lambda _: {}, snapshot=lambda: {}, frozen_filestore_manifest_sha256="a" * 64)
            observation = session.observe(memory="")
            self.assertEqual(session.current_frame_id(), observation.frame_id)
            from cursibench.scale_action_output_v066 import normalize_model_action
            action = normalize_model_action('{"type":"key","key":"Control+A"}', observation,
                                             current_frame_id=observation.frame_id)
            session.dispatch(action)
            self.assertEqual(page.actions, [("key", "Control+A")])
            result = workers.audit_native_contract(
                session.native_last_contract_receipt, action, observation.screenshot_bytes,
                0, {"task_id": "opaque-task", "package_sha256": "a" * 64}, root)
            self.assertEqual(result["guard_pngs_reopened"], 6)
            bad = copy.deepcopy(session.native_last_contract_receipt)
            bad["native_material_dispatch_guard"]["action_sha256"] = "0" * 64
            with self.assertRaises(workers.NativeMaterialWorkerError):
                workers.audit_native_contract(bad, action, observation.screenshot_bytes,
                                              0, {"task_id": "opaque-task", "package_sha256": "a" * 64}, root)

    def test_base_and_checkpoint_keep_existing_strict_start_binding(self):
        _, selection = workers._model_modules(workers.public_binding())
        tasks = [{"task_id": f"selection-{index}", "package_sha256": f"{index + 1:064x}"}
                 for index in range(20)]
        start = {"attempt_id": "native-selection-001", "task_count": 20,
                 "selection_tasks": tasks,
                 "selection_identities_sha256": workers.digest(workers.canonical(tasks)),
                 "checkpoint_path_sha256": "a" * 64}
        selection._start_view(start, selection.QWEN_MODEL, base_mode=True,
                              allow_base_model=True, expected_base_checkpoint_sha256="a" * 64)
        checkpoint = "tinker://opaque/sampler_weights/selected"
        selected = {**start, "checkpoint_path_sha256": workers.digest(checkpoint.encode())}
        selection._start_view(selected, checkpoint)
        with self.assertRaises(selection.SelectionWorkerError):
            selection._start_view(selected, "tinker://other/sampler_weights/selected")
        with self.assertRaises(selection.SelectionWorkerError):
            selection._start_view(start, selection.QWEN_MODEL, base_mode=True,
                                  allow_base_model=False, expected_base_checkpoint_sha256="a" * 64)

    def test_teacher_end_to_end_preserves_official_sample_trace_equality(self):
        f = fixture()
        binding = workers.public_binding()
        teacher, _ = workers._model_modules(binding)
        page, adapter, _ = f.setup("purchase")
        page.alt = False  # finish retains the shared adapter's exact PNG mode.
        page.reload = lambda **_kwargs: None
        page.locator = lambda _selector: SimpleNamespace(wait_for=lambda: None)
        task = {"task_id": "opaque-task", "package_sha256": "a" * 64,
                "visible_instruction": adapter.instruction}
        samples = []

        class FakeNativeBackend:
            @contextmanager
            def open(self, _task):
                from enterprise_fallback.odoo18 import native_service_readiness_v1 as readiness
                services = set()

                def compose(*args):
                    if args[:2] == ("up", "-d"):
                        services.update(args[2:])
                    elif args[0] == "stop":
                        services.difference_update(args[1:])

                with patch("tools.odoo_v066_train_attachment_calibration_v13._wait_db_ready", return_value={
                    "status": "postgres_health_and_select_1_ready", "query": "SELECT 1", "probe_count": 1,
                    "elapsed_milliseconds": 1,
                    "observations": [{"attempt": 1, "services": ["db"], "compose_ps_exit_code": 0,
                                      "pg_isready_exit_code": 0, "psql_exit_code": 0}],
                }):
                    readiness.ensure_ready(worker=(root / "train").resolve(), running_before=set(),
                                           compose=compose, running=lambda: set(services),
                                           receipt_sink=self._native_readiness_sink)
                session = teacher._RealOdooSession(
                    page=page, adapter=adapter, case_id="opaque-task", baseline_semantic={},
                    score=lambda _: {"reward": 1.0, "checks_passed": True, "difference_codes": []},
                    snapshot=lambda: {}, frozen_filestore_manifest_sha256="a" * 64)
                try:
                    yield session
                finally:
                    session.reset_semantic = {}
                    session.post_restore_exact = True
                    session.environment_terminated = True

        def sample(observation, current_frame_id):
            from cursibench.scale_action_output_v066 import normalize_model_action
            action = normalize_model_action('{"type":"finish"}', observation,
                                             current_frame_id=current_frame_id())
            row = {"action": action, "step": observation.step, "frame_id": observation.frame_id,
                   "frame_sha256": observation.screenshot["sha256"], "teacher_result_sha256": "d" * 64}
            samples.append(copy.deepcopy(row))
            return {"action": action, "trace_row": row, "teacher_result_sha256": "d" * 64}

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            binding_path, control_path, campaign_path = (
                root / "binding.json", root / "control.json", root / "campaign.json")
            binding_sha = write_json(binding_path, binding)
            control_sha = write_json(control_path, fake_train_proof(binding))
            campaign_sha = write_json(campaign_path, fake_campaign(binding))
            worker = workers.train_worker(
                native_binding_path=binding_path, native_binding_file_sha256=binding_sha,
                train_control_path=control_path, train_control_sha256=control_sha,
                campaign_ratification_path=campaign_path, campaign_ratification_sha256=campaign_sha,
                worker_dir=root / "train", private_output_root=root,
                expected_runtime_sha256=binding["binding_sha256"],
                expected_verifier_sha256=binding["source_sha256s"]["enterprise_fallback/odoo18/verify.py"],
                enable_live=True)
            worker.backend = FakeNativeBackend()
            output = root / "episode"
            output.mkdir(mode=0o700)
            (output / "frames").mkdir(mode=0o700)
            result = worker.run_episode(task=task, out_dir=output, sample_teacher=sample,
                                        dispatch_e2b=lambda *_args, **_kwargs: None)
            self.assertTrue(result["episode_receipt_sha256"])
            self.assertEqual(workers.private_json_list(output / "actions.private.json"), samples)
            self.assertTrue((output / "artifacts" / "native-contracts" / "step-000.private.json").is_file())
            self.assertTrue((output / "artifacts" / "db-readiness.private.json").is_file())
            self.assertEqual(len(list((output / "frames").glob("guard-*.png"))), 6)

    def test_qwen_case_source_loop_parses_retains_and_reaudits_neutral_guards(self):
        f = fixture()
        binding = workers.public_binding()
        _, selection = workers._model_modules(binding)
        page = f.FakePage("purchase")
        page.reload = lambda **_kwargs: None
        page.locator = lambda _selector: SimpleNamespace(wait_for=lambda: None)
        page.goto = lambda url: setattr(page, "url", url)
        browser = SimpleNamespace(new_page=lambda **_kwargs: page, close=lambda: None)

        @contextmanager
        def sync_playwright():
            yield SimpleNamespace(chromium=SimpleNamespace(launch=lambda **_kwargs: browser))

        playwright = ModuleType("playwright.sync_api")
        playwright.sync_playwright = sync_playwright
        task = {"task_id": "opaque-selection-task", "package_sha256": "a" * 64}
        score_calls = 0

        def score(_task):
            nonlocal score_calls
            score_calls += 1
            return {"reward": 0.0 if score_calls == 1 else 1.0,
                    "checks_passed": score_calls > 1, "difference_codes": []}

        class FakeSampler:
            def sample(self, observation, *, task_dir, **_kwargs):
                journal = task_dir / "sampling-journal"
                journal.mkdir(mode=0o700)
                path = journal / "requests.sqlite3"
                path.write_bytes(b"fixture-only-sampling-journal")
                path.chmod(0o600)
                return {"status": "completed", "text": '{"type":"finish"}',
                        "request_id": "fixture-request", "paid_attempt_id": "fixture-paid-id",
                        "rendered_usage": {"input_tokens": 100, "output_tokens": 10}}

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            private = root / "private"
            private.mkdir(mode=0o700)
            write_json(private / "checkpoint_receipt.json", {"db_sha256": "b" * 64, "filestore_sha256": "c" * 64})
            write_json(private / "actor_credentials.json", {"login": "fixture-login", "password": "fixture-password"})
            factory = SimpleNamespace(PRIVATE=private, local_config=lambda: {"ODOO_PORT": "8069"})
            reset = SimpleNamespace(restore=lambda: {
                "business_snapshot_equal": True, "physical_filestore_equal_before_web_restart": True})
            verify = SimpleNamespace(snapshot=lambda: {}, score=score)
            gui = SimpleNamespace(browser_login=lambda *_args: None)
            environment = selection.RealOdooSelectionEnvironment(root / "selection")
            environment._module_boundary = lambda: (factory, gui, reset, verify, None)
            environment._cases = {task["task_id"]: ("purchase", {"id": task["task_id"], "prompt": "Fixture visible instruction"})}
            environment._package_by_id = {task["task_id"]: task["package_sha256"]}
            output = root / "task"
            output.mkdir(mode=0o700)
            with patch.dict(sys.modules, {"playwright.sync_api": playwright}):
                result = environment.run_case(task, 0, FakeSampler(), output)
            selection._audit_task_artifacts(output, task, result)
            actions = workers.private_json_list(output / "actions.private.json")
            self.assertEqual(actions[0]["native_action"]["type"], "finish")
            self.assertEqual(actions[0]["contract_receipt"]["native_adapter_profile"], binding["profile"])
            self.assertEqual(len(list((output / "frames").glob("guard-*.png"))), 6)
            self.assertEqual(result["termination"], "model_finish")

    def test_evaluator_single_attempt_parse_failure_never_resamples_or_clicks(self):
        f = fixture()
        binding = workers.public_binding()
        module = workers.evaluator_module(binding)
        page, adapter, _ = f.setup("purchase")
        page.bad = "body"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            journal = module.HoldoutJournal(adapter, page, root)
            calls = 0
            original = adapter.observe_for_model

            def observed(**kwargs):
                nonlocal calls
                calls += 1
                return original(**kwargs)

            adapter.observe_for_model = observed
            with self.assertRaises(ContractError):
                journal.act("key", phase="positive", key="Control+A")
            self.assertEqual(calls, 1)
            self.assertEqual(page.actions, [])
            self.assertEqual(len(journal.pre_intent_rejections), 1)
            self.assertEqual(list((root / "actions").glob("*-intent.private.json")), [])

    def test_three_isolated_startup_paths_put_shared_readiness_before_first_restore(self):
        binding = workers.public_binding()
        case = workers.evaluator_module(binding)
        teacher, selection = workers._model_modules(binding)
        paths = (case.execute_case, teacher.RealOdooTrainBackend.open.__wrapped__,
                 selection.RealOdooSelectionEnvironment.batch.__wrapped__)
        for function in paths:
            instructions = list(dis.get_instructions(function))
            ready = next(index for index, instruction in enumerate(instructions)
                         if instruction.argval == "_native_ensure_ready")
            restore = next(index for index, instruction in enumerate(instructions)
                           if instruction.argval == "restore")
            self.assertLess(ready, restore)
        self.assertIs(teacher._native_ensure_ready, selection._native_ensure_ready)
        self.assertIn("enterprise_fallback/odoo18/native_service_readiness_v1.py", binding["source_sha256s"])
        self.assertIn("tools/odoo_v066_train_attachment_calibration_v13.py", binding["source_sha256s"])
        self.assertEqual(binding["service_readiness_policy"]["max_probes"], 30)

    def test_evaluator_failed_ready_gate_retains_receipt_without_sql_or_actor_action(self):
        binding = workers.public_binding()
        module = workers.evaluator_module(binding)
        calls = []
        playwright = ModuleType("playwright.sync_api")
        playwright.sync_playwright = lambda: (_ for _ in ()).throw(AssertionError("browser reached"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            private = root / "private"
            private.mkdir(mode=0o700)
            run_dir = private / "run"
            run_dir.mkdir(mode=0o700)
            factory = SimpleNamespace(HERE=root, PRIVATE=private,
                                      local_config=lambda: {"ODOO_PARTITION": "train"})
            reset = SimpleNamespace(restore=lambda: (_ for _ in ()).throw(AssertionError("SQL before ready")))
            original_recorder = module.train_recorder
            module.train_recorder = SimpleNamespace(_running=lambda _worker: set(),
                                                    _compose=lambda *_args: calls.append("compose"))

            def failed_ready(**kwargs):
                calls.append("ready_gate")
                kwargs["receipt_sink"]({"status": "fixture_failed_ready_with_original_services_restored"})
                raise RuntimeError("fixture-readiness-failure")

            original_ready = module._native_ensure_ready
            module._native_ensure_ready = failed_ready
            row = {key: "a" * 64 for key in (
                "package_sha256", "task_binding_sha256", "source_freeze_sha256",
                "epoch_source_freeze_sha256", "current_candidate_private_sha256",
                "no_gui_gate_sha256", "run_nonce_sha256")}
            row.update(task_id="fixture-task", physical_dispatch_profile=binding["profile"])
            try:
                with patch.dict(sys.modules, {"playwright.sync_api": playwright}):
                    with self.assertRaises(module.ScaleControlError):
                        module.execute_case(run_dir=run_dir, ordinal=0, row=row,
                                            case={"id": "fixture-task"}, wrong={}, family="purchase",
                                            modules=(factory, None, reset, None, None))
            finally:
                module._native_ensure_ready = original_ready
                module.train_recorder = original_recorder
            self.assertEqual(calls, ["ready_gate"])
            self.assertTrue((run_dir / "attempt-000" / "db-readiness.private.json").is_file())
            self.assertFalse((run_dir / "attempt-000" / "pre_restore.json").exists())
            self.assertTrue((run_dir / "attempt-000" / "failure.private.json").is_file())

    def test_model_live_gate_requires_current_source_and_fresh_proof_before_callbacks(self):
        binding = workers.public_binding()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            binding_path, control_path = root / "binding.json", root / "control.json"
            binding_sha = write_json(binding_path, binding)
            control_sha = write_json(control_path, fake_train_proof(binding))
            worker = workers.train_worker(
                native_binding_path=binding_path, native_binding_file_sha256=binding_sha,
                train_control_path=control_path, train_control_sha256=control_sha,
                worker_dir=root / "train", private_output_root=root,
                expected_runtime_sha256=binding["binding_sha256"],
                expected_verifier_sha256=binding["source_sha256s"]["enterprise_fallback/odoo18/verify.py"],
                enable_live=False)
            with self.assertRaises(workers.NativeMaterialWorkerError):
                worker._require_ratification()
            worker.enable_live = True
            with self.assertRaisesRegex(workers.NativeMaterialWorkerError, "campaign_ratification_pending"):
                worker._require_ratification()
            workers._require_live(worker, binding, binding_path, binding_sha, control_path, control_sha)
            write_json(control_path, {**fake_train_proof(binding), "model_attempts": 1})
            with self.assertRaises(workers.NativeMaterialWorkerError):
                worker._require_ratification()

    def test_separate_real_campaign_validator_and_neutral_profile_are_mandatory(self):
        binding = workers.public_binding()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            campaign_path = root / "campaign.json"
            campaign = fake_campaign(binding)
            campaign_sha = write_json(campaign_path, campaign)
            workers._require_campaign_ratification(binding, campaign_path, campaign_sha)
            campaign["cell_profiles"]["odoo-community"]["adapter_sha256"] = "0" * 64
            changed_sha = write_json(campaign_path, campaign)
            with self.assertRaisesRegex(workers.NativeMaterialWorkerError, "neutral_profile_not_admitted"):
                workers._require_campaign_ratification(binding, campaign_path, changed_sha)
            campaign = fake_campaign(binding)
            campaign["cell_profiles"]["odoo-community"]["native_worker_binding_sha256"] = binding["binding_sha256"]
            extra_key_sha = write_json(campaign_path, campaign)
            with self.assertRaisesRegex(workers.NativeMaterialWorkerError, "ratification_not_admitted"):
                workers._require_campaign_ratification(binding, campaign_path, extra_key_sha)
            with patch("native_desktop_factory.v066_final_freeze.validate_ratification", side_effect=ValueError):
                with self.assertRaisesRegex(workers.NativeMaterialWorkerError, "ratification_not_admitted"):
                    workers._require_campaign_ratification(binding, campaign_path, extra_key_sha)

    def test_reference_escape_symlink_and_nonprivate_raw_frame_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            frames = root / "frames"
            frames.mkdir(mode=0o700)
            image = frames / "guard.png"
            image.write_bytes(b"not-used-as-an-image")
            image.chmod(0o600)
            ref = {"path": "frames/guard.png", "sha256": workers.digest(image.read_bytes())}
            self.assertEqual(workers.private_ref_bytes(root, ref), image.read_bytes())
            for path in ("../guard.png", "/tmp/guard.png", "other/guard.png"):
                with self.assertRaises(workers.NativeMaterialWorkerError):
                    workers.private_ref_bytes(root, {**ref, "path": path})
            image.chmod(0o644)
            with self.assertRaises(workers.NativeMaterialWorkerError):
                workers.private_ref_bytes(root, ref)
            image.chmod(0o600)
            link = frames / "link.png"
            link.symlink_to(image)
            with self.assertRaises(workers.NativeMaterialWorkerError):
                workers.private_ref_bytes(root, {**ref, "path": "frames/link.png"})


if __name__ == "__main__":
    unittest.main()
