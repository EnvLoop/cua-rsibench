"""The prospective control compiler does not execute or admit hidden tasks."""

from __future__ import annotations

import unittest

from native_desktop_factory.v066_control_plan import compile_script


class V066ControlPlanTests(unittest.TestCase):
    def test_gui_commands_compile_with_bounded_waits_and_trusted_guards(self):
        actions, guards = compile_script(
            "wait 7\npress ctrl,h\ndouble 400,300\nwrite replacement text\n"
            "assert_window Find and Replace\nscreen edited\nreadback\nstop\n")
        self.assertEqual([row["type"] for row in actions],
                         ["wait"] * 4 + ["key", "double_click", "type"])
        self.assertEqual([row["duration_ms"] for row in actions[:4]],
                         [2000, 2000, 2000, 1000])
        self.assertEqual(actions[-1],
                         {"type": "type", "text": "replacement text", "mode": "insert"})
        self.assertEqual(guards["visible_window_assertions"], 1)
        self.assertEqual(guards["saved_artifact_readbacks"], 1)

    def test_unapproved_shell_or_shortcut_fails_closed(self):
        for script in (
            "shell libreoffice --convert-to pdf\nreadback\nstop\n",
            "press ctrl,p\nreadback\nstop\n",
            "write x\nstop\n",
            "wait 11\nreadback\nstop\n",
            "click 1,2\nreadback\nstop\nstop\n",
        ):
            with self.subTest(script=script), self.assertRaises(ValueError):
                compile_script(script)


if __name__ == "__main__":
    unittest.main()
