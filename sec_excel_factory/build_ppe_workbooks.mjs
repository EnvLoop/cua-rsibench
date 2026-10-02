import fs from 'node:fs/promises';
import path from 'node:path';
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const [, , casesPath, outRoot] = process.argv;
if (!casesPath || !outRoot) throw new Error('usage: node build_ppe_workbooks.mjs CASES_JSON OUT_ROOT');
const cases = JSON.parse(await fs.readFile(casesPath, 'utf8'));
const SHEETS = ['PPE Review', 'Filing Selection', 'Gross-to-Net', 'Asset Movement',
  'Capital Intensity', 'Asset Stress', 'Audit', 'Source 10-K', 'Filing Map'];
const METRICS = ['gross_ppe', 'accumulated_depreciation', 'net_ppe', 'assets',
  'capex', 'depreciation_amortization'];
const HEADERS = ['Record ID', 'Concept', 'Unit', 'Start', 'End', 'Filed',
  'Accession', 'Reported USD', 'FY', 'FP', 'Frame'];

function formulas(c) {
  const out = new Map();
  const put = (sheet, addr, good, bad) => out.set(`${sheet}!${addr}`, { good, bad });
  const source = (year, metric) => {
    const record = c.canonical[`${year}:${metric}`];
    const i = c.records.findIndex(r => r.id === record.id);
    if (i < 0) throw new Error(`source missing ${c.case_id}:${year}:${metric}`);
    return `'Source 10-K'!H${i + 5}`;
  };
  for (const [year, col] of [['prior', 'B'], ['current', 'C']]) {
    METRICS.forEach((metric, i) => {
      const wrongYear = year === 'prior' ? 'current' : 'prior';
      const wrong = i % 2 ? source(year, METRICS[(i + 1) % METRICS.length]) : source(wrongYear, metric);
      put('Filing Selection', `${col}${i + 5}`, `=${source(year, metric)}/1000000`, `=${wrong}/1000000`);
    });
  }
  const f = a => `'Filing Selection'!${a}`;
  put('Gross-to-Net', 'B5', `=${f('C5')}`, `=${f('B5')}`);
  put('Gross-to-Net', 'B6', `=${f('C6')}`, `=${f('B6')}`);
  put('Gross-to-Net', 'B7', '=B5-B6', '=B5+B6');
  put('Gross-to-Net', 'B8', `=${f('C7')}`, `=${f('B7')}`);
  put('Gross-to-Net', 'B9', '=B7-B8', '=B7+B8');
  put('Gross-to-Net', 'B10', '=B6/B5', '=B5/B6');
  put('Gross-to-Net', 'B11', '=B8/B5', '=B5/B8');
  put('Gross-to-Net', 'B12', `=B8/${f('C8')}`, `=B8/${f('B8')}`);
  put('Asset Movement', 'B5', `=${f('B5')}`, `=${f('C5')}`);
  put('Asset Movement', 'B6', `=${f('C5')}`, `=${f('B5')}`);
  put('Asset Movement', 'B7', '=B6-B5', '=B6+B5');
  put('Asset Movement', 'B8', `=${f('B6')}`, `=${f('C6')}`);
  put('Asset Movement', 'B9', `=${f('C6')}`, `=${f('B6')}`);
  put('Asset Movement', 'B10', '=B9-B8', '=B9+B8');
  put('Asset Movement', 'B11', `=${f('B7')}`, `=${f('C7')}`);
  put('Asset Movement', 'B12', `=${f('C7')}`, `=${f('B7')}`);
  put('Asset Movement', 'B13', '=B12-B11', '=B12+B11');
  put('Asset Movement', 'B14', `=${f('C9')}-${f('C10')}`, `=${f('C9')}+${f('C10')}`);
  put('Asset Movement', 'B15', '=B13-B14', '=B13+B14');
  put('Capital Intensity', 'B5', `=${f('C9')}`, `=${f('B9')}`);
  put('Capital Intensity', 'B6', `=${f('C10')}`, `=${f('B10')}`);
  put('Capital Intensity', 'B7', '=B5/B6', '=B6/B5');
  put('Capital Intensity', 'B8', `=B5/${f('C7')}`, `=B5/${f('B7')}`);
  put('Capital Intensity', 'B9', `=B6/${f('C7')}`, `=B6/${f('B7')}`);
  put('Capital Intensity', 'B10', `=${f('C7')}/${f('C8')}`, `=${f('C8')}/${f('C7')}`);
  put('Asset Stress', 'C5', `=${f('C7')}*B5`, `=${f('B7')}*B5`);
  put('Asset Stress', 'C6', `=${f('C9')}*(1+B6)`, `=${f('C9')}*(1-B6)`);
  put('Asset Stress', 'C7', `=${f('C7')}-C5`, `=${f('C7')}+C5`);
  put('Asset Stress', 'C8', `=${f('C8')}-C5`, `=${f('C8')}+C5`);
  put('Asset Stress', 'C9', '=C7/C8', '=C8/C7');
  put('Asset Stress', 'C10', `=C6/${f('C10')}`, `=C6/${f('C9')}`);
  put('PPE Review', 'B5', "='Gross-to-Net'!B8", "='Gross-to-Net'!B7");
  put('PPE Review', 'B6', "='Gross-to-Net'!B9", "='Gross-to-Net'!B7");
  put('PPE Review', 'B7', "='Gross-to-Net'!B10", "='Gross-to-Net'!B11");
  put('PPE Review', 'B8', "='Asset Movement'!B13", "='Asset Movement'!B14");
  put('PPE Review', 'B9', "='Asset Movement'!B15", "='Asset Movement'!B14");
  put('PPE Review', 'B10', "='Capital Intensity'!B7", "='Capital Intensity'!B8");
  put('PPE Review', 'B11', "='Asset Stress'!C9", "='Asset Stress'!C7");
  put('PPE Review', 'B12', "='Asset Stress'!C10", "='Asset Stress'!C9");
  put('Audit', 'B5', "='Gross-to-Net'!B7-'Gross-to-Net'!B8",
    "='Gross-to-Net'!B7+'Gross-to-Net'!B8");
  put('Audit', 'B6', "='Asset Movement'!B6-'Asset Movement'!B5-'Asset Movement'!B7",
    "='Asset Movement'!B6+'Asset Movement'!B5-'Asset Movement'!B7");
  put('Audit', 'B7', "='Asset Movement'!B12-'Asset Movement'!B11-'Asset Movement'!B13",
    "='Asset Movement'!B12+'Asset Movement'!B11-'Asset Movement'!B13");
  put('Audit', 'B8', "='Asset Stress'!C7+'Asset Stress'!C5-'Gross-to-Net'!B8",
    "='Asset Stress'!C7-'Asset Stress'!C5-'Gross-to-Net'!B8");
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
  ws.getRange('A:A').format.columnWidth = 43;
  ws.getRange('B:B').format.columnWidth = 25;
  if (last === 'C') ws.getRange('C:C').format.columnWidth = 25;
}

function workbook(c, targets, faults) {
  const wb = Workbook.create();
  for (const name of SHEETS) wb.worksheets.add(name);
  const review = wb.worksheets.getItem('PPE Review');
  layout(review, `${c.ticker} FY${c.filing_fiscal_year} PPE carrying-value review`, ['Measure', 'USD m / ratio']);
  set(review, 'A2', [['Repair unmarked defects; SEC disclosures and modeled stress stay separate.']]);
  set(review, 'A5:A12', [['Reported net PPE'], ['Gross less accumulated minus net residual'],
    ['Accumulated depreciation / gross PPE'], ['Reported net PPE change'],
    ['Net movement less capex plus D&A residual'], ['Capex / D&A'],
    ['Modeled net PPE / modeled assets'], ['Modeled capex / reported D&A']]);
  review.getRange('B5:B6').setNumberFormat('#,##0.00');
  review.getRange('B7').setNumberFormat('0.0%');
  review.getRange('B8:B9').setNumberFormat('#,##0.00');
  review.getRange('B10').setNumberFormat('0.00');
  review.getRange('B11').setNumberFormat('0.0%');
  review.getRange('B12').setNumberFormat('0.00');
  const selection = wb.worksheets.getItem('Filing Selection');
  layout(selection, 'Original 10-K property and capital facts', ['SEC metric', 'Prior FY', 'Current FY'], 'C');
  set(selection, 'A2', [[`Accession ${c.filing_accession}; current ${c.annual_start} to ${c.annual_end}.`]]);
  set(selection, 'A5:A10', [['Gross PPE'], ['Accumulated depreciation'], ['Net PPE'],
    ['Total assets'], ['Capital expenditures'], ['Depreciation and amortization']]);
  selection.getRange('B5:C10').setNumberFormat('#,##0.00');
  const gross = wb.worksheets.getItem('Gross-to-Net');
  layout(gross, 'Reported gross-to-net PPE bridge', ['Measure', 'USD m / ratio']);
  set(gross, 'A2', [['A small rounding difference can remain between reported figures.']]);
  set(gross, 'A5:A12', [['Reported gross PPE'], ['Reported accumulated depreciation'],
    ['Gross less accumulated'], ['Separately reported net PPE'],
    ['Computed less reported net residual'], ['Accumulated / gross'],
    ['Reported net / gross'], ['Reported net PPE / total assets']]);
  gross.getRange('B5:B9').setNumberFormat('#,##0.00');
  gross.getRange('B10:B12').setNumberFormat('0.0%');
  const movement = wb.worksheets.getItem('Asset Movement');
  layout(movement, 'PPE movement and unexplained residual', ['Measure', 'USD m']);
  set(movement, 'A2', [['Residual may include disposals, acquisitions, FX or other effects; no cause is inferred.']]);
  set(movement, 'A5:A15', [['Prior gross PPE'], ['Current gross PPE'], ['Change in gross PPE'],
    ['Prior accumulated depreciation'], ['Current accumulated depreciation'],
    ['Change in accumulated depreciation'], ['Prior reported net PPE'],
    ['Current reported net PPE'], ['Change in reported net PPE'],
    ['Current capex less current D&A'], ['Unexplained net PPE movement']]);
  movement.getRange('B5:B15').setNumberFormat('#,##0.00');
  const intensity = wb.worksheets.getItem('Capital Intensity');
  layout(intensity, 'Capital expenditure and asset-base ratios', ['Measure', 'USD m / ratio']);
  set(intensity, 'A5:A10', [['Current capital expenditures'], ['Current D&A'],
    ['Capex / D&A'], ['Capex / reported net PPE'], ['D&A / reported net PPE'],
    ['Reported net PPE / total assets']]);
  intensity.getRange('B5:B6').setNumberFormat('#,##0.00');
  intensity.getRange('B7').setNumberFormat('0.00');
  intensity.getRange('B8:B10').setNumberFormat('0.0%');
  const stress = wb.worksheets.getItem('Asset Stress');
  layout(stress, 'Synthetic write-down and capex stress — not SEC guidance',
    ['Driver / output', 'Assumption', 'Modeled result'], 'C');
  set(stress, 'A2', [['Illustrative carrying-value sensitivity; not an issuer forecast or booked impairment.']]);
  set(stress, 'A5:A10', [['Net PPE write-down fraction → amount'],
    ['Capex increase fraction → modeled capex'], ['Modeled net PPE'],
    ['Modeled total assets'], ['Modeled net PPE / modeled assets'],
    ['Modeled capex / reported D&A']]);
  set(stress, 'B5:B6', [[c.scenario.modeled_write_down_fraction],
    [c.scenario.maintenance_capex_increase_fraction]]);
  stress.getRange('B5:B6').format = { fill: '#FFF0BE',
    font: { name: 'Arial', size: 10, color: '#185AA6' } };
  stress.getRange('B5:B6').setNumberFormat('0.0%');
  stress.getRange('C5:C8').setNumberFormat('#,##0.00');
  stress.getRange('C9').setNumberFormat('0.0%');
  stress.getRange('C10').setNumberFormat('0.00');
  const audit = wb.worksheets.getItem('Audit');
  layout(audit, 'PPE formula relationship checks', ['Check', 'USD m']);
  set(audit, 'A5:A8', [['Gross-to-net residual (may be nonzero from rounding)'],
    ['Gross PPE delta relationship (zero)'], ['Net PPE delta relationship (zero)'],
    ['Modeled net PPE bridge (zero)']]);
  audit.getRange('B5:B8').setNumberFormat('#,##0.000');
  const raw = wb.worksheets.getItem('Source 10-K');
  layout(raw, 'Unedited original-filing PPE facts', HEADERS, 'K');
  set(raw, 'A2', [[c.filing_index_url]]);
  const rows = c.records.map(r => [r.id, r.concept, r.unit, r.start, r.end,
    r.filed, r.accession, r.value, r.fy, r.fp, r.frame]);
  set(raw, `A5:K${rows.length + 4}`, rows);
  raw.getRange('A:A').format.columnWidth = 22;
  raw.getRange('B:B').format.columnWidth = 74;
  raw.getRange('C:F').format.columnWidth = 18;
  raw.getRange('G:G').format.columnWidth = 26;
  raw.getRange('H:H').format.columnWidth = 22;
  raw.getRange('I:K').format.columnWidth = 14;
  raw.freezePanes.freezeRows(4);
  raw.tables.add(`A4:K${rows.length + 4}`, true, 'PpeSecFacts');
  const map = wb.worksheets.getItem('Filing Map');
  layout(map, 'Original filing and modeled boundary', ['Field', 'Value']);
  set(map, 'A5:B12', [['CIK', `CIK${String(c.cik).padStart(10, '0')}`],
    ['Accession', c.filing_accession], ['Filing fiscal year', c.filing_fiscal_year],
    ['Prior period end', c.prior_end], ['Current period end', c.annual_end],
    ['Excerpt SHA-256', c.source_excerpt_sha256], ['Raw source SHA-256', c.source_raw_json_sha256],
    ['Scenario boundary', 'Write-down and maintenance capex increase are authored; SEC facts stay unchanged']]);
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
  const faults = new Set(Array.from({ length: 9 }, (_, i) => pool[(index * 17 + i * 13) % pool.length]));
  if (faults.size !== 9) throw new Error(`fault collision ${c.case_id}`);
  for (const [filename, selected] of [['actor.xlsx', faults], ['reference.xlsx', new Set()]]) {
    const wb = workbook(c, targets, selected);
    if (process.env.SEC_PPE_RENDER_QA === '1' && filename === 'reference.xlsx') {
      for (const [sheet, range] of [['PPE Review', 'A1:B13'], ['Filing Selection', 'A1:C11'],
        ['Gross-to-Net', 'A1:B13'], ['Asset Movement', 'A1:B16'],
        ['Capital Intensity', 'A1:B11'], ['Asset Stress', 'A1:C11'],
        ['Audit', 'A1:B9'], ['Source 10-K', 'A1:K12'], ['Filing Map', 'A1:B15']]) {
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
    `# Property, plant and equipment audit\n\nOpen the ${c.ticker} original 10-K workbook in Microsoft Excel for the web. Repair unmarked formula faults across gross-to-net PPE carrying values, two-year asset movement, capex and depreciation ratios, and a separate synthetic write-down and maintenance-capex stress. Save and submit the downloaded .xlsx. Preserve every SEC source fact, scenario input, unrelated formula, table, and sheet. The movement residual has no asserted cause; the write-down is illustrative, not booked by the issuer.\n`);
  process.stdout.write(`${c.case_id}: ${targets.size} targets, ${faults.size} unmarked faults\n`);
}
