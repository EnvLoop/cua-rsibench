"""Public python-pptx generator; a new artifact epoch, never old byte identity."""
import argparse
import json
import shutil
from pathlib import Path
from hashlib import sha256
from zipfile import ZipFile, ZIP_DEFLATED
from xml.etree import ElementTree as ET
import io
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from . import verify


def build(task, output):
    pres=Presentation();pres.slide_width=Inches(13.333333);pres.slide_height=Inches(7.5)
    def box(slide,name,text,x,y,w,h,size=22):
        shape=slide.shapes.add_textbox(Inches(x/96),Inches(y/96),Inches(w/96),Inches(h/96));shape.name=name
        shape.text_frame.text=str(text)
        for p in shape.text_frame.paragraphs:
            p.font.name='Arial';p.font.size=Pt(size);p.font.color.rgb=RGBColor.from_string('183044')
        return shape
    def page(title,n):
        s=pres.slides.add_slide(pres.slide_layouts[6]);box(s,f'slide_{n}_title',title,64,35,1150,80,30)
        box(s,f'slide_{n}_footer',f'Economic monitoring brief | {task["country_name"]} | {n}/7',64,664,1150,32,12)
        s.notes_slide.notes_text_frame.text='World Bank WDI; pinned public observations. Committee thresholds and draft errors are benchmark-authored.'
        return s
    def table(s,values,x,y,w,h):
        t=s.shapes.add_table(len(values),len(values[0]),Inches(x/96),Inches(y/96),Inches(w/96),Inches(h/96)).table
        for r,row in enumerate(values):
            for c,value in enumerate(row):
                t.cell(r,c).text=str(value)
                for p in t.cell(r,c).text_frame.paragraphs:p.font.name='Arial';p.font.size=Pt(14)
        return t
    s=page(task['country_name']+' economic monitoring',1)
    box(s,'brief_heading',task['heading'],72,142,1134,80,22);box(s,'target__summary',task['draft']['summary'],76,276,1110,100,28)
    box(s,'brief_method','Reconcile the flagged fields using the pinned evidence. Preserve all other content.',76,430,1080,105,20)
    s=page('WDI source observations',2)
    values=[['Year','GDP, USD bn','GDP/person, USD','CPI, %','Population, m','Unemployment, %']]
    for year in ('2019','2020','2021','2022','2023','2024'):
        f=task['facts'][year];values.append([year,f'{f["NY.GDP.MKTP.CD"]/1e9:.1f}',f'{f["NY.GDP.PCAP.CD"]:.0f}',
            f'{f["FP.CPI.TOTL.ZG"]:.2f}',f'{f["SP.POP.TOTL"]/1e6:.2f}',f'{f["SL.UEM.TOTL.ZS"]:.2f}'])
    table(s,values,61,210,1156,365);box(s,'source_attribution','World Development Indicators | pinned public source | CC BY 4.0',66,595,1120,32,14)
    s=page('Indicator trend, 2019-2024',3)
    data=CategoryChartData();data.categories=task['chart']['categories']
    for series in task['chart']['series']:data.add_series(series['name'],series['values'])
    chart=s.shapes.add_chart(XL_CHART_TYPE.LINE_MARKERS,Inches(83/96),Inches(175/96),Inches(1090/96),Inches(425/96),data).chart
    chart.has_legend=len(task['chart']['series'])>1
    box(s,'chart_attribution',task['draft'].get('chart_caption','Chart data: the rounded WDI observations on slide 2.'),70,605,1090,33,14)
    s=page('Calculation review',4);box(s,'calculation_rule','Review rule: '+task['calculation']['rule'],72,140,1105,72,21)
    table(s,[['Field','Analyst draft','Use'],['Derived measure',task['draft']['ledger'],task['calculation']['window']],
        ['Unit and rule',task['calculation']['unit'],f'Simulated threshold: {task["calculation"]["simulated_threshold"]:.1f}']],72,253,1128,236)
    s=page('Analyst interpretation',5);box(s,'target__interpretation',task['draft']['interpretation'],75,280,1085,165,25)
    box(s,'interpretation_caveat','Rate differences use percentage points; percent growth uses the stated base year.',74,524,1100,70,18)
    s=page('Committee decision',6);box(s,'target__decision',task['draft']['decision'],74,295,1100,140,25)
    box(s,'decision_scope','The committee threshold is benchmark-authored. Preserve the source evidence and unrelated fields.',74,530,1090,70,18)
    s=page('Method and attribution',7);box(s,'method_1','Observed values: pinned World Development Indicators, 2019-2024.',75,150,1090,90,22)
    box(s,'method_2','Calculations use the displayed rounded values and the stated committee rule.',75,283,1090,86,22)
    box(s,'method_3','The committee threshold and intentional draft defects are authored benchmark scenarios.',75,417,1090,86,22)
    box(s,'target__attribution',task['draft']['attribution'],75,552,1090,62,15)
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);pres.save(output)
    # The original verifier binds literal native chart labels plus the embedded
    # workbook. python-pptx emits a strRef label; select the equivalent literal
    # OOXML tx/v representation in this new generator epoch only.
    with ZipFile(output) as archive:members={info.filename:archive.read(info) for info in archive.infolist()}
    ns='{http://schemas.openxmlformats.org/drawingml/2006/chart}'
    for name,raw in list(members.items()):
        if name.startswith('ppt/charts/chart') and name.endswith('.xml'):
            chart_xml=ET.fromstring(raw)
            for series,declared in zip(chart_xml.iter(ns+'ser'),task['chart']['series'],strict=True):
                tx=series.find(ns+'tx');tx.clear();ET.SubElement(tx,ns+'v').text=declared['name']
            for formula in chart_xml.iter(ns+'f'):
                if formula.text:formula.text=formula.text.replace('$C$','$D$')
            members[name]=ET.tostring(chart_xml,encoding='utf-8',xml_declaration=True)
        if name.startswith('ppt/embeddings/') and name.endswith('.xlsx'):
            with ZipFile(io.BytesIO(raw)) as book:parts={part:book.read(part) for part in book.namelist()}
            sn='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
            strings=ET.fromstring(parts['xl/sharedStrings.xml']);texts=[''.join(node.itertext()) for node in strings]
            sheet=ET.fromstring(parts['xl/worksheets/sheet1.xml'])
            for cell in sheet.iter(sn+'c'):
                if cell.get('r','').startswith('C'):cell.set('r','D'+cell.get('r')[1:])
                if cell.get('t')=='s':
                    value=cell.find(sn+'v');text=texts[int(value.text)];cell.remove(value);cell.set('t','inlineStr')
                    ET.SubElement(ET.SubElement(cell,sn+'is'),sn+'t').text=text
            parts['xl/worksheets/sheet1.xml']=ET.tostring(sheet,encoding='utf-8',xml_declaration=True)
            buffer=io.BytesIO()
            with ZipFile(buffer,'w',ZIP_DEFLATED) as book:
                for part,data in parts.items():book.writestr(part,data)
            members[name]=buffer.getvalue()
    with ZipFile(output,'w',ZIP_DEFLATED) as archive:
        for name,raw in members.items():archive.writestr(name,raw)
    output.chmod(0o600)
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--task');p.add_argument('--output');p.add_argument('--plan-root');p.add_argument('--output-root')
    args=p.parse_args()
    if args.plan_root:
        if args.task or args.output or not args.output_root:raise ValueError('Use plan-root/output-root for full portable generation')
        source_root=Path(args.plan_root);root=Path(args.output_root)
        if root.exists():raise ValueError('New portable artifact epoch requires fresh output')
        plan=json.loads((source_root/'candidate-plan.private.json').read_bytes());receipts=[]
        for split,count in (('train',20),('selection',20),('final_candidate',100)):
            if len(plan['sets'][split])!=count:raise ValueError('Portable full-generation requires exact20/20/100')
            for task in plan['sets'][split]:
                origin=source_root/'packages'/split/task['task_id'];package=root/'packages'/split/task['task_id'];package.mkdir(mode=0o700,parents=True)
                (package/'task.private.json').write_bytes((origin/'task.private.json').read_bytes());(package/'task.private.json').chmod(0o600)
                for name in ('source-snapshot.private.json','source-provenance.private.json','source-country.private.zip'):
                    if (origin/name).exists():shutil.copyfile(origin/name,package/name);(package/name).chmod(0o600)
                build(task,package/'source.pptx');receipts.append(verify.calibrate(package))
        (root/'portable-build-receipt.private.json').write_text(json.dumps({'schema':'ppt-wdi-portable-build-all-v1','artifact_epoch':'python-pptx-new-bytes','rows':receipts,'native_qualified':False})+'\n')
        print(json.dumps({'portable_decks':len(receipts),'all_offline_controls_pass':all(r['offline_controls_pass'] for r in receipts),'native_qualified':False}));return
    if not args.task or not args.output:raise ValueError('Use task/output or plan-root/output-root')
    task_path=Path(args.task);task=json.loads(task_path.read_bytes());output=build(task,args.output)
    for name in ('source-snapshot.private.json','source-provenance.private.json','source-country.private.zip'):
        origin=task_path.parent/name
        if origin.exists():shutil.copyfile(origin,output.parent/name);(output.parent/name).chmod(0o600)
    oracle=verify.freeze(output,task)
    print(json.dumps({'schema':'ppt-wdi-portable-build-v1','package_epoch':'python-pptx-new-bytes','output_sha256':sha256(output.read_bytes()).hexdigest(),
        'baseline_score':verify.verify(output,output,oracle)['score'],'native_qualified':False}))


if __name__=='__main__':main()
