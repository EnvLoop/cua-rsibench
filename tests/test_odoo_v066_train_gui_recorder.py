"""Fake GUI and offline preflight tests; never touch Odoo or Docker."""

from __future__ import annotations

from hashlib import sha256
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from cursibench.scale_action_contract import make_observation
from cursibench.scale_action_contract_v066 import public_receipt
from cursibench.scale_action_output_v066 import (
    normalize_model_action, render_for_model)
from tools import record_odoo_v066_train_gui_v1 as rec


def png(color=(20, 30, 40)):
    buffer = io.BytesIO()
    Image.new("RGB", (1440, 1000), color).save(buffer, "PNG")
    return buffer.getvalue()


def private_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_bytes(rec.canonical(value))
    path.chmod(0o600)
    return rec.sha(path.read_bytes())


class FakePage:
    pass


class FakeAdapter:
    def __init__(self, output, *, fail_dispatch=False):
        self.output = output
        self.step = 0
        self.latest = None
        self.fail_dispatch = fail_dispatch
        self.dispatch_calls = 0

    def observe_for_model(self, *, memory=""):
        observation = make_observation(
            task_id="TRAIN-ONLY-1", task_binding_sha256="a" * 64,
            instruction="Edit the one training RFQ", step=self.step,
            screenshot_bytes=png(), controls=[],
            previous_action_result=({"status": "applied", "code": "ok"}
                                    if self.step else None),
            memory=memory)
        self.latest = observation
        return observation, render_for_model(observation)

    def parse_current_action(self, raw):
        return normalize_model_action(
            raw, self.latest, current_frame_id=self.latest.frame_id)

    def dispatch(self, normalized):
        self.dispatch_calls += 1
        intent = self.output / "actions" / f"step-{self.step:03d}-intent.private.json"
        assert intent.is_file(), "normalized action intent must exist before dispatch"
        saved = json.loads(intent.read_text())
        assert saved["normalized_action"] == normalized
        assert saved["frame_id"] == self.latest.frame_id
        if self.fail_dispatch:
            raise RuntimeError("fake uncertain GUI dispatch")
        receipt = public_receipt(self.latest, action=normalized)
        self.step += 1
        return {"action": normalized, "public_contract_receipt": receipt,
                "finished": False}


class RecorderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_intent_and_exact_multimodal_sft_bytes_precede_gui_dispatch(self):
        out = self.root / "attempt"
        out.mkdir(mode=0o700)
        adapter = FakeAdapter(out)
        journal = rec.ActionJournal(adapter, FakePage(), out)
        frame = journal.act("wait", phase="positive", duration_ms=50,
                            memory="Read the source PDF")
        self.assertEqual(adapter.dispatch_calls, 1)
        self.assertEqual(len(journal.trace), 1)
        self.assertEqual(len(journal.sft), 1)
        datum = journal.sft[0]
        image = (out / datum["frame"]["path"]).read_bytes()
        rendered = (out / datum["rendered_instruction"]["path"]).read_text()
        action = (out / datum["assistant_action"]["path"]).read_text()
        normalized = json.loads((out / datum["normalized_action_intent"]["path"]).read_text())
        self.assertEqual(rec.sha(image), frame["sha256"])
        self.assertIn("Read the source PDF", rendered)
        self.assertEqual(json.loads(action), {"duration_ms": 50, "type": "wait"})
        self.assertEqual(normalized["normalized_action"]["frame_id"],
                         normalized["frame_id"])
        self.assertEqual(stat.S_IMODE((out / datum["frame"]["path"]).stat().st_mode),
                         0o600)
        journal.act("wait", phase="negative", duration_ms=50)
        self.assertEqual(len(journal.trace), 2)
        self.assertEqual(len(journal.sft), 1, "wrong-object actions cannot enter SFT")

    def test_exact_sft_gate_requires_positive_only_and_pilot_audit(self):
        out = self.root / "attempt"
        out.mkdir(mode=0o700)
        adapter = FakeAdapter(out)
        journal = rec.ActionJournal(adapter, FakePage(), out)
        journal.act("wait", phase="positive", duration_ms=50)
        journal.act("wait", phase="negative", duration_ms=50)
        private_json(out / "gui_trace.json", {
            "schema": rec.GUI_SCHEMA, "task_binding_sha256": "b" * 64,
            "actions": journal.trace})
        candidate = {"schema": rec.SFT_SCHEMA,
                     "status": "pending_independent_visual_and_semantic_pilot_audit",
                     "split": "train", "cell": "odoo-community",
                     "model": "Qwen/Qwen3.8-27B",
                     "action_profile": "scale-action-profile-v0.6.6",
                     "task_binding_sha256": "b" * 64,
                     "positive_steps_only": journal.sft,
                     "selection_or_hidden_examples": 0,
                     "tinker_training_started": False}
        private_json(out / "sft_candidate.private.json", candidate)
        private_json(out / "attempt.private.json", {"schema": rec.ATTEMPT_SCHEMA})
        binding_parent = self.root / "binding"
        binding_parent.mkdir(mode=0o700)
        binding = binding_parent / "pilot.private.json"
        private_json(binding, {"task": {"task_id": "TRAIN-ONLY-1",
                                        "package_sha256": "a" * 64,
                                        "task_binding_sha256": "b" * 64}})
        pilot = self.root / "pilot-audit.json"
        pilot.write_bytes(rec.canonical({
            "schema": "envloop-odoo-v066-gui-control-pilot-audit-v1",
            "status": "fresh_train_candidate_control_derived_from_raw_evidence",
            "private_attempt_sha256": rec.sha((out / "attempt.private.json").read_bytes()),
            "fresh_train_candidate_controls_qualified": 1,
            "positive_gui_actions": 1,
            "official_final_tasks_admitted": 0,
            "model_attempts": 0}))
        result = rec.audit_sft_source(out_dir=out, binding_path=binding,
                                      pilot_audit_path=pilot)
        self.assertEqual(result["datum_count"], 1)
        self.assertEqual(result["official_final_tasks_admitted"], 0)
        candidate["positive_steps_only"].append({"step": 1})
        private_json(out / "sft_candidate.private.json", candidate)
        with self.assertRaisesRegex(rec.RecorderError,
                                    "exact_sft_source_or_pilot_not_admitted"):
            rec.audit_sft_source(out_dir=out, binding_path=binding,
                                 pilot_audit_path=pilot)

    def test_uncertain_dispatch_retains_intent_and_never_replays(self):
        out = self.root / "attempt"
        out.mkdir(mode=0o700)
        adapter = FakeAdapter(out, fail_dispatch=True)
        journal = rec.ActionJournal(adapter, FakePage(), out)
        with self.assertRaisesRegex(RuntimeError, "uncertain GUI dispatch"):
            journal.act("wait", phase="positive", duration_ms=50)
        self.assertEqual(adapter.dispatch_calls, 1)
        self.assertTrue((out / "actions" / "step-000-intent.private.json").is_file())
        self.assertFalse((out / "actions" / "step-000-result.private.json").exists())
        self.assertEqual(journal.trace, [])
        self.assertEqual(journal.sft, [])

    def test_train_only_pilot_projection_and_source_preflight(self):
        from enterprise_fallback.odoo18.partition_factory import (
            candidate_world, source_asset)
        world = candidate_world("synthetic-train-only-seed-0123456789abcdef", "train")
        case = world["cases"]["purchase"][0]
        source = source_asset(case, world)
        package = rec.sha(json.dumps(case, sort_keys=True).encode() + b"\n" + source)
        worker = self.root / "partition_workers" / "train"
        private = worker / "private"
        private.mkdir(parents=True, mode=0o700)
        db, fs = b"synthetic db checkpoint", b"synthetic filestore checkpoint"
        (private / "baseline.pgcustom").write_bytes(db)
        (private / "baseline-filestore.tgz").write_bytes(fs)
        private_json(private / "baseline_snapshot.json", {})
        private_json(private / "baseline-filestore-manifest.json", {})
        private_json(private / "partition_cases.json", world)
        own, common = rec._source_hashes()
        task = {"task_id": case["id"], "split": "train",
                "family": "purchase", "package_sha256": package,
                "source_asset_sha256": rec.sha(source),
                "visible_instruction_sha256": rec.sha(case["prompt"].encode()),
                "source_label": f"{case['id']}-source.pdf",
                "odoo_adapter_sha256": own[rec.ODOO_SOURCE_FILES[0]],
                "fresh_v066_gui_proof_status": "pending",
                "ratification_sha256": rec.RATIFICATION_SHA,
                "action_profile": "scale-action-profile-v0.6.6"}
        checkpoint = {
            "db_sha256": rec.sha(db), "filestore_sha256": rec.sha(fs),
            "baseline_snapshot_sha256": rec.sha((private / "baseline_snapshot.json").read_bytes()),
            "baseline_filestore_manifest_sha256": rec.sha(
                (private / "baseline-filestore-manifest.json").read_bytes()),
        }
        task["checkpoint"] = checkpoint
        task["task_binding_sha256"] = rec.sha(rec.canonical({key: task[key]
            for key in ("ratification_sha256", "action_profile", "split", "task_id",
                        "package_sha256", "source_asset_sha256",
                        "visible_instruction_sha256", "checkpoint",
                        "odoo_adapter_sha256")}))
        private_plan = {"schema": "envloop-odoo-v066-prospective-gui-requalification-plan-v1",
                        "ratification_sha256": rec.RATIFICATION_SHA,
                        "official_final_tasks_admitted": 0,
                        "odoo_source_sha256s": own,
                        "common_action_source_sha256s": common,
                        "pilot": {"split": "train", "task_id": case["id"],
                                  "task_binding_sha256": task["task_binding_sha256"]},
                        "tasks": {"train": [task]},
                        "checkpoints": {"train": checkpoint}}
        plan_dir = self.root / "plans"
        plan_dir.mkdir(mode=0o700)
        plan_path = plan_dir / "private-plan.json"
        private_json(plan_path, private_plan)
        public_path = self.root / "public-plan.json"
        public_path.write_bytes(rec.canonical({
            "status": "source_bound_plan_only_no_current_gui_proofs",
            "new_six_cell_ratification_sha256": rec.RATIFICATION_SHA,
            "pilot_receipt_present": False,
            "private_plan_sha256": rec.sha(plan_path.read_bytes()),
            "candidate_counts": {"train": 20, "selection": 20,
                                 "official_hidden": 100},
            "official_final_tasks_admitted": 0,
            "pilot_auditor_source_sha256": "8" * 64}))
        pilot_binding = plan_dir / "pilot.private.json"
        public_summary = rec.prepare_binding(plan_path, public_path,
                                             pilot_binding)
        self.assertFalse(public_summary["selection_or_hidden_task_values_included"])
        self.assertEqual(stat.S_IMODE(pilot_binding.stat().st_mode), 0o600)
        self.assertNotIn("HID-FILLER", pilot_binding.read_text())
        binding = json.loads(pilot_binding.read_text())
        freeze_path = self.root / "freeze.json"
        freeze_path.write_bytes(rec.canonical({
            "schema": rec.FREEZE_SCHEMA,
            "status": "frozen_before_first_live_train_gui_attempt",
            "recorder_source_sha256": rec.sha(Path(rec.__file__).read_bytes()),
            "train_pilot_binding_sha256": rec.sha(pilot_binding.read_bytes()),
            "public_plan_sha256": rec.sha(public_path.read_bytes()),
            "private_plan_sha256": binding["private_plan_sha256"],
            "pilot_auditor_source_sha256": "8" * 64,
            "host_runtime": rec.host_runtime(),
            "ratification_sha256": rec.RATIFICATION_SHA,
            "official_final_tasks_admitted": 0,
            "live_gui_attempts_before_freeze": 0,
            "provider_calls_before_freeze": 0}))
        out = private / "v066_requalification_runs" / "first-live-pilot"
        with patch.dict(os.environ, {"ENVLOOP_ODOO_WORKER_DIR": str(worker.resolve())}):
            selected, loaded, wrong = rec.preflight(
                worker_dir=worker, binding_path=pilot_binding,
                public_plan_path=public_path, freeze_path=freeze_path,
                out_dir=out)
        self.assertEqual(selected["task"]["task_id"], case["id"])
        self.assertEqual(loaded["id"], case["id"])
        self.assertNotEqual(wrong["id"], case["id"])
        self.assertFalse(out.exists(), "preflight must not create a run")
        freeze_path.write_text("{}")
        with patch.dict(os.environ, {"ENVLOOP_ODOO_WORKER_DIR": str(worker.resolve())}):
            with self.assertRaisesRegex(rec.RecorderError,
                                        "recorder_code_or_plan_freeze_changed"):
                rec.preflight(worker_dir=worker, binding_path=pilot_binding,
                              public_plan_path=public_path,
                              freeze_path=freeze_path, out_dir=out)

    def test_live_command_requires_explicit_execute_before_any_docker(self):
        argv = ["record-odoo", "record", "--worker-dir", "/missing/train",
                "--pilot-binding", "/missing/binding",
                "--public-plan", "/missing/plan",
                "--code-freeze", "/missing/freeze",
                "--out-dir", "/missing/output"]
        with patch.object(rec.sys, "argv", argv), patch.object(
                rec, "_compose", side_effect=AssertionError("Docker called")):
            with self.assertRaisesRegex(rec.RecorderError,
                                        "explicit_live_execute_flag_required"):
                rec.main()

    def test_finalize_needs_distinct_post_run_visual_review(self):
        out = self.root / "attempt"
        out.mkdir(mode=0o700)
        (out / "frames").mkdir(mode=0o700)
        frame = out / "frames" / "source.png"
        frame.write_bytes(png())
        frame.chmod(0o600)
        frame_ref = {"path": "frames/source.png", "sha256": rec.sha(frame.read_bytes())}
        binding_dir = self.root / "bindings"
        binding_dir.mkdir(mode=0o700)
        binding_path = binding_dir / "pilot.private.json"
        task = {"task_id": "TRAIN-1", "package_sha256": "a" * 64,
                "task_binding_sha256": "b" * 64,
                "source_asset_sha256": "c" * 64,
                "source_label": "TRAIN-1-source.pdf"}
        private_json(binding_path, {"task": task,
                                    "private_plan_sha256": "d" * 64})
        draft = {"schema": rec.ATTEMPT_SCHEMA,
                 "status": "awaiting_independent_source_frame_review",
                 "task_id": task["task_id"],
                 "package_sha256": task["package_sha256"],
                 "task_binding_sha256": task["task_binding_sha256"],
                 "plan_sha256": "d" * 64,
                 "finished_at_utc": "2026-09-28T00:00:08+00:00",
                 "refs": {"source_frame": frame_ref}}
        private_json(out / "draft.private.json", draft)
        review_path = out / "source_review.json"
        review = {"schema": rec.REVIEW_SCHEMA,
                  "decision": "source_visible_in_original_odoo_gui",
                  "reviewer_role": "independent_visual_source_reviewer",
                  "reviewer_id_sha256": rec.CONTROLLER_SHA,
                  "source_frame_sha256": frame_ref["sha256"],
                  "source_asset_sha256": task["source_asset_sha256"],
                  "source_label": task["source_label"],
                  "reviewed_at_utc": "2026-09-28T00:00:09+00:00"}
        private_json(review_path, review)
        with self.assertRaisesRegex(rec.RecorderError,
                                    "independent_visual_review_unbound"):
            rec.finalize(out_dir=out, review_path=review_path,
                         binding_path=binding_path)
        review["reviewer_id_sha256"] = "e" * 64
        private_json(review_path, review)
        result = rec.finalize(out_dir=out, review_path=review_path,
                              binding_path=binding_path)
        self.assertEqual(result["official_final_tasks_admitted"], 0)
        self.assertTrue((out / "attempt.private.json").is_file())
        self.assertEqual(stat.S_IMODE((out / "attempt.private.json").stat().st_mode),
                         0o600)


if __name__ == "__main__":
    unittest.main()
