"""Offline-only source partition, action metric and no-replay diagnostic tests."""

from __future__ import annotations

from hashlib import sha256
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from cursibench import qwen38_real_gui_diagnostic_v1 as core
from cursibench import qwen38_real_gui_diagnostic_run_v1 as runner
from cursibench.scale_action_contract import ContractLimits, make_observation


ROOT = Path(__file__).resolve().parents[1]


def _observation(step=0):
    image = Image.new("RGB", (1280, 800), (230, 232, 235))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return make_observation(
        task_id="public-train-diagnostic-test",
        task_binding_sha256="a" * 64,
        instruction="Use the visible public training document.",
        step=step, screenshot_bytes=stream.getvalue(),
        a11y_text="", dom_text="", controls=(),
        previous_action_result=(None if step == 0 else
                                {"status": "applied", "code": "ok"}),
        memory="",
        limits=ContractLimits(max_step=20))


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.prereg, _ = core.load_prereg(ROOT)
        self.episodes = [
            {"workflow": workflow, "task_id": "public-train-" + workflow,
             "package_sha256": character * 64,
             "source_gui_receipt_sha256": character * 64,
             "turns": [None] * count}
            for workflow, character, count in (
                ("impress", "a", 18), ("calc", "b", 10),
                ("writer", "c", 7))]

    def test_only_one_real_task_is_blocked_before_renderer_or_paid_work(self):
        with self.assertRaisesRegex(core.DiagnosticError,
                                    "distinct_train_workflows_not_ready"):
            core.split_tasks(self.episodes[:1], self.prereg)

    def test_task_disjoint_split_is_deterministic_and_uses_no_action_labels(self):
        first = core.split_tasks(self.episodes, self.prereg)
        second = core.split_tasks(self.episodes, self.prereg)
        self.assertEqual(first, second)
        train, holdout = first
        self.assertFalse(set(train) & set(holdout))
        self.assertEqual(len(train), 2)
        self.assertEqual(len(holdout), 1)
        self.assertGreaterEqual(sum(len(self.episodes[index]["turns"])
                                    for index in train), 24)
        self.assertGreaterEqual(sum(len(self.episodes[index]["turns"])
                                    for index in holdout), 6)

    def test_multistep_schedule_covers_every_train_turn_and_cost_cap(self):
        lengths = [1500] * 28
        batches = core.schedule(lengths, self.prereg)
        self.assertEqual(len(batches), 64)
        self.assertEqual({len(batch) for batch in batches}, {2})
        self.assertEqual(set(index for batch in batches for index in batch),
                         set(range(28)))
        quote = core.nominal_quote(
            lengths, [1400] * 7, batches, self.prereg)
        self.assertGreater(float(quote), 0)
        self.assertFalse(self.prereg["pricing_quote_is_dispatch_gate"])

    def test_action_comparison_is_strict_and_is_not_an_app_score(self):
        observation = _observation()
        reference = {"type": "wait", "duration_ms": 1000}
        correct = core.score_action_text(
            '{"type":"wait","duration_ms":1000}',
            observation, reference)
        malformed = core.score_action_text(
            'not a JSON action', observation, reference)
        wrong = core.score_action_text(
            '{"type":"finish"}', observation, reference)
        self.assertEqual(correct, {
            "format_valid": True, "action_type_match": True,
            "payload_exact_match": True, "error_type": None})
        self.assertFalse(malformed["format_valid"])
        self.assertTrue(wrong["format_valid"])
        self.assertFalse(wrong["action_type_match"])

    def test_non_wait_summary_keeps_waits_out_of_action_agreement(self):
        def fields(valid):
            return {"format_valid": valid,
                    "action_type_match": valid,
                    "payload_exact_match": valid,
                    "error_type": None}
        summary = runner.paired_summary([
            {"reference_type": "wait",
             "base": fields(True), "lora": fields(True)},
            {"reference_type": "click",
             "base": fields(False), "lora": fields(True)},
        ])
        self.assertEqual(summary["holdout_turns"], 2)
        self.assertEqual(summary["non_wait_reference_turns"], 1)
        self.assertEqual(summary["base_non_wait_action_type_match"], 0)
        self.assertEqual(summary["lora_non_wait_action_type_match"], 1)

    def test_ready_plan_is_json_stable_and_has_disjoint_task_refs(self):
        identity = {"model": core.MODEL,
                    "renderer": "qwen3_5_disable_thinking",
                    "image_processor": "Qwen2VLImageProcessorPil"}
        def fake_render(cell_id, task_ids, receipts, turns, vision):
            return SimpleNamespace(
                datums=[object()] * len(turns),
                prompts=[object()] * len(turns),
                receipt={"cell_id": cell_id, "task_ids": task_ids,
                         "receipt_shas": receipts,
                         "datum_token_lengths": [1500] * len(turns),
                         "prompt_token_lengths": [1400] * len(turns)})
        with patch.object(core, "load_sources", return_value=(
                self.episodes, "d" * 64, "e" * 64)), \
             patch.object(core, "_render_turns", side_effect=fake_render):
            plan, proposal = core.prepare_plan(
                ROOT, ROOT / "unused-sources", ROOT / "unused-ratification",
                lambda: SimpleNamespace(identity=identity))
        self.assertEqual(json.loads(core.canonical(plan)), plan)
        self.assertEqual(len(plan["batches"]), 64)
        self.assertEqual(len(plan["train_turn_refs"]), 25 if
                         plan["holdout_source_indexes"] == [1] else 28)
        self.assertEqual(proposal["selection_tasks_used"], 0)
        self.assertEqual(proposal["final_tasks_used"], 0)

    def test_one_source_plan_refuses_before_renderer_load(self):
        with patch.object(core, "load_sources", return_value=(
                self.episodes[:1], "d" * 64, "e" * 64)):
            with self.assertRaisesRegex(core.DiagnosticError,
                                        "distinct_train_workflows_not_ready"):
                core.prepare_plan(
                    ROOT, ROOT / "unused-sources",
                    ROOT / "unused-ratification",
                    lambda: self.fail("renderer must not load"))


class JournalTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name) / "run"
        self.directory.mkdir(mode=0o700)

    def test_uncertain_provider_call_is_durable_and_never_replayed(self):
        journal = runner.RunJournal(self.directory, {"plan_sha256": "a" * 64})
        calls = []
        def fail():
            calls.append("called")
            raise TimeoutError("fake transport timeout")
        with self.assertRaisesRegex(runner.RunError,
                                    "uncertain_no_replay"):
            journal.call("forward_backward", {"step": 1}, fail)
        self.assertEqual(calls, ["called"])
        state = runner.RunJournal.audit_existing(self.directory).snapshot()
        self.assertEqual(state["uncertain_operations"], 1)
        self.assertFalse(state["automatic_replay_authorized"])
        with self.assertRaises(runner.RunError):
            runner.RunJournal(self.directory, {"plan_sha256": "a" * 64})

    def test_completed_result_byte_tamper_is_detected(self):
        journal = runner.RunJournal(self.directory, {"plan_sha256": "a" * 64})
        journal.call("sample", {"kind": "base"},
                     lambda: {"status": "completed", "text": "private"})
        result = self.directory / "operation-0001.result.private.json"
        result.write_bytes(b'{}\n')
        with self.assertRaisesRegex(runner.RunError,
                                    "provider_result_bytes_changed"):
            runner.RunJournal.audit_existing(self.directory)

    def test_dispatched_request_byte_tamper_is_detected(self):
        journal = runner.RunJournal(self.directory, {"plan_sha256": "a" * 64})
        journal.call("sample", {"kind": "base"},
                     lambda: {"status": "completed"})
        request = self.directory / "operation-0001.request.private.json"
        request.write_bytes(b'{}\n')
        with self.assertRaisesRegex(runner.RunError,
                                    "provider_request_bytes_changed"):
            runner.RunJournal.audit_existing(self.directory)


class MatchedFakeRunTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.work = self.root / "work"
        self.work.mkdir(mode=0o700)
        prereg = self.root / core.PREREG_RELATIVE
        prereg.parent.mkdir(parents=True)
        prereg.write_bytes((ROOT / core.PREREG_RELATIVE).read_bytes())
        self.prereg, self.prereg_sha = core.load_prereg(self.root)
        self.turns = [{"observation": _observation(index),
                       "action": {"type": "wait", "duration_ms": 1000}}
                      for index in range(7)]
        self.vision = SimpleNamespace(identity={"model": core.MODEL})
        self.train_batch = SimpleNamespace(datums=[object()] * 28)
        self.holdout_batch = SimpleNamespace(prompts=[object()] * 7)
        self.batches = core.schedule([1500] * 28, self.prereg)
        self.plan = {
            "schema": core.PLAN_SCHEMA,
            "status": "eligible_pending_immutable_public_freeze",
            "prereg_sha256": self.prereg_sha,
            "batches": self.batches,
            "training_datum_lengths": [1500] * 28,
            "holdout_prompt_lengths": [1400] * 7,
            "train_render_receipt_sha256": "b" * 64,
            "holdout_render_receipt_sha256": "c" * 64,
            "scheduled_train_tokens": 64 * 2 * 1500,
            "nominal_quote_usd": "1.000000000",
        }
        self.plan_path = self.work / "plan.private.json"
        self.plan_path.write_bytes(core.canonical(self.plan))
        self.plan_path.chmod(0o600)
        self.plan_sha = sha256(self.plan_path.read_bytes()).hexdigest()
        self.witness = {
            "schema": runner.WITNESS_SCHEMA,
            "status": "frozen_before_diagnostic_paid_dispatch",
            "plan_sha256": self.plan_sha,
            "prereg_sha256": self.prereg_sha,
            "student_model": core.MODEL,
            "eligible_split": "train",
            "task_disjoint_holdout": True,
            "minimum_distinct_workflows": 3,
            "optimizer_steps": 64,
            "pricing_quote_is_dispatch_gate": False,
            "diagnostic_only": True,
            "selection_and_final_task_access": False,
            "paid_diagnostic_calls_before_freeze": 0,
            "official_researcher_campaigns_before_freeze": 0,
            "official_final_model_attempts_before_freeze": 0,
        }
        self.calls = []

    def fake_provider_factory(self, vision, prereg, run_id):
        calls = self.calls
        class FakeProvider:
            service = None
            def open_service(self):
                self.service = object()
                calls.append("service")
                return {"status": "service_opened"}
            def open_training(self):
                calls.append("train")
                return {"status": "opened"}
            def forward_backward(self, datums):
                calls.append("forward")
                return {"status": "completed"}
            def optim_step(self):
                calls.append("optim")
                return {"status": "completed"}
            def save_state(self, step):
                calls.append("save_state")
                return {"status": "completed",
                        "checkpoint_path": "tinker://fake/weights/state"}
            def save_sampler(self):
                calls.append("save_sampler")
                return {"status": "completed",
                        "checkpoint_path":
                        "tinker://fake/sampler_weights/final"}
            def open_sampler(self, kind, checkpoint):
                calls.append("open_" + kind)
                return {"status": "completed",
                        "reported_base_model": core.MODEL}
            def sample(self, kind, prompt):
                calls.append("sample_" + kind)
                return {"status": "completed",
                        "text": ('{"type":"wait","duration_ms":1000}'
                                 if kind == "lora" else "invalid"),
                        "output_tokens": 8}
            def close(self, status):
                calls.append("close")
                return {"status": "closed"}
        return FakeProvider()

    def _run(self, run_name):
        runtime = {
            "status": "pre_dispatch_runtime_evidence_verified",
            "provider_calls": 0, "dispatch_authorized": False,
            "runtime_spec_sha256": "d" * 64,
            "toy_public_receipt_sha256": "e" * 64,
        }
        materialized = (self.plan, {}, self.train_batch,
                        self.holdout_batch, self.turns, self.vision)
        with patch.object(core, "materialize_plan", return_value=materialized), \
             patch.object(runner.runtime_gate, "validate",
                          return_value=runtime), \
             patch.object(runner.runtime_gate, "assert_active_worker"), \
             patch.dict(os.environ, {"HF_HUB_OFFLINE": "1",
                                  "TRANSFORMERS_OFFLINE": "1"}):
            return runner.run(
                repo_root=self.root,
                manifest_path=self.work / "sources.private.json",
                ratification_path=self.work / "ratification.private.json",
                plan_path=self.plan_path,
                public_commit="f" * 40,
                run_dir=self.work / run_name,
                renderer_loader=lambda: self.vision,
                provider_factory=self.fake_provider_factory,
                witness_fetcher=lambda _url: core.canonical(self.witness),
                require_provider_key=False)

    def test_64_step_fake_training_and_matched_holdout_are_diagnostic_only(self):
        result = self._run("fake-run-one")
        self.assertEqual(self.calls.count("forward"), 64)
        self.assertEqual(self.calls.count("optim"), 64)
        self.assertEqual(self.calls.count("save_state"), 4)
        self.assertEqual(self.calls.count("sample_base"), 7)
        self.assertEqual(self.calls.count("sample_lora"), 7)
        self.assertEqual(result["base_format_valid"], 0)
        self.assertEqual(result["lora_format_valid"], 7)
        self.assertEqual(result["paired_format_valid_gain"], 7)
        self.assertEqual(result["non_wait_reference_turns"], 0)
        self.assertEqual(result["observed_sample_output_tokens"], 112)
        self.assertIsNone(result["provider_billed_tokens"])
        self.assertFalse(result["pricing_quote_is_dispatch_gate"])
        self.assertFalse(result["official_researcher_campaign"])
        self.assertIsNone(result["application_success_estimate"])
        self.assertIsNone(result["benchmark_score"])
        state = runner.RunJournal.audit_existing(
            self.work / "fake-run-one").snapshot()
        self.assertEqual(state["uncertain_operations"], 0)

    def test_same_plan_cannot_dispatch_again_under_new_run_directory(self):
        self._run("fake-run-one")
        calls_before = len(self.calls)
        with self.assertRaises(runner.RunError):
            self._run("fake-run-two")
        self.assertEqual(len(self.calls), calls_before)
        self.assertFalse((self.work / "fake-run-two").exists())

    def test_immutable_witness_claimed_prior_paid_call_is_rejected(self):
        self.witness["paid_diagnostic_calls_before_freeze"] = 1
        with self.assertRaisesRegex(runner.RunError,
                                    "public_witness_not_exact"):
            self._run("fake-run-one")
        self.assertEqual(self.calls, [])
        self.assertFalse((self.work / "fake-run-one").exists())


if __name__ == "__main__":
    unittest.main()
