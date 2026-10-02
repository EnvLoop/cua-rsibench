"""The paid loop retries only a corroborated narrow caret alternate."""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from native_desktop_factory import qwen_v066_adapter_v4_strict as strict
from tests.test_native_desktop_v066_caret_liveness_v4 import Sandbox, _png


class StrictLivenessTests(unittest.TestCase):
    action = '{"type":"click","target":{"x":400,"y":300}}'

    def observe(self, sandbox):
        return strict.observe(
            sandbox, task_id="train.synthetic", task_binding_sha256="a" * 64,
            instruction="Edit the visible document.", step=0, max_actions=90)

    @patch.object(strict.prototype.v3.time, "sleep")
    def test_two_observation_caret_is_the_only_retry(self, _sleep):
        plain, caret = _png(), _png(x=502)
        sandbox = Sandbox([plain] + [caret] * 6 + [plain, caret])
        with self.assertRaises(strict.PhysicalFrameDrift):
            strict.parse_current_action(self.action, self.observe(sandbox), sandbox)
        action = strict.parse_current_action(
            self.action, self.observe(sandbox), sandbox)
        self.assertEqual(action["type"], "click")

    @patch.object(strict.prototype.v3.time, "sleep")
    def test_persistent_caret_and_material_change_end_attempt(self, _sleep):
        plain, caret, material = _png(), _png(x=502), _png(material=True)
        sandbox = Sandbox([plain] + [caret] * 8)
        with self.assertRaises(strict.PhysicalFrameDrift):
            strict.parse_current_action(self.action, self.observe(sandbox), sandbox)
        with self.assertRaises(strict.MaterialFrameDrift):
            strict.parse_current_action(self.action, self.observe(sandbox), sandbox)
        changed = Sandbox([plain, material])
        with self.assertRaises(strict.MaterialFrameDrift):
            strict.parse_current_action(self.action, self.observe(changed), changed)

    @patch.object(strict.prototype.v3.time, "sleep")
    def test_third_state_and_action_change_end_attempt(self, _sleep):
        plain, caret, other = _png(), _png(x=502), _png(x=503)
        for tail, action in ((other, self.action),
                             (caret, '{"type":"click","target":{"x":401,"y":300}}')):
            sandbox = Sandbox([plain] + [caret] * 6 + [plain, tail])
            with self.assertRaises(strict.PhysicalFrameDrift):
                strict.parse_current_action(self.action, self.observe(sandbox), sandbox)
            with self.assertRaises(strict.MaterialFrameDrift):
                strict.parse_current_action(action, self.observe(sandbox), sandbox)

    @patch.object(strict.prototype.v3.time, "sleep")
    def test_internal_b_to_c_third_state_cannot_be_recast_as_caret(self, _sleep):
        plain, first_caret, third_caret = (
            _png(), _png(x=502), _png(x=503))
        sandbox = Sandbox([plain, first_caret, third_caret,
                           plain, third_caret])
        with self.assertRaises(strict.MaterialFrameDrift):
            strict.parse_current_action(self.action, self.observe(sandbox), sandbox)
        self.assertNotIn(sandbox, strict.prototype._pending)
        self.assertEqual(sandbox.calls, [])

    @patch.object(strict.prototype.v3.time, "sleep")
    def test_allowed_probe_persists_all_six_raw_frames(self, _sleep):
        plain, caret = _png(), _png(x=502)
        sandbox = Sandbox([plain] + [caret] * 6 + [plain, caret])
        with TemporaryDirectory() as directory:
            root = Path(directory) / "attempts"
            out = root / "synthetic-11/positive"
            out.mkdir(parents=True)
            with patch.dict(os.environ, {
                    "ENVLOOP_DESKTOP_V4_ATTEMPTS_ROOT": str(root),
                    "ENVLOOP_DESKTOP_V4_ATTEMPT_DIR": str(out)}):
                with self.assertRaises(strict.PhysicalFrameDrift):
                    strict.parse_current_action(
                        self.action, self.observe(sandbox), sandbox)
                manifest = json.loads((out / "probe-step-00-00.json").read_bytes())
                self.assertEqual(manifest["status"], "pending_exact_alternate")
                self.assertEqual(len(manifest["sample_frames"]), 6)
                self.assertTrue(all((root / ref["private_path"]).is_file()
                                    for ref in manifest["sample_frames"]))
                self.assertEqual(strict.parse_current_action(
                    self.action, self.observe(sandbox), sandbox)["type"],
                    "click")


if __name__ == "__main__":
    unittest.main()
