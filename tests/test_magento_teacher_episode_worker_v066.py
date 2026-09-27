"""Fake original-Magento teacher episodes; no Docker, model or final task."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import copy
from hashlib import sha256
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

from cursibench import full_study_teacher_adapter_v1 as teacher
from cursibench.scale_action_output_v066 import normalize_model_action
from magento_catalog_factory import plan, seed
from tests.test_magento_catalog_saved_state import CASE, baseline
from tests.test_full_study_teacher_adapter_v1 import (
    FakeSession as FakeCampaignSession, write_private,
)
from native_desktop_factory.v066_final_freeze import (
    source_hashes as common_source_hashes,
)
from native_desktop_factory import qwen_v066_adapter
from tools import magento_teacher_episode_worker_v066 as worker_module


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


class FakeLocator:
    async def element_handles(self): return []


class FakeMouse:
    def __init__(self, calls): self.calls = calls
    async def click(self, x, y): self.calls.append(("click", x, y))


class FakePage:
    def __init__(self, png: bytes):
        self.png = png
        self.url = "http://127.0.0.1:7820/admin/dashboard"
        self.calls = []
        self.mouse = FakeMouse(self.calls)
    async def screenshot(self, **_kwargs): return self.png
    def locator(self, _selector): return FakeLocator()
    async def wait_for_load_state(self, *_args, **_kwargs):
        self.calls.append(("networkidle",))


class FakeSession:
    def __init__(self, before: dict, after: dict, png: bytes):
        self.page = FakePage(png)
        self.baseline_state = before
        self.after = after
        self.fresh_clone_prepared = True
        self.native_quote_visible = True
        self.reset_proof = None
    async def saved_state(self):
        return {"snapshot": self.after,
                "native_save_observed": True,
                "gui_reload_frame_sha256": digest(self.page.png)}


class FakeRuntime:
    qualified = True
    def __init__(self, before: dict, after: dict, png: bytes):
        self.before, self.after, self.png = before, after, png
        self.calls = []
        self.bad_reset = False
        self.session = None
    def reserve_capacity(self, _request):
        self.calls.append("local_capacity_reserved")
        return {"status": "reserved_before_original_gui_start",
                "provider_invoice_usd": None}
    @asynccontextmanager
    async def open_case(self, _case, _out_dir):
        self.calls.append("original_gui_open")
        self.session = FakeSession(self.before, self.after, self.png)
        try:
            yield self.session
        finally:
            self.calls.append("fresh_clone_reset")
            self.session.reset_proof = {
                "fresh_clone_reset_passed": not self.bad_reset,
                "different_app_container_ids": True,
                "different_search_container_ids": True,
                "no_host_mounts": True,
                "both_pairs_removed": True,
                "restored_snapshot": copy.deepcopy(self.before),
            }


class MagentoTeacherWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="magento-teacher-fake-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.work = self.root / "work"
        self.work.mkdir(mode=0o700)
        self.out = self.work / "episode-001"
        self.out.mkdir(mode=0o700)
        (self.out / "frames").mkdir(mode=0o700)
        self.case = {**CASE, "split": "train",
                     "target_variants": [CASE["target_variants"][0]],
                     "instruction": "Repair the training price in Magento."}
        self.case["package_sha256"] = plan.digest({
            key: value for key, value in self.case.items()
            if key != "package_sha256"})
        self.task = {"task_id": self.case["task_id"],
                     "package_sha256": self.case["package_sha256"],
                     "visible_instruction": self.case["instruction"]}
        before = baseline()
        del before["database"]["prices"][str(CASE["target_variants"][1]
                                               ["entity_id"])]
        after = copy.deepcopy(before)
        target = self.case["target_variants"][0]
        after["database"]["prices"][str(target["entity_id"])]["price"] = (
            target["target_price"])
        after["database"]["hashes"]["full"]["catalog_product_entity"] = (
            "changed")
        after["search"]["full_sha256"] = "changed"
        after["search"]["parent_document_sha256"] = "changed"
        png = io.BytesIO()
        Image.new("RGB", (160, 120), (70, 80, 90)).save(png, "PNG")
        self.runtime = FakeRuntime(before, after, png.getvalue())
        self.worker = worker_module.MagentoTeacherEpisodeWorker(
            plan_path=self.work / "magento-plan.private.json",
            plan_sha256="a" * 64, private_output_root=self.work)
        self.events = []
        self.turns = []
        self.e2b_calls = []

    def teacher_sample(self, observation, current_frame_id):
        self.events.append("fake_teacher_sample")
        self.assertEqual(current_frame_id(), observation.frame_id)
        raw = ('{"type":"click","target":{"x":5,"y":6}}'
               if observation.step == 0 else '{"type":"finish"}')
        action = normalize_model_action(raw, observation,
                                        current_frame_id=current_frame_id())
        result_sha = digest(f"fake-result-{observation.step}".encode())
        trace = {"step": observation.step,
                 "frame_id": observation.frame_id,
                 "frame_sha256": digest(observation.screenshot_bytes),
                 "observation": {
                     "task_id": observation.task_id,
                     "task_binding_sha256": observation.task_binding_sha256,
                     "instruction": observation.instruction,
                     "a11y_text": observation.a11y_text,
                     "dom_text": observation.dom_text,
                     "controls": [vars(control) for control in
                                  observation.controls],
                     "previous_action_result": observation.previous_action_result,
                     "memory": observation.memory,
                     "issued_at": observation.issued_at},
                 "action": action,
                 "teacher_result_sha256": result_sha}
        self.turns.append({"observation": observation, "action": action,
                           "trace_row": trace,
                           "teacher_result_sha256": result_sha})
        return {"action": action, "trace_row": trace,
                "teacher_result_sha256": result_sha}

    def local_dispatch(self, *, attempt_id, category, work, request,
                       reserve_usd, resource_reservation, provider):
        self.assertEqual(category, "storage_application")
        self.assertEqual(resource_reservation, {})
        self.assertGreater(float(reserve_usd), 0)
        self.assertEqual(work["task_id"], self.task["task_id"])
        self.events.append("local_cost_reserved")
        result = provider(request)
        return {"attempt_id": attempt_id, "result": result,
                "result_sha256": digest(worker_module._canonical(result)),
                "billing_state": "awaiting_provider_usage_reconciliation"}

    def e2b(self, **kwargs):
        self.e2b_calls.append(kwargs)
        raise AssertionError("Self-hosted Magento cannot use E2B")

    def run_fake(self):
        self.worker.backend = self.runtime
        self.worker.dispatch_local_service = self.local_dispatch
        with patch.object(self.worker, "_require_live", return_value={
                "hourly_usd_upper": "1.00"}), \
             patch.object(self.worker, "_train_case", return_value=self.case):
            return self.worker.run_episode(
                task=self.task, out_dir=self.out,
                sample_teacher=self.teacher_sample,
                dispatch_e2b=self.e2b)

    def test_default_refuses_before_backend_or_paid_call(self):
        with self.assertRaisesRegex(worker_module.MagentoTeacherWorkerError,
                                    "dedicated_frozen_lane"):
            self.worker.run_episode(task=self.task, out_dir=self.out,
                                    sample_teacher=self.teacher_sample,
                                    dispatch_e2b=self.e2b)
        self.assertEqual(self.events, [])
        self.assertEqual(self.runtime.calls, [])
        self.assertEqual(self.e2b_calls, [])

    def test_live_flag_and_injected_backend_still_refuse_without_qualified_lane(self):
        self.worker.enable_live = True
        self.worker.backend = self.runtime
        self.worker.dispatch_local_service = self.local_dispatch
        with self.assertRaisesRegex(worker_module.MagentoTeacherWorkerError,
                                    "dedicated_frozen_lane"):
            self.worker.run_episode(task=self.task, out_dir=self.out,
                                    sample_teacher=self.teacher_sample,
                                    dispatch_e2b=self.e2b)
        self.assertEqual(self.runtime.calls, [])
        self.assertEqual(self.events, [])

    def test_fake_saved_state_and_fresh_clone_episode_matches_teacher_contract(self):
        result = self.run_fake()
        receipt_sha = teacher._verify_episode(
            self.out, result, cell_id="magento-admin", task=self.task,
            runtime_sha=self.worker.runtime_sha256,
            adapter_sha=self.worker.adapter_sha256,
            verifier_sha=self.worker.verifier_sha256,
            turns=self.turns, e2b_attempt_ids=[], requires_e2b=False)
        self.assertEqual(receipt_sha, result["episode_receipt_sha256"])
        self.assertEqual(self.events[0], "local_cost_reserved")
        self.assertEqual(self.runtime.calls, [
            "local_capacity_reserved", "original_gui_open",
            "fresh_clone_reset"])
        self.assertEqual(self.runtime.session.page.calls,
                         [("click", 5, 6), ("networkidle",)])
        self.assertEqual(self.e2b_calls, [])
        reset = json.loads((self.out / "reset.private.json").read_bytes())
        self.assertEqual(reset["baseline_semantic_sha256"],
                         reset["restored_semantic_sha256"])
        self.assertNotEqual(reset["raw_baseline_state_ref"]["path"],
                            reset["raw_restored_state_ref"]["path"])
        state = json.loads((self.out / "saved-state.private.json").read_bytes())
        self.assertTrue(state["score_receipt"]["passed"])
        self.assertIsNone(json.loads((self.out / "artifacts" /
            "local-service.private.json").read_bytes())[
            "provider_invoice_usd"])

    def test_bad_saved_state_keeps_failure_and_never_admits(self):
        target = self.case["target_variants"][0]
        self.runtime.after["database"]["prices"][str(target["entity_id"])] = (
            copy.deepcopy(self.runtime.before["database"]["prices"][str(
                target["entity_id"])]))
        with self.assertRaisesRegex(worker_module.MagentoTeacherWorkerError,
                                    "positive_not_saved"):
            self.run_fake()
        self.assertFalse((self.out / "episode.private.json").exists())
        self.assertTrue((self.out / "failure.private.json").is_file())
        self.assertEqual(self.runtime.calls[-1], "fresh_clone_reset")

    def test_inexact_physical_reset_cannot_be_teacher_data(self):
        self.runtime.bad_reset = True
        with self.assertRaisesRegex(worker_module.MagentoTeacherWorkerError,
                                    "fresh_clone_reset_unverified"):
            self.run_fake()
        self.assertFalse((self.out / "episode.private.json").exists())

    def test_stale_frame_after_paid_teacher_call_aborts_before_gui_action(self):
        def stale(observation, current_frame_id):
            result = self.teacher_sample(observation, current_frame_id)
            self.runtime.session.page.url = "http://127.0.0.1:7820/admin/changed"
            return result
        self.worker.backend = self.runtime
        self.worker.dispatch_local_service = self.local_dispatch
        with patch.object(self.worker, "_require_live", return_value={
                "hourly_usd_upper": "1.00"}), \
             patch.object(self.worker, "_train_case", return_value=self.case):
            with self.assertRaisesRegex(worker_module.MagentoTeacherWorkerError,
                                        "frame_changed_after_paid_call"):
                self.worker.run_episode(task=self.task, out_dir=self.out,
                                        sample_teacher=stale,
                                        dispatch_e2b=self.e2b)
        self.assertEqual(self.runtime.session.page.calls, [])
        self.assertFalse((self.out / "episode.private.json").exists())

    def test_train_partition_and_package_are_checked_offline(self):
        cases = []
        for index in range(20):
            case = dict(self.case,
                        task_id=f"magento-catalog-{index:016x}")
            case["quote_page_body_sha256"] = digest(
                case["quote_page_body"].encode())
            case["package_sha256"] = plan.digest({key: value
                for key, value in case.items() if key != "package_sha256"})
            cases.append(case)
        data = {"schema": plan.SCHEMA,
                "status": "offline_candidates_not_gui_admitted",
                "official_final_admitted_count": 0,
                "cases": {"train": cases, "selection": [],
                          "official_candidate": []}}
        path = self.work / "magento-plan.private.json"
        path.write_bytes(worker_module._canonical(data))
        path.chmod(0o600)
        self.worker.plan_path = path.resolve()
        self.worker.plan_sha256 = digest(path.read_bytes())
        selected = {"task_id": cases[0]["task_id"],
                    "package_sha256": cases[0]["package_sha256"],
                    "visible_instruction": cases[0]["instruction"]}
        with patch.object(worker_module, "ROOT", self.root), \
             patch.object(seed, "ROOT", self.root):
            self.assertEqual(self.worker._train_case(selected)["split"],
                             "train")
            with self.assertRaisesRegex(worker_module.MagentoTeacherWorkerError,
                                        "cross_split_or_instruction"):
                self.worker._train_case({**selected,
                    "visible_instruction": "changed instruction"})

    def test_fake_campaign_collect_train_batch_reserves_local_before_teacher(self):
        common = common_source_hashes()
        profiles = {cell_id: {
            "common_source_sha256s": common,
            "adapter_sha256": (self.worker.adapter_sha256
                               if cell_id == "magento-admin" else "e" * 64),
        } for cell_id in teacher.matrix.CELLS}
        profiles["desktop-native"]["adapter_sha256"] = digest(
            Path(qwen_v066_adapter.__file__).read_bytes())
        ratification = {
            "schema": "cua-six-cell-action-profile-v066-ratification-v1",
            "status": "ratified_pre_result",
            "ratified_utc": datetime.now(timezone.utc).isoformat(),
            "action_profile": teacher.ACTION_PROFILE_VERSION,
            "common_source_sha256s": common,
            "cell_profiles": profiles,
            "base_and_selected_identical": True,
            "hidden_final_model_attempts_before_ratification": 0,
        }
        ratification_path = self.root / "synthetic-ratification.private.json"
        write_private(ratification_path, ratification)
        campaign = FakeCampaignSession(self.root, ratification_path,
                                       ratification)
        magento_plan = next(row for row in campaign.study.plan["cells"]
                            if row["cell_id"] == "magento-admin")
        magento_plan["matched_bindings"] = {
            "runtime": self.worker.runtime_sha256,
            "verifier": self.worker.verifier_sha256,
        }
        campaign.views["train"] = ({"task_id": self.task["task_id"],
                                    "package_sha256": self.task[
                                        "package_sha256"]},)
        campaign.proposal["train_task_ids"] = [self.task["task_id"]]
        campaign.proposal_sha = write_private(campaign.proposal_path,
                                              campaign.proposal)
        context = self.work / "synthetic-train-context.private.json"
        write_private(context, {
            "schema": "cua-full-study-researcher-train-view-v1",
            "cell_id": "magento-admin", "tasks": [self.task],
        })
        campaign.context_sha = digest(context.read_bytes())
        self.worker.backend = self.runtime
        self.worker.dispatch_local_service = campaign.dispatch_paid
        calls = []

        def provider(request):
            calls.append(request)
            action = ('{"type":"click","target":{"x":5,"y":6}}'
                      if request["step"] == 0 else '{"type":"finish"}')
            return {"text": action,
                    "receipt": {"reported_model": teacher.matrix.TEACHER,
                                "status": "completed",
                                "response_id": "fake-" + str(len(calls)),
                                "usage": {"input_tokens": 100,
                                          "output_tokens": 10}}}

        def fake_render(cell_id, task_ids, episode_shas, turns, _vision):
            self.assertEqual(cell_id, "magento-admin")
            self.assertEqual(task_ids, [self.task["task_id"]])
            self.assertEqual(len(episode_shas), 1)
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

        with patch.object(self.worker, "_require_live", return_value={
                "hourly_usd_upper": "1.00"}), \
             patch.object(self.worker, "_train_case", return_value=self.case), \
             patch.object(teacher, "_load_renderer", return_value=object()), \
             patch.object(teacher, "_render_turns", side_effect=fake_render):
            collected = teacher.collect_train_batch(
                campaign, 1, context,
                self.work / "teacher-round-001", self.worker,
                teacher_provider=provider)
        self.assertEqual(len(calls), 2)
        self.assertEqual([row["category"] for row in campaign.calls],
                         ["storage_application", "teacher_rollout",
                          "teacher_rollout"])
        self.assertEqual(campaign.calls[0]["resource_reservation"], {})
        self.assertEqual(json.loads(collected.dataset_manifest_path.read_bytes())[
            "selection_task_count"], 0)
        self.assertEqual(self.e2b_calls, [])


if __name__ == "__main__":
    unittest.main()
