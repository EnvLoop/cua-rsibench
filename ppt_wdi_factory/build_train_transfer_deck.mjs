// Build a separate seven-slide, editable train-only transfer template.
// Run a copy of this module from a private build directory with linked runtime
// node_modules. Inputs and output decks contain evaluator-private train data.
import fs from "node:fs/promises";
import path from "node:path";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const inputPath = process.argv[2];
const outputPath = process.argv[3];
if (!inputPath || !outputPath) throw new Error("Usage: build_train_transfer_deck.mjs TASK_JSON OUTPUT_PPTX");
const task = JSON.parse(await fs.readFile(inputPath, "utf8"));
if (task.schema !== "ppt-wdi-original-candidates-v1") throw new Error("Bad task schema");
if (task.split !== "train_policy_development" ||
    task.development_source_split !== "train" ||
    task.analogue_role !== "additional_train_only_after_private_control_admission" ||
    task.source_scope !== "private_wdi_country_csv_reserve_v1" ||
    task.presentation_template !== "ppt_wdi_factory/build_train_transfer_deck.mjs" ||
    task.rights_tier !== "wdi_cc_by_4_0_facts_plus_authored_simulation") {
  throw new Error("Only independently sourced transfer-training specs are accepted");
}
const snapshotDate = task.source_snapshot_date ?? "2026-09-25";
if (!/^\d{4}-\d{2}-\d{2}$/.test(snapshotDate)) throw new Error("Bad WDI snapshot date");
const countryCsv = true;
if (countryCsv && !/^\d{4}-\d{2}-\d{2}$/.test(task.source_csv_data_last_updated ?? "")) {
  throw new Error("Bad World Bank country CSV data-update date");
}

const W = 1280, H = 720;
// A separate visual template prevents a template-byte shortcut to the final
// decks while retaining the same causal targets and native OOXML objects.
const colors = { ink: "#173B35", blue: "#385F80", teal: "#286F5E", muted: "#5C6D65", amber: "#865A2B" };
const font = "Arial";
const pres = Presentation.create({ slideSize: { width: W, height: H } });

function text(slide, name, value, x, y, w, h, size = 22, bold = false, color = colors.ink) {
  const shape = slide.shapes.add({
    geometry: "textbox", name, position: { left: x, top: y, width: w, height: h },
    fill: "none", line: { fill: "none", width: 0 },
  });
  shape.text = value;
  shape.text.style = { typeface: font, fontSize: size, bold, color, autoFit: "none" };
  return shape;
}
function slideBase(title, n, note) {
  const s = pres.slides.add();
  s.background.fill = "#FFFFFF";
  text(s, `slide_${n}_title`, title, 64, 45, 1150, 72, 34, true, colors.ink);
  text(s, `slide_${n}_footer`, `Training evidence review  •  ${task.country_name}  •  ${n}/7`, 66, 654, 1130, 32, 13, false, colors.muted);
  s.speakerNotes.textFrame.setText(note);
  return s;
}
const pinnedSource = countryCsv
  ? `pinned country CSV download ${snapshotDate} (data updated ${task.source_csv_data_last_updated})`
  : `pinned API snapshot ${snapshotDate}`;
const sourceNote = `Source: World Bank, World Development Indicators, ${pinnedSource}, 2019–2024, CC BY 4.0. The monitoring brief, draft defects, and committee rules are EnvLoop-authored simulations, not World Bank conclusions.`;
const s1 = slideBase(`${task.country_name} | evidence review`, 1, sourceNote);
text(s1, "brief_heading", task.heading, 72, 159, 1134, 75, 25, false, colors.muted);
text(s1, "target__summary", task.draft.summary, 76, 276, 1110, 92, 32, true, colors.amber);
const targetLabels = { summary: "summary", ledger: "calculation", interpretation: "interpretation",
  decision: "committee decision", attribution: "source footnote",
  legend_cpi: "blue chart legend", legend_unemployment: "teal chart legend",
  chart_caption: "chart caption" };
text(s1, "brief_method", `Reconcile the flagged ${task.target_keys.map(key => targetLabels[key]).join(", ")} with the pinned evidence. Preserve all other content.`, 76, 422, 1080, 105, 23, false, colors.ink);

const s2 = slideBase("WDI source observations", 2, sourceNote);
text(s2, "evidence_intro", "WDI observations rounded for this brief. Compute from the displayed values; rate differences use percentage points.", 66, 126, 1150, 66, 19, false, colors.muted);
const header = ["Year", "GDP, USD bn", "GDP/person, USD", "CPI, %", "Population, m", "Unemployment, %"];
const vals = [header];
for (const year of ["2019", "2020", "2021", "2022", "2023", "2024"]) {
  const row = task.facts[year];
  vals.push([year,
    (row["NY.GDP.MKTP.CD"] / 1e9).toFixed(1),
    row["NY.GDP.PCAP.CD"].toFixed(0),
    row["FP.CPI.TOTL.ZG"].toFixed(2),
    (row["SP.POP.TOTL"] / 1e6).toFixed(2),
    row["SL.UEM.TOTL.ZS"].toFixed(2)]);
}
const evidence = s2.tables.add({ rows: 7, columns: 6, left: 61, top: 210, width: 1156, height: 365, values: vals });
evidence.styleOptions = { headerRow: true, bandedRows: true };
evidence.borders.assign({ style: "solid", fill: "#DBE6EA", width: 1 });
for (let c = 0; c < 6; c++) evidence.getCell(0, c).fill = "#E3EEF2";
for (let r = 0; r < 7; r++) for (let c = 0; c < 6; c++) {
  evidence.getCell(r, c).text.style = { typeface: font, fontSize: 16, color: colors.ink };
}
text(s2, "source_attribution", `World Development Indicators  •  pinned ${countryCsv ? "country CSV" : "snapshot"} ${snapshotDate}  •  CC BY 4.0`, 66, 595, 1120, 32, 14, false, colors.muted);

const s3 = slideBase("Indicator trend, 2019–2024", 3, sourceNote);
text(s3, "chart_unit", `${task.calculation.series}  |  ${task.chart.unit}`, 70, 122, 1100, 42, 20, false, colors.muted);
const observedChartValues = task.chart.series.flatMap(series => series.values.map(Number));
if (!observedChartValues.length || observedChartValues.some(value => !Number.isFinite(value))) {
  throw new Error("Chart source values must be finite WDI observations");
}
const chartLow = Math.min(...observedChartValues);
const chartHigh = Math.max(...observedChartValues);
const chartPadding = Math.max(0.2, (chartHigh - chartLow) * 0.12);
const axisFloor = chartLow < 0 ? chartLow - chartPadding : 0;
const axisCeiling = Math.max(0, chartHigh + chartPadding);
const rawAxisStep = Math.max(Number.EPSILON, (axisCeiling - axisFloor) / 5);
const axisMagnitude = 10 ** Math.floor(Math.log10(rawAxisStep));
const axisStep = [1, 2, 5, 10].find(step => step * axisMagnitude >= rawAxisStep) * axisMagnitude;
const axisMin = Math.floor(axisFloor / axisStep) * axisStep;
const axisMax = Math.ceil(axisCeiling / axisStep) * axisStep;
const chart = s3.charts.add("line", {
  position: { left: 83, top: 175, width: 1090, height: 425 },
  categories: task.chart.categories,
  series: task.chart.series.map((r, i) => ({
    name: r.name, values: r.values,
    line: { style: "solid", fill: i === 0 ? colors.blue : colors.teal, width: 3 },
    marker: { symbol: "circle", size: 5 },
  })),
  lineOptions: { smooth: false },
  hasLegend: task.chart.series.length > 1,
  legend: { position: "bottom", overlay: false, textStyle: { typeface: font, fontSize: 15, fill: colors.ink } },
  xAxis: { textStyle: { typeface: font, fontSize: 15, fill: colors.muted } },
  yAxis: { min: axisMin, max: axisMax, majorUnit: axisStep,
           textStyle: { typeface: font, fontSize: 15, fill: colors.muted },
           majorGridlines: { style: "solid", fill: "#DAE4E8", width: 1 } },
});
text(s3, "chart_attribution", task.draft.chart_caption ?? "Chart data: the same rounded WDI observations shown on slide 2.", 70, 605, 1090, 33, 14, false,
     task.target_keys.includes("chart_caption") ? colors.amber : colors.muted);

const s4 = slideBase("Calculation review", 4, sourceNote);
text(s4, "calculation_rule", `Review rule: ${task.calculation.rule}`, 72, 140, 1105, 72, 23, false, colors.ink);
const review = s4.tables.add({ rows: 3, columns: 3, left: 72, top: 253, width: 1128, height: 236,
  values: [["Field", "Analyst draft", "Use"],
           [task.workflow === "source_year_reconciliation" ? "Source observation" : "Derived measure",
            task.draft.ledger, task.calculation.window],
           ["Unit and rule", task.calculation.unit, `Simulated threshold: ${task.calculation.simulated_threshold.toFixed(1)}`]] });
review.styleOptions = { headerRow: true };
review.borders.assign({ style: "solid", fill: "#D6E2E6", width: 1 });
for (let c = 0; c < 3; c++) review.getCell(0, c).fill = "#E3EEF2";
for (let r = 0; r < 3; r++) for (let c = 0; c < 3; c++) {
  review.getCell(r, c).text.style = { typeface: font, fontSize: 17, color: colors.ink };
}
text(s4, "review_note", "The value in the analyst-draft row must follow the source years, indicator and unit; preserve the underlying WDI extract.", 73, 521, 1110, 82, 19, false, colors.muted);

const s5 = slideBase("Analyst interpretation", 5, sourceNote);
text(s5, "interpretation_prompt", task.target_keys.includes("interpretation")
     ? "Check whether the analyst's carried-forward explanation matches the evidence and the calculation rule."
     : "This method note is already approved; preserve it when correcting the flagged fields.",
     74, 140, 1080, 72, 22, false, colors.muted);
text(s5, "target__interpretation", task.draft.interpretation, 75, 280, 1085, 165, 27, true,
     task.target_keys.includes("interpretation") ? colors.amber : colors.ink);
text(s5, "interpretation_caveat", "A difference of rates is in percentage points. A percent growth rate uses a ratio to its specified base year.", 74, 524, 1100, 70, 19, false, colors.ink);

const s6 = slideBase("Committee decision", 6, sourceNote);
text(s6, "decision_prompt", "Apply the stated simulated threshold to the corrected measure; the rule is an analyst exercise, not a WDI policy recommendation.", 74, 148, 1090, 91, 22, false, colors.muted);
text(s6, "target__decision", task.draft.decision, 74, 295, 1100, 140, 28, true,
     task.target_keys.includes("decision") ? colors.amber : colors.ink);
text(s6, "decision_scope", task.target_keys.includes("decision")
     ? "Only the decision derived from the corrected measure should change. Preserve the evidence, year window and method note."
     : "The committee decision is already approved; preserve it while correcting the flagged fields.",
     74, 530, 1090, 70, 19, false, colors.ink);

const s7 = slideBase("Method and attribution", 7, sourceNote);
text(s7, "method_1", `Observed values: World Development Indicators, 2019–2024 ${countryCsv ? "country CSV extract" : "API snapshot"}. The table contains the five pinned series for this country.`, 75, 150, 1090, 90, 23, false, colors.ink);
text(s7, "method_2", "Calculations: derive from the displayed, rounded WDI values; round results to two decimals for the committee memo.", 75, 283, 1090, 86, 23, false, colors.ink);
text(s7, "method_3", "Scenario: the committee threshold and the intentional draft errors are EnvLoop-authored benchmark fiction.", 75, 417, 1090, 86, 23, false, colors.ink);
text(s7, "target__attribution", task.draft.attribution, 75, 552, 1090, 62, 16, false,
     task.target_keys.includes("attribution") ? colors.amber : colors.muted);

await fs.mkdir(path.dirname(outputPath), { recursive: true });
await (await PresentationFile.exportPptx(pres)).save(outputPath);
console.log(JSON.stringify({ output: outputPath, slides: 7, nativeTables: 2, nativeCharts: 1 }));
