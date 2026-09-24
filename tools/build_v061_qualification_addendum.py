"""Build the evidence-bound v0.6.1 real-software qualification addendum.

The three controls are development probes. This builder deliberately does not
aggregate their scores or promote them into the planned 24-campaign study.
"""

from __future__ import annotations

import json
from pathlib import Path

from reportlab.graphics import renderSVG
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    Flowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
    Table, TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/evidence"
OUT = ROOT / "docs/qualification-v061"
PDF = OUT / "EnvLoop-Real-Software-Qualification-Addendum.pdf"
SVG = OUT / "figures/control-transitions.svg"

INK = colors.HexColor("#19333d")
TEAL = colors.HexColor("#087c72")
MUTED = colors.HexColor("#566c73")
PALE = colors.HexColor("#eef4f3")
RED = colors.HexColor("#c75b48")
GOLD = colors.HexColor("#d4a136")
GREEN = colors.HexColor("#268b68")
WHITE = colors.white
PAGE = (595, 842)
WIDTH = 491

STYLES = {
    "title": ParagraphStyle("title", fontName="Times-Bold", fontSize=23,
                            leading=27, textColor=INK, spaceAfter=10),
    "deck": ParagraphStyle("deck", fontName="Helvetica", fontSize=9,
                           leading=13, textColor=TEAL, spaceAfter=15),
    "heading": ParagraphStyle("heading", fontName="Times-Bold", fontSize=14,
                              leading=17, textColor=INK, spaceBefore=13,
                              spaceAfter=6, keepWithNext=True),
    "body": ParagraphStyle("body", fontName="Times-Roman", fontSize=10,
                           leading=14.3, textColor=INK, spaceAfter=8,
                           allowOrphans=0, allowWidows=0),
    "small": ParagraphStyle("small", fontName="Helvetica", fontSize=8.2,
                            leading=11.3, textColor=MUTED, spaceAfter=5),
    "caption": ParagraphStyle("caption", fontName="Helvetica", fontSize=8.1,
                              leading=11, textColor=MUTED, spaceBefore=6,
                              spaceAfter=12),
    "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=8.2,
                           leading=11.2, textColor=INK),
    "cellhead": ParagraphStyle("cellhead", fontName="Helvetica-Bold",
                               fontSize=8.2, leading=11.2, textColor=INK),
}


def p(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, STYLES[style])


def load_receipts() -> dict:
    retail = json.loads((EVIDENCE / "sec-retail-working-capital-excel-web-controls-2026-09-24.json").read_text())
    ppt = json.loads((EVIDENCE / "ppt-eval-office-web-gate-2026-09-24.json").read_text())
    magento = json.loads((EVIDENCE / "magento-variant-price-qualified-2026-09-24.json").read_text())
    checks = [
        ("retail has no model calls", retail["observed_gui"]["model_calls"] == 0),
        ("retail partial is one repair", retail["partial_control"]["repaired_faults"] == 1),
        ("retail full is nine repairs", retail["full_control"]["repaired_faults"] == 9),
        ("retail checks 92 targets", retail["full_control"]["checked_targets"] == 92),
        ("retail reset has zero repairs", retail["reset_control"]["repaired_faults_remaining"] == 0),
        ("retail automated reset unproven", retail["admission_limits"]["automated_cloud_reset_proven"] is False),
        ("PPT baseline scores zero", ppt["baseline_noop_official_score"] == 0),
        ("PPT partial upstream score", ppt["real_gui_mixed_size_negative"]["official_score_against_office_baseline"] == 1),
        ("PPT partial guard score", ppt["real_gui_mixed_size_negative"]["independent_guard_score"] == 0),
        ("PPT full upstream score", ppt["real_gui_full_title_positive"]["official_score_against_office_baseline"] == 1),
        ("PPT full guard score", ppt["real_gui_full_title_positive"]["independent_guard_score"] == 1),
        ("PPT reset score", ppt["rollback"]["official_target_score_after_reset"] == 0),
        ("PPT has no model or final task", ppt["qualified_final_tasks"] == ppt["model_calls"] == 0),
        ("Magento positive score", magento["positive"]["published_evaluator_score"] == 1),
        ("Magento negative score", magento["negative"]["published_evaluator_score"] == 0),
        ("Magento reset SQL scope", magento["reset"]["sql_monitored_business_table_count"] == 9),
        ("Magento reset search scope", magento["reset"]["search_index_document_count"] == 181),
        ("Magento final reset", magento["reset"]["final_reset_verified"] is True),
        ("Magento has no model or final task", magento["admission"]["model_calls"] == magento["admission"]["official_final_task_count"] == 0),
    ]
    for label, passed in checks:
        if not passed:
            raise ValueError(f"receipt gate failed: {label}")
    return {"retail": retail, "ppt": ppt, "magento": magento}


def label(d: Drawing, x: float, y: float, value: str, *, size=9, color=INK,
          bold=False) -> None:
    d.add(String(x, y, value, fontName="Helvetica-Bold" if bold else "Helvetica",
                 fontSize=size, fillColor=color))


def score_box(d: Drawing, x: float, y: float, number: str, desc: str,
              color) -> None:
    d.add(Rect(x, y, 92, 45, rx=5, ry=5, fillColor=color, strokeColor=None))
    label(d, x + 9, y + 24, number, size=15, color=WHITE, bold=True)
    label(d, x + 9, y + 10, desc, size=7.4, color=WHITE)


def arrow(d: Drawing, x1: float, x2: float, y: float) -> None:
    d.add(Line(x1, y, x2, y, strokeColor=MUTED, strokeWidth=1))
    d.add(Line(x2 - 5, y + 3, x2, y, strokeColor=MUTED, strokeWidth=1))
    d.add(Line(x2 - 5, y - 3, x2, y, strokeColor=MUTED, strokeWidth=1))


def figure() -> Drawing:
    """A comparison of within-task controls; no cross-surface score average."""
    d = Drawing(WIDTH, 218)
    d.add(Rect(0, 0, WIDTH, 218, fillColor=WHITE,
               strokeColor=colors.HexColor("#d8e2e0"), strokeWidth=.7))
    label(d, 12, 198, "REAL-SOFTWARE DEVELOPMENT CONTROLS", size=9,
          color=TEAL, bold=True)
    label(d, 12, 184, "Each row has its own verifier and denominator.",
          size=8, color=MUTED)

    rows = [
        ("EXCEL WEB", "faults repaired", [("1/9", "partial", GOLD),
                                         ("9/9", "full + replays", GREEN),
                                         ("0/9", "manual reset", RED)]),
        ("POWERPOINT WEB", "official / guard", [("1 / 0", "mixed-size", RED),
                                                ("1 / 1", "full title", GREEN),
                                                ("0", "reset target", GOLD)]),
        ("MAGENTO ADMIN", "published evaluator", [("1.0", "five target SKUs", GREEN),
                                                   ("0.0", "wrong color", RED),
                                                   ("match", "reset after each", GOLD)]),
    ]
    ys = [123, 66, 9]
    for (surface, metric, steps), y in zip(rows, ys):
        d.add(Line(12, y + 53, WIDTH - 12, y + 53,
                   strokeColor=colors.HexColor("#e6eceb"), strokeWidth=.6))
        label(d, 12, y + 31, surface, size=8.5, bold=True)
        label(d, 12, y + 18, metric, size=7.1, color=MUTED)
        xs = [168, 274, 380]
        for idx, (score, desc, color) in enumerate(steps):
            score_box(d, xs[idx], y, score, desc, color)
        if surface != "MAGENTO ADMIN":
            arrow(d, 260, 272, y + 22)
            arrow(d, 366, 378, y + 22)
    return d


class VectorFigure(Flowable):
    def __init__(self, drawing: Drawing):
        super().__init__()
        self.drawing = drawing
        self.width = drawing.width
        self.height = drawing.height

    def draw(self):
        from reportlab.graphics import renderPDF
        renderPDF.draw(self.drawing, self.canv, 0, 0)


def table(headers: list[str], rows: list[list[str]], widths: list[int]) -> Table:
    data = [[p(v, "cellhead" if i == 0 else "cell") for v in row]
            for i, row in enumerate([headers] + rows)]
    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, 0), PALE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, colors.HexColor("#f9fbfb")]),
        ("LINEABOVE", (0, 0), (-1, 0), .8, INK),
        ("LINEBELOW", (0, -1), (-1, -1), .8, INK),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def decorate(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(TEAL)
    canvas.setLineWidth(.9)
    canvas.line(52, 803, 543, 803)
    canvas.setFillColor(TEAL)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(52, 813, "ENVLOOP")
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(543, 815, "COMPUTER-USE BENCHMARK / v0.6.1")
    canvas.line(52, 39, 543, 39)
    canvas.drawString(52, 25, "Real-software qualification addendum - no full-study results")
    canvas.drawRightString(543, 25, str(doc.page))
    canvas.restoreState()


def story() -> list:
    return [
        p("Real-Software Qualification: Three Saved-State Controls", "title"),
        p("EnvLoop | v0.6.1 addendum | 24 September 2026", "deck"),
        p("<b>Study status:</b> 0/24 researcher campaigns and 0/600 distinct official final "
          "task identities completed. The observations below are development controls, "
          "not student-model scores, hidden final tasks, or evidence of training gain."),
        VectorFigure(figure()),
        p("Figure 1. Within-task positive, negative, and reset signals observed in real "
          "software. Values across rows are deliberately not pooled.", "caption"),
        p("Observed readback", "heading"),
        table(["Surface", "Evidence-bearing observation", "Boundary"], [
            ["Microsoft Excel for the web",
             "A five-sheet retail working-capital workbook with 112 authentic SEC "
             "companyfacts observations and 92 formula targets was edited through the "
             "GUI. Partial, full, and same-file manual reset downloads scored 1/9, "
             "9/9, and 0/9 faults repaired. The full repair passed 92/92 targets and "
             "two evaluator-side replays.",
             "Public development fixture. No Qwen run or automated fresh-attempt cloud reset."],
            ["Microsoft PowerPoint for the web",
             "A 32-slide PPT-Eval selection deck was Office-normalized before scoring. "
             "Changing only one word of the title scored 1.0 upstream but 0.0 under "
             "the independent all-runs guard. The complete 48 pt title scored 1.0 "
             "under both; GUI rollback returned the target score to 0.0.",
             "One selection task, no final task. Office's first-save visual equivalence "
             "was not comprehensively proven."],
            ["Magento admin",
             "After repair of one isolated clone's search service and base URL, a "
             "scripted GUI control saved five green variants at $47 from $52. The "
             "unchanged published evaluator scored 1.0; a wrong-color save scored "
             "0.0. Monitored SQL and all 181 search documents reset to baseline.",
             "One clone and one public task. No model score or general 100-task reset."],
        ], [104, 231, 156]),
        PageBreak(),
        p("What the controls establish", "heading"),
        p("<b>Excel:</b> The operator repaired one formula, saved, reloaded, and downloaded "
          "the file; the independent oracle gave isolated 1/9 credit but failed the "
          "complete task. Continuing on the same cloud file, nine repairs passed 92 "
          "targets and both public development replay profiles. The operator then "
          "manually reverted the same file. Formula text, source values, checked "
          "structure, and tables matched the seed; all 92 Excel-populated caches were "
          "current. The reset scored 0/9. A separate full positive and automatic reset "
          "remain unverified."),
        p("<b>PowerPoint:</b> A frozen, evaluator-owned Office-normalized baseline "
          "prevented first-save package rewriting from being mistaken for actor damage. "
          "The unchanged PPT-Eval check nevertheless accepted a mixed-size title as a "
          "perfect edit. The independent guard required every nonempty title run to "
          "be 48 pt and rejected it. A complete GUI title selection then passed both "
          "checks, and a same-file GUI rollback restored the 42 pt title and target "
          "score of zero."),
        p("<b>Magento:</b> The previous task-777 rejection remains valid for its failed "
          "clone: HTTP 302 and an evaluator score of 1.0 had not persisted the prices. "
          "The repaired disposable clone produced a native save confirmation, "
          "independent SQL readback of five target prices, and a wrong-color negative. "
          "SQL rollback alone left stale search state, so the qualification tool rebuilt "
          "and compared all 181 search documents after both cases. Its nine monitored "
          "SQL business tables also matched baseline after each case."),
        p("Admission boundary", "heading"),
        p("The public Excel builder exposes its fault map and replay vectors; the "
          "published PPT-Eval and WebArena task identities are also discoverable. "
          "These cases are reproducible development probes, not hidden official finals. "
          "A cell still needs source-disjoint final identities, 100 individually admitted "
          "tasks, bounded model actions, evaluator-owned fresh reset, and observed "
          "checkpoint results. No cell currently satisfies that complete gate."),
        p("Evidence ledger", "heading"),
        p("The field-limited public receipts below bind saved artifact hashes, "
          "scores, and reset scope without publishing account identities, private "
          "document links, raw authenticated traces, or evaluator-only answers."),
        p("1. <font name='Courier'>docs/evidence/sec-retail-working-capital-excel-web-controls-2026-09-24.json</font>", "small"),
        p("2. <font name='Courier'>docs/evidence/ppt-eval-office-web-gate-2026-09-24.json</font>", "small"),
        p("3. <font name='Courier'>docs/evidence/magento-variant-price-qualified-2026-09-24.json</font>", "small"),
        Spacer(1, 8),
        p("This addendum supplements the v0.6 qualification note. It does not revise "
          "the immutable v0.5 Kanboard result or report the planned full-scale study.",
          "small"),
    ]


def build() -> tuple[Path, Path]:
    load_receipts()
    OUT.mkdir(parents=True, exist_ok=True)
    SVG.parent.mkdir(parents=True, exist_ok=True)
    renderSVG.drawToFile(figure(), str(SVG))
    doc = SimpleDocTemplate(str(PDF), pagesize=PAGE, leftMargin=52,
                            rightMargin=52, topMargin=58, bottomMargin=55,
                            title="EnvLoop Real-Software Qualification Addendum",
                            author="EnvLoop",
                            subject="v0.6.1 development controls; no full-study results")
    doc.build(story(), onFirstPage=decorate, onLaterPages=decorate)
    return PDF, SVG


if __name__ == "__main__":
    pdf, svg = build()
    print(pdf)
    print(svg)
