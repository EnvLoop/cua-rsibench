"""Safety checks for the evaluator-owned PPT-Eval Office artifact gate."""

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('ppt_eval_office_admission',
                                             ROOT / 'tools/ppt_eval_office_admission.py')
import sys
sys.path.insert(0, str(ROOT / 'tools'))
admission = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(admission)

SLIDE = '''<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:cSld><p:spTree><p:sp><p:nvSpPr><p:cNvPr id="2" name="Title"/><p:nvPr><p:ph type="ctrTitle"/></p:nvPr></p:nvSpPr><p:txBody><a:p><a:r>{properties}<a:t>Same title</a:t></a:r></a:p></p:txBody></p:sp><p:sp><p:nvSpPr><p:cNvPr id="3" name="Subtitle"/><p:nvPr><p:ph type="subTitle"/></p:nvPr></p:nvSpPr><p:txBody><a:p><a:r><a:t>{subtitle}</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>'''


def deck(path, size=None, subtitle='Untouched subtitle', media=b'original image'):
    props = '' if size is None else f'<a:rPr sz="{size}"/>'
    members = {'[Content_Types].xml': b'<Types/>',
               'ppt/presentation.xml': b'<presentation/>',
               'ppt/slides/slide1.xml': SLIDE.format(properties=props, subtitle=subtitle).encode(),
               'ppt/slides/_rels/slide1.xml.rels': b'<Relationships/>',
               'ppt/media/image1.png': media}
    with zipfile.ZipFile(path, 'w') as archive:
        for name, data in members.items():
            archive.writestr(name, data)


class OfficeAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / 'source.pptx'
        self.baseline = self.root / 'normalized.pptx'
        self.candidate = self.root / 'candidate.pptx'
        self.rubric = self.root / 'rubric.json'
        self.contract = self.root / 'controller-only' / 'contract.json'
        deck(self.source)
        deck(self.baseline)
        self.rubric.write_text('{}')
        self.source_pin = patch.object(admission, 'SOURCE_SHA256', admission.digest(self.source))
        self.rubric_pin = patch.object(admission, 'RUBRIC_SHA256', admission.digest(self.rubric))
        self.source_pin.start()
        self.rubric_pin.start()

    def tearDown(self):
        self.rubric_pin.stop()
        self.source_pin.stop()
        self.temp.cleanup()

    def test_freeze_before_candidate_and_positive_negative_scoring(self):
        receipt = admission.freeze(self.source, self.baseline, self.candidate,
                                   self.rubric, self.contract)
        self.assertEqual(receipt['status'], 'frozen')
        self.assertEqual(self.contract.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(self.contract.read_text())['candidate_path'], str(self.candidate.resolve()))
        deck(self.candidate, size=4800)
        with patch.object(admission, 'official_score', return_value=(1.0, [{'name': 'target', 'score': 1.0}])):
            passed = admission.verify(self.source, self.baseline, self.candidate,
                                      self.rubric, self.contract, self.root)
        self.assertEqual((passed['status'], passed['score'], passed['official_score']), ('scored', 1.0, 1.0))
        deck(self.candidate, size=3600)
        with patch.object(admission, 'official_score', return_value=(0.0, [])):
            failed = admission.verify(self.source, self.baseline, self.candidate,
                                      self.rubric, self.contract, self.root)
        self.assertEqual((failed['status'], failed['score'], failed['official_score']), ('scored', 0.0, 0.0))

    def test_freeze_refuses_existing_candidate_or_contract(self):
        deck(self.candidate, size=4800)
        with self.assertRaisesRegex(ValueError, 'freeze before'):
            admission.freeze(self.source, self.baseline, self.candidate, self.rubric, self.contract)
        self.candidate.unlink()
        admission.freeze(self.source, self.baseline, self.candidate, self.rubric, self.contract)
        with self.assertRaisesRegex(ValueError, 'freeze before'):
            admission.freeze(self.source, self.baseline, self.candidate, self.rubric, self.contract)

    def test_baseline_screen_rejects_content_loss_and_target_already_done(self):
        for kwargs in ({'subtitle': 'Corrupted'}, {'media': b'changed'}, {'size': 4800}):
            with self.subTest(kwargs=kwargs):
                deck(self.baseline, **kwargs)
                with self.assertRaises(admission.guard.ArtifactUnavailable):
                    admission.freeze(self.source, self.baseline, self.candidate,
                                     self.rubric, self.contract)

    def test_candidate_must_follow_freeze_and_match_frozen_source(self):
        admission.freeze(self.source, self.baseline, self.candidate, self.rubric, self.contract)
        deck(self.candidate, size=4800)
        os.utime(self.candidate, (1, 1))
        with self.assertRaisesRegex(admission.guard.ArtifactUnavailable, 'predates'):
            admission.verify(self.source, self.baseline, self.candidate,
                             self.rubric, self.contract, self.root)
        os.utime(self.candidate, None)
        deck(self.source, subtitle='Changed after freeze')
        with self.assertRaisesRegex(admission.guard.ArtifactUnavailable, 'differs'):
            admission.verify(self.source, self.baseline, self.candidate,
                             self.rubric, self.contract, self.root)

    def test_official_failure_remains_unscored(self):
        admission.freeze(self.source, self.baseline, self.candidate, self.rubric, self.contract)
        deck(self.candidate, size=4800)
        with patch.object(admission, 'official_score', side_effect=RuntimeError('renderer failure')):
            result = admission.verify(self.source, self.baseline, self.candidate,
                                      self.rubric, self.contract, self.root)
        self.assertEqual(result['status'], 'infrastructure_error')
        self.assertIsNone(result['score'])
        self.assertEqual(result['combined']['error_type'], 'RuntimeError')

    def test_reset_accepts_inherited_or_explicit_42_but_rejects_collateral_change(self):
        reset = self.root / 'reset.pptx'
        admission.freeze(self.source, self.baseline, self.candidate, self.rubric, self.contract)
        deck(self.candidate, size=4800)
        deck(reset, size=4200)
        later = self.candidate.stat().st_mtime + 2
        os.utime(reset, (later, later))
        with patch.object(admission, 'official_score', return_value=(0.0, [])):
            result = admission.verify_reset(self.source, self.baseline, self.candidate,
                                            reset, self.rubric, self.contract, self.root)
        self.assertEqual((result['status'], result['reset_pass']), ('checked', True))

        deck(reset, size=4200, subtitle='Unrequested change')
        os.utime(reset, (later, later))
        with patch.object(admission, 'official_score', return_value=(0.0, [])):
            result = admission.verify_reset(self.source, self.baseline, self.candidate,
                                            reset, self.rubric, self.contract, self.root)
        self.assertEqual((result['status'], result['reset_pass']), ('checked', False))


if __name__ == '__main__':
    unittest.main()
