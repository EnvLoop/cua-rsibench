"""Public boundary tests; signed private evidence is replayed separately."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from tools.office_excel_transfer_signed_review_v1 import _private_modes


class SignedExcelReviewPrivacyTests(unittest.TestCase):
    def test_owner_only_modes_required_at_all_levels(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "private"
            nested = root / "source_snapshot" / "work"
            nested.mkdir(parents=True)
            source = nested / "generator.mjs"
            source.write_text("if (faults.size !== 9) throw Error();\n")
            for directory in (root, root / "source_snapshot", nested):
                os.chmod(directory, 0o700)
            os.chmod(source, 0o600)
            _private_modes(root)
            os.chmod(nested, 0o755)
            with self.assertRaisesRegex(ValueError, "nested_mode_changed"):
                _private_modes(root)

    def test_final_workbook_cannot_enter_source_review_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "private"
            root.mkdir(mode=0o700)
            workbook = root / "hidden-final.xlsx"
            workbook.write_bytes(b"not a workbook")
            os.chmod(workbook, 0o600)
            with self.assertRaisesRegex(ValueError, "must_not_contain_workbooks"):
                _private_modes(root)

    def test_source_snapshot_cannot_escape_through_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "private"
            root.mkdir(mode=0o700)
            (root / "escaped.mjs").symlink_to(Path(temp) / "elsewhere.mjs")
            with self.assertRaisesRegex(ValueError, "symlink_forbidden"):
                _private_modes(root)


if __name__ == "__main__":
    unittest.main()
