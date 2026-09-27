"""Draw an evidence-bound six-cell preparation chart, never a result figure."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from xml.sax.saxutils import escape


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    value = json.loads(raw)
    require(isinstance(value, dict), f'{path}: JSON object required')
    return value, hashlib.sha256(raw).hexdigest()


def chart(rows: list[dict]) -> str:
    width, height = 1210, 555
    left, x0, bar_width = 32, 284, 660
    colors = {'inventory': '#CED8E4', 'control': '#3B72B8'}
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" '
           f'viewBox="0 0 {width} {height}" role="img" '
           f'aria-label="Six-cell benchmark preparation, not model results">',
           '<rect width="100%" height="100%" fill="#FFFFFF"/>',
           '<text x="32" y="46" font-family="Arial,sans-serif" '
           'font-weight="700" font-size="26" fill="#10243A">'
           'Six-cell benchmark preparation</text>',
           '<text x="32" y="73" font-family="Arial,sans-serif" '
           'font-size="14" fill="#42576E">'
           'Dated aggregate evidence • 27 Sep 2026 • 100 proposed final tasks per cell'
           '</text>',
           '<rect x="285" y="95" width="18" height="12" fill="#CED8E4"/>',
           '<text x="310" y="106" font-family="Arial,sans-serif" '
           'font-size="13" fill="#42576E">Offline final candidates</text>',
           '<rect x="531" y="95" width="18" height="12" fill="#3B72B8"/>',
           '<text x="556" y="106" font-family="Arial,sans-serif" '
           'font-size="13" fill="#42576E">Development GUI controls</text>',
           '<text x="970" y="106" font-family="Arial,sans-serif" '
           'font-size="13" fill="#42576E">Official admitted</text>']
    for tick in (0, 25, 50, 75, 100):
        x = x0 + bar_width * tick / 100
        out.append(f'<line x1="{x:.1f}" y1="129" x2="{x:.1f}" '
                   'y2="444" stroke="#E5EBF1" stroke-width="1"/>')
        out.append(f'<text x="{x:.1f}" y="124" text-anchor="middle" '
                   'font-family="Arial,sans-serif" font-size="12" '
                   f'fill="#61758B">{tick}</text>')
    for index, row in enumerate(rows):
        y = 159 + index * 51
        label = escape(row['label'])
        inventory, control, official = (row[key] for key in
                                        ('offline_final', 'development_gui',
                                         'official_admitted'))
        out.append(f'<text x="{left}" y="{y + 19}" '
                   'font-family="Arial,sans-serif" font-size="16" '
                   f'fill="#10243A">{label}</text>')
        out.append(f'<rect x="{x0}" y="{y}" width="{bar_width}" height="26" '
                   'rx="4" fill="#F1F4F8"/>')
        out.append(f'<rect x="{x0}" y="{y}" '
                   f'width="{bar_width * inventory / 100:.1f}" height="26" '
                   f'rx="4" fill="{colors["inventory"]}"/>')
        if control:
            out.append(f'<rect x="{x0}" y="{y + 7}" '
                       f'width="{bar_width * control / 100:.1f}" height="12" '
                       f'rx="3" fill="{colors["control"]}"/>')
        out.append(f'<text x="965" y="{y + 19}" '
                   'font-family="Arial,sans-serif" font-size="14" '
                   f'fill="#263D55">{inventory} / {control}</text>')
        out.append(f'<text x="1118" y="{y + 19}" '
                   'font-family="Arial,sans-serif" font-size="16" '
                   f'font-weight="700" fill="#B04B38">{official}</text>')
    out.extend([
        '<line x1="32" y1="465" x2="1178" y2="465" stroke="#DCE5ED"/>',
        '<text x="32" y="492" font-family="Arial,sans-serif" '
        'font-size="13" fill="#42576E">'
        'Development controls differ by application and may include quarantined '
        'candidate families. They are not comparable success rates.</text>',
        '<text x="32" y="516" font-family="Arial,sans-serif" '
        'font-size="13" fill="#42576E">'
        'No cell has a ratified 100-task official denominator; '
        'no 24-campaign model result is represented here.</text>',
        '</svg>'])
    return '\n'.join(out) + '\n'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for cell in ('ppt', 'excel', 'desktop', 'odoo', 'gitlab', 'magento'):
        parser.add_argument('--' + cell, type=Path, required=True)
    parser.add_argument('--out-json', type=Path, required=True)
    parser.add_argument('--out-svg', type=Path, required=True)
    args = parser.parse_args()
    require(not args.out_json.exists() and not args.out_svg.exists(),
            'fresh outputs required')
    sources = {name: load(getattr(args, name)) for name in
               ('ppt', 'excel', 'desktop', 'odoo', 'gitlab', 'magento')}
    ppt, excel, desktop, odoo, gitlab, magento = (
        sources[name][0] for name in
        ('ppt', 'excel', 'desktop', 'odoo', 'gitlab', 'magento'))
    require(ppt['schema'] == 'envloop-ppt-wdi-seven-reserve-revision-public-v1'
            and excel['offline_candidates']['selection'] == 20
            and desktop['final_gui_control_passed_count'] == 100
            and odoo['all_per_id_gui_positive_negative_reset_controls_passed']
            is True
            and gitlab['cumulative']['candidate_final_total'] == 100
            and magento['total_final_candidate_ids'] == 100,
            'readiness sources changed')
    rows = [
        {'cell': 'ppt', 'label': 'PowerPoint web',
         'offline_final': ppt['split_candidate_counts']['final_candidate'],
         'development_gui': ppt['office_web_gui_admitted'],
         'official_admitted': ppt['official_final_tasks_admitted']},
        {'cell': 'excel', 'label': 'Excel web',
         'offline_final': excel['offline_candidates']['final'],
         'development_gui': excel['structurally_qualified_private_split_tasks'],
         'official_admitted':
             excel['microsoft_excel_web_official_hidden_final_admissions']},
        {'cell': 'desktop', 'label': 'LibreOffice desktop',
         'offline_final': desktop['candidate_counts']['final_candidate'],
         'development_gui': desktop['final_gui_control_passed_count'],
         'official_admitted': desktop['official_full_study_admitted_final_count']},
        {'cell': 'odoo', 'label': 'Odoo Community',
         'offline_final': odoo['candidate_counts']['official_hidden'],
         'development_gui': 100,
         'official_admitted': odoo['official_final_tasks_admitted']},
        {'cell': 'gitlab', 'label': 'GitLab CE',
         'offline_final': gitlab['cumulative']['candidate_final_total'],
         'development_gui': gitlab['cumulative']['development_gui_trio_passed'],
         'official_admitted': gitlab['cumulative']['official_final_admitted']},
        {'cell': 'magento', 'label': 'Magento admin',
         'offline_final': magento['total_final_candidate_ids'],
         'development_gui':
             magento['distinct_final_candidate_ids_gui_calibrated'],
         'official_admitted': magento['official_final_admitted']},
    ]
    require(all(0 <= row['official_admitted'] <=
                row['development_gui'] <= row['offline_final'] <= 100
                for row in rows) and
            all(row['official_admitted'] == 0 for row in rows),
            'a proposed-only methods figure cannot show model results')
    manifest = {'schema': 'envloop-full-study-readiness-figure-data-v1',
                'status': 'methods_preparation_not_model_results',
                'date': '2026-09-27', 'proposed_final_per_cell': 100,
                'cells': rows,
                'source_receipt_sha256': {name: item[1]
                                          for name, item in sources.items()},
                'official_campaigns': 0,
                'development_controls_not_comparable': True}
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_svg.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    args.out_svg.write_text(chart(rows))
    print(json.dumps({'status': manifest['status'],
                      'cell_count': len(rows), 'official_admissions': 0,
                      'svg': str(args.out_svg)}, sort_keys=True))


if __name__ == '__main__':
    main()
