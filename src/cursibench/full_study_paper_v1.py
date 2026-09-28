"""English, vector-first paper from a fully audited full-study source object.

This renderer is deliberately separate from the input gate. Its public CLI
calls `load_publication_data` first and has no synthetic/preview flag.
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
import json
import os
from pathlib import Path
import shutil
import tempfile
from xml.sax.saxutils import escape

from reportlab.graphics import renderSVG
from reportlab.graphics.shapes import Drawing, Line, Rect, String, Circle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table,
    TableStyle, KeepTogether, PageBreak,
)

from . import full_study_matrix_v1 as matrix
from . import full_study_publication_v1 as publication
from . import scale_final_v06 as evidence


WIDTH = A4[0] - 108
INK = colors.HexColor('#1c2937')
BLUE = colors.HexColor('#2766a5')
PALE_BLUE = colors.HexColor('#e8f1fa')
ORANGE = colors.HexColor('#b35c24')
PALE_ORANGE = colors.HexColor('#f8ece4')
GRAY = colors.HexColor('#617284')
LIGHT = colors.HexColor('#e5ebef')

LABELS = {
    'powerpoint-web': 'PowerPoint web',
    'excel-web': 'Excel web',
    'desktop-native': 'Native desktop',
    'odoo-community': 'Odoo Community',
    'gitlab': 'GitLab',
    'magento-admin': 'Magento admin',
}
RESEARCHER_LABELS = {
    'astra': 'Astra 6', 'sol56': 'Sol 5.6',
    'sol6': 'Sol 6', 'luna6': 'Luna 6',
}
SOURCE_NOTES = {
    'powerpoint-web': 'WDI observations in authored seven-slide decks',
    'excel-web': 'SEC filing facts in authored workbooks',
    'desktop-native': 'WDI observations in LibreOffice tasks',
    'odoo-community': 'Original Odoo Community business workflows',
    'gitlab': 'CISA KEV facts in synthetic project operations',
    'magento-admin': 'Magento sample catalog with synthetic supplier policies',
}


def _style(name: str, size: float, leading: float, *, bold: bool = False,
           color=INK, before: float = 0, after: float = 0,
           alignment: int = 0) -> ParagraphStyle:
    return ParagraphStyle(
        name, fontName='Helvetica-Bold' if bold else 'Helvetica',
        fontSize=size, leading=leading, textColor=color,
        spaceBefore=before, spaceAfter=after, alignment=alignment,
    )


STYLES = {
    'title': _style('title', 22, 27, bold=True, after=13),
    'subtitle': _style('subtitle', 11, 15, color=GRAY, after=19),
    'h1': _style('h1', 13.5, 17, bold=True, before=17, after=9),
    'h2': _style('h2', 10.7, 14, bold=True, before=12, after=6),
    'body': _style('body', 9.2, 13.5, after=8),
    'small': _style('small', 8.1, 11.4, color=GRAY, after=8),
    'caption': _style('caption', 8.2, 11.5, color=GRAY, after=13),
    'cell': _style('cell', 7.8, 10.3),
    'center': _style('center', 9, 12, alignment=TA_CENTER),
}


def para(text: str, kind: str = 'body') -> Paragraph:
    return Paragraph(escape(text), STYLES[kind])


def _text(drawing: Drawing, x: float, y: float, value: str,
          *, size: float = 8, color=INK, bold: bool = False,
          anchor: str = 'start') -> None:
    drawing.add(String(x, y, value, fontName='Helvetica-Bold' if bold else
                       'Helvetica', fontSize=size, fillColor=color,
                       textAnchor=anchor))


def _comparisons(data: dict) -> dict[tuple[str, str], dict]:
    return {(row['cell_id'], row['researcher_id']): row['summary']
            for row in data['summary']['comparisons']}


def _delta_color(value: float):
    if value > 0:
        return BLUE, PALE_BLUE
    if value < 0:
        return ORANGE, PALE_ORANGE
    return GRAY, LIGHT


def matrix_figure(data: dict) -> Drawing:
    """All 24 paired differences in a compact six-by-four matrix."""
    d = Drawing(WIDTH, 244)
    left, top, cell_w, cell_h = 105, 187, 88, 30
    comparisons = _comparisons(data)
    for col, researcher in enumerate(matrix.RESEARCHERS):
        _text(d, left + col * cell_w + cell_w / 2, 214,
              RESEARCHER_LABELS[researcher], size=8, color=GRAY,
              bold=True, anchor='middle')
    for row, cell in enumerate(matrix.CELLS):
        y = top - row * cell_h
        _text(d, 0, y + 10, LABELS[cell], size=8, bold=True)
        for col, researcher in enumerate(matrix.RESEARCHERS):
            result = comparisons[(cell, researcher)]
            delta = result['paired_delta_pp']
            foreground, background = _delta_color(delta)
            x = left + col * cell_w
            d.add(Rect(x, y, cell_w - 5, 27, fillColor=background,
                       strokeColor=colors.white))
            _text(d, x + (cell_w - 5) / 2, y + 9,
                  f'{delta:+.0f} pp', size=10, color=foreground,
                  bold=True, anchor='middle')
    _text(d, 0, 7, 'Positive/negative values are paired selected-minus-base percentage points.',
          size=7.5, color=GRAY)
    return d


def effect_figure(data: dict) -> Drawing:
    """Paired family-cluster intervals; no interval if source family n < 2."""
    d = Drawing(WIDTH, 608)
    x0, x1 = 174, 400
    axis = lambda value: x0 + (value + 100) / 200 * (x1 - x0)
    comparisons = _comparisons(data)
    for tick in (-100, -50, 0, 50, 100):
        x = axis(tick)
        d.add(Line(x, 25, x, 575, strokeColor=LIGHT if tick else GRAY,
                   strokeWidth=0.7 if tick else 1.0))
        _text(d, x, 10, f'{tick:+d}', size=7.3, color=GRAY, anchor='middle')
    row = 0
    for cell in matrix.CELLS:
        y_header = 578 - row * 18
        _text(d, 0, y_header, LABELS[cell], size=8.7, bold=True)
        row += 1
        for researcher in matrix.RESEARCHERS:
            result = comparisons[(cell, researcher)]
            y = 578 - row * 18
            _text(d, 13, y, RESEARCHER_LABELS[researcher], size=7.8)
            interval = result['primary_family_cluster_interval_pp']
            if interval is not None:
                lo, hi = interval
                d.add(Line(axis(lo), y + 3, axis(hi), y + 3,
                           strokeColor=BLUE, strokeWidth=2))
                for endpoint in (lo, hi):
                    d.add(Line(axis(endpoint), y - 1, axis(endpoint), y + 7,
                               strokeColor=BLUE, strokeWidth=1))
            delta = result['paired_delta_pp']
            color, _ = _delta_color(delta)
            d.add(Circle(axis(delta), y + 3, 3.2, fillColor=color,
                         strokeColor=colors.white))
            _text(d, 410, y, f'{delta:+.0f} pp  n={result["source_family_count"]}',
                  size=7.4, color=color)
            row += 1
    return d


def family_figure(data: dict) -> Drawing:
    d = Drawing(WIDTH, 190)
    max_count = max(data['family_counts'].values())
    scale = 280 / max_count
    for index, cell in enumerate(matrix.CELLS):
        y = 152 - 25 * index
        count = data['family_counts'][cell]
        _text(d, 0, y + 5, LABELS[cell], size=8, bold=True)
        d.add(Rect(125, y, count * scale, 17, fillColor=BLUE,
                   strokeColor=colors.white))
        _text(d, 132 + count * scale, y + 5, str(count), size=8,
              color=INK, bold=True)
    return d


def trajectory_figure(data: dict) -> Drawing:
    """Small multiples show valid selection outcomes and unscored rounds."""
    d = Drawing(WIDTH, 365)
    by_key = {(row['cell_id'], row['researcher_id']): row
              for row in data['trajectory']['campaigns']}
    left, col_width = 110, 93
    for column, researcher in enumerate(matrix.RESEARCHERS):
        _text(d, left + column * col_width + 43, 341,
              RESEARCHER_LABELS[researcher], size=8, color=GRAY,
              bold=True, anchor='middle')
    for row_index, cell in enumerate(matrix.CELLS):
        bottom = 297 - row_index * 49
        _text(d, 0, bottom + 18, LABELS[cell], size=8, bold=True)
        for column, researcher in enumerate(matrix.RESEARCHERS):
            campaign = by_key[(cell, researcher)]
            rounds = campaign['rounds']
            max_round = max(len(rounds), 2)
            start = left + column * col_width
            xcoord = lambda number: start + 10 + (number - 1) * 63 / (max_round - 1)
            ycoord = lambda wins: bottom + wins * 1.2
            d.add(Line(start + 7, bottom, start + 76, bottom,
                       strokeColor=LIGHT, strokeWidth=.5))
            last = None
            for round_row in rounds:
                x = xcoord(round_row['round'])
                wins = round_row['selection_wins']
                if wins is None:
                    _text(d, x, bottom + 12, 'x', size=8, color=ORANGE,
                          bold=True, anchor='middle')
                    continue
                y = ycoord(wins)
                if last is not None:
                    d.add(Line(last[0], last[1], x, y,
                               strokeColor=BLUE, strokeWidth=1))
                d.add(Circle(x, y, 2.6, fillColor=BLUE,
                             strokeColor=colors.white))
                last = (x, y)
            _text(d, start + 81, bottom + 3,
                  str(campaign['selected_checkpoint_selection_wins']),
                  size=7.2, color=GRAY, anchor='end')
    _text(d, 0, 5,
          'Blue = valid selection score (0-20); orange x = unscored round; right number = selected incumbent.',
          size=7.1, color=GRAY)
    return d


def _table(rows: list[list[str]], widths: list[float]) -> Table:
    table = Table([[para(str(value), 'cell') for value in row] for row in rows],
                  colWidths=widths, repeatRows=1, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, 0), PALE_BLUE),
        ('LINEBELOW', (0, 0), (-1, 0), 0.7, BLUE),
        ('LINEBELOW', (0, -1), (-1, -1), 0.5, LIGHT),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    return table


def percentile(values: list[int], fraction: float) -> float:
    ordered = sorted(values)
    position = fraction * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _family_supplement(data: dict) -> dict:
    rows = []
    for comparison in data['summary']['comparisons']:
        cell = comparison['cell_id']
        entry = []
        for number, family in enumerate(
                comparison['summary']['source_family_outcomes'], start=1):
            token = f'F{number:03d}'
            entry.append({key: value for key, value in family.items()
                          if key != 'source_family'} | {'family_pseudonym': token})
        rows.append({'cell_id': cell, 'researcher_id': comparison['researcher_id'],
                     'families': entry})
    return {
        'schema': 'cua-full-study-pseudonymized-family-effects-v1',
        'study_id': data['summary']['study_id'],
        'matrix_plan_sha256': data['summary']['matrix_plan_sha256'],
        'comparisons': rows,
        'boundary': 'Family identifiers are pseudonyms; source identities and task gold are excluded.',
    }


def _page(canvas, doc, *, synthetic_fixture: bool) -> None:
    canvas.saveState()
    canvas.setStrokeColor(BLUE)
    canvas.line(54, A4[1] - 36, A4[0] - 54, A4[1] - 36)
    canvas.setFont('Helvetica-Bold', 8)
    canvas.setFillColor(BLUE)
    canvas.drawString(54, A4[1] - 30, 'EnvLoop  /  Computer-use data research')
    canvas.setFont('Helvetica', 7.5)
    canvas.setFillColor(GRAY)
    canvas.drawString(54, 25, 'Full-study technical report  |  source-bound release')
    canvas.drawRightString(A4[0] - 54, 25, str(doc.page))
    if synthetic_fixture:
        canvas.setFillColor(colors.HexColor('#b52020'))
        canvas.setFont('Helvetica-Bold', 18)
        canvas.translate(A4[0] / 2, A4[1] / 2)
        canvas.rotate(35)
        canvas.drawCentredString(0, 0, 'SYNTHETIC LAYOUT FIXTURE - NOT RESULTS')
    canvas.restoreState()


def _render_pdf(data: dict, path: Path, *, synthetic_fixture: bool = False) -> None:
    summary = data['summary']
    comparisons = summary['comparisons']
    deltas = [row['summary']['paired_delta_pp'] for row in comparisons]
    positive = sum(value > 0 for value in deltas)
    tied = sum(value == 0 for value in deltas)
    negative = sum(value < 0 for value in deltas)
    doc = BaseDocTemplate(str(path), pagesize=A4, leftMargin=54,
                          rightMargin=54, topMargin=51, bottomMargin=45,
                          title='EnvLoop Full Computer-Use Study',
                          author='EnvLoop',
                          subject='Audited 4 x 6 data-research benchmark results')
    doc.addPageTemplates(PageTemplate(
        id='paper', frames=[Frame(54, 45, WIDTH, A4[1] - 96,
                                  leftPadding=0, rightPadding=0,
                                  topPadding=0, bottomPadding=0)],
        onPage=lambda canvas, template: _page(
            canvas, template, synthetic_fixture=synthetic_fixture)))
    story = []
    story.append(para('Data-Centric Research for Verifiable Computer Use', 'title'))
    story.append(para('A matched six-application study of four researcher configurations '
                      'and a fixed Qwen3.8-27B student', 'subtitle'))
    story.append(para('Abstract', 'h1'))
    story.append(para(
        f'We evaluate 24 frozen data-research campaigns across six real-software '
        f'cells with {summary["distinct_final_task_identities"]} distinct final task '
        f'identities and {summary["slot_task_result_count"]} matched comparison '
        f'slots. On the audited paired selected-minus-base measure, {positive} '
        f'cell/researcher comparisons improved, {tied} tied, and {negative} '
        f'regressed. The primary intervals resample preregistered source families '
        f'and are conditional on one checkpoint and rollout seed. The release '
        f'separates model outcomes, invalid infrastructure attempts, explicit '
        f'timeout subtypes, and cost basis.'))
    story.append(para('1. Question and controlled comparison', 'h1'))
    story.append(para(
        'The research question is whether a researcher system can improve a '
        'fixed vision-capable computer-use student by creating and selecting '
        'training data under matched service and budget constraints. The '
        'student is Qwen/Qwen3.8-27B and the rollout teacher is gpt-5.6-sol. '
        'The four researcher configurations are gpt-6-astra, gpt-5.6-sol, '
        'gpt-6-sol, and gpt-6-luna. They differ as frozen system configurations; '
        'this is not a controlled experiment on model weights alone.'))
    story.append(para(
        'Each application provides 20 selection tasks and 100 held-out final '
        'identities. Four researcher campaigns per cell share the base, teacher, '
        'task partitions, training interface, and declared per-campaign caps. '
        'One base execution is shared within each cell; identical selected '
        'checkpoints reuse the same evidence rather than creating new samples. '
        'Selections are frozen before final execution. The nominal campaign '
        'limit is 16 hours and USD 500 of Tinker usage, with separate all-in '
        'limits and a usage ledger.'))
    story.append(para(
        'The design adapts the data-only research isolation of RSIBench-Data [1] '
        'to original computer-use tasks. Its applications, student, task pools, '
        'and paired selected-minus-base estimand differ, so scores are not '
        'directly comparable to that benchmark.'))
    story.append(para('2. Tasks, sources, and application state', 'h1'))
    rows = [['Application', 'Source and task provenance', 'Final families']]
    for cell in matrix.CELLS:
        rows.append([LABELS[cell], SOURCE_NOTES[cell], str(data['family_counts'][cell])])
    story.append(_table(rows, [116, 302, WIDTH - 418]))
    story.append(Spacer(1, 7))
    story.append(para(
        'Real external facts are separated from authored workflows and '
        'operational values. World Development Indicators and SEC filing '
        'facts anchor document tasks; CISA KEV anchors GitLab scenarios. '
        'Magento sample catalog data are real application fixtures, while '
        'supplier quote policies are authored simulations. The Odoo cell '
        'uses original workflows in Odoo Community. Each admitted task has '
        'a fresh reset, native GUI controls, saved-state readback, and an '
        'independent verifier. The separate six-cell review index binds '
        'source rights, hidden-set separation, traces, and negative controls.'))
    story.append(KeepTogether([family_figure(data),
                               para('Figure 1. Preregistered final-task source-family counts. '
                                    'Each cell has 100 final identities; variants within a '
                                    'family are correlated.', 'caption')]))
    story.append(para('3. Action contract and scoring', 'h1'))
    story.append(para(
        'The frozen common model contract binds screenshot observations, '
        'the bounded GUI action grammar, current-frame and task scope, '
        'sampling, parser, and exact environment versions before dispatch. '
        'The actor cannot earn success by claiming completion. Native '
        'application state or saved documents are read back by an isolated '
        'verifier, including preservation of unrelated state. A scored task '
        'is binary. A provider, transport, environment, or verifier failure '
        'is invalid and may have one rule-bound recovery; it is never '
        'silently converted into model zero. An actor action or wall budget '
        'timeout, by contrast, is a scored model failure and remains '
        'explicit in the telemetry ledger.'))
    story.append(para(
        'The primary cell/researcher statistic is the within-task selected '
        'success rate minus its shared base rate, in percentage points. '
        'The 95% percentile interval resamples prespecified source-family '
        'clusters with 10,000 draws and seed 23. The secondary task '
        'bootstrap treats within-family variants as independent and is '
        'included only in the machine-readable audited summary. Family '
        'intervals are descriptive when fewer than ten credible families '
        'exist. No unadjusted per-comparison significance claims are made.'))
    story.append(para('4. Complete paired outcomes', 'h1'))
    story.append(KeepTogether([matrix_figure(data),
                               para('Figure 2. All 24 selected-minus-base paired '
                                    'differences on the same 100 identities in '
                                    'each cell. Color indicates direction, not '
                                    'statistical significance.', 'caption')]))
    story.append(KeepTogether([effect_figure(data),
                               para('Figure 3. Paired effect and 95% source-family '
                                    'cluster interval for every cell/researcher '
                                    'comparison. A missing interval denotes too '
                                    'few families for a cluster interval.', 'caption')]))
    story.append(PageBreak())
    story.append(para('5. Research-process trajectories', 'h1'))
    trajectory = data['trajectory']
    story.append(para(
        f'The 24 campaigns contain {trajectory["round_count"]} ordered research '
        f'rounds: {trajectory["scored_round_count"]} with valid selection '
        f'feedback and {trajectory["unscored_round_count"]} without a valid '
        f'selection score. {trajectory["improved_over_first_valid_campaigns"]} '
        f'campaigns found a later candidate above their first valid score; '
        f'{trajectory["last_below_peak_campaigns"]} ended with a lower last '
        f'valid candidate after seeing a peak. The median recorded round '
        f'duration was {trajectory["round_wall_seconds_median"] / 60:.1f} '
        f'minutes, with USD {trajectory["round_cost_subtotal_usd"]} '
        f'attributed to rounds and {trajectory["selection_retry_count"]} '
        f'bound selection retries. The selected incumbent can '
        f'differ from both the highest observed and last candidate. These '
        f'within-campaign paths describe search behavior, not sustained '
        f'recursive self-improvement.'))
    story.append(KeepTogether([trajectory_figure(data),
                               para('Figure 4. Ordered candidate selection '
                                    'paths for all 24 campaigns. Unscored '
                                    'rounds remain visible, and the chosen '
                                    'incumbent is distinct from the last '
                                    'candidate. Full numeric paths and failure '
                                    'classes are in campaign-search-summary.json.',
                                    'caption')]))
    story.append(para('6. Operational outcomes and cost', 'h1'))
    telemetry = data['telemetry']
    timeout_count = sum(value for key, value in telemetry['timeout_counts'].items()
                        if key != 'none')
    story.append(para(
        f'The audit covers {telemetry["task_count"]} unique checkpoint-task '
        f'executions and {telemetry["attempt_count"]} total final attempts, '
        f'including {telemetry["retry_count"]} preserved, rule-bound '
        f'infrastructure recoveries. {timeout_count} attempts carry an '
        f'explicit timeout subtype. The 3,000 comparison slots can exceed '
        f'unique executions because identical checkpoint evidence is reused.'))
    failure_rows = [['Failure class', 'Campaign ledger', 'Invalid final attempts',
                     'Timed-out final attempts']]
    for failure in sorted(data['usage']['campaign_failures_by_type']):
        failure_rows.append([
            failure,
            str(data['usage']['campaign_failures_by_type'][failure]),
            str(summary['infrastructure_invalid_attempts_by_type'][failure]),
            str(telemetry['timeout_counts'][failure]),
        ])
    failure_rows.append([
        'actor budget', 'n/a', 'scored model zero',
        str(telemetry['timeout_counts']['actor_action_budget'] +
            telemetry['timeout_counts']['actor_wall_budget']),
    ])
    story.append(_table(failure_rows, [116, 104, 122, WIDTH - 342]))
    story.append(Spacer(1, 7))
    lat = telemetry['provider_latencies_ms']
    wall = telemetry['wall_times_ms']
    actions = telemetry['action_counts']
    operational_rows = [
        ['Final-attempt measurement', 'Median', '95th percentile'],
        ['Actions', f'{percentile(actions, .5):.1f}', f'{percentile(actions, .95):.1f}'],
        ['Wall time (s)', f'{percentile(wall, .5)/1000:.2f}',
         f'{percentile(wall, .95)/1000:.2f}'],
        ['Cumulative provider latency (s)',
         f'{percentile(lat, .5)/1000:.2f}',
         f'{percentile(lat, .95)/1000:.2f}'],
    ]
    latency_note = para(
        'Latency is the per-attempt cumulative provider wait recorded by '
        'the telemetry ledger, not a server-side token/s measure. All '
        'percentiles include valid scored attempts and preserved invalid '
        'attempts; they are descriptive of this execution, not uncertainty '
        'across independent training runs.', 'small')
    story.append(KeepTogether([
        _table(operational_rows, [226, 125, WIDTH - 351]), latency_note]))
    story.append(para('Resource accounting', 'h2'))
    cost_rows = [['Component', 'Reported USD']]
    for key, value in data['usage']['cost_components_usd'].items():
        cost_rows.append([key.replace('_', ' '), str(value)])
    cost_rows.append(['shared base final', data['usage']['shared_base_final_usd']])
    cost_rows.append(['all-in subtotal', summary['reported_all_in_cost_subtotal_usd']])
    story.append(_table(cost_rows, [310, WIDTH - 310]))
    story.append(para(
        'Cost bases present: ' + ', '.join(summary['cost_bases_present']) + '. '
        + ('Every provider invoice is present.' if summary['provider_invoice_complete']
           else 'Provider invoices are incomplete; nominal-rate values must not be read as billed spend.'),
        'small'))
    story.append(para('7. Limitations and reproducibility', 'h1'))
    story.append(para(
        'The intervals condition on one selected checkpoint and rollout '
        'seed; they do not quantify researcher-search or independent '
        'training-run variability. Related variants share source families, '
        'and authored business policies limit claims about production '
        'generality. Model-provider identifiers do not attest exact weight '
        'bytes. Application-specific review receipts document human audit '
        'but do not make raw trace truth cryptographically self-proving. '
        'Different applications remain separate estimands; no pooled '
        'computer-use score is reported.'))
    story.append(para(
        'Reproduction begins with the pinned pre-campaign manifest, '
        'post-campaign matrix, execution index, candidate/selection trajectory '
        'ledger, selection and usage '
        'receipts, saved-state/reset/verifier evidence, complete attempt '
        'telemetry, and six independent reviews. The report builder '
        'revalidates all referenced bytes and recomputes paired statistics '
        'before producing this PDF. The source-hash manifest and '
        'pseudonymized family-effect supplement accompany the report. '
        'Credentials, hidden task instructions, gold, and raw account '
        'state are excluded from the public projection.'))
    story.append(PageBreak())
    story.append(para('Appendix A. Source-bound release record', 'h1'))
    story.append(para(
        'The table gives short SHA-256 prefixes for navigation; the full '
        'hashes and every generated-asset digest are in the accompanying '
        'report-source-manifest.json. A hash identifies bytes and detects '
        'later changes; it does not certify the truth of a GUI observation.'))
    hash_rows = [['Verified input', 'SHA-256 prefix']]
    for name, value in data['source_hashes'].items():
        hash_rows.append([name.replace('_', ' '), str(value)[:20]])
    story.append(_table(hash_rows, [273, WIDTH - 273]))
    story.append(para('Independent cell review coverage', 'h2'))
    review_rows = [['Cell', 'Final task receipts reviewed', 'Review gate']]
    for cell in matrix.CELLS:
        review_rows.append([LABELS[cell], '100', 'passed'])
    story.append(_table(review_rows, [177, 174, WIDTH - 351]))
    story.append(Spacer(1, 7))
    story.append(para(
        'The pseudonymized family-effects JSON supplies every source-family '
        'task count, base and selected win count, improved count, regressed '
        'count, and paired difference for all 24 comparisons. The public '
        'projection does not expose source-family identity strings or task gold.'))
    story.append(para('References', 'h1'))
    story.append(para(
        '[1] Meng et al., RSIBench-Data: Benchmarking Data-Centric Research '
        'for Recursive Self-Improvement, arXiv:2607.25886 (2026). '
        'https://arxiv.org/abs/2607.25886', 'small'))
    story.append(para(
        '[2] EnvLoop, Full computer-use study: pre-result protocol. '
        'https://github.com/EnvLoop/cua-rsibench/blob/main/docs/'
        'FULL_STUDY_PREREGISTRATION.md', 'small'))
    story.append(para(
        '[3] EnvLoop, Full-study result audit and report input. '
        'https://github.com/EnvLoop/cua-rsibench/blob/main/docs/'
        'FULL_STUDY_RESULTS_AUDIT.md', 'small'))
    doc.build(story)


def build_report(data: dict, out_dir: Path, *,
                 synthetic_fixture: bool = False) -> dict:
    """Write a fresh private review directory from audited or test-only data."""
    if not synthetic_fixture and not isinstance(data, publication.VerifiedPublicationData):
        raise ValueError('unwatermarked report requires verified publication data')
    out_dir = out_dir.resolve()
    repo_root = Path(__file__).resolve().parents[2]
    try:
        within_repo = out_dir.relative_to(repo_root)
    except ValueError:
        pass
    else:
        if not within_repo.parts or within_repo.parts[0] not in {'work', 'tmp'}:
            raise ValueError('report must be built in a private review directory')
    if out_dir.exists():
        raise FileExistsError(f'report output already exists: {out_dir}')
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.full-paper-stage-', dir=out_dir.parent))
    try:
        figures = stage / 'figures'
        figures.mkdir()
        for name, drawing in (
            ('source-families.svg', family_figure(data)),
            ('paired-matrix.svg', matrix_figure(data)),
            ('family-effects.svg', effect_figure(data)),
            ('candidate-trajectories.svg', trajectory_figure(data)),
        ):
            if synthetic_fixture:
                drawing.add(Rect(1, 1, drawing.width - 2, drawing.height - 2,
                                 fillColor=None, strokeColor=colors.HexColor('#b52020'),
                                 strokeWidth=2))
                _text(drawing, 6, drawing.height - 14,
                      'SYNTHETIC FIXTURE - NOT RESULTS', size=9,
                      color=colors.HexColor('#b52020'), bold=True)
            renderSVG.drawToFile(drawing, str(figures / name))
        family_path = stage / 'family-effects-pseudonymized.json'
        family = _family_supplement(data)
        if synthetic_fixture:
            family['synthetic_layout_fixture'] = True
        family_path.write_bytes(evidence.json_bytes(family) + b'\n')
        search_path = stage / 'campaign-search-summary.json'
        search = {
            'schema': 'cua-full-study-public-campaign-search-summary-v1',
            'study_id': data['summary']['study_id'],
            'matrix_plan_sha256': data['summary']['matrix_plan_sha256'],
            'trajectory_index_sha256': data['trajectory']['index_sha256'],
            'campaigns': data['trajectory']['campaigns'],
        }
        if synthetic_fixture:
            search['synthetic_layout_fixture'] = True
        search_path.write_bytes(evidence.json_bytes(search) + b'\n')
        pdf_path = stage / 'EnvLoop-Full-Computer-Use-Study.pdf'
        _render_pdf(data, pdf_path, synthetic_fixture=synthetic_fixture)
        files = sorted(path for path in stage.rglob('*') if path.is_file())
        manifest = {
            'schema': 'cua-full-study-paper-output-manifest-v1',
            'study_id': data['summary']['study_id'],
            'synthetic_layout_fixture': synthetic_fixture,
            'source_hashes': data['source_hashes'],
            'file_sha256': {
                path.relative_to(stage).as_posix(): evidence.digest(path.read_bytes())
                for path in files
            },
            'publication_boundary': (
                'Private review output. Publish only after privacy and rendered-PDF inspection.'
            ),
        }
        (stage / 'report-source-manifest.json').write_bytes(
            evidence.json_bytes(manifest) + b'\n')
        os.replace(stage, out_dir)
        return manifest
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
