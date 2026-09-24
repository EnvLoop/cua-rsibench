"""Build the self-contained v0.6 qualification explorer from audited JSON."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'docs/evidence/v0.6-qualification-report-data.json'
TEMPLATE = ROOT / 'tools/v06_qualification_site_template.html'
OUTPUT = ROOT / 'docs/qualification-v06/index.html'


def build() -> Path:
    data = json.loads(DATA.read_text())
    if data['schema'] != 'cua-rsibench-v0.6-qualification-report-data-v1':
        raise ValueError('unexpected qualification data schema')
    progress = data['merged_snapshot_progress']
    if any(progress[key] != 0 for key in
           ('frozen_100_task_cells', 'admitted_official_final_task_identities',
            'completed_researcher_campaigns', 'completed_full_scale_official_trials')):
        raise ValueError('publication snapshot no longer has zero official outcomes')
    if len(data['application_qualification']) != 6:
        raise ValueError('six application cells required')
    for key, source in data['sources'].items():
        path = ROOT / source['path']
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != source['sha256']:
            raise ValueError('source bytes changed: ' + key)
    embedded = json.dumps(data, ensure_ascii=True, separators=(',', ':'))
    embedded = embedded.replace('</', '<\\/')
    template = TEMPLATE.read_text()
    if template.count('{{DATA_JSON}}') != 1:
        raise ValueError('site template data marker missing or repeated')
    html = template.replace('{{DATA_JSON}}', embedded)
    if re.search(r'[\u3400-\u9fff\uf900-\ufaff]', html):
        raise ValueError('non-English characters in public HTML')
    if re.search(r'@outlook\.com|(?:sk-|tml-|e2b_)[A-Za-z0-9]{20,}|onedrive\.live\.com/personal/',
                 html, re.I):
        raise ValueError('possible private account or credential in public HTML')
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html)
    return OUTPUT


if __name__ == '__main__':
    print(build())
