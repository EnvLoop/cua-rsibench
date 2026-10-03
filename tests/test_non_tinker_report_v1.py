"""Check report dates and public language in the actual saved PDF."""
import tempfile
import unittest
from pathlib import Path
from pypdf import PdfReader
from tools.build_non_tinker_report_v1 import build


class ReportTests(unittest.TestCase):
    def render(self, text, **kwargs):
        with tempfile.TemporaryDirectory() as folder:
            status=Path(folder)/'status.md';status.write_text(text)
            output=Path(folder)/'report.pdf'
            build(output,None,status=status,**kwargs)
            return '\n'.join(page.extract_text() for page in PdfReader(output).pages)

    def test_saved_title_and_footer_use_status_date(self):
        text=self.render('# Status\nUpdated: 3 October 2026.\n\n## Evidence\nActual build passed.\n')
        self.assertGreaterEqual(text.count('3 October 2026'),3)
        self.assertNotIn('2 October 2026',text)

    def test_explicit_date_is_preserved(self):
        text=self.render('# Status\nDated build evidence.\n',report_date='2026-10-02')
        self.assertIn('2 October 2026',text)

    def test_missing_date_and_non_english_public_source_refused(self):
        with self.assertRaisesRegex(ValueError,'dated status'):
            self.render('# Undated status\n')
        with self.assertRaisesRegex(ValueError,'English public report'):
            self.render('# Status\nUpdated: 3 October 2026.\n\u6d4b\u8bd5\n')


if __name__=='__main__':unittest.main()
