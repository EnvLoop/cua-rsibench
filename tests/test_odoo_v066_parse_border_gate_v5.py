"""Offline cleanup checks for the v5 Odoo no-GUI baseline collector."""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from tools import odoo_v066_parse_border_no_gui_gate_v5 as gate


class FakeLease:
    def exclusive_worker_operation(self, _operation):
        return nullcontext()


class GateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.worker = Path(self.temp.name) / "selection"
        self.worker.mkdir(mode=0o700)
        private = self.worker / "private"
        private.mkdir(mode=0o700)
        env = self.worker / ".env"
        env.write_text("ODOO_PARTITION=selection\n")
        env.chmod(0o600)
        lease = private / "worker-lease-events.jsonl"
        lease.write_bytes(b'{"event":"released"}\n')
        lease.chmod(0o600)
        self.compose = Mock()
        self.factory = Mock()
        self.factory.local_config.return_value = {"ODOO_PROJECT": "test"}
        self.reset = Mock()
        self.reset.filestore_manifest.return_value = {"files": []}
        self.verify = Mock()
        self.verify.snapshot.return_value = {"tables": []}
        self.modules = (self.factory, None, self.reset,
                        self.verify, FakeLease())

    def test_collect_checks_readiness_and_restores_stopped_state(self) -> None:
        with patch.object(gate.controller, "_modules",
                          return_value=self.modules), \
             patch.object(gate.controller, "_run_lock",
                          return_value=nullcontext()), \
             patch.object(gate.controller,
                          "_running_services_without_compose_blank",
                          return_value=set()), \
             patch.object(gate.train_recorder, "_compose", self.compose), \
             patch.object(gate.prior_gate, "_wait_db_ready",
                          return_value={"status": "ready"}):
            sql, files, ready, lease_sha, lease_bytes = gate.collect(
                self.worker)
        self.assertEqual(sql, {"tables": []})
        self.assertEqual(files, {"files": []})
        self.assertEqual(ready["status"], "ready")
        self.assertEqual(len(lease_sha), 64)
        self.assertGreater(lease_bytes, 0)
        self.assertEqual(self.compose.call_args_list[0].args[1:],
                         ("up", "-d", "db"))
        self.assertEqual(self.compose.call_args_list[-1].args[1:],
                         ("stop", "db"))

    def test_collect_stops_db_after_snapshot_error(self) -> None:
        self.verify.snapshot.side_effect = RuntimeError("test snapshot error")
        with patch.object(gate.controller, "_modules",
                          return_value=self.modules), \
             patch.object(gate.controller, "_run_lock",
                          return_value=nullcontext()), \
             patch.object(gate.controller,
                          "_running_services_without_compose_blank",
                          return_value=set()), \
             patch.object(gate.train_recorder, "_compose", self.compose), \
             patch.object(gate.prior_gate, "_wait_db_ready",
                          return_value={"status": "ready"}):
            with self.assertRaises(RuntimeError):
                gate.collect(self.worker)
        self.assertEqual(self.compose.call_args_list[-1].args[1:],
                         ("stop", "db"))


if __name__ == "__main__":
    unittest.main()
