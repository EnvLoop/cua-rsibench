import fs from 'node:fs/promises';
import path from 'node:path';
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const [, , casesPath, outRoot] = process.argv;
if (!casesPath || !outRoot) throw new Error('usage: node build_eps_workbooks.mjs CASES_JSON OUT_ROOT');
const cases = JSON.parse(await fs.readFile(casesPath, 'utf8'));
const SHEETS = ['Return Review', 'Filing Selection', 'EPS Bridge', 'Capital Returns',
  'Repurchase Scenario', 'Audit', 'Source 10-K', 'Filing Map'];
const METRICS = ['net_income', 'basic_shares', 'diluted_shares', 'eps_basic',
  'eps_diluted', 'repurchases', 'dividends'];
const HEADERS = ['Record ID', 'Concept', 'Unit', 'Start', 'End', 'Filed',
  'Accession', 'Reported value', 'FY', 'FP', 'Frame'];

function formulas(c) {
  const targets = new Map();
  const put = (sheet, cell, good, bad) => targets.set(`${sheet}!${cell}`, { good, bad });
  const raw = (year, metric) => {
    const r = c.canonical[`${year}:${metric}`];
    const i = c.records.findIndex(row => row.id === r.id);
    if (i < 0) throw new Error(`missing source ${year}:${metric}`);
    return `'Source 10-K'!H${i + 5}`;
  };
  for (const [year, col] of [['prior', 'B'], ['current', 'C']]) {
    METRICS.forEach((metric, i) => {
      const conversion = metric.startsWith('eps_') ? '' : '/1000000';
      const wrongYear = year === 'prior' ? 'current' : 'prior';
      const bad = i % 2
        ? `=${raw(year, METRICS[(i + 1) % METRICS.length])}${conversion}`
        : `=${raw(wrongYear, metric)}${conversion}`;
      put('Filing Selection', `${col}${i + 5}`, `=${raw(year, metric)}${conversion}`, bad);
    });
  }
  const f = addr => `'Filing Selection'!${addr}`;
  put('EPS Bridge', 'B5', `=${f('C6')}`, `=${f('B6')}`);
  put('EPS Bridge', 'B6', `=${f('C7')}`, `=${f('B7')}`);
  put('EPS Bridge', 'B7', '=B6-B5', '=B6+B5');
  put('EPS Bridge', 'B8', '=B7/B5', '=B7/B6');
  put('EPS Bridge', 'B9', `=${f('C8')}-${f('C9')}`, `=${f('C8')}+${f('C9')}`);
  put('EPS Bridge', 'B10', `=${f('C5')}/B5`, `=${f('C5')}/B6`);
  put('EPS Bridge', 'B11', `=${f('C5')}/B6`, `=${f('C5')}/B5`);
  put('EPS Bridge', 'B12', `=${f('C9')}-B11`, `=${f('C9')}+B11`);
  for (const col of ['B', 'C']) {
    put('Capital Returns', `${col}5`, `=${f(`${col}10`)}`, `=${f(`${col}11`)}`);
    put('Capital Returns', `${col}6`, `=${f(`${col}11`)}`, `=${f(`${col}10`)}`);
    put('Capital Returns', `${col}7`, `=${col}5+${col}6`, `=${col}5-${col}6`);
    put('Capital Returns', `${col}8`, `=${col}7/${f(`${col}5`)}`, `=${col}5/${f(`${col}5`)}`);
    put('Capital Returns', `${col}9`, `=${col}5/${col}7`, `=${col}6/${col}7`);
    put('Capital Returns', `${col}10`, `=${f(`${col}5`)}-${col}7`, `=${f(`${col}5`)}+${col}7`);
  }
  put('Repurchase Scenario', 'C5', `=${f('C10')}*B6`, `=${f('C10')}*(1+B6)`);
  put('Repurchase Scenario', 'C6', '=C5/B5', '=C5*B5');
  put('Repurchase Scenario', 'C7', `=${f('C7')}-C6`, `=${f('C7')}+C6`);
  put('Repurchase Scenario', 'C8', `=${f('C5')}/C7`, `=${f('C5')}/${f('C7')}`);
  put('Repurchase Scenario', 'C9', "=C8-'EPS Bridge'!B11", "=C8+'EPS Bridge'!B11");
  put('Repurchase Scenario', 'C10', `=(${f('C11')}+C5)/${f('C5')}`,
    `=(${f('C11')}+${f('C10')})/${f('C5')}`);
  put('Return Review', 'B5', `=${f('C5')}`, `=${f('B5')}`);
  put('Return Review', 'B6', `=${f('C9')}`, `=${f('C8')}`);
  put('Return Review', 'B7', "='EPS Bridge'!B7", "='EPS Bridge'!B5");
  put('Return Review', 'B8', "='Capital Returns'!C7", "='Capital Returns'!C5");
  put('Return Review', 'B9', "='Capital Returns'!C8", "='Capital Returns'!B8");
  put('Return Review', 'B10', "='Repurchase Scenario'!C8", "='Repurchase Scenario'!C9");
  put('Return Review', 'B11', "='Repurchase Scenario'!C9", "='Repurchase Scenario'!C8");
  put('Audit', 'B5', "='Capital Returns'!C5+'Capital Returns'!C6-'Capital Returns'!C7",
    "='Capital Returns'!C5-'Capital Returns'!C6-'Capital Returns'!C7");
  put('Audit', 'B6', "='EPS Bridge'!B5+'EPS Bridge'!B7-'EPS Bridge'!B6",
    "='EPS Bridge'!B5-'EPS Bridge'!B7-'EPS Bridge'!B6");
  put('Audit', 'B7', "='Repurchase Scenario'!C6*'Repurchase Scenario'!B5-'Repurchase Scenario'!C5",
    "='Repurchase Scenario'!C6+'Repurchase Scenario'!B5-'Repurchase Scenario'!C5");
  return targets;
}

function set(ws, range, values) { ws.getRange(range).values = values; }
function frame(ws, title, header, last = 'B') {
  ws.showGridLines = false;
  set(ws, 'A1', [[title]]);
  ws.getRange('A1').format.font = { name: 'Arial', size: 15, bold: true, color: '#173A5E' };
  set(ws, `A4:${last}4`, [header]);
  ws.getRange(`A4:${last}4`).format = { fill: '#173A5E',
    font: { name: 'Arial', size: 10, bold: true, color: '#FFFFFF' }, rowHeight: 30 };
  ws.getRange('A:A').format.columnWidth = 39;
  ws.getRange('B:B').format.columnWidth = 24;
  if (last === 'C') ws.getRange('C:C').format.columnWidth = 24;
}
function workbook(c, targets, faulted) {
  const wb = Workbook.create();
  for (const name of SHEETS) wb.worksheets.add(name);
  const review = wb.worksheets.getItem('Return Review');
  frame(review, `${c.ticker} FY${c.filing_fiscal_year} EPS and capital returns`, ['Measure', 'USD m / shares m / EPS']);
  set(review, 'A2', [['Repair unmarked calculation faults; SEC data and scenario are separate.']]);
  set(review, 'A5:A11', [['Net income'], ['Reported diluted EPS'], ['Weighted-average share dilution'],
    ['Cash repurchases plus dividends'], ['Cash return / net income'],
    ['Illustrative diluted EPS after buyback'], ['Illustrative EPS change']]);
  review.getRange('B5').setNumberFormat('#,##0.0');
  review.getRange('B6').setNumberFormat('0.00');
  review.getRange('B7:B8').setNumberFormat('#,##0.0');
  review.getRange('B9').setNumberFormat('0.0%');
  review.getRange('B10:B11').setNumberFormat('0.00');
  const sel = wb.worksheets.getItem('Filing Selection');
  frame(sel, 'Original 10-K, mixed USD / share / EPS units', ['SEC metric', 'Prior FY', 'Current FY'], 'C');
  set(sel, 'A2', [[`Accession ${c.filing_accession}; current ${c.annual_start} to ${c.annual_end}.`]]);
  set(sel, 'A5:A11', [['Net income, USD m'], ['Basic weighted-average shares, m'],
    ['Diluted weighted-average shares, m'], ['Reported basic EPS, USD/share'],
    ['Reported diluted EPS, USD/share'], ['Cash repurchases, USD m'], ['Cash dividends, USD m']]);
  sel.getRange('B5:C7').setNumberFormat('#,##0.0');
  sel.getRange('B8:C9').setNumberFormat('0.00');
  sel.getRange('B10:C11').setNumberFormat('#,##0.0');
  const eps = wb.worksheets.getItem('EPS Bridge');
  frame(eps, 'Diluted share bridge and reported EPS context', ['Measure', 'Shares m / USD per share']);
  set(eps, 'A2', [['Simple net-income/share estimates need not equal reported EPS.']]);
  set(eps, 'A5:A12', [['Basic weighted-average shares'], ['Diluted weighted-average shares'],
    ['Share dilution spread'], ['Dilution / basic shares'], ['Reported basic less diluted EPS'],
    ['Simple income / basic share ratio'], ['Simple income / diluted share ratio'],
    ['Reported diluted EPS less simple ratio']]);
  eps.getRange('B5:B7').setNumberFormat('#,##0.0');
  eps.getRange('B8').setNumberFormat('0.0%');
  eps.getRange('B9:B12').setNumberFormat('0.000');
  const returns = wb.worksheets.getItem('Capital Returns');
  frame(returns, 'Cash returned to shareholders', ['Measure', 'Prior FY', 'Current FY'], 'C');
  set(returns, 'A5:A10', [['Cash share repurchases'], ['Cash dividends'], ['Total cash returns'],
    ['Returns / net income'], ['Repurchases / cash returns'], ['Net income less cash returns']]);
  returns.getRange('B5:C7').setNumberFormat('#,##0.0');
  returns.getRange('B8:C9').setNumberFormat('0.0%');
  returns.getRange('B10:C10').setNumberFormat('#,##0.0');
  const sc = wb.worksheets.getItem('Repurchase Scenario');
  frame(sc, 'Synthetic repurchase case — not SEC guidance', ['Driver / modeled result', 'Assumption', 'Result'], 'C');
  set(sc, 'A2', [['Price and spend ignore timing, tax, market response, and numerator changes.']]);
  set(sc, 'A5:A10', [['Share price → modeled spend'], ['Buyback fraction → shares retired'],
    ['Illustrative diluted shares'], ['Illustrative diluted EPS'],
    ['EPS change from simple base'], ['Modeled cash return / net income']]);
  set(sc, 'B5:B6', [[c.scenario.synthetic_repurchase_price_usd],
    [c.scenario.synthetic_buyback_budget_fraction]]);
  sc.getRange('B5:B6').format = { fill: '#FFF0BE',
    font: { name: 'Arial', size: 10, color: '#185AA6' } };
  sc.getRange('B5').setNumberFormat('#,##0.00');
  sc.getRange('B6').setNumberFormat('0.0%');
  sc.getRange('C5:C7').setNumberFormat('#,##0.0');
  sc.getRange('C8:C9').setNumberFormat('0.000');
  sc.getRange('C10').setNumberFormat('0.0%');
  const audit = wb.worksheets.getItem('Audit');
  frame(audit, 'Formula relationship checks', ['Check', 'Expected zero']);
  set(audit, 'A5:A7', [['Cash-return components less total'], ['Basic plus spread less diluted shares'],
    ['Retired shares times price less spend']]);
  audit.getRange('B5:B7').setNumberFormat('#,##0.000');
  const raw = wb.worksheets.getItem('Source 10-K');
  frame(raw, 'Unedited mixed-unit SEC filing facts', HEADERS, 'K');
  set(raw, 'A2', [[c.filing_index_url]]);
  const rows = c.records.map(r => [r.id, r.concept, r.unit, r.start, r.end,
    r.filed, r.accession, r.value, r.fy, r.fp, r.frame]);
  set(raw, `A5:K${rows.length + 4}`, rows);
  raw.getRange('A:A').format.columnWidth = 22;
  raw.getRange('B:B').format.columnWidth = 55;
  raw.getRange('C:F').format.columnWidth = 18;
  raw.getRange('G:G').format.columnWidth = 26;
  raw.getRange('H:H').format.columnWidth = 22;
  raw.getRange('I:K').format.columnWidth = 15;
  raw.freezePanes.freezeRows(4);
  raw.tables.add(`A4:K${rows.length + 4}`, true, 'EpsSecFacts');
  const map = wb.worksheets.getItem('Filing Map');
  frame(map, 'Filing provenance and scenario boundary', ['Field', 'Value']);
  set(map, 'A5:B12', [['CIK', `CIK${String(c.cik).padStart(10, '0')}`],
    ['Accession', c.filing_accession], ['Filing fiscal year', c.filing_fiscal_year],
    ['Prior period end', c.prior_end], ['Current period end', c.annual_end],
    ['Excerpt SHA-256', c.source_excerpt_sha256], ['Raw source SHA-256', c.source_raw_json_sha256],
    ['Model boundary', 'Scenario price and spend authored; reported EPS is separate']]);
  map.getRange('A:A').format.columnWidth = 34;
  map.getRange('B:B').format.columnWidth = 84;
  set(map, 'A14', [[c.filing_index_url]]);
  for (const [key, pair] of targets) {
    const bang = key.lastIndexOf('!');
    wb.worksheets.getItem(key.slice(0, bang)).getRange(key.slice(bang + 1)).formulas = [[
      faulted.has(key) ? pair.bad : pair.good,
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
  const pool = [...targets.keys()].filter(key => !key.startsWith('Audit!'));
  const faults = new Set(Array.from({ length: 9 }, (_, i) => pool[(index * 13 + i * 7) % pool.length]));
  if (faults.size !== 9) throw new Error(`fault collision ${c.case_id}`);
  for (const [filename, selected] of [['actor.xlsx', faults], ['reference.xlsx', new Set()]]) {
    const wb = workbook(c, targets, selected);
    if (process.env.SEC_EPS_RENDER_QA === '1' && filename === 'reference.xlsx') {
      for (const [sheet, range] of [['Return Review', 'A1:B12'], ['Filing Selection', 'A1:C12'],
        ['EPS Bridge', 'A1:B13'], ['Capital Returns', 'A1:C11'],
        ['Repurchase Scenario', 'A1:C11'], ['Audit', 'A1:B8'],
        ['Source 10-K', 'A1:K12'], ['Filing Map', 'A1:B15']]) {
        const rendered = await wb.render({ sheetName: sheet, range, scale: 1.25, format: 'png' });
        await fs.writeFile(path.join(dir, `qa-${sheet.toLowerCase().replaceAll(' ', '-')}.png`),
          new Uint8Array(await rendered.arrayBuffer()));
      }
    }
    const file = await SpreadsheetFile.exportXlsx(wb);
    await file.save(path.join(dir, filename));
  }
  await fs.writeFile(path.join(dir, 'private-oracle.json'), JSON.stringify({
    case_id: c.case_id, sheet_order: SHEETS, faulted: [...faults].sort(),
    targets: Object.fromEntries([...targets].map(([key, pair]) => [key, pair.good])),
  }, null, 2) + '\n');
  await fs.writeFile(path.join(dir, 'task.md'),
    `# Dilution and shareholder-return audit\n\nOpen the ${c.ticker} 10-K workbook in Microsoft Excel for the web. Repair unmarked formula faults across fiscal fact selection, weighted-average shares and EPS, shareholder cash returns, and the synthetic repurchase case. Save and submit the downloaded .xlsx. Preserve every SEC record, model input, unrelated formula, table, and sheet. The scenario price and spend fraction are benchmark-authored, not market data or SEC guidance. Reported EPS may differ from simple net-income-per-share ratios due to accounting basis or rounding.\n`);
  process.stdout.write(`${c.case_id}: ${targets.size} targets and ${faults.size} unmarked faults\n`);
}
