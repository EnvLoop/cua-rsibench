import fs from 'node:fs/promises';
import path from 'node:path';
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const [, , casesPath, outRoot] = process.argv;
if (!casesPath || !outRoot) throw new Error('usage: node build_ar_workbooks.mjs CASES_JSON OUT_ROOT');
const cases = JSON.parse(await fs.readFile(casesPath, 'utf8'));
const SHEETS = ['Collection Review', 'Filing Selection', 'Reserve Bridge', 'DSO Trend',
  'Cash Conversion', 'Credit Stress', 'Audit', 'Source 10-K', 'Filing Map'];
const METRICS = ['net_ar', 'allowance', 'revenue', 'ocf', 'current_assets'];
const RAW_HEADERS = ['Record ID', 'Concept', 'Unit', 'Start', 'End', 'Filed',
  'Accession', 'Reported USD', 'FY', 'FP', 'Frame'];
function formulas(c) {
  const out = new Map();
  const put = (sheet, addr, good, bad) => out.set(`${sheet}!${addr}`, { good, bad });
  const raw = (year, metric) => {
    const r = c.canonical[`${year}:${metric}`];
    const i = c.records.findIndex(item => item.id === r.id);
    if (i < 0) throw new Error(`source row missing ${c.case_id}:${year}:${metric}`);
    return `'Source 10-K'!H${i + 5}`;
  };
  for (const [year, col] of [['prior', 'B'], ['current', 'C']]) {
    METRICS.forEach((metric, i) => {
      const altYear = year === 'prior' ? 'current' : 'prior';
      const bad = i % 2 ? raw(year, METRICS[(i + 1) % METRICS.length]) : raw(altYear, metric);
      put('Filing Selection', `${col}${i + 5}`, `=${raw(year, metric)}/1000000`, `=${bad}/1000000`);
    });
  }
  const f = addr => `'Filing Selection'!${addr}`;
  for (const col of ['B', 'C']) {
    put('Reserve Bridge', `${col}5`, `=${f(`${col}5`)}`, `=${f(`${col}6`)}`);
    put('Reserve Bridge', `${col}6`, `=${f(`${col}6`)}`, `=${f(`${col}5`)}`);
    put('Reserve Bridge', `${col}7`, `=${col}5+${col}6`, `=${col}5-${col}6`);
    put('Reserve Bridge', `${col}8`, `=${col}6/${col}7`, `=${col}6/${col}5`);
    put('Reserve Bridge', `${col}9`, `=${col}5/${f(`${col}9`)}`, `=${col}7/${f(`${col}9`)}`);
  }
  put('DSO Trend', 'B5', "='Filing Map'!B5", "='Filing Map'!B6");
  put('DSO Trend', 'B6', "='Filing Map'!B6", "='Filing Map'!B5");
  put('DSO Trend', 'B7', `=(${f('B5')}+${f('C5')})/2`, `=${f('C5')}`);
  put('DSO Trend', 'B8', `=B7/${f('C7')}*B6`, `=B7/${f('B7')}*B6`);
  put('DSO Trend', 'B9', `=${f('C7')}/${f('B7')}-1`, `=${f('C7')}/${f('B7')}+1`);
  put('DSO Trend', 'B10', `=${f('C5')}/${f('B5')}-1`, `=${f('C5')}/${f('B5')}+1`);
  put('Cash Conversion', 'B5', `=${f('C8')}/${f('C7')}`, `=${f('C8')}/${f('B7')}`);
  put('Cash Conversion', 'B6', `=${f('C5')}/${f('C7')}`, `=${f('C5')}/${f('B7')}`);
  put('Cash Conversion', 'B7', `=${f('C8')}/${f('C5')}`, `=${f('C8')}/${f('B5')}`);
  put('Cash Conversion', 'B8', `=${f('C8')}/${f('B8')}-1`, `=${f('C8')}/${f('B8')}+1`);
  put('Cash Conversion', 'B9', `=${f('C5')}-${f('B5')}`, `=${f('C5')}+${f('B5')}`);
  put('Cash Conversion', 'B10', `=${f('C8')}-B9`, `=${f('C8')}+B9`);
  put('Credit Stress', 'C5', "='Reserve Bridge'!C7*B5", "='Reserve Bridge'!C7*(1+B5)");
  put('Credit Stress', 'C6', '=C5*B6', '=C5+B6');
  put('Credit Stress', 'C7', `=${f('C5')}-C5`, `=${f('C5')}+C5`);
  put('Credit Stress', 'C8', `=(${f('C6')}+C5)/'Reserve Bridge'!C7`, `=(${f('C6')}+C5)/${f('C5')}`);
  put('Credit Stress', 'C9', "='Reserve Bridge'!C7", "='Reserve Bridge'!B7");
  put('Credit Stress', 'C10', `=${f('C9')}-C5`, `=${f('C9')}+C5`);
  put('Credit Stress', 'C11', '=C7/C10', '=C5/C10');
  put('Collection Review', 'B5', `=${f('C5')}`, `=${f('B5')}`);
  put('Collection Review', 'B6', "='Reserve Bridge'!C7", "='Reserve Bridge'!B7");
  put('Collection Review', 'B7', "='Reserve Bridge'!C8", "='Reserve Bridge'!B8");
  put('Collection Review', 'B8', "='DSO Trend'!B8", "='DSO Trend'!B7");
  put('Collection Review', 'B9', "='Cash Conversion'!B5", "='Cash Conversion'!B6");
  put('Collection Review', 'B10', "='Credit Stress'!C7", "='Credit Stress'!C5");
  put('Collection Review', 'B11', "='Credit Stress'!C6", "='Credit Stress'!C5");
  put('Audit', 'B5', `='Reserve Bridge'!C7-${f('C5')}-${f('C6')}`,
    `='Reserve Bridge'!C7-${f('C5')}+${f('C6')}`);
  put('Audit', 'B6', `='Credit Stress'!C7+${f('C6')}+'Credit Stress'!C5-'Credit Stress'!C9`,
    `='Credit Stress'!C7-${f('C6')}+'Credit Stress'!C5-'Credit Stress'!C9`);
  put('Audit', 'B7', `='DSO Trend'!B8-'DSO Trend'!B7/${f('C7')}*'DSO Trend'!B6`,
    `='DSO Trend'!B8+'DSO Trend'!B7/${f('C7')}*'DSO Trend'!B6`);
  return out;
}
function set(ws, range, values) { ws.getRange(range).values = values; }
function layout(ws, title, headers, last = 'B') {
  ws.showGridLines = false;
  set(ws, 'A1', [[title]]);
  ws.getRange('A1').format.font = { name: 'Arial', size: 15, bold: true, color: '#173A5E' };
  set(ws, `A4:${last}4`, [headers]);
  ws.getRange(`A4:${last}4`).format = { fill: '#173A5E',
    font: { name: 'Arial', size: 10, bold: true, color: '#FFFFFF' }, rowHeight: 30 };
  ws.getRange('A:A').format.columnWidth = 40;
  ws.getRange('B:B').format.columnWidth = 24;
  if (last === 'C') ws.getRange('C:C').format.columnWidth = 24;
}
function workbook(c, targets, faults) {
  const wb = Workbook.create();
  for (const name of SHEETS) wb.worksheets.add(name);
  const review = wb.worksheets.getItem('Collection Review');
  layout(review, `${c.ticker} FY${c.filing_fiscal_year} receivables audit`, ['Measure', 'USD m / days / ratio']);
  set(review, 'A2', [['Repair unmarked formula faults; preserve original SEC disclosures.']]);
  set(review, 'A5:A11', [['Net receivables'], ['Gross receivables inferred from net + reserve'],
    ['Reported reserve / inferred gross'], ['Average net-receivable days'],
    ['Operating cash flow / revenue'], ['Modeled net receivables'],
    ['Modeled cash shortfall proxy']]);
  review.getRange('B5:B6').setNumberFormat('#,##0.0');
  review.getRange('B7').setNumberFormat('0.0%');
  review.getRange('B8').setNumberFormat('0.0');
  review.getRange('B9').setNumberFormat('0.0%');
  review.getRange('B10:B11').setNumberFormat('#,##0.0');
  const selection = wb.worksheets.getItem('Filing Selection');
  layout(selection, 'Original 10-K receivable and revenue facts', ['SEC metric', 'Prior FY/date', 'Current FY/date'], 'C');
  set(selection, 'A2', [[`Accession ${c.filing_accession}; current ${c.annual_start} to ${c.annual_end}.`]]);
  set(selection, 'A5:A9', [['Net accounts receivable'], ['Doubtful-account allowance'],
    ['Selected annual revenue'], ['Operating cash flow'], ['Current assets']]);
  selection.getRange('B5:C9').setNumberFormat('#,##0.0');
  const reserve = wb.worksheets.getItem('Reserve Bridge');
  layout(reserve, 'Net, reserve, and inferred gross receivables', ['Measure', 'Prior FY/date', 'Current FY/date'], 'C');
  set(reserve, 'A2', [['Gross is inferred from net plus separately reported allowance.']]);
  set(reserve, 'A5:A9', [['Net receivables'], ['Allowance'], ['Inferred gross receivables'],
    ['Allowance / inferred gross'], ['Net receivables / current assets']]);
  reserve.getRange('B5:C7').setNumberFormat('#,##0.0');
  reserve.getRange('B8:C9').setNumberFormat('0.0%');
  const dso = wb.worksheets.getItem('DSO Trend');
  layout(dso, 'Average-balance receivable-days analysis', ['Measure', 'Days / USD m / growth']);
  set(dso, 'A5:A10', [['Prior fiscal days'], ['Current fiscal days'],
    ['Average opening/closing net receivables'], ['Average receivable days'],
    ['Revenue year-over-year growth'], ['Net receivable growth']]);
  dso.getRange('B5:B8').setNumberFormat('#,##0.0');
  dso.getRange('B9:B10').setNumberFormat('0.0%');
  const cash = wb.worksheets.getItem('Cash Conversion');
  layout(cash, 'Cash-flow context, not an actual collections ledger', ['Measure', 'USD m / ratio']);
  set(cash, 'A5:A10', [['Operating cash flow / revenue'], ['Net receivables / revenue'],
    ['Operating cash flow / net receivables'], ['Operating cash flow growth'],
    ['Net receivable balance change'], ['Cash flow less receivable change proxy']]);
  cash.getRange('B5:B6').setNumberFormat('0.0%');
  cash.getRange('B7').setNumberFormat('0.00');
  cash.getRange('B8').setNumberFormat('0.0%');
  cash.getRange('B9:B10').setNumberFormat('#,##0.0');
  const stress = wb.worksheets.getItem('Credit Stress');
  layout(stress, 'Synthetic reserve stress — not a credit-loss forecast', ['Driver / output', 'Assumption', 'Modeled result'], 'C');
  set(stress, 'A2', [['Reserve change and realized cash loss are separately modeled assumptions.']]);
  set(stress, 'A5:A11', [['Incremental reserve rate → added reserve'],
    ['Cash realization share → cash shortfall proxy'], ['Modeled net receivables'],
    ['Modeled allowance / gross'], ['Inferred gross receivables'],
    ['Current assets after added reserve'], ['Modeled net receivables / current assets']]);
  set(stress, 'B5:B6', [[c.scenario.incremental_reserve_rate],
    [c.scenario.modeled_cash_realization_fraction]]);
  stress.getRange('B5:B6').format = { fill: '#FFF0BE',
    font: { name: 'Arial', size: 10, color: '#185AA6' } };
  stress.getRange('B5:B6').setNumberFormat('0.0%');
  stress.getRange('C5:C7').setNumberFormat('#,##0.0');
  stress.getRange('C8').setNumberFormat('0.0%');
  stress.getRange('C9:C10').setNumberFormat('#,##0.0');
  stress.getRange('C11').setNumberFormat('0.0%');
  const audit = wb.worksheets.getItem('Audit');
  layout(audit, 'Formula relationship checks', ['Check', 'Expected zero']);
  set(audit, 'A5:A7', [['Gross less net and allowance'],
    ['Modeled gross less net and total reserve'], ['Receivable-days formula checksum']]);
  audit.getRange('B5:B7').setNumberFormat('#,##0.000');
  const raw = wb.worksheets.getItem('Source 10-K');
  layout(raw, 'Unedited original SEC receivable facts', RAW_HEADERS, 'K');
  set(raw, 'A2', [[c.filing_index_url]]);
  const rows = c.records.map(r => [r.id, r.concept, r.unit, r.start, r.end,
    r.filed, r.accession, r.value, r.fy, r.fp, r.frame]);
  set(raw, `A5:K${rows.length + 4}`, rows);
  raw.getRange('A:A').format.columnWidth = 22;
  raw.getRange('B:B').format.columnWidth = 62;
  raw.getRange('C:F').format.columnWidth = 18;
  raw.getRange('G:G').format.columnWidth = 26;
  raw.getRange('H:H').format.columnWidth = 22;
  raw.getRange('I:K').format.columnWidth = 14;
  raw.freezePanes.freezeRows(4);
  raw.tables.add(`A4:K${rows.length + 4}`, true, 'ArSecFacts');
  const map = wb.worksheets.getItem('Filing Map');
  layout(map, 'Filing provenance and modeled boundary', ['Field', 'Value']);
  set(map, 'A5:B13', [['Prior fiscal days', c.prior_fiscal_days],
    ['Current fiscal days', c.current_fiscal_days], ['CIK', `CIK${String(c.cik).padStart(10, '0')}`],
    ['Accession', c.filing_accession], ['Fiscal year', c.filing_fiscal_year],
    ['Prior end', c.prior_end], ['Current end', c.annual_end],
    ['Excerpt SHA-256', c.source_excerpt_sha256], ['Raw SHA-256', c.source_raw_json_sha256]]);
  map.getRange('A:A').format.columnWidth = 36;
  map.getRange('B:B').format.columnWidth = 88;
  set(map, 'A15', [['Reserve and cash-realization assumptions are authored; source facts unchanged.']]);
  for (const [key, pair] of targets) {
    const bang = key.lastIndexOf('!');
    wb.worksheets.getItem(key.slice(0, bang)).getRange(key.slice(bang + 1)).formulas = [[
      faults.has(key) ? pair.bad : pair.good,
    ]];
  }
  wb.recalculate();
  return wb;
}
await fs.mkdir(outRoot, { recursive: true });
for (const [index, c] of cases.entries()) {
  const dir = path.join(outRoot, c.case_id);
  await fs.mkdir(dir, { recursive: true });
  const targets = formulas(c);
  const pool = [...targets.keys()].filter(k => !k.startsWith('Audit!'));
  const faults = new Set(Array.from({ length: 9 }, (_, i) => pool[(index * 17 + i * 11) % pool.length]));
  if (faults.size !== 9) throw new Error(`fault collision ${c.case_id}`);
  for (const [filename, selected] of [['actor.xlsx', faults], ['reference.xlsx', new Set()]]) {
    const wb = workbook(c, targets, selected);
    if (process.env.SEC_AR_RENDER_QA === '1' && filename === 'reference.xlsx') {
      for (const [sheet, range] of [['Collection Review', 'A1:B12'], ['Filing Selection', 'A1:C10'],
        ['Reserve Bridge', 'A1:C10'], ['DSO Trend', 'A1:B11'],
        ['Cash Conversion', 'A1:B11'], ['Credit Stress', 'A1:C12'],
        ['Audit', 'A1:B8'], ['Source 10-K', 'A1:K12'], ['Filing Map', 'A1:B16']]) {
        const image = await wb.render({ sheetName: sheet, range, scale: 1.25, format: 'png' });
        await fs.writeFile(path.join(dir, `qa-${sheet.toLowerCase().replaceAll(' ', '-')}.png`),
          new Uint8Array(await image.arrayBuffer()));
      }
    }
    const exported = await SpreadsheetFile.exportXlsx(wb);
    await exported.save(path.join(dir, filename));
  }
  await fs.writeFile(path.join(dir, 'private-oracle.json'), JSON.stringify({
    case_id: c.case_id, sheet_order: SHEETS, faulted: [...faults].sort(),
    targets: Object.fromEntries([...targets].map(([key, pair]) => [key, pair.good])),
  }, null, 2) + '\n');
  await fs.writeFile(path.join(dir, 'task.md'),
    `# Receivables and reserve audit\n\nOpen the ${c.ticker} original filing workbook in Microsoft Excel for the web. Repair unmarked formula faults across net/gross receivables, the reported doubtful-account allowance, average-balance receivable days, cash-flow context, and a separately labeled synthetic reserve stress. Save and submit the downloaded .xlsx. Preserve every SEC fact, scenario input, unrelated formula, table, and sheet. The modeled cash shortfall is not actual collections, and the reserve scenario is not SEC guidance.\n`);
  process.stdout.write(`${c.case_id}: ${targets.size} targets, ${faults.size} unmarked faults\n`);
}
