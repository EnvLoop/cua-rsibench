"""Reset-controller tests preserve the line between local copies and GUI evidence."""

import importlib.util
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "stage_office_web_fresh_attempt", ROOT / "tools/stage_office_web_fresh_attempt.py")
controller = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(controller)


def pptx(path: Path, slide: bytes = b"<p:sld/>"):
    with ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("ppt/presentation.xml", "<p:presentation/>")
        archive.writestr("ppt/slides/slide1.xml", slide)


def xlsx(path: Path):
    with ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")


class FreshOfficeControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "office-baseline.pptx"
        pptx(self.source)
        self.sha = sha256(self.source.read_bytes()).hexdigest()
        self.attempt = self.root / "attempt"

    def tearDown(self):
        self.temp.cleanup()

    def test_staging_produces_distinct_private_copies_without_gui_credit(self):
        manifest = controller.stage(self.source, self.sha, "powerpoint-web", "selection-control", self.attempt)
        self.assertEqual(len(manifest["slots"]), 5)
        self.assertEqual(len({r["inode"] for r in manifest["slots"].values()}), 5)
        self.assertFalse(manifest["cloud_upload_verified"])
        self.assertFalse(manifest["fresh_cloud_reset_verified"])
        self.assertEqual((self.attempt / "controller.json").stat().st_mode & 0o777, 0o600)
        self.assertEqual(controller.verify_staged(self.attempt)["status"],
                         "local_byte_integrity_pass_gui_provenance_unverified")
        with self.assertRaisesRegex(ValueError, "already exists"):
            controller.stage(self.source, self.sha, "powerpoint-web", "selection-control", self.attempt)

    def test_source_and_input_tampering_fail_closed(self):
        controller.stage(self.source, self.sha, "powerpoint-web", "selection-control", self.attempt)
        pptx(self.source, b"source changed")
        # The private source snapshot remains auditable if the upstream
        # worktree is later modified or removed.
        self.assertFalse(controller.verify_staged(self.attempt)["gui_admitted"])
        pptx(self.attempt / "source_snapshot.pptx", b"snapshot changed")
        with self.assertRaisesRegex(ValueError, "source snapshot"):
            controller.verify_staged(self.attempt)
        pptx(self.attempt / "source_snapshot.pptx")
        pptx(self.attempt / "inputs/positive.pptx", b"candidate changed")
        with self.assertRaisesRegex(ValueError, "fresh input changed"):
            controller.verify_staged(self.attempt)

    def test_download_binding_checks_file_bytes_but_never_proves_cloud_origin(self):
        controller.stage(self.source, self.sha, "powerpoint-web", "selection-control", self.attempt)
        download = self.root / "download.pptx"
        pptx(download, b"edited")
        result = controller.bind_operator_download(self.attempt, "positive", download)
        self.assertEqual(result["download_binding_count"], 1)
        self.assertFalse(result["gui_admitted"])
        manifest = json.loads((self.attempt / "controller.json").read_text())
        self.assertEqual(manifest["downloads"]["positive"]["provenance"],
                         "operator_supplied_file_not_independent_cloud_proof")
        with self.assertRaisesRegex(ValueError, "already has"):
            controller.bind_operator_download(self.attempt, "positive", download)
        pptx(self.attempt / "downloads/positive.pptx", b"tampered")
        with self.assertRaisesRegex(ValueError, "downloaded artifact changed"):
            controller.verify_staged(self.attempt)

    def test_wrong_source_hash_invalid_zip_and_unsafe_manifest_path_fail(self):
        with self.assertRaisesRegex(ValueError, "frozen pin"):
            controller.stage(self.source, "0"*64, "powerpoint-web", "selection-control", self.attempt)
        self.source.write_bytes(b"not an Office document")
        with self.assertRaisesRegex(ValueError, "not a valid ZIP"):
            controller.stage(self.source, sha256(self.source.read_bytes()).hexdigest(),
                             "powerpoint-web", "selection-control", self.attempt)
        pptx(self.source)
        controller.stage(self.source, self.sha, "powerpoint-web", "selection-control", self.attempt)
        manifest_path = self.attempt / "controller.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["slots"]["fresh_reset"]["path"] = "../outside.pptx"
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "unsafe controller"):
            controller.verify_staged(self.attempt)

    def test_repo_private_copy_guard_blocks_public_output(self):
        with patch.object(controller, "PROJECT_ROOT", self.root):
            with self.assertRaisesRegex(ValueError, "ignored work"):
                controller.stage(self.source, self.sha, "powerpoint-web", "selection-control",
                                 self.root / "docs/published-attempt")

    def test_excel_cell_uses_xlsx_and_rejects_cross_format_source(self):
        with self.assertRaisesRegex(ValueError, "wrong extension"):
            controller.stage(self.source, self.sha, "excel-web", "case", self.attempt)
        book = self.root / "office-baseline.xlsx"
        xlsx(book)
        result = controller.stage(book, sha256(book.read_bytes()).hexdigest(),
                                  "excel-web", "case", self.attempt)
        self.assertEqual(result["cell_id"], "excel-web")
        self.assertFalse(controller.verify_staged(self.attempt)["gui_admitted"])


if __name__ == "__main__":
    unittest.main()
