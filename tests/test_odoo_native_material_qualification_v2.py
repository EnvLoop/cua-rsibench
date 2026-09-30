"""Metadata planning and fail-closed execution gates; no live task reads."""

from __future__ import annotations

import copy
from contextlib import contextmanager
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from enterprise_fallback.odoo18 import native_material_workers_v2 as workers
from tools import odoo_v066_native_material_qualification_v2 as qualification


def roster(split="selection"):
    count, per_family = qualification.SPLITS[split]
    return {
        "schema": qualification.ROSTER_SCHEMA, "split": split,
        "checkpoint": {name: f"{index + 1:064x}"
                       for index, name in enumerate(qualification.CHECKPOINT_FILES)},
        "tasks": [{"task_id": f"opaque-{split}-{index}",
                   "family": qualification.FAMILIES[index // per_family],
                   "package_sha256": f"{index + 10:064x}",
                   "task_binding_sha256": f"{index + 200:064x}",
                   "source_asset_sha256": f"{index + 300:064x}",
                   "visible_instruction_sha256": f"{index + 400:064x}",
                   "source_label": f"opaque-source-{index}.pdf"}
                  for index in range(count)],
    }


def fake_train_proof(binding):
    path = Path(__file__).with_name("test_odoo_native_material_workers_v2.py")
    spec = importlib.util.spec_from_file_location("_native_worker_test_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.fake_train_proof(binding)


def write_json(path, value):
    path.write_bytes(workers.canonical(value))
    path.chmod(0o600)
    return workers.digest(path.read_bytes())


class FakeControlRuntime:
    """Fixture-only execution seam, preserving real orchestration and files."""

    def __init__(self):
        self.held = False
        self.calls = []
        self.fail_ordinal = None

    @contextmanager
    def exclusive_worker_operation(self, _operation):
        assert not self.held
        self.held = True
        try:
            yield
        finally:
            self.held = False

    def execute_case(self, *, run_dir, ordinal, row, **_rest):
        assert self.held
        self.calls.append(ordinal)
        attempt = run_dir / f"attempt-{ordinal:03d}"
        attempt.mkdir(mode=0o700)
        (attempt / "frames").mkdir(mode=0o700)
        frame = attempt / "frames" / "source.png"
        frame.write_bytes(b"fixture-only-source-frame-retention")
        frame.chmod(0o600)
        write_json(attempt / "attempt.private.json", {
            "task_id": row["task_id"], "finished_at_utc": "2026-09-30T00:00:00+00:00",
            "refs": {"source_frame": {"path": "frames/source.png", "sha256": workers.digest(frame.read_bytes())}},
        })
        if ordinal == self.fail_ordinal:
            raise workers.NativeMaterialWorkerError("fixture_control_failure")

    def audit(self, *, plan, row, **_rest):
        assert not self.held
        return {
            "schema": qualification.AUDIT_SCHEMA, "status": "fixture_verified_source_review_pending",
            "task_id": row["task_id"], "family": row["family"], "split": plan["split"],
            "native_worker_binding_sha256": plan["native_worker_binding_sha256"],
            "native_adapter_binding_sha256": plan["native_adapter_binding_sha256"],
            "run_nonce_sha256": plan["run_nonce_sha256"],
            "independent_baseline_reward": 0.0, "independent_positive_reward": 1.0,
            "independent_wrong_object_reward": 0.0,
            "full_pre_web_filestore_reset_exact": True,
            "protected_post_web_source_bytes_equal": True,
            "source_attachment_gui_frame_retained": True,
            "source_attachment_readback": False, "original_services_restored": True,
            "native_service_readiness_verified": True,
            "native_service_readiness_receipt_sha256": "9" * 64,
            "source_visual_review_verified": False, "source_visual_review_pending": True,
            "old_positive_credit": 0, "model_attempts": 0, "official_final_tasks_admitted": 0,
        }

    def patches(self, plan, private):
        world = {"cases": {family: [{"id": row["task_id"]} for row in plan["tasks"]
                                   if row["family"] == family]
                           for family in qualification.FAMILIES}}
        from tools import odoo_v066_scale_controller_v1 as controller
        return (
            patch.object(qualification, "_live_preflight", return_value=(world, private)),
            patch.object(controller, "_modules", return_value=(None, None, None, None, self)),
            patch.object(workers, "evaluator_module", return_value=SimpleNamespace(execute_case=self.execute_case)),
            patch.object(qualification, "audit_case", side_effect=self.audit),
        )


class QualificationTests(unittest.TestCase):
    def test_existing_full_or_split_plan_metadata_projects_without_task_bodies(self):
        inputs = {split: roster(split) for split in qualification.SPLITS}
        full = {
            "schema": "envloop-odoo-v066-prospective-gui-requalification-plan-v1",
            "tasks": {split: [{**row, "split": split, "checkpoint": value["checkpoint"],
                                "fresh_v066_gui_proof_status": "pending"}
                               for row in value["tasks"]]
                      for split, value in inputs.items()},
            "checkpoints": {split: value["checkpoint"] for split, value in inputs.items()},
        }
        for split, expected in inputs.items():
            self.assertEqual(qualification.project_legacy_metadata(full, split), expected)
            one = {"schema": "envloop-odoo-v066-split-gui-control-plan-v1", "split": split,
                   "tasks": full["tasks"][split], "checkpoint": full["checkpoints"][split]}
            self.assertEqual(qualification.project_legacy_metadata(one, split), expected)
        remaining = {"schema": "envloop-odoo-v066-split-gui-control-plan-v1", "split": "train",
                     "tasks": full["tasks"]["train"][1:], "checkpoint": full["checkpoints"]["train"]}
        with self.assertRaisesRegex(workers.NativeMaterialWorkerError, "count_or_checkpoint"):
            qualification.project_legacy_metadata(remaining, "train")
        contaminated = copy.deepcopy(full)
        contaminated["tasks"]["selection"][0]["prompt"] = "not metadata"
        with self.assertRaisesRegex(workers.NativeMaterialWorkerError, "contain_task_body"):
            qualification.project_legacy_metadata(contaminated, "selection")
        with self.assertRaisesRegex(workers.NativeMaterialWorkerError, "frozen_metadata_plan_required"):
            qualification.project_legacy_metadata({"train": [{"task_id": "opaque"}]}, "train")

    def test_prepare_exact_20_and_100_metadata_with_new_nonce_and_zero_credit(self):
        with patch.object(qualification, "_live_preflight", side_effect=AssertionError("live boundary crossed")):
            for split, count in (("train", 20), ("selection", 20), ("official_hidden", 100)):
                with self.subTest(split=split):
                    plan, public = qualification.prepare(roster(split))
                    qualification.validate_plan(plan)
                    self.assertEqual(plan["task_count"], count)
                    self.assertEqual(public["candidate_count"], count)
                    self.assertNotIn("tasks", public)
                    self.assertEqual(public["fresh_native_gui_controls"], 0)
                    self.assertEqual(public["official_final_tasks_admitted"], 0)
                    self.assertEqual(public["model_attempts"], 0)
                    self.assertEqual(public["old_positive_credit"], 0)
                    other, _ = qualification.prepare(roster(split))
                    self.assertNotEqual(plan["run_nonce_sha256"], other["run_nonce_sha256"])

    def test_metadata_rejects_prompt_oracle_missing_rows_and_duplicate_id(self):
        for mutation in ("prompt", "expected", "gold", "missing", "duplicate", "family"):
            value = roster()
            if mutation == "missing":
                value["tasks"].pop()
            elif mutation == "duplicate":
                value["tasks"][1]["task_id"] = value["tasks"][0]["task_id"]
            elif mutation == "family":
                value["tasks"][0]["family"] = "crm"
            else:
                value["tasks"][0][mutation] = "private content"
            with self.subTest(mutation=mutation), self.assertRaises(workers.NativeMaterialWorkerError):
                qualification.prepare(value)

    def test_plan_nonzero_credit_mutated_roster_nonce_and_binding_rejected(self):
        plan, _ = qualification.prepare(roster())
        for mutation in ("credit", "nonce", "source", "task"):
            bad = copy.deepcopy(plan)
            if mutation == "credit":
                bad["old_positive_credit"] = 1
            elif mutation == "nonce":
                bad["run_nonce_hex"] = "1" * 32
            elif mutation == "source":
                bad["native_worker_binding"]["source_sha256s"][workers.ADAPTER_FILE] = "0" * 64
            else:
                bad["tasks"][0]["package_sha256"] = "0" * 64
            with self.subTest(mutation=mutation), self.assertRaises(workers.NativeMaterialWorkerError):
                qualification.validate_plan(bad)

    def test_execute_switch_checked_before_any_plan_or_private_read(self):
        with patch.object(workers, "private_json", side_effect=AssertionError("private read")):
            with self.assertRaisesRegex(workers.NativeMaterialWorkerError, "explicit_execute_required"):
                qualification.run(plan_path=Path("unused"), worker_dir=Path("unused"), run_dir=Path("unused"))

    def test_selection_and_final_fresh_train_prerequisite_before_runtime_read(self):
        for split in ("selection", "official_hidden"):
            with self.subTest(split=split), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                root.chmod(0o700)
                plan, _ = qualification.prepare(roster(split))
                path = root / "plan.json"
                path.write_bytes(workers.canonical(plan))
                path.chmod(0o600)
                with patch.object(qualification, "_live_preflight", side_effect=AssertionError("runtime read")):
                    with self.assertRaisesRegex(workers.NativeMaterialWorkerError, "fresh_train_control"):
                        qualification.run(plan_path=path, worker_dir=root / split,
                                          run_dir=root / "unused", execute=True)

    def test_train_refuses_prior_positive_control_before_runtime_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            plan, _ = qualification.prepare(roster("train"))
            path = root / "plan.json"
            path.write_bytes(workers.canonical(plan))
            path.chmod(0o600)
            with patch.object(qualification, "_live_preflight", side_effect=AssertionError("runtime read")):
                with self.assertRaisesRegex(workers.NativeMaterialWorkerError, "refuses_old_positive_credit"):
                    qualification.run(plan_path=path, worker_dir=root / "train", run_dir=root / "unused",
                                      execute=True, train_control_path=root / "old-v13.json")

    def test_full_20_and_100_fake_orchestration_requires_fresh_proof_and_admits_zero(self):
        for split, count in (("selection", 20), ("official_hidden", 100)):
            with self.subTest(split=split), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                root.chmod(0o700)
                worker = root / split
                worker.mkdir(mode=0o700)
                private = worker / "private"
                private.mkdir(mode=0o700)
                plan, _ = qualification.prepare(roster(split))
                path = root / "plan.json"
                write_json(path, plan)
                proof = root / "train-proof.json"
                proof_sha = write_json(proof, fake_train_proof(plan["native_worker_binding"]))
                runtime = FakeControlRuntime()
                a, b, c, d = runtime.patches(plan, private)
                run_dir = private / "v066_native_material_controls_v2" / plan["fresh_run_directory_name"]
                with a, b, c, d:
                    result = qualification.run(plan_path=path, worker_dir=worker, run_dir=run_dir,
                                               execute=True, train_control_path=proof,
                                               train_control_sha256=proof_sha)
                self.assertEqual(runtime.calls, list(range(count)))
                self.assertEqual(result["fresh_native_gui_controls"], count)
                self.assertEqual(result["official_final_tasks_admitted"], 0)
                self.assertEqual(result["model_attempts"], 0)
                self.assertTrue(result["source_visual_review_pending"])
                with self.assertRaisesRegex(workers.NativeMaterialWorkerError, "no_resume_or_replay"):
                    qualification.run(plan_path=path, worker_dir=worker, run_dir=run_dir,
                                      execute=True, train_control_path=proof, train_control_sha256=proof_sha)

    def test_first_train_is_pending_until_separate_bound_source_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            worker = root / "train"
            worker.mkdir(mode=0o700)
            private = worker / "private"
            private.mkdir(mode=0o700)
            plan, _ = qualification.prepare(roster("train"))
            path = root / "plan.json"
            write_json(path, plan)
            runtime = FakeControlRuntime()
            a, b, c, d = runtime.patches(plan, private)
            run_dir = private / "v066_native_material_controls_v2" / plan["fresh_run_directory_name"]
            with a, b, c, d:
                result = qualification.run(plan_path=path, worker_dir=worker, run_dir=run_dir, execute=True)
            self.assertEqual(runtime.calls, [0])
            self.assertEqual(result["status"], qualification.TRAIN_CANDIDATE_STATUS)
            self.assertFalse((run_dir / "train-control.private.json").exists())
            candidate = workers.private_json(run_dir / "train-control-candidate.private.json")
            with self.assertRaises(workers.NativeMaterialWorkerError):
                workers.validate_train_control(candidate, plan["native_worker_binding"])
            frame = workers.private_json(run_dir / "attempt-000" / "attempt.private.json")["refs"]["source_frame"]
            row = plan["tasks"][0]
            review = {
                "schema": qualification.SOURCE_REVIEW_SCHEMA, "status": qualification.SOURCE_REVIEW_STATUS,
                "task_id": row["task_id"], "package_sha256": row["package_sha256"],
                "source_asset_sha256": row["source_asset_sha256"], "source_frame_sha256": frame["sha256"],
                "attempt_sha256": candidate["attempt_sha256"], "audit_sha256": candidate["audit_sha256"],
                "native_worker_binding_sha256": plan["native_worker_binding_sha256"],
                "native_adapter_binding_sha256": plan["native_adapter_binding_sha256"],
                "run_nonce_sha256": plan["run_nonce_sha256"], "reviewer_independent_of_actor": True,
                "source_attachment_readable": True, "source_matches_package": True,
                "reviewed_at_utc": "2026-09-30T00:00:01+00:00",
            }
            review_path = root / "review.json"
            for key, value in (("source_frame_sha256", "0" * 64),
                               ("run_nonce_sha256", "0" * 64),
                               ("source_matches_package", False),
                               ("reviewed_at_utc", "2026-09-29T00:00:00+00:00")):
                review_sha = write_json(review_path, {**review, key: value})
                with patch.object(qualification, "audit_case", side_effect=runtime.audit):
                    with self.subTest(key=key), self.assertRaises(workers.NativeMaterialWorkerError):
                        qualification.finalize_train_control(
                            plan_path=path, worker_dir=worker, run_dir=run_dir,
                            source_review_path=review_path, source_review_sha256=review_sha)
            review_sha = write_json(review_path, review)
            with patch.object(qualification, "audit_case", side_effect=runtime.audit):
                finalized = qualification.finalize_train_control(
                    plan_path=path, worker_dir=worker, run_dir=run_dir,
                    source_review_path=review_path, source_review_sha256=review_sha)
            proof = workers.private_json(run_dir / "train-control.private.json", finalized["train_control_sha256"])
            workers.validate_train_control(proof, plan["native_worker_binding"])
            self.assertTrue(proof["source_visual_review_verified"])
            self.assertFalse(proof["source_visual_review_pending"])

    def test_failed_case_keeps_attempt_and_never_replays(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            worker = root / "selection"
            worker.mkdir(mode=0o700)
            private = worker / "private"
            private.mkdir(mode=0o700)
            plan, _ = qualification.prepare(roster())
            path = root / "plan.json"
            write_json(path, plan)
            proof = root / "proof.json"
            proof_sha = write_json(proof, fake_train_proof(plan["native_worker_binding"]))
            runtime = FakeControlRuntime()
            runtime.fail_ordinal = 3
            a, b, c, d = runtime.patches(plan, private)
            run_dir = private / "v066_native_material_controls_v2" / plan["fresh_run_directory_name"]
            with a, b, c, d:
                with self.assertRaisesRegex(workers.NativeMaterialWorkerError, "fixture_control_failure"):
                    qualification.run(plan_path=path, worker_dir=worker, run_dir=run_dir, execute=True,
                                      train_control_path=proof, train_control_sha256=proof_sha)
            self.assertEqual(runtime.calls, [0, 1, 2, 3])
            self.assertTrue((run_dir / "failed.private.json").is_file())
            self.assertTrue((run_dir / "attempt-003" / "attempt.private.json").is_file())
            self.assertFalse((run_dir / "result.private.json").exists())
            with self.assertRaisesRegex(workers.NativeMaterialWorkerError, "no_resume_or_replay"):
                qualification.run(plan_path=path, worker_dir=worker, run_dir=run_dir, execute=True,
                                  train_control_path=proof, train_control_sha256=proof_sha)


if __name__ == "__main__":
    unittest.main()
