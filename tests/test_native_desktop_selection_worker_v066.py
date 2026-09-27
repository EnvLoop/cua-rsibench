"""No-cloud 20-task Desktop selection and paid-coverage regression tests."""

from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

from cursibench import full_study_selection_paid_coverage_v1 as coverage
from cursibench.scale_action_contract import ContractLimits, make_observation
from native_desktop_factory import selection_worker_v066 as selection
from native_desktop_factory.teacher_episode_worker_v066 import _semantic_input


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "native_desktop_factory/dev-fixtures"
GUEST_PUBLIC = ROOT / "docs/evidence/native-wdi-guest-content-identity-2026-09-27.json"
GUEST = json.loads(GUEST_PUBLIC.read_bytes())


def png() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (1280, 800), "white").save(output, "PNG")
    return output.getvalue()


def source_case(workflow: str):
    raw_dir = PUBLIC / ("wdi-native-mex-" + workflow)
    baseline = next(path.read_bytes() for path in raw_dir.iterdir()
                    if path.suffix in (".xlsx", ".pptx", ".docx"))
    oracle = json.loads((raw_dir / "oracle.json").read_bytes())
    ext = ".xlsx" if workflow.startswith("calc-") else \
          ".pptx" if workflow == "impress-deck" else ".docx"
    positive_dir = (PUBLIC / "wdi-native-mex-impress-deck-normalized"
                    if ext == ".pptx" else raw_dir)
    positive = (positive_dir / "controls" / ("positive" + ext)).read_bytes()
    normalized = (next(positive_dir.glob("*.pptx")).read_bytes()
                  if ext == ".pptx" else baseline)
    return baseline, normalized, positive, oracle, ext


class FakeGuest:
    def __init__(self, backend, phase, lease, package):
        self.backend = backend
        self.phase = phase
        self.lease = lease
        self.package = package
        self.sandbox_id = ("fake-" + phase + "-" +
                           package.identity["task_id"])
        self.guest_content_sha256 = None
        self.profile_sha256 = None
        self.provider_shape_attested = False
        self.fresh_profile_absent = False
        self.neutral_input = None
        self.raw_input_sha256 = None
        self.killed = False
        self.latest = None
        self.frame = png()
        self.dispatched = []

    def prepare(self, *, source, filename, oracle, guest_identity):
        self.guest_content_sha256 = guest_identity["static_content_sha256"]
        self.provider_shape_attested = True
        self.fresh_profile_absent = True
        self.raw_input_sha256 = selection._sha(source)
        self.neutral_input = self.package.neutral
        self.profile_sha256 = ("b" * 64 if self.backend.reset_profile_drift and
                               self.phase == "reset" else "a" * 64)
        assert _semantic_input(source, Path(filename).suffix) == \
            _semantic_input(self.neutral_input, Path(filename).suffix)

    def observe(self, *, task, step, previous, memory, max_actions):
        self.latest = make_observation(
            task_id=task["task_id"],
            task_binding_sha256=task["package_sha256"],
            instruction=task["visible_instruction"],
            step=step, screenshot_bytes=self.frame,
            previous_action_result=previous, memory=memory,
            limits=ContractLimits(max_step=max_actions))
        return self.latest

    def current_frame_id(self):
        return ("stale" if self.backend.stale_after_sample and
                self.backend.sampled else self.latest.frame_id)

    def predispatch_frame(self):
        return self.frame

    def dispatch(self, action):
        assert self.current_frame_id() == self.latest.frame_id
        self.dispatched.append(action["type"])

    def read_saved(self):
        if self.phase == "reset":
            return self.neutral_input
        if ("click" in self.dispatched and "finish" in self.dispatched and
                not self.backend.unsolved):
            return self.package.positive
        return self.neutral_input

    def close(self):
        self.killed = True
        return True


class FakeBackend:
    is_fake = True

    def __init__(self):
        self.guests = []
        self.unsolved = False
        self.reset_profile_drift = False
        self.stale_after_sample = False
        self.sampled = False

    def create(self, phase, lease, package):
        guest = FakeGuest(self, phase, lease, package)
        self.guests.append(guest)
        return guest


class FakeSampler:
    is_fake = True

    def __init__(self):
        self.started = False
        self.closed = False
        self.invalid_ordinal = None
        self.provider_failure_ordinal = None
        self.backend = None

    def start(self, *, checkpoint_path, checkpoint_sha256,
              config, out_dir, attempt_id):
        assert checkpoint_path.startswith("tinker://fake/")
        self.started = True
        return {"schema": "cua-native-wdi-v066-sampler-setup-v1",
                "status": "ready",
                "checkpoint_path_sha256": checkpoint_sha256,
                "provider_invoice_usd": None}

    def sample(self, *, observation, ordinal, step, task_dir):
        if ordinal == self.provider_failure_ordinal:
            raise RuntimeError("fake transport failure")
        if self.backend is not None:
            self.backend.sampled = True
        text = ("not JSON" if ordinal == self.invalid_ordinal else
                '{"type":"click","target":{"x":500,"y":400}}'
                if step == 0 else '{"type":"finish"}')
        return {"status": "completed", "new_dispatch": True,
                "reused": False, "text": text,
                "usage": {"input_tokens": 100,
                          "output_tokens": 8,
                          "image_tokens": 12,
                          "provider_billed_tokens": None}}

    def close(self, *, success):
        self.closed = True


class FakeSession:
    def __init__(self, root, tasks, started):
        self.study = SimpleNamespace(repo_root=root)
        self.intent = {"cell_id": "desktop-native",
                       "e2b_sandbox_hours_cap": "20",
                       "e2b_usd_cap": "20"}
        self.views = {"selection": tasks}
        self.started = started
        self.calls = []
        self.omit_paid_for_coverage = None

        def training():
            return {"model": selection.MODEL,
                    "action_profile": selection.ACTION_PROFILE_VERSION,
                    "sample_max_tokens": 128,
                    "max_supervised_tokens": 32768,
                    "prefill_usd_per_million_tokens": "1",
                    "sample_usd_per_million_tokens": "2",
                    "billing_multiplier_upper": "1"}, "c" * 64
        self.study.student_training_configuration = training

    def dispatch_paid(self, *, attempt_id, category, work, request,
                      reserve_usd, resource_reservation, provider):
        call = {"attempt_id": attempt_id, "category": category,
                "work": work, "request": request,
                "reserve_usd": reserve_usd,
                "resource_reservation": resource_reservation}
        self.calls.append(call)
        result = provider(request)
        call["result"] = result
        return {"attempt_id": attempt_id, "result": result,
                "result_sha256": selection._sha(selection._canonical(result)),
                "billing_state": "awaiting_provider_usage_reconciliation"}

    def _selection_paid_coverage(self, *, attempt_id,
                                 checkpoint_sha256, paid_attempt_ids):
        return coverage.validate(
            cell_id="desktop-native", attempt_id=attempt_id,
            checkpoint_sha256=checkpoint_sha256,
            selection_tasks=self.started["selection_tasks"],
            selection_identities_sha256=
                self.started["selection_identities_sha256"],
            paid_calls=[{"attempt_id": row["attempt_id"],
                         "category": row["category"],
                         "request": row["request"],
                         "result_present": "result" in row,
                         "result_status": row.get("result", {}).get("status")}
                        for row in self.calls if "result" in row and
                        row["attempt_id"] != self.omit_paid_for_coverage],
            related_paid_attempt_ids={row["attempt_id"]
                                      for row in self.calls})

    def _selection_result(self, result, *, checkpoint_sha256):
        expected = {row["task_id"]: row["package_sha256"]
                    for row in self.views["selection"]}
        assert result["schema"] == selection.RESULT_SCHEMA
        assert result["checkpoint_sha256"] == checkpoint_sha256
        assert len(result["tasks"]) == 20
        assert {row["task_id"]: row["package_sha256"]
                for row in result["tasks"]} == expected
        return {row["task_id"]: row["score"] for row in result["tasks"]}


class DesktopSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="native-selection-fake-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / "work"
        self.work.mkdir(mode=0o700)
        self.out = self.work / "selection-001"
        workflows = (["calc-growth"] * 10 + ["impress-deck"] * 5 +
                     ["writer-brief"] * 5)
        self.identities = [
            {"task_id": f"synthetic-selection-{index:03d}",
             "package_sha256": f"{index:064x}"}
            for index in range(1, 21)]
        self.packages = []
        for identity, workflow in zip(self.identities, workflows):
            source, neutral, positive, oracle, ext = source_case(workflow)
            oracle = {**oracle, "task_id": identity["task_id"],
                      "input_sha256": selection._sha(source),
                      "split": "selection"}
            self.packages.append(selection.SelectionPackage(
                identity=identity, source=source, oracle=oracle,
                filename=identity["task_id"] + ext,
                instruction="Use only the native GUI on this synthetic case.",
                source_inventory_sha256="d" * 64))
            # The fake backend sees the original source package and chooses
            # an already native-normalized development baseline when needed.
            object.__setattr__(self.packages[-1], "neutral", neutral)
            object.__setattr__(self.packages[-1], "positive", positive)
        checkpoint = "tinker://fake/sampler_weights/selected"
        self.started = {
            "attempt_id": "selection-001",
            "checkpoint_path_sha256": selection._sha(checkpoint.encode()),
            "selection_tasks": self.identities,
            "selection_identities_sha256": selection._sha(
                selection._canonical(self.identities)),
            "task_count": 20,
        }
        self.checkpoint = checkpoint
        self.session = FakeSession(self.root, self.identities,
                                   self.started)
        self.backend = FakeBackend()
        self.sampler = FakeSampler()
        self.sampler.backend = self.backend
        self.private_map = self.work / "private-map.json"
        self.private_map.write_text(json.dumps({"variant_salt": "a" * 64}))
        self.private_map.chmod(0o600)
        self.worker = selection.DesktopSelectionWorker(
            candidate_root=self.work / "not-used-candidate-root",
            private_map=self.private_map,
            guest_identity_public=GUEST_PUBLIC,
            expected_inventory_sha256="d" * 64,
            expected_guest_identity_sha256=selection._sha(
                GUEST_PUBLIC.read_bytes()),
            backend=self.backend, sampler=self.sampler)
        self.cell = {"sampling": {"seed": 23,
                                  "temperature": 0.0,
                                  "max_output_tokens": 64},
                     "execution": {"max_actions_per_task": 3,
                                   "max_wall_seconds_per_task": 720}}

    def run_fake(self):
        with patch.object(self.worker, "_require_frozen",
                          return_value=(self.cell, self.started)), \
             patch.object(self.worker, "_resolve_checkpoint",
                          return_value=self.checkpoint), \
             patch.object(selection, "_load_selection_packages",
                          return_value=self.packages):
            return self.worker.run_selection(
                session=self.session, started=self.started,
                checkpoint_path=self.checkpoint, out_dir=self.out)

    def test_default_refuses_before_output_or_provider(self):
        with self.assertRaisesRegex(selection.DesktopSelectionError,
                                    "selection_requires_real_six_cell_freeze"):
            self.worker.run_selection(
                session=self.session, started=self.started,
                checkpoint_path=self.checkpoint, out_dir=self.out)
        self.assertEqual(self.session.calls, [])
        self.assertFalse(self.out.exists())

    def test_native_observation_renders_exact_frozen_action_cap(self):
        sandbox = SimpleNamespace(sandbox_id="fake-viewport",
                                  screenshot=png)
        guest = selection.RealDesktopSelectionGuest(sandbox, phase="actor")
        task = {**self.identities[0],
                "visible_instruction": "Inspect the current LibreOffice GUI."}
        frame = guest.observe(task=task, step=0, previous=None,
                              memory="", max_actions=3)
        rendered = json.loads(selection.output_v066.render_for_model(
            frame)["instruction"])
        self.assertEqual(frame.limits.max_step, 3)
        self.assertEqual(rendered["max_actions"], 3)

    def test_twenty_per_id_profile_refs_are_hash_bound_and_not_optional(self):
        manifest = self.work / "selection-profiles.private.json"
        source = source_case("calc-growth")[0]
        profile_root = self.work / "profiles"
        profile_root.mkdir(mode=0o700)
        accepted = []
        for identity in self.identities:
            directory = profile_root / identity["task_id"]
            directory.mkdir(mode=0o700)
            frame = directory / "neutral-open.png"
            frame.write_bytes(png())
            frame.chmod(0o600)
            neutral = directory / "neutral-baseline.xlsx"
            neutral.write_bytes(source)
            neutral.chmod(0o600)
            receipt = {
                "schema":
                    "cua-native-wdi-v066-selection-profile-baseline-v1",
                "status": "profile_baseline_passed",
                "split": "selection", **identity,
                "canonical_profile_sha256": "a" * 64,
                "profile_snapshot_sha256s": ["a" * 64, "a" * 64],
                "guest_content_sha256": GUEST["static_content_sha256"],
                "provider_kind": "e2b_desktop",
                "sdk_version": "2.2.0",
                "provider_shape_attested": True,
                "fresh_profile_absent": True,
                "source_semantics_equal_after_neutral_save": True,
                "kill_returned": True,
                "is_running_after_kill": False,
                "model_calls": 0, "provider_invoice_usd": None,
                "lease_seconds": 600,
                "full_lease_reserved_usd": "0.166666667",
                "input_sha256": selection._sha(source),
                "neutral_input_sha256": selection._sha(source),
                "neutral_open_screenshot_sha256": selection._sha(
                    frame.read_bytes()),
                "sandbox_id_sha256": selection._sha(
                    identity["task_id"].encode()),
            }
            receipt_path = directory / "receipt.json"
            receipt_path.write_bytes(selection._canonical(receipt))
            receipt_path.chmod(0o600)
            accepted.append({**identity,
                             "canonical_profile_sha256": "a" * 64,
                             "receipt_path": str(receipt_path.relative_to(
                                 manifest.parent)),
                             "receipt_sha256": selection._sha(
                                 receipt_path.read_bytes())})
        value = {
            "schema":
                "cua-native-wdi-v066-selection-profile-baselines-private-v1",
            "candidate_inventory_sha256": "d" * 64,
            "guest_identity_public_sha256": selection._sha(
                GUEST_PUBLIC.read_bytes()),
            "distinct_sandbox_count": 20,
            "model_calls": 0, "provider_invoice_usd": None,
            "accepted": accepted,
        }
        manifest.write_bytes(selection._canonical(value))
        manifest.chmod(0o600)
        profiles = selection._load_selection_profiles(
            manifest, selection._sha(manifest.read_bytes()),
            "d" * 64, selection._sha(GUEST_PUBLIC.read_bytes()),
            GUEST["static_content_sha256"], self.identities)
        self.assertEqual(len(profiles), 20)
        with self.assertRaisesRegex(
                selection.DesktopSelectionError,
                "selection_per_id_profile_reference_missing"):
            selection._load_selection_profiles(
                None, None, "d" * 64,
                selection._sha(GUEST_PUBLIC.read_bytes()),
                GUEST["static_content_sha256"], self.identities)
        value["accepted"][0]["package_sha256"] = "0" * 64
        manifest.write_bytes(selection._canonical(value))
        with self.assertRaisesRegex(
                selection.DesktopSelectionError,
                "selection_per_id_profile_reference_invalid"):
            selection._load_selection_profiles(
                manifest, selection._sha(manifest.read_bytes()),
                "d" * 64, selection._sha(GUEST_PUBLIC.read_bytes()),
                GUEST["static_content_sha256"], self.identities)

    def test_twenty_fake_gui_tasks_pass_paid_coverage_and_saved_scoring(self):
        result = self.run_fake()
        self.assertEqual(result["status"], "scored")
        self.assertEqual(len(result["result"]["tasks"]), 20)
        self.assertEqual(sum(row["score"] for row in
                             result["result"]["tasks"]), 20)
        self.assertEqual(len(result["paid_attempt_ids"]), 81)
        self.assertEqual(sum(row["category"] == "e2b" for row in
                             self.session.calls), 40)
        self.assertEqual(sum(row["category"] == "tinker" for row in
                             self.session.calls), 41)
        self.assertTrue(all(guest.killed for guest in self.backend.guests))
        self.assertEqual(len(self.backend.guests), 40)
        ledger = json.loads(Path(result["task_ledger_path"]).read_bytes())
        self.assertEqual(ledger["schema"], selection.LEDGER_SCHEMA)
        self.assertTrue(all(len(row["e2b_paid_attempt_ids"]) == 2 and
                            len(row["qwen_paid_attempt_ids"]) == 2
                            for row in ledger["tasks"]))
        coverage_receipt = json.loads(
            Path(result["paid_coverage_path"]).read_bytes())
        self.assertEqual(coverage_receipt["task_count"], 20)
        self.assertEqual(coverage_receipt["sample_paid_attempt_count"], 40)
        self.assertEqual(coverage_receipt["environment_paid_attempt_count"], 40)
        self.assertFalse(coverage_receipt["provider_invoice_verified"])
        checked_scores = selection.campaign.CampaignSession._selection_result(
            SimpleNamespace(intent={"cell_id": "desktop-native"},
                            views={"selection": self.identities}),
            result["result"],
            checkpoint_sha256=self.started["checkpoint_path_sha256"])
        self.assertEqual(sum(checked_scores.values()), 20)

    def test_invalid_model_action_is_scored_zero_only_after_saved_reset(self):
        self.sampler.invalid_ordinal = 7
        result = self.run_fake()
        self.assertEqual(result["status"], "scored")
        self.assertEqual(sum(row["score"] for row in
                             result["result"]["tasks"]), 19)
        self.assertTrue(all(guest.killed for guest in self.backend.guests))
        self.assertEqual(len(self.backend.guests), 40)
        trace = json.loads((self.out / "tasks/task-007/actions.private.json").read_bytes())
        self.assertEqual(trace[0]["model_error_code"], "invalid_action_json")

    def test_provider_uncertainty_stops_without_task_zero_or_auto_replay(self):
        self.sampler.provider_failure_ordinal = 4
        result = self.run_fake()
        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["failure_type"], "provider")
        failure = json.loads(Path(result["invalid_receipt_path"]).read_bytes())
        self.assertFalse(failure["automatic_paid_replay_authorized"])
        self.assertFalse(failure["model_score_inferred_for_failed_task"])
        self.assertFalse((self.out / "selection-result.private.json").exists())
        self.assertTrue(all(guest.killed for guest in self.backend.guests))

    def test_fresh_reset_profile_drift_invalidates_whole_attempt(self):
        self.backend.reset_profile_drift = True
        result = self.run_fake()
        self.assertEqual(result["status"], "invalid")
        self.assertFalse((self.out / "selection-result.private.json").exists())
        self.assertTrue(all(guest.killed for guest in self.backend.guests))

    def test_physical_frame_drift_after_paid_sample_is_invalid_not_zero(self):
        self.backend.stale_after_sample = True
        result = self.run_fake()
        self.assertEqual(result["status"], "invalid")
        self.assertFalse((self.out / "selection-result.private.json").exists())
        self.assertTrue(self.session.calls)
        self.assertTrue(all(guest.killed for guest in self.backend.guests))

    def test_missing_paid_sample_in_coverage_cannot_register_scores(self):
        self.session.omit_paid_for_coverage = "selection-001-sample-007-001"
        result = self.run_fake()
        self.assertEqual(result["status"], "invalid")
        self.assertFalse((self.out / "selection-result.private.json").exists())
        self.assertEqual(len(self.backend.guests), 40)

    def test_e2b_budget_too_small_refuses_before_provider(self):
        self.session.intent["e2b_usd_cap"] = "1"
        with patch.object(self.worker, "_require_frozen",
                          return_value=(self.cell, self.started)), \
             patch.object(self.worker, "_resolve_checkpoint",
                          return_value=self.checkpoint):
            with self.assertRaisesRegex(
                    selection.DesktopSelectionError,
                    "selection_e2b_or_tinker_budget_insufficient"):
                self.worker.run_selection(
                    session=self.session, started=self.started,
                    checkpoint_path=self.checkpoint, out_dir=self.out)
        self.assertEqual(self.session.calls, [])
        self.assertFalse(self.out.exists())

    def test_rounded_full_lease_hour_cap_refuses_before_provider(self):
        self.session.intent["e2b_sandbox_hours_cap"] = "8.333333334"
        with patch.object(self.worker, "_require_frozen",
                          return_value=(self.cell, self.started)), \
             patch.object(self.worker, "_resolve_checkpoint",
                          return_value=self.checkpoint):
            with self.assertRaisesRegex(
                    selection.DesktopSelectionError,
                    "selection_e2b_or_tinker_budget_insufficient"):
                self.worker.run_selection(
                    session=self.session, started=self.started,
                    checkpoint_path=self.checkpoint, out_dir=self.out)
        self.assertEqual(self.session.calls, [])
        self.assertFalse(self.out.exists())

    def test_checkpoint_path_mismatch_refuses_before_provider(self):
        with patch.object(self.worker, "_require_frozen",
                          return_value=(self.cell, self.started)), \
             patch.object(self.worker, "_resolve_checkpoint",
                          return_value=self.checkpoint):
            with self.assertRaisesRegex(
                    selection.DesktopSelectionError,
                    "selection_checkpoint_path_changed"):
                self.worker.run_selection(
                    session=self.session, started=self.started,
                    checkpoint_path="tinker://fake/wrong-checkpoint",
                    out_dir=self.out)
        self.assertEqual(self.session.calls, [])
        self.assertFalse(self.out.exists())

    def test_raw_predispatch_mutation_rejected_by_task_auditor(self):
        result = self.run_fake()
        self.assertEqual(result["status"], "scored")
        path = self.out / "tasks/task-001/frames/predispatch-000.png"
        path.write_bytes(b"tampered")
        ledger = json.loads(Path(result["task_ledger_path"]).read_bytes())
        receipt = json.loads((self.out / "tasks/task-001/task.private.json").read_bytes())
        row = {**result["result"]["tasks"][0],
               "task_receipt_sha256": ledger["tasks"][0]["task_receipt_sha256"],
               "paid_attempt_ids": receipt["paid_attempt_ids"]}
        with self.assertRaisesRegex(
                selection.DesktopSelectionError,
                "selection_private_artifact_hash_changed"):
            self.worker._audit_task(
                batch_dir=self.out, package=self.packages[0],
                ordinal=1, row=row, private_salt="a" * 64)


if __name__ == "__main__":
    unittest.main()
