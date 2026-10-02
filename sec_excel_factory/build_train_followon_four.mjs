import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { FileBlob, SpreadsheetFile, Workbook } from '@oai/artifact-tool';

// TRAIN-only workbook authoring from reviewed original SEC facts. No final
// workbook, model result, or Office application is read by this builder.
const [, , reviewPath, outputDirectory] = process.argv;
if (!reviewPath || !outputDirectory) {
  throw new Error('usage: node build_train_followon_four.mjs REVIEW_PRIVATE_JSON OUTPUT_DIR');
}
const review = JSON.parse(await fs.readFile(reviewPath, 'utf8'));
if (review.schema !== 'envloop.sec_excel_train_followon_four_review.private.v1' ||
    review.cases?.length !== 4 ||
    review.cases.some(c => c.review_status !==
      'source_field_review_pass; independent_audit_pending' ||
      c.excel_web_admitted !== false || c.official_final_admitted !== false)) {
  throw new Error('reviewed_train_source_scope_changed');
}
const COLORS = {navy: '#173A5E', blue: '#185AA6',
  amber: '#FFF0BE', slate: '#415466'};
const NUM = '#,##0.0;(#,##0.0);-';
const ALLOWANCE = [
  ['gross_loans', 'Gross loans and leases'],
  ['allowance', 'Allowance for loan losses, magnitude'],
  ['net_loans', 'Filed net loans and leases'],
  ['beginning_allowance', 'Beginning allowance'],
  ['chargeoffs', 'Charge-offs, signed'],
  ['recoveries', 'Recoveries'],
  ['provision', 'Provision for credit losses'],
  ['other', 'Other allowance activity, signed'],
  ['ending_allowance', 'Filed ending allowance'],
];
const SEGMENT = [
  ['segment_sales_1', 'Segment 1 sales'],
  ['segment_sales_2', 'Segment 2 sales'],
  ['segment_sales_3', 'Segment 3 sales'],
  ['segment_sales_4', 'Segment 4 sales'],
  ['segment_profit_1', 'Segment 1 operating profit'],
  ['segment_profit_2', 'Segment 2 operating profit'],
  ['segment_profit_3', 'Segment 3 operating profit'],
  ['segment_profit_4', 'Segment 4 operating profit'],
  ['sales_adjustment', 'Signed sales eliminations or corporate amount'],
  ['profit_adjustment', 'Signed profit eliminations and corporate items'],
  ['filed_sales', 'Filed consolidated sales'],
  ['filed_profit', 'Filed consolidated operating profit'],
  ['customer_1', 'Customer category 1 sales'],
  ['customer_2', 'Customer category 2 sales'],
  ['customer_3', 'Customer category 3 sales'],
  ['customer_4', 'Customer category 4 sales'],
];
const SHEETS = {
  allowance: ['Loan summary', 'Loss scenario', 'Loan build',
    'Source facts', 'Source lineage', 'Checks'],
  segment: ['Segment summary', 'Segment scenario', 'Segment build',
    'Customer cut', 'Source facts', 'Source lineage', 'Checks'],
};
const put = (s,a,v) => {s.getRange(a).values = [[v]];};
const formula = (s,a,v) => {s.getRange(a).formulas = [[v]];};
function layout(s,title,headers,last,bottom) {
  s.showGridLines = false;
  put(s,'A1',title);
  s.getRange('A1').format.font =
    {name:'Arial',size:15,bold:true,color:COLORS.navy};
  s.getRange(`A4:${last}4`).values = [headers];
  s.getRange(`A4:${last}4`).format = {fill:COLORS.navy,
    font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},
    rowHeight:28,verticalAlignment:'center'};
  s.getRange(`A5:${last}${bottom}`).format.font =
    {name:'Arial',size:10,color:'#1D2933'};
  s.getRange('A:A').format.columnWidth = 55;
  s.getRange('B:C').format.columnWidth = 22;
  s.getRange(`B5:C${bottom}`).setNumberFormat(NUM);
  s.freezePanes.freezeRows(4);
}
function entries(c) {
  return c.profile === 'allowance' ? ALLOWANCE : SEGMENT;
}
function source(c,w) {
  const e = entries(c);
  const s = w.worksheets.getItem('Source facts');
  layout(s,'Original SEC 10-K facts (USD millions)',
    ['Filed measure',`Prior: ${c.periods[0].period_end}`,
      `Current: ${c.periods[1].period_end}`,'Scope and absence'],
    'D',4+e.length);
  s.getRange('D:D').format.columnWidth = 66;
  put(s,'A2',`Original filing: ${c.source.original_sec_url}`);
  s.getRange('A2').format.font = {name:'Arial',size:9,color:COLORS.slate};
  for (let i=0;i<e.length;i++) {
    const [key,baseLabel]=e[i]; const row=i+5;
    const label = key.startsWith('customer_') ?
      c.source.customer_labels?.[Number(key.slice(-1))-1] || baseLabel :
      key.startsWith('segment_sales_') ?
      `${c.source.segment_labels?.[Number(key.slice(-1))-1] || 'Segment '+key.slice(-1)} sales` :
      key.startsWith('segment_profit_') ?
      `${c.source.segment_labels?.[Number(key.slice(-1))-1] || 'Segment '+key.slice(-1)} operating profit` :
      baseLabel;
    put(s,`A${row}`,label);
    for(let p=0;p<2;p++) {
      const fact=c.periods[p].fields[key];
      if(!fact) throw new Error(`reviewed_source_fact_missing:${key}`);
      put(s,`${p?'C':'B'}${row}`,fact.value===null?'n.r.':fact.value);
    }
    const absent=c.periods.some(p=>p.fields[key].value===null);
    put(s,`D${row}`,absent ?
      'n.r. means not separately reported; zero is a calculation convention' :
      key==='profit_adjustment' ?
      'Signed eliminations and corporate items stay outside the four segment amounts' :
      key==='allowance' ?
      'Positive magnitude of a contra-asset; subtract from gross loans' : '');
  }
  s.getRange(`B5:C${4+e.length}`).format.font =
    {name:'Arial',size:10,color:COLORS.blue};
  const l=w.worksheets.getItem('Source lineage');
  layout(l,'Filed fact locators and source scope',
    ['Measure','Period end','Presence','XBRL concept',
      'Context / source row','Original filing'],
    'F',4+e.length*2);
  l.getRange('A:A').format.columnWidth=55;
  l.getRange('B:C').format.columnWidth=22;
  l.getRange('D:E').format.columnWidth=52;
  l.getRange('F:F').format.columnWidth=78;
  l.getRange(`D5:F${4+e.length*2}`).format.wrapText=true;
  l.getRange(`A5:F${4+e.length*2}`).format.rowHeight=28;
  let row=5;
  for(const period of c.periods) for(const [key] of e) {
    const fact=period.fields[key];
    const label=s.getRange(`A${e.findIndex(x=>x[0]===key)+5}`).values[0][0];
    l.getRange(`A${row}:F${row}`).values = [[
      label,period.period_end,fact.presence,fact.ixbrl_tag||'',
      fact.context_ref||fact.row_sha256||'',c.source.original_sec_url,
    ]];
    row++;
  }
}
function allowanceFormulas() {
  const m=new Map(); const add=(s,a,good,bad=null)=>m.set(`${s}!${a}`,{good,bad});
  const src=(c,r)=>`='Source facts'!${c}${r}`;
  for(const c of ['B','C']) {
    for(const [r,fr] of [[5,5],[6,6],[8,7],[10,8],[11,9],[12,10],
                           [13,11],[14,12],[16,13]]) add('Loan build',`${c}${r}`,src(c,fr));
    add('Loan build',`${c}7`,`=${c}5-${c}6`);
    add('Loan build',`${c}9`,`=${c}7-${c}8`);
    add('Loan build',`${c}15`,`=${c}10+${c}11+${c}12+${c}13+${c}14`);
    add('Loan build',`${c}17`,`=${c}15-${c}16`);
    add('Loan build',`${c}18`,`=${c}6/${c}5`);
    add('Loan build',`${c}19`,`=-${c}11/${c}5`);
  }
  add('Loan build','C20','=C6-B6');
  for(const [r,f] of [[5,"='Loan build'!C5"],[6,'=C5*(1+B6)'],
                       [7,"='Loan build'!C16"],[8,'=C7+B5'],
                       [9,'=C6-C8'],[10,'=C8/C6']]) add('Loss scenario',`C${r}`,f);
  for(const [r,f] of [[5,"='Loan build'!C8"],[6,"='Loan build'!C6"],
                       [7,"='Loan build'!C9"],[8,"='Loan build'!C17"],
                       [9,"='Loss scenario'!C9"]]) add('Loan summary',`B${r}`,f);
  add('Checks','B5',"='Loan build'!C9");
  add('Checks','B6',"='Loan build'!C17");
  add('Checks','B7',"='Loss scenario'!C9-('Loss scenario'!C6-'Loss scenario'!C8)");
  const bad={
    'Loan build!B5':src('C',5),
    'Loan build!C5':src('B',5),
    'Loan build!C6':src('B',6),
    'Loan build!C7':'=C5+C6',
    'Loan build!C9':'=C7+C8',
    'Loan build!C11':`=-'Source facts'!C9`,
    'Loan build!C13':src('B',11),
    'Loan build!C15':'=C10+C11+C13+C14',
    'Loan build!C17':'=C15+C16',
    'Loan build!C18':'=C5/C6',
    'Loss scenario!C9':'=C6+C8',
    'Loan summary!B9':"='Loan build'!C8",
  };
  for(const [key,value] of Object.entries(bad)) m.get(key).bad=value;
  return m;
}
function segmentFormulas(c) {
  const m=new Map(); const add=(s,a,good,bad=null)=>m.set(`${s}!${a}`,{good,bad});
  const src=(col,row)=>`='Source facts'!${col}${row}`;
  for(const col of ['B','C']) {
    for(const [r,sourceRow] of [
      [5,5],[6,6],[7,7],[8,8],[9,13],[11,15],
      [13,9],[14,10],[15,11],[16,12],[17,14],[19,16]])
      add('Segment build',`${col}${r}`,src(col,sourceRow));
    add('Segment build',`${col}10`,
      `=${col}5+${col}6+${col}7+${col}8+${col}9`);
    add('Segment build',`${col}12`,`=${col}10-${col}11`);
    add('Segment build',`${col}18`,
      `=${col}13+${col}14+${col}15+${col}16+${col}17`);
    add('Segment build',`${col}20`,`=${col}18-${col}19`);
    add('Segment build',`${col}21`,`=${col}13/${col}5`);
    for(let i=0;i<4;i++) {
      const key=`customer_${i+1}`;
      const p=col==='B'?0:1;
      add('Customer cut',`${col}${5+i}`,
        c.periods[p].fields[key].value===null ? '=0' : src(col,17+i));
    }
    add('Customer cut',`${col}9`,
      `=${col}5+${col}6+${col}7+${col}8`);
    add('Customer cut',`${col}10`,`='Segment build'!${col}11`);
    add('Customer cut',`${col}11`,`=${col}9-${col}10`);
  }
  add('Segment build','C22','=C11/B11-1');
  for(const [r,f] of [[5,"='Segment build'!C5"],[6,'=C5*B5'],
                       [7,"='Segment build'!C13"],
                       [8,"='Segment build'!C11+C6"],
                       [9,"='Segment build'!C19+C6*B6"],
                       [10,'=C9/C8'],[11,'=C7+C6*B6']])
    add('Segment scenario',`C${r}`,f);
  for(const [r,f] of [[5,"='Segment build'!C11"],
                       [6,"='Segment build'!C19"],
                       [7,"='Customer cut'!C11"],
                       [8,"='Segment scenario'!C8"],
                       [9,"='Segment scenario'!C9"]])
    add('Segment summary',`B${r}`,f);
  for(const [r,f] of [[5,"='Segment build'!C12"],
                       [6,"='Segment build'!C20"],
                       [7,"='Customer cut'!C11"],
                       [8,"='Segment scenario'!C8-('Segment build'!C11+'Segment scenario'!C6)"],
                       [9,"='Segment scenario'!C9-('Segment build'!C19+'Segment scenario'!C6*'Segment scenario'!B6)"]])
    add('Checks',`B${r}`,f);
  const bad={
    'Segment build!C5':src('B',5),
    'Segment build!C6':src('C',5),
    'Segment build!C9':src('C',17),
    'Segment build!C10':'=C5+C6+C7+C9',
    'Segment build!C12':'=C10+C11',
    'Segment build!C13':src('B',9),
    'Segment build!C17':`=-'Source facts'!C14`,
    'Segment build!C18':'=C13+C14+C15+C16',
    'Segment build!C20':'=C18+C19',
    'Customer cut!C9':'=C5+C6+C8',
    'Segment scenario!C8':"='Segment build'!C11",
    'Segment summary!B9':"='Segment build'!C19",
  };
  for(const [key,value] of Object.entries(bad)) m.get(key).bad=value;
  return m;
}
function working(c,w) {
  const prior=c.periods[0].period_end,current=c.periods[1].period_end;
  if(c.profile==='allowance') {
    const sum=w.worksheets.getItem('Loan summary');
    layout(sum,'Loan allowance and stress review (USD millions)',
      ['Measure','Result'],'B',9);
    sum.getRange('A5:A9').values=[
      ['Filed net loans'],['Filed allowance for loan losses'],
      ['Loan-base difference'],['Allowance-rollforward difference'],
      ['Modeled net loans after provision and portfolio change']];
    const scenario=w.worksheets.getItem('Loss scenario');
    layout(scenario,'Provision and loan-base scenario (USD millions)',
      ['Editable driver','Input','Result','Result description'],'D',10);
    scenario.getRange('D:D').format.columnWidth=50;
    scenario.getRange('A5:A10').values=[
      ['Additional provision'],['Change in gross loans'],[''],[''],[''],['']];
    scenario.getRange('D5:D10').values=[
      ['Filed gross loans'],['Modeled gross loans'],['Filed ending allowance'],
      ['Modeled allowance'],['Modeled net loans'],['Modeled allowance / loans']];
    put(scenario,'B5',c.scenario.additional_provision);
    put(scenario,'B6',c.scenario.gross_loan_change);
    scenario.getRange('B5:B6').format.fill=COLORS.amber;
    scenario.getRange('B6').setNumberFormat('0.0%');
    scenario.getRange('C10').setNumberFormat('0.0%');
    const build=w.worksheets.getItem('Loan build');
    layout(build,'Gross loans, allowance and loss activity',
      ['Measure',`Prior: ${prior}`,`Current: ${current}`],'C',20);
    build.getRange('A5:A20').values=[
      ['Gross loans and leases'],['Allowance for loan losses'],
      ['Rebuilt net loans'],['Filed net loans'],['Net-loan difference'],
      ['Beginning allowance'],['Charge-offs, signed'],['Recoveries'],
      ['Provision'],['Other signed allowance activity'],
      ['Rebuilt ending allowance'],['Filed ending allowance'],
      ['Allowance-rollforward difference'],['Allowance / gross loans'],
      ['Charge-offs / year-end gross loans'],['Change in allowance']];
    build.getRange('B18:C19').setNumberFormat('0.0%');
    const checks=w.worksheets.getItem('Checks');
    layout(checks,'Independent reconciliation differences (USD millions)',
      ['Check','Difference'],'B',7);
    checks.getRange('A5:A7').values=[
      ['Gross less allowance versus filed net loans'],
      ['Allowance activity versus filed ending balance'],
      ['Scenario net-loan arithmetic']];
    checks.getRange('B5:B7').setNumberFormat('0.00;(0.00);0.00');
  } else {
    const sum=w.worksheets.getItem('Segment summary');
    layout(sum,'Four-segment sales and operating profit (USD millions)',
      ['Measure','Result'],'B',9);
    sum.getRange('A5:A9').values=[
      ['Filed consolidated sales'],['Filed consolidated operating profit'],
      ['Customer-cut sales difference'],['Modeled consolidated sales'],
      ['Modeled consolidated operating profit']];
    const scenario=w.worksheets.getItem('Segment scenario');
    layout(scenario,'Selected-segment sensitivity (USD millions)',
      ['Editable driver','Input','Result','Result description'],'D',11);
    scenario.getRange('D:D').format.columnWidth=54;
    scenario.getRange('A5:A11').values=[
      ['Selected segment sales change'],['Incremental profit margin'],
      [''],[''],[''],[''],['']];
    scenario.getRange('D5:D11').values=[
      ['Filed selected-segment sales'],['Added selected-segment sales'],
      ['Filed selected-segment profit'],['Modeled consolidated sales'],
      ['Modeled consolidated profit'],['Modeled consolidated margin'],
      ['Modeled selected-segment profit']];
    put(scenario,'B5',c.scenario.selected_segment_sales_change);
    put(scenario,'B6',c.scenario.incremental_profit_margin);
    scenario.getRange('B5:B6').format.fill=COLORS.amber;
    scenario.getRange('B5:B6').setNumberFormat('0.0%');
    scenario.getRange('C10').setNumberFormat('0.0%');
    const build=w.worksheets.getItem('Segment build');
    layout(build,'Four-segment sales and profit reconciliation',
      ['Measure',`Prior: ${prior}`,`Current: ${current}`],'C',22);
    build.getRange('A5:A22').values=[
      ...c.source.segment_labels.map(x=>[`${x} sales`]),
      ['Signed sales adjustment'],['Rebuilt consolidated sales'],
      ['Filed consolidated sales'],['Sales difference'],
      ...c.source.segment_labels.map(x=>[`${x} operating profit`]),
      ['Signed profit adjustment'],['Rebuilt consolidated profit'],
      ['Filed consolidated profit'],['Profit difference'],
      ['Selected-segment operating margin'],['Filed sales change']];
    build.getRange('B21:C22').setNumberFormat('0.0%');
    const cut=w.worksheets.getItem('Customer cut');
    layout(cut,'Independent customer-sales classification',
      ['Customer category',`Prior: ${prior}`,`Current: ${current}`],'C',11);
    cut.getRange('A5:A11').values=[
      ...c.source.customer_labels.map(x=>[x]),
      ['Rebuilt customer-cut sales'],['Filed consolidated sales'],
      ['Customer-cut difference']];
    const checks=w.worksheets.getItem('Checks');
    layout(checks,'Independent reconciliation differences (USD millions)',
      ['Check','Difference'],'B',9);
    checks.getRange('A5:A9').values=[
      ['Four segments plus sales adjustment versus filed sales'],
      ['Four segments plus profit adjustment versus filed profit'],
      ['Customer categories versus filed sales'],
      ['Scenario sales identity'],['Scenario profit identity']];
    checks.getRange('B5:B9').setNumberFormat('0.00;(0.00);0.00');
  }
}
function apply(w,map,kind) {
  for(const [key,x] of map) {
    const [sheet,address]=key.split('!');
    formula(w.worksheets.getItem(sheet),address,
      kind==='seed'&&x.bad?x.bad:x.good);
  }
}
const targets=map=>[...map].filter(([,x])=>x.bad!==null).map(([k])=>k).sort();
function previewRange(name) {
  if(name==='Source lineage') return 'A1:F38';
  if(name==='Source facts') return 'A1:D22';
  if(name.endsWith('scenario')) return 'A1:D13';
  if(name.endsWith('summary')||name==='Checks') return 'A1:B12';
  return 'A1:C24';
}
async function make(c,kind,dir) {
  const w=Workbook.create();
  for(const name of SHEETS[c.profile]) w.worksheets.add(name);
  source(c,w); working(c,w);
  const map=c.profile==='allowance'?allowanceFormulas():segmentFormulas(c);
  if(targets(map).length!==12) throw new Error('target_repair_depth_not_twelve');
  apply(w,map,kind);
  w.recalculate();
  const out=await SpreadsheetFile.exportXlsx(w);
  const file=path.join(dir,`${kind}.xlsx`);
  await out.save(file);
  if(kind==='positive') for(const name of SHEETS[c.profile]) {
    const image=await w.render({sheetName:name,range:previewRange(name),
      scale:1.3,format:'png'});
    await fs.writeFile(path.join(dir,
      `preview-${name.toLowerCase().replaceAll(' ','-')}.png`),
      new Uint8Array(await image.arrayBuffer()));
  }
  const raw=await fs.readFile(file);
  return {sha256:createHash('sha256').update(raw).digest('hex'),
    bytes:raw.length,target_cells:targets(map)};
}
async function secureTree(dir) {
  await fs.chmod(dir,0o700);
  for(const entry of await fs.readdir(dir,{withFileTypes:true})) {
    const p=path.join(dir,entry.name);
    if(entry.isSymbolicLink()) throw new Error('private_workbook_symlink_forbidden');
    if(entry.isDirectory()) await secureTree(p);
    else await fs.chmod(p,0o600);
  }
}
if(process.argv.includes('--render-only')) {
  for(const c of review.cases) {
    const dir=path.join(outputDirectory,`case-${String(c.case_index).padStart(2,'0')}`);
    const w=await SpreadsheetFile.importXlsx(
      await FileBlob.load(path.join(dir,'positive.xlsx')));
    for(const name of SHEETS[c.profile]) {
      const blob=await w.render({sheetName:name,range:previewRange(name),
        scale:1.3,format:'png'});
      const target=path.join(dir,
        `preview-${name.toLowerCase().replaceAll(' ','-')}.png`);
      await fs.writeFile(target,new Uint8Array(await blob.arrayBuffer()));
      await fs.chmod(target,0o600);
    }
  }
  console.log(JSON.stringify({status:'existing_previews_refreshed',
    workbook_edits:0}));
  process.exit(0);
}
await fs.mkdir(outputDirectory,{recursive:true,mode:0o700});
const manifest={schema:'envloop.sec_excel_train_followon_four_workbooks.private.v1',
  review_sha256:createHash('sha256').update(await fs.readFile(reviewPath)).digest('hex'),
  status:'TRAIN-only offline workbooks; independent OOXML audit pending',cases:[]};
for(const c of review.cases) {
  const dir=path.join(outputDirectory,`case-${String(c.case_index).padStart(2,'0')}`);
  await fs.mkdir(dir,{recursive:true,mode:0o700});
  const seed=await make(c,'seed',dir);
  const positive=await make(c,'positive',dir);
  manifest.cases.push({case_index:c.case_index,profile:c.profile,seed,positive});
}
const manifestPath=path.join(outputDirectory,'workbooks-manifest.private.json');
await fs.writeFile(manifestPath,JSON.stringify(manifest,null,2)+'\n',
  {mode:0o600,flag:'wx'});
await secureTree(outputDirectory);
console.log(JSON.stringify({status:'four_followon_workbook_pairs_created',
  cases:manifest.cases.length,repairs_per_case:manifest.cases.map(x=>x.seed.target_cells.length),
  manifest_sha256:createHash('sha256').update(await fs.readFile(manifestPath)).digest('hex')}));
