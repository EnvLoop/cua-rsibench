"""Render an English research manuscript with tables and audit-derived results."""
import argparse,json,re
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,KeepTogether,PageBreak
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor
ROOT=Path(__file__).resolve().parents[1];WIDTH=483
INK=HexColor('#202733');BLUE=HexColor('#3154a5');GRAY=HexColor('#596271')
S={
 'title':ParagraphStyle('title',fontName='Times-Bold',fontSize=23,leading=27,alignment=1,textColor=INK,spaceAfter=13),
 'author':ParagraphStyle('author',fontName='Times-Roman',fontSize=11,leading=15,alignment=1,textColor=GRAY,spaceAfter=12),
 'h1':ParagraphStyle('h1',fontName='Times-Bold',fontSize=15,leading=19,textColor=INK,spaceBefore=17,spaceAfter=9,keepWithNext=True),
 'h2':ParagraphStyle('h2',fontName='Times-Bold',fontSize=11.6,leading=15,textColor=INK,spaceBefore=11,spaceAfter=5,keepWithNext=True),
 'body':ParagraphStyle('body',fontName='Times-Roman',fontSize=10.5,leading=14.7,textColor=INK,spaceAfter=8,alignment=4),
 'small':ParagraphStyle('small',fontName='Times-Roman',fontSize=9.1,leading=12.3,textColor=GRAY,spaceAfter=10),
 'cell':ParagraphStyle('cell',fontName='Times-Roman',fontSize=8.7,leading=11.5,textColor=INK),
}
def inline(text):
 text=escape(text)
 text=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',text)
 text=re.sub(r'`([^`]+)`',r'<font name="Courier">\1</font>',text)
 text=re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)',r'<link href="\2" color="#3154a5">\1</link>',text)
 return text

def P(text,kind='body'):return Paragraph(inline(text),S[kind])
def score(x):return 'N/A' if x is None else f'{x*100:.0f}%'
def markdown_table(rows):return '\n'.join('| '+' | '.join(map(str,row))+' |' for row in rows)
def manuscript(e):
 runs=e['data_campaigns'];data={'TOTAL_TOKENS':f'{sum(x["training_tokens"] for x in runs):,}'}
 rows=[['Researcher','Scored / invalid','First / best / last valid','Selection','Train tokens']]
 ledger=[['Researcher / round','Train tokens','Reward','Valid actions','Targets']]
 finals=[['Researcher selection','Final executions 1 / 2 / 3','Complete mean']]
 for r in runs:
  valid=[a for a in r['attempts'] if a['evaluation']['status']=='scored'];values=[a['evaluation']['reward'] for a in valid]
  rows.append([r['researcher'].replace('gpt-',''),f'{len(valid)} / {len(r["attempts"])-len(valid)}',' / '.join(score(v) for v in (values[0],max(values),values[-1])),'Base' if r['selection']['selected_baseline'] else r['selection']['selected_attempt'],f'{r["training_tokens"]:,}'])
  vals=[score(x.get('reward')) if x['status']=='scored' else ('Infra' if x['status']=='infrastructure_error' else 'Pending') for x in r['final_tests']]
  finals.append([r['researcher'].replace('gpt-','')+' -> Base',' / '.join(vals),score(r['final_avg'])])
  for a in r['attempts']:
   ev=a['evaluation'];v=ev.get('saved_state_verification') or {};target=f'{v["correct_target_tasks"]}/{v["target_tasks"]}' if v else 'N/A'
   ledger.append([r['researcher'].replace('gpt-','')+f' / {a["attempt"]}',f'{a["training_tokens"]:,}',score(ev.get('reward')),score(ev.get('valid_action_rate')),target])
 data.update(CANDIDATE_TABLE=markdown_table(rows),FINAL_TABLE=markdown_table(finals),LEDGER_TABLE=markdown_table(ledger))
 rows=[['Task / actor','Actions','Strict outcome']]
 for r in e['trials']:
  if not r['infrastructure_error']:rows.append([r['case'].replace('kanboard-','')+' / '+r['model'].replace('gpt-',''),r['steps'],'Pass' if r['verification'].get('success') else 'Fail'])
 data['CALIBRATION_TABLE']=markdown_table(rows)
 rows=[['Journaled replay','Status','Reward']]
 for r in (e.get('journal_recovery') or {}).get('runs',[]):rows.append([r['run'],r['evaluation']['status'],score(r['evaluation'].get('reward'))])
 data['JOURNAL_TABLE']=markdown_table(rows) if len(rows)>1 else 'Journaled recovery executions are in progress; no unobserved result is reported.'
 source=(ROOT/'tools/report_template.md').read_text()
 for key,value in data.items():source=source.replace('{{'+key+'}}',value)
 if '{{' in source:raise ValueError('unresolved report field')
 if re.search(r'[\u3400-\u9fff]',source):raise ValueError('non-English CJK content in manuscript')
 return source

def render(text,out,asset_root=None):
 asset_root=Path(asset_root) if asset_root else ROOT/'outputs'
 title=next((line[2:].strip() for line in text.splitlines() if line.startswith('# ')), 'CUA-RSIBench - Technical Report')
 story=[]
 for block in text.split('\n\n'):
  block=block.strip()
  if not block:continue
  if block=='---PAGEBREAK---':story.append(PageBreak());continue
  if block.startswith('# '):story.append(P(block[2:],'title'));story.append(P('EnvLoop | Technical Report | September 2026','author'));continue
  if block.startswith('### '):story.append(P(block[4:],'h2'));continue
  if block.startswith('## '):story.append(P(block[3:],'h1'));continue
  if block.startswith('!['):
   match=re.fullmatch(r'!\[(.*?)\]\((.*?)\)',block,re.S)
   if not match:raise ValueError('bad figure block')
   caption,path=match.groups();im=Image(str(asset_root/path));height=WIDTH*im.imageHeight/im.imageWidth
   story.append(KeepTogether([Image(str(asset_root/path),width=WIDTH,height=height),P(caption,'small')]));continue
  if block.startswith('|'):
   rows=[[x.strip() for x in line.strip().strip('|').split('|')] for line in block.splitlines()]
   rows=[row for row in rows if not all(re.fullmatch(r':?-{3,}:?',cell) for cell in row)]
   columns=len(rows[0]);weights={2:[.27,.73],3:[.48,.20,.32],5:[.25,.18,.16,.22,.19]}.get(columns,[1/columns]*columns)
   if 'Task family' in block:weights=[.20,.47,.33]
   if 'First / best' in block:weights=[.17,.17,.31,.14,.21]
   if 'Final executions' in block:weights=[.34,.44,.22]
   t=Table([[P(x,'cell') for x in row] for row in rows],colWidths=[WIDTH*w for w in weights],repeatRows=1)
   t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,0),HexColor('#f0f3f9')),('LINEABOVE',(0,0),(-1,0),.8,INK),('LINEBELOW',(0,0),(-1,0),.5,INK),('LINEBELOW',(0,-1),(-1,-1),.8,INK),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]));t.keepWithNext=True;spacer=Spacer(1,5);spacer.keepWithNext=True;story.extend([t,spacer]);continue
  text=' '.join(block.splitlines())
  story.append(P(text,'small' if text.startswith('**Table ') or text.startswith('[') else 'body'))
 def page(c,doc):
  c.setStrokeColor(BLUE);c.setLineWidth(.7);c.line(56,806,539,806)
  c.setFillColor(BLUE);c.setFont('Helvetica-Bold',14 if doc.page==1 else 9);c.drawString(56,815,'EnvLoop')
  c.setFillColor(GRAY);c.setFont('Times-Roman',8);c.drawRightString(539,815,'CUA-RSIBench - Technical Report')
  c.drawString(56,29,'github.com/EnvLoop/cua-rsibench');c.drawRightString(539,29,str(doc.page))
 out=Path(out)
 SimpleDocTemplate(str(out),pagesize=(595,842),leftMargin=56,rightMargin=56,topMargin=56,bottomMargin=50,title=title,author='EnvLoop').build(story,onFirstPage=page,onLaterPages=page)
 print(out)
def build(out):
 e=json.loads((ROOT/'outputs/evidence.json').read_text());text=manuscript(e)
 (ROOT/'outputs/CUA-RSIBench-Technical-Report.md').write_text(text)
 render(text,out)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',default='outputs/CUA-RSIBench-Technical-Report.pdf');a=p.parse_args();build(a.out)
