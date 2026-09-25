# Original WDI PowerPoint-web candidate source

This package generates an **offline candidate source**, not admitted Microsoft PowerPoint-for-the-web tasks or model scores. The source observations are the repository's pinned 2019–2024 World Development Indicators snapshot (35 countries, five indicators, 1,050 numeric observations). The seven-slide analyst briefs, committee rules, review instructions, and deliberate defects are EnvLoop-authored simulations. The WDI data are attributed in the slides and notes under CC BY 4.0.

The private seed assigns five entire country families to training, five to selection, and 25 to final candidates. Each family has four separate task files: 20/20/100 candidates in total. Ten final workflows exercise distinct failures: a stale GDP denominator; aggregate versus per-capita growth; wrong CPI comparison year; one-year versus five-year labor change; wrong population base year; population growth substituted for per-capita growth; stale labor data in a price–labor spread; an OR watch rule treated as a minimum; a 2023 CPI observation cited as 2024 across the deck and source footnote; and swapped native chart legend labels with matching wrong embedded-workbook headers. Training requires one edit, selection requires three dependent edits, and final tasks require four corrections across the relevant slides. Native chart values and the WDI evidence table remain unchanged in scoring. The presentation finalizer materializes each literal chart's data as an embedded workbook and checks the chart relationship before the candidate source is frozen.

Run from the repository root, using the bundled workspace Node.js and Artifact Tool runtime:

```bash
python3 -m ppt_wdi_factory.plan \
  --private-root work/ppt-wdi-original \
  --align-country-map /private/path/to/native-desktop/private-map.json \
  --public-receipt docs/evidence/ppt-wdi-original-offline-inventory-2026-09-25.json
python3 -m ppt_wdi_factory.build --private-root work/ppt-wdi-original
python3 -m ppt_wdi_factory.verify --private-root work/ppt-wdi-original
python3 -m ppt_wdi_factory.summarize \
  --private-root work/ppt-wdi-original \
  --align-country-map /private/path/to/native-desktop/private-map.json \
  --public-receipt docs/evidence/ppt-wdi-original-offline-inventory-2026-09-25.json
```

The ignored `work/` tree holds the secret seed, country split, exact tasks, target answers, decks, per-ID source hashes, frozen oracles, and direct-OOXML controls. Do not publish it before evaluation. Aligning with the private original-desktop WDI map keeps a desktop training country out of the PPT final partition. The checked-in receipt reports aggregate counts and commitments only. `verify.py` recomputes the numeric answer from the rounded WDI values visible on the slide, checks the source table and native chart against the embedded workbook, freezes exact target locations, accepts all four corrected targets only when every other package part is preserved, and rejects partial, collateral, chart-value, and chart/workbook legend-desynchronization edits. A malformed or unavailable package is an infrastructure error, not a model failure.

These direct-file controls do not establish that PowerPoint for the web can open, edit, save, or download the decks. For **each** final ID, a separate dedicated-account gate still needs a fresh isolated OneDrive copy; untouched save/reload/download and normalized-baseline freeze; a visible-GUI known-positive edit; partial, wrong-series, and collateral negatives; saved-file artifact readback; same-file restoration; and a new fresh-copy reset. Original source rights and Office chart/table edit compatibility also need a visible pilot. The public final exam remains at zero tasks until those receipts and the common pre-campaign matrix pass. Treat the four tasks from one country as a cluster when reporting uncertainty.
