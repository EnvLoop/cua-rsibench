"""Independent image-boundary checks for the preserved Odoo GUI failure."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from tools import audit_odoo_v066_current_candidate_first_failure_20260929 as audit


def png(image: Image.Image) -> bytes:
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


class FailureAuditUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.first = Image.new("RGB", (1440, 1000), (255, 255, 255))
        for xy in audit.PIXELS:
            self.first.putpixel(xy, (235, 237, 239))
        self.second = self.first.copy()
        for xy in audit.PIXELS:
            self.second.putpixel(xy, (235, 237, 240))

    def test_exact_two_pixel_alternate(self) -> None:
        self.assertTrue(audit.two_pixel_alternate(
            png(self.first), png(self.second)))
        self.assertTrue(audit.two_pixel_alternate(
            png(self.second), png(self.first)))

    def test_third_pixel_or_material_change_rejected(self) -> None:
        third = self.second.copy()
        third.putpixel((1400, 900), (0, 0, 0))
        self.assertFalse(audit.two_pixel_alternate(
            png(self.first), png(third)))
        other = self.first.copy()
        other.putpixel((41, 419), (0, 0, 0))
        self.assertFalse(audit.two_pixel_alternate(
            png(self.first), png(other)))
        self.assertFalse(audit.two_pixel_alternate(
            png(self.first), png(self.first)))

    def test_reference_hash_and_parent_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "frame.png").write_bytes(b"frame")
            reference = {"path": "frame.png",
                         "sha256": sha256(b"frame").hexdigest()}
            self.assertEqual(audit.ref_bytes(root, reference), b"frame")
            with self.assertRaises(audit.FailureAuditError):
                audit.ref_bytes(root, {**reference, "path": "../frame.png"})
            with self.assertRaises(audit.FailureAuditError):
                audit.ref_bytes(root, {**reference, "sha256": "0" * 64})

    def test_original_lease_prefix_survives_complete_append(self) -> None:
        acquired = "2026-09-29T05:49:32+00:00"
        released = "2026-09-29T05:50:07+00:00"
        original = [
            {"event": "acquired", "operation": "v066_scale_gui",
             "pid": 123, "at_utc": acquired},
            {"event": "released", "operation": "v066_scale_gui",
             "pid": 123, "at_utc": released},
        ]
        encode = lambda rows: b"".join(
            json.dumps(row, sort_keys=True).encode() + b"\n" for row in rows)
        prefix = encode(original)
        suffix = encode([
            {"event": "acquired", "operation": "future_gate", "pid": 234},
            {"event": "released", "operation": "future_gate", "pid": 234},
        ])
        args = dict(started=datetime.fromisoformat(
                        "2026-09-29T05:49:33+00:00"),
                    ended=datetime.fromisoformat(
                        "2026-09-29T05:50:08+00:00"),
                    prefix_bytes=len(prefix),
                    prefix_sha256=sha256(prefix).hexdigest(),
                    row_count=2, pid=123,
                    acquired_at=acquired, released_at=released)
        audit.verify_original_lease_prefix(prefix, **args)
        audit.verify_original_lease_prefix(prefix + suffix, **args)
        with self.assertRaises(audit.FailureAuditError):
            audit.verify_original_lease_prefix(prefix[:-1] + suffix, **args)
        with self.assertRaises(audit.FailureAuditError):
            audit.verify_original_lease_prefix(
                prefix.replace(b"v066_scale_gui", b"v066_other_gui") + suffix,
                **args)
        with self.assertRaises(audit.FailureAuditError):
            audit.verify_original_lease_prefix(prefix + suffix.splitlines()[0] + b"\n",
                                               **args)


if __name__ == "__main__":
    unittest.main()
