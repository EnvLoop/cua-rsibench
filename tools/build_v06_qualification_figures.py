"""Build evidence-bound raster figures for the v0.6 qualification note."""

from __future__ import annotations

import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'docs/evidence/v0.6-qualification-report-data.json'
OUT = ROOT / 'docs/qualification-v06/figures'
FONT = next(str(path) for path in (
    Path('/System/Library/Fonts/Supplemental/Arial.ttf'),
    Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
) if path.exists())
FONT_BOLD = next(str(path) for path in (
    Path('/System/Library/Fonts/Supplemental/Arial Bold.ttf'),
    Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
) if path.exists())
BG = '#f7f8f4'
INK = '#19333d'
MUTED = '#657a7d'
TEAL = '#087c72'
TEAL_LIGHT = '#d8eeea'
AMBER = '#b7672a'
AMBER_LIGHT = '#f8eadc'
LINE = '#d7e1dd'
WHITE = '#ffffff'


def font(size: int, bold: bool = False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT, size)


def width(draw, value: str, face) -> int:
    left, _, right, _ = draw.textbbox((0, 0), value, font=face)
    return right - left


def wrap(draw, value: str, face, maximum: int) -> list[str]:
    words = value.split()
    result: list[str] = []
    current = ''
    for word in words:
        proposed = (current + ' ' + word).strip()
        if current and width(draw, proposed, face) > maximum:
            result.append(current)
            current = word
        else:
            current = proposed
    if current:
        result.append(current)
    return result


def text(draw, xy, value, *, size=27, fill=INK, bold=False, max_width=None,
         line_height=None):
    face = font(size, bold)
    lines = wrap(draw, value, face, max_width) if max_width else [value]
    step = line_height or int(size * 1.36)
    x, y = xy
    for line in lines:
        draw.text((x, y), line, font=face, fill=fill)
        y += step
    return y


def base(name: str, title: str, subtitle: str, w: int, h: int):
    image = Image.new('RGB', (w, h), BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 12, h), fill=TEAL)
    text(draw, (56, 33), title, size=38, bold=True)
    text(draw, (57, 88), subtitle, size=23, fill=MUTED)
    return image, draw


def save(image: Image.Image, name: str):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    image.save(path, format='PNG', optimize=True)
    return path


def pipeline(data: dict):
    assert data['merged_snapshot_progress']['completed_researcher_campaigns'] == 0
    image, draw = base('pipeline', 'Fixed research, separate evaluation',
                       'Declared v0.6 architecture - not a completed run', 1600, 492)
    labels = [
        ('Researcher', 'Data hypotheses and verified task experience'),
        ('Tinker', 'Fixed Qwen3.8-27B LoRA and sampler'),
        ('GUI actor', 'Screenshot / action contract in real software'),
        ('Evaluator', 'Saved state, negatives, reset, hidden final'),
    ]
    left, gap, card_width = 55, 30, 350
    for index, (heading, description) in enumerate(labels):
        x = left + index * (card_width + gap)
        draw.rounded_rectangle((x, 163, x + card_width, 329), radius=16,
                               fill=WHITE, outline=LINE, width=2)
        draw.rectangle((x, 163, x + card_width, 173), fill=TEAL)
        text(draw, (x + 22, 195), f'{index + 1:02d}  {heading}', size=29, bold=True)
        text(draw, (x + 22, 244), description, size=24, fill=MUTED,
             max_width=card_width - 44)
        if index < len(labels) - 1:
            px = x + card_width + 9
            draw.line((px, 245, px + 14, 245), fill=TEAL, width=5)
            draw.polygon([(px + 14, 237), (px + 28, 245), (px + 14, 253)],
                         fill=TEAL)
    draw.rounded_rectangle((55, 365, 755, 451), radius=13,
                           fill=TEAL_LIGHT)
    text(draw, (79, 382), 'Training: separate permitted sources', size=26,
         fill=TEAL, bold=True)
    draw.rounded_rectangle((785, 365, 1545, 451), radius=13,
                           fill=AMBER_LIGHT)
    text(draw, (809, 382), 'WorkArena instances: evaluation only', size=26,
         fill=AMBER, bold=True)
    return save(image, 'pipeline.png')


def readiness(data: dict):
    rows = data['application_qualification']
    if len(rows) != 6 or any(row['qualified_final_tasks'] != 0 for row in rows):
        raise ValueError('readiness figure requires the zero-final snapshot')
    image, draw = base('readiness', 'Qualification is narrower than inventory',
                       'Different source-task grains; colored marks show only the stated local proof',
                       1600, 684)
    columns = ['Real GUI', 'Negative', 'Readback', 'Reset', 'Student', '100 final']
    x0, colw = 567, 158
    for index, heading in enumerate(columns):
        x = x0 + index * colw
        text(draw, (x, 157), heading, size=22, bold=True,
             max_width=colw - 10)
    names = [
        ('PowerPoint web', 120, ['yes', 'limited', 'limited', 'no', 'no', 'no']),
        ('Excel web', 200, ['yes', 'limited', 'yes', 'no', 'no', 'no']),
        ('Native desktop', 369, ['limited', 'no', 'limited', 'limited', 'no', 'no']),
        ('ServiceNow', 175, ['no', 'no', 'no', 'no', 'no', 'no']),
        ('GitLab', 180, ['yes', 'yes', 'yes', 'limited', 'no', 'no']),
        ('Magento', 182, ['yes', 'yes', 'yes', 'limited', 'limited', 'no']),
    ]
    expected = {row['cell']: row['candidate_inventory'] for row in rows}
    canonical = {'PowerPoint for the web': 120,
                 'Microsoft Excel for the web': 200,
                 'Native desktop applications': 369,
                 'ServiceNow compositional work': 175,
                 'GitLab project operations': 180,
                 'Magento administration': 182}
    if expected != canonical:
        raise ValueError('source inventory changed; review readiness figure')
    for index, (name, count, states) in enumerate(names):
        y = 210 + index * 67
        if index % 2 == 0:
            draw.rounded_rectangle((42, y - 4, 1559, y + 57), radius=8,
                                   fill=WHITE)
        text(draw, (61, y + 9), name, size=27, bold=True)
        text(draw, (372, y + 12), f'{count} source', size=22, fill=MUTED)
        for col, state in enumerate(states):
            x = x0 + col * colw + 24
            fill = TEAL if state == 'yes' else AMBER if state == 'limited' else LINE
            draw.rounded_rectangle((x, y + 5, x + 88, y + 39), radius=17,
                                   fill=fill)
            label = 'YES' if state == 'yes' else 'LIMIT' if state == 'limited' else '-'
            face = font(17, True)
            draw.text((x + (88 - width(draw, label, face)) / 2, y + 12),
                      label, font=face, fill=WHITE if state != 'no' else MUTED)
    text(draw, (58, 627), 'No colored mark is a completed 100-task cell result.',
         size=22, fill=MUTED)
    return save(image, 'readiness.png')


def excel_funnel(data: dict):
    spec = next(row for row in data['suggested_figures']
                if row['id'] == 'hard_excel_source_funnel')
    tasks = spec['task_instance_series']
    families = spec['base_workbook_family_series']
    assert [row['count'] for row in tasks] == [200, 100, 0]
    assert [row['count'] for row in families] == [30, 22, 15]
    image, draw = base('excel-funnel', 'Hard Excel narrows before GUI admission',
                       'Task instances and base workbook families are separate units',
                       1600, 567)
    for x, heading, rows, maximum in (
        (60, 'TASK INSTANCES', tasks, 200),
        (830, 'BASE WORKBOOK FAMILIES', families, 30),
    ):
        text(draw, (x, 157), heading, size=24, bold=True, fill=TEAL)
        for index, row in enumerate(rows):
            y = 209 + index * 104
            text(draw, (x, y), row['stage'], size=22,
                 max_width=675)
            length = 580 * row['count'] / maximum
            draw.rounded_rectangle((x, y + 40, x + 590, y + 67), radius=13,
                                   fill=LINE)
            if length:
                draw.rounded_rectangle((x, y + 40, x + max(27, length), y + 67),
                                       radius=13, fill=TEAL if index < 2 else AMBER)
            text(draw, (x + 612, y + 39), str(row['count']), size=25, bold=True)
    text(draw, (62, 525), 'Offline structural selection is not task difficulty or software compatibility.',
         size=21, fill=MUTED)
    return save(image, 'excel-source-funnel.png')


def excel_audit(data: dict):
    spec = next(row for row in data['suggested_figures']
                if row['id'] == 'sec_development_control')
    bars = spec['bars']
    assert [(row['repaired_faults'], row['total_faults'], row['full_pass'])
            for row in bars] == [(1, 9, False), (9, 9, True)]
    image, draw = base('excel-audit', 'One blind audit, two GUI controls',
                       'SEC-backed public development fixture - human operated, zero model calls',
                       1600, 489)
    x0, maximum = 520, 875
    for index, (label, count, passed) in enumerate((
        ('One-edit control', 1, False), ('Full repair', 9, True))):
        y = 178 + index * 116
        text(draw, (61, y + 13), label, size=31, bold=True)
        draw.rounded_rectangle((x0, y + 1, x0 + maximum, y + 62),
                               radius=24, fill=LINE)
        draw.rounded_rectangle((x0, y + 1, x0 + maximum * count / 9, y + 62),
                               radius=24, fill=TEAL if passed else AMBER)
        text(draw, (1415, y + 13), f'{count}/9', size=35,
             fill=TEAL if passed else AMBER, bold=True)
    draw.line((60, 421, 1540, 421), fill=LINE, width=2)
    text(draw, (62, 438), 'Full downloaded workbook: 114/114 targets and two evaluator-side replays passed.',
         size=23, fill=MUTED)
    return save(image, 'excel-audit.png')


def magento_disagreement(data: dict):
    spec = next(row for row in data['suggested_figures']
                if row['id'] == 'magento_network_state_disagreement')
    if (spec['official_network_score'] != 1.0 or
            spec['requested_price_changes'] != 5 or
            spec['persisted_price_changes'] != 0 or
            spec['admission'] != 'rejected_unscored'):
        raise ValueError('Magento rejection evidence changed')
    image, draw = base('magento-state-gap', 'A score is not a saved state',
                       'One isolated Magento clone - task 777 rejected before admission',
                       1600, 521)
    cards = [
        (55, 'PUBLISHED HAR EVALUATOR', '1.0',
         'Five product-save POSTs returned 302', TEAL_LIGHT, TEAL),
        (814, 'INDEPENDENT SQL READBACK', '0 / 5',
         'Requested price changes persisted', AMBER_LIGHT, AMBER),
    ]
    for x, heading, value, note, background, color in cards:
        draw.rounded_rectangle((x, 158, x + 730, 359), radius=18,
                               fill=background)
        text(draw, (x + 27, 184), heading, size=23, bold=True, fill=color)
        text(draw, (x + 27, 220), value, size=76, bold=True, fill=INK)
        text(draw, (x + 29, 316), note, size=25, fill=MUTED)
    draw.rounded_rectangle((55, 397, 1544, 476), radius=12,
                           fill='#fff0ed')
    text(draw, (79, 412), 'Visible save error: "The stock item was unable to be saved."',
         size=26, bold=True, fill='#a34837')
    return save(image, 'magento-state-gap.png')


def build():
    data = json.loads(DATA.read_text())
    if ('No full-scale researcher comparison' not in data['result_status'] or
            data['merged_snapshot_progress']['admitted_official_final_task_identities'] != 0):
        raise ValueError('unexpected result status')
    return [pipeline(data), readiness(data), excel_funnel(data),
            excel_audit(data), magento_disagreement(data)]


if __name__ == '__main__':
    for path in build():
        print(path)
