import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { FileBlob, SpreadsheetFile, Workbook } from '@oai/artifact-tool';

// TRAIN-only source-transfer workbooks. Facts and case identities remain in
// evaluator-private reviewed packages, never in this authoring source.
const [, , reviewPath, outputDirectory] = process.argv;
if (!reviewPath || !outputDirectory) {
  throw new Error('usage: node build_train_remaining_four.mjs REVIEW_PRIVATE_JSON OUTPUT_DIR');
}
const review = JSON.parse(await fs.readFile(reviewPath, 'utf8'));
if (review.schema !== 'envloop.sec_excel_train_remaining_four_review.private.v1' ||
    review.cases?.length !== 4 ||
    review.cases.some(c => c.review_status !==
      'source_field_review_pass; independent_audit_pending' ||
      c.excel_web_admitted !== false || c.official_final_admitted !== false)) {
  throw new Error('reviewed_train_source_scope_changed');
}
const COLORS = {navy:'#173A5E',blue:'#185AA6',amber:'#FFF0BE',slate:'#415466'};
const NUM = '#,##0.0;(#,##0.0);-';
const PENSION = [
  ['opening_assets','Opening international-plan assets'],
  ['acquisition','Acquisition or divestiture asset change'],
  ['return','Actual return on plan assets'],
  ['employer','Employer contributions'],
  ['participant','Participant contributions'],
  ['fx_or_other','Currency and other filed asset activity'],
  ['benefits','Benefits paid, signed'],
  ['settlements_or_other','Settlements and related items, signed'],
  ['closing_assets','Filed closing plan assets'],
  ['obligation','Projected benefit obligation'],
  ['reported_funded','Filed funded status'],
];
const AFS = [
  ['amortized_cost','AFS amortized cost before allowance'],
  ['acl_signed','Allowance for credit losses, signed'],
  ['unrealized_gains','Gross unrealized gains'],
  ['unrealized_losses_signed','Gross unrealized losses, signed'],
  ['fair_value','Filed AFS fair value'],
  ['loss_age_lt_fair','Loss-position fair value, under 12 months'],
  ['loss_age_lt_loss','Loss-position gross losses, under 12 months'],
  ['loss_age_ge_fair','Loss-position fair value, 12 months or more'],
  ['loss_age_ge_loss','Loss-position gross losses, 12 months or more'],
  ['loss_position_fair','Filed fair value of loss-position subset'],
  ['loss_position_loss','Filed gross losses of loss-position subset'],
];
const SHEETS = {
  pension_full:['Pension summary','Plan scenario','Asset build',
    'Source facts','Source lineage','Checks'],
  afs:['AFS summary','Rate scenario','Fair bridge','Loss aging',
    'Maturity ladder','Source facts','Source lineage','Checks'],
};
const put=(s,a,v)=>{s.getRange(a).values=[[v]];};
const formula=(s,a,v)=>{s.getRange(a).formulas=[[v]];};
function layout(s,title,headers,last,bottom) {
  s.showGridLines=false;
  put(s,'A1',title);
  s.getRange('A1').format.font={name:'Arial',size:15,bold:true,color:COLORS.navy};
  s.getRange(`A4:${last}4`).values=[headers];
  s.getRange(`A4:${last}4`).format={fill:COLORS.navy,
    font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},
    rowHeight:28,verticalAlignment:'center'};
  s.getRange(`A5:${last}${bottom}`).format.font=
    {name:'Arial',size:10,color:'#1D2933'};
  s.getRange('A:A').format.columnWidth=55;
  s.getRange('B:C').format.columnWidth=22;
  s.getRange(`B5:C${bottom}`).setNumberFormat(NUM);
  s.freezePanes.freezeRows(4);
}
function entries(c) {return c.profile==='pension_full'?PENSION:AFS;}
function source(c,w) {
  const e=entries(c); const s=w.worksheets.getItem('Source facts');
  const last=c.profile==='afs'?28:15;
  layout(s,'Original SEC 10-K facts (USD millions)',
    ['Filed measure',`Prior: ${c.periods[0].period_end}`,
      `Current: ${c.periods[1].period_end}`,'Scope and absence'],'D',last);
  s.getRange('D:D').format.columnWidth=66;
  put(s,'A2',`Original filing: ${c.source.original_sec_url}`);
  s.getRange('A2').format.font={name:'Arial',size:9,color:COLORS.slate};
  for(let i=0;i<e.length;i++) {
    const [key,label]=e[i];const row=i+5;
    put(s,`A${row}`,label);
    for(let p=0;p<2;p++) {
      const fact=c.periods[p].fields[key];
      if(!fact) throw new Error(`reviewed_source_fact_missing:${key}`);
      put(s,`${p?'C':'B'}${row}`,fact.value===null?'n.r.':fact.value);
    }
    const absent=c.periods.some(p=>p.fields[key].value===null);
    put(s,`D${row}`,absent ?
      'n.r. is not a filed zero; zero is used only in the authored bridge' :
      key==='fx_or_other' ? c.source.fx_scope :
      key==='loss_position_loss' ?
      'Loss-position aging may be narrower than total gross unrealized loss' :
      key==='acl_signed' ?
      'Contra-asset allowance stays signed in the fair-value bridge' : '');
  }
  s.getRange(`B5:C${4+e.length}`).format.font=
    {name:'Arial',size:10,color:COLORS.blue};
  const lineage=w.worksheets.getItem('Source lineage');
  const extra=c.profile==='afs'?12:0;
  layout(lineage,'Filed fact locators and source scope',
    ['Measure','Period end','Presence','XBRL concept',
      'Context / source row','Original filing'],
    'F',4+e.length*2+extra);
  lineage.getRange('A:A').format.columnWidth=55;
  lineage.getRange('B:C').format.columnWidth=22;
  lineage.getRange('D:E').format.columnWidth=52;
  lineage.getRange('F:F').format.columnWidth=78;
  lineage.getRange(`D5:F${4+e.length*2+extra}`).format.wrapText=true;
  lineage.getRange(`A5:F${4+e.length*2+extra}`).format.rowHeight=28;
  let row=5;
  for(const period of c.periods) for(const [key,label] of e) {
    const fact=period.fields[key];
    lineage.getRange(`A${row}:F${row}`).values=[[
      label,period.period_end,fact.presence,fact.ixbrl_tag||'',
      fact.context_ref||fact.row_sha256||'',c.source.original_sec_url]];
    row++;
  }
  if(c.profile==='afs') {
    put(s,'A16','Current maturity buckets, filed basis');
    s.getRange('A16:D16').format={fill:COLORS.navy,
      font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'}};
    for(let i=0;i<5;i++) {
      const bucket=c.maturity.buckets[i];
      put(s,`A${17+i}`,`${bucket.label} cost`);
      put(s,`C${17+i}`,bucket.cost.value);
      put(s,`A${22+i}`,`${bucket.label} fair value`);
      put(s,`C${22+i}`,bucket.fair.value);
      for(const [key,fact] of [['cost',bucket.cost],['fair',bucket.fair]]) {
        const label=`${bucket.label} ${key}`;
        lineage.getRange(`A${row}:F${row}`).values=[[
          label,c.maturity.period_end,fact.presence,fact.ixbrl_tag||'',
          fact.context_ref||fact.row_sha256||'',c.source.original_sec_url]];
        row++;
      }
    }
    put(s,'A27','Filed maturity total cost');
    put(s,'C27',c.maturity.filed_total_cost.value);
    put(s,'A28','Filed maturity total fair value');
    put(s,'C28',c.maturity.filed_total_fair.value);
    put(s,'D27',c.maturity.cost_basis==='net_of_allowance' ?
      'Maturity cost is net of the filed credit-loss allowance' :
      'Maturity cost is gross amortized cost');
    for(const [label,fact] of [
      ['Filed maturity total cost',c.maturity.filed_total_cost],
      ['Filed maturity total fair value',c.maturity.filed_total_fair]]) {
      lineage.getRange(`A${row}:F${row}`).values=[[
        label,c.maturity.period_end,fact.presence,fact.ixbrl_tag||'',
        fact.context_ref||fact.row_sha256||'',c.source.original_sec_url]];
      row++;
    }
    s.getRange('C17:C28').format.font=
      {name:'Arial',size:10,color:COLORS.blue};
  }
}
function pensionFormulas(c) {
  const m=new Map();const add=(s,a,good,bad=null)=>m.set(`${s}!${a}`,{good,bad});
  const src=(col,row)=>`='Source facts'!${col}${row}`;
  for(const col of ['B','C']) {
    const p=col==='B'?0:1;
    for(const [r,fr,key] of [[5,5,'opening_assets'],[6,6,'acquisition'],
      [7,7,'return'],[8,8,'employer'],[9,9,'participant'],
      [10,10,'fx_or_other'],[11,11,'benefits'],
      [12,12,'settlements_or_other'],[14,13,'closing_assets'],
      [16,14,'obligation'],[18,15,'reported_funded']])
      add('Asset build',`${col}${r}`,
        c.periods[p].fields[key].value===null?'=0':src(col,fr));
    add('Asset build',`${col}13`,
      `=${col}5+${col}6+${col}7+${col}8+${col}9+${col}10+${col}11+${col}12`);
    add('Asset build',`${col}15`,`=${col}13-${col}14`);
    add('Asset build',`${col}17`,`=${col}14-${col}16`);
    add('Asset build',`${col}19`,`=${col}17-${col}18`);
    add('Asset build',`${col}20`,`=${col}9/${col}14`);
    add('Asset build',`${col}21`,`=${col}10/${col}14`);
  }
  for(const [r,f] of [[5,"='Asset build'!C14"],
    [6,"='Asset build'!C5*B6"],[7,'=B7'],
    [8,'=C5+B5+C6+C7'],[9,"='Asset build'!C16"],
    [10,'=C9*(1+B8)'],[11,'=C8-C10']])
    add('Plan scenario',`C${r}`,f);
  for(const [r,f] of [[5,"='Asset build'!C17"],
    [6,"='Asset build'!B17"],[7,"='Asset build'!C15"],
    [8,"='Asset build'!C20"],[9,"='Plan scenario'!C11"]])
    add('Pension summary',`B${r}`,f);
  add('Checks','B5',"='Asset build'!C15");
  add('Checks','B6',"='Asset build'!C19");
  add('Checks','B7',
    "='Plan scenario'!C11-('Plan scenario'!C8-'Plan scenario'!C10)");
  const bad={
    'Asset build!C5':src('B',5),
    'Asset build!C7':src('B',7),
    'Asset build!C8':src('B',8),
    'Asset build!C9':src('C',8),
    'Asset build!C10':`=-'Source facts'!C10`,
    'Asset build!C11':`=-'Source facts'!C11`,
    'Asset build!C12':src('B',12),
    'Asset build!C13':'=C5+C6+C7+C8+C9+C11+C12',
    'Asset build!C15':'=C13+C14',
    'Asset build!C17':'=C16-C14',
    'Plan scenario!C11':'=C8+C10',
    'Pension summary!B9':"='Asset build'!C17",
  };
  for(const [key,value] of Object.entries(bad)) m.get(key).bad=value;
  return m;
}
function afsFormulas() {
  const m=new Map();const add=(s,a,good,bad=null)=>m.set(`${s}!${a}`,{good,bad});
  const src=(col,row)=>`='Source facts'!${col}${row}`;
  for(const col of ['B','C']) {
    for(const [r,fr] of [[5,5],[6,6],[7,7],[8,8],[10,9]])
      add('Fair bridge',`${col}${r}`,src(col,fr));
    add('Fair bridge',`${col}9`,
      `=${col}5+${col}6+${col}7+${col}8`);
    add('Fair bridge',`${col}11`,`=${col}9-${col}10`);
    add('Fair bridge',`${col}12`,`=-${col}8-${src(col,15).slice(1)}`);
    for(const [r,fr] of [[5,10],[6,11],[7,12],[8,13],[10,14],[13,15]])
      add('Loss aging',`${col}${r}`,src(col,fr));
    add('Loss aging',`${col}9`,`=${col}5+${col}7`);
    add('Loss aging',`${col}11`,`=${col}9-${col}10`);
    add('Loss aging',`${col}12`,`=${col}6+${col}8`);
    add('Loss aging',`${col}14`,`=${col}12-${col}13`);
  }
  add('Fair bridge','C13','=C10/B10-1');
  for(let i=0;i<5;i++) {
    add('Maturity ladder',`C${5+i}`,src('C',17+i));
    add('Maturity ladder',`C${11+i}`,src('C',22+i));
  }
  add('Maturity ladder','C16','=C5+C6+C7+C8+C9');
  add('Maturity ladder','C17',src('C',27));
  add('Maturity ladder','C18','=C16-C17');
  add('Maturity ladder','C19','=C11+C12+C13+C14+C15');
  add('Maturity ladder','C20',src('C',28));
  add('Maturity ladder','C21','=C19-C20');
  add('Maturity ladder','C22','=(C14+C15)/C20');
  for(const [r,f] of [[5,"='Maturity ladder'!C20"],
    [6,"='Maturity ladder'!C12*B5"],
    [7,"='Maturity ladder'!C14*B6"],
    [8,"='Maturity ladder'!C15*B7"],
    [9,'=C5-C6-C7-C8'],[10,"=C9-'Fair bridge'!C10"]])
    add('Rate scenario',`C${r}`,f);
  for(const [r,f] of [[5,"='Fair bridge'!C10"],
    [6,"='Fair bridge'!B10"],[7,"='Fair bridge'!C12"],
    [8,"='Maturity ladder'!C22"],
    [9,"='Rate scenario'!C9"]]) add('AFS summary',`B${r}`,f);
  for(const [r,f] of [[5,"='Fair bridge'!C11"],
    [6,"='Loss aging'!C11"],[7,"='Loss aging'!C14"],
    [8,"='Maturity ladder'!C18"],[9,"='Maturity ladder'!C21"],
    [10,"='Rate scenario'!C9-('Rate scenario'!C5-'Rate scenario'!C6-'Rate scenario'!C7-'Rate scenario'!C8)"]])
    add('Checks',`B${r}`,f);
  const bad={
    'Fair bridge!C5':src('B',5),
    'Fair bridge!C6':`=-'Source facts'!C6`,
    'Fair bridge!C7':src('B',7),
    'Fair bridge!C8':src('B',8),
    'Fair bridge!C9':'=C5+C7+C8',
    'Fair bridge!C11':'=C9+C10',
    'Loss aging!C9':'=C5',
    'Loss aging!C12':'=C6-C8',
    'Maturity ladder!C16':'=C5+C6+C7+C8',
    'Maturity ladder!C19':'=C11+C12+C13+C15',
    'Rate scenario!C9':'=C5+C6+C7+C8',
    'AFS summary!B9':"='Fair bridge'!C10",
  };
  for(const [key,value] of Object.entries(bad)) m.get(key).bad=value;
  return m;
}
function working(c,w) {
  const prior=c.periods[0].period_end,current=c.periods[1].period_end;
  if(c.profile==='pension_full') {
    const sum=w.worksheets.getItem('Pension summary');
    layout(sum,'International pension funding (USD millions)',
      ['Measure','Result'],'B',9);
    sum.getRange('A5:A9').values=[
      ['Current filed funded status'],['Prior filed funded status'],
      ['Full asset-movement difference'],
      ['Participant contributions / closing assets'],
      ['Modeled funded status']];
    sum.getRange('B8').setNumberFormat('0.0%');
    const scenario=w.worksheets.getItem('Plan scenario');
    layout(scenario,'Plan asset and obligation scenario (USD millions)',
      ['Editable driver','Input','Result','Result description'],'D',11);
    scenario.getRange('D:D').format.columnWidth=50;
    scenario.getRange('A5:A11').values=[
      ['Additional sponsor contribution'],['Change in asset return'],
      ['Currency-related adjustment'],['Change in obligation'],
      [''],[''],['']];
    scenario.getRange('D5:D11').values=[
      ['Filed closing plan assets'],['Asset-return effect on opening assets'],
      ['Added currency-related amount'],['Modeled closing plan assets'],
      ['Filed projected benefit obligation'],['Modeled obligation'],
      ['Modeled funded status']];
    for(const [r,key] of [[5,'sponsor_contribution'],[6,'return_change'],
                          [7,'fx_shift'],[8,'obligation_change']])
      put(scenario,`B${r}`,c.scenario[key]);
    scenario.getRange('B5:B8').format.fill=COLORS.amber;
    scenario.getRange('B6').setNumberFormat('0.0%');
    scenario.getRange('B8').setNumberFormat('0.0%');
    const build=w.worksheets.getItem('Asset build');
    layout(build,'Full international-plan asset and funded-status bridge',
      ['Measure',`Prior: ${prior}`,`Current: ${current}`],'C',21);
    build.getRange('A5:A21').values=[
      ['Opening plan assets'],['Acquisition or divestiture'],
      ['Actual return'],['Employer contributions'],
      ['Participant contributions'],[c.source.fx_scope],
      ['Benefits paid, signed'],['Settlements and related items, signed'],
      ['Rebuilt closing assets'],['Filed closing assets'],
      ['Full asset-movement difference'],['Projected benefit obligation'],
      ['Calculated funded status'],['Filed funded status'],
      ['Funded-status difference'],
      ['Participant contributions / closing assets'],
      ['Currency and other activity / closing assets']];
    build.getRange('B20:C21').setNumberFormat('0.0%');
    const checks=w.worksheets.getItem('Checks');
    layout(checks,'Independent reconciliation differences (USD millions)',
      ['Check','Difference'],'B',7);
    checks.getRange('A5:A7').values=[
      ['Full asset movement versus filed closing assets'],
      ['Calculated versus filed funded status'],
      ['Scenario funded-status arithmetic']];
    checks.getRange('B5:B7').setNumberFormat('0.00;(0.00);0.00');
  } else {
    const sum=w.worksheets.getItem('AFS summary');
    layout(sum,'AFS fair value and maturity stress (USD millions)',
      ['Measure','Result'],'B',9);
    sum.getRange('A5:A9').values=[
      ['Current filed AFS fair value'],['Prior filed AFS fair value'],
      ['Gross-loss difference outside aging subset'],
      ['After-ten-year and no-date fair-value share'],
      ['Modeled AFS fair value after selected haircuts']];
    sum.getRange('B8').setNumberFormat('0.0%');
    const scenario=w.worksheets.getItem('Rate scenario');
    layout(scenario,'Selected maturity-bucket haircuts (USD millions)',
      ['Editable haircut','Input','Result','Result description'],'D',10);
    scenario.getRange('D:D').format.columnWidth=50;
    scenario.getRange('A5:A10').values=[
      ['Years two through five'],['After year ten'],
      ['No single maturity date'],[''],[''],['']];
    scenario.getRange('D5:D10').values=[
      ['Filed total AFS maturity fair value'],
      ['Fair-value reduction, years two through five'],
      ['Fair-value reduction, after year ten'],
      ['Fair-value reduction, no single date'],
      ['Modeled total fair value'],
      ['Modeled less filed AFS fair value']];
    for(const [r,key] of [[5,'years_two_five_haircut'],
                          [6,'after_ten_haircut'],
                          [7,'no_single_date_haircut']])
      put(scenario,`B${r}`,c.scenario[key]);
    scenario.getRange('B5:B7').format.fill=COLORS.amber;
    scenario.getRange('B5:B7').setNumberFormat('0.0%');
    const bridge=w.worksheets.getItem('Fair bridge');
    layout(bridge,'AFS cost, allowance and unrealized-value bridge',
      ['Measure',`Prior: ${prior}`,`Current: ${current}`],'C',13);
    bridge.getRange('A5:A13').values=[
      ['Amortized cost before allowance'],['Credit-loss allowance, signed'],
      ['Gross unrealized gains'],['Gross unrealized losses, signed'],
      ['Rebuilt AFS fair value'],['Filed AFS fair value'],
      ['Fair-value difference'],
      ['Gross loss outside filed aging subset'],
      ['Filed fair-value change']];
    bridge.getRange('C13').setNumberFormat('0.0%');
    const aging=w.worksheets.getItem('Loss aging');
    layout(aging,'AFS unrealized-loss position by age',
      ['Measure',`Prior: ${prior}`,`Current: ${current}`],'C',14);
    aging.getRange('A5:A14').values=[
      ['Fair value, under 12 months'],['Gross losses, under 12 months'],
      ['Fair value, 12 months or more'],
      ['Gross losses, 12 months or more'],
      ['Rebuilt loss-position fair value'],
      ['Filed loss-position fair value'],['Loss-position fair difference'],
      ['Rebuilt loss-position gross losses'],
      ['Filed loss-position gross losses'],['Loss-position loss difference']];
    const maturity=w.worksheets.getItem('Maturity ladder');
    layout(maturity,'Current AFS maturity buckets (USD millions)',
      ['Bucket or measure','Source or method','Amount'],'C',22);
    maturity.getRange('A5:A22').values=[
      ...c.maturity.buckets.map(x=>[`${x.label} cost`]),
      [''],...c.maturity.buckets.map(x=>[`${x.label} fair value`]),
      ['Rebuilt maturity cost'],['Filed maturity cost'],
      ['Maturity-cost difference'],['Rebuilt maturity fair value'],
      ['Filed maturity fair value'],['Maturity fair-value difference'],
      ['After-ten-year and no-date fair-value share']];
    for(let row=5;row<=9;row++) put(maturity,`B${row}`,'Filed bucket');
    for(let row=11;row<=15;row++) put(maturity,`B${row}`,'Filed bucket');
    for(const [row,label] of [[16,'Calculated'],[17,'Filed total'],
                               [18,'Difference'],[19,'Calculated'],
                               [20,'Filed total'],[21,'Difference'],
                               [22,'Calculated']])
      put(maturity,`B${row}`,label);
    put(maturity,'A2',c.maturity.cost_basis==='net_of_allowance' ?
      'Filed maturity cost is net of credit-loss allowance.' :
      'Filed maturity cost is gross amortized cost.');
    maturity.getRange('C22').setNumberFormat('0.0%');
    const checks=w.worksheets.getItem('Checks');
    layout(checks,'Independent reconciliation differences (USD millions)',
      ['Check','Difference'],'B',10);
    checks.getRange('A5:A10').values=[
      ['Cost, allowance, gains and losses versus filed fair value'],
      ['Loss-position fair-value age buckets'],
      ['Loss-position gross-loss age buckets'],
      ['Maturity cost buckets versus filed cost basis'],
      ['Maturity fair-value buckets versus filed fair value'],
      ['Scenario haircut arithmetic']];
    checks.getRange('B5:B10').setNumberFormat('0.00;(0.00);0.00');
  }
}
const targets=m=>[...m].filter(([,x])=>x.bad!==null).map(([k])=>k).sort();
function apply(w,m,kind) {
  for(const [key,x] of m) {
    const [s,a]=key.split('!');
    formula(w.worksheets.getItem(s),a,kind==='seed'&&x.bad?x.bad:x.good);
  }
}
function previewRange(name) {
  if(name==='Source lineage') return 'A1:F42';
  if(name==='Source facts') return 'A1:D30';
  if(name.endsWith('scenario')) return 'A1:D13';
  if(name.endsWith('summary')||name==='Checks') return 'A1:B13';
  return 'A1:C24';
}
async function make(c,kind,dir) {
  const w=Workbook.create();
  for(const name of SHEETS[c.profile]) w.worksheets.add(name);
  source(c,w);working(c,w);
  const map=c.profile==='pension_full'?pensionFormulas(c):afsFormulas();
  if(targets(map).length!==12) throw new Error('target_repair_depth_not_twelve');
  apply(w,map,kind);w.recalculate();
  const out=await SpreadsheetFile.exportXlsx(w);
  const file=path.join(dir,`${kind}.xlsx`);await out.save(file);
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
  for(const item of await fs.readdir(dir,{withFileTypes:true})) {
    const child=path.join(dir,item.name);
    if(item.isSymbolicLink()) throw new Error('private_workbook_symlink_forbidden');
    if(item.isDirectory()) await secureTree(child);
    else await fs.chmod(child,0o600);
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
    workbook_edits:0}));process.exit(0);
}
await fs.mkdir(outputDirectory,{recursive:true,mode:0o700});
const manifest={schema:'envloop.sec_excel_train_remaining_four_workbooks.private.v1',
  review_sha256:createHash('sha256').update(await fs.readFile(reviewPath)).digest('hex'),
  status:'TRAIN-only offline workbooks; independent OOXML audit pending',cases:[]};
for(const c of review.cases) {
  const dir=path.join(outputDirectory,`case-${String(c.case_index).padStart(2,'0')}`);
  await fs.mkdir(dir,{recursive:true,mode:0o700});
  const seed=await make(c,'seed',dir);
  const positive=await make(c,'positive',dir);
  manifest.cases.push({case_index:c.case_index,profile:c.profile,seed,positive});
}
const mpath=path.join(outputDirectory,'workbooks-manifest.private.json');
await fs.writeFile(mpath,JSON.stringify(manifest,null,2)+'\n',
  {mode:0o600,flag:'wx'});
await secureTree(outputDirectory);
console.log(JSON.stringify({status:'four_remaining_source_workbook_pairs_created',
  cases:manifest.cases.length,repairs_per_case:manifest.cases.map(x=>x.seed.target_cells.length),
  manifest_sha256:createHash('sha256').update(await fs.readFile(mpath)).digest('hex')}));
