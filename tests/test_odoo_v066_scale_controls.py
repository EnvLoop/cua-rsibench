"""Offline split plans, holdout action chain and resumable journal invariants."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from enterprise_fallback.odoo18.hidden_factory import hidden_candidate_world
from enterprise_fallback.odoo18.partition_factory import (
    candidate_world, source_asset)
from tools import odoo_v066_scale_protocol_v1 as protocol
from tools import odoo_v066_scale_controller_v1 as controller
from tools import odoo_v066_scale_audit_v1 as auditor
from tools import odoo_v066_scale_recipes_v1 as recipes
from tests.test_odoo_v066_train_gui_recorder import FakeAdapter, FakePage, png


def write(path: Path, value: object, *, private: bool = True):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_bytes(value if type(value) is bytes else protocol.canonical(value))
    path.chmod(0o600 if private else 0o644)


class ScalePlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workers = self.root / "workers"
        self.plan_root = self.root / "plans"
        self.plan_root.mkdir(mode=0o700)
        seed = "synthetic-odoo-scale-train-seed-0123456789abcdef"
        hidden_seed = "synthetic-odoo-scale-hidden-seed-0123456789abcdef"
        worlds = {"train": candidate_world(seed, "train"),
                  "selection": candidate_world(seed, "selection"),
                  "official_hidden": hidden_candidate_world(hidden_seed)}
        checkpoints = {}
        tasks = {}
        for split, world in worlds.items():
            worker = self.workers / split
            private = worker / "private"
            private.mkdir(parents=True, mode=0o700)
            write(worker / ".env", f"ODOO_PARTITION={split}\n".encode())
            db, fs = (split + "-db").encode(), (split + "-fs").encode()
            write(private / "baseline.pgcustom", db)
            write(private / "baseline-filestore.tgz", fs)
            write(private / "baseline_snapshot.json", {})
            write(private / "baseline-filestore-manifest.json", {})
            checkpoint = {"db_sha256": protocol.digest(db),
                          "filestore_sha256": protocol.digest(fs),
                          "baseline_snapshot_sha256": protocol.digest(
                              (private / "baseline_snapshot.json").read_bytes()),
                          "baseline_filestore_manifest_sha256": protocol.digest(
                              (private / "baseline-filestore-manifest.json").read_bytes())}
            checkpoints[split] = checkpoint
            write(private / "checkpoint_receipt.json", checkpoint)
            write(private / "partition_cases.json", world)
            source_hashes = {}
            rows = []
            for family in protocol.FAMILIES:
                for case in world["cases"][family]:
                    asset = source_asset(case, world)
                    source_sha = protocol.digest(asset)
                    package = protocol.digest(
                        json.dumps(case, sort_keys=True).encode() + b"\n" + asset)
                    source_hashes[case["id"]] = source_sha
                    rows.append({"task_id": case["id"], "family": family,
                                 "package_sha256": package,
                                 "source_asset_sha256": source_sha,
                                 "visible_instruction_sha256": protocol.digest(
                                     case["prompt"].encode()),
                                 "checkpoint": checkpoint,
                                 "split": split,
                                 "task_binding_sha256": protocol.digest(
                                     case["id"].encode()),
                                 "source_label": (f"Purchase planning note for {case['sku']}"
                                                  if family == "inventory" else
                                                  f"{case['id']}-source.pdf")})
            write(private / "source_hashes.json", source_hashes)
            tasks[split] = rows
        self.full = {"schema": "envloop-odoo-v066-prospective-gui-requalification-plan-v1",
                     "ratification_sha256": protocol.RATIFICATION_SHA,
                     "tasks": tasks, "checkpoints": checkpoints,
                     "pilot": {"split": "train", "task_id": tasks["train"][0]["task_id"]},
                     "task_set_manifest_sha256": "f" * 64}
        self.full_private = self.plan_root / "full.private.json"
        write(self.full_private, self.full)
        self.full_public = self.root / "full.public.json"
        write(self.full_public, {"private_plan_sha256": protocol.digest(
            self.full_private.read_bytes()),
            "candidate_counts": {"train": 20, "selection": 20,
                                 "official_hidden": 100}}, private=False)
        self.train_pilot = self.root / "train-pilot.public.json"
        write(self.train_pilot, {
            "schema": "envloop-odoo-v066-gui-control-pilot-audit-v1",
            "fresh_train_candidate_controls_qualified": 1,
            "official_final_tasks_admitted": 0}, private=False)
        self.freeze = self.root / "freeze.public.json"
        write(self.freeze, {
            "schema": protocol.SOURCE_FREEZE_SCHEMA,
            "status": "frozen_after_selection_blank_compose_service_fix",
            "ratification_sha256": protocol.RATIFICATION_SHA,
            "source_sha256s": protocol.current_source_hashes(),
            "host_runtime": protocol.host_runtime(),
            "train_pilot_public_sha256": protocol.digest(
                self.train_pilot.read_bytes()),
            "accepted_train_pilot_count": 1,
            "old_source_freeze_sha256": protocol.OLD_LEASE_FREEZE_SHA256,
            "old_exact_return_draft_sha256":
                protocol.EXACT_RETURN_DRAFT_SHA256,
            "old_selection_gate_audit_freeze_sha256":
                protocol.SELECTION_GATE_AUDIT_FREEZE_SHA256,
            "selection_preflight_incident_public_sha256": protocol.digest((
                protocol.ROOT / "docs/evidence/odoo-v066-selection-blank-compose-preflight-2026-09-29.json").read_bytes()),
            "frame_guard_amendment": protocol.EXACT_RETURN_AMENDMENT,
            "selection_failure_public_sha256": protocol.digest((
                protocol.ROOT / "docs/evidence/odoo-v066-selection-first-exact-frame-flicker-incident-2026-09-28.json").read_bytes()),
            "retained_selection_failed_controls_before_freeze": 1,
            "official_final_gui_controls_before_freeze": 0,
            "official_final_tasks_admitted": 0,
            "model_attempts": 0}, private=False)

    def build(self, split):
        return protocol.build_split_plan(
            split=split, worker_dir=self.workers / split,
            full_private_plan=self.full_private,
            full_public_plan=self.full_public,
            source_freeze_path=self.freeze,
            train_pilot_public_path=self.train_pilot)

    def test_train_remaining_19_and_selection20_final100_are_split_local(self):
        for split, count, purchase_count in (
                ("train", 19, 4), ("selection", 20, 5),
                ("official_hidden", 100, 25)):
            private, public = self.build(split)
            self.assertEqual(private["task_count"], count)
            self.assertEqual(public["candidate_count"], count)
            self.assertEqual(public["family_candidate_counts"]["purchase"],
                             purchase_count)
            self.assertNotIn(self.full["pilot"]["task_id"],
                             {row["task_id"] for row in private["tasks"]}
                             if split == "train" else set())
            self.assertEqual(public["official_final_tasks_admitted"], 0)
            self.assertNotIn(private["tasks"][0]["task_id"], json.dumps(public))
            out_private = self.plan_root / f"{split}.private.json"
            out_public = self.root / f"{split}.public.json"
            protocol.write_new(out_private, private, private=True)
            protocol.write_new(out_public, public, private=False)
            validated = protocol.validate_split_plan(
                split=split, private_path=out_private,
                public_path=out_public, source_freeze_path=self.freeze)
            self.assertEqual(validated["task_count"], count)

    def test_source_or_checkpoint_drift_closes_plan(self):
        target = self.workers / "selection" / "private" / "baseline.pgcustom"
        write(target, b"changed")
        with self.assertRaisesRegex(protocol.ScaleProtocolError,
                                    "scale_task_source_or_checkpoint_changed"):
            self.build("selection")


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run_dir = Path(self.temp.name) / "run"
        self.run_dir.mkdir(mode=0o700)
        self.plan = {"task_count": 2, "tasks": [
            {"task_id": "case-0", "package_sha256": "a" * 64},
            {"task_id": "case-1", "package_sha256": "b" * 64}]}
        self.journal = self.run_dir / "journal.private.jsonl"

    def test_contiguous_completion_resumes_only_next_id(self):
        controller._event(self.journal, {"event": "case_started", "ordinal": 0,
            "task_id": "case-0", "package_sha256": "a" * 64,
            "attempt_dir": "attempt-000"})
        attempt = self.run_dir / "attempt-000"
        attempt.mkdir(mode=0o700)
        receipt = attempt / "attempt.private.json"
        write(receipt, {"schema": "raw-evidence"})
        controller._event(self.journal, {"event": "case_completed", "ordinal": 0,
            "task_id": "case-0", "package_sha256": "a" * 64,
            "attempt_dir": "attempt-000",
            "attempt_receipt_sha256": protocol.digest(receipt.read_bytes())})
        self.assertEqual(controller.next_case_index(self.run_dir, self.plan), 1)
        controller._event(self.journal, {"event": "case_started", "ordinal": 1,
            "task_id": "case-1", "package_sha256": "b" * 64,
            "attempt_dir": "attempt-001"})
        with self.assertRaisesRegex(controller.ScaleControlError,
                                    "scale_partial_case_requires_manual_reconciliation"):
            controller.next_case_index(self.run_dir, self.plan)

    def test_tampered_chain_and_failed_case_stop_without_replay(self):
        controller._event(self.journal, {"event": "case_started", "ordinal": 0,
            "task_id": "case-0", "package_sha256": "a" * 64,
            "attempt_dir": "attempt-000"})
        controller._event(self.journal, {"event": "case_failed", "ordinal": 0,
            "task_id": "case-0", "package_sha256": "a" * 64,
            "attempt_dir": "attempt-000"})
        with self.assertRaisesRegex(controller.ScaleControlError,
                                    "scale_failed_case_requires_manual_reconciliation"):
            controller.next_case_index(self.run_dir, self.plan)
        raw = self.journal.read_bytes().replace(b"case-0", b"case-x", 1)
        self.journal.write_bytes(raw)
        with self.assertRaisesRegex(controller.ScaleControlError,
                                    "scale_journal_hash_chain_changed"):
            controller.read_journal(self.journal)


class LeaseTimingTests(unittest.TestCase):
    def test_independent_case_audit_runs_only_after_release(self):
        events = []

        class FakeLease:
            @contextmanager
            def exclusive_worker_operation(self, operation):
                events.append("acquired")
                try:
                    yield
                finally:
                    events.append("released")

        row = {"task_id": "case-0", "package_sha256": "a" * 64}
        plan = {"tasks": [row]}
        with patch.object(controller, "_event", side_effect=lambda *_: events.append("started")), \
             patch.object(controller, "_case_evidence", side_effect=lambda **_: events.append("gui")), \
             patch.object(auditor, "audit_case", side_effect=lambda **_: events.append("independent_audit")):
            controller._execute_case_then_audit_after_release(
                lease=FakeLease(), run_dir=Path("/unused"), ordinal=0,
                row=row, case={}, wrong={}, family="purchase",
                modules=(), plan=plan, worker_private=Path("/unused"))
        self.assertEqual(events,
                         ["acquired", "started", "gui", "released", "independent_audit"])

    def test_reclassification_retains_failed_row_and_requires_live_baseline(self):
        with tempfile.TemporaryDirectory() as scratch:
            run_dir = Path(scratch) / "run"
            run_dir.mkdir(mode=0o700)
            plan = {"task_count": 1, "tasks": [{
                "task_id": "case-0", "package_sha256": "a" * 64}]}
            attempt = run_dir / "attempt-000"
            attempt.mkdir(mode=0o700)
            receipt = attempt / "attempt.private.json"
            write(receipt, {"schema": "raw-control"})
            args = {"ordinal": 0, "task_id": "case-0",
                    "package_sha256": "a" * 64,
                    "attempt_dir": "attempt-000"}
            controller._event(run_dir / "journal.private.jsonl",
                              {"event": "case_started", **args})
            controller._event(run_dir / "journal.private.jsonl",
                              {"event": "case_failed", **args})
            with self.assertRaisesRegex(controller.ScaleControlError,
                                        "scale_failed_case_requires_manual_reconciliation"):
                controller.next_case_index(run_dir, plan)
            baseline_path = run_dir / "current-baseline-check.private.json"
            sql_path = run_dir / "current-baseline-sql.private.json"
            files_path = run_dir / "current-baseline-filestore.private.json"
            write(sql_path, {"saved_sql": []})
            write(files_path, {"saved_filestore": []})
            baseline = {"schema": "envloop-odoo-v066-current-baseline-check-v1",
                        "status": "current_sql_and_full_filestore_equal_frozen_baseline",
                        "sql_snapshot_sha256": protocol.digest(sql_path.read_bytes()),
                        "filestore_manifest_sha256": protocol.digest(files_path.read_bytes()),
                        "original_service_state_restored": True,
                        "current_baseline_checked_after_old_lease_release": True,
                        "official_final_tasks_admitted": 0}
            write(baseline_path, baseline)
            authority_path = run_dir / "reclassification.private.json"
            authority = {"schema": "envloop-odoo-v066-manual-lease-reclassification-v1",
                         "status": "approved_after_current_live_baseline_and_post_lease_audit",
                         "ordinal": 0, "task_id": "case-0",
                         "package_sha256": "a" * 64,
                         "new_private_plan_sha256": protocol.digest(protocol.canonical(plan)),
                         "old_attempt_sha256": protocol.digest(receipt.read_bytes()),
                         "current_baseline_check_sha256": protocol.digest(
                             baseline_path.read_bytes())}
            write(authority_path, authority)
            controller._event(run_dir / "journal.private.jsonl", {
                "event": "case_reclassified_after_lease_release", **args,
                "authority_sha256": protocol.digest(authority_path.read_bytes()),
                "attempt_receipt_sha256": authority["old_attempt_sha256"]})
            self.assertEqual(controller.next_case_index(run_dir, plan), 1)
            baseline["status"] = "not_equal"
            write(baseline_path, baseline)
            with self.assertRaisesRegex(controller.ScaleControlError,
                                        "scale_reclassification_current_baseline_missing"):
                controller.next_case_index(run_dir, plan)


class HoldoutActionTests(unittest.TestCase):
    def test_train_exact_return_cannot_replay_without_source_transition(self):
        from unittest.mock import patch
        with patch.object(controller, "_preflight", return_value=(
                {"frame_guard_amendment": protocol.EXACT_RETURN_AMENDMENT},
                Path("/unused/private"))), patch.object(
                    controller, "_modules", side_effect=AssertionError(
                        "modules must not load")):
            with self.assertRaisesRegex(
                    controller.ScaleControlError,
                    "scale_train_requires_separate_source_transition"):
                controller.run(
                    split="train", worker_dir=Path("/unused/train"),
                    private_plan_path=Path("/unused/plan"),
                    public_plan_path=Path("/unused/public"),
                    source_freeze_path=Path("/unused/freeze"),
                    run_dir=Path("/unused/run"), resume=False, max_cases=1)

    def test_current_frame_actions_never_create_sft_candidate(self):
        with tempfile.TemporaryDirectory() as scratch:
            out = Path(scratch) / "attempt"
            out.mkdir(mode=0o700)
            adapter = FakeAdapter(out)
            journal = controller.HoldoutJournal(adapter, FakePage(), out)
            journal.act("wait", phase="positive", duration_ms=50)
            journal.act("wait", phase="negative", duration_ms=50)
            trace = {"schema": controller.TRACE_SCHEMA,
                     "task_binding_sha256": "b" * 64,
                     "actions": journal.trace,
                     "pre_intent_rejections": journal.pre_intent_rejections,
                     "sft_examples_written": 0}
            row = {"task_id": "TRAIN-ONLY-1", "package_sha256": "a" * 64,
                   "task_binding_sha256": "b" * 64}
            self.assertEqual(auditor._action_chain(out, trace, row), (1, 1, 0))
            self.assertEqual(journal.sft, [])
            self.assertFalse((out / "sft_candidate.private.json").exists())


class IndependentSavedStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.private = self.root / "train" / "private"
        self.private.mkdir(parents=True, mode=0o700)
        self.attempt = self.private / "controls" / "attempt-000"
        self.attempt.mkdir(parents=True, mode=0o700)
        task_id = "TRAIN-ONLY-1"
        self.row = {"task_id": task_id, "package_sha256": "a" * 64,
                    "task_binding_sha256": "b" * 64,
                    "family": "inventory", "split": "train",
                    "source_asset_sha256": protocol.digest(b"Synthetic note"),
                    "source_label": "Purchase planning note for SKU-1"}
        checksum = lambda i: hashlib.sha1(str(i).encode()).hexdigest()
        attachments = [{"id": i, "checksum": checksum(i)} for i in range(1, 17)]
        frozen = {f"filestore/bench/{item['checksum'][:2]}/{item['checksum']}":
                  protocol.digest(str(item["id"]).encode()) for item in attachments}
        store_paths = {str(item["id"]):
                       f"{item['checksum'][:2]}/{item['checksum']}"
                       for item in attachments}
        rule = {"id": 1, "product_id": 1, "location_id": 1,
                "warehouse_id": 1, "company_id": 1,
                "minimum": "10", "maximum": "20", "multiple": "1",
                "trigger": "manual"}
        other = {**rule, "id": 2, "product_id": 2,
                 "minimum": "5", "maximum": "9"}
        baseline = {"global_business_identity": {},
                    **{name: [] for name in (
                        "orders", "lines", "vendors", "products", "sales_orders",
                        "sales_lines", "crm_leads", "customers", "salespeople",
                        "crm_stages")},
                    "attachments": attachments, "orderpoints": [rule, other]}
        positive = deepcopy(baseline)
        positive["orderpoints"][0]["minimum"] = "12"
        positive["orderpoints"][0]["maximum"] = "24"
        negative = deepcopy(positive)
        negative["orderpoints"][1]["minimum"] = "6"
        db, fs = b"db-checkpoint", b"fs-checkpoint"
        write(self.private / "baseline.pgcustom", db)
        write(self.private / "baseline-filestore.tgz", fs)
        write(self.private / "baseline_snapshot.json", baseline)
        write(self.private / "baseline-filestore-manifest.json", frozen)
        write(self.private / "partition_cases.json", {"split": "train",
            "cases": {"inventory": [{"id": task_id, "family": "inventory",
                                      "sku": "SKU-1", "source_note": "Synthetic note"}],
                      "purchase": [], "sales": [], "crm": []}})
        write(self.private / "replenishment_gold.json", {task_id: {
            "rule_id": 1, "expected": {"minimum": 12, "maximum": 24}}})
        self.plan = {"split": "train", "checkpoint": {
            "db_sha256": protocol.digest(db),
            "filestore_sha256": protocol.digest(fs),
            "baseline_snapshot_sha256": protocol.digest(
                (self.private / "baseline_snapshot.json").read_bytes()),
            "baseline_filestore_manifest_sha256": protocol.digest(
                (self.private / "baseline-filestore-manifest.json").read_bytes())},
            "source_freeze_sha256": "c" * 64}
        adapter = FakeAdapter(self.attempt)
        journal = controller.HoldoutJournal(adapter, FakePage(), self.attempt)
        source_frame = journal.act("wait", phase="positive", duration_ms=50)
        journal.act("wait", phase="negative", duration_ms=50)
        refs = {}
        def artifact(name, value):
            path = self.attempt / f"{name}.json"
            write(path, value)
            refs[name] = {"path": path.name,
                          "sha256": protocol.digest(path.read_bytes())}
        restore = {"status": "restored", "business_snapshot_equal": True,
                   "physical_filestore_equal_before_web_restart": True,
                   "db_sha256": self.plan["checkpoint"]["db_sha256"],
                   "filestore_sha256": self.plan["checkpoint"]["filestore_sha256"]}
        values = {"pre_restore": restore, "post_restore": restore,
                  "baseline_sql": baseline, "positive_sql": positive,
                  "negative_sql": negative, "restored_sql": baseline,
                  "positive_filestore": frozen, "negative_filestore": frozen,
                  "restored_filestore": frozen,
                  "positive_store_paths": store_paths,
                  "negative_store_paths": store_paths,
                  "source_evidence": {
                      "schema": "envloop-odoo-v066-native-source-presentation-v1",
                      "task_id": task_id,
                      "source_asset_sha256": self.row["source_asset_sha256"],
                      "source_label": self.row["source_label"],
                      "source_frame_sha256": source_frame["sha256"],
                      "source_opened_via_v066_gui_actions": True},
                  "gui_trace": {"schema": controller.TRACE_SCHEMA,
                                "task_binding_sha256": self.row["task_binding_sha256"],
                                "actions": journal.trace,
                                "pre_intent_rejections": [],
                                "sft_examples_written": 0}}
        for name, value in values.items(): artifact(name, value)
        refs["source_frame"] = source_frame
        for name, color in (("positive_reload_frame", (2,3,4)),
                            ("negative_reload_frame", (5,6,7))):
            path = self.attempt / f"{name}.png"
            write(path, png(color))
            refs[name] = {"path": path.name,
                          "sha256": protocol.digest(path.read_bytes())}
        start = datetime(2026, 9, 28, tzinfo=timezone.utc)
        stamps = {key: (start + timedelta(seconds=i+1)).isoformat()
                  for i, key in enumerate(controller.STAGES)}
        events = [{"event": "acquired", "operation": controller.LEASE_OPERATION,
                   "pid": 123, "at_utc": (start-timedelta(seconds=1)).isoformat()},
                  {"event": "released", "operation": controller.LEASE_OPERATION,
                   "pid": 123, "at_utc": (start+timedelta(seconds=9)).isoformat()}]
        write(self.private / "worker-lease-events.jsonl",
              ("\n".join(json.dumps(event) for event in events)+"\n").encode())
        self.receipt = {"schema": protocol.CASE_SCHEMA,
            "status": controller.CASE_STATUS, "split": "train",
            "family": "inventory", "task_id": task_id,
            "package_sha256": self.row["package_sha256"],
            "task_binding_sha256": self.row["task_binding_sha256"],
            "source_freeze_sha256": self.plan["source_freeze_sha256"],
            "plan_sha256": protocol.digest(protocol.canonical(self.plan)),
            "ratification_sha256": protocol.RATIFICATION_SHA,
            "worker_pid": 123,
            "started_at_utc": start.isoformat(),
            "finished_at_utc": (start+timedelta(seconds=8)).isoformat(),
            "lease_operation": controller.LEASE_OPERATION,
            "stage_timestamps": stamps, "refs": refs,
            "service_state_restored_receipt": True,
            "official_final_tasks_admitted": 0, "model_attempts": 0}
        write(self.attempt / "attempt.private.json", self.receipt)

    def test_raw_sql_positive_negative_and_reset_derive_independently(self):
        result = auditor.audit_case(plan=self.plan, row=self.row,
                                    attempt=self.attempt,
                                    worker_private=self.private)
        self.assertEqual(result["independent_positive_reward"], 1.0)
        self.assertEqual(result["independent_wrong_object_reward"], 0.0)
        self.assertEqual(result["positive_gui_actions"], 1)
        self.assertEqual(result["negative_gui_actions"], 1)
        self.assertTrue(result["source_visual_review_pending"])
        self.assertEqual(result["official_final_tasks_admitted"], 0)

    def test_changed_negative_state_rejected_even_when_reference_rehashed(self):
        path = self.attempt / "negative_sql.json"
        positive = json.loads((self.attempt / "positive_sql.json").read_bytes())
        write(path, positive)
        self.receipt["refs"]["negative_sql"]["sha256"] = protocol.digest(path.read_bytes())
        write(self.attempt / "attempt.private.json", self.receipt)
        with self.assertRaisesRegex(auditor.ScaleAuditError,
                                    "scale_case_independent_saved_state_or_negative_invalid"):
            auditor.audit_case(plan=self.plan, row=self.row,
                               attempt=self.attempt, worker_private=self.private)


    def test_resampled_pre_intent_frames_are_audited_without_replay(self):
        with tempfile.TemporaryDirectory() as scratch:
            out = Path(scratch) / "attempt"
            out.mkdir(mode=0o700)
            adapter = FakeAdapter(out, stale_before_intent=2)
            journal = controller.HoldoutJournal(adapter, FakePage(), out)
            journal.act("wait", phase="positive", duration_ms=50)
            journal.act("wait", phase="negative", duration_ms=50)
            trace = {"schema": controller.TRACE_SCHEMA,
                     "task_binding_sha256": "b" * 64,
                     "actions": journal.trace,
                     "pre_intent_rejections": journal.pre_intent_rejections,
                     "sft_examples_written": 0}
            row = {"task_id": "TRAIN-ONLY-1", "package_sha256": "a" * 64,
                   "task_binding_sha256": "b" * 64}
            self.assertEqual(auditor._action_chain(out, trace, row), (1, 1, 2))
            self.assertEqual(adapter.dispatch_calls, 2)
            self.assertEqual(len(journal.pre_intent_rejections), 2)


class ReclassifiedBaselineTests(unittest.TestCase):
    def test_saved_current_baseline_must_equal_frozen_bytes_on_resume(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            run_dir = root / "run"
            private = root / "worker-private"
            run_dir.mkdir(mode=0o700)
            private.mkdir(mode=0o700)
            write(run_dir / "current-baseline-sql.private.json", {"rows": [1]})
            write(run_dir / "current-baseline-filestore.private.json", {"file": "a"})
            write(private / "baseline_snapshot.json", {"rows": [1]})
            write(private / "baseline-filestore-manifest.json", {"file": "a"})
            controller.verify_reclassified_current_baseline(run_dir, private)
            write(run_dir / "current-baseline-filestore.private.json", {"file": "b"})
            with self.assertRaisesRegex(controller.ScaleControlError,
                                        "scale_reclassified_current_baseline_artifacts_changed"):
                controller.verify_reclassified_current_baseline(run_dir, private)


class LiveDispatchGuardTests(unittest.TestCase):
    def test_cli_refuses_without_execute_before_docker_or_private_lookup(self):
        command = [sys.executable,
                   str(Path(__file__).resolve().parents[1] /
                       "tools/odoo_v066_scale_controller_v1.py"),
                   "run", "--split", "selection", "--worker-dir", "/missing",
                   "--private-plan", "/missing/plan", "--public-plan", "/missing/public",
                   "--source-freeze", "/missing/freeze", "--run-dir", "/missing/run"]
        completed = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(json.loads(completed.stdout)["status"],
                         "refused_without_explicit_execute")
        self.assertNotIn("/missing", completed.stdout)


    def test_reconcile_cli_refuses_without_explicit_live_baseline_check(self):
        command = [sys.executable,
                   str(Path(__file__).resolve().parents[1] /
                       "tools/odoo_v066_scale_controller_v1.py"),
                   "reconcile", "--worker-dir", "/missing/train",
                   "--run-dir", "/missing/run",
                   "--old-private-plan", "/missing/old",
                   "--old-source-freeze", "/missing/old-freeze",
                   "--new-private-plan", "/missing/new",
                   "--new-public-plan", "/missing/new-public",
                   "--new-source-freeze", "/missing/new-freeze",
                   "--incident-public", "/missing/incident",
                   "--adoption-private", "/missing/adoption"]
        completed = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(json.loads(completed.stdout)["status"],
                         "refused_without_explicit_execute")
        self.assertNotIn("/missing", completed.stdout)


class RecipeMetadataTests(unittest.TestCase):
    def test_purchase_and_inventory_positive_cover_expected_fields(self):
        page = MagicMock()
        page.locator.return_value.input_value.return_value = "private-ref"
        journal = object()
        purchase = {"lines": [
            {"sku": "a", "initial": {"qty": 1, "price": 2},
             "expected": {"qty": 1, "price": 3}},
            {"sku": "b", "initial": {"qty": 4, "price": 5},
             "expected": {"qty": 6, "price": 7}}],
            "vendor_reference": "private-ref"}
        with patch.object(recipes, "_grid_edit") as edit, patch.object(
                recipes, "_fill") as fill, patch.object(
                recipes, "_act") as act, patch.object(
                recipes, "_save"):
            recipes.apply_positive(page, journal, "purchase", purchase, 8078)
            self.assertEqual(edit.call_count, 3)
            self.assertEqual([call.kwargs["cell"] for call in edit.call_args_list],
                             ["price_unit", "product_qty", "price_unit"])
            self.assertEqual(fill.call_count, 1)
            self.assertTrue(act.called)
        inventory = {"sku": "SKU", "expected": {"minimum": 11, "maximum": 29}}
        with patch.object(recipes, "_open_inventory_rule"), patch.object(
                recipes, "_grid_edit") as edit:
            recipes.apply_positive(page, journal, "inventory", inventory, 8078)
            self.assertEqual([call.kwargs["cell"] for call in edit.call_args_list],
                             ["product_min_qty", "product_max_qty"])

    def test_sales_and_crm_hidden_fields_and_wrong_object_controls(self):
        page = MagicMock()
        journal = object()
        sales = {"customer_reference": "private-reference",
                 "expiration_date": "2027-01-15",
                 "lines": [
                     {"sku": "a", "initial": {"qty": 3, "price": 4},
                      "expected": {"qty": 5, "price": 4}},
                     {"sku": "b", "initial": {"qty": 6, "price": 7},
                      "expected": {"qty": 6, "price": 9}}]}
        with patch.object(recipes, "_grid_edit") as edit, patch.object(
                recipes, "_fill") as fill, patch.object(
                recipes, "_act"), patch.object(recipes, "_save"):
            recipes.apply_positive(page, journal, "sales", sales, 8078)
            self.assertEqual(fill.call_count, 2)
            self.assertEqual([call.kwargs["cell"] for call in edit.call_args_list],
                             ["product_uom_qty", "price_unit", "price_unit"])
        crm = {"salesperson_names": ["Avery Lane", "Morgan Ellis", "Riley Chen"],
               "initial": {"stage_name": "New", "salesperson_index": 0,
                           "revenue": 1.0, "deadline": "2026-01-01",
                           "priority": "1"},
               "expected": {"stage_name": "Qualified", "salesperson_index": 1,
                            "revenue": 20000.0, "deadline": "2026-02-02",
                            "priority": "2", "email_from": "synthetic@example.invalid",
                            "phone": "+1 555 0100"}}
        with patch.object(recipes, "_fill") as fill, patch.object(
                recipes, "_act") as act, patch.object(recipes, "_save"):
            recipes.apply_positive(page, journal, "crm", crm, 8078)
            self.assertEqual(fill.call_count, 5)
            self.assertTrue(act.called)
        wrong = {"initial": {"priority": "1"}}
        with patch.object(recipes, "open_case") as opened, patch.object(
                recipes, "_act") as act, patch.object(recipes, "_save"):
            recipes.apply_negative(page, journal, "crm", wrong, 8078)
            self.assertTrue(opened.called)
            self.assertTrue(act.called)


if __name__ == "__main__":
    unittest.main()
