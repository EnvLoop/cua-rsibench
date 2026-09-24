import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const here = path.dirname(fileURLToPath(import.meta.url));
const excerpt = JSON.parse(await fs.readFile(path.join(here, 'sources/excerpt.json'), 'utf8'));
const outDir = process.argv[2] || path.join(here, 'output');
const variant = process.argv[3] || 'base';
if (!['base', 'holdout'].includes(variant)) throw new Error('variant must be base or holdout');
const multiplier = variant === 'base' ? 1 : 1.173;
const metricColumns = {
  'Revenue': 'D', 'Operating income': 'E', 'Operating cash flow': 'F',
  'Capital expenditures': 'G', 'Assets': 'H', 'Liabilities': 'I', 'Equity': 'J',
};
const rowFor = new Map(excerpt.rows.map((r, i) => [r.id, i + 5]));
const target = new Map();
const put = (sheet, cell, formula) => target.set(`${sheet}!${cell}`, formula);

for (const [issuer, year, row] of [['Apple', '2023', 5], ['Apple', '2024', 6], ['Microsoft', '2023', 7], ['Microsoft', '2024', 8]]) {
  for (const [metric, col] of Object.entries(metricColumns)) {
    const id = excerpt.canonical_record_ids[`${issuer}:${year}:${metric}`];
    const rawRow = rowFor.get(id);
    if (!rawRow) throw new Error(`Canonical record absent: ${issuer} ${year} ${metric}`);
    put('FY Selection', `${col}${row}`, `='Raw SEC'!O${rawRow}/1000000`);
  }
  put('FY Selection', `K${row}`, `=H${row}-I${row}-J${row}`);
}
for (const [driverRow, fy23, fy24] of [[5, 5, 6], [6, 7, 8]]) {
  put('Drivers', `B${driverRow}`, `='FY Selection'!D${fy24}/'FY Selection'!D${fy23}-1`);
  put('Drivers', `C${driverRow}`, `='FY Selection'!F${fy24}/'FY Selection'!D${fy24}`);
  put('Drivers', `D${driverRow}`, `='FY Selection'!G${fy24}/'FY Selection'!D${fy24}`);
  put('Drivers', `E${driverRow}`, `=B${driverRow}/2`);
}
for (const [r25, r26, actualRow, driverRow] of [[5, 6, 6, 5], [7, 8, 8, 6]]) {
  for (const [r, prior, growthCol] of [[r25, `'FY Selection'!D${actualRow}`, 'B'], [r26, `D${r25}`, 'E']]) {
    put('Forecast', `C${r}`, `=${prior}`);
    put('Forecast', `D${r}`, `=C${r}*(1+Drivers!${growthCol}${driverRow})`);
    put('Forecast', `E${r}`, `=D${r}*Drivers!C${driverRow}`);
    put('Forecast', `F${r}`, `=D${r}*Drivers!D${driverRow}*Drivers!F${driverRow}`);
    put('Forecast', `G${r}`, `=E${r}-F${r}`);
    put('Forecast', `H${r}`, `=D${r}*'FY Selection'!E${actualRow}/'FY Selection'!D${actualRow}`);
    put('Forecast', `I${r}`, `=G${r}/D${r}`);
  }
}
for (const [viewRow, actualRow, driverRow, forecastRow] of [[5, 6, 5, 6], [6, 8, 6, 8]]) {
  for (const [col, formula] of Object.entries({
    B: `='FY Selection'!D${actualRow}`,
    C: `='FY Selection'!F${actualRow}-'FY Selection'!G${actualRow}`,
    D: `=Drivers!B${driverRow}`,
    E: `='FY Selection'!E${actualRow}/'FY Selection'!D${actualRow}`,
    F: `=Forecast!D${forecastRow}`,
    G: `=Forecast!G${forecastRow}`,
    H: `=Forecast!I${forecastRow}`,
    I: `='FY Selection'!K${actualRow}`,
  })) put('Committee View', `${col}${viewRow}`, formula);
}

function baseStyle(sheet, range) {
  sheet.showGridLines = false;
  sheet.getRange(range).format.font = { name: 'Arial', size: 10, color: '#202A33' };
  sheet.getRange('A:A').format.columnWidth = 19;
  sheet.getRange('B:B').format.columnWidth = 18;
  sheet.getRange('C:C').format.columnWidth = 18;
  sheet.getRange('D:K').format.columnWidth = 19;
  sheet.getRange('A1:K1').format.font = { name: 'Arial', size: 14, bold: true, color: '#1A3552' };
  sheet.getRange('A4:K4').format = { fill: '#173A5E', font: { name: 'Arial', size: 10, bold: true, color: '#FFFFFF' }, rowHeight: 32, wrapText: true };
}
function setRows(sheet, addr, matrix) { sheet.getRange(addr).values = matrix; }
function createWorkbook(filled) {
  const wb = Workbook.create();
  for (const name of ['Committee View', 'FY Selection', 'Drivers', 'Forecast', 'Raw SEC']) wb.worksheets.add(name);
  const view = wb.worksheets.getItem('Committee View');
  baseStyle(view, 'A1:I8');
  view.tabColor = '#173A5E';
  setRows(view, 'A1:A1', [['Fiscal 2024 review and FY2026 forecast']]);
  setRows(view, 'A2:A2', [['USD millions; fiscal year ends differ by issuer']]);
  setRows(view, 'A4:I4', [['Issuer', 'FY24 revenue', 'FY24 free cash flow', 'FY24 revenue growth', 'FY24 operating margin', 'FY26 revenue', 'FY26 free cash flow', 'FY26 FCF margin', 'Assets less liabilities/equity']]);
  setRows(view, 'A5:A6', [['Apple'], ['Microsoft']]);
  view.getRange('B5:C6').setNumberFormat('#,##0.0;(#,##0.0);-');
  view.getRange('F5:G6').setNumberFormat('#,##0.0;(#,##0.0);-');
  view.getRange('D5:E6').setNumberFormat('0.0%');
  view.getRange('H5:H6').setNumberFormat('0.0%');
  view.getRange('I5:I6').setNumberFormat('0.00;[Red](0.00);-');

  const selection = wb.worksheets.getItem('FY Selection');
  baseStyle(selection, 'A1:K9');
  selection.tabColor = '#D9B77A';
  setRows(selection, 'A1:A1', [['Annual facts selected from issuer FY2024 10-K filings']]);
  setRows(selection, 'A2:A2', [['USD millions. Use each issuer’s exact fiscal year-end and filing accession.']]);
  setRows(selection, 'A4:K4', [['Issuer', 'Fiscal year', 'Period end', 'Revenue', 'Operating income', 'Operating cash flow', 'Capital expenditures', 'Assets', 'Liabilities', 'Equity', 'Balance check']]);
  setRows(selection, 'A5:C8', [['Apple', 2023, '2023-09-30'], ['Apple', 2024, '2024-09-28'], ['Microsoft', 2023, '2023-06-30'], ['Microsoft', 2024, '2024-06-30']]);
  selection.getRange('D5:K8').setNumberFormat('#,##0.0;(#,##0.0);-');

  const drivers = wb.worksheets.getItem('Drivers');
  baseStyle(drivers, 'A1:F8');
  drivers.tabColor = '#6686A8';
  setRows(drivers, 'A1:A1', [['Forecast drivers']]);
  setRows(drivers, 'A2:A2', [['FY25 growth and cash ratios use FY24 actuals; FY26 growth is half FY25.']]);
  setRows(drivers, 'A3:A3', [['Capital-spending multiplier is an editable scenario assumption, not an SEC fact.']]);
  setRows(drivers, 'A4:F4', [['Issuer', 'FY25 revenue growth', 'FY24 OCF/revenue', 'FY24 capex/revenue', 'FY26 revenue growth', 'Capex scenario multiplier']]);
  setRows(drivers, 'A5:A6', [['Apple'], ['Microsoft']]);
  drivers.getRange('F5:F6').values = [[multiplier], [1]];
  drivers.getRange('B5:E6').setNumberFormat('0.0%');
  drivers.getRange('F5:F6').setNumberFormat('0.000x');
  drivers.getRange('F5:F6').format = { fill: '#FFF0BE', font: { name: 'Arial', size: 10, color: '#185AA6' } };

  const forecast = wb.worksheets.getItem('Forecast');
  baseStyle(forecast, 'A1:I9');
  setRows(forecast, 'A1:A1', [['Fiscal 2025–2026 operating forecast']]);
  setRows(forecast, 'A2:A2', [['USD millions. OCF and capex ratios are held at FY24 levels.']]);
  setRows(forecast, 'A4:I4', [['Issuer', 'Fiscal year', 'Prior-year revenue', 'Revenue', 'Operating cash flow', 'Capital expenditures', 'Free cash flow', 'Operating income', 'FCF margin']]);
  setRows(forecast, 'A5:B8', [['Apple', 2025], ['Apple', 2026], ['Microsoft', 2025], ['Microsoft', 2026]]);
  forecast.getRange('C5:H8').setNumberFormat('#,##0.0;(#,##0.0);-');
  forecast.getRange('I5:I8').setNumberFormat('0.0%');

  const raw = wb.worksheets.getItem('Raw SEC');
  raw.showGridLines = false;
  raw.freezePanes.freezeRows(4);
  raw.getRange(`A1:O${excerpt.rows.length + 4}`).format.font = { name: 'Arial', size: 10, color: '#202A33' };
  raw.getRange('A1').values = [['SEC EDGAR companyfacts excerpt']];
  raw.getRange('A1').format.font = { name: 'Arial', size: 14, bold: true, color: '#1A3552' };
  raw.getRange('A2').values = [[excerpt.sources[0].url]];
  raw.getRange('A3').values = [[excerpt.sources[1].url]];
  raw.getRange('A4:O4').values = [['Record ID', 'Issuer', 'CIK', 'Metric', 'US-GAAP concept', 'Period start', 'Period end', 'Filed', 'Form', 'Accession', 'Fiscal year', 'Fiscal period', 'Frame', 'Unit', 'Reported value']];
  raw.getRange('A4:O4').format = { fill: '#173A5E', font: { name: 'Arial', size: 10, bold: true, color: '#FFFFFF' }, rowHeight: 30 };
  const rawMatrix = excerpt.rows.map(r => [r.id, r.issuer, String(r.cik).padStart(10, '0'), r.metric, r.concept, r.start, r.end, r.filed, r.form, r.accession, r.fy, r.fp, r.frame, r.unit, r.reported_value]);
  raw.getRange(`A5:O${rawMatrix.length + 4}`).values = rawMatrix;
  raw.tables.add(`A4:O${rawMatrix.length + 4}`, true, 'SecFactTable');
  raw.getRange(`C5:C${rawMatrix.length + 4}`).setNumberFormat('@');
  raw.getRange(`O5:O${rawMatrix.length + 4}`).setNumberFormat('#,##0;(#,##0);-');
  raw.getRange('A:A').format.columnWidth = 21;
  raw.getRange('B:C').format.columnWidth = 14;
  raw.getRange('D:D').format.columnWidth = 24;
  raw.getRange('E:E').format.columnWidth = 49;
  raw.getRange('F:I').format.columnWidth = 15;
  raw.getRange('J:J').format.columnWidth = 26;
  raw.getRange('K:N').format.columnWidth = 14;
  raw.getRange('O:O').format.columnWidth = 22;

  for (const [key, formula] of target) {
    const bang = key.lastIndexOf('!');
    const name = key.slice(0, bang), cell = key.slice(bang + 1);
    const range = wb.worksheets.getItem(name).getRange(cell);
    range.format = { fill: '#FFF0BE', font: { name: 'Arial', size: 10, color: '#087046' } };
    if (filled) range.formulas = [[formula]];
  }
  wb.recalculate();
  return wb;
}

await fs.mkdir(path.join(outDir, 'actor'), { recursive: true });
await fs.mkdir(path.join(outDir, 'private'), { recursive: true });
await fs.copyFile(path.join(here, 'ACTOR_TASK.md'), path.join(outDir, 'actor/task.md'));
for (const [filled, file] of [[false, 'actor/task.xlsx'], [true, 'private/positive.xlsx']]) {
  const wb = createWorkbook(filled);
  if (filled) {
    for (const [sheetName, range, slug] of [
      ['Committee View', 'A1:I8', 'committee'],
      ['FY Selection', 'A1:K9', 'selection'],
      ['Drivers', 'A1:F8', 'drivers'],
      ['Forecast', 'A1:I9', 'forecast'],
      ['Raw SEC', 'A1:O17', 'raw-sec'],
    ]) {
      const preview = await wb.render({ sheetName, range, scale: 1.25, format: 'png' });
      await fs.writeFile(path.join(outDir, `private/${slug}-preview.png`), new Uint8Array(await preview.arrayBuffer()));
    }
    const inspect = await wb.inspect({ kind: 'table', range: 'Committee View!A4:I6', include: 'values,formulas', tableMaxRows: 3, tableMaxCols: 9 });
    console.log(inspect.ndjson);
  }
  const output = await SpreadsheetFile.exportXlsx(wb);
  await output.save(path.join(outDir, file));
}
await fs.writeFile(path.join(outDir, 'private', 'target_cells.json'), JSON.stringify([...target.keys()].sort(), null, 2) + '\n');
await fs.rm(path.join(outDir, 'actor/task.xlsx.inspect.ndjson'), { force: true });
await fs.rm(path.join(outDir, 'private/positive.xlsx.inspect.ndjson'), { force: true });
console.log(`${variant}: ${excerpt.rows.length} SEC fact rows, ${target.size} target cells; output ${outDir}`);
