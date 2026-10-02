"""Prove the v1 timestamp artifact and the prospective v2 scoring boundary."""

from __future__ import annotations

from dataclasses import replace
import io
import unittest

from PIL import Image

from cursibench import qwen38_real_gui_diagnostic_v1 as original
from cursibench import qwen38_real_gui_diagnostic_scoring_v2 as scoring
from cursibench.scale_action_contract import make_observation


def observation():
    png = io.BytesIO()
    Image.new("RGB", (1280, 800), (230, 232, 235)).save(png, "PNG")
    return make_observation(
        task_id="public-train-scoring-regression",
        task_binding_sha256="a" * 64,
        instruction="Use the visible public training document.",
        step=0, screenshot_bytes=png.getvalue())


class ArchivedScoringTests(unittest.TestCase):
    def test_v1_expired_frame_artifact_is_corrected_without_new_action(self):
        frame = replace(observation(), issued_at=0.0, expires_at=1.0)
        target = {"type": "wait", "duration_ms": 1000}
        text = '{"type":"wait","duration_ms":1000}'
        self.assertFalse(original.score_action_text(
            text, frame, target)["format_valid"])
        self.assertEqual(scoring.score_archived_action_text(
            text, frame, target), {
                "format_valid": True, "action_type_match": True,
                "payload_exact_match": True, "error_type": None})

    def test_reissue_keeps_exact_source_binding_and_frame_identity(self):
        frame = replace(observation(), issued_at=0.0, expires_at=1.0)
        renewed = scoring.reissue_archived_frame(frame)
        self.assertEqual(replace(renewed, issued_at=0.0, expires_at=1.0),
                         frame)
        self.assertEqual(renewed.frame_id, frame.frame_id)
        self.assertEqual(renewed.screenshot_bytes, frame.screenshot_bytes)
        self.assertGreater(renewed.expires_at, renewed.issued_at)

    def test_live_expired_frame_is_a_fail_fast_error_not_model_failure(self):
        frame = replace(observation(), issued_at=0.0, expires_at=1.0)
        with self.assertRaisesRegex(
                scoring.ScoringV2Error, "diagnostic_v2_live_frame_expired"):
            scoring.score_live_action_text(
                '{"type":"wait","duration_ms":1000}', frame,
                {"type": "wait", "duration_ms": 1000})


if __name__ == "__main__":
    unittest.main()
