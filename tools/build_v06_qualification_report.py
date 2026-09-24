"""Render the evidence-bound v0.6 qualification manuscript as an English PDF.

This is a methods and task-qualification note. It deliberately does not infer
scores for the unrun 24-campaign experiment from one-task pilot receipts.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
    Table, TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/qualification-v06/EnvLoop-Computer-Use-Qualification-Report.md'
OUTPUT = ROOT / 'docs/qualification-v06/EnvLoop-Computer-Use-Qualification-Report.pdf'
PAGE = (595, 842)
BODY_WIDTH = 491
INK = colors.HexColor('#19333d')
MUTED = colors.HexColor('#566c73')
ACCENT = colors.HexColor('#087c72')
PAPER = colors.HexColor('#eef4f3')


STYLES = {
    'title': ParagraphStyle('q-title', fontName='Times-Bold', fontSize=23,
                            leading=27, textColor=INK, spaceAfter=15),
    'meta': ParagraphStyle('q-meta', fontName='Helvetica', fontSize=9,
                           leading=13, textColor=ACCENT, spaceAfter=16),
    'h1': ParagraphStyle('q-h1', fontName='Times-Bold', fontSize=14.5,
                         leading=18, textColor=INK, spaceBefore=17,
                         spaceAfter=8, keepWithNext=True),
    'body': ParagraphStyle('q-body', fontName='Times-Roman', fontSize=10.1,
                           leading=14.3, textColor=INK, spaceAfter=9,
                           allowOrphans=0, allowWidows=0),
    'caption': ParagraphStyle('q-caption', fontName='Helvetica', fontSize=8.4,
                              leading=11.5, textColor=MUTED, spaceBefore=5,
                              spaceAfter=14),
    'cell': ParagraphStyle('q-cell', fontName='Helvetica', fontSize=8.2,
                           leading=11.2, textColor=INK),
    'cellhead': ParagraphStyle('q-cellhead', fontName='Helvetica-Bold',
                               fontSize=8.2, leading=11.2, textColor=INK),
}


def inline(value: str) -> str:
    value = escape(value)
    value = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', value)
    value = re.sub(r'`([^`]+)`', r'<font name="Courier">\1</font>', value)
    value = re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)',
                   r'<link href="\2" color="#087c72">\1</link>', value)
    return value


def paragraph(value: str, style: str = 'body') -> Paragraph:
    return Paragraph(inline(value), STYLES[style])


def parse_table(block: str) -> Table:
    rows = [[value.strip() for value in line.strip().strip('|').split('|')]
            for line in block.splitlines()]
    rows = [row for row in rows if not all(re.fullmatch(r':?-{3,}:?',
                                                     cell) for cell in row)]
    if not rows or any(len(row) != len(rows[0]) for row in rows):
        raise ValueError('irregular markdown table')
    if rows[0] == ['Cell', 'Narrowest observed positive',
                   'Key missing admission evidence']:
        widths = [BODY_WIDTH * part for part in (.19, .39, .42)]
    elif rows[0] == ['Probe', 'Observed control', 'Admission boundary']:
        widths = [BODY_WIDTH * part for part in (.18, .45, .37)]
    else:
        widths = [BODY_WIDTH / len(rows[0])] * len(rows[0])
    data = [[paragraph(value, 'cellhead' if index == 0 else 'cell')
             for value in row] for index, row in enumerate(rows)]
    table = Table(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
    commands = [
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, 0), PAPER),
        ('LINEABOVE', (0, 0), (-1, 0), .8, INK),
        ('LINEBELOW', (0, 0), (-1, 0), .5, INK),
        ('LINEBELOW', (0, -1), (-1, -1), .8, INK),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]
    for row in range(1, len(rows)):
        if row % 2 == 0:
            commands.append(('BACKGROUND', (0, row), (-1, row),
                             colors.HexColor('#f9fbfb')))
    table.setStyle(TableStyle(commands))
    return table


def figure(block: str) -> KeepTogether:
    match = re.fullmatch(r'!\[(.+?)\]\((figures/[^)]+\.png)\)', block)
    if not match:
        raise ValueError('invalid figure block')
    caption, relative = match.groups()
    path = SOURCE.parent / relative
    if not path.is_file():
        raise FileNotFoundError(path)
    image = Image(str(path))
    height = BODY_WIDTH * image.imageHeight / image.imageWidth
    if height > 258:
        height = 258
    image.drawWidth = BODY_WIDTH
    image.drawHeight = height
    return KeepTogether([image, paragraph(caption, 'caption')])


def build_story(source: str) -> list:
    if re.search(r'[\u3400-\u9fff\uf900-\ufaff]', source):
        raise ValueError('non-English characters in technical manuscript')
    if '{{' in source or 'TODO' in source or 'TBD' in source:
        raise ValueError('unfinished manuscript placeholder')
    story = []
    for raw in source.split('\n\n'):
        block = raw.strip()
        if not block:
            continue
        if block == '---PAGEBREAK---':
            story.append(PageBreak())
        elif block.startswith('# '):
            story.append(paragraph(block[2:], 'title'))
        elif block.startswith('## '):
            story.append(paragraph(block[3:], 'h1'))
        elif block.startswith('!['):
            story.append(figure(block))
        elif block.startswith('|'):
            story.append(KeepTogether([parse_table(block), Spacer(1, 10)]))
        elif block.startswith('EnvLoop | Version'):
            story.append(paragraph(block, 'meta'))
        elif block.startswith('To test a different failure mode'):
            story.append(KeepTogether([paragraph(' '.join(block.splitlines()))]))
        else:
            story.append(paragraph(' '.join(block.splitlines())))
    return story


def decorate(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(ACCENT)
    canvas.setLineWidth(1)
    canvas.line(52, 803, 543, 803)
    canvas.setFont('Helvetica-Bold', 11)
    canvas.setFillColor(ACCENT)
    canvas.drawString(52, 813, 'ENVLOOP')
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(543, 815, 'COMPUTER-USE BENCHMARK / v0.6')
    canvas.line(52, 39, 543, 39)
    canvas.drawString(52, 25, 'Qualification note - no full-study results')
    canvas.drawRightString(543, 25, str(doc.page))
    canvas.restoreState()


def build(source_path: Path = SOURCE, output_path: Path = OUTPUT) -> Path:
    text = source_path.read_text(encoding='utf-8')
    story = build_story(text)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(output_path), pagesize=PAGE,
                            leftMargin=52, rightMargin=52,
                            topMargin=58, bottomMargin=55,
                            title='EnvLoop Computer-Use Benchmark: Real-Software Qualification Note',
                            author='EnvLoop', subject='v0.6 task and environment qualification')
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return output_path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--out', type=Path, default=OUTPUT)
    args = parser.parse_args()
    print(build(args.source, args.out))
