"""Fake full SQL/filestore gate with independent tamper checks."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import audit_odoo_v066_current_candidate_no_gui_gate_v1 as auditor
from tools import odoo_v066_current_candidate_no_gui_gate_v1 as gate
from tools import odoo_v066_scale_protocol_v1 as protocol


class CurrentCandidateNoGuiGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.worker = self.root / "selection"
        self.private = self.worker / "private"
        self.epoch_dir = self.private / "v066_current_candidate_epoch"
        self.epoch_dir.mkdir(parents=True, mode=0o700)
        self.private.chmod(0o700)
        self.plan_path = self.epoch_dir / "selection-20260929.private.json"
        self.public_path = self.root / "selection-public.json"
        self.old_private = self.root / "old-private.json"
        self.old_public = self.root / "old-public.json"
        for path in (self.public_path, self.old_private, self.old_public):
            path.write_text("{}\n", encoding="utf-8")
        self.failures = {"first": "1" * 64, "second": "2" * 64,
                         "third": "3" * 64}
        protocol.write_new(self.plan_path, {
            "run_nonce_hex": "a" * 32,
            "fresh_run_directory_name": "current-candidate-" + "a" * 32,
            "current_candidate_private_sha256": "b" * 64,
            "source_freeze_sha256": "c" * 64,
            "retained_terminal_failure_public_sha256s": self.failures,
        }, private=True)
        self.sql = {"tables": ["saved-state-baseline"]}
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
        self.events.write_bytes(("\n".join(json.dumps(event)
                                     for event in events) + "\n").encode())
        self.events.chmod(0o600)

    def _call(self):
        return gate.prepare(
            worker_dir=self.worker, historical_root=self.root,
            private_plan=self.plan_path, public_plan=self.public_path,
            old_private_plan=self.old_private,
            old_public_plan=self.old_public,
            execute_baseline_check=True)

    def _mocks(self):
        return (
            patch.object(gate, "_ac_power", return_value=True),
            patch.object(gate.plan_audit, "audit", return_value={}),
            patch.object(gate.protocol, "_worker_split",
                         return_value=self.private),
            patch.object(gate, "_reaudit_failures",
                         return_value=self.failures),
            patch.object(gate, "_collect_live_baseline",
                         return_value=(self.sql, self.files,
                                       sha256(self.events.read_bytes()).hexdigest(),
                                       self.events.stat().st_size, True)),
            patch.dict(os.environ, {"ENVLOOP_ODOO_WORKER_DIR":
                                    str(self.worker.resolve())}),
        )

    def test_exact_sql_and_every_filestore_entry_passes_then_tamper_fails(self):
        from contextlib import ExitStack
        with ExitStack() as stack:
            for context in self._mocks():
                stack.enter_context(context)
            value = self._call()
            self.assertEqual(value["status"], gate.GATE_STATUS)
            self.assertFalse(value["control_dispatch_authorized"])
            audited = auditor.audit(
                worker_dir=self.worker, historical_root=self.root,
                private_plan=self.plan_path, public_plan=self.public_path,
                old_private_plan=self.old_private,
                old_public_plan=self.old_public)
            self.assertEqual(audited["retained_terminal_selection_failures"], 3)
            self.assertFalse(audited["control_dispatch_authorized"])
            path = self.epoch_dir / gate.FILES_FILE
            files = protocol.private_json(path)
            files.pop("filestore/two")
            path.write_bytes(protocol.canonical(files))
            with self.assertRaisesRegex(auditor.GateAuditError,
                                        "full_baseline_inexact"):
                auditor.audit(
                    worker_dir=self.worker, historical_root=self.root,
                    private_plan=self.plan_path, public_plan=self.public_path,
                    old_private_plan=self.old_private,
                    old_public_plan=self.old_public)

    def test_battery_refuses_before_any_gate_output(self):
        with patch.object(gate, "_ac_power", return_value=False):
            with self.assertRaisesRegex(gate.NoGuiGateError,
                                        "verified_ac_power"):
                self._call()
        self.assertFalse((self.epoch_dir / gate.GATE_FILE).exists())

    def test_mismatch_does_not_write_claimed_pass(self):
        from contextlib import ExitStack
        mocks = self._mocks()
        with ExitStack() as stack:
            for context in mocks:
                stack.enter_context(context)
            with patch.object(gate, "_collect_live_baseline",
                              return_value=(self.sql, {"wrong": "content"},
                                            sha256(self.events.read_bytes()).hexdigest(),
                                            self.events.stat().st_size, True)):
                with self.assertRaisesRegex(gate.NoGuiGateError,
                                            "current_sql_or_full_filestore_not_exact"):
                    self._call()
        self.assertFalse((self.epoch_dir / gate.GATE_FILE).exists())


if __name__ == "__main__":
    unittest.main()
