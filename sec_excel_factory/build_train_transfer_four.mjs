import fs from 'node:fs/promises';
import path from 'node:path';
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool';

// TRAIN-only analogue authoring. Private cases contain reviewed original SEC
// facts; this source contains no issuer, accession, final case, or answer.
const [, , casesDirectory, outputDirectory] = process.argv;
if (!casesDirectory || !outputDirectory) {
  throw new Error('usage: node build_train_transfer_four.mjs CASES_DIR OUTPUT_DIR');
}

const PROFILES = new Set(['cash_train_profile', 'interest_train_profile']);
const COLORS = { navy: '#173A5E', teal: '#167A83', pale: '#E8F3F5', amber: '#FFF0BE', blue: '#185AA6', gray: '#65717B' };
const CASH_METRICS = [
  ['operating', 'Operating cash flow'], ['investing', 'Investing cash flow'],
  ['financing', 'Financing cash flow'], ['fx', 'Foreign-exchange effect'],
  ['net_change', 'Reported net change in cash and restricted cash'],
  ['beginning', 'Beginning cash and restricted cash'],
  ['ending', 'Ending cash and restricted cash'],
  ['cash', 'Ending cash and cash equivalents'],
  ['restricted', 'Ending restricted cash and cash equivalents'],
];
const INTEREST_METRICS = [
  ['operating_income', 'Operating income'],
  ['interest_expense_abs', 'Reported interest expense magnitude'],
  ['cash_from_operations', 'Operating cash flow'],
  ['debt_component_1', 'Tracked debt principal component 1'],
  ['debt_component_2', 'Tracked debt principal component 2'],
  ['debt_component_3', 'Tracked debt principal component 3'],
  ['debt_component_4', 'Tracked debt principal component 4'],
  ['debt_principal_direct', 'Direct reported gross principal, if available'],
  ['debt_carrying', 'Reported debt carrying value, if applicable'],
  ['unamortized_cost', 'Reported unamortized issuance cost, if applicable'],
];

function put(sheet, address, value) { sheet.getRange(address).values = [[value]]; }
function formula(sheet, address, value) { sheet.getRange(address).formulas = [[value]]; }
function layout(sheet, title, headings, lastColumn = 'B', lastBodyRow = 12) {
  sheet.showGridLines = false;
  put(sheet, 'A1', title);
  sheet.getRange('A1').format.font = { name: 'Arial', size: 15, bold: true, color: COLORS.navy };
  sheet.getRange(`A4:${lastColumn}4`).values = [headings];
  sheet.getRange(`A4:${lastColumn}4`).format = {
    fill: COLORS.navy,
    font: { name: 'Arial', size: 10, bold: true, color: '#FFFFFF' },
    rowHeight: 28,
    verticalAlignment: 'center',
  };
  sheet.getRange('A:A').format.columnWidth = 48;
  sheet.getRange('B:C').format.columnWidth = 22;
  if (lastBodyRow >= 5) sheet.getRange(`A5:${lastColumn}${lastBodyRow}`).format.font = {
    name: 'Arial', size: 10, color: '#1D2933' };
  sheet.freezePanes.freezeRows(4);
}
function makeSheets(workbook, names) {
  for (const name of names) workbook.worksheets.add(name);
}
function sourceSheets(workbook, c, metrics) {
  const source = workbook.worksheets.getItem('Source facts');
  layout(source, 'Original 10-K facts (USD millions)',
         ['Filed metric', `Prior: ${c.periods[0].period_end}`, `Current: ${c.periods[1].period_end}`],
         'C', metrics.length + 4);
  put(source, 'A2', `Original filing: ${c.source.original_10k_url}`);
  source.getRange('A2').format.font = { name: 'Arial', size: 9, color: COLORS.gray };
  source.getRange('B5:C16').setNumberFormat('#,##0.0;(#,##0.0);-');
  source.getRange('B5:C16').format.horizontalAlignment = 'right';
  for (let i = 0; i < metrics.length; i++) {
    const [key, label] = metrics[i];
    const row = i + 5;
    put(source, `A${row}`, label);
    for (let p = 0; p < 2; p++) {
      const entry = c.periods[p].facts[key];
      if (entry && typeof entry.value === 'number') {
        put(source, `${p ? 'C' : 'B'}${row}`, entry.value);
      } else {
        put(source, `${p ? 'C' : 'B'}${row}`, 'n.a.');
      }
    }
  }
  source.getRange('B5:C16').format.font = { name: 'Arial', size: 10, color: COLORS.blue };

  const lineage = workbook.worksheets.getItem('Source lineage');
  layout(lineage, 'Original filing fact locators',
         ['Metric', 'Period end', 'Evidence class', 'XBRL tag / note label',
          'Inline fact ID', 'Context / row SHA-256', 'Original SEC filing', 'Accession'], 'H', 4);
  lineage.getRange('A:A').format.columnWidth = 36;
  lineage.getRange('B:C').format.columnWidth = 20;
  lineage.getRange('D:F').format.columnWidth = 36;
  lineage.getRange('G:G').format.columnWidth = 70;
  lineage.getRange('H:H').format.columnWidth = 28;
  let next = 5;
  for (let p = 0; p < 2; p++) {
    for (const [key, label] of metrics) {
      const item = c.periods[p].facts[key];
      if (!item || typeof item.value !== 'number') continue;
      lineage.getRange(`A${next}:H${next}`).values = [[
        label, c.periods[p].period_end, item.evidence_class,
        item.tag || item.note_label || '', item.ix_id || '',
        [item.context_ref || '', item.row_sha256 || ''].filter(Boolean).join(' / '),
        c.source.original_10k_url, c.source.accession,
      ]];
      lineage.getRange(`A${next}:H${next}`).format.rowHeight = 36;
      next++;
    }
  }
  lineage.getRange(`A5:H${next - 1}`).format.font = { name: 'Arial', size: 10, color: '#1D2933' };
  lineage.getRange(`D5:H${next - 1}`).format.wrapText = true;
  return source;
}
function cashFormulaMap() {
  const f = new Map();
  const add = (sheet, addr, good, bad) => f.set(`${sheet}!${addr}`, { good, bad });
  const src = (col, row) => `='Source facts'!${col}${row}`;
  for (const [col] of [['B'], ['C']]) {
    for (let row = 5; row <= 8; row++) add('Flow build', `${col}${row}`, src(col, row), null);
    add('Flow build', `${col}9`, `=${col}5+${col}6+${col}7+${col}8`, null);
    for (const [to, from] of [[10, 9], [12, 10], [14, 11], [15, 12], [16, 13]]) {
      add('Flow build', `${col}${to}`, src(col, from), null);
    }
    add('Flow build', `${col}11`, `=${col}9-${col}10`, null);
    add('Flow build', `${col}13`, `=${col}12+${col}9`, null);
    add('Flow build', `${col}17`, `=${col}14-${col}15-${col}16`, null);
    add('Flow build', `${col}18`, `=${col}13-${col}14`, null);
    add('Flow build', `${col}19`, `=${col}5/${col}10`, null);
    add('Flow build', `${col}20`, `=${col}6/${col}10`, null);
  }
  add('Flow build', 'C21', '=C5-B5', null);
  add('Cash scenario', 'C5', "='Flow build'!C5*(1+B5)", "='Flow build'!C5*(1-B5)");
  add('Cash scenario', 'C6', "='Flow build'!C6-'Flow build'!C5*B6", null);
  add('Cash scenario', 'C7', "='Flow build'!C8+'Flow build'!C5*B7", null);
  add('Cash scenario', 'C8', "='Flow build'!C7", null);
  add('Cash scenario', 'C9', '=C5+C6+C7+C8', '=C5+C6-C7+C8');
  add('Cash scenario', 'C10', "='Flow build'!C12+C9", "='Flow build'!C15+C9");
  add('Cash scenario', 'C11', "='Flow build'!C16", null);
  add('Cash scenario', 'C12', '=C10-C11', null);
  for (const [row, good] of [[5,"='Flow build'!C14"],[6,"='Flow build'!C15"],
    [7,"='Flow build'!C14-'Flow build'!B14"],[8,"='Cash scenario'!C9"],
    [9,"='Cash scenario'!C10"],[10,"='Cash scenario'!C12"],
    [11,"='Flow build'!C19"],[12,"='Flow build'!C21"]]) add('Cash summary', `B${row}`, good, null);
  for (const [row, good] of [[5,"='Flow build'!C9-'Flow build'!C10"],
    [6,"='Flow build'!C14-'Flow build'!C15-'Flow build'!C16"],
    [7,"='Flow build'!C13-'Flow build'!C14"],
    [8,"='Cash scenario'!C10-'Flow build'!C12-'Cash scenario'!C9"]]) {
    add('Checks', `B${row}`, good, null);
  }
  const targetBad = new Map([
    ['Flow build!B5', src('C', 5)], ['Flow build!C5', src('B', 5)],
    ['Flow build!C6', src('C', 7)], ['Flow build!C9', '=C5+C6+C7'],
    ['Flow build!C11', '=C9+C10'], ['Flow build!C13', '=C12-C9'],
    ['Flow build!C17', '=C14-C15+C16'], ['Flow build!C19', '=C10/C5'],
    ['Cash scenario!C5', "='Flow build'!C5*(1-B5)"],
    ['Cash scenario!C9', '=C5+C6-C7+C8'],
    ['Cash scenario!C10', "='Flow build'!C15+C9"],
    ['Cash summary!B9', "='Cash scenario'!C12"],
  ]);
  for (const [key, bad] of targetBad) f.get(key).bad = bad;
  return { formulas: f, targets: [...targetBad.keys()] };
}
function interestFormulaMap(c) {
  const f = new Map();
  const add = (sheet, addr, good, bad) => f.set(`${sheet}!${addr}`, { good, bad });
  const src = (col, row) => `='Source facts'!${col}${row}`;
  for (const col of ['B', 'C']) {
    for (const row of [5, 6, 7]) add('Interest build', `${col}${row}`, src(col, row), null);
    const compCount = c.periods[col === 'B' ? 0 : 1].component_count;
    if (![3, 4].includes(compCount)) throw new Error('unsupported_debt_component_count');
    const componentCells = Array.from({ length: compCount }, (_, i) => src(col, i + 8).slice(1));
    add('Interest build', `${col}8`, `=${componentCells.join('+')}`, null);
    add('Interest build', `${col}9`, c.source.debt_control_kind === 'direct_principal'
      ? src(col, 12) : `=${src(col, 13).slice(1)}+${src(col, 14).slice(1)}`, null);
    add('Interest build', `${col}10`, `=${col}8-${col}9`, null);
    add('Interest build', `${col}11`, `=${col}5/${col}6`, null);
    add('Interest build', `${col}12`, `=${col}7/${col}6`, null);
  }
  add('Interest build', 'C13', '=C5-B5', null);
  add('Interest build', 'C14', '=C11-B11', null);
  add('Interest build', 'C15', '=C8-B8', null);
  add('Rate scenario', 'C5', "='Interest build'!C8", "='Interest build'!B8");
  add('Rate scenario', 'C6', '=C5*B5', '=C5*(1+B5)');
  add('Rate scenario', 'C7', "='Interest build'!C6+C6", "='Interest build'!C6-C6");
  add('Rate scenario', 'C8', "='Interest build'!C5*(1+B6)", null);
  add('Rate scenario', 'C9', "='Interest build'!C7*(1+B7)", null);
  add('Rate scenario', 'C10', '=C8/C7', '=C9/C7');
  add('Rate scenario', 'C11', '=C9/C7', null);
  for (const [row, good] of [[5,"='Interest build'!C11"], [6,"='Interest build'!C12"],
    [7,"='Interest build'!C8"], [8,"='Rate scenario'!C10"],
    [9,"='Rate scenario'!C11"], [10,'=B8-B5'],[11,"='Interest build'!C15"]]) {
    add('Interest summary', `B${row}`, good, null);
  }
  for (const [row, good] of [[5,"='Interest build'!C8-'Interest build'!C9"],
    [6,"='Rate scenario'!C7-'Interest build'!C6-'Rate scenario'!C6"],
    [7,"='Rate scenario'!C10*'Rate scenario'!C7-'Rate scenario'!C8"]]) {
    add('Checks', `B${row}`, good, null);
  }
  const badDebtSum = c.periods[1].component_count === 4
    ? `=${src('C',8).slice(1)}+${src('C',9).slice(1)}+${src('C',10).slice(1)}`
    : `=${src('C',8).slice(1)}+${src('C',9).slice(1)}`;
  const targetBad = new Map([
    ['Interest build!B5', src('C',5)], ['Interest build!C5', src('B',5)],
    ['Interest build!C6', src('C',7)], ['Interest build!C8', badDebtSum],
    ['Interest build!C9', c.source.debt_control_kind === 'direct_principal'
      ? src('B',12) : src('C',13)],
    ['Interest build!C11', '=C6/C5'], ['Interest build!C12', '=C5/C6'],
    ['Rate scenario!C5', "='Interest build'!B8"],
    ['Rate scenario!C6', '=C5*(1+B5)'],
    ['Rate scenario!C7', "='Interest build'!C6-C6"],
    ['Rate scenario!C10', '=C9/C7'],
    ['Interest summary!B8', "='Rate scenario'!C11"],
  ]);
  for (const [key, bad] of targetBad) f.get(key).bad = bad;
  return { formulas: f, targets: [...targetBad.keys()] };
}
function configureCash(workbook, c) {
  makeSheets(workbook, ['Cash summary', 'Cash scenario', 'Flow build', 'Source facts', 'Source lineage', 'Checks']);
  const summary = workbook.worksheets.getItem('Cash summary');
  layout(summary, 'Cash and restricted cash review', ['Measure', 'USD millions / ratio'], 'B', 12);
  put(summary, 'A2', 'Original filed cash-flow periods and a separately authored cash scenario.');
  const labels = [
    'Reported ending cash and restricted cash', 'Reported unrestricted cash',
    'Change in ending cash since prior year', 'Scenario net cash change',
    'Scenario ending cash and restricted cash', 'Scenario unrestricted cash',
    'Operating cash flow / signed net cash change', 'Current less prior operating cash flow',
  ];
  summary.getRange('A5:A12').values = labels.map(x => [x]);
  summary.getRange('B5:B12').setNumberFormat('#,##0.0;(#,##0.0);-');
  summary.getRange('B11').setNumberFormat('0.00');

  const scenario = workbook.worksheets.getItem('Cash scenario');
  layout(scenario, 'Authored cash scenario',
    ['Authored driver', 'Editable assumption', 'Modeled result', 'Result definition'], 'D', 12);
  scenario.getRange('D:D').format.columnWidth = 48;
  put(scenario, 'A2', 'Synthetic assumptions are not reported by the SEC issuer. Restricted cash is held at the filed amount.');
  scenario.getRange('A5:A7').values = [
    'Operating cash flow change', 'Additional investing use / filed operating cash flow',
    'FX change / filed operating cash flow',
  ].map(x => [x]);
  scenario.getRange('D5:D12').values = [
    'Modeled operating cash flow', 'Modeled investing cash flow',
    'Modeled FX effect', 'Filed financing cash flow held unchanged',
    'Modeled signed net cash change', 'Modeled ending cash and restricted cash',
    'Restricted cash held at filed balance', 'Modeled unrestricted cash',
  ].map(x => [x]);
  scenario.getRange('B5:B7').values = [[c.scenario.operating_change],
    [c.scenario.extra_investing_share], [c.scenario.fx_share_change]];
  scenario.getRange('B5:B7').format = { fill: COLORS.amber,
    font: { name: 'Arial', size: 10, color: COLORS.blue } };
  scenario.getRange('B5:B7').setNumberFormat('0.0%');
  scenario.getRange('C5:C12').setNumberFormat('#,##0.0;(#,##0.0);-');

  const build = workbook.worksheets.getItem('Flow build');
  layout(build, 'Signed cash-flow reconciliation',
    ['Measure', `Prior: ${c.periods[0].period_end}`, `Current: ${c.periods[1].period_end}`], 'C', 21);
  build.getRange('A5:A21').values = [
    'Operating cash flow', 'Investing cash flow', 'Financing cash flow',
    'Foreign-exchange effect', 'Sum of signed flow components',
    'Reported net cash change', 'Flow component residual',
    'Beginning cash and restricted cash', 'Beginning plus signed flow components',
    'Reported ending cash and restricted cash', 'Reported unrestricted cash',
    'Reported restricted cash', 'Ending total less both cash balances',
    'Bridge ending less reported ending',
    'Operating cash flow / signed net change',
    'Investing cash flow / signed net change',
    'Current less prior operating cash flow',
  ].map(x => [x]);
  build.getRange('B5:C21').setNumberFormat('#,##0.0;(#,##0.0);-');
  build.getRange('B19:C20').setNumberFormat('0.00');
  sourceSheets(workbook, c, CASH_METRICS);
  const checks = workbook.worksheets.getItem('Checks');
  layout(checks, 'Reconciliation differences', ['Independent check', 'Expected zero'], 'B', 8);
  checks.getRange('A5:A8').values = [
    'Signed flows less reported net change',
    'Ending total less unrestricted and restricted cash',
    'Calculated ending total less reported ending total',
    'Scenario ending total less beginning and modeled change',
  ].map(x => [x]);
  checks.getRange('B5:B8').setNumberFormat('0.00;0.00;0.00');
  checks.getRange('B5:B8').conditionalFormats.addCustom('=ABS(B5)>0.005', {
    fill: '#FCE8E6', font: { bold: true, color: '#A51616' },
  });
  return cashFormulaMap();
}
function configureInterest(workbook, c) {
  makeSheets(workbook, ['Interest summary', 'Rate scenario', 'Interest build', 'Source facts', 'Source lineage', 'Checks']);
  const summary = workbook.worksheets.getItem('Interest summary');
  layout(summary, 'Interest coverage review', ['Measure', 'USD millions / ratio'], 'B', 11);
  put(summary, 'A2', 'Original reported income, cash flow, and debt; separately authored rate and earnings changes.');
  summary.getRange('A5:A11').values = [
    'Reported operating income / interest expense', 'Reported operating cash flow / interest expense',
    'Tracked gross debt principal', 'Scenario operating income / interest expense',
    'Scenario operating cash flow / interest expense',
    'Scenario less reported operating coverage', 'Change in gross debt principal since prior year',
  ].map(x => [x]);
  summary.getRange('B5:B11').setNumberFormat('#,##0.00;(#,##0.00);-');
  const scenario = workbook.worksheets.getItem('Rate scenario');
  layout(scenario, 'Authored interest and income scenario',
    ['Authored driver', 'Editable assumption', 'Modeled result', 'Result definition'], 'D', 11);
  scenario.getRange('D:D').format.columnWidth = 48;
  put(scenario, 'A2', 'The rate change applies only to tracked gross debt principal. No refinancing or issuer forecast is asserted.');
  scenario.getRange('A5:A7').values = [
    'Added annual rate on tracked gross principal', 'Operating income change',
    'Operating cash flow change',
  ].map(x => [x]);
  scenario.getRange('D5:D11').values = [
    'Tracked gross principal', 'Incremental annual interest',
    'Modeled annual interest expense', 'Modeled operating income',
    'Modeled operating cash flow', 'Modeled operating income coverage',
    'Modeled operating cash flow coverage',
  ].map(x => [x]);
  scenario.getRange('B5:B7').values = [[c.scenario.rate_change],
    [c.scenario.income_change], [c.scenario.cash_flow_change]];
  scenario.getRange('B5:B7').format = { fill: COLORS.amber,
    font: { name: 'Arial', size: 10, color: COLORS.blue } };
  scenario.getRange('B5').setNumberFormat('0.00%');
  scenario.getRange('B6:B7').setNumberFormat('0.0%');
  scenario.getRange('C5:C11').setNumberFormat('#,##0.00;(#,##0.00);-');
  const build = workbook.worksheets.getItem('Interest build');
  layout(build, 'Reported coverage and tracked debt reconciliation',
    ['Measure', `Prior: ${c.periods[0].period_end}`, `Current: ${c.periods[1].period_end}`], 'C', 15);
  build.getRange('A5:A15').values = [
    'Operating income', 'Reported interest expense magnitude', 'Operating cash flow',
    'Sum of tracked gross principal components',
    'Separately disclosed principal or carrying plus costs',
    'Tracked gross principal residual', 'Operating income / interest expense',
    'Operating cash flow / interest expense', 'Current less prior operating income',
    'Current less prior operating coverage', 'Current less prior tracked gross principal',
  ].map(x => [x]);
  build.getRange('B5:C15').setNumberFormat('#,##0.00;(#,##0.00);-');
  sourceSheets(workbook, c, INTEREST_METRICS);
  const checks = workbook.worksheets.getItem('Checks');
  layout(checks, 'Tracked principal and coverage differences', ['Independent check', 'Expected zero'], 'B', 7);
  checks.getRange('A5:A7').values = [
    'Component principal less independent filing control',
    'Modeled interest less reported interest and rate addition',
    'Modeled coverage times modeled interest less modeled income',
  ].map(x => [x]);
  checks.getRange('B5:B7').setNumberFormat('0.00;0.00;0.00');
  checks.getRange('B5:B7').conditionalFormats.addCustom('=ABS(B5)>0.005', {
    fill: '#FCE8E6', font: { bold: true, color: '#A51616' },
  });
  return interestFormulaMap(c);
}
function fillFormulas(workbook, map, variant) {
  for (const [key, pair] of map) {
    const idx = key.lastIndexOf('!');
    const sheet = workbook.worksheets.getItem(key.slice(0, idx));
    formula(sheet, key.slice(idx + 1), variant === 'seed' && pair.bad ? pair.bad : pair.good);
  }
}
async function buildCase(c, variant, outputRoot) {
  if (!PROFILES.has(c.profile) || c.periods?.length !== 2 || !Number.isInteger(c.case_index)) {
    throw new Error('unsupported_private_train_case');
  }
  const workbook = Workbook.create();
  const spec = c.profile === 'cash_train_profile'
    ? configureCash(workbook, c) : configureInterest(workbook, c);
  if (spec.targets.length !== 12 || new Set(spec.targets).size !== 12) {
    throw new Error('twelve_distinct_target_formula_repairs_required');
  }
  fillFormulas(workbook, spec.formulas, variant);
  workbook.recalculate();
  const err = await workbook.inspect({kind: 'match',
    searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',
    options: {useRegex: true, maxResults: 100}, maxChars: 1200});
  const sheetNames = c.profile === 'cash_train_profile'
    ? ['Cash summary', 'Cash scenario', 'Flow build', 'Source facts', 'Source lineage', 'Checks']
    : ['Interest summary', 'Rate scenario', 'Interest build', 'Source facts', 'Source lineage', 'Checks'];
  const caseDir = path.join(outputRoot, `case-${String(c.case_index).padStart(2, '0')}`);
  await fs.mkdir(caseDir, {recursive: true, mode: 0o700});
  await fs.chmod(caseDir, 0o700);
  const exported = await SpreadsheetFile.exportXlsx(workbook);
  const xlsxPath = path.join(caseDir, `${variant}.xlsx`);
  await exported.save(xlsxPath);
  await fs.chmod(xlsxPath, 0o600);
  if (variant === 'positive') {
    for (const name of sheetNames) {
      const png = await workbook.render({sheetName: name, autoCrop: 'all', scale: 1.5, format: 'png'});
      const previewPath = path.join(caseDir, `preview-${name.toLowerCase().replaceAll(' ', '-')}.png`);
      await fs.writeFile(previewPath, new Uint8Array(await png.arrayBuffer()), {mode: 0o600});
      await fs.chmod(previewPath, 0o600);
    }
  }
  return {case_index: c.case_index, variant, target_count: spec.targets.length,
          sheet_count: sheetNames.length, formula_error_scan: err.ndjson || ''};
}

const files = (await fs.readdir(casesDirectory)).filter(x => /^case-\d\d\.private\.json$/.test(x)).sort();
if (files.length !== 4) throw new Error('exactly_four_private_train_case_packages_required');
const results = [];
for (const file of files) {
  const c = JSON.parse(await fs.readFile(path.join(casesDirectory, file), 'utf8'));
  results.push(await buildCase(c, 'seed', outputDirectory));
  results.push(await buildCase(c, 'positive', outputDirectory));
}
console.log(JSON.stringify({status: 'four_train_only_workbooks_authored',
  workbook_count: results.length, case_count: files.length,
  target_formula_count_each: 12,
  artifact_tool_formula_error_scans: results.map(x => x.formula_error_scan.length)}, null, 2));
