"""Dated Odoo v3 gate identity and independent prefix-receipt tamper checks."""

from __future__ import annotations

from contextlib import ExitStack
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import audit_odoo_v066_current_candidate_no_gui_gate_v3 as audit
from tools import audit_odoo_v066_battery_authorized_batch_v3 as batch
from tools import odoo_v066_current_candidate_no_gui_gate_v3 as gate
from tools import odoo_v066_current_candidate_one_selection_v3 as runner
from tools import odoo_v066_lease_prefix_source_v3 as source
from tools import odoo_v066_battery_authorized_power_v2 as power
from tools import odoo_v066_scale_protocol_v1 as protocol


def sample(second: int) -> dict:
    raw = ("Now drawing from 'Battery Power'\n"
           " -InternalBattery-0 (id=12345) 35%; discharging; 1:30 remaining\n")
    return {
        "schema": power.POWER_SCHEMA,
        "captured_at_utc": f"2026-09-29T00:00:{second:02d}+00:00",
        "source": "Battery Power",
        "battery_percent": 35,
        "raw_pmset_stdout": raw,
        "raw_pmset_stdout_sha256": sha256(raw.encode()).hexdigest(),
        "battery_operation_authorized_by_user_on": "2026-09-29",
    }


class LeasePrefixGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.worker = self.root / "selection"
        self.private = self.worker / "private"
        self.epoch = self.private / "v066_current_candidate_epoch"
        self.epoch.mkdir(parents=True, mode=0o700)
        self.private.chmod(0o700)
        self.plan = self.epoch / "plan.private.json"
        self.public = self.root / "plan-public.json"
        self.old_private = self.root / "old-private.json"
        self.old_public = self.root / "old-public.json"
        self.freeze = self.root / "v3-freeze.json"
        for path in (self.public, self.old_private, self.old_public,
                     self.freeze):
            path.write_text("{}\n")
        self.failures = {label: char * 64 for label, char in
                         (("first", "1"), ("second", "2"), ("third", "3"))}
        self.prefixes = {
            "second": {"published_prefix_sha256": "a" * 64,
                       "published_prefix_bytes": 100,
                       "published_prefix_rows": 2},
            "third": {"published_prefix_sha256": "b" * 64,
                      "published_prefix_bytes": 200,
                      "published_prefix_rows": 4},
        }
        protocol.write_new(self.plan, {
            "run_nonce_hex": "a" * 32,
            "fresh_run_directory_name": "current-candidate-" + "a" * 32,
            "current_candidate_private_sha256": "b" * 64,
            "source_freeze_sha256": "c" * 64,
            "retained_terminal_failure_public_sha256s": self.failures,
        }, private=True)
        self.sql = {"baseline": "saved state"}
        self.files = {"filestore/a": "d" * 64}
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
        self.events.write_bytes(("\n".join(json.dumps(e) for e in events)
                                 + "\n").encode())
        self.events.chmod(0o600)

    def kwargs(self) -> dict:
        return dict(worker_dir=self.worker, historical_root=self.root,
                    private_plan=self.plan, public_plan=self.public,
                    old_private_plan=self.old_private,
                    old_public_plan=self.old_public)

    def contexts(self):
        return (
            patch.object(source, "validate", return_value={}),
            patch.object(source, "FREEZE", self.freeze),
            patch.object(gate.power, "capture", side_effect=[sample(0), sample(1)]),
            patch.object(gate.plan_audit, "audit", return_value={}),
            patch.object(gate.protocol, "_worker_split",
                         return_value=self.private),
            patch.object(gate.retained, "reaudit_retained",
                         return_value=(self.failures, self.prefixes)),
            patch.object(gate, "_collect_live_baseline", return_value=(
                self.sql, self.files,
                sha256(self.events.read_bytes()).hexdigest(),
                self.events.stat().st_size, True)),
            patch.dict(os.environ, {"ENVLOOP_ODOO_WORKER_DIR":
                                    str(self.worker.resolve())}),
        )

    def test_v3_gate_and_independent_audit_bind_old_prefixes(self) -> None:
        with ExitStack() as stack:
            for context in self.contexts():
                stack.enter_context(context)
            result = gate.prepare(**self.kwargs(), execute_baseline_check=True)
            self.assertEqual(result["schema"], gate.GATE_SCHEMA)
            receipt_path = self.epoch / gate.GATE_FILE
            receipt = protocol.private_json(receipt_path)
            self.assertEqual(receipt["retained_historical_lease_prefixes"],
                             self.prefixes)
            self.assertFalse(receipt["control_dispatch_authorized"])
            verified = audit.audit(**self.kwargs())
            self.assertEqual(verified["gate_sha256"], result["gate_sha256"])
            receipt["retained_historical_lease_prefixes"]["second"][
                "published_prefix_bytes"] += 1
            receipt_path.write_bytes(protocol.canonical(receipt))
            with self.assertRaisesRegex(audit.GateAuditError,
                                        "retained_failures_changed"):
                audit.audit(**self.kwargs())
        self.assertFalse((self.epoch /
                          "selection-20260929-no-gui-gate-battery-v2.private.json")
                         .exists())

    def test_runner_and_batch_use_v3_gate_source(self) -> None:
        self.assertEqual(source.validate()["schema"], source.SCHEMA)
        self.assertEqual(audit.PUBLIC_AUDIT.parent,
                         protocol.ROOT / "docs/evidence")
        self.assertFalse(audit.PUBLIC_AUDIT.exists())
        self.assertIs(runner.gate_audit, audit)
        self.assertIs(batch.gate_audit, audit)
        self.assertIs(runner.source, source)
        self.assertIs(batch.source, source)
        self.assertNotEqual(runner.BATCH_SCHEMA,
                            "envloop-odoo-v066-current-candidate-one-selection-intent-v2")


if __name__ == "__main__":
    unittest.main()
