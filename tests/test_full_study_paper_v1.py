"""Synthetic, watermarked layout test; never a benchmark-result artifact."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from PIL import Image
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from cursibench import full_study_paper_v1 as paper  # noqa: E402
from cursibench import full_study_matrix_v1 as matrix  # noqa: E402
import test_full_study_publication_v1 as publication_fixture  # noqa: E402


class PaperLayoutTests(unittest.TestCase):
    def test_synthetic_layout_is_watermarked_and_not_overwritten(self):
        fixture = publication_fixture.PublicationGateTests
        fixture.setUpClass()
        try:
            telemetry = fixture.telemetry
            measure = publication_fixture.publication._telemetry_bundle(
                telemetry, fixture.root, fixture.index, fixture.root,
                fixture.summary)
            data = {
                'plan': fixture.plan,
                'summary': fixture.summary,
                'telemetry': measure,
                'trajectory': publication_fixture.publication._trajectory_bundle(
                    fixture.trajectory, fixture.root, fixture.index,
                    fixture.root, fixture.summary),
                'usage': publication_fixture.publication._usage_aggregates(
                    fixture.index, fixture.root, fixture.summary),
                'family_counts': {cell: 10 for cell in matrix.CELLS},
                'source_hashes': {'synthetic_fixture': 'test-only'},
            }
            with tempfile.TemporaryDirectory(prefix='cua-paper-layout-') as temp:
                output = Path(temp) / 'synthetic-layout'
                manifest = paper.build_report(data, output,
                                              synthetic_fixture=True)
                self.assertTrue(manifest['synthetic_layout_fixture'])
                self.assertEqual(len(manifest['file_sha256']), 7)
                self.assertTrue((output / 'EnvLoop-Full-Computer-Use-Study.pdf').is_file())
                self.assertEqual(len(list((output / 'figures').glob('*.svg'))), 4)
                search = json.loads((output / 'campaign-search-summary.json').read_text())
                self.assertEqual(len(search['campaigns']), 24)
                supplement = json.loads((output / 'family-effects-pseudonymized.json').read_text())
                self.assertEqual(len(supplement['comparisons']), 24)
                self.assertTrue(all('source_family' not in family
                                    for entry in supplement['comparisons']
                                    for family in entry['families']))
                pdf_path = output / 'EnvLoop-Full-Computer-Use-Study.pdf'
                info = subprocess.run(['pdfinfo', str(pdf_path)],
                                      check=True, capture_output=True, text=True)
                pages = int(next(line.split(':', 1)[1].strip()
                                 for line in info.stdout.splitlines()
                                 if line.startswith('Pages:')))
                self.assertGreaterEqual(pages, 4)
                page_prefix = Path(temp) / 'rendered'
                subprocess.run(['pdftoppm', '-f', '1', '-l', '1',
                                '-scale-to', '600', '-singlefile', '-png',
                                str(pdf_path), str(page_prefix)],
                               check=True, capture_output=True)
                with Image.open(page_prefix.with_suffix('.png')) as image:
                    red_pixels = sum(1 for red, green, blue in
                                     image.convert('RGB').get_flattened_data()
                                     if red > 110 and red > green * 1.7 and
                                     red > blue * 1.5)
                self.assertGreater(red_pixels, 100)
                with self.assertRaises(FileExistsError):
                    paper.build_report(data, output, synthetic_fixture=True)
        finally:
            fixture.tearDownClass()


if __name__ == '__main__':
    unittest.main()
