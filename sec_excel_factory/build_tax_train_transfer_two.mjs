import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool';

// TRAIN-only authoring. All source facts arrive in independently reviewed
// private packages. This module contains no issuer, accession, final task or gold.
const [, , casesDirectory, outputDirectory] = process.argv;
if (!casesDirectory || !outputDirectory) {
  throw new Error('usage: node build_tax_train_transfer_two.mjs CASES_DIR OUTPUT_DIR');
}
const SHEETS = ['Tax summary', 'Tax scenario', 'Gross bridge', 'Interest scope',
  'Source facts', 'Source lineage', 'Checks'];
const METRICS = [
  ['opening', 'Opening gross uncertain tax positions'],
  ['current_year_additions', 'Current-year position additions'],
  ['prior_year_additions', 'Prior-year position additions'],
  ['prior_year_reductions', 'Prior-year position reductions, signed'],
  ['settlements', 'Settlements, signed'],
  ['lapse', 'Statute lapse, signed'],
  ['translation', 'Currency translation, signed'],
  ['other', 'Other disclosed signed activity'],
  ['closing', 'Filed closing gross uncertain tax positions'],
  ['accrued_interest_penalties', 'Separately accrued interest and penalties'],
  ['interest_flow', 'Filed interest-related expense/(benefit)'],
];
const SOURCE_ROW = Object.fromEntries(METRICS.map(([key], i) => [key, i + 5]));
const COLORS = { navy: '#173A5E', teal: '#167A83', pale: '#E8F3F5',
  amber: '#FFF0BE', blue: '#185AA6', green: '#137A62', gray: '#65717B' };
function put(sheet, addr, value) { sheet.getRange(addr).values = [[value]]; }
function formula(sheet, addr, value) { sheet.getRange(addr).formulas = [[value]]; }
function layout(sheet, title, headings, lastColumn, lastBodyRow) {
  sheet.showGridLines = false;
  put(sheet, 'A1', title);
  sheet.getRange('A1').format.font = {name: 'Arial', size: 15, bold: true, color: COLORS.navy};
  sheet.getRange(`A4:${lastColumn}4`).values = [headings];
  sheet.getRange(`A4:${lastColumn}4`).format = {fill: COLORS.navy,
    font: {name: 'Arial', size: 10, bold: true, color: '#FFFFFF'}, rowHeight: 28,
    verticalAlignment: 'center'};
  sheet.getRange('A:A').format.columnWidth = 54;
  sheet.getRange('B:C').format.columnWidth = 23;
  sheet.getRange(`A5:${lastColumn}${lastBodyRow}`).format.font =
    {name: 'Arial', size: 10, color: '#1D2933'};
  sheet.freezePanes.freezeRows(4);
}
function entry(c, period, key) { return c.periods[period].fields[key]; }
function labelFor(c, key, fallback) {
  return key === 'interest_flow' ? c.source.interest_flow_label : fallback;
}
function validateCase(c) {
  if (c.schema !== 'envloop.sec_tax_train_analogue_case.private.v1' ||
      c.scope !== 'TRAIN-only offline analogue; no final workbook or GUI admission' ||
      !Number.isInteger(c.case_index) || c.periods?.length !== 2 ||
      c.skill?.signature_sha256 !==
        'ff413ae00b002631deefbccab6a6392405c63e6f31a968efbb5ef67aaa5506e8') {
    throw new Error('unsupported_private_tax_train_case');
  }
  for (const p of c.periods) {
    for (const [key] of METRICS) {
      const x = p.fields[key];
      if (!x || !['reported', 'disclosed_dash', 'not_separately_reported'].includes(x.presence)) {
        throw new Error(`unreviewed_fact_presence:${key}`);
      }
      if (x.presence === 'not_separately_reported' ? x.value !== null :
          typeof x.value !== 'number' || !Number.isFinite(x.value)) {
        throw new Error(`invalid_reviewed_fact:${key}`);
      }
    }
  }
}
function makeSourceSheets(w, c) {
  const s = w.worksheets.getItem('Source facts');
  layout(s, 'Original SEC filing tax note facts (USD millions)',
    ['Filed category', `Prior: ${c.periods[0].period_end}`,
      `Current: ${c.periods[1].period_end}`, 'Source scope'], 'D', 15);
  s.getRange('D:D').format.columnWidth = 56;
  put(s, 'A2', `Original filing: ${c.source.original_sec_url}`);
  s.getRange('A2').format.font = {name: 'Arial', size: 9, color: COLORS.gray};
  for (let i = 0; i < METRICS.length; i++) {
    const [key, fallback] = METRICS[i];
    const label = labelFor(c, key, fallback);
    const row = i + 5;
    put(s, `A${row}`, label);
    for (let period = 0; period < 2; period++) {
      const x = entry(c, period, key);
      const col = period ? 'C' : 'B';
      put(s, `${col}${row}`, x.presence === 'not_separately_reported' ? 'n.r.' : x.value);
    }
    const absent = c.periods.some(p => p.fields[key].presence === 'not_separately_reported');
    put(s, `D${row}`, key === 'accrued_interest_penalties' ?
      'Separate liability; excluded from the gross position rollforward' :
      key === 'interest_flow' ?
      'Signed annual flow; scope follows the original source, outside the gross bridge' :
      absent ? 'n.r. is not separately reported; zero is a bridge convention' : '');
  }
  s.getRange('B5:C15').setNumberFormat('#,##0.0;(#,##0.0);-');
  s.getRange('B5:C15').format.font = {name: 'Arial', size: 10, color: COLORS.blue};
  const lineage = w.worksheets.getItem('Source lineage');
  layout(lineage, 'Filed fact and absence locators',
    ['Category', 'Period end', 'Presence', 'Original document', 'XBRL tag',
      'Context / row locator', 'Original SEC filing', 'Accession'], 'H', 26);
  lineage.getRange('A:A').format.columnWidth = 48;
  lineage.getRange('B:C').format.columnWidth = 22;
  lineage.getRange('D:F').format.columnWidth = 40;
  lineage.getRange('G:G').format.columnWidth = 72;
  lineage.getRange('H:H').format.columnWidth = 28;
  let row = 5;
  for (let period = 0; period < 2; period++) {
    for (const [key, fallback] of METRICS) {
      const label = labelFor(c, key, fallback);
      const x = entry(c, period, key);
      lineage.getRange(`A${row}:H${row}`).values = [[label, c.periods[period].period_end,
        x.presence, x.document || '', x.ixbrl_tag || '',
        x.ixbrl_context_ref || x.row_locator || '',
        c.source.original_sec_url, c.source.accession]];
      row++;
    }
  }
  lineage.getRange(`A5:H${row - 1}`).format.rowHeight = 27;
  lineage.getRange(`D5:H${row - 1}`).format.wrapText = true;
}
function formulaMap(c) {
  const map = new Map();
  const add = (sheet, addr, good, bad = null) => map.set(`${sheet}!${addr}`, {good, bad});
  const src = (col, row) => `='Source facts'!${col}${row}`;
  const bridge = (col, row) => `='Gross bridge'!${col}${row}`;
  for (const [period, col] of [[0, 'B'], [1, 'C']]) {
    add('Gross bridge', `${col}5`, src(col, 5), period === 0 ? src('C', 5) : src('B', 5));
    for (const [key, row] of Object.entries(SOURCE_ROW)) {
      if (row < 6 || row > 12) continue;
      const x = entry(c, period, key);
      add('Gross bridge', `${col}${row}`,
        x.presence === 'not_separately_reported' ? '=0' : src(col, row));
    }
    add('Gross bridge', `${col}13`, `=${col}6+${col}7+${col}8+${col}9+${col}10+${col}11+${col}12`);
    add('Gross bridge', `${col}14`, `=${col}5+${col}13`);
    add('Gross bridge', `${col}15`, src(col, 13));
    add('Gross bridge', `${col}16`, `=${col}14-${col}15`);
    add('Interest scope', `${col}5`, src(col, 14));
    add('Interest scope', `${col}6`, src(col, 15));
    add('Interest scope', `${col}7`, bridge(col, 15));
    add('Interest scope', `${col}8`, `=${col}5+${col}7`);
    add('Interest scope', `${col}9`, `=${col}5/${col}7`);
  }
  add('Tax scenario', 'C5', "='Gross bridge'!C15+B5");
  add('Tax scenario', 'C6', '=C5+B6');
  add('Tax scenario', 'C7', "='Interest scope'!C5*(1+B7)");
  add('Tax scenario', 'C8', '=C6+C7');
  for (const [row, good] of [[5,"='Gross bridge'!C15"],
    [6,"='Interest scope'!C5"],[7,"='Interest scope'!C8"],
    [8,"='Tax scenario'!C8"],[9,"='Gross bridge'!C16"]]) {
    add('Tax summary', `B${row}`, good);
  }
  add('Checks', 'B5', "='Gross bridge'!B16");
  add('Checks', 'B6', "='Gross bridge'!C16");
  add('Checks', 'B7', "='Interest scope'!C8-'Interest scope'!C7-'Interest scope'!C5");
  add('Checks', 'B8', "='Tax scenario'!C8-'Tax scenario'!C6-'Tax scenario'!C7");
  const wrong = new Map([
    ['Gross bridge!B5', src('C', 5)],
    ['Gross bridge!C5', src('B', 5)],
    ['Gross bridge!C6', src('C', 7)],
    ['Gross bridge!C8', `=-'Source facts'!C8`],
    ['Gross bridge!C9', src('B', 9)],
    ['Gross bridge!C13', '=C6+C7+C8+C10+C11+C12'],
    ['Gross bridge!C14', '=C5-C13'],
    ['Gross bridge!C16', '=C15-C14'],
    ['Interest scope!C5', src('B', 14)],
    ['Tax scenario!C5', "='Gross bridge'!C15-B5"],
    ['Tax scenario!C6', '=C5-B6'],
    ['Tax summary!B8', "='Interest scope'!C8"],
  ]);
  if (wrong.size !== 12) throw new Error('exact_twelve_repairs_required');
  for (const [key, bad] of wrong) {
    if (!map.has(key) || map.get(key).good === bad) throw new Error('invalid_unmarked_fault');
    map.get(key).bad = bad;
  }
  return {map, targets: [...wrong.keys()]};
}
function configure(w, c) {
  for (const name of SHEETS) w.worksheets.add(name);
  const summary = w.worksheets.getItem('Tax summary');
  layout(summary, 'Gross tax positions and separate interest',
    ['Measure', 'USD millions'], 'B', 9);
  put(summary, 'A2', 'Filed balances are separated from the authored scenario.');
  summary.getRange('A5:A9').values = [
    'Filed gross uncertain tax positions', 'Separately accrued interest and penalties',
    'Gross positions plus separate accrual', 'Scenario combined balance',
    'Gross position rollforward difference',
  ].map(x => [x]);
  summary.getRange('B5:B9').setNumberFormat('#,##0.0;(#,##0.0);-');
  const scenario = w.worksheets.getItem('Tax scenario');
  layout(scenario, 'Authored position and interest scenario',
    ['Authored driver', 'Editable amount / ratio', 'Modeled result', 'Result definition'], 'D', 8);
  scenario.getRange('D:D').format.columnWidth = 50;
  put(scenario, 'A2', 'Synthetic sensitivities are not filed amounts or estimates of audit outcomes.');
  scenario.getRange('A5:A7').values = [
    'Additional current positions', 'Additional settlements, signed',
    'Accrued interest and penalties change',
  ].map(x => [x]);
  scenario.getRange('D5:D8').values = [
    'Gross positions after new positions', 'Gross positions after settlements',
    'Modeled separate interest and penalties accrual', 'Modeled combined balance',
  ].map(x => [x]);
  scenario.getRange('B5:B7').values = [[c.scenario.additions],
    [c.scenario.settlements], [c.scenario.accrual_change]];
  scenario.getRange('B5:B7').format = {fill: COLORS.amber,
    font: {name: 'Arial', size: 10, color: COLORS.blue}};
  scenario.getRange('B5:B6').setNumberFormat('#,##0.0;(#,##0.0);-');
  scenario.getRange('B7').setNumberFormat('0.0%');
  scenario.getRange('C5:C8').setNumberFormat('#,##0.0;(#,##0.0);-');
  const bridge = w.worksheets.getItem('Gross bridge');
  layout(bridge, 'Signed gross uncertain tax position rollforward',
    ['Measure', `Prior: ${c.periods[0].period_end}`,
      `Current: ${c.periods[1].period_end}`, 'Source status'], 'D', 16);
  bridge.getRange('D:D').format.columnWidth = 48;
  bridge.getRange('A5:A16').values = [
    'Opening gross positions', 'Current-year additions', 'Prior-year additions',
    'Prior-year reductions, signed', 'Settlements, signed', 'Statute lapse, signed',
    'Currency translation, signed', 'Other disclosed signed activity',
    'Sum of signed activity', 'Rebuilt closing gross positions',
    'Filed closing gross positions', 'Rebuilt less filed closing',
  ].map(x => [x]);
  for (const [key, row] of Object.entries(SOURCE_ROW)) {
    if (row < 6 || row > 12) continue;
    const statuses = c.periods.map(p => p.fields[key].presence);
    if (statuses.includes('not_separately_reported')) {
      put(bridge, `D${row}`,
        'n.r. uses zero only as a bridge convention; not a filed zero');
    }
  }
  bridge.getRange('B5:C16').setNumberFormat('#,##0.0;(#,##0.0);-');
  const interest = w.worksheets.getItem('Interest scope');
  layout(interest, 'Accrued interest and penalties outside gross positions',
    ['Measure', `Prior: ${c.periods[0].period_end}`,
      `Current: ${c.periods[1].period_end}`], 'C', 9);
  put(interest, 'A2', 'Expense/(benefit) is a signed annual flow; accrual is a separate balance.');
  interest.getRange('A5:A9').values = [
    'Accrued interest and penalties', c.source.interest_flow_label,
    'Filed gross positions', 'Gross positions plus separate accrual',
    'Separate accrual / gross positions',
  ].map(x => [x]);
  interest.getRange('B5:C8').setNumberFormat('#,##0.0;(#,##0.0);-');
  interest.getRange('B9:C9').setNumberFormat('0.0%');
  makeSourceSheets(w, c);
  const checks = w.worksheets.getItem('Checks');
  layout(checks, 'Reconciliation differences', ['Independent check', 'Expected zero'], 'B', 8);
  checks.getRange('A5:A8').values = [
    'Prior signed bridge less filed closing', 'Current signed bridge less filed closing',
    'Separate accrual scope identity', 'Scenario combined balance identity',
  ].map(x => [x]);
  checks.getRange('B5:B8').setNumberFormat('0.00;0.00;0.00');
  checks.getRange('B5:B8').conditionalFormats.addCustom('=ABS(B5)>0.005',
    {fill: '#FCE8E6', font: {bold: true, color: '#A51616'}});
}
async function build(c, variant) {
  validateCase(c);
  const w = Workbook.create();
  configure(w, c);
  const spec = formulaMap(c);
  for (const [key, pair] of spec.map) {
    const index = key.lastIndexOf('!');
    formula(w.worksheets.getItem(key.slice(0, index)), key.slice(index + 1),
      variant === 'seed' && pair.bad ? pair.bad : pair.good);
  }
  w.recalculate();
  const errors = await w.inspect({kind: 'match',
    searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',
    options: {useRegex: true, maxResults: 100}, maxChars: 1500});
  const scan = JSON.parse((errors.ndjson || '').trim());
  if (scan.kind !== 'notice' || scan.message !== 'Cell search matched 0 entries.') {
    throw new Error('artifact_tool_formula_error_scan_not_clean');
  }
  const out = path.join(outputDirectory, `case-${String(c.case_index).padStart(2, '0')}`);
  await fs.mkdir(out, {recursive: true, mode: 0o700});
  await fs.chmod(out, 0o700);
  const blob = await SpreadsheetFile.exportXlsx(w);
  const dest = path.join(out, `${variant}.xlsx`);
  await blob.save(dest);
  await fs.chmod(dest, 0o600);
  // The spreadsheet runtime may emit a sibling inspection trace. It can
  // contain workbook content and must remain evaluator-private as well.
  const inspectionTrace = `${dest}.inspect.ndjson`;
  try {
    await fs.chmod(inspectionTrace, 0o600);
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
  if (variant === 'positive') {
    for (const name of SHEETS) {
      const png = await w.render({sheetName: name, autoCrop: 'all', scale: 1.5, format: 'png'});
      const preview = path.join(out, `preview-${name.toLowerCase().replaceAll(' ', '-')}.png`);
      await fs.writeFile(preview, new Uint8Array(await png.arrayBuffer()), {mode: 0o600});
      await fs.chmod(preview, 0o600);
    }
  }
  return {case_index: c.case_index, variant, sheet_count: SHEETS.length,
    target_count: spec.targets.length, formula_errors: 0};
}
const files = (await fs.readdir(casesDirectory)).filter(x => /^case-\d\d\.private\.json$/.test(x)).sort();
if (files.length !== 2) throw new Error('exactly_two_reviewed_tax_train_cases_required');
const root = path.dirname(casesDirectory);
const manifest = JSON.parse(await fs.readFile(path.join(root, 'cases-manifest.private.json'), 'utf8'));
if (manifest.schema !== 'envloop.sec_tax_train_case_manifest.private.v1' ||
    manifest.case_count !== 2 || manifest.official_excel_web_admitted !== 0) {
  throw new Error('private_train_case_manifest_missing');
}
const cases = [];
for (let i = 0; i < files.length; i++) {
  if (files[i] !== `case-${String(i).padStart(2, '0')}.private.json`) {
    throw new Error('private_case_order_changed');
  }
  const raw = await fs.readFile(path.join(casesDirectory, files[i]));
  if (createHash('sha256').update(raw).digest('hex') !== manifest.case_sha256[i]) {
    throw new Error('private_case_bytes_not_bound_to_manifest');
  }
  const c = JSON.parse(raw);
  if (c.source.semantic_review_sha256 !== manifest.semantic_review_sha256) {
    throw new Error('case_semantic_review_binding_changed');
  }
  cases.push(c);
}
await fs.mkdir(outputDirectory, {recursive: false, mode: 0o700});
await fs.chmod(outputDirectory, 0o700);
const results = [];
for (const c of cases) {
  results.push(await build(c, 'seed'));
  results.push(await build(c, 'positive'));
}
console.log(JSON.stringify({status: 'two_train_only_tax_workbooks_generated_pending_independent_saved_ooxml_audit',
  cases: 2, workbooks: results.length, target_count_each: 12,
  formula_errors: results.reduce((n, r) => n + r.formula_errors, 0)}, null, 2));
