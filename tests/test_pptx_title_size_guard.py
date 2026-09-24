import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

PATH = Path(__file__).resolve().parents[1] / 'tools/pptx_title_size_guard.py'
SPEC = importlib.util.spec_from_file_location('pptx_title_size_guard', PATH)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)

SLIDE = '''<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:cSld><p:spTree><p:sp><p:nvSpPr><p:cNvPr id="2" name="Title"/><p:nvPr><p:ph type="ctrTitle"/></p:nvPr></p:nvSpPr><p:txBody><a:p><a:r>{properties}<a:t>Same title</a:t></a:r></a:p></p:txBody></p:sp><p:sp><p:nvSpPr><p:cNvPr id="3" name="Subtitle"/><p:nvPr><p:ph type="subTitle"/></p:nvPr></p:nvSpPr><p:txBody><a:p><a:r><a:t>{subtitle}</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>'''


def deck(path, size=None, subtitle='Untouched subtitle', extra=None):
    props = '' if size is None else f'<a:rPr sz="{size}"/>'
    entries = {'[Content_Types].xml': b'<Types/>', 'ppt/presentation.xml': b'<presentation/>',
               'ppt/slides/slide1.xml': SLIDE.format(properties=props, subtitle=subtitle).encode(),
               'ppt/media/image1.png': b'original image', 'ppt/slides/_rels/slide1.xml.rels': b'<Relationships/>'}
    entries.update(extra or {})
    with zipfile.ZipFile(path, 'w') as archive:
        for name, data in entries.items():
            archive.writestr(name, data)


class TitleSizeGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.original = self.root / 'original.pptx'
        self.modified = self.root / 'modified.pptx'
        deck(self.original)
        self.contract = guard.freeze_contract(self.original, 'ppt/slides/slide1.xml', '2', 48.0)

    def tearDown(self):
        self.temp.cleanup()

    def check(self, **kwargs):
        deck(self.modified, **kwargs)
        return guard.verify(self.original, self.modified, self.contract)

    def test_only_correct_target_change_passes(self):
        self.assertEqual(self.check(size=4800)['score'], 1.0)
        self.assertEqual(self.check(size=3600)['score'], 0.0)
        self.assertEqual(self.check()['score'], 0.0)

    def test_correct_target_plus_same_slide_collateral_edit_fails(self):
        result = self.check(size=4800, subtitle='Unrequested corruption')
        self.assertTrue(result['target_correct'])
        self.assertFalse(result['preservation_pass'])
        self.assertEqual(result['score'], 0.0)
        self.assertEqual(result['unexpected_parts'], ['ppt/slides/slide1.xml'])

    def test_unrelated_image_relationship_notes_and_new_slide_changes_fail(self):
        for part, data in [('ppt/media/image1.png', b'changed image'),
                           ('ppt/slides/_rels/slide1.xml.rels', b'<Relationships><relationship/></Relationships>'),
                           ('ppt/notesSlides/notesSlide1.xml', b'<notes/>'),
                           ('ppt/slides/slide2.xml', b'<slide/>')]:
            with self.subTest(part=part):
                result = self.check(size=4800, extra={part: data})
                self.assertEqual(result['score'], 0.0)
                self.assertIn(part, result['unexpected_parts'])

    def test_changed_source_and_unreadable_artifacts_are_unscored(self):
        deck(self.modified, size=4800)
        deck(self.original, subtitle='changed source')
        result = guard.verify(self.original, self.modified, self.contract)
        self.assertEqual(result['status'], 'infrastructure_error')
        self.assertIsNone(result['score'])
        self.modified.write_text('not a pptx')
        self.assertIsNone(guard.verify(self.original, self.modified, self.contract)['score'])

    def test_xml_encoding_change_without_semantic_change_is_permitted(self):
        deck(self.modified, size=4800, extra={'ppt/presentation.xml': b'<?xml version="1.0"?><presentation></presentation>'})
        self.assertEqual(guard.verify(self.original, self.modified, self.contract)['score'], 1.0)

    def test_screenshot_failure_wrapped_as_zero_is_never_an_agent_zero(self):
        passed = self.check(size=4800)
        result = guard.combine_upstream(0.0, passed, 'ScreenshotsUnavailableError')
        self.assertEqual(result['status'], 'infrastructure_error')
        self.assertIsNone(result['score'])
        self.assertIsNone(result['strict_success'])

    def test_partial_upstream_and_false_positive_are_distinguished(self):
        passed = self.check(size=4800)
        self.assertEqual(guard.combine_upstream(.85, passed)['score'], 0.0)
        self.assertEqual(guard.combine_upstream(.85, passed)['upstream_partial_score'], .85)
        rejected = self.check(size=4800, subtitle='wrong')
        self.assertEqual(guard.combine_upstream(1.0, rejected)['score'], 0.0)
        self.assertEqual(guard.combine_upstream(1.0, passed)['score'], 1.0)

    def test_nan_and_unknown_contract_fail_closed(self):
        passed = self.check(size=4800)
        self.assertIsNone(guard.combine_upstream(float('nan'), passed)['score'])
        contract = copy.deepcopy(self.contract)
        contract['schema'] = 'unknown'
        self.assertIsNone(guard.verify(self.original, self.modified, contract)['score'])


if __name__ == '__main__':
    unittest.main()
