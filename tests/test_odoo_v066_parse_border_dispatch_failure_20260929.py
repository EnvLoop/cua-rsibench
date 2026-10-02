"""Offline evidence boundaries for the preserved Odoo v5 dispatch failure."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from io import BytesIO
import json
import unittest

from PIL import Image

from tools import audit_odoo_v066_parse_border_dispatch_failure_20260929 as audit


def png(image: Image.Image) -> bytes:
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


class DispatchFailureAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        first = Image.new("RGB", (1440, 1000), (255, 255, 255))
        for point in ((41, 419), (132, 419)):
            first.putpixel(point, (235, 237, 240))
        alternate = first.copy()
        for point in ((41, 419), (132, 419)):
            alternate.putpixel(point, (235, 237, 239))
        self.observed = png(first)
        self.alternate = png(alternate)

    def test_exact_observed_return_is_not_a_third_image(self) -> None:
        self.assertEqual(audit.classify_return(
            self.observed, [self.alternate] * 6, self.observed),
            "exact_observed_return_after_six_identical_two_pixel_alternates")

    def test_third_final_png_or_changed_alternate_fails(self) -> None:
        third = Image.open(BytesIO(self.observed)).copy()
        third.putpixel((800, 800), (0, 0, 0))
        with self.assertRaises(audit.DispatchFailureAuditError):
            audit.classify_return(self.observed,
                                  [self.alternate] * 6, png(third))
        with self.assertRaises(audit.DispatchFailureAuditError):
            audit.classify_return(self.observed,
                                  [self.alternate] * 5 + [png(third)],
                                  self.observed)

    def test_lease_prefix_rejects_mutation_but_allows_complete_append(self) -> None:
        acquired = "2026-09-29T07:43:17+00:00"
        released = "2026-09-29T07:43:50+00:00"
        encode = lambda rows: b"".join(
            json.dumps(row, sort_keys=True).encode() + b"\n" for row in rows)
        prefix = encode([
            {"event": "acquired", "operation": "v066_scale_gui",
             "pid": 123, "at_utc": acquired},
            {"event": "released", "operation": "v066_scale_gui",
             "pid": 123, "at_utc": released},
        ])
        suffix = encode([
            {"event": "acquired", "operation": "later", "pid": 234},
            {"event": "released", "operation": "later", "pid": 234},
        ])
        args = dict(started=datetime.fromisoformat(
                        "2026-09-29T07:43:18+00:00"),
                    ended=datetime.fromisoformat(
                        "2026-09-29T07:43:51+00:00"),
                    prefix_bytes=len(prefix),
                    prefix_sha256=sha256(prefix).hexdigest(),
                    row_count=2, pid=123,
                    acquired_at=acquired, released_at=released)
        audit.verify_lease_prefix(prefix + suffix, **args)
        with self.assertRaises(audit.DispatchFailureAuditError):
            audit.verify_lease_prefix(prefix[:-1] + suffix, **args)
        with self.assertRaises(audit.DispatchFailureAuditError):
            audit.verify_lease_prefix(
                prefix.replace(b"v066_scale_gui", b"v066_other_gui") + suffix,
                **args)
        with self.assertRaises(audit.DispatchFailureAuditError):
            audit.verify_lease_prefix(prefix + suffix.splitlines()[0] + b"\n",
                                      **args)


if __name__ == "__main__":
    unittest.main()
