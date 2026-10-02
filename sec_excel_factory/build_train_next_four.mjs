import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { FileBlob, SpreadsheetFile, Workbook } from '@oai/artifact-tool';

// TRAIN-only authoring. Source identities and values are in evaluator-private
// reviewed packages. This file never reads held-out workbooks or answers.
const [, , reviewPath, outputDirectory] = process.argv;
if (!reviewPath || !outputDirectory) {
  throw new Error('usage: node build_train_next_four.mjs REVIEW_PRIVATE_JSON OUTPUT_DIR');
}
const review = JSON.parse(await fs.readFile(reviewPath, 'utf8'));
if (review.schema !== 'envloop.sec_excel_train_next_four_review.private.v1' ||
    review.cases?.length !== 4 ||
    review.cases.some(c => c.review_status !==
      'source_field_review_pass; independent_audit_pending' ||
      c.excel_web_admitted !== false || c.official_final_admitted !== false)) {
  throw new Error('reviewed_train_source_scope_changed');
}

const COLORS = { navy: '#173A5E', mid: '#28718A', blue: '#185AA6',
  green: '#137A62', amber: '#FFF0BE', slate: '#415466', pale: '#E8F3F5' };
const PENSION = [
  ['opening_assets', 'Opening plan assets'],
  ['actual_return', 'Actual return on plan assets'],
  ['employer_contributions', 'Employer contributions'],
  ['participant_contributions', 'Participant contributions'],
  ['benefits_paid', 'Benefits paid, signed'],
  ['settlements', 'Plan settlements, signed'],
  ['closing_assets', 'Filed closing plan assets'],
  ['obligation', 'Projected benefit obligation'],
  ['reported_funded', 'Filed funded status'],
  ['other_disclosed', 'Other disclosed plan-asset activity'],
];
const BANK = [
  ['interest_income', 'Filed interest income'],
  ['interest_expense', 'Filed interest expense'],
  ['reported_net_interest', 'Filed net interest income'],
  ['interest_bearing_deposits', 'Interest-bearing deposits, closing'],
  ['total_deposits', 'Total deposits, closing'],
  ['average_interest_bearing_deposits', 'Interest-bearing deposits, annual average'],
];
const SHEETS = {
  pension: ['Benefit summary', 'Asset scenario', 'Asset bridge',
    'Source facts', 'Source lineage', 'Checks'],
  bank: ['Interest summary', 'Rate scenario', 'Interest build',
    'Source facts', 'Source lineage', 'Checks'],
};
function previewRange(name) {
  if (name === 'Source lineage') return 'A1:F25';
  if (name === 'Source facts') return 'A1:D16';
  if (name.endsWith('scenario')) return 'A1:D13';
  if (name.endsWith('summary') || name === 'Checks') return 'A1:B11';
  return 'A1:C20';
}
const format = '#,##0.0;(#,##0.0);-';
const put = (sheet, address, value) => { sheet.getRange(address).values = [[value]]; };
const formula = (sheet, address, value) => {
  sheet.getRange(address).formulas = [[value]];
};
function layout(sheet, title, headers, last, bottom) {
  sheet.showGridLines = false;
  put(sheet, 'A1', title);
  sheet.getRange('A1').format.font =
    { name: 'Arial', size: 15, bold: true, color: COLORS.navy };
  sheet.getRange(`A4:${last}4`).values = [headers];
  sheet.getRange(`A4:${last}4`).format = {
    fill: COLORS.navy,
    font: { name: 'Arial', size: 10, bold: true, color: '#FFFFFF' },
    rowHeight: 28, verticalAlignment: 'center',
  };
  sheet.getRange(`A5:${last}${bottom}`).format.font =
    { name: 'Arial', size: 10, color: '#1D2933' };
  sheet.getRange('A:A').format.columnWidth = 48;
  sheet.getRange('B:C').format.columnWidth = 22;
  sheet.getRange(`B5:C${bottom}`).setNumberFormat(format);
  sheet.freezePanes.freezeRows(4);
}
function source(c, wb) {
  const entries = c.profile === 'pension' ? PENSION : BANK;
  const s = wb.worksheets.getItem('Source facts');
  layout(s, `Original SEC 10-K facts (USD millions)`,
    ['Filed measure', `Prior: ${c.periods[0].period_end}`,
      `Current: ${c.periods[1].period_end}`, 'Scope and absence'],
    'D', 4 + entries.length);
  s.getRange('D:D').format.columnWidth = 66;
  put(s, 'A2', `Original filing: ${c.source.original_sec_url}`);
  s.getRange('A2').format.font =
    { name: 'Arial', size: 9, color: COLORS.slate };
  for (let i = 0; i < entries.length; i++) {
    const [key, label] = entries[i];
    const row = i + 5;
    put(s, `A${row}`, label);
    for (let p = 0; p < 2; p++) {
      const item = c.periods[p].fields[key];
      if (!item) throw new Error(`reviewed_source_fact_missing:${key}`);
      put(s, `${p ? 'C' : 'B'}${row}`,
        item.value === null ? 'n.r.' : item.value);
    }
    const absent = c.periods.some(p =>
      p.fields[key].presence === 'not_separately_reported');
    put(s, `D${row}`, key === 'other_disclosed' ?
      'Disclosed items omitted from the partial bridge; used only as a residual control' :
      key === 'average_interest_bearing_deposits' ?
      'Annual average from filed table; closing deposits are a separate balance' :
      absent ? 'n.r. means not separately reported, never a filed zero' : '');
  }
  s.getRange(`B5:C${4 + entries.length}`).format.font =
    { name: 'Arial', size: 10, color: COLORS.blue };
  const l = wb.worksheets.getItem('Source lineage');
  layout(l, 'Filed fact locators and source scope',
    ['Measure', 'Period end', 'Presence', 'XBRL concept',
      'Context / source row', 'Original filing'],
    'F', 4 + entries.length * 2);
  l.getRange('A:A').format.columnWidth = 48;
  l.getRange('B:C').format.columnWidth = 22;
  l.getRange('D:E').format.columnWidth = 52;
  l.getRange('F:F').format.columnWidth = 78;
  l.getRange(`D5:F${4 + entries.length * 2}`).format.wrapText = true;
  l.getRange(`A5:F${4 + entries.length * 2}`).format.rowHeight = 28;
  let row = 5;
  for (const period of c.periods) {
    for (const [key, label] of entries) {
      const item = period.fields[key];
      l.getRange(`A${row}:F${row}`).values = [[
        label, period.period_end, item.presence,
        item.ixbrl_tag || '',
        item.context_ref || (item.row_sha256 || ''),
        c.source.original_sec_url,
      ]];
      row++;
    }
  }
}
function pensionFormulas(c) {
  const m = new Map();
  const add = (sheet, cell, good, bad = null) => m.set(`${sheet}!${cell}`, { good, bad });
  const src = (col, row) => `='Source facts'!${col}${row}`;
  for (const col of ['B', 'C']) {
    for (const [row, srcrow, key] of [
      [5, 5, 'opening_assets'], [6, 6, 'actual_return'],
      [7, 7, 'employer_contributions'], [8, 8, 'participant_contributions'],
      [9, 9, 'benefits_paid'], [10, 10, 'settlements'],
      [12, 11, 'closing_assets'], [14, 12, 'obligation'],
      [16, 13, 'reported_funded']]) {
      const p = col === 'B' ? 0 : 1;
      add('Asset bridge', `${col}${row}`,
        c.periods[p].fields[key].value === null ? '=0' : src(col, srcrow));
    }
    add('Asset bridge', `${col}11`,
      `=${col}5+${col}6+${col}7+${col}8+${col}9+${col}10`);
    add('Asset bridge', `${col}13`, `=${col}12-${col}11`);
    add('Asset bridge', `${col}15`, `=${col}12-${col}14`);
    add('Asset bridge', `${col}17`, `=${col}15-${col}16`);
    add('Asset bridge', `${col}18`, `=${col}14-${col}12`);
  }
  for (const [row, good] of [
    [5, "='Asset bridge'!C12"], [6, "='Asset bridge'!C5*B6"],
    [7, '=B5'], [8, '=C5+C6+C7'],
    [9, "='Asset bridge'!C14"], [10, '=C9*(1+B7)'],
    [11, '=C8-C10']]) add('Asset scenario', `C${row}`, good);
  for (const [row, good] of [
    [5, "='Asset bridge'!C15"], [6, "='Asset bridge'!B15"],
    [7, "='Asset bridge'!C13"], [8, "='Asset bridge'!C18"],
    [9, "='Asset scenario'!C11"]]) add('Benefit summary', `B${row}`, good);
  add('Checks', 'B5', "='Asset bridge'!C17");
  add('Checks', 'B6', "='Asset bridge'!C13-'Source facts'!C14");
  add('Checks', 'B7',
    "='Asset scenario'!C11-('Asset scenario'!C8-'Asset scenario'!C10)");
  const bad = {
    'Asset bridge!B5': src('C', 5),
    'Asset bridge!C5': src('B', 5),
    'Asset bridge!C6': src('B', 6),
    'Asset bridge!C9': `=-'Source facts'!C9`,
    'Asset bridge!C11': '=C5+C7+C8+C9+C10',
    'Asset bridge!C13': '=C12-C11+C6',
    'Asset bridge!C15': '=C14-C12',
    'Asset bridge!C17': '=C15+C16',
    'Asset bridge!C18': '=C12-C14',
    'Asset scenario!C6': "='Asset bridge'!B5*B6",
    'Asset scenario!C11': '=C8+C10',
    'Benefit summary!B9': "='Asset scenario'!C8",
  };
  for (const [key, value] of Object.entries(bad)) m.get(key).bad = value;
  return m;
}
function bankFormulas() {
  const m = new Map();
  const add = (sheet, cell, good, bad = null) => m.set(`${sheet}!${cell}`, { good, bad });
  const src = (col, row) => `='Source facts'!${col}${row}`;
  for (const col of ['B', 'C']) {
    for (const [row, factrow] of [[5, 5], [6, 6], [8, 7], [10, 10]]) {
      add('Interest build', `${col}${row}`, src(col, factrow));
    }
    add('Interest build', `${col}7`, `=${col}5-${col}6`);
    add('Interest build', `${col}9`, `=${col}7-${col}8`);
    add('Interest build', `${col}11`, `${src(col, 8)}/${src(col, 9).slice(1)}`);
    add('Interest build', `${col}14`, `=${col}6/${col}5`);
  }
  add('Interest build', 'C12', `${src('C', 9)}-${src('B', 9).slice(1)}`);
  add('Interest build', 'C13', '=C8-B8');
  for (const [row, good] of [
    [5, "='Interest build'!C8"],
    [6, "='Interest build'!C10*B5/10000"],
    [7, '=C5-C6'], [8, '=C7-C5']]) add('Rate scenario', `C${row}`, good);
  for (const [row, good] of [
    [5, "='Interest build'!C8"], [6, "='Interest build'!B8"],
    [7, "='Interest build'!C11"], [8, "='Rate scenario'!C7"],
    [9, "='Interest build'!C9"]]) add('Interest summary', `B${row}`, good);
  add('Checks', 'B5', "='Interest build'!C9");
  add('Checks', 'B6',
    "='Rate scenario'!C7-('Rate scenario'!C5-'Rate scenario'!C6)");
  const bad = {
    'Interest build!B5': src('C', 5),
    'Interest build!C5': src('B', 5),
    'Interest build!C6': src('B', 6),
    'Interest build!C7': '=C5+C6',
    'Interest build!C9': '=C7+C8',
    'Interest build!C10': src('B', 10),
    'Interest build!C11': `${src('C', 9)}/${src('C', 8).slice(1)}`,
    'Interest build!C12': `${src('B', 9)}-${src('C', 9).slice(1)}`,
    'Interest build!C13': '=C8+B8',
    'Rate scenario!C6': `${src('C', 8)}*B5/10000`,
    'Rate scenario!C7': '=C5+C6',
    'Interest summary!B8': "='Rate scenario'!C5",
  };
  for (const [key, value] of Object.entries(bad)) m.get(key).bad = value;
  return m;
}
function workingSheets(c, w) {
  const prior = c.periods[0].period_end;
  const current = c.periods[1].period_end;
  if (c.profile === 'pension') {
    const summary = w.worksheets.getItem('Benefit summary');
    layout(summary, `${c.source.plan_scope} benefit position (USD millions)`,
      ['Measure', 'Result'], 'B', 9);
    summary.getRange('A5:A9').values = [
      ['Current funded status'], ['Prior funded status'],
      ['Current partial asset-bridge residual'],
      ['Current gap to full funding'], ['Modeled funded status']];
    const scenario = w.worksheets.getItem('Asset scenario');
    layout(scenario, 'Pension asset and obligation scenario (USD millions)',
      ['Editable driver', 'Input', 'Result', 'Result description'], 'D', 11);
    scenario.getRange('D:D').format.columnWidth = 45;
    scenario.getRange('A5:A11').values = [
      ['Additional sponsor contribution'], ['Change in asset return'],
      ['Change in obligation'], [''], [''], [''], ['']];
    scenario.getRange('D5:D11').values = [
      ['Filed closing plan assets'], ['Change in assets from return'],
      ['Added sponsor assets'], ['Modeled closing assets'],
      ['Filed projected benefit obligation'], ['Modeled obligation'],
      ['Modeled funded status']];
    put(scenario, 'B5', c.scenario.sponsor_contribution);
    put(scenario, 'B6', c.scenario.return_change);
    put(scenario, 'B7', c.scenario.obligation_change);
    scenario.getRange('B5:B7').format.fill = COLORS.amber;
    scenario.getRange('B6:B7').setNumberFormat('0.0%');
    const bridge = w.worksheets.getItem('Asset bridge');
    layout(bridge, 'Plan asset and funded-status bridge (USD millions)',
      ['Measure', `Prior: ${prior}`, `Current: ${current}`], 'C', 18);
    bridge.getRange('A5:A18').values = [
      ['Opening plan assets'], ['Actual return'], ['Employer contributions'],
      ['Participant contributions'], ['Benefits paid, signed'],
      ['Settlements, signed'], ['Partial reconstructed assets'],
      ['Filed closing assets'], ['Residual from other disclosed items'],
      ['Projected benefit obligation'], ['Calculated funded status'],
      ['Filed funded status'], ['Funded-status difference'],
      ['Gap to full funding']];
    const checks = w.worksheets.getItem('Checks');
    layout(checks, 'Independent reconciliation differences (USD millions)',
      ['Check', 'Difference'], 'B', 7);
    checks.getRange('A5:A7').values = [
      ['Calculated minus filed funded status'],
      ['Partial-bridge residual minus disclosed other activity'],
      ['Scenario funded-status arithmetic']];
    checks.getRange('B5:B7').setNumberFormat('0.00;(0.00);0.00');
  } else {
    const summary = w.worksheets.getItem('Interest summary');
    layout(summary, 'Bank net interest and funding (USD millions)',
      ['Measure', 'Result'], 'B', 9);
    summary.getRange('A5:A9').values = [
      ['Current net interest income'], ['Prior net interest income'],
      ['Closing interest-bearing deposit share'],
      ['Modeled net interest after deposit-rate change'],
      ['Rebuilt net-interest difference']];
    summary.getRange('B7').setNumberFormat('0.0%');
    const scenario = w.worksheets.getItem('Rate scenario');
    layout(scenario, 'Deposit funding-rate scenario (USD millions)',
      ['Editable driver', 'Input', 'Result', 'Result description'], 'D', 8);
    scenario.getRange('D:D').format.columnWidth = 49;
    scenario.getRange('A5:A8').values = [
      ['Increase in deposit funding rate (basis points)'],
      [''], [''], ['']];
    scenario.getRange('D5:D8').values = [
      ['Filed net interest income'], ['Additional annual interest expense'],
      ['Modeled net interest income'],
      ['Modeled less filed net interest income']];
    put(scenario, 'B5', c.scenario.deposit_rate_change_bps);
    scenario.getRange('B5').format.fill = COLORS.amber;
    const build = w.worksheets.getItem('Interest build');
    layout(build, 'Net-interest and deposit funding analysis',
      ['Measure', `Prior: ${prior}`, `Current: ${current}`], 'C', 14);
    build.getRange('A5:A14').values = [
      ['Filed interest income'], ['Filed interest expense'],
      ['Rebuilt net interest income'], ['Filed net interest income'],
      ['Rebuilt less filed difference'],
      ['Average interest-bearing deposits'],
      ['Closing interest-bearing / total deposits'],
      ['Change in closing total deposits'],
      ['Change in filed net interest income'],
      ['Interest expense / interest income']];
    build.getRange('B11:C11').setNumberFormat('0.0%');
    build.getRange('B14:C14').setNumberFormat('0.0%');
    const checks = w.worksheets.getItem('Checks');
    layout(checks, 'Independent reconciliation differences (USD millions)',
      ['Check', 'Difference'], 'B', 6);
    checks.getRange('A5:A6').values = [
      ['Rebuilt less filed net interest'],
      ['Scenario expense and net-interest identity']];
    checks.getRange('B5:B6').setNumberFormat('0.00;(0.00);0.00');
  }
}
function applyFormulas(w, map, kind) {
  for (const [key, value] of map) {
    const [sheet, address] = key.split('!');
    formula(w.worksheets.getItem(sheet), address,
      kind === 'seed' && value.bad ? value.bad : value.good);
  }
}
function targets(map) {
  return [...map].filter(([, v]) => v.bad !== null).map(([k]) => k).sort();
}
async function make(c, kind, caseDir) {
  const w = Workbook.create();
  for (const name of SHEETS[c.profile]) w.worksheets.add(name);
  source(c, w);
  workingSheets(c, w);
  const map = c.profile === 'pension' ? pensionFormulas(c) : bankFormulas();
  if (targets(map).length !== 12) throw new Error('target_repair_depth_not_twelve');
  applyFormulas(w, map, kind);
  w.recalculate();
  const errors = await w.inspect({kind: 'match',
    searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',
    options: {useRegex: true, maxResults: 30}, maxChars: 1600});
  if (errors.ndjson.includes('"match"')) throw new Error('formula_error_after_recalculation');
  const out = await SpreadsheetFile.exportXlsx(w);
  const destination = path.join(caseDir, `${kind}.xlsx`);
  await out.save(destination);
  if (kind === 'positive') {
    for (const name of SHEETS[c.profile]) {
      const image = await w.render({sheetName: name,
        range: previewRange(name), scale: 1.3, format: 'png'});
      await fs.writeFile(path.join(caseDir,
        `preview-${name.toLowerCase().replaceAll(' ', '-')}.png`),
        new Uint8Array(await image.arrayBuffer()));
    }
  }
  const saved = await fs.readFile(destination);
  return {sha256: createHash('sha256').update(saved).digest('hex'),
    bytes: saved.length, target_cells: targets(map)};
}

if (process.argv.includes('--render-only')) {
  for (const c of review.cases) {
    const dir = path.join(outputDirectory,
      `case-${String(c.case_index).padStart(2, '0')}`);
    const w = await SpreadsheetFile.importXlsx(
      await FileBlob.load(path.join(dir, 'positive.xlsx')));
    for (const name of SHEETS[c.profile]) {
      const preview = await w.render({sheetName: name,
        range: previewRange(name), scale: 1.3, format: 'png'});
      const file = path.join(dir,
        `preview-${name.toLowerCase().replaceAll(' ', '-')}.png`);
      await fs.writeFile(file,
        new Uint8Array(await preview.arrayBuffer()));
      await fs.chmod(file, 0o600);
    }
  }
  console.log(JSON.stringify({status: 'existing_reference_previews_refreshed',
    workbooks_edited: 0, previews: review.cases.length * 6}));
  process.exit(0);
}

await fs.mkdir(outputDirectory, {recursive: true, mode: 0o700});
await fs.chmod(outputDirectory, 0o700);
const manifest = {schema: 'envloop.sec_excel_train_next_four_workbooks.private.v1',
  source_review_sha256: createHash('sha256').update(await fs.readFile(reviewPath)).digest('hex'),
  status: 'TRAIN-only offline workbook pairs; independent OOXML audit pending',
  cases: []};
for (const c of review.cases) {
  const caseDir = path.join(outputDirectory, `case-${String(c.case_index).padStart(2, '0')}`);
  await fs.mkdir(caseDir, {recursive: true, mode: 0o700});
  await fs.chmod(caseDir, 0o700);
  const seed = await make(c, 'seed', caseDir);
  const positive = await make(c, 'positive', caseDir);
  manifest.cases.push({case_index: c.case_index, profile: c.profile,
    seed, positive});
}
const manifestFile = path.join(outputDirectory, 'workbooks-manifest.private.json');
await fs.writeFile(manifestFile, JSON.stringify(manifest, null, 2) + '\n',
  {mode: 0o600, flag: 'wx'});
async function secureTree(directory) {
  await fs.chmod(directory, 0o700);
  for (const item of await fs.readdir(directory, {withFileTypes: true})) {
    const next = path.join(directory, item.name);
    if (item.isSymbolicLink()) throw new Error('private_workbook_symlink_forbidden');
    if (item.isDirectory()) await secureTree(next);
    else await fs.chmod(next, 0o600);
  }
}
await secureTree(outputDirectory);
console.log(JSON.stringify({status: 'four_workbook_pairs_created',
  cases: manifest.cases.length,
  repairs_per_case: manifest.cases.map(c => c.seed.target_cells.length),
  manifest_sha256: createHash('sha256').update(await fs.readFile(manifestFile)).digest('hex')}));
