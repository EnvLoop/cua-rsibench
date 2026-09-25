"""Independent fresh-copy artifact controls must reject realistic near misses."""

from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from tools import audit_office_web_fresh_ppt as audit
from tools import stage_office_web_fresh_attempt as stage

P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
SLIDE = (f'<p:sld xmlns:p="{P}" xmlns:a="{A}"><p:cSld><p:spTree>'
         '<p:sp><p:nvSpPr><p:cNvPr id="2" name="Title"/><p:nvPr>'
         '<p:ph type="ctrTitle"/></p:nvPr></p:nvSpPr><p:txBody><a:p>{title_runs}'
         '</a:p></p:txBody></p:sp><p:sp><p:nvSpPr><p:cNvPr id="3" '
         'name="Subtitle"/><p:nvPr><p:ph type="subTitle"/></p:nvPr>'
         '</p:nvSpPr><p:txBody><a:p><a:r><a:t>{subtitle}</a:t>'
         '</a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>')


def deck(path: Path, *, kind: str = "base", subtitle: str = "Stable subtitle",
         media: bytes = b"stable") -> None:
    plain = '<a:r><a:t>Same title</a:t></a:r>'
    target = '<a:r><a:rPr sz="4800"/><a:t>Same title</a:t></a:r>'
    partial = ('<a:r><a:rPr sz="4800"/><a:t>Same </a:t></a:r>'
               '<a:r><a:t>title</a:t></a:r>')
    title = {"base": plain, "positive": target, "partial": partial}[kind]
    with ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("ppt/presentation.xml", "<presentation/>")
        archive.writestr("ppt/slides/slide1.xml", SLIDE.format(
            title_runs=title, subtitle=subtitle))
        archive.writestr("ppt/media/image1.png", media)


class FreshPptArtifactAuditTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "frozen.pptx"
        deck(self.source)
        self.attempt = self.root / "attempt"
        stage.stage(self.source, stage.digest(self.source), "powerpoint-web",
                    "selection-development-control", self.attempt)

    def freeze(self):
        return audit.freeze(self.attempt, slide_part="ppt/slides/slide1.xml",
                            shape_id="2", target_size_pt=48.0,
                            expected_collateral_part="ppt/slides/slide1.xml")

    def bind(self, *, positive="positive", partial="partial", collateral="positive",
             collateral_subtitle="Corrupted subtitle", reset_media=b"stable"):
        specs = {
            "untouched": dict(kind="base"),
            "positive": dict(kind=positive),
            "partial_negative": dict(kind=partial),
            "collateral_negative": dict(kind=collateral, subtitle=collateral_subtitle),
            "fresh_reset": dict(kind="base", media=reset_media),
        }
        for slot, kwargs in specs.items():
            local = self.root / f"local-{slot}.pptx"
            deck(local, **kwargs)
            stage.bind_operator_download(self.attempt, slot, local)

    def test_five_distinct_artifacts_pass_offline_controls_but_not_gui_admission(self):
        self.freeze()
        self.bind()
        result = audit.write_audit(self.attempt)
        self.assertEqual(result["status"], "checked")
        self.assertTrue(result["artifact_controls_pass"])
        self.assertFalse(result["gui_admitted"])
        self.assertEqual(result["official_final_credit"], 0)
        self.assertTrue(result["controls"]["positive"]["preservation_pass"])
        self.assertFalse(result["controls"]["collateral_negative"]["preservation_pass"])
        self.assertTrue((self.attempt / audit.RECEIPT_NAME).is_file())
        with self.assertRaisesRegex(ValueError, "never overwrite"):
            audit.write_audit(self.attempt)

    def test_partial_requires_real_mixed_target_runs(self):
        self.freeze()
        self.bind(partial="base")
        result = audit.audit(self.attempt)
        self.assertEqual(result["status"], "checked")
        self.assertFalse(result["artifact_controls_pass"])
        self.assertTrue(result["controls"]["partial_negative"]["preservation_pass"])

    def test_target_plus_collateral_media_and_wrong_object_are_rejected(self):
        self.freeze()
        self.bind(collateral_subtitle="Stable subtitle", reset_media=b"changed")
        result = audit.audit(self.attempt)
        self.assertFalse(result["artifact_controls_pass"])
        self.assertIn("ppt/media/image1.png",
                      result["controls"]["fresh_reset"]["unexpected_parts"])

    def test_oracle_must_precede_binding_and_remain_immutable(self):
        local = self.root / "download.pptx"
        deck(local)
        stage.bind_operator_download(self.attempt, "untouched", local)
        with self.assertRaisesRegex(ValueError, "must precede"):
            self.freeze()
        other = self.root / "other"
        stage.stage(self.source, stage.digest(self.source), "powerpoint-web", "other", other)
        audit.freeze(other, slide_part="ppt/slides/slide1.xml", shape_id="2",
                     target_size_pt=48, expected_collateral_part="ppt/slides/slide1.xml")
        incomplete = audit.audit(other)
        self.assertEqual(incomplete["status"], "incomplete_downloads")
        self.assertIsNone(incomplete["artifact_controls_pass"])
        (other / audit.ORACLE_NAME).write_text("{}")
        with self.assertRaisesRegex(ValueError, "oracle is missing or changed"):
            audit.audit(other)

    def test_unreadable_download_is_infrastructure_error_not_model_failure(self):
        self.freeze()
        self.bind()
        # The binding validator rejects a corrupt file; a later local loss
        # also cannot be mistaken for a student-model zero.
        (self.attempt / "downloads/positive.pptx").write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "downloaded artifact changed"):
            audit.audit(self.attempt)


if __name__ == "__main__":
    unittest.main()
