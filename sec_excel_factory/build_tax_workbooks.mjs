import fs from 'node:fs/promises';
import path from 'node:path';
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const [, , casesPath, outRoot] = process.argv;
if (!casesPath || !outRoot) throw new Error('usage: node build_tax_workbooks.mjs CASES_JSON OUT_ROOT');
const cases = JSON.parse(await fs.readFile(casesPath, 'utf8'));
const SHEETS = ['Tax Review', 'Filing Selection', 'Provision Bridge', 'Cash Taxes',
  'Deferred Assets', 'Rate Stress', 'Audit', 'Source 10-K', 'Filing Map'];
const METRICS = ['pretax', 'tax_expense', 'current_tax', 'deferred_tax', 'cash_taxes', 'dta'];
const RAW_HEADERS = ['Record ID', 'Concept', 'Unit', 'Start', 'End', 'Filed',
  'Accession', 'Reported USD', 'FY', 'FP', 'Frame'];
function formulas(c) {
  const out = new Map();
  const put = (sheet, addr, good, bad) => out.set(`${sheet}!${addr}`, { good, bad });
  const src = (year, metric) => {
    const record = c.canonical[`${year}:${metric}`];
    const index = c.records.findIndex(r => r.id === record.id);
    if (index < 0) throw new Error(`source row missing ${c.case_id}:${year}:${metric}`);
    return `'Source 10-K'!H${index + 5}`;
  };
  for (const [year, col] of [['prior', 'B'], ['current', 'C']]) {
    METRICS.forEach((metric, i) => {
      const wrongYear = year === 'prior' ? 'current' : 'prior';
      const wrong = i % 2 ? src(year, METRICS[(i + 1) % METRICS.length]) : src(wrongYear, metric);
      put('Filing Selection', `${col}${i + 5}`, `=${src(year, metric)}/1000000`, `=${wrong}/1000000`);
    });
  }
  const f = a => `'Filing Selection'!${a}`;
  put('Provision Bridge', 'B5', `=${f('C7')}`, `=${f('B7')}`);
  put('Provision Bridge', 'B6', `=${f('C8')}`, `=${f('B8')}`);
  put('Provision Bridge', 'B7', '=B5+B6', '=B5-B6');
  put('Provision Bridge', 'B8', `=${f('C6')}`, `=${f('B6')}`);
  put('Provision Bridge', 'B9', '=B7-B8', '=B7+B8');
  put('Provision Bridge', 'B10', `=B8/${f('C5')}`, `=B8/${f('B5')}`);
  put('Provision Bridge', 'B11', `=${f('B6')}/${f('B5')}`, `=${f('B7')}/${f('B5')}`);
  put('Provision Bridge', 'B12', '=B10-B11', '=B10+B11');
  put('Cash Taxes', 'B5', `=${f('C9')}`, `=${f('B9')}`);
  put('Cash Taxes', 'B6', `=${f('C6')}`, `=${f('C7')}`);
  put('Cash Taxes', 'B7', '=B5-B6', '=B5+B6');
  put('Cash Taxes', 'B8', `=B5/${f('C5')}`, `=B5/${f('B5')}`);
  put('Cash Taxes', 'B9', `=B5-${f('C7')}`, `=B5+${f('C7')}`);
  put('Deferred Assets', 'B5', `=${f('B10')}`, `=${f('C10')}`);
  put('Deferred Assets', 'B6', `=${f('C10')}`, `=${f('B10')}`);
  put('Deferred Assets', 'B7', '=B6-B5', '=B5-B6');
  put('Deferred Assets', 'B8', `=B6/${f('C5')}`, `=B6/${f('B5')}`);
  put('Deferred Assets', 'B9', `=${f('C8')}+B7`, `=${f('C8')}-B7`);
  put('Rate Stress', 'C5', `=${f('C5')}+B5`, `=${f('C5')}-B5`);
  put('Rate Stress', 'C6', "='Provision Bridge'!B10", "='Provision Bridge'!B11");
  put('Rate Stress', 'C7', '=C6+B6', '=C6-B6');
  put('Rate Stress', 'C8', '=C5*C7', '=C5/C7');
  put('Rate Stress', 'C9', '=C5-C8', '=C5+C8');
  put('Rate Stress', 'C10', `=C9-(${f('C5')}-${f('C6')})`, `=C9+(${f('C5')}-${f('C6')})`);
  put('Tax Review', 'B5', `=${f('C5')}`, `=${f('B5')}`);
  put('Tax Review', 'B6', `=${f('C6')}`, `=${f('C7')}`);
  put('Tax Review', 'B7', "='Provision Bridge'!B10", "='Provision Bridge'!B11");
  put('Tax Review', 'B8', "='Cash Taxes'!B5", "='Cash Taxes'!B6");
  put('Tax Review', 'B9', "='Deferred Assets'!B7", "='Deferred Assets'!B6");
  put('Tax Review', 'B10', "='Rate Stress'!C8", "='Rate Stress'!C5");
  put('Tax Review', 'B11', "='Rate Stress'!C9", "='Rate Stress'!C8");
  put('Audit', 'B5', "='Provision Bridge'!B5+'Provision Bridge'!B6-'Provision Bridge'!B8",
    "='Provision Bridge'!B5-'Provision Bridge'!B6-'Provision Bridge'!B8");
  put('Audit', 'B6', "='Provision Bridge'!B7-'Provision Bridge'!B8",
    "='Provision Bridge'!B7+'Provision Bridge'!B8");
  put('Audit', 'B7', "='Rate Stress'!C8-'Rate Stress'!C5*'Rate Stress'!C7",
    "='Rate Stress'!C8+'Rate Stress'!C5*'Rate Stress'!C7");
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
  const review = wb.worksheets.getItem('Tax Review');
  layout(review, `${c.ticker} FY${c.filing_fiscal_year} tax provision review`, ['Measure', 'USD m / rate']);
  set(review, 'A2', [['Repair unmarked formula faults; keep source facts and scenario distinct.']]);
  set(review, 'A5:A11', [['Pre-tax income'], ['Reported tax expense'], ['Effective tax rate'],
    ['Cash income taxes paid'], ['Change in deferred tax assets'],
    ['Modeled stressed tax provision'], ['Modeled after-tax income']]);
  review.getRange('B5:B6').setNumberFormat('#,##0.0');
  review.getRange('B7').setNumberFormat('0.0%');
  review.getRange('B8:B11').setNumberFormat('#,##0.0');
  const selection = wb.worksheets.getItem('Filing Selection');
  layout(selection, 'Original 10-K selected tax and cash facts', ['SEC metric', 'Prior FY', 'Current FY'], 'C');
  set(selection, 'A2', [[`Accession ${c.filing_accession}; current ${c.annual_start} to ${c.annual_end}.`]]);
  set(selection, 'A5:A10', [['Pre-tax income'], ['Total tax expense'], ['Current tax expense'],
    ['Deferred tax expense (may be negative)'], ['Cash income taxes paid'],
    ['Net deferred tax assets at period end']]);
  selection.getRange('B5:C10').setNumberFormat('#,##0.0');
  const bridge = wb.worksheets.getItem('Provision Bridge');
  layout(bridge, 'Current and deferred provision reconciliation', ['Measure', 'USD m / rate']);
  set(bridge, 'A5:A12', [['Current tax expense'], ['Deferred tax expense'], ['Calculated provision'],
    ['Reported total tax expense'], ['Calculated less reported'],
    ['Current effective tax rate'], ['Prior effective tax rate'], ['Effective-rate change']]);
  bridge.getRange('B5:B9').setNumberFormat('#,##0.0');
  bridge.getRange('B10:B12').setNumberFormat('0.0%');
  const cash = wb.worksheets.getItem('Cash Taxes');
  layout(cash, 'Cash taxes versus accrual provision', ['Measure', 'USD m / rate']);
  set(cash, 'A5:A9', [['Cash income taxes paid'], ['Reported tax expense'],
    ['Cash less accrual expense'], ['Cash taxes / pre-tax income'],
    ['Cash paid less current provision']]);
  cash.getRange('B5:B7').setNumberFormat('#,##0.0');
  cash.getRange('B8').setNumberFormat('0.0%');
  cash.getRange('B9').setNumberFormat('#,##0.0');
  const dta = wb.worksheets.getItem('Deferred Assets');
  layout(dta, 'Deferred-tax assets: two filing dates', ['Measure', 'USD m / ratio']);
  set(dta, 'A2', [['DTA movement need not equal deferred-tax expense due to other effects.']]);
  set(dta, 'A5:A9', [['Opening net deferred-tax assets'], ['Closing net deferred-tax assets'],
    ['Change in net deferred-tax assets'], ['Closing DTA / pre-tax income'],
    ['Deferred expense plus DTA movement residual']]);
  dta.getRange('B5:B7').setNumberFormat('#,##0.0');
  dta.getRange('B8').setNumberFormat('0.0%');
  dta.getRange('B9').setNumberFormat('#,##0.0');
  const stress = wb.worksheets.getItem('Rate Stress');
  layout(stress, 'Synthetic taxable-income/rate stress', ['Driver / output', 'Assumption', 'Modeled result'], 'C');
  set(stress, 'A2', [['This illustrative model is not a filing prediction or tax advice.']]);
  set(stress, 'A5:A10', [['Pre-tax income change → stressed income'],
    ['Rate shift → base effective rate'], ['Stressed effective rate'],
    ['Modeled tax provision'], ['Modeled after-tax income'],
    ['Modeled after-tax change versus historical proxy']]);
  set(stress, 'B5:B6', [[c.scenario.pretax_delta_m], [c.scenario.effective_rate_shift]]);
  stress.getRange('B5:B6').format = { fill: '#FFF0BE',
    font: { name: 'Arial', size: 10, color: '#185AA6' } };
  stress.getRange('B5').setNumberFormat('#,##0.0');
  stress.getRange('B6').setNumberFormat('0.0%');
  stress.getRange('C5').setNumberFormat('#,##0.0');
  stress.getRange('C6:C7').setNumberFormat('0.0%');
  stress.getRange('C8:C10').setNumberFormat('#,##0.0');
  const audit = wb.worksheets.getItem('Audit');
  layout(audit, 'Formula relationship checks', ['Check', 'Expected zero']);
  set(audit, 'A5:A7', [['Current plus deferred less total expense'],
    ['Calculated provision less reported expense'], ['Modeled tax less income times rate']]);
  audit.getRange('B5:B7').setNumberFormat('#,##0.000');
  const raw = wb.worksheets.getItem('Source 10-K');
  layout(raw, 'Unedited original-filing tax fact rows', RAW_HEADERS, 'K');
  set(raw, 'A2', [[c.filing_index_url]]);
  const rows = c.records.map(r => [r.id, r.concept, r.unit, r.start, r.end,
    r.filed, r.accession, r.value, r.fy, r.fp, r.frame]);
  set(raw, `A5:K${rows.length + 4}`, rows);
  raw.getRange('A:A').format.columnWidth = 22;
  raw.getRange('B:B').format.columnWidth = 65;
  raw.getRange('C:F').format.columnWidth = 18;
  raw.getRange('G:G').format.columnWidth = 26;
  raw.getRange('H:H').format.columnWidth = 22;
  raw.getRange('I:K').format.columnWidth = 15;
  raw.freezePanes.freezeRows(4);
  raw.tables.add(`A4:K${rows.length + 4}`, true, 'TaxSecFacts');
  const map = wb.worksheets.getItem('Filing Map');
  layout(map, 'Filing provenance and modeled boundary', ['Field', 'Value']);
  set(map, 'A5:B12', [['CIK', `CIK${String(c.cik).padStart(10, '0')}`],
    ['Accession', c.filing_accession], ['Filing fiscal year', c.filing_fiscal_year],
    ['Prior period end', c.prior_end], ['Current period end', c.annual_end],
    ['Excerpt SHA-256', c.source_excerpt_sha256], ['Raw source SHA-256', c.source_raw_json_sha256],
    ['Scenario boundary', 'Rate and income shocks authored; tax facts remain SEC source']]);
  map.getRange('A:A').format.columnWidth = 35;
  map.getRange('B:B').format.columnWidth = 90;
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
    if (process.env.SEC_TAX_RENDER_QA === '1' && filename === 'reference.xlsx') {
      for (const [sheet, range] of [['Tax Review', 'A1:B12'], ['Filing Selection', 'A1:C11'],
        ['Provision Bridge', 'A1:B13'], ['Cash Taxes', 'A1:B10'],
        ['Deferred Assets', 'A1:B10'], ['Rate Stress', 'A1:C11'],
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
    `# Tax provision and cash-tax audit\n\nOpen the ${c.ticker} original 10-K workbook in Microsoft Excel for the web. Repair its unmarked formula faults across source selection, current/deferred provision, cash taxes, deferred-tax assets, and the separately labeled synthetic rate stress. Save and submit the downloaded .xlsx. Preserve every SEC source record, scenario input, unrelated formula, table, and sheet. The scenario is not SEC guidance, a tax filing, or tax advice; cash taxes, accrual expense, and DTA movements have different accounting bases.\n`);
  process.stdout.write(`${c.case_id}: ${targets.size} targets, ${faults.size} unmarked faults\n`);
}
