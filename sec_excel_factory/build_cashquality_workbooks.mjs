import fs from 'node:fs/promises';
import path from 'node:path';
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const [, , casesPath, outRoot] = process.argv;
if (!casesPath || !outRoot) throw new Error('usage: node build_cashquality_workbooks.mjs CASES_JSON OUT_ROOT');
const cases = JSON.parse(await fs.readFile(casesPath, 'utf8'));
const SHEETS = ['Cash Quality Review', 'Filing Selection', 'Noncash Bridge', 'Reinvestment',
  'Trend', 'Cash Stress', 'Audit', 'Source 10-K', 'Filing Map'];
const METRICS = ['net_income', 'operating_cash_flow', 'depreciation_amortization',
  'share_based_compensation', 'capital_expenditures', 'repurchases'];
const HEADERS = ['Record ID', 'Concept', 'Unit', 'Start', 'End', 'Filed',
  'Accession', 'Reported USD', 'FY', 'FP', 'Frame'];
function formulas(c) {
  const out = new Map();
  const put = (sheet, addr, good, bad) => out.set(`${sheet}!${addr}`, { good, bad });
  const source = (year, metric) => {
    const record = c.canonical[`${year}:${metric}`];
    const i = c.records.findIndex(r => r.id === record.id);
    if (i < 0) throw new Error(`source missing ${c.case_id}:${year}:${metric}`);
    return `'Source 10-K'!H${i + 5}`;
  };
  for (const [year, col] of [['prior', 'B'], ['current', 'C']]) {
    METRICS.forEach((metric, i) => {
      const wrongYear = year === 'prior' ? 'current' : 'prior';
      const wrong = i % 2 ? source(year, METRICS[(i + 1) % METRICS.length]) : source(wrongYear, metric);
      put('Filing Selection', `${col}${i + 5}`, `=${source(year, metric)}/1000000`, `=${wrong}/1000000`);
    });
  }
  const f = a => `'Filing Selection'!${a}`;
  put('Noncash Bridge', 'B5', `=${f('C5')}`, `=${f('B5')}`);
  put('Noncash Bridge', 'B6', `=${f('C7')}`, `=${f('B7')}`);
  put('Noncash Bridge', 'B7', `=${f('C8')}`, `=${f('B8')}`);
  put('Noncash Bridge', 'B8', '=B5+B6+B7', '=B5+B6-B7');
  put('Noncash Bridge', 'B9', `=${f('C6')}`, `=${f('B6')}`);
  put('Noncash Bridge', 'B10', '=B9-B8', '=B9+B8');
  put('Noncash Bridge', 'B11', '=B10/B9', '=B10/B8');
  put('Noncash Bridge', 'B12', '=B9/B5', '=B5/B9');
  put('Reinvestment', 'B5', `=${f('C9')}`, `=${f('B9')}`);
  put('Reinvestment', 'B6', `=${f('C6')}-B5`, `=${f('C6')}+B5`);
  put('Reinvestment', 'B7', `=B5/${f('C6')}`, `=B5/${f('C5')}`);
  put('Reinvestment', 'B8', `=${f('C10')}`, `=${f('B10')}`);
  put('Reinvestment', 'B9', '=B6-B8', '=B6+B8');
  put('Reinvestment', 'B10', '=B8/B6', '=B8/B9');
  put('Trend', 'B5', `=${f('B6')}/${f('B5')}`, `=${f('B5')}/${f('B6')}`);
  put('Trend', 'B6', `=${f('C6')}/${f('C5')}`, `=${f('C5')}/${f('C6')}`);
  put('Trend', 'B7', '=B6-B5', '=B6+B5');
  put('Trend', 'B8', `=${f('B6')}-${f('B9')}`, `=${f('B6')}+${f('B9')}`);
  put('Trend', 'B9', "='Reinvestment'!B6", "='Reinvestment'!B8");
  put('Trend', 'B10', '=B9/B8-1', '=B9/B8+1');
  put('Cash Stress', 'C5', `=${f('C9')}*(1+B5)`, `=${f('C9')}*(1-B5)`);
  put('Cash Stress', 'C6', `=${f('C6')}-B6`, `=${f('C6')}+B6`);
  put('Cash Stress', 'C7', '=C6-C5', '=C6+C5');
  put('Cash Stress', 'C8', `=C7/${f('C10')}`, `=C7/${f('C9')}`);
  put('Cash Stress', 'C9', `=C7-${f('C10')}`, `=C7+${f('C10')}`);
  put('Cash Stress', 'C10', `=C6/${f('C5')}`, `=C6/${f('C6')}`);
  put('Cash Quality Review', 'B5', "='Noncash Bridge'!B12", "='Noncash Bridge'!B11");
  put('Cash Quality Review', 'B6', "='Noncash Bridge'!B10", "='Noncash Bridge'!B8");
  put('Cash Quality Review', 'B7', "='Reinvestment'!B6", "='Reinvestment'!B5");
  put('Cash Quality Review', 'B8', "='Reinvestment'!B7", "='Reinvestment'!B10");
  put('Cash Quality Review', 'B9', "='Cash Stress'!C7", "='Cash Stress'!C6");
  put('Cash Quality Review', 'B10', "='Cash Stress'!C8", "='Cash Stress'!C10");
  put('Cash Quality Review', 'B11', "='Cash Stress'!C9", "='Cash Stress'!C7");
  put('Audit', 'B5', "='Noncash Bridge'!B8+'Noncash Bridge'!B10-'Noncash Bridge'!B9",
    "='Noncash Bridge'!B8-'Noncash Bridge'!B10-'Noncash Bridge'!B9");
  put('Audit', 'B6', `='Reinvestment'!B6+'Reinvestment'!B5-${f('C6')}`,
    `='Reinvestment'!B6-'Reinvestment'!B5-${f('C6')}`);
  put('Audit', 'B7', "='Cash Stress'!C7-'Cash Stress'!C6+'Cash Stress'!C5",
    "='Cash Stress'!C7+'Cash Stress'!C6+'Cash Stress'!C5");
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
  if (last === 'C') ws.getRange('C:C').format.columnWidth = 25;
}
function workbook(c, targets, faults) {
  const wb = Workbook.create();
  for (const name of SHEETS) wb.worksheets.add(name);
  const review = wb.worksheets.getItem('Cash Quality Review');
  layout(review, `${c.ticker} FY${c.filing_fiscal_year} cash-flow quality`, ['Measure', 'USD m / ratio']);
  set(review, 'A2', [['Repair unmarked defects; keep SEC facts and scenario drivers separate.']]);
  set(review, 'A5:A11', [['Operating cash flow / net income'],
    ['Operating cash flow bridge residual'], ['Operating cash flow less capex'],
    ['Capex / operating cash flow'], ['Modeled stressed free cash flow'],
    ['Modeled FCF / reported buybacks'], ['Modeled FCF less reported buybacks']]);
  review.getRange('B5').setNumberFormat('0.00');
  review.getRange('B6:B7').setNumberFormat('#,##0.0');
  review.getRange('B8').setNumberFormat('0.0%');
  review.getRange('B9').setNumberFormat('#,##0.0');
  review.getRange('B10').setNumberFormat('0.00');
  review.getRange('B11').setNumberFormat('#,##0.0');
  const selection = wb.worksheets.getItem('Filing Selection');
  layout(selection, 'Original 10-K earnings and cash-flow facts', ['SEC metric', 'Prior FY', 'Current FY'], 'C');
  set(selection, 'A2', [[`Accession ${c.filing_accession}; current ${c.annual_start} to ${c.annual_end}.`]]);
  set(selection, 'A5:A10', [['Net income'], ['Operating cash flow'],
    ['Depreciation, depletion and amortization'], ['Share-based compensation'],
    ['Capital expenditures'], ['Cash share repurchases']]);
  selection.getRange('B5:C10').setNumberFormat('#,##0.0');
  const bridge = wb.worksheets.getItem('Noncash Bridge');
  layout(bridge, 'Reported earnings to cash-flow residual', ['Measure', 'USD m / ratio']);
  set(bridge, 'A2', [['Residual includes working capital and other items; not a single reported adjustment.']]);
  set(bridge, 'A5:A12', [['Net income'], ['Depreciation/depletion/amortization'],
    ['Share-based compensation'], ['Income plus two noncash items'],
    ['Reported operating cash flow'], ['Other cash-flow residual'],
    ['Residual / operating cash flow'], ['Operating cash flow / net income']]);
  bridge.getRange('B5:B10').setNumberFormat('#,##0.0');
  bridge.getRange('B11').setNumberFormat('0.0%');
  bridge.getRange('B12').setNumberFormat('0.00');
  const reinvest = wb.worksheets.getItem('Reinvestment');
  layout(reinvest, 'Capital expenditure and buyback coverage', ['Measure', 'USD m / ratio']);
  set(reinvest, 'A5:A10', [['Reported capital expenditures'], ['Operating cash flow less capex'],
    ['Capex / operating cash flow'], ['Cash share repurchases'],
    ['Cash flow less capex and buybacks'], ['Buybacks / cash flow after capex']]);
  reinvest.getRange('B5:B6').setNumberFormat('#,##0.0');
  reinvest.getRange('B7').setNumberFormat('0.0%');
  reinvest.getRange('B8:B9').setNumberFormat('#,##0.0');
  reinvest.getRange('B10').setNumberFormat('0.00');
  const trend = wb.worksheets.getItem('Trend');
  layout(trend, 'Two-year conversion and reinvestment comparison', ['Measure', 'USD m / ratio']);
  set(trend, 'A5:A10', [['Prior operating cash flow / net income'],
    ['Current operating cash flow / net income'], ['Conversion-ratio change'],
    ['Prior cash flow after capex'], ['Current cash flow after capex'],
    ['Cash flow after capex growth']]);
  trend.getRange('B5:B6').setNumberFormat('0.00');
  trend.getRange('B7').setNumberFormat('0.00');
  trend.getRange('B8:B9').setNumberFormat('#,##0.0');
  trend.getRange('B10').setNumberFormat('0.0%');
  const stress = wb.worksheets.getItem('Cash Stress');
  layout(stress, 'Synthetic capex and cash drag — not SEC guidance', ['Driver / output', 'Assumption', 'Modeled result'], 'C');
  set(stress, 'A2', [['A scenario capacity test, not a working-capital forecast or cash commitment.']]);
  set(stress, 'A5:A10', [['Capex increase → modeled capex'], ['Cash drag → modeled operating flow'],
    ['Modeled flow after capex'], ['Modeled flow / reported buybacks'],
    ['Modeled flow less reported buybacks'], ['Modeled operating flow / net income']]);
  set(stress, 'B5:B6', [[c.scenario.capex_increase_fraction],
    [c.scenario.working_capital_cash_drag_m]]);
  stress.getRange('B5:B6').format = { fill: '#FFF0BE',
    font: { name: 'Arial', size: 10, color: '#185AA6' } };
  stress.getRange('B5').setNumberFormat('0.0%');
  stress.getRange('B6').setNumberFormat('#,##0.0');
  stress.getRange('C5:C7').setNumberFormat('#,##0.0');
  stress.getRange('C8').setNumberFormat('0.00');
  stress.getRange('C9').setNumberFormat('#,##0.0');
  stress.getRange('C10').setNumberFormat('0.00');
  const audit = wb.worksheets.getItem('Audit');
  layout(audit, 'Formula relationship checks', ['Check', 'Expected zero']);
  set(audit, 'A5:A7', [['Earnings plus items and residual less cash flow'],
    ['Cash flow after capex plus capex less cash flow'],
    ['Modeled flow less operating flow plus capex']]);
  audit.getRange('B5:B7').setNumberFormat('#,##0.000');
  const raw = wb.worksheets.getItem('Source 10-K');
  layout(raw, 'Unedited original-filing cash facts', HEADERS, 'K');
  set(raw, 'A2', [[c.filing_index_url]]);
  const rows = c.records.map(r => [r.id, r.concept, r.unit, r.start, r.end,
    r.filed, r.accession, r.value, r.fy, r.fp, r.frame]);
  set(raw, `A5:K${rows.length + 4}`, rows);
  raw.getRange('A:A').format.columnWidth = 22;
  raw.getRange('B:B').format.columnWidth = 61;
  raw.getRange('C:F').format.columnWidth = 18;
  raw.getRange('G:G').format.columnWidth = 26;
  raw.getRange('H:H').format.columnWidth = 22;
  raw.getRange('I:K').format.columnWidth = 14;
  raw.freezePanes.freezeRows(4);
  raw.tables.add(`A4:K${rows.length + 4}`, true, 'CashQualitySecFacts');
  const map = wb.worksheets.getItem('Filing Map');
  layout(map, 'Original filing and modeled boundary', ['Field', 'Value']);
  set(map, 'A5:B12', [['CIK', `CIK${String(c.cik).padStart(10, '0')}`],
    ['Accession', c.filing_accession], ['Filing fiscal year', c.filing_fiscal_year],
    ['Prior period end', c.prior_end], ['Current period end', c.annual_end],
    ['Excerpt SHA-256', c.source_excerpt_sha256], ['Raw source SHA-256', c.source_raw_json_sha256],
    ['Scenario boundary', 'Capex and cash drag are authored; filing facts remain unchanged']]);
  map.getRange('A:A').format.columnWidth = 35;
  map.getRange('B:B').format.columnWidth = 88;
  set(map, 'A14', [[c.filing_index_url]]);
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
    if (process.env.SEC_CASHQUALITY_RENDER_QA === '1' && filename === 'reference.xlsx') {
      for (const [sheet, range] of [['Cash Quality Review', 'A1:B12'], ['Filing Selection', 'A1:C11'],
        ['Noncash Bridge', 'A1:B13'], ['Reinvestment', 'A1:B11'],
        ['Trend', 'A1:B11'], ['Cash Stress', 'A1:C11'],
        ['Audit', 'A1:B8'], ['Source 10-K', 'A1:K12'], ['Filing Map', 'A1:B15']]) {
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
    `# Cash-flow quality and reinvestment audit\n\nOpen the ${c.ticker} original 10-K workbook in Microsoft Excel for the web. Repair unmarked formula faults across net-income-to-operating-cash-flow residuals, noncash adjustments, capital expenditures, shareholder repurchases, and the separate synthetic cash-drag stress. Save and submit the downloaded .xlsx. Preserve all SEC source facts, scenario inputs, unrelated formulas, tables, and sheets. The residual is not a single reported adjustment and the scenario is not SEC guidance or a cash forecast.\n`);
  process.stdout.write(`${c.case_id}: ${targets.size} targets, ${faults.size} unmarked faults\n`);
}
