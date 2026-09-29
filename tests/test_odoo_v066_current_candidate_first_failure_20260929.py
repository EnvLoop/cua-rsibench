"""Independent image-boundary checks for the preserved Odoo GUI failure."""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
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


if __name__ == "__main__":
    unittest.main()
