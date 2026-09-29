"""Battery-power provenance with unchanged Odoo SQL/filestore and no-replay gates."""

from __future__ import annotations

from contextlib import ExitStack, contextmanager, nullcontext
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import audit_odoo_v066_current_candidate_no_gui_gate_v2 as gate_audit
from tools import audit_odoo_v066_battery_authorized_batch_v2 as batch_audit
from tools import odoo_v066_current_candidate_no_gui_gate_v2 as gate
from tools import odoo_v066_current_candidate_one_selection_v2 as runner
from tools import odoo_v066_battery_authorized_power_v2 as power
from tools import odoo_v066_scale_protocol_v1 as protocol


def sample(second: int, source: str = "Battery Power") -> dict:
    raw = (f"Now drawing from '{source}'\n"
           " -InternalBattery-0 (id=12345) 6%; discharging; 0:20 remaining\n")
    return {
        "schema": power.POWER_SCHEMA,
        "captured_at_utc": f"2026-09-29T00:00:{second:02d}+00:00",
        "source": source,
        "battery_percent": 6,
        "raw_pmset_stdout": raw,
        "raw_pmset_stdout_sha256": sha256(raw.encode()).hexdigest(),
        "battery_operation_authorized_by_user_on": "2026-09-29",
    }


class PowerTests(unittest.TestCase):
    def test_battery_valid_and_tamper_rejected(self):
        self.assertEqual(power.validate(sample(0)).second, 0)
        changed = dict(sample(0))
        changed["battery_percent"] = 7
        with self.assertRaisesRegex(power.PowerSampleError, "parse_or_digest"):
            power.validate(changed)
        with self.assertRaisesRegex(power.PowerSampleError, "source_or_level"):
            power.parse("Now drawing from 'Unknown Power'\n")


class GateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.worker = self.root / "selection"
        self.private = self.worker / "private"
        self.epoch = self.private / "v066_current_candidate_epoch"
        self.epoch.mkdir(parents=True, mode=0o700)
        self.private.chmod(0o700)
        self.plan = self.epoch / "plan.private.json"
        self.public = self.root / "public.json"
        self.old_private = self.root / "old.private.json"
        self.old_public = self.root / "old.public.json"
        for path in (self.public, self.old_private, self.old_public):
            path.write_text("{}\n")
        self.failures = {k: k[0] * 64 for k in ("first", "second", "third")}
        protocol.write_new(self.plan, {
            "run_nonce_hex": "a" * 32,
            "fresh_run_directory_name": "current-candidate-" + "a" * 32,
            "current_candidate_private_sha256": "b" * 64,
            "source_freeze_sha256": "c" * 64,
            "retained_terminal_failure_public_sha256s": self.failures,
        }, private=True)
        self.sql = {"baseline": 1}
        self.files = {"filestore/one": "a" * 64,
                      "filestore/two": "b" * 64}
        protocol.write_new(self.private / "baseline_snapshot.json",
                           self.sql, private=True)
        protocol.write_new(self.private / "baseline-filestore-manifest.json",
                           self.files, private=True)
        events = [
            {"event": "acquired", "operation": gate.GATE_OPERATION,
             "pid": 123, "at_utc": "2026-09-29T00:00:00+00:00"},
            {"event": "released", "operation": gate.GATE_OPERATION,
             "pid": 123, "at_utc": "2026-09-29T00:00:01+00:00"},
        ]
        self.events = self.private / "worker-lease-events.jsonl"
        self.events.write_bytes(("\n".join(json.dumps(e) for e in events) + "\n").encode())
        self.events.chmod(0o600)

    def contexts(self):
        return (
            patch.object(gate.amendment, "validate", return_value={}),
            patch.object(gate.power, "capture", side_effect=[sample(0), sample(1)]),
            patch.object(gate.plan_audit, "audit", return_value={}),
            patch.object(gate.protocol, "_worker_split", return_value=self.private),
            patch.object(gate, "_reaudit_failures", return_value=self.failures),
            patch.object(gate, "_collect_live_baseline", return_value=(
                self.sql, self.files, sha256(self.events.read_bytes()).hexdigest(),
                self.events.stat().st_size, True)),
            patch.dict(os.environ, {"ENVLOOP_ODOO_WORKER_DIR":
                                    str(self.worker.resolve())}),
        )

    def call(self):
        return gate.prepare(
            worker_dir=self.worker, historical_root=self.root,
            private_plan=self.plan, public_plan=self.public,
            old_private_plan=self.old_private,
            old_public_plan=self.old_public, execute_baseline_check=True)

    def test_battery_gate_exact_baseline_and_independent_power_audit(self):
        with ExitStack() as stack:
            for context in self.contexts():
                stack.enter_context(context)
            self.assertEqual(self.call()["status"], gate.GATE_STATUS)
            audited = gate_audit.audit(
                worker_dir=self.worker, historical_root=self.root,
                private_plan=self.plan, public_plan=self.public,
                old_private_plan=self.old_private,
                old_public_plan=self.old_public)
            self.assertEqual(audited["host_power_entry_source"], "Battery Power")
            receipt_path = self.epoch / gate.GATE_FILE
            receipt = protocol.private_json(receipt_path)
            receipt["host_power_exit"]["battery_percent"] = 7
            receipt_path.write_bytes(protocol.canonical(receipt))
            with self.assertRaisesRegex(power.PowerSampleError, "parse_or_digest"):
                gate_audit.audit(
                    worker_dir=self.worker, historical_root=self.root,
                    private_plan=self.plan, public_plan=self.public,
                    old_private_plan=self.old_private,
                    old_public_plan=self.old_public)

    def test_sql_or_filestore_mismatch_still_refuses_receipt(self):
        with ExitStack() as stack:
            for context in self.contexts():
                stack.enter_context(context)
            with patch.object(gate, "_collect_live_baseline", return_value=(
                self.sql, {"wrong": "value"},
                sha256(self.events.read_bytes()).hexdigest(),
                self.events.stat().st_size, True)):
                with self.assertRaisesRegex(gate.NoGuiGateError,
                                            "current_sql_or_full_filestore_not_exact"):
                    self.call()
        self.assertFalse((self.epoch / gate.GATE_FILE).exists())


class FakeLease:
    @contextmanager
    def exclusive_worker_operation(self, _operation):
        yield


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.worker = self.root / "selection"
        self.private = self.worker / "private"
        (self.private / "v066_scale_controls").mkdir(parents=True, mode=0o700)
        self.private.chmod(0o700)
        self.plan_path = self.root / "plan.private.json"
        self.public = self.root / "public.json"
        self.old_private = self.root / "old.private.json"
        self.old_public = self.root / "old.public.json"
        self.freeze = self.root / "source-freeze.json"
        for path in (self.public, self.old_private, self.old_public, self.freeze):
            path.write_text("{}\n")
        self.plan = {
            "split": "selection",
            "fresh_run_directory_name": "current-candidate-" + "a" * 32,
            "run_nonce_hex": "a" * 32,
            "source_freeze_sha256": "b" * 64,
            "physical_dispatch_profile": protocol.PINNED_BORDER_PROFILE,
            "current_candidate_private_sha256": "c" * 64,
            "historical_ratification_sha256": protocol.RATIFICATION_SHA,
            "tasks": [{"task_id": "FAKE-1", "family": "inventory",
                       "package_sha256": "d" * 64,
                       "task_binding_sha256": "e" * 64,
                       "source_asset_sha256": "f" * 64,
                       "split": "selection"}],
        }
        protocol.write_new(self.plan_path, self.plan, private=True)
        protocol.write_new(self.private / "partition_cases.json", {
            "cases": {"inventory": [{"id": "FAKE-1"}, {"id": "FAKE-2"}]}
        }, private=True)

    def contexts(self):
        return (
            patch.object(runner.source, "validate", return_value={}),
            patch.object(runner.source, "FREEZE", self.freeze),
            patch.object(runner.power, "capture", side_effect=[
                sample(0), sample(1), sample(2)]),
            patch.object(runner.plan_audit, "audit", return_value={}),
            patch.object(runner.gate_audit, "audit", return_value={
                "status": "no_gui_current_sql_full_filestore_gate_independently_verified",
                "gate_sha256": "9" * 64}),
            patch.object(runner.protocol, "_worker_split", return_value=self.private),
            patch.object(runner.controller, "_run_lock", return_value=nullcontext()),
            patch.object(runner.controller, "_modules", return_value=(
                object(), object(), object(), object(), FakeLease())),
            patch.dict(os.environ, {"ENVLOOP_ODOO_WORKER_DIR":
                                    str(self.worker.resolve())}),
        )

    def test_pre_dispatch_failure_retains_terminal_power_and_no_replay(self):
        with ExitStack() as stack:
            for context in self.contexts():
                stack.enter_context(context)
            with patch.object(runner.power, "capture", side_effect=[
                sample(0), power.PowerSampleError("pmset_unavailable"),
                sample(2)]):
                with self.assertRaisesRegex(runner.CurrentControlError,
                                            "preserve_original_no_automatic_replay"):
                    runner.run_one(
                        worker_dir=self.worker, historical_root=self.root,
                        private_plan=self.plan_path, public_plan=self.public,
                        old_private_plan=self.old_private,
                        old_public_plan=self.old_public, execute=True)
        run = self.private / "v066_scale_controls" / self.plan["fresh_run_directory_name"]
        failure = protocol.private_json(run / "pre-dispatch-failure.private.json")
        self.assertEqual(failure["status"], "terminal_before_case_started_no_replay")
        self.assertEqual(failure["host_power_end"]["battery_percent"], 6)
        self.assertFalse((run / "attempt-000").exists())

    def test_battery_one_case_has_three_ordered_power_samples(self):
        def execute(**kwargs):
            attempt = kwargs["run_dir"] / "attempt-000"
            attempt.mkdir(mode=0o700)
            protocol.write_new(attempt / "attempt.private.json",
                               {"schema": "fake"}, private=True)

        def case_audit(**_kwargs):
            return {
                "status": "current_candidate_raw_gui_semantics_verified_source_visual_review_pending",
                "independent_baseline_reward": 0.0,
                "independent_positive_reward": 1.0,
                "independent_wrong_object_reward": 0.0,
                "full_pre_web_filestore_reset_exact": True,
                "protected_post_web_source_bytes_equal": True,
                "source_visual_review_pending": True,
                "official_final_tasks_admitted": 0,
            }

        def fake_batch_audit(**_kwargs):
            return {
                "status": "one_raw_selection_control_independently_verified_visual_review_pending",
                "independently_verified_raw_selection_controls": 1,
                "official_final_tasks_admitted": 0,
            }

        with ExitStack() as stack:
            for context in self.contexts():
                stack.enter_context(context)
            result = runner.run_one(
                worker_dir=self.worker, historical_root=self.root,
                private_plan=self.plan_path, public_plan=self.public,
                old_private_plan=self.old_private, old_public_plan=self.old_public,
                execute=True, case_executor=execute, case_auditor=case_audit,
                batch_auditor=fake_batch_audit)
        self.assertEqual(result["independently_audited_raw_cases"], 1)
        run = self.private / "v066_scale_controls" / self.plan["fresh_run_directory_name"]
        intent = protocol.private_json(run / "batch-intent.private.json")
        self.assertEqual(intent["host_power_pre_intent"]["source"], "Battery Power")
        events = [json.loads(line) for line in
                  (run / "journal.private.jsonl").read_text().splitlines()]
        self.assertEqual(events[0]["host_power_pre_dispatch"]["battery_percent"], 6)
        self.assertEqual(events[-1]["host_power_end"]["battery_percent"], 6)
        with patch.object(batch_audit.source, "validate", return_value={}), \
                patch.object(batch_audit.source, "FREEZE", self.freeze), \
                patch.object(batch_audit.protocol, "_worker_split",
                             return_value=self.private), \
                patch.object(batch_audit.gate_audit, "audit", return_value={
                    "gate_sha256": "9" * 64}), \
                patch.object(batch_audit, "audit_current_case", return_value={
                    "independent_baseline_reward": 0.0,
                    "independent_positive_reward": 1.0,
                    "independent_wrong_object_reward": 0.0,
                    "full_pre_web_filestore_reset_exact": True,
                    "source_visual_review_pending": True}):
            audited = batch_audit.audit_one_batch(
                worker_dir=self.worker, historical_root=self.root,
                private_plan=self.plan_path, public_plan=self.public,
                old_private_plan=self.old_private, old_public_plan=self.old_public)
            self.assertEqual(audited["host_power_end_source"], "Battery Power")
            intent["host_power_pre_intent"]["battery_percent"] = 7
            (run / "batch-intent.private.json").write_bytes(
                protocol.canonical(intent))
            with self.assertRaisesRegex(power.PowerSampleError,
                                        "parse_or_digest"):
                batch_audit.audit_one_batch(
                    worker_dir=self.worker, historical_root=self.root,
                    private_plan=self.plan_path, public_plan=self.public,
                    old_private_plan=self.old_private,
                    old_public_plan=self.old_public)
        with ExitStack() as stack:
            for context in self.contexts():
                stack.enter_context(context)
            with self.assertRaisesRegex(runner.CurrentControlError,
                                        "fresh_run_already_exists"):
                runner.run_one(
                    worker_dir=self.worker, historical_root=self.root,
                    private_plan=self.plan_path, public_plan=self.public,
                    old_private_plan=self.old_private,
                    old_public_plan=self.old_public, execute=True)


if __name__ == "__main__":
    unittest.main()
