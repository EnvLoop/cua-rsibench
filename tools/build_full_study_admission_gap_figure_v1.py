"""Render a dated methods figure from public aggregate receipts only.

The bars are evaluator development controls, never agent success rates.
No private task identity or gold is read by this program.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
READINESS = 'docs/evidence/full-study-readiness-offline-complete-2026-09-27.json'
GITLAB = 'docs/evidence/gitlab-scoped-gui-progress-85-2026-09-27.json'
MAGENTO = 'docs/evidence/magento-original-cellwide-index-drift-stop-2026-09-27.json'
DESKTOP = 'docs/evidence/native-wdi-v065-final-admission-preflight-2026-09-27.json'
ODOO = 'docs/evidence/odoo-official-hidden-100-gui-audit-2026-09-25.json'
DATA_OUT = ROOT / 'docs/evidence/full-study-admission-gap-2026-09-28.json'
SVG_OUT = ROOT / 'docs/site/figures/full-study-admission-gap-2026-09-28.svg'
LABELS = (
    ('ppt', 'PowerPoint web'), ('excel', 'Excel web'),
    ('desktop', 'LibreOffice desktop'), ('odoo', 'Odoo Community'),
    ('gitlab', 'GitLab CE'), ('magento', 'Magento admin'),
)


def read(path: str) -> tuple[dict, str]:
    raw = (ROOT / path).read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def data() -> dict:
    base, h_base = read(READINESS)
    gitlab, h_gitlab = read(GITLAB)
    magento, h_magento = read(MAGENTO)
    desktop, h_desktop = read(DESKTOP)
    odoo, h_odoo = read(ODOO)
    rows = base['cells']
    if (base['schema'] != 'envloop-full-study-readiness-figure-data-v1'
            or [(r['cell'], r['label']) for r in rows] != list(LABELS)
            or any(r['offline_final'] != 100 or r['official_admitted'] != 0
                   for r in rows)
            or gitlab['cumulative']['candidate_final_total'] != 100
            or gitlab['cumulative']['development_gui_trio_passed'] != 81
            or gitlab['cumulative']['individually_attempted_ids'] != 85
            or gitlab['official_final_admitted'] != 0
            or magento['candidate_gui_controls_passed_before_stop'] != 35
            or magento['official_final_admitted'] != 0
            or desktop['historical_gui_trios_passed'] != 100
            or desktop['official_full_study_admitted_final_count'] != 0
            or odoo['cases_with_all_per_id_controls'] != 100
            or odoo['official_final_tasks_admitted'] != 0):
        raise ValueError('public source receipts differ from dated figure shape')
    history = {'ppt': 0, 'excel': 0, 'desktop': 100,
               'odoo': 100, 'gitlab': 81, 'magento': 35}
    result = {
        'schema': 'envloop-full-study-admission-gap-figure-v1',
        'date': '2026-09-28',
        'scope': 'methods_progress_not_model_results',
        'cell_rows': [{
            'cell': key, 'label': label, 'offline_final_candidates': 100,
            'historical_development_gui_controls': history[key],
            'fresh_v066_final_gui_trios': 0, 'official_final_admissions': 0,
        } for key, label in LABELS],
        'offline_candidate_total': 600,
        'historical_development_gui_total': sum(history.values()),
        'fresh_v066_final_gui_trio_total': 0,
        'official_final_admission_total': 0,
        'researcher_campaigns_completed': 0,
        'source_receipt_sha256': {
            READINESS: h_base, GITLAB: h_gitlab, MAGENTO: h_magento,
            DESKTOP: h_desktop, ODOO: h_odoo,
        },
        'warning': ('Historical evaluator GUI controls use different action '
                    'and runtime versions; these bars are not comparable '
                    'agent success rates or current-profile admission proofs.'),
    }
    return result


def svg(result: dict) -> str:
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 690" '
        'role="img" aria-label="Six-cell benchmark admission progress">',
        '<rect width="1120" height="690" fill="#f8f9f6"/>',
        '<text x="55" y="64" font-family="Arial,sans-serif" font-size="30" '
        'font-weight="700" fill="#17363d">From candidate inventory to admitted exam</text>',
        '<text x="55" y="94" font-family="Arial,sans-serif" font-size="16" '
        'fill="#53686e">28 September 2026 · six original-software cells · methods progress</text>',
        '<rect x="55" y="119" width="1010" height="74" rx="10" fill="#e9f0ed"/>',
        '<text x="76" y="149" font-family="Arial,sans-serif" font-size="17" '
        'font-weight="700" fill="#17363d">600 offline candidates</text>',
        '<text x="76" y="176" font-family="Arial,sans-serif" font-size="15" '
        'fill="#53686e">316 historical evaluator GUI controls · 0 current v0.6.6 final trios '
        '· 0 official admissions · 0/24 researcher campaigns</text>',
    ]
    x, width = 331, 650
    for tick in (0, 25, 50, 75, 100):
        tx = x + width * tick / 100
        parts.append(f'<line x1="{tx:.1f}" y1="225" x2="{tx:.1f}" y2="578" '
                     'stroke="#d8dfdc" stroke-width="1"/>')
        parts.append(f'<text x="{tx:.1f}" y="215" text-anchor="middle" '
                     'font-family="Arial,sans-serif" font-size="13" fill="#718188">'
                     f'{tick}</text>')
    for index, row in enumerate(result['cell_rows']):
        y = 250 + index * 54
        label = escape(row['label'])
        amount = row['historical_development_gui_controls']
        parts.append(f'<text x="55" y="{y + 20}" font-family="Arial,sans-serif" '
                     f'font-size="17" fill="#17363d">{label}</text>')
        parts.append(f'<rect x="{x}" y="{y}" width="{width}" height="28" rx="5" '
                     'fill="#dce3df"/>')
        if amount:
            parts.append(f'<rect x="{x}" y="{y}" width="{width * amount / 100:.1f}" '
                         'height="28" rx="5" fill="#307a87"/>')
        parts.append(f'<text x="1004" y="{y + 20}" font-family="Arial,sans-serif" '
                     f'font-size="16" fill="#17363d">{amount}/100</text>')
    parts.extend([
        '<rect x="55" y="600" width="16" height="16" rx="2" fill="#dce3df"/>',
        '<text x="79" y="613" font-family="Arial,sans-serif" font-size="13" '
        'fill="#53686e">Constructed offline candidate</text>',
        '<rect x="358" y="600" width="16" height="16" rx="2" fill="#307a87"/>',
        '<text x="382" y="613" font-family="Arial,sans-serif" font-size="13" '
        'fill="#53686e">Historical evaluator GUI control</text>',
        '<text x="55" y="643" font-family="Arial,sans-serif" font-size="13" '
        'fill="#8a5a2b">Heterogeneous development controls; no bar is a model score '
        'or a v0.6.6 admission proof.</text>',
        '<text x="55" y="668" font-family="Arial,sans-serif" font-size="12" '
        'fill="#718188">Source hashes and dated counts: docs/evidence/'
        'full-study-admission-gap-2026-09-28.json</text>',
        '</svg>',
    ])
    return '\n'.join(parts) + '\n'


def main() -> None:
    value = data()
    DATA_OUT.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')
    SVG_OUT.write_text(svg(value))
    print(json.dumps({'offline_candidates': 600,
                      'historical_gui_controls': value['historical_development_gui_total'],
                      'official_admitted': 0, 'svg': str(SVG_OUT)}))


if __name__ == '__main__':
    main()
