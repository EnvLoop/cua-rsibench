"""Portable adversarial checks for the offline-only Enter-settle candidate."""

from __future__ import annotations

from io import BytesIO
import unittest

from PIL import Image, ImageDraw
from cursibench.scale_action_contract import ContractError

from native_desktop_factory.post_enter_settle_candidate_v1 import (
    validate_post_enter_transition,
)


def frame(*, toolbar: bool = False, caret: bool = False) -> bytes:
    image = Image.new("RGB", (1280, 800), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 250, 220, 280), fill="#D8E2E9")
    if toolbar:
        draw.rectangle((380, 85, 395, 105), fill="#D57234")
    if caret:
        draw.line((501, 300, 501, 320), fill="black")
    buffer = BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.a = frame()
        self.b = frame(toolbar=True)
        self.c = frame(caret=True)
        self.enter = {"type": "key", "key": "Enter"}

    def test_one_material_transition_then_exact_fresh_pair(self):
        result = validate_post_enter_transition(
            previous_action=self.enter, first_observation=self.a,
            first_predispatch=self.b, fresh_observation=self.b,
            fresh_predispatch=self.b, waited_ms=1000)
        self.assertTrue(result.next_action_requires_fresh_observation)
        self.assertEqual(result.material_predispatch_application_sha256,
                         result.fresh_predispatch_application_sha256)

    def test_only_prior_enter_and_exact_one_second_wait(self):
        for previous, delay in [({"type": "key", "key": "Control+S"}, 1000),
                                (self.enter, 0), (self.enter, 1200)]:
            with self.subTest(previous=previous, delay=delay), \
                    self.assertRaises(ValueError):
                validate_post_enter_transition(
                    previous_action=previous, first_observation=self.a,
                    first_predispatch=self.b, fresh_observation=self.b,
                    fresh_predispatch=self.b, waited_ms=delay)

    def test_third_state_or_late_predispatch_change_is_rejected(self):
        for fresh_observation, fresh_predispatch in [
            (self.c, self.c), (self.b, self.c), (self.a, self.a),
        ]:
            with self.subTest(), self.assertRaises(ValueError):
                validate_post_enter_transition(
                    previous_action=self.enter, first_observation=self.a,
                    first_predispatch=self.b,
                    fresh_observation=fresh_observation,
                    fresh_predispatch=fresh_predispatch, waited_ms=1000)

    def test_caret_or_no_change_remain_on_existing_guard(self):
        for first_predispatch in (self.a, self.c):
            with self.subTest(), self.assertRaises(ValueError):
                validate_post_enter_transition(
                    previous_action=self.enter, first_observation=self.a,
                    first_predispatch=first_predispatch,
                    fresh_observation=first_predispatch,
                    fresh_predispatch=first_predispatch, waited_ms=1000)

    def test_invalid_frame_fails_closed(self):
        with self.assertRaises(ContractError):
            validate_post_enter_transition(
                previous_action=self.enter, first_observation=b"not a PNG",
                first_predispatch=self.b, fresh_observation=self.b,
                fresh_predispatch=self.b, waited_ms=1000)


if __name__ == "__main__":
    unittest.main()
