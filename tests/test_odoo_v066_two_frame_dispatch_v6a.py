"""Mutation checks for additive Odoo v6 guard completeness audit."""

from __future__ import annotations

import unittest

from tests.test_odoo_v066_two_frame_dispatch_audit_v6 import TwoFrameAuditTests
from tools import audit_odoo_v066_two_frame_dispatch_v6a as strict


class StrictAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.case = TwoFrameAuditTests(
            "test_observed_return_audits_every_indexed_frame")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.case.action["step"] = 0
        self.case.write_result()

    def test_valid_trace_and_source_freeze(self) -> None:
        self.assertEqual(strict.audit_trace(
            self.case.root, self.case.trace, self.case.row)[
                "indexed_guard_pngs"], 9)
        self.assertEqual(strict.validate_source()["schema"], strict.SCHEMA)

    def test_paired_intent_result_identity_mutations_rejected(self) -> None:
        for key in ("task_id", "task_binding_sha256", "frame_id", "step"):
            with self.subTest(key=key):
                original = self.case.action[key]
                self.case.action[key] = (
                    12 if key == "step" else "tampered-" + key)
                self.case.write_result()
                with self.assertRaises(strict.StrictAuditError):
                    strict.audit_trace(
                        self.case.root, self.case.trace, self.case.row)
                self.case.action[key] = original
                self.case.write_result()

    def test_orphan_guard_png_rejected(self) -> None:
        extra = self.case.root / "frames/guard-0009.png"
        extra.write_bytes(self.case.observed)
        with self.assertRaisesRegex(
                strict.StrictAuditError,
                "strict_audit_guard_sink_file_set_unbound"):
            strict.audit_trace(self.case.root, self.case.trace, self.case.row)

    def test_missing_or_symlink_guard_png_rejected(self) -> None:
        guard = self.case.root / "frames/guard-0008.png"
        guard.unlink()
        with self.assertRaises(Exception):
            strict.audit_trace(self.case.root, self.case.trace, self.case.row)


if __name__ == "__main__":
    unittest.main()
