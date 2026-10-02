import fs from 'node:fs/promises';
import path from 'node:path';
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const [, , casesPath, outRoot] = process.argv;
if (!casesPath || !outRoot) throw new Error('usage: node build_debt_workbooks.mjs CASES_JSON OUT_ROOT');
const cases = JSON.parse(await fs.readFile(casesPath, 'utf8'));
const SHEETS = ['Debt Review', 'Filing Selection', 'Debt Mix', 'Cash Capacity',
  'Refinance Stress', 'Audit', 'Source 10-K', 'Filing Map'];
const rawHeaders = ['Record ID', 'Concept', 'Period start', 'Period end', 'Filed',
  'Form', 'Accession', 'Reported USD', 'FY', 'FP', 'Frame', 'Unit'];
const METRICS = ['current_long_term_debt', 'noncurrent_long_term_debt', 'cash',
  'operating_cash_flow', 'capital_expenditures', 'current_liabilities', 'current_assets'];
function formulaMap(c) {
  const out = new Map();
  const put = (sheet, addr, good, bad) => out.set(`${sheet}!${addr}`, { good, bad });
  const raw = key => {
    const i = c.records.findIndex(r => r.id === c.canonical[key].id);
    if (i < 0) throw new Error(`source record missing ${c.case_id}:${key}`);
    return `'Source 10-K'!H${i + 5}`;
  };
  METRICS.forEach((metric, i) => {
    const row = i + 5;
    const wrong = i < METRICS.length - 1 ? METRICS[i + 1] : METRICS[0];
    put('Filing Selection', `B${row}`, `=${raw(metric)}/1000000`,
      `=${raw(wrong)}/1000000`);
  });
  const f = cell => `'Filing Selection'!${cell}`;
  put('Debt Mix', 'B5', `=${f('B5')}+${f('B6')}`, `=${f('B5')}+${f('B7')}`);
  put('Debt Mix', 'B6', `=${f('B5')}/B5`, `=${f('B6')}/B5`);
  put('Debt Mix', 'B7', `=B5-${f('B7')}`, `=B5+${f('B7')}`);
  put('Debt Mix', 'B8', `=${f('B7')}/B5`, `=${f('B7')}/${f('B6')}`);
  put('Cash Capacity', 'B5', `=${f('B8')}-${f('B9')}`, `=${f('B8')}+${f('B9')}`);
  put('Cash Capacity', 'B6', `=B5/${f('B5')}`, `=B5/${f('B6')}`);
  put('Cash Capacity', 'B7', `=${f('B7')}+B5`, `=${f('B7')}-B5`);
  put('Cash Capacity', 'B8', `=B7/${f('B5')}`, `=B7/${f('B6')}`);
  put('Cash Capacity', 'B9', `=${f('B11')}-${f('B10')}`, `=${f('B11')}+${f('B10')}`);
  put('Refinance Stress', 'C5', `=${f('B5')}`, `=${f('B6')}`);
  put('Refinance Stress', 'C6', '=C5*B5', '=C5*(1+B5)');
  put('Refinance Stress', 'C7', '=C5-C6', '=C5+C6');
  put('Refinance Stress', 'C8', '=C6*B6', '=C5*B6');
  put('Refinance Stress', 'C9', "='Cash Capacity'!B5-C8", "='Cash Capacity'!B5+C8");
  put('Refinance Stress', 'C10', `=${f('B7')}+C9-C7`, `=${f('B7')}+C9+C7`);
  put('Refinance Stress', 'C11', `=(${f('B7')}+C9)/C7`, `=(${f('B7')}+C9)/C6`);
  put('Debt Review', 'B5', `=${f('B5')}`, `=${f('B6')}`);
  put('Debt Review', 'B6', "='Debt Mix'!B5", "='Debt Mix'!B7");
  put('Debt Review', 'B7', "='Cash Capacity'!B5", "='Cash Capacity'!B7");
  put('Debt Review', 'B8', "='Refinance Stress'!C10", "='Refinance Stress'!C9");
  put('Debt Review', 'B9', "='Refinance Stress'!C11", "='Cash Capacity'!B8");
  put('Debt Review', 'B10', `=${f('B11')}/${f('B10')}`, `=${f('B10')}/${f('B11')}`);
  put('Debt Review', 'B11', "='Debt Mix'!B7", "='Debt Mix'!B5");
  put('Audit', 'B5', `='Debt Mix'!B5-${f('B5')}-${f('B6')}`,
    `='Debt Mix'!B5-${f('B5')}+${f('B6')}`);
  put('Audit', 'B6', `='Cash Capacity'!B5-${f('B8')}+${f('B9')}`,
    `='Cash Capacity'!B5+${f('B8')}+${f('B9')}`);
  put('Audit', 'B7', "='Refinance Stress'!C6+'Refinance Stress'!C7-'Refinance Stress'!C5",
    "='Refinance Stress'!C6-'Refinance Stress'!C7-'Refinance Stress'!C5");
  return out;
}
function set(ws, addr, values) { ws.getRange(addr).values = values; }
function layout(ws, title, headers, last = 'B') {
  ws.showGridLines = false;
  set(ws, 'A1', [[title]]);
  ws.getRange('A1').format.font = { name: 'Arial', size: 15, bold: true, color: '#173A5E' };
  set(ws, `A4:${last}4`, [headers]);
  ws.getRange(`A4:${last}4`).format = { fill: '#173A5E',
    font: { name: 'Arial', size: 10, bold: true, color: '#FFFFFF' }, rowHeight: 30 };
  ws.getRange('A:A').format.columnWidth = 38;
  ws.getRange('B:B').format.columnWidth = 24;
  if (last === 'C') ws.getRange('C:C').format.columnWidth = 25;
}
function workbook(c, formulas, faults) {
  const wb = Workbook.create();
  for (const name of SHEETS) wb.worksheets.add(name);
  const review = wb.worksheets.getItem('Debt Review');
  layout(review, `${c.ticker} filing debt and cash capacity`, ['Measure', 'USD millions / ratio']);
  set(review, 'A2', [['Repair unmarked formula faults; preserve SEC data and modeled drivers.']]);
  set(review, 'A5:A11', [['Reported current portion of long-term debt'],
    ['Tracked current + noncurrent long-term debt'], ['Operating cash flow less capex'],
    ['Modeled cash after current-debt maturity'], ['Modeled maturity coverage'],
    ['Reported current ratio'], ['Tracked long-term debt less cash']]);
  review.getRange('B5:B8').setNumberFormat('#,##0.0');
  review.getRange('B9:B10').setNumberFormat('0.00');
  review.getRange('B11').setNumberFormat('#,##0.0');
  const selection = wb.worksheets.getItem('Filing Selection');
  layout(selection, 'Original 10-K selected balances and cash flows', ['Disclosure', 'USD millions']);
  set(selection, 'A2', [[`Accession ${c.filing_accession}, period ${c.annual_start} to ${c.annual_end}.`]]);
  set(selection, 'A5:A11', [['Current portion of long-term debt'], ['Noncurrent long-term debt'],
    ['Cash and cash equivalents'], ['Operating cash flow'], ['Capital expenditures'],
    ['Current liabilities'], ['Current assets']]);
  selection.getRange('B5:B11').setNumberFormat('#,##0.0');
  const mix = wb.worksheets.getItem('Debt Mix');
  layout(mix, 'Only the two tracked long-term debt disclosures', ['Measure', 'USD millions / ratio']);
  set(mix, 'A2', [['Excludes other borrowing categories, leases, and untagged obligations.']]);
  set(mix, 'A5:A8', [['Current + noncurrent long-term debt'], ['Current share of tracked debt'],
    ['Tracked debt less cash'], ['Cash / tracked debt']]);
  mix.getRange('B5').setNumberFormat('#,##0.0');
  mix.getRange('B6').setNumberFormat('0.0%');
  mix.getRange('B7').setNumberFormat('#,##0.0');
  mix.getRange('B8').setNumberFormat('0.00');
  const cash = wb.worksheets.getItem('Cash Capacity');
  layout(cash, 'Historical cash generation and liquidity', ['Measure', 'USD millions / ratio']);
  set(cash, 'A5:A9', [['Operating cash flow less capex'], ['Cash-flow/current-debt coverage'],
    ['Cash plus historical cash flow'], ['Cash-plus-flow/current-debt coverage'],
    ['Current assets less current liabilities']]);
  cash.getRange('B5').setNumberFormat('#,##0.0');
  cash.getRange('B6').setNumberFormat('0.00');
  cash.getRange('B7').setNumberFormat('#,##0.0');
  cash.getRange('B8').setNumberFormat('0.00');
  cash.getRange('B9').setNumberFormat('#,##0.0');
  const stress = wb.worksheets.getItem('Refinance Stress');
  layout(stress, 'Synthetic refinancing case — not SEC guidance', ['Driver / result', 'Assumption', 'Modeled result'], 'C');
  set(stress, 'A2', [['Uses current long-term debt only; historical cash flow is an illustrative capacity proxy.']]);
  set(stress, 'A5:A11', [['Refinance share → current debt at maturity'], ['Incremental annual rate → refinanced amount'],
    ['Cash due at maturity'], ['Modeled annual interest'], ['Historical flow after added interest'],
    ['Illustrative cash after maturity'], ['Illustrative cash coverage of due amount']]);
  set(stress, 'B5:B6', [[c.scenario.refinance_share], [c.scenario.incremental_interest_rate]]);
  stress.getRange('B5:B6').format = { fill: '#FFF0BE', font: { name: 'Arial', size: 10, color: '#185AA6' } };
  stress.getRange('B5:B6').setNumberFormat('0.0%');
  stress.getRange('C5:C10').setNumberFormat('#,##0.0');
  stress.getRange('C11').setNumberFormat('0.00');
  const audit = wb.worksheets.getItem('Audit');
  layout(audit, 'Reconciliation checks', ['Check', 'Expected zero']);
  set(audit, 'A5:A7', [['Tracked debt less two source components'],
    ['Historical cash flow less operating flow plus capex'],
    ['Refinanced + cash due - current debt']]);
  audit.getRange('B5:B7').setNumberFormat('#,##0.0');
  const raw = wb.worksheets.getItem('Source 10-K');
  layout(raw, 'Unedited original SEC fact excerpt', rawHeaders, 'L');
  set(raw, 'A2', [[c.filing_index_url]]);
  const rows = c.records.map(r => [r.id, r.concept, r.start, r.end, r.filed,
    r.form, r.accession, r.value, r.fy, r.fp, r.frame, r.unit]);
  set(raw, `A5:L${rows.length + 4}`, rows);
  raw.getRange('A:A').format.columnWidth = 22;
  raw.getRange('B:B').format.columnWidth = 51;
  raw.getRange('C:F').format.columnWidth = 17;
  raw.getRange('G:G').format.columnWidth = 26;
  raw.getRange('H:H').format.columnWidth = 22;
  raw.getRange('I:L').format.columnWidth = 14;
  raw.getRange(`H5:H${rows.length + 4}`).setNumberFormat('#,##0;(#,##0);-');
  raw.freezePanes.freezeRows(4);
  raw.tables.add(`A4:L${rows.length + 4}`, true, 'DebtSecFacts');
  const map = wb.worksheets.getItem('Filing Map');
  layout(map, 'Exact filing and model boundary', ['Field', 'Value']);
  set(map, 'A5:B12', [['CIK', `CIK${String(c.cik).padStart(10, '0')}`],
    ['Accession', c.filing_accession], ['Filing fiscal year', c.filing_fiscal_year],
    ['Annual start', c.annual_start], ['Annual end', c.annual_end],
    ['Excerpt SHA-256', c.source_excerpt_sha256], ['Raw source SHA-256', c.source_raw_json_sha256],
    ['Model boundary', 'Refinance assumptions are synthetic; tracked debt is not total corporate debt']]);
  map.getRange('A:A').format.columnWidth = 34;
  map.getRange('B:B').format.columnWidth = 85;
  set(map, 'A14', [[c.filing_index_url]]);
  for (const [key, pair] of formulas) {
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
  const map = formulaMap(c);
  const keys = [...map.keys()].filter(k => !k.startsWith('Audit!'));
  const faults = new Set(Array.from({ length: 8 }, (_, i) => keys[(index * 9 + i * 7) % keys.length]));
  if (faults.size !== 8) throw new Error(`fault collision ${c.case_id}`);
  for (const [filename, selected] of [['actor.xlsx', faults], ['reference.xlsx', new Set()]]) {
    const wb = workbook(c, map, selected);
    if (process.env.SEC_DEBT_RENDER_QA === '1' && filename === 'reference.xlsx') {
      for (const [sheet, range] of [['Debt Review', 'A1:B12'], ['Filing Selection', 'A1:B12'],
        ['Debt Mix', 'A1:B9'], ['Cash Capacity', 'A1:B10'],
        ['Refinance Stress', 'A1:C12'], ['Audit', 'A1:B8'],
        ['Source 10-K', 'A1:L12'], ['Filing Map', 'A1:B15']]) {
        const rendered = await wb.render({ sheetName: sheet, range, scale: 1.25, format: 'png' });
        await fs.writeFile(path.join(dir, `qa-${sheet.toLowerCase().replaceAll(' ', '-')}.png`),
          new Uint8Array(await rendered.arrayBuffer()));
      }
    }
    const exported = await SpreadsheetFile.exportXlsx(wb);
    await exported.save(path.join(dir, filename));
  }
  await fs.writeFile(path.join(dir, 'private-oracle.json'), JSON.stringify({
    case_id: c.case_id, sheet_order: SHEETS, faulted: [...faults].sort(),
    targets: Object.fromEntries([...map].map(([key, v]) => [key, v.good])),
  }, null, 2) + '\n');
  await fs.writeFile(path.join(dir, 'task.md'),
    `# Debt maturity and cash-capacity audit\n\nOpen the ${c.ticker} filing workbook in Microsoft Excel for the web. Repair its unmarked formula faults across fact selection, the two tracked long-term-debt components, historical cash capacity, and the separately labeled synthetic refinancing stress. Save and submit the downloaded .xlsx. Keep all SEC source facts, scenario inputs, unrelated formulas, tables, and sheets intact. Current plus noncurrent long-term debt here is a tracked subset, not total corporate debt, and the scenario is not SEC guidance.\n`);
  process.stdout.write(`${c.case_id}: ${map.size} targets, ${faults.size} unmarked faults\n`);
}
