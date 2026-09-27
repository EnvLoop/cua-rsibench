"""Native Office first-run modal must clear before GUI calibration actions."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from native_desktop_factory.gui_control_shell import wait_for_document_ready


class _Commands:
    def __init__(self, titles):
        self.titles = list(titles)

    def run(self, _cmd):
        value = self.titles.pop(0) if self.titles else ""
        return type("Result", (), {"stdout": value + "\n"})()


class _Sandbox:
    def __init__(self, titles):
        self.commands = _Commands(titles)
        self.presses = []

    def press(self, key):
        self.presses.append(key)


class ReadyWindowTests(unittest.TestCase):
    def test_late_first_run_tip_is_dismissed_before_actor(self):
        filename = "case.docx"
        sandbox = _Sandbox(["", filename + " - LibreOffice Writer",
                            "Tip of the Day: 1/223",
                            filename + " - LibreOffice Writer",
                            filename + " - LibreOffice Writer"])
        with patch("native_desktop_factory.gui_control_shell.time.sleep"):
            result = wait_for_document_ready(sandbox, filename, seconds=6)
        self.assertEqual(result["first_run_tip_dismissals"], 1)
        self.assertEqual(sandbox.presses, ["esc"])
        self.assertIn(filename, result["ready_window_title"])

    def test_missing_document_fails_closed(self):
        sandbox = _Sandbox(["", "Other app", ""])
        with patch("native_desktop_factory.gui_control_shell.time.sleep"):
            with self.assertRaisesRegex(TimeoutError, "never became ready"):
                wait_for_document_ready(sandbox, "case.docx", seconds=3)


if __name__ == "__main__":
    unittest.main()
