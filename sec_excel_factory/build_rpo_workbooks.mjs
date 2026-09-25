import fs from 'node:fs/promises';
import path from 'node:path';
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const [, , casesPath, outRoot] = process.argv;
if (!casesPath || !outRoot) throw new Error('usage: node build_rpo_workbooks.mjs CASES_JSON OUT_ROOT');
const cases = JSON.parse(await fs.readFile(casesPath, 'utf8'));
const SHEETS = ['Executive', 'Filing Selection', 'Liability Rollforward', 'RPO Scenario',
  'Liquidity Review', 'Audit', 'Source 10-K', 'Filing Map'];
const rawHeaders = ['Record ID', 'Concept', 'Period start', 'Period end', 'Filed',
  'Form', 'Accession', 'Reported USD', 'FY', 'FP', 'Frame', 'Unit'];
function rowFor(testCase, key) {
  const record = testCase.canonical[key];
  if (!record) return null;
  const found = testCase.records.findIndex(r => r.id === record.id);
  if (found < 0) throw new Error(`canonical source absent ${testCase.case_id}:${key}`);
  return found + 5;
}
function fact(testCase, key) {
  const row = rowFor(testCase, key);
  if (!row) throw new Error(`missing fact ${testCase.case_id}:${key}`);
  return `='Source 10-K'!H${row}/1000000`;
}
function formulas(testCase) {
  const all = new Map();
  const put = (sheet, cell, good, bad) => all.set(`${sheet}!${cell}`, { good, bad });
  put('Filing Selection', 'B5', fact(testCase, 'revenue'), fact(testCase, 'revenue_prior'));
  put('Filing Selection', 'B6', fact(testCase, 'revenue_prior'), fact(testCase, 'revenue'));
  const priorTotal = testCase.canonical.prior_total ? fact(testCase, 'prior_total') : '=B8+B9';
  const priorNoncurrent = testCase.canonical.prior_noncurrent ? fact(testCase, 'prior_noncurrent') : '=B7-B8';
  const currentTotal = testCase.canonical.total ? fact(testCase, 'total') : '=B11+B12';
  const currentNoncurrent = testCase.canonical.noncurrent ? fact(testCase, 'noncurrent') : '=B10-B11';
  put('Filing Selection', 'B7', priorTotal, fact(testCase, 'prior_current'));
  put('Filing Selection', 'B8', fact(testCase, 'prior_current'), fact(testCase, 'current'));
  put('Filing Selection', 'B9', priorNoncurrent, '=B7-B11');
  put('Filing Selection', 'B10', currentTotal, '=B7');
  put('Filing Selection', 'B11', fact(testCase, 'current'), '=B8');
  put('Filing Selection', 'B12', currentNoncurrent,
    testCase.canonical.total ? '=B10-B8' : '=B11-B8');
  put('Filing Selection', 'B13', fact(testCase, 'rpo'), '=B5');
  put('Filing Selection', 'B14', fact(testCase, 'recognized'), '=B13');
  put('Filing Selection', 'B15', fact(testCase, 'assets_current'), fact(testCase, 'cash'));
  put('Filing Selection', 'B16', fact(testCase, 'liabilities_current'), '=B10');
  put('Filing Selection', 'B17', fact(testCase, 'cash'), '=B16');
  const fs = addr => `'Filing Selection'!${addr}`;
  put('Liability Rollforward', 'B5', `=${fs('B7')}`, `=${fs('B10')}`);
  put('Liability Rollforward', 'B6', `=${fs('B14')}`, `=${fs('B5')}`);
  put('Liability Rollforward', 'B7', `=${fs('B10')}`, `=${fs('B7')}`);
  put('Liability Rollforward', 'B8', '=B7-B5', '=B5-B7');
  put('Liability Rollforward', 'B9', '=B7-B5+B6', '=B7-B5-B6');
  put('Liability Rollforward', 'B10', '=B6/B5', `=B6/${fs('B5')}`);
  put('Liability Rollforward', 'B11', `=${fs('B11')}/B7`, `=${fs('B11')}/${fs('B5')}`);
  put('Liability Rollforward', 'B12', `=${fs('B8')}/B5`, `=${fs('B8')}/B7`);
  put('Liability Rollforward', 'B13', '=B11-B12', '=B12-B11');
  put('RPO Scenario', 'C5', `=${fs('B13')}*(1-B5)`, `=${fs('B13')}*(1+B5)`);
  put('RPO Scenario', 'C6', '=C5*B6', `=${fs('B5')}*B6`);
  put('RPO Scenario', 'C7', '=C5-C6', '=C5+C6');
  put('RPO Scenario', 'C8', `=${fs('B13')}/${fs('B5')}`, `=${fs('B13')}/${fs('B6')}`);
  put('RPO Scenario', 'C9', `=C6/${fs('B5')}`, `=C6/${fs('B6')}`);
  put('RPO Scenario', 'C10', `=${fs('B10')}/${fs('B13')}`, `=${fs('B11')}/${fs('B13')}`);
  put('Liquidity Review', 'B5', `=${fs('B15')}/${fs('B16')}`, `=${fs('B16')}/${fs('B15')}`);
  put('Liquidity Review', 'B6', `=${fs('B17')}/${fs('B16')}`, `=${fs('B17')}/${fs('B15')}`);
  put('Liquidity Review', 'B7', `=${fs('B16')}-${fs('B17')}`, `=${fs('B16')}+${fs('B17')}`);
  put('Liquidity Review', 'B8', `=${fs('B11')}/${fs('B16')}`, `=${fs('B10')}/${fs('B16')}`);
  put('Liquidity Review', 'B9', `=${fs('B17')}/${fs('B11')}`, `=${fs('B17')}/${fs('B10')}`);
  put('Executive', 'B5', `=${fs('B5')}`, `=${fs('B6')}`);
  put('Executive', 'B6', `=${fs('B13')}`, `=${fs('B10')}`);
  put('Executive', 'B7', "='Liability Rollforward'!B10", "='Liability Rollforward'!B11");
  put('Executive', 'B8', "='Liability Rollforward'!B13", "='Liability Rollforward'!B12");
  put('Executive', 'B9', "='RPO Scenario'!C6", "='RPO Scenario'!C5");
  put('Executive', 'B10', "='Liquidity Review'!B5", "='Liquidity Review'!B6");
  put('Executive', 'B11', "='Liability Rollforward'!B9", "='Liability Rollforward'!B8");
  put('Audit', 'B5', `=${fs('B10')}-${fs('B11')}-${fs('B12')}`, `=${fs('B10')}-${fs('B11')}+${fs('B12')}`);
  put('Audit', 'B6', `=${fs('B7')}-${fs('B8')}-${fs('B9')}`, `=${fs('B7')}-${fs('B8')}+${fs('B9')}`);
  put('Audit', 'B7', "='RPO Scenario'!C6+'RPO Scenario'!C7-'RPO Scenario'!C5",
    "='RPO Scenario'!C6-'RPO Scenario'!C7-'RPO Scenario'!C5");
  return all;
}
function set(ws, addr, values) { ws.getRange(addr).values = values; }
function style(ws, title, headers, last = 'B') {
  ws.showGridLines = false;
  set(ws, 'A1', [[title]]);
  ws.getRange('A1').format.font = { name: 'Arial', size: 15, bold: true, color: '#173A5E' };
  set(ws, `A4:${last}4`, [headers]);
  ws.getRange(`A4:${last}4`).format = { fill: '#173A5E',
    font: { name: 'Arial', size: 10, bold: true, color: '#FFFFFF' }, rowHeight: 30 };
  ws.getRange('A:A').format.columnWidth = 36;
  ws.getRange('B:B').format.columnWidth = 25;
  if (last === 'C') ws.getRange('C:C').format.columnWidth = 24;
}
function workbook(testCase, targetMap, faulted) {
  const wb = Workbook.create();
  for (const name of SHEETS) wb.worksheets.add(name);
  const executive = wb.worksheets.getItem('Executive');
  style(executive, `${testCase.ticker} FY2024 contract obligations review`, ['Measure', 'USD millions / ratio']);
  set(executive, 'A2', [['Inspect unmarked defects; preserve source facts and drivers.']]);
  set(executive, 'A5:A11', [['FY revenue'], ['Remaining performance obligations'],
    ['Recognized from opening liability / opening'], ['Current-liability share change'],
    ['Modeled next-12-month RPO'], ['Current ratio'], ['Implied other liability changes (not billings)']]);
  executive.getRange('B5:B6').setNumberFormat('#,##0.0');
  executive.getRange('B7:B8').setNumberFormat('0.0%');
  executive.getRange('B9').setNumberFormat('#,##0.0');
  executive.getRange('B10').setNumberFormat('0.00');
  executive.getRange('B11').setNumberFormat('#,##0.0');
  const selection = wb.worksheets.getItem('Filing Selection');
  style(selection, 'Original 10-K fact selection', ['Measure', 'USD millions']);
  set(selection, 'A2', [[`Accession ${testCase.filing_accession}; period ${testCase.annual_start} to ${testCase.annual_end}.`]]);
  set(selection, 'A5:A17', [['FY revenue'], ['Prior FY revenue'], ['Opening contract liability total'],
    ['Opening current portion'], ['Opening noncurrent portion'], ['Closing contract liability total'],
    ['Closing current portion'], ['Closing noncurrent portion'], ['Remaining performance obligations'],
    ['Revenue recognized from opening liability'], ['Current assets'], ['Current liabilities'], ['Cash']]);
  selection.getRange('B5:B17').setNumberFormat('#,##0.0');
  const roll = wb.worksheets.getItem('Liability Rollforward');
  style(roll, 'Contract-liability classification and movement', ['Measure', 'USD millions / ratio']);
  set(roll, 'A2', [['Residual is not billings; source drivers are not separated.']]);
  set(roll, 'A5:A13', [['Opening liability'], ['Recognized from opening liability'],
    ['Closing liability'], ['Net change'], ['Implied other changes, not billings'],
    ['Opening recognized share'], ['Closing current share'], ['Opening current share'],
    ['Current-share change']]);
  roll.getRange('B5:B9').setNumberFormat('#,##0.0');
  roll.getRange('B10:B13').setNumberFormat('0.0%');
  const rpo = wb.worksheets.getItem('RPO Scenario');
  style(rpo, 'Modeled RPO timing — not SEC guidance', ['Driver / result', 'Assumption', 'Modeled result'], 'C');
  set(rpo, 'A2', [['RPO includes deferred revenue and future invoicing; this worksheet does not project cash.']]);
  set(rpo, 'A5:A10', [['RPO haircut → stressed RPO'], ['Next-12 share → next-12 RPO'],
    ['Later recognition'], ['Reported RPO / FY revenue'], ['Modeled next-12 / FY revenue'],
    ['Contract liability / reported RPO']]);
  set(rpo, 'B5:B6', [[testCase.scenario.rpo_haircut], [testCase.scenario.next12_recognition_share]]);
  rpo.getRange('B5:B6').format = { fill: '#FFF0BE', font: { name: 'Arial', size: 10, color: '#185AA6' } };
  rpo.getRange('B5:B6').setNumberFormat('0.0%');
  rpo.getRange('C5:C7').setNumberFormat('#,##0.0');
  rpo.getRange('C8:C10').setNumberFormat('0.0%');
  const liquidity = wb.worksheets.getItem('Liquidity Review');
  style(liquidity, 'Balance-sheet coverage; RPO is not cash', ['Measure', 'Ratio / USD millions']);
  set(liquidity, 'A5:A9', [['Current assets / current liabilities'], ['Cash / current liabilities'],
    ['Current liabilities less cash'], ['Current contract liability / current liabilities'],
    ['Cash / current contract liability']]);
  liquidity.getRange('B5:B6').setNumberFormat('0.00');
  liquidity.getRange('B7').setNumberFormat('#,##0.0');
  liquidity.getRange('B8:B9').setNumberFormat('0.00');
  const audit = wb.worksheets.getItem('Audit');
  style(audit, 'Reconciliation checks', ['Check', 'Expected zero']);
  set(audit, 'A5:A7', [['Closing total less current/noncurrent'],
    ['Opening total less current/noncurrent'], ['Modeled RPO allocation residual']]);
  audit.getRange('B5:B7').setNumberFormat('#,##0.0');
  const raw = wb.worksheets.getItem('Source 10-K');
  style(raw, 'Unedited SEC filing excerpt', rawHeaders, 'L');
  set(raw, 'A2', [[testCase.filing_index_url]]);
  const rows = testCase.records.map(r => [r.id, r.concept, r.start, r.end,
    r.filed, r.form, r.accession, r.value, r.fy, r.fp, r.frame, r.unit]);
  set(raw, `A5:L${rows.length + 4}`, rows);
  raw.getRange('A:A').format.columnWidth = 22;
  raw.getRange('B:B').format.columnWidth = 51;
  raw.getRange('C:F').format.columnWidth = 17;
  raw.getRange('G:G').format.columnWidth = 26;
  raw.getRange('H:H').format.columnWidth = 22;
  raw.getRange('I:L').format.columnWidth = 14;
  raw.getRange(`H5:H${rows.length + 4}`).setNumberFormat('#,##0;(#,##0);-');
  raw.freezePanes.freezeRows(4);
  raw.tables.add(`A4:L${rows.length + 4}`, true, 'RpoSecFacts');
  const map = wb.worksheets.getItem('Filing Map');
  style(map, 'Provenance and data boundary', ['Field', 'Value']);
  set(map, 'A5:B12', [['CIK', `CIK${String(testCase.cik).padStart(10, '0')}`],
    ['Accession', testCase.filing_accession], ['Annual start', testCase.annual_start],
    ['Annual end', testCase.annual_end], ['Previous end', testCase.prior_end],
    ['Source excerpt SHA-256', testCase.source_excerpt_sha256],
    ['Annual source SHA-256', testCase.source_raw_json_sha256],
    ['Source facts', 'SEC public filing; scenario/faults authored by benchmark']]);
  map.getRange('A:A').format.columnWidth = 32;
  map.getRange('B:B').format.columnWidth = 85;
  set(map, 'A14', [[testCase.filing_index_url]]);
  for (const [key, { good, bad }] of targetMap) {
    const bang = key.lastIndexOf('!');
    wb.worksheets.getItem(key.slice(0, bang)).getRange(key.slice(bang + 1)).formulas = [[faulted.has(key) ? bad : good]];
  }
  wb.recalculate();
  return wb;
}
await fs.mkdir(outRoot, { recursive: true });
for (const [index, testCase] of cases.entries()) {
  const dir = path.join(outRoot, testCase.case_id);
  await fs.mkdir(dir, { recursive: true });
  const targetMap = formulas(testCase);
  const keys = [...targetMap.keys()].filter(k => !k.startsWith('Audit!'));
  const selected = new Set(Array.from({ length: 9 }, (_, i) => keys[(index * 11 + i * 7) % keys.length]));
  if (selected.size !== 9) throw new Error(`fault selection collision ${testCase.case_id}`);
  for (const [name, faulted] of [['actor.xlsx', selected], ['reference.xlsx', new Set()]]) {
    const wb = workbook(testCase, targetMap, faulted);
    if (process.env.SEC_RPO_RENDER_QA === '1' && name === 'reference.xlsx') {
      for (const [sheet, range] of [['Executive', 'A1:B12'], ['Filing Selection', 'A1:B18'],
        ['Liability Rollforward', 'A1:B14'], ['RPO Scenario', 'A1:C11'],
        ['Liquidity Review', 'A1:B10'], ['Audit', 'A1:B8'],
        ['Source 10-K', 'A1:L12'], ['Filing Map', 'A1:B15']]) {
        const rendered = await wb.render({ sheetName: sheet, range, scale: 1.25, format: 'png' });
        await fs.writeFile(path.join(dir, `qa-${sheet.toLowerCase().replaceAll(' ', '-')}.png`),
          new Uint8Array(await rendered.arrayBuffer()));
      }
    }
    const file = await SpreadsheetFile.exportXlsx(wb);
    await file.save(path.join(dir, name));
  }
  await fs.writeFile(path.join(dir, 'private-oracle.json'), JSON.stringify({
    case_id: testCase.case_id, sheet_order: SHEETS, faulted: [...selected].sort(),
    targets: Object.fromEntries([...targetMap].map(([k, v]) => [k, v.good])),
  }, null, 2) + '\n');
  await fs.writeFile(path.join(dir, 'task.md'),
    `# Contract obligations and RPO audit\n\nOpen the attached ${testCase.ticker} FY2024 workbook in Microsoft Excel for the web. Repair unmarked formula defects across the 10-K fact selection, contract-liability classification and rollforward, remaining-performance-obligation scenario, and liquidity views. Save and submit the downloaded .xlsx. Preserve source records, model assumptions, unrelated formulas, tables, and sheet structure. The scenario is a benchmark-authored stress case, not an SEC forecast or cash-flow projection.\n`);
  process.stdout.write(`${testCase.case_id}: 8 sheets, ${targetMap.size} formulas, 9 injected faults\n`);
}
