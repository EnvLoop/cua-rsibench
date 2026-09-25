import fs from 'node:fs/promises';
import path from 'node:path';
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const [, , casesPath, outRoot] = process.argv;
if (!casesPath || !outRoot) throw new Error('usage: node build_goodwill_workbooks.mjs CASES_JSON OUT_ROOT');
const cases = JSON.parse(await fs.readFile(casesPath, 'utf8'));
const SHEETS = ['Asset Review', 'Filing Selection', 'Goodwill Movement', 'Intangible Carrying',
  'Earnings Burden', 'WriteDown Stress', 'Audit', 'Source 10-K', 'Filing Map'];
const RAW_HEADERS = ['Record ID', 'Concept', 'Unit', 'Start', 'End', 'Filed',
  'Accession', 'Reported USD', 'FY', 'FP', 'Frame'];
function formulas(c) {
  const out = new Map();
  const put = (sheet, addr, good, bad) => out.set(`${sheet}!${addr}`, { good, bad });
  const src = key => {
    const record = c.canonical[key];
    const i = c.records.findIndex(r => r.id === record.id);
    if (i < 0) throw new Error(`source row missing ${c.case_id}:${key}`);
    return `'Source 10-K'!H${i + 5}`;
  };
  for (const [year, col] of [['prior', 'B'], ['current', 'C']]) {
    for (const [metric, row] of [['goodwill', 5], ['intangibles', 6], ['assets', 7]]) {
      const otherYear = year === 'prior' ? 'current' : 'prior';
      put('Filing Selection', `${col}${row}`, `=${src(`${year}:${metric}`)}/1000000`,
        `=${src(`${otherYear}:${metric}`)}/1000000`);
    }
  }
  for (const [metric, row, wrong] of [['acquired_goodwill', 8, 'amortization'],
                                       ['amortization', 9, 'net_income'],
                                       ['net_income', 10, 'acquired_goodwill']]) {
    put('Filing Selection', `C${row}`, `=${src(metric)}/1000000`, `=${src(wrong)}/1000000`);
  }
  const f = a => `'Filing Selection'!${a}`;
  put('Goodwill Movement', 'B5', `=${f('B5')}`, `=${f('C5')}`);
  put('Goodwill Movement', 'B6', `=${f('C8')}`, `=${f('C9')}`);
  put('Goodwill Movement', 'B7', `=${f('C5')}`, `=${f('B5')}`);
  put('Goodwill Movement', 'B8', '=B7-B5', '=B7+B5');
  put('Goodwill Movement', 'B9', '=B8-B6', '=B8+B6');
  put('Goodwill Movement', 'B10', '=B9/B7', '=B9/B5');
  put('Goodwill Movement', 'B11', `=B7/${f('C7')}`, `=B7/${f('B7')}`);
  put('Intangible Carrying', 'B5', `=${f('B6')}`, `=${f('C6')}`);
  put('Intangible Carrying', 'B6', `=${f('C6')}`, `=${f('B6')}`);
  put('Intangible Carrying', 'B7', '=B6-B5', '=B5-B6');
  put('Intangible Carrying', 'B8', `=${f('C9')}`, `=${f('C8')}`);
  put('Intangible Carrying', 'B9', '=B7+B8', '=B7-B8');
  put('Intangible Carrying', 'B10', `=(${f('C5')}+B6)/${f('C7')}`, `=(${f('C5')}+B6)/${f('B7')}`);
  put('Intangible Carrying', 'B11', `=(${f('B5')}+B5)/${f('B7')}`, `=(${f('B5')}+B5)/${f('C7')}`);
  put('Intangible Carrying', 'B12', '=B10-B11', '=B10+B11');
  put('Earnings Burden', 'B5', `=${f('C10')}`, `=${f('C8')}`);
  put('Earnings Burden', 'B6', `=${f('C9')}`, `=${f('C10')}`);
  put('Earnings Burden', 'B7', '=B5/B6', '=B6/B5');
  put('Earnings Burden', 'B8', `=B6/${f('C6')}`, `=B6/${f('B6')}`);
  put('Earnings Burden', 'B9', `=B6/${f('C7')}`, `=B6/${f('B7')}`);
  put('WriteDown Stress', 'C5', `=${f('C5')}*B5`, `=${f('C5')}*(1+B5)`);
  put('WriteDown Stress', 'C6', `=${f('C6')}-B6`, `=${f('C6')}+B6`);
  put('WriteDown Stress', 'C7', `=${f('C5')}-C5`, `=${f('C5')}+C5`);
  put('WriteDown Stress', 'C8', `=${f('C7')}-C5-B6`, `=${f('C7')}+C5+B6`);
  put('WriteDown Stress', 'C9', `=${f('C10')}-C5-B6`, `=${f('C10')}+C5+B6`);
  put('WriteDown Stress', 'C10', '=(C6+C7)/C8', '=(C6+C7)/C9');
  put('Asset Review', 'B5', `=${f('C5')}`, `=${f('B5')}`);
  put('Asset Review', 'B6', `=${f('C8')}`, `=${f('C9')}`);
  put('Asset Review', 'B7', "='Goodwill Movement'!B9", "='Goodwill Movement'!B8");
  put('Asset Review', 'B8', "='Intangible Carrying'!B10", "='Intangible Carrying'!B11");
  put('Asset Review', 'B9', "='Earnings Burden'!B8", "='Earnings Burden'!B9");
  put('Asset Review', 'B10', "='WriteDown Stress'!C8", "='WriteDown Stress'!C9");
  put('Asset Review', 'B11', "='WriteDown Stress'!C9", "='WriteDown Stress'!C8");
  put('Audit', 'B5', "='Goodwill Movement'!B8-'Goodwill Movement'!B6-'Goodwill Movement'!B9",
    "='Goodwill Movement'!B8+'Goodwill Movement'!B6-'Goodwill Movement'!B9");
  put('Audit', 'B6', `=${f('C5')}+${f('C6')}-('Intangible Carrying'!B10*${f('C7')})`,
    `=${f('C5')}-${f('C6')}-('Intangible Carrying'!B10*${f('C7')})`);
  put('Audit', 'B7', "='WriteDown Stress'!C6+'WriteDown Stress'!C7-('WriteDown Stress'!C10*'WriteDown Stress'!C8)",
    "='WriteDown Stress'!C6-'WriteDown Stress'!C7-('WriteDown Stress'!C10*'WriteDown Stress'!C8)");
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
  ws.getRange('A:A').format.columnWidth = 39;
  ws.getRange('B:B').format.columnWidth = 25;
  if (last === 'C') ws.getRange('C:C').format.columnWidth = 25;
}
function workbook(c, targets, faults) {
  const wb = Workbook.create();
  for (const name of SHEETS) wb.worksheets.add(name);
  const review = wb.worksheets.getItem('Asset Review');
  layout(review, `${c.ticker} FY${c.filing_fiscal_year} goodwill and intangibles`, ['Measure', 'USD m / ratio']);
  set(review, 'A2', [['Repair unmarked calculation faults; preserve original SEC facts.']]);
  set(review, 'A5:A11', [['Closing goodwill'], ['Goodwill acquired during FY'],
    ['Unexplained goodwill movement'],
    ['Goodwill plus intangibles / total assets'], ['Amortization / closing intangibles'],
    ['Modeled assets after charges'], ['Modeled net income after charges']]);
  review.getRange('B5:B7').setNumberFormat('#,##0.0');
  review.getRange('B8:B9').setNumberFormat('0.0%');
  review.getRange('B10:B11').setNumberFormat('#,##0.0');
  const selection = wb.worksheets.getItem('Filing Selection');
  layout(selection, 'Original 10-K acquisition and asset facts', ['Disclosure', 'Prior date', 'Current FY/date'], 'C');
  set(selection, 'A2', [[`Accession ${c.filing_accession}; current ${c.annual_start} to ${c.annual_end}.`]]);
  set(selection, 'A5:A10', [['Goodwill'], ['Intangible assets excluding goodwill'], ['Total assets'],
    ['Goodwill acquired during FY'], ['FY intangible amortization'], ['FY net income']]);
  selection.getRange('B5:C10').setNumberFormat('#,##0.0');
  const movement = wb.worksheets.getItem('Goodwill Movement');
  layout(movement, 'Goodwill acquired versus total carrying movement', ['Measure', 'USD m / ratio']);
  set(movement, 'A2', [['Unexplained movement can include FX, measurement, disposal, or other effects.']]);
  set(movement, 'A5:A11', [['Opening goodwill'], ['Acquired goodwill'], ['Closing goodwill'],
    ['Total goodwill movement'], ['Movement less acquired goodwill'],
    ['Residual / closing goodwill'], ['Closing goodwill / assets']]);
  movement.getRange('B5:B9').setNumberFormat('#,##0.0');
  movement.getRange('B10:B11').setNumberFormat('0.0%');
  const intangible = wb.worksheets.getItem('Intangible Carrying');
  layout(intangible, 'Intangible carrying value and asset mix', ['Measure', 'USD m / ratio']);
  set(intangible, 'A2', [['Intangible movement plus amortization is a residual, not acquired value.']]);
  set(intangible, 'A5:A12', [['Opening non-goodwill intangibles'], ['Closing non-goodwill intangibles'],
    ['Change in carrying value'], ['FY amortization'], ['Other movement residual'],
    ['Current goodwill + intangible / assets'], ['Prior goodwill + intangible / assets'],
    ['Asset-mix change']]);
  intangible.getRange('B5:B9').setNumberFormat('#,##0.0');
  intangible.getRange('B10:B12').setNumberFormat('0.0%');
  const burden = wb.worksheets.getItem('Earnings Burden');
  layout(burden, 'Amortization relative to reported earnings/assets', ['Measure', 'USD m / ratio']);
  set(burden, 'A5:A9', [['Reported net income'], ['FY intangible amortization'],
    ['Net income / amortization'], ['Amortization / closing intangibles'],
    ['Amortization / total assets']]);
  burden.getRange('B5:B6').setNumberFormat('#,##0.0');
  burden.getRange('B7').setNumberFormat('0.00');
  burden.getRange('B8:B9').setNumberFormat('0.0%');
  const stress = wb.worksheets.getItem('WriteDown Stress');
  layout(stress, 'Synthetic carrying-value shock — not SEC guidance', ['Driver / output', 'Assumption', 'Modeled result'], 'C');
  set(stress, 'A2', [['Illustration ignores tax, timing, recoveries, and full impairment rules.']]);
  set(stress, 'A5:A10', [['Goodwill write-down share → charge'],
    ['Additional amortization → intangibles after charge'],
    ['Goodwill after write-down'], ['Modeled total assets'],
    ['Modeled net income after charges'], ['Modeled combined carrying / assets']]);
  set(stress, 'B5:B6', [[c.scenario.goodwill_write_down_fraction],
    [c.scenario.incremental_amortization_m]]);
  stress.getRange('B5:B6').format = { fill: '#FFF0BE',
    font: { name: 'Arial', size: 10, color: '#185AA6' } };
  stress.getRange('B5').setNumberFormat('0.0%');
  stress.getRange('B6').setNumberFormat('#,##0.0');
  stress.getRange('C5:C9').setNumberFormat('#,##0.0');
  stress.getRange('C10').setNumberFormat('0.0%');
  const audit = wb.worksheets.getItem('Audit');
  layout(audit, 'Formula relationship checks', ['Check', 'Expected zero']);
  set(audit, 'A5:A7', [['Total movement less acquired and residual'],
    ['Reported asset mix less source amounts'], ['Modeled carrying ratio checksum']]);
  audit.getRange('B5:B7').setNumberFormat('#,##0.000');
  const raw = wb.worksheets.getItem('Source 10-K');
  layout(raw, 'Unedited original SEC asset fact rows', RAW_HEADERS, 'K');
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
  raw.tables.add(`A4:K${rows.length + 4}`, true, 'GoodwillSecFacts');
  const map = wb.worksheets.getItem('Filing Map');
  layout(map, 'Filing provenance and modeled boundary', ['Field', 'Value']);
  set(map, 'A5:B12', [['CIK', `CIK${String(c.cik).padStart(10, '0')}`],
    ['Accession', c.filing_accession], ['Filing fiscal year', c.filing_fiscal_year],
    ['Prior period end', c.prior_end], ['Current period end', c.annual_end],
    ['Excerpt SHA-256', c.source_excerpt_sha256], ['Raw source SHA-256', c.source_raw_json_sha256],
    ['Scenario boundary', 'Write-down and amortization changes are authored, not filing facts']]);
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
    if (process.env.SEC_GOODWILL_RENDER_QA === '1' && filename === 'reference.xlsx') {
      for (const [sheet, range] of [['Asset Review', 'A1:B12'], ['Filing Selection', 'A1:C11'],
        ['Goodwill Movement', 'A1:B12'], ['Intangible Carrying', 'A1:B13'],
        ['Earnings Burden', 'A1:B10'], ['WriteDown Stress', 'A1:C11'],
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
    `# Goodwill and intangible-asset audit\n\nOpen the ${c.ticker} filing workbook in Microsoft Excel for the web. Repair unmarked formula faults across reported goodwill movement, non-goodwill intangible carrying values, amortization context, and the separate synthetic asset write-down stress. Save and submit the downloaded .xlsx. Preserve all SEC facts, scenario inputs, unrelated formulas, tables, and sheets. The residual goodwill movement is not assumed to equal an acquisition amount; the scenario ignores tax and is not SEC guidance.\n`);
  process.stdout.write(`${c.case_id}: ${targets.size} targets, ${faults.size} unmarked faults\n`);
}
