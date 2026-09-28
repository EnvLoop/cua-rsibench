"""No-Docker tests for the fourth-attempt cold-baseline authority."""

from __future__ import annotations

from contextlib import nullcontext
from hashlib import sha256
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import odoo_v066_scale_audit_v1 as independent
from tools import odoo_v066_scale_controller_v1 as controller
from tools import odoo_v066_scale_protocol_v1 as protocol


def save(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_bytes(protocol.canonical(value))
    path.chmod(0o600)


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


class ValidatorRetryGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.worker = self.root / "selection"
        self.private = self.worker / "private"
        self.controls = self.private / "v066_scale_controls"
        self.old = self.controls / "controls-20260929-pinned-border-01"
        self.attempt = self.old / "attempt-000"
        self.attempt.mkdir(parents=True, mode=0o700)
        for path in (self.worker, self.private, self.controls,
                     self.old, self.attempt):
            path.chmod(0o700)
        self.new_plan = self.root / "new-plan.private.json"
        self.new_freeze = self.root / "new-freeze.json"
        self.incident_path = self.root / "third-incident.json"
        save(self.new_plan, {"split": "selection"})
        save(self.new_freeze, {"status": "new"})
        save(self.old / "batch-intent.private.json", {"old": True})
        save(self.attempt / "failure.private.json", {"error": "invalid_action"})
        save(self.attempt / "gui_trace.json", {"actions": [1]})
        save(self.attempt / "actions/step-008-intent.private.json",
             {"step": 8})
        case = {"ordinal": 0, "task_id": "case-1",
                "package_sha256": "a" * 64,
                "attempt_dir": "attempt-000",
                "run_intent_sha256": digest(
                    self.old / "batch-intent.private.json")}
        controller._event(self.old / "journal.private.jsonl",
                          {"event": "case_started", **case})
        tail = controller._event(self.old / "journal.private.jsonl",
                                 {"event": "case_failed", **case})
        save(self.incident_path, {
            "status":
                "post_intent_pre_dispatch_base_validator_rejected_v066_double_click",
            "step_eight_mouse_action_dispatched": False,
            "all_three_failed_attempts_preserved": True,
            "batch_intent_sha256": digest(
                self.old / "batch-intent.private.json"),
            "journal_sha256": digest(self.old / "journal.private.jsonl"),
            "journal_tail_sha256": tail,
            "private_failure_sha256": digest(
                self.attempt / "failure.private.json"),
            "private_gui_trace_sha256": digest(
                self.attempt / "gui_trace.json"),
            "private_step_eight_intent_sha256": digest(
                self.attempt / "actions/step-008-intent.private.json"),
        })
        save(self.private / "baseline_snapshot.json", {"rows": [1]})
        save(self.private / "baseline-filestore-manifest.json",
             {"files": ["x"]})
        self.sql = self.controls / "selection-v066-validator-current-sql.private.json"
        self.files = self.controls / \
            "selection-v066-validator-current-filestore.private.json"
        save(self.sql, {"rows": [1]})
        save(self.files, {"files": ["x"]})
        events = self.private / "worker-lease-events.jsonl"
        events.write_bytes(b'{"event":"released"}\n')
        events.chmod(0o600)
        self.gate = self.controls / \
            "selection-v066-validator-retry-gate.private.json"
        save(self.gate, {
            "schema": controller.VALIDATOR_RETRY_GATE_SCHEMA,
            "status":
                "three_failed_attempts_retained_current_baseline_exact_no_gui_replay",
            "validator_amendment": protocol.VALIDATOR_V066_AMENDMENT,
            "new_private_plan_sha256": digest(self.new_plan),
            "new_source_freeze_sha256": digest(self.new_freeze),
            "third_failure_public_sha256": digest(self.incident_path),
            "old_batch_intent_sha256": digest(
                self.old / "batch-intent.private.json"),
            "old_journal_sha256": digest(self.old / "journal.private.jsonl"),
            "old_journal_tail_sha256": tail,
            "old_failure_sha256": digest(
                self.attempt / "failure.private.json"),
            "old_gui_trace_sha256": digest(
                self.attempt / "gui_trace.json"),
            "old_step_eight_intent_sha256": digest(
                self.attempt / "actions/step-008-intent.private.json"),
            "old_step_eight_result_exists": False,
            "prior_failed_control_count": 3,
            "current_sql_sha256": digest(self.sql),
            "current_filestore_sha256": digest(self.files),
            "worker_lease_events_sha256": digest(events),
            "service_state_restored": True,
            "official_final_tasks_admitted": 0,
            "model_attempts": 0,
        })
        self.plan = {
            "validator_amendment": protocol.VALIDATOR_V066_AMENDMENT,
            "frame_guard_amendment": protocol.EXACT_RETURN_AMENDMENT,
            "physical_dispatch_profile": protocol.PINNED_BORDER_PROFILE,
            "tasks": [{"task_id": "case-1",
                       "package_sha256": "a" * 64}],
        }

    def check(self):
        return controller._validator_retry_gate(
            gate_path=self.gate, worker=self.worker, plan=self.plan,
            private_plan_path=self.new_plan,
            source_freeze_path=self.new_freeze,
            old_run_dir=self.old, incident_public_path=self.incident_path,
            require_unchanged_lease_log=True)

    def test_gate_binds_third_failure_and_current_baseline(self):
        self.assertEqual(self.check()["prior_failed_control_count"], 3)
        save(self.attempt / "actions/step-008-result.private.json", {})
        with self.assertRaisesRegex(
                controller.ScaleControlError,
                "scale_validator_retry_prior_failure_or_authority_changed"):
            self.check()

    def test_gate_rejects_changed_current_filestore_and_worker_log(self):
        save(self.files, {"files": ["unexpected"]})
        with self.assertRaisesRegex(
                controller.ScaleControlError,
                "scale_validator_retry_current_baseline_not_exact"):
            self.check()
        save(self.files, {"files": ["x"]})
        with (self.private / "worker-lease-events.jsonl").open("ab") as stream:
            stream.write(b'{"event":"acquired"}\n')
        with self.assertRaisesRegex(
                controller.ScaleControlError,
                "scale_validator_retry_gate_stale_worker_activity"):
            self.check()

    def test_independent_gate_binds_batch_and_prior_receipts(self):
        batch = {"selection_retry_gate_sha256": digest(self.gate)}
        independent._validator_retry_gate_independent(
            worker_private=self.private, plan=self.plan,
            batch_intent=batch, private_plan_path=self.new_plan,
            source_freeze_path=self.new_freeze,
            incident_public_path=self.incident_path,
            old_run_dir=self.old)
        batch["selection_retry_gate_sha256"] = "0" * 64
        with self.assertRaisesRegex(
                independent.ScaleAuditError,
                "scale_independent_validator_retry_gate_unbound"):
            independent._validator_retry_gate_independent(
                worker_private=self.private, plan=self.plan,
                batch_intent=batch, private_plan_path=self.new_plan,
                source_freeze_path=self.new_freeze,
                incident_public_path=self.incident_path,
                old_run_dir=self.old)

    def test_fake_no_gui_baseline_writes_new_gate(self):
        self.gate.unlink()
        self.sql.unlink()
        self.files.unlink()
        published = protocol.public_json(self.incident_path)
        modules = (
            SimpleNamespace(local_config=lambda: {"ODOO_PROJECT": "test"}),
            None,
            SimpleNamespace(filestore_manifest=lambda _volume: {"files": ["x"]}),
            SimpleNamespace(snapshot=lambda: {"rows": [1]}),
            SimpleNamespace(exclusive_worker_operation=lambda _operation:
                            nullcontext()),
        )
        with patch.dict(os.environ, {
                "ENVLOOP_ODOO_WORKER_DIR": str(self.worker.resolve())}), \
                patch.object(controller, "_preflight",
                             return_value=(self.plan, self.private)), \
                patch("tools.audit_odoo_v066_selection_third_invalid_action_v1.audit",
                      return_value=published), \
                patch.object(controller, "_modules", return_value=modules), \
                patch.object(controller, "_run_lock",
                             return_value=nullcontext()), \
                patch.object(controller, "_running_services_without_compose_blank",
                             return_value=set()), \
                patch.object(controller.train_recorder, "_compose") as compose:
            result = controller.prepare_selection_retry_gate(
                worker_dir=self.worker,
                new_private_plan_path=self.new_plan,
                new_public_plan_path=self.root / "new-public.json",
                new_source_freeze_path=self.new_freeze,
                old_run_dir=self.old,
                old_private_plan_path=self.root / "old-plan.json",
                old_public_plan_path=self.root / "old-public.json",
                old_source_freeze_path=self.root / "old-freeze.json",
                incident_public_path=self.incident_path,
                new_run_dir=self.controls / "future-validator-run")
        self.assertEqual(result["status"],
                         "same_id_retry_preflight_ready_no_gui_dispatched")
        self.assertEqual(compose.call_count, 2)
        self.assertEqual(protocol.private_json(self.gate)
                         ["prior_failed_control_count"], 3)


if __name__ == "__main__":
    unittest.main()
