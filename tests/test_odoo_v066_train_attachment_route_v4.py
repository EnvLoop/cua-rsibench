"""Cold Compose output must not consume a train-only route attempt."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import odoo_v066_train_attachment_calibration_v4 as calibration


class TrainAttachmentRouteV4Tests(unittest.TestCase):
    def test_cold_compose_newline_is_no_running_services(self) -> None:
        worker = Path("/synthetic/train")
        with patch.object(calibration.recorder, "_compose",
                          return_value=SimpleNamespace(stdout="\n")) as compose:
            self.assertEqual(calibration._running(worker), set())
        compose.assert_called_once_with(
            worker, "ps", "--status", "running", "--services")

    def test_whitespace_rows_are_ignored_without_losing_real_services(self) -> None:
        with patch.object(calibration.recorder, "_compose",
                          return_value=SimpleNamespace(
                              stdout="  \n\t\ndb\n web \n")):
            self.assertEqual(calibration._running(Path("/synthetic/train")),
                             {"db", "web"})

    def test_new_run_and_source_are_distinct_from_terminal_v3(self) -> None:
        self.assertEqual(calibration.RUN_NAME,
                         "attachment-route-train-pilot-20260929-02")
        self.assertIn("tools/odoo_v066_train_attachment_calibration_v4.py",
                      calibration.SOURCE_FILES)
        self.assertIn("tools/audit_odoo_v066_train_attachment_calibration_v4.py",
                      calibration.SOURCE_FILES)
        self.assertNotIn("tools/odoo_v066_train_attachment_calibration_v1.py",
                         calibration.SOURCE_FILES)


if __name__ == "__main__":
    unittest.main()
