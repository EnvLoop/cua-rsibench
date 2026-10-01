"""Offline V14 qualification namespace and admission checks only."""
from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cursibench.native_surface_guard_policy_v1 import POLICY_SHA
from enterprise_fallback.odoo18 import native_surface_workers_v14 as workers
from tools import odoo_v066_native_surface_qualification_v14 as qualification


ROOT = Path(__file__).resolve().parents[1]


def binding_fixture():
    return {
        "binding_sha256": "a" * 64,
        "native_adapter_binding": {"binding_sha256": "b" * 64},
        "profile": "native-owned-surface-safety-envelope-v14",
    }


def metadata_fixture(split):
    return {
        "schema": qualification.ROSTER_SCHEMA,
        "split": split,
        "tasks": [
            {
                "task_id": f"synthetic-{split}-{family}-{index}",
                "family": family,
                "package_sha256": hashlib.sha256(f"{family}-{index}".encode()).hexdigest(),
                "task_binding_sha256": "c" * 64,
                "source_asset_sha256": "d" * 64,
                "visible_instruction_sha256": "e" * 64,
                "source_label": "Synthetic source-only metadata fixture",
            }
            for family in qualification.FAMILIES
            for index in range(qualification.SPLITS[split][1])
        ],
        "checkpoint": {key: "f" * 64 for key in qualification.CHECKPOINT_FILES},
    }


class NativeSurfaceQualificationV14Tests(unittest.TestCase):
    def prepare_plan(self, split):
        with patch.object(workers, "public_binding", return_value=binding_fixture()), \
             patch.object(workers, "validate_binding", side_effect=lambda value, *_: value):
            plan, public = qualification.prepare(metadata_fixture(split))
            qualification.validate_plan(plan)
        return plan, public

    def test_frozen_qualification_source_uses_independent_v14_namespace(self):
        from tools import odoo_v066_native_surface_qualification_v13 as historical

        raw = (ROOT / "tools/odoo_v066_native_surface_qualification_v6.py").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         "7c9906b883552885dd0a483c731d948d935a4744674d5b0134d4871c9738baaa")
        transformed = raw.decode().replace("v6", "v14")
        self.assertEqual(qualification._impl._native_compat_source_sha256,
                         hashlib.sha256(transformed.encode()).hexdigest())
        self.assertIsNot(qualification._impl, historical._impl)
        self.assertIsNot(qualification._impl._impl, historical._impl._impl)
        self.assertIs(qualification.workers, workers)
        self.assertEqual(qualification.PLAN_SCHEMA,
                         "envloop-odoo-v066-native-surface-qualification-plan-v14")
        self.assertEqual(historical.PLAN_SCHEMA,
                         "envloop-odoo-v066-native-surface-qualification-plan-v13")
        self.assertEqual(qualification.SPLITS,
                         {"train": (20, 5), "selection": (20, 5), "official_hidden": (100, 25)})

    def test_prepare_retains_public_partitions_and_fresh_zero_credit_plans(self):
        prepared = [self.prepare_plan(split) for split in qualification.SPLITS]
        self.assertEqual([plan["task_count"] for plan, _ in prepared], [20, 20, 100])
        self.assertEqual(len({plan["run_nonce_sha256"] for plan, _ in prepared}), 3)
        for plan, public in prepared:
            self.assertTrue(plan["fresh_run_directory_name"].startswith("native-v14-"))
            self.assertEqual(plan["physical_dispatch_profile"],
                             "native-owned-surface-safety-envelope-v14")
            self.assertFalse(plan["automatic_replay_authorized"])
            for key in ("old_positive_credit", "fresh_native_gui_controls",
                        "official_final_tasks_admitted", "model_attempts"):
                self.assertEqual(plan[key], 0)
                self.assertEqual(public[key], 0)

    def test_task_body_and_historical_plan_are_rejected(self):
        metadata = metadata_fixture("train")
        metadata["tasks"][0]["prompt"] = "Forbidden synthetic task-body field"
        with self.assertRaisesRegex(workers.NativeMaterialWorkerError,
                                    "native_roster_identity_or_nonmetadata_field_invalid"):
            qualification.prepare(metadata)
        plan, _ = self.prepare_plan("train")
        plan["schema"] = "envloop-odoo-v066-native-surface-qualification-plan-v13"
        with self.assertRaisesRegex(workers.NativeMaterialWorkerError,
                                    "native_qualification_plan_invalid"):
            qualification.validate_plan(plan)

    def test_old_v13_train_control_cannot_admit_v14(self):
        binding = binding_fixture()
        nonce = "1" * 32
        control = {
            "schema": workers.TRAIN_CONTROL_SCHEMA,
            "status": workers.TRAIN_CONTROL_STATUS,
            "split": "train", "family": "purchase",
            "run_nonce_hex": nonce,
            "run_nonce_sha256": hashlib.sha256(nonce.encode()).hexdigest(),
            "native_adapter_binding_sha256": binding["native_adapter_binding"]["binding_sha256"],
            "native_worker_binding_sha256": binding["binding_sha256"],
            "independent_baseline_reward": 0.0,
            "independent_positive_reward": 1.0,
            "independent_wrong_object_reward": 0.0,
            "source_visual_review_pending": False,
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
        control_globals = workers.validate_train_control.__globals__
        with patch.dict(control_globals, {"validate_binding": lambda value, *_: value}):
            self.assertIs(workers.validate_train_control(control, binding), control)
            for namespace in ("native-material", "native-surface"):
                with self.subTest(namespace=namespace), \
                     self.assertRaisesRegex(workers.NativeMaterialWorkerError,
                                            "fresh_native_train_control_required"):
                    workers.validate_train_control({**control,
                        "schema": f"envloop-odoo-v066-{namespace}-train-control-v13",
                    }, binding)

    def test_all_nontrain_splits_need_fresh_control_before_live_preflight(self):
        for split in ("selection", "official_hidden"):
            with self.subTest(split=split):
                plan, _ = self.prepare_plan(split)
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    root.chmod(0o700)
                    path = root / "plan.private.json"
                    path.write_bytes(workers.canonical(plan))
                    path.chmod(0o600)
                    with patch.object(workers, "validate_binding", side_effect=lambda value, *_: value), \
                         patch.object(qualification._impl._impl, "_live_preflight",
                                      side_effect=AssertionError("No live preflight authorized")):
                        with self.assertRaisesRegex(workers.NativeMaterialWorkerError,
                                                    "native_full_split_requires_hash_bound_fresh_train_control"):
                            qualification.run(plan_path=path, worker_dir=root / split,
                                              run_dir=root / "unused", execute=True)

    def test_train_refuses_existing_run_directory_before_live_preflight(self):
        plan, _ = self.prepare_plan("train")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            path = root / "plan.private.json"
            path.write_bytes(workers.canonical(plan))
            path.chmod(0o600)
            run_dir = root / "private" / "v066_native_surface_controls_v14" / plan["fresh_run_directory_name"]
            run_dir.mkdir(parents=True, mode=0o700)
            with patch.object(workers, "validate_binding", side_effect=lambda value, *_: value), \
                 patch.object(qualification._impl._impl, "_live_preflight",
                              side_effect=AssertionError("No live preflight authorized")):
                with self.assertRaisesRegex(workers.NativeMaterialWorkerError,
                                            "native_fresh_nonce_directory_required_no_resume_or_replay"):
                    qualification.run(plan_path=path, worker_dir=root, run_dir=run_dir,
                                      execute=True)

    def test_control_audit_requires_actual_applied_driver_or_logical_finish(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            actions = root / "actions"
            actions.mkdir(mode=0o700)
            action = {"step": 0, "frame_id": "synthetic-fresh-frame", "type": "wait"}
            intent = {"step": 0, "frame_id": action["frame_id"], "normalized_action": action,
                      "observation_controls": [{"ref": "observed", "visible": True, "enabled": True}]}
            path = actions / "step-000-intent.private.json"
            path.write_bytes(workers.canonical(intent))
            path.chmod(0o600)
            trace = {"native_surface_policy_sha256": POLICY_SHA, "pre_intent_rejections": [],
                     "actions": [{"frame": {}, "contract_receipt": {
                         "native_surface_guard": {"path": "synthetic-guard.private.json"}}}]}
            row = {"task_id": "synthetic-control", "package_sha256": "a" * 64}
            for decision, dispatch, action_type, accepted in (
                ("accepted", "applied", "wait", True),
                ("rejected", "rejected", "wait", False),
                ("accepted", "finished", "wait", False),
                ("accepted", "finished", "finish", True),
            ):
                with self.subTest(decision=decision, dispatch=dispatch, action_type=action_type):
                    action["type"] = action_type
                    path.write_bytes(workers.canonical(intent))
                    audited = {"decision_status": decision, "dispatch_status": dispatch,
                               "guard_pngs_reopened": 2}
                    with patch.object(workers, "private_ref_bytes", return_value=b"synthetic frame"), \
                         patch.object(workers, "audit_native_contract", return_value=audited) as audit:
                        if accepted:
                            result = qualification.audit_native_trace(root, trace, row)
                            self.assertEqual(result["native_guard_action_count"], 1)
                            self.assertEqual(result["native_guard_pngs_reopened"], 2)
                            self.assertEqual(result["native_surface_actual_applied_controls"], dispatch == "applied")
                            self.assertEqual(result["native_surface_logical_finishes"], dispatch == "finished")
                        else:
                            with self.assertRaisesRegex(workers.NativeMaterialWorkerError,
                                                        "native_surface_control_requires_actual_applied_driver"):
                                qualification.audit_native_trace(root, trace, row)
                        self.assertEqual(audit.call_args.kwargs["observation_control_refs"], ["observed"])


if __name__ == "__main__":
    unittest.main()
