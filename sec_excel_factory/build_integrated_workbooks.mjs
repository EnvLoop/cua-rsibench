import fs from 'node:fs/promises';
import path from 'node:path';
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool';

// Every authored workbook starts with the frozen, independently extracted SEC
// rows in prepare_integrated_cases.py. Only private work/ output is created.
const [, , manifestPath, outputRoot, limitArg = '140'] = process.argv;
if (!manifestPath || !outputRoot) throw new Error('usage: node build_integrated_workbooks.mjs CASES_JSON OUTPUT_ROOT [LIMIT]');
const cases = JSON.parse(await fs.readFile(manifestPath, 'utf8'));
const limit = Math.min(cases.length, Number(limitArg));
if (!Number.isInteger(limit) || limit < 1) throw new Error('limit must be a positive integer');

const annualMetrics = ['revenue', 'operating_income', 'operating_cash_flow',
  'capital_expenditures', 'cost_of_sales', 'assets', 'liabilities', 'equity',
  'inventory', 'trade_payables', 'cash'];
const q3Metrics = annualMetrics.slice(0, 5);
const rawHeaders = ['Record ID', 'Ticker', 'Metric', 'US-GAAP concept', 'Start', 'End',
  'Filed', 'Form', 'Accession', 'Fiscal year', 'Fiscal period', 'Frame', 'Unit', 'Reported USD'];
const useQuarter = split => split !== 'train_candidate';
const useWorkingCapital = split => split === 'final_candidate';
const useScenario = split => split !== 'selection_candidate';
const sheetList = split => [
  'Review', 'FY Selection', ...(useQuarter(split) ? ['Q3 Selection', 'Q4 Bridge'] : []),
  ...(useWorkingCapital(split) ? ['Working Capital'] : []),
  ...(useScenario(split) ? ['Scenario'] : []), 'Audit', 'Annual 10-K',
  ...(useQuarter(split) ? ['Q3 10-Q'] : []), 'Source Map',
];
function rawRow(record, baseRows) {
  const i = baseRows.findIndex(r => r.id === record.id);
  if (i < 0) throw new Error(`source record missing ${record.id}`);
  return i + 5;
}
function priorFact(pkg, metric) {
  const candidates = pkg.annual_rows.filter(r => r.metric === metric && r.end < pkg.annual_end
    && r.form === '10-K' && r.accession === pkg.annual_accession && !r.start);
  if (!candidates.length) throw new Error(`prior balance missing ${pkg.ticker}/${pkg.fiscal_year}/${metric}`);
  candidates.sort((a, b) => b.end.localeCompare(a.end));
  return candidates[0];
}
function priorFlow(pkg, metric) {
  const candidates = pkg.annual_rows.filter(r => r.metric === metric && r.end < pkg.annual_end
    && r.form === '10-K' && r.accession === pkg.annual_accession && r.start);
  if (!candidates.length) throw new Error(`prior flow missing ${pkg.ticker}/${pkg.fiscal_year}/${metric}`);
  candidates.sort((a, b) => b.end.localeCompare(a.end));
  return candidates[0];
}
function quarterFlow(pkg, metric) {
  const candidates = pkg.q3_rows.filter(r => r.metric === metric && r.end === pkg.q3_end
    && r.start && r.start !== pkg.annual_start && r.accession === pkg.q3_accession);
  if (!candidates.length) return null;
  candidates.sort((a, b) => b.start.localeCompare(a.start));
  return candidates[0];
}
function targetsFor(testCase) {
  const pkg = testCase.source_package;
  const refs = new Map();
  const all = new Map();
  const put = (sheet, addr, correct, faulty) => all.set(`${sheet}!${addr}`, { correct, faulty });
  const annual = metric => `'Annual 10-K'!N${rawRow(pkg.canonical[`annual:${metric}`], pkg.annual_rows)}`;
  const q3 = metric => `'Q3 10-Q'!N${rawRow(pkg.canonical[`q3:${metric}`], pkg.q3_rows)}`;
  for (let i = 0; i < annualMetrics.length; i++) {
    const metric = annualMetrics[i], row = i + 5;
    refs.set(metric, `B${row}`);
    const correct = `=${annual(metric)}/1000000`;
    const wrong = i === 0 ? `='Annual 10-K'!N${rawRow(priorFlow(pkg, metric), pkg.annual_rows)}/1000000`
      : i === 1 ? `=-${annual(metric)}/1000000`
      : i === 2 ? `=${annual('capital_expenditures')}/1000000`
      : i === 3 ? `=${annual(metric)}/1000`
      : i === 4 ? `=${annual('revenue')}/1000000`
      : `=${annual(metric)}/1000000*1.01`;
    put('FY Selection', `B${row}`, correct, wrong);
  }
  if (useQuarter(testCase.split)) {
    for (let i = 0; i < q3Metrics.length; i++) {
      const metric = q3Metrics[i], row = i + 5;
      const correct = `=${q3(metric)}/1000000`;
      const sameMetricQuarter = quarterFlow(pkg, metric);
      const wrong = i === 0 || i === 2
        ? sameMetricQuarter
          ? `='Q3 10-Q'!N${rawRow(sameMetricQuarter, pkg.q3_rows)}/1000000`
          : `=${q3(q3Metrics[(i + 1) % q3Metrics.length])}/1000000`
        : `=${q3(q3Metrics[(i + 1) % q3Metrics.length])}/1000000`;
      put('Q3 Selection', `B${row}`, correct, wrong);
      put('Q4 Bridge', `B${row}`, `='FY Selection'!B${row}-'Q3 Selection'!B${row}`,
        i % 2 ? `='FY Selection'!B${row}-'Q3 Selection'!B5`
          : `='FY Selection'!B${row}+'Q3 Selection'!B${row}`);
    }
    put('Q4 Bridge', 'C10', '=B6/B5', '=B6/\'FY Selection\'!B5');
    put('Q4 Bridge', 'C11', '=B7-B8', '=B7+B8');
    put('Q4 Bridge', 'C12', '=C11/B5', '=C11/\'FY Selection\'!B5');
  }
  if (useWorkingCapital(testCase.split)) {
    const wc = [
      ['B5', "='FY Selection'!B13", "='FY Selection'!B14"],
      ['B6', "='FY Selection'!B14", "='FY Selection'!B13"],
      ['B7', "='FY Selection'!B9", "='FY Selection'!B5"],
      ['B8', "='Source Map'!B6", "='Source Map'!B7"],
      ['B12', `='Annual 10-K'!N${rawRow(priorFact(pkg, 'inventory'), pkg.annual_rows)}/1000000`, '=B5'],
      ['B13', `='Annual 10-K'!N${rawRow(priorFact(pkg, 'trade_payables'), pkg.annual_rows)}/1000000`, '=B6'],
      ['B9', '=(B5+B12)/2/B7*B8', '=B5/B7*B8'],
      ['B10', '=(B6+B13)/2/B7*B8', '=(B6+B13)/2/\'FY Selection\'!B5*B8'],
      ['B11', '=B5-B6', '=B5+B6'],
    ];
    for (const [cell, correct, faulty] of wc) put('Working Capital', cell, correct, faulty);
  }
  if (useScenario(testCase.split)) {
    const wc = useWorkingCapital(testCase.split);
    put('Scenario', 'C5', wc ? "='Working Capital'!B5+B5" : "='FY Selection'!B13+B5",
      wc ? "='Working Capital'!B5-B5" : "='FY Selection'!B13-B5");
    put('Scenario', 'C6', wc ? "='Working Capital'!B6+B6" : "='FY Selection'!B14+B6",
      wc ? "='Working Capital'!B6-B6" : "='FY Selection'!B14-B6");
    put('Scenario', 'C7', "='FY Selection'!B8*B7", "='FY Selection'!B8*(1+B7)");
    put('Scenario', 'C8', '=C5-C6', '=C5+C6');
    put('Scenario', 'C9', "='FY Selection'!B7-C7", "='FY Selection'!B7+C7");
    put('Scenario', 'C10', "=C9/'FY Selection'!B5", "=C9/'FY Selection'!B9");
  }
  put('Review', 'B5', "='FY Selection'!B5", "='FY Selection'!B6");
  put('Review', 'B6', "='FY Selection'!B6/'FY Selection'!B5", "='FY Selection'!B6/'FY Selection'!B9");
  put('Review', 'B7', "='FY Selection'!B7-'FY Selection'!B8", "='FY Selection'!B7+'FY Selection'!B8");
  if (useQuarter(testCase.split)) {
    put('Review', 'B8', "='Q4 Bridge'!B5", "='Q3 Selection'!B5");
    put('Review', 'B9', "='Q4 Bridge'!C10", "='FY Selection'!B6/'FY Selection'!B5");
  } else {
    put('Review', 'B8', "='FY Selection'!B5-'FY Selection'!B9", "='FY Selection'!B5+'FY Selection'!B9");
    put('Review', 'B9', "='FY Selection'!B15", "='FY Selection'!B13");
  }
  if (useScenario(testCase.split)) {
    put('Review', 'B10', "=Scenario!C9", "=Scenario!C8");
    put('Review', 'B11', "=Scenario!C8", "=Scenario!C5");
  } else {
    put('Review', 'B10', "='Q4 Bridge'!C11", "='Q4 Bridge'!B7");
    put('Review', 'B11', "='Q4 Bridge'!C12", "='Q4 Bridge'!C10");
  }
  put('Audit', 'B5', "='FY Selection'!B10-'FY Selection'!B11-'FY Selection'!B12",
    "='FY Selection'!B10-'FY Selection'!B11+'FY Selection'!B12");
  if (useQuarter(testCase.split)) {
    put('Audit', 'B6', "='Q4 Bridge'!B5+'Q3 Selection'!B5-'FY Selection'!B5",
      "='Q4 Bridge'!B5-'Q3 Selection'!B5-'FY Selection'!B5");
  }
  return all;
}

function valuesForRows(rows) {
  return rows.map(r => [r.id, r.ticker, r.metric, r.concept, r.start, r.end,
    r.filed, r.form, r.accession, r.fy, r.fp, r.frame, r.unit, r.value]);
}
function set(sheet, address, values) { sheet.getRange(address).values = values; }
function decorate(sheet, title, headers, lastColumn = 'B') {
  sheet.showGridLines = false;
  set(sheet, 'A1', [[title]]);
  sheet.getRange('A1').format.font = { name: 'Arial', size: 15, bold: true, color: '#173A5E' };
  set(sheet, `A4:${lastColumn}4`, [headers]);
  sheet.getRange(`A4:${lastColumn}4`).format = {
    fill: '#173A5E', font: { name: 'Arial', size: 10, bold: true, color: '#FFFFFF' },
    rowHeight: 30, wrapText: true,
  };
  sheet.getRange('A:A').format.columnWidth = 34;
  sheet.getRange('B:B').format.columnWidth = 24;
  if (lastColumn === 'C') sheet.getRange('C:C').format.columnWidth = 25;
}
function rawSheet(wb, name, rows, sourceUrl) {
  const sheet = wb.worksheets.getItem(name);
  decorate(sheet, `${name} — unedited SEC filing facts`, rawHeaders, 'N');
  set(sheet, 'A2', [[sourceUrl]]);
  sheet.getRange('A2').format.columnWidth = 40;
  const end = rows.length + 4;
  set(sheet, `A5:N${end}`, valuesForRows(rows));
  sheet.getRange('A:A').format.columnWidth = 22;
  sheet.getRange('B:C').format.columnWidth = 22;
  sheet.getRange('D:D').format.columnWidth = 48;
  sheet.getRange('E:H').format.columnWidth = 16;
  sheet.getRange('I:I').format.columnWidth = 26;
  sheet.getRange('J:M').format.columnWidth = 14;
  sheet.getRange('N:N').format.columnWidth = 22;
  sheet.getRange(`N5:N${end}`).setNumberFormat('#,##0;(#,##0);-');
  sheet.freezePanes.freezeRows(4);
  sheet.tables.add(`A4:N${end}`, true, name === 'Annual 10-K' ? 'AnnualSecFacts' : 'Q3SecFacts');
}
function createWorkbook(testCase, targets, faulted) {
  const pkg = testCase.source_package;
  const wb = Workbook.create();
  const names = sheetList(testCase.split);
  for (const name of names) wb.worksheets.add(name);
  const review = wb.worksheets.getItem('Review');
  decorate(review, `${pkg.ticker} FY${pkg.fiscal_year} filing reconciliation`, ['Measure', 'USD millions / ratio']);
  set(review, 'A2', [['Repair unmarked calculation faults; preserve source facts.']]);
  set(review, 'A5:A11', [['FY revenue'], ['FY operating margin'], ['FY free cash flow'],
    [useQuarter(testCase.split) ? 'Q4 revenue bridge' : 'FY gross profit'],
    [useQuarter(testCase.split) ? 'Q4 operating margin' : 'Cash balance'],
    [useScenario(testCase.split) ? 'Stressed free cash flow' : 'Q4 free cash flow'],
    [useScenario(testCase.split) ? 'Stressed working capital' : 'Q4 FCF margin']]);
  review.getRange('B5').setNumberFormat('#,##0.0');
  review.getRange('B6').setNumberFormat('0.0%');
  review.getRange('B7:B8').setNumberFormat('#,##0.0');
  if (useQuarter(testCase.split)) review.getRange('B9').setNumberFormat('0.0%');
  review.getRange('B10:B11').setNumberFormat('#,##0.0');
  if (!useScenario(testCase.split)) review.getRange('B11').setNumberFormat('0.0%');
  const fy = wb.worksheets.getItem('FY Selection');
  decorate(fy, 'Annual 10-K fact selection', ['Metric', 'USD millions']);
  set(fy, 'A2', [[`Use filing ${pkg.annual_accession}, fiscal period ${pkg.annual_start} to ${pkg.annual_end}.`]]);
  set(fy, 'A5:A15', annualMetrics.map(m => [m.replaceAll('_', ' ')]));
  fy.getRange('B5:B15').setNumberFormat('#,##0.0');
  if (useQuarter(testCase.split)) {
    const q3 = wb.worksheets.getItem('Q3 Selection');
    decorate(q3, 'Nine-month 10-Q fact selection', ['Metric', 'USD millions']);
    set(q3, 'A2', [[`Use YTD facts from ${pkg.q3_accession}, ending ${pkg.q3_end}.`]]);
    set(q3, 'A5:A9', q3Metrics.map(m => [m.replaceAll('_', ' ')]));
    q3.getRange('B5:B9').setNumberFormat('#,##0.0');
    const q4 = wb.worksheets.getItem('Q4 Bridge');
    decorate(q4, 'Q4 derived from FY less Q3 YTD', ['Metric', 'Q4 USD millions', 'Derived ratio'], 'C');
    set(q4, 'A5:A9', q3Metrics.map(m => [m.replaceAll('_', ' ')]));
    set(q4, 'A10:A12', [['Q4 operating margin'], ['Q4 free cash flow'], ['Q4 FCF margin']]);
    q4.getRange('B5:B9').setNumberFormat('#,##0.0');
    q4.getRange('C10').setNumberFormat('0.0%');
    q4.getRange('C11').setNumberFormat('#,##0.0');
    q4.getRange('C12').setNumberFormat('0.0%');
  }
  if (useWorkingCapital(testCase.split)) {
    const wc = wb.worksheets.getItem('Working Capital');
    decorate(wc, 'Inventory and payables cycle', ['Measure', 'USD millions / days']);
    set(wc, 'A5:A13', [['Closing inventory'], ['Closing trade payables'], ['Cost of sales'],
      ['Fiscal days'], ['Average inventory days'], ['Average payables days'],
      ['Closing net working capital'], ['Opening inventory'], ['Opening payables']]);
    wc.getRange('B5:B13').setNumberFormat('#,##0.0');
  }
  if (useScenario(testCase.split)) {
    const sc = wb.worksheets.getItem('Scenario');
    decorate(sc, 'Modeled operating stress — not SEC facts', ['Driver / output', 'Assumption', 'Result'], 'C');
    set(sc, 'A5:A10', [['Inventory shock → stressed inventory'], ['Payables shock → stressed payables'],
      ['Capex multiplier → stressed capex'], ['Stressed working capital'],
      ['Stressed free cash flow'], ['Stressed FCF margin']]);
    set(sc, 'B5:B7', [[testCase.scenario.inventory_shock_m],
      [testCase.scenario.payables_shock_m], [testCase.scenario.capex_multiplier]]);
    sc.getRange('B5:B7').format = { fill: '#FFF0BE', font: { name: 'Arial', size: 10, color: '#185AA6' } };
    sc.getRange('B5:B6').setNumberFormat('#,##0.0');
    sc.getRange('B7').setNumberFormat('0.000');
    sc.getRange('C5:C9').setNumberFormat('#,##0.0');
    sc.getRange('C10').setNumberFormat('0.0%');
  }
  const audit = wb.worksheets.getItem('Audit');
  decorate(audit, 'Independent reconciliation checks', ['Check', 'Expected zero']);
  set(audit, 'A5', [['Assets - liabilities - equity']]);
  if (useQuarter(testCase.split)) set(audit, 'A6', [['Q4 + Q3 YTD - FY revenue']]);
  rawSheet(wb, 'Annual 10-K', pkg.annual_rows, pkg.source_url);
  if (useQuarter(testCase.split)) rawSheet(wb, 'Q3 10-Q', pkg.q3_rows, pkg.source_url);
  const sm = wb.worksheets.getItem('Source Map');
  decorate(sm, 'Filing provenance and method', ['Field', 'Value']);
  set(sm, 'A5:B11', [
    ['CIK', `CIK${String(pkg.cik).padStart(10, '0')}`], ['Fiscal days', pkg.fiscal_days],
    ['Q3 YTD days', pkg.q3_days], ['Annual accession', pkg.annual_accession],
    ['Annual filed', pkg.annual_filed], ['Q3 accession', pkg.q3_accession],
    ['Q3 filed', pkg.q3_filed],
  ]);
  set(sm, 'A13', [['SEC filing facts are public. Scenario and inserted faults are benchmark-authored.']]);
  set(sm, 'A14', [[pkg.source_url]]);
  sm.getRange('A:A').format.columnWidth = 76;
  for (const [key, formula] of targets) {
    const bang = key.lastIndexOf('!');
    const name = key.slice(0, bang), addr = key.slice(bang + 1);
    const cell = wb.worksheets.getItem(name).getRange(addr);
    cell.formulas = [[faulted.has(key) ? formula.faulty : formula.correct]];
  }
  wb.recalculate();
  return wb;
}

await fs.mkdir(outputRoot, { recursive: true });
let count = 0;
for (const testCase of cases.slice(0, limit)) {
  const dir = path.join(outputRoot, testCase.split, testCase.case_id);
  await fs.mkdir(dir, { recursive: true });
  const targets = targetsFor(testCase);
  const keys = [...targets.keys()].filter(k => !k.startsWith('Audit!'));
  const start = testCase.fault_offset % keys.length;
  const selected = new Set(Array.from({ length: testCase.fault_count }, (_, i) => keys[(start + i * 7) % keys.length]));
  if (selected.size !== testCase.fault_count) throw new Error(`fault pool collision ${testCase.case_id}`);
  for (const [file, faulted] of [['actor.xlsx', selected], ['reference.xlsx', new Set()]]) {
    const wb = createWorkbook(testCase, targets, faulted);
    if (process.env.SEC_EXCEL_RENDER_QA === '1' && file === 'reference.xlsx') {
      const ranges = {
        'Review': 'A1:B12', 'FY Selection': 'A1:B16', 'Q3 Selection': 'A1:B10',
        'Q4 Bridge': 'A1:C13', 'Working Capital': 'A1:B14', 'Scenario': 'A1:C11',
        'Audit': 'A1:B7', 'Annual 10-K': 'A1:N12', 'Q3 10-Q': 'A1:N12',
        'Source Map': 'A1:B15',
      };
      for (const [sheet, range] of Object.entries(ranges)) {
        if (!sheetList(testCase.split).includes(sheet)) continue;
        const rendered = await wb.render({ sheetName: sheet, range, scale: 1.25, format: 'png' });
        await fs.writeFile(path.join(dir, `qa-${sheet.toLowerCase().replaceAll(' ', '-')}.png`),
          new Uint8Array(await rendered.arrayBuffer()));
      }
    }
    const exported = await SpreadsheetFile.exportXlsx(wb);
    await exported.save(path.join(dir, file));
  }
  await fs.writeFile(path.join(dir, 'private-oracle.json'), JSON.stringify({
    case_id: testCase.case_id, split: testCase.split, source_group: testCase.source_group,
    sheet_order: sheetList(testCase.split), faulted: [...selected].sort(),
    targets: Object.fromEntries([...targets].map(([k, v]) => [k, v.correct])),
  }, null, 2) + '\n');
  await fs.writeFile(path.join(dir, 'task.md'),
    `# Filing-close workbook audit\n\nOpen the supplied workbook in Microsoft Excel for the web. The workbook represents ${testCase.source_package.ticker} FY${testCase.source_package.fiscal_year}. Diagnose and repair its unmarked calculation faults across the annual filing selection, quarter bridge, working-capital and scenario views that are present. Save the workbook and submit the downloaded .xlsx.\n\nUse the cited original Form 10-K accession ${testCase.source_package.annual_accession} and Form 10-Q accession ${testCase.source_package.q3_accession}. Keep every SEC source record, scenario input, unrelated formula, sheet, and table intact. The scenario shocks and inserted faults are benchmark-authored; they are not SEC-reported amounts.\n`);
  count++;
  if (count % 10 === 0 || count === limit) process.stdout.write(`${count}/${limit} workbook pairs exported\n`);
}
