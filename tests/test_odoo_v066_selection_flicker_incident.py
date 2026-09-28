from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from tools.audit_odoo_v066_selection_flicker_v1 import (
    SelectionIncidentError, audit_rejections, changed_pixels,
)


def private(path: Path, raw: bytes) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_bytes(raw)
    path.chmod(0o600)
    return {"path": str(path.relative_to(path.parents[1])),
            "sha256": sha256(raw).hexdigest()}


class SelectionFlickerIncidentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.attempt = Path(self.temp.name) / "attempt-000"
        self.attempt.mkdir(mode=0o700)
        images = {}
        for label, blue in (("a", 239), ("b", 240)):
            image = Image.new("RGB", (1440, 1000), (255, 255, 255))
            for x in (41, 132):
                image.putpixel((x, 419), (235, 237, blue))
            path = self.attempt / "frames" / f"{label}.png"
            path.parent.mkdir(mode=0o700, exist_ok=True)
            image.save(path)
            path.chmod(0o600)
            images[label] = {"path": f"frames/{label}.png",
                             "sha256": sha256(path.read_bytes()).hexdigest()}
        self.images = images
        action = private(self.attempt / "actions" / "click.json",
                         b'{"type":"click","target":{"x":1400,"y":870}}')
        self.refs = []
        for index, (first, second) in enumerate((("a", "b"), ("b", "a"),
                                                  ("a", "b"))):
            prefix = "step-003" + ("" if index == 0 else
                                   f"-resample-{index:02d}")
            raw = json.dumps({
                "schema": "envloop-odoo-v066-pre-intent-frame-rejection-v1",
                "phase": "positive", "step": 3,
                "observation_attempt": index, "error_code": "stale_frame",
                "pre_dispatch_intent_created": False,
                "gui_action_dispatched": False,
                "observed_frame_ref": images[first],
                "current_frame_ref": images[second],
                "assistant_action_ref": action,
            }, sort_keys=True).encode()
            self.refs.append(private(self.attempt / "actions" /
                                     f"{prefix}-rejection.private.json", raw))
        self.trace = {"actions": [{}, {}, {}],
                      "pre_intent_rejections": self.refs,
                      "sft_examples_written": 0}

    def test_exact_alternating_two_pixel_flicker_is_bound(self):
        self.assertEqual(audit_rejections(self.attempt, self.trace), (3, 2))

    def test_intent_after_rejection_fails_closed(self):
        private(self.attempt / "actions" / "step-003-intent.private.json",
                b"{}")
        with self.assertRaisesRegex(SelectionIncidentError,
                                    "incident_rejection_not_pre_intent"):
            audit_rejections(self.attempt, self.trace)

    def test_changed_business_pixel_is_not_two_pixel_flicker(self):
        path = self.attempt / "frames" / "c.png"
        image = Image.open(self.attempt / "frames" / "b.png")
        image.putpixel((800, 400), (0, 0, 0))
        image.save(path)
        path.chmod(0o600)
        self.assertEqual(len(changed_pixels(self.attempt / "frames" / "a.png",
                                            path)), 3)


if __name__ == "__main__":
    unittest.main()
