"""A v0.6.6 smoke may only use the pinned public Impress train fixture."""

from __future__ import annotations

import unittest

from native_desktop_factory.v066_train_primitive_smoke import (
    MAX_ACTIONS, _script, _train_package,
)


class V066TrainSmokeTests(unittest.TestCase):
    def test_pinned_fixture_and_bounded_native_primitive_script(self):
        package, oracle, baseline, instruction, filename = _train_package()
        self.assertEqual(package["split"], "train")
        self.assertEqual(oracle["split"], "train")
        self.assertTrue(filename.endswith(".pptx"))
        self.assertTrue(baseline)
        self.assertIn("native LibreOffice GUI", instruction)
        script = _script(next(iter(oracle["targets"].values())))
        self.assertLessEqual(len(script), MAX_ACTIONS)
        self.assertEqual(sum(row["type"] == "double_click" for row in script), 1)
        focused = [row for row in script if row["type"] == "type"]
        self.assertEqual(len(focused), 1)
        self.assertNotIn("target", focused[0])
        self.assertEqual(focused[0]["mode"], "insert")
        keys = [row["key"] for row in script if row["type"] == "key"]
        for chord in ("Control+F", "Control+H", "Control+End", "Shift+End"):
            self.assertIn(chord, keys)


if __name__ == "__main__":
    unittest.main()
