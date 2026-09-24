"""Validate the public v0.6 methods note before any repository/release push."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from PIL import Image
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'docs/qualification-v06'
DATA = ROOT / 'docs/evidence/v0.6-qualification-report-data.json'
QA = REPORT / 'publication-qa.json'
ASSETS = [
    REPORT / 'EnvLoop-Computer-Use-Qualification-Report.md',
    REPORT / 'EnvLoop-Computer-Use-Qualification-Report.pdf',
    REPORT / 'index.html',
    *(REPORT / 'figures' / name for name in
      ('pipeline.png', 'readiness.png', 'excel-source-funnel.png',
       'excel-audit.png', 'magento-state-gap.png')),
    DATA,
    ROOT / 'docs/evidence/workarena-access-request-2026-09-24.json',
]
SENSITIVE = {
    'private_email': r'@outlook\.com',
    'credential_shape': r'(?:sk-|tml-|e2b_)[A-Za-z0-9]{20,}',
    'private_document_link': r'(?:onedrive\.live\.com|microsoftpersonalcontent\.com)/personal/',
    'non_english_han': r'[\u3400-\u9fff\uf900-\ufaff]',
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(*, visually_reviewed_pages: int | None = None,
             interactive_site_checked: bool = False) -> dict:
    data = json.loads(DATA.read_text())
    progress = data['merged_snapshot_progress']
    assert data['language'] == 'en'
    assert all(progress[key] == 0 for key in
               ('frozen_100_task_cells', 'admitted_official_final_task_identities',
                'completed_researcher_campaigns', 'completed_full_scale_official_trials'))
    assert len(data['application_qualification']) == 6
    for name, item in data['sources'].items():
        path = ROOT / item['path']
        if not path.is_file() or sha(path) != item['sha256']:
            raise ValueError('source drift: ' + name)
    for path in ASSETS:
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError('missing or empty release asset: ' + str(path))

    for path in (ASSETS[0], ASSETS[2], DATA, ASSETS[-1]):
        value = path.read_text(errors='replace')
        for label, pattern in SENSITIVE.items():
            if re.search(pattern, value, re.I):
                raise ValueError(label + ' in ' + str(path))
        if '{{' in value or '---PAGEBREAK---' in value and path.suffix != '.md':
            raise ValueError('unrendered template marker: ' + str(path))

    reader = PdfReader(str(ASSETS[1]))
    pages = len(reader.pages)
    if pages < 4 or pages > 10:
        raise ValueError('unexpected PDF page count: ' + str(pages))
    if visually_reviewed_pages is not None and visually_reviewed_pages != pages:
        raise ValueError('visual review count does not cover all PDF pages')
    extracted = '\n'.join(page.extract_text() or '' for page in reader.pages)
    for needle in ('Qualification Note', '0/24', '0/600', '114/114',
                   'Figure 1.', 'Figure 2.', 'Figure 3.', 'Figure 4.',
                   'Figure 5.'):
        if needle not in extracted:
            raise ValueError('missing PDF content: ' + needle)
    for label, pattern in SENSITIVE.items():
        if re.search(pattern, extracted, re.I):
            raise ValueError(label + ' in PDF text')
    if '{{' in extracted or '---PAGEBREAK---' in extracted:
        raise ValueError('unrendered PDF marker')

    dimensions = {}
    for path in ASSETS[3:8]:
        with Image.open(path) as image:
            if image.width < 1200 or image.height < 350:
                raise ValueError('figure too small: ' + str(path))
            dimensions[path.name] = [image.width, image.height]
    html = ASSETS[2].read_text()
    if html.count('id="qualificationData"') != 1:
        raise ValueError('embedded site data missing')
    if not all(value in html for value in
               ('0 / 24', '0 / 600', 'technical PDF', 'surfaceButtons')):
        raise ValueError('public site incomplete')
    if 'localhost' in html or '127.0.0.1' in html:
        raise ValueError('localhost URL in published HTML')
    result = {
        'schema': 'cua-v06-qualification-publication-qa-v1',
        'report_type': 'qualification_note_not_full_scale_results',
        'pdf_pages': pages,
        'all_pdf_pages_visually_reviewed': visually_reviewed_pages == pages,
        'interactive_site_checked_in_browser': interactive_site_checked,
        'evidence_registry_sources_verified': len(data['sources']),
        'candidate_cells': len(data['application_qualification']),
        'official_campaigns_completed': 0,
        'official_final_instances_completed': 0,
        'figure_dimensions': dimensions,
        'assets_sha256': {str(path.relative_to(ROOT)): sha(path) for path in ASSETS},
        'privacy_patterns_passed': True,
        'remote_pages_fetchback_verified': False,
        'release_assets_fetchback_verified': False,
    }
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--visually-reviewed-pages', type=int)
    parser.add_argument('--interactive-site-checked', action='store_true')
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    result = validate(visually_reviewed_pages=args.visually_reviewed_pages,
                      interactive_site_checked=args.interactive_site_checked)
    if args.write:
        QA.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({key: result[key] for key in
                      ('pdf_pages', 'all_pdf_pages_visually_reviewed',
                       'evidence_registry_sources_verified', 'privacy_patterns_passed')}))
