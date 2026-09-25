import fs from 'node:fs/promises';
import path from 'node:path';
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const [, , casesPath, outRoot] = process.argv;
if (!casesPath || !outRoot) throw new Error('usage: node build_lease_workbooks.mjs CASES_JSON OUT_ROOT');
const cases = JSON.parse(await fs.readFile(casesPath, 'utf8'));
const SHEETS = ['Lease Review', 'Filing Selection', 'Maturity Ladder', 'Liability Bridge',
  'Cash Burden', 'Occupancy Stress', 'Audit', 'Source 10-K', 'Filing Map'];
const METRICS = ['current_liability', 'noncurrent_liability', 'rou_asset', 'lease_cost',
  'lease_payments', 'discount_rate', 'operating_cash_flow', 'due_next12', 'due_year2',
  'due_year3', 'due_year4', 'due_year5', 'due_after5', 'due_total'];
const RAW_HEADERS = ['Record ID', 'Concept', 'Unit', 'Start', 'End', 'Filed',
  'Accession', 'Reported value', 'FY', 'FP', 'Frame'];
function formulas(c) {
  const out = new Map();
  const put = (sheet, addr, good, bad) => out.set(`${sheet}!${addr}`, { good, bad });
  const source = key => {
    const index = c.records.findIndex(r => r.id === c.canonical[key].id);
    if (index < 0) throw new Error(`source missing ${c.case_id}:${key}`);
    return `'Source 10-K'!H${index + 5}`;
  };
  METRICS.forEach((key, i) => {
    const convert = key === 'discount_rate' ? '' : '/1000000';
    const other = METRICS[(i + 1) % METRICS.length];
    put('Filing Selection', `B${i + 5}`, `=${source(key)}${convert}`,
      `=${source(other)}${convert}`);
  });
  const f = cell => `'Filing Selection'!${cell}`;
  for (let i = 0; i < 6; i++) {
    const row = i + 5;
    put('Maturity Ladder', `B${row}`, `=${f(`B${i + 12}`)}`,
      `=${f(`B${((i + 1) % 6) + 12}`)}`);
  }
  put('Maturity Ladder', 'B11', '=B5+B6+B7+B8+B9', '=B5+B6+B7+B8-B9');
  put('Maturity Ladder', 'B12', '=B11+B10', '=B11-B10');
  put('Maturity Ladder', 'B13', `=${f('B18')}`, `=${f('B17')}`);
  put('Maturity Ladder', 'B14', '=B12-B13', '=B12+B13');
  put('Liability Bridge', 'B5', `=${f('B5')}`, `=${f('B6')}`);
  put('Liability Bridge', 'B6', `=${f('B6')}`, `=${f('B5')}`);
  put('Liability Bridge', 'B7', '=B5+B6', '=B5-B6');
  put('Liability Bridge', 'B8', "='Maturity Ladder'!B13", "='Maturity Ladder'!B11");
  put('Liability Bridge', 'B9', '=B8-B7', '=B8+B7');
  put('Liability Bridge', 'B10', `=${f('B7')}/B7`, `=${f('B7')}/B8`);
  put('Liability Bridge', 'B11', `=${f('B10')}`, `=${f('B9')}`);
  put('Cash Burden', 'B5', "='Maturity Ladder'!B5", "='Maturity Ladder'!B6");
  put('Cash Burden', 'B6', `=${f('B9')}`, `=${f('B8')}`);
  put('Cash Burden', 'B7', '=B5-B6', '=B5+B6');
  put('Cash Burden', 'B8', `=B5/${f('B11')}`, `=B5/${f('B9')}`);
  put('Cash Burden', 'B9', `=${f('B5')}/B5`, `=${f('B6')}/B5`);
  put('Cash Burden', 'B10', `=${f('B8')}/B6`, `=${f('B9')}/B6`);
  put('Occupancy Stress', 'C5', "='Maturity Ladder'!B5*(1-B5)*(1+B6)",
    "='Maturity Ladder'!B5*(1+B5)*(1+B6)");
  put('Occupancy Stress', 'C6', "=('Maturity Ladder'!B5+'Maturity Ladder'!B6+'Maturity Ladder'!B7)*(1-B5)*(1+B6)",
    "=('Maturity Ladder'!B5+'Maturity Ladder'!B6+'Maturity Ladder'!B7)*(1+B5)*(1+B6)");
  put('Occupancy Stress', 'C7', "='Maturity Ladder'!B5-C5", "='Maturity Ladder'!B5+C5");
  put('Occupancy Stress', 'C8', `=C5/${f('B11')}`, `=C5/${f('B9')}`);
  put('Occupancy Stress', 'C9', `=C5/${f('B9')}`, `=C5/${f('B8')}`);
  put('Lease Review', 'B5', "='Maturity Ladder'!B13", "='Maturity Ladder'!B11");
  put('Lease Review', 'B6', "='Liability Bridge'!B7", "='Liability Bridge'!B8");
  put('Lease Review', 'B7', "='Liability Bridge'!B9", "='Liability Bridge'!B7");
  put('Lease Review', 'B8', "='Maturity Ladder'!B5", "='Maturity Ladder'!B6");
  put('Lease Review', 'B9', "='Liability Bridge'!B11", "='Liability Bridge'!B10");
  put('Lease Review', 'B10', "='Occupancy Stress'!C5", "='Occupancy Stress'!C6");
  put('Lease Review', 'B11', "='Occupancy Stress'!C8", "='Occupancy Stress'!C9");
  put('Audit', 'B5', "='Maturity Ladder'!B12-'Maturity Ladder'!B13",
    "='Maturity Ladder'!B12+'Maturity Ladder'!B13");
  put('Audit', 'B6', "='Liability Bridge'!B5+'Liability Bridge'!B6-'Liability Bridge'!B7",
    "='Liability Bridge'!B5-'Liability Bridge'!B6-'Liability Bridge'!B7");
  put('Audit', 'B7', "='Occupancy Stress'!C5+'Occupancy Stress'!C7-'Maturity Ladder'!B5",
    "='Occupancy Stress'!C5-'Occupancy Stress'!C7-'Maturity Ladder'!B5");
  return out;
}
function set(ws, range, values) { ws.getRange(range).values = values; }
function frame(ws, title, headers, last = 'B') {
  ws.showGridLines = false;
  set(ws, 'A1', [[title]]);
  ws.getRange('A1').format.font = { name: 'Arial', size: 15, bold: true, color: '#173A5E' };
  set(ws, `A4:${last}4`, [headers]);
  ws.getRange(`A4:${last}4`).format = { fill: '#173A5E',
    font: { name: 'Arial', size: 10, bold: true, color: '#FFFFFF' }, rowHeight: 30 };
  ws.getRange('A:A').format.columnWidth = 39;
  ws.getRange('B:B').format.columnWidth = 24;
  if (last === 'C') ws.getRange('C:C').format.columnWidth = 25;
}
function workbook(c, targets, faults) {
  const wb = Workbook.create();
  for (const name of SHEETS) wb.worksheets.add(name);
  const review = wb.worksheets.getItem('Lease Review');
  frame(review, `${c.ticker} FY${c.filing_fiscal_year} operating-lease maturity`, ['Measure', 'USD m / ratio']);
  set(review, 'A2', [['Repair unmarked formula faults; preserve contractual source records.']]);
  set(review, 'A5:A11', [['Undiscounted future lease payments'], ['Reported lease liability'],
    ['Undiscounted less reported liability'], ['Next-12-month payments due'],
    ['Reported weighted-average discount rate'], ['Modeled next-12-month payments'],
    ['Modeled due / operating cash flow']]);
  review.getRange('B5:B8').setNumberFormat('#,##0.0');
  review.getRange('B9').setNumberFormat('0.0%');
  review.getRange('B10').setNumberFormat('#,##0.0');
  review.getRange('B11').setNumberFormat('0.0%');
  const sel = wb.worksheets.getItem('Filing Selection');
  frame(sel, 'Original 10-K operating-lease disclosures', ['SEC metric', 'USD m / rate']);
  set(sel, 'A2', [[`Accession ${c.filing_accession}; period ${c.annual_start} to ${c.annual_end}.`]]);
  set(sel, 'A5:A18', [['Current operating-lease liability'], ['Noncurrent operating-lease liability'],
    ['Operating-lease right-of-use asset'], ['FY operating-lease cost'],
    ['FY cash lease payments'], ['Weighted-average discount rate'],
    ['FY operating cash flow'], ['Payment due next 12 months'], ['Payment due year 2'],
    ['Payment due year 3'], ['Payment due year 4'], ['Payment due year 5'],
    ['Payment due after year 5'], ['Total undiscounted payments']]);
  sel.getRange('B5:B18').setNumberFormat('#,##0.0');
  sel.getRange('B10').setNumberFormat('0.0%');
  const ladder = wb.worksheets.getItem('Maturity Ladder');
  frame(ladder, 'Six reported contractual payment buckets', ['Payment period', 'USD millions']);
  set(ladder, 'A2', [['Original filing schedule; no inferred bucket allocation.']]);
  set(ladder, 'A5:A14', [['Next 12 months'], ['Year 2'], ['Year 3'], ['Year 4'], ['Year 5'],
    ['After year 5'], ['First five years'], ['Sum of six buckets'],
    ['Reported undiscounted total'], ['Sum less reported total']]);
  ladder.getRange('B5:B14').setNumberFormat('#,##0.0');
  const bridge = wb.worksheets.getItem('Liability Bridge');
  frame(bridge, 'Reported lease liability versus payments', ['Measure', 'USD m / ratio']);
  set(bridge, 'A2', [['Payment less liability is an arithmetic gap, not an independently reported fact.']]);
  set(bridge, 'A5:A11', [['Current liability'], ['Noncurrent liability'], ['Total reported liability'],
    ['Undiscounted contractual payments'], ['Undiscounted less reported liability'],
    ['ROU asset / liability'], ['Reported weighted-average discount rate']]);
  bridge.getRange('B5:B9').setNumberFormat('#,##0.0');
  bridge.getRange('B10').setNumberFormat('0.00');
  bridge.getRange('B11').setNumberFormat('0.0%');
  const cash = wb.worksheets.getItem('Cash Burden');
  frame(cash, 'Next-12 obligations versus historic cash activity', ['Measure', 'USD m / ratio']);
  set(cash, 'A5:A10', [['Next-12 scheduled payments'], ['Historic lease cash payments'],
    ['Next-12 less historic payments'], ['Next-12 due / operating cash flow'],
    ['Current liability / next-12 due'], ['Lease cost / historic payments']]);
  cash.getRange('B5:B7').setNumberFormat('#,##0.0');
  cash.getRange('B8').setNumberFormat('0.0%');
  cash.getRange('B9:B10').setNumberFormat('0.00');
  const stress = wb.worksheets.getItem('Occupancy Stress');
  frame(stress, 'Synthetic payment stress — not contract renegotiation', ['Driver / output', 'Assumption', 'Modeled result'], 'C');
  set(stress, 'A2', [['Assumed reductions and escalation do not alter reported lease commitments.']]);
  set(stress, 'A5:A9', [['Payment reduction → modeled next 12'], ['Escalation → modeled three-year due'],
    ['Modeled next-12 savings'], ['Modeled due / operating cash flow'],
    ['Modeled due / historical lease payments']]);
  set(stress, 'B5:B6', [[c.scenario.next12_payment_reduction], [c.scenario.next12_escalation]]);
  stress.getRange('B5:B6').format = { fill: '#FFF0BE',
    font: { name: 'Arial', size: 10, color: '#185AA6' } };
  stress.getRange('B5:B6').setNumberFormat('0.0%');
  stress.getRange('C5:C7').setNumberFormat('#,##0.0');
  stress.getRange('C8').setNumberFormat('0.0%');
  stress.getRange('C9').setNumberFormat('0.00');
  const audit = wb.worksheets.getItem('Audit');
  frame(audit, 'Formula relationship checks', ['Check', 'Expected zero']);
  set(audit, 'A5:A7', [['Six buckets less reported total'],
    ['Current plus noncurrent less liability'], ['Modeled due plus savings less reported due']]);
  audit.getRange('B5:B7').setNumberFormat('#,##0.000');
  const raw = wb.worksheets.getItem('Source 10-K');
  frame(raw, 'Unedited SEC lease fact records', RAW_HEADERS, 'K');
  set(raw, 'A2', [[c.filing_index_url]]);
  const rows = c.records.map(r => [r.id, r.concept, r.unit, r.start, r.end,
    r.filed, r.accession, r.value, r.fy, r.fp, r.frame]);
  set(raw, `A5:K${rows.length + 4}`, rows);
  raw.getRange('A:A').format.columnWidth = 22;
  raw.getRange('B:B').format.columnWidth = 58;
  raw.getRange('C:F').format.columnWidth = 18;
  raw.getRange('G:G').format.columnWidth = 26;
  raw.getRange('H:H').format.columnWidth = 22;
  raw.getRange('I:K').format.columnWidth = 14;
  raw.freezePanes.freezeRows(4);
  raw.tables.add(`A4:K${rows.length + 4}`, true, 'LeaseSecFacts');
  const map = wb.worksheets.getItem('Filing Map');
  frame(map, 'Original filing and scenario boundary', ['Field', 'Value']);
  set(map, 'A5:B12', [['CIK', `CIK${String(c.cik).padStart(10, '0')}`],
    ['Accession', c.filing_accession], ['Filing fiscal year', c.filing_fiscal_year],
    ['Annual start', c.annual_start], ['Annual end', c.annual_end],
    ['Excerpt SHA-256', c.source_excerpt_sha256], ['Raw source SHA-256', c.source_raw_json_sha256],
    ['Scenario boundary', 'Payment reduction and escalation are authored; contractual data unchanged']]);
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
    if (process.env.SEC_LEASE_RENDER_QA === '1' && filename === 'reference.xlsx') {
      for (const [sheet, range] of [['Lease Review', 'A1:B12'], ['Filing Selection', 'A1:B19'],
        ['Maturity Ladder', 'A1:B15'], ['Liability Bridge', 'A1:B12'],
        ['Cash Burden', 'A1:B11'], ['Occupancy Stress', 'A1:C10'],
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
    `# Operating-lease maturity audit\n\nOpen the ${c.ticker} filing workbook in Microsoft Excel for the web. Repair unmarked formula faults in source selection, the six-bucket operating-lease maturity ladder, liability-versus-undiscounted-payment bridge, cash-burden view, and separately modeled payment stress. Save and submit the downloaded .xlsx. Preserve all original SEC records, scenario inputs, unrelated formulas, tables, and sheets. The payment-reduction and escalation assumptions are benchmark-authored and do not change contractual obligations or represent SEC guidance.\n`);
  process.stdout.write(`${c.case_id}: ${targets.size} targets, ${faults.size} unmarked faults\n`);
}
