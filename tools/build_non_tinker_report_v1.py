"""English methods/build PDF from the current public status document.

This is a build report, not a benchmark result or model-performance report.
Render the output and inspect every page before delivery.
"""
from pathlib import Path
import argparse,re
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,PageBreak
from reportlab.lib.pagesizes import A4
from xml.sax.saxutils import escape

ROOT=Path(__file__).resolve().parents[1]

def inline(text):
    text=re.sub(r'!\[[^]]*\]\([^)]+\)','',text)
    text=re.sub(r'\[([^]]+)\]\([^)]+\)',r'\1',text)
    return escape(text).replace('`','')


def build(output,diagram):
    status=ROOT/'deployment/non-tinker-runner/BUILD_STATUS.md'
    text=status.read_text()
    if re.search(r'[\u3400-\u9fff]',text):raise ValueError('English public report required')
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    navy=colors.HexColor('#173448');teal=colors.HexColor('#287d87');muted=colors.HexColor('#496579')
    styles={
        'title':ParagraphStyle('Title',fontName='Helvetica-Bold',fontSize=23,leading=28,textColor=navy,spaceAfter=14),
        'heading':ParagraphStyle('Heading',fontName='Helvetica-Bold',fontSize=13,leading=17,textColor=teal,spaceBefore=14,spaceAfter=8),
        'body':ParagraphStyle('Body',fontName='Helvetica',fontSize=9.5,leading=12.5,textColor=navy,spaceAfter=6),
        'cell':ParagraphStyle('Cell',fontName='Helvetica',fontSize=8,leading=11,textColor=navy),
        'header':ParagraphStyle('Header',fontName='Helvetica-Bold',fontSize=8,leading=11,textColor=colors.white),
    }
    def footer(canvas,doc):
        canvas.saveState();canvas.setStrokeColor(colors.HexColor('#c3d3dc'));canvas.line(42,42,A4[0]-42,42)
        canvas.setFont('Helvetica',8);canvas.setFillColor(muted)
        canvas.drawString(42,29,'ENVLOOP  |  Non-training build evidence  |  2 October 2026')
        canvas.drawRightString(A4[0]-42,29,str(doc.page));canvas.restoreState()
    doc=SimpleDocTemplate(str(output),pagesize=A4,rightMargin=42,leftMargin=42,topMargin=40,bottomMargin=55,
        title='EnvLoop Computer Use Benchmark: Non-Training Build Report',author='EnvLoop')
    story=[Paragraph('Computer Use Benchmark<br/>Non-Training Build Report',styles['title']),
        Paragraph('EnvLoop / 2 October 2026',styles['body']),
        Paragraph('Scope: executable infrastructure and independently checked controls. This report contains no full-study model result or measured training gain.',styles['body'])]
    if diagram:
        dimensions=ImageReader(str(diagram)).getSize();width=A4[0]-84
        story.extend([Image(str(diagram),width=width,height=width*dimensions[1]/dimensions[0]),Spacer(1,12)])
    lines=text.splitlines();i=0
    while i<len(lines):
        line=lines[i].strip();i+=1
        if not line or line.startswith('# ') or line.startswith('!['):continue
        if line.startswith('## '):
            if line[3:] in ('Executable components','What can run without Tinker'):story.append(PageBreak())
            story.append(Paragraph(inline(line[3:]),styles['heading']));continue
        if line.startswith('|'):
            rows=[]
            while True:
                if not re.fullmatch(r'[| :\-]+',line):rows.append([part.strip() for part in line.strip('|').split('|')])
                if i>=len(lines) or not lines[i].strip().startswith('|'):break
                line=lines[i].strip();i+=1
            values=[[Paragraph(inline(c),styles['header' if n==0 else 'cell']) for c in row] for n,row in enumerate(rows)]
            table=Table(values,colWidths=[70,136,143,A4[0]-84-349],repeatRows=1,hAlign='LEFT')
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),navy),('VALIGN',(0,0),(-1,-1),'TOP'),
                ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
                ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
                ('LINEBELOW',(0,1),(-1,-1),0.4,colors.HexColor('#c3d3dc')),
                ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#f3f7f9'),colors.white])]))
            story.extend([table,Spacer(1,9)]);continue
        if line.startswith('- '):story.append(Paragraph('&#8226; '+inline(line[2:]),styles['body']));continue
        paragraph=[line]
        while i<len(lines) and lines[i].strip() and not lines[i].startswith(('#','|','- ','![')):
            paragraph.append(lines[i].strip());i+=1
        story.append(Paragraph(inline(' '.join(paragraph)),styles['body']))
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True);p.add_argument('--diagram-png')
    a=p.parse_args();print(str(build(a.out,a.diagram_png).resolve()))

if __name__=='__main__':main()
