# A fourth Excel workflow: EPS dilution and shareholder returns

The [mixed-unit source receipt](sec-eps-sources-2026-09-25.json) freezes 84 exact facts from four distinct original 10-K accessions: Alphabet, NVIDIA, Meta, and Coca-Cola. The source units are **USD**, **shares**, and **USD/shares**, each preserved from hash-pinned [SEC companyfacts](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) responses previously fetched directly. The compact public source files are in [`sec_excel_factory/sources/eps`](../../sec_excel_factory/sources/eps). Annual net income, basic and diluted weighted-average shares, reported basic and diluted EPS, cash repurchases, and dividends are all selected from the same exact filing and period rather than mixed across later comparatives. The original source filing pages and raw hashes are bound in each excerpt.

The [offline audit](sec-eps-offline-four-2026-09-25.json) covers four **public development** actor/reference workbook pairs. Each has eight functional tabs, 50 independently checked formula targets, and nine unmarked defects. The dependency graph selects mixed-unit facts for two fiscal years; computes share dilution, reported-versus-simple EPS differences, cash returns, and payout ratios; and evaluates an explicitly synthetic share-repurchase case. The synthetic share price and deployed fraction are neither market observations nor SEC guidance. It does not force reported EPS to equal net income divided by weighted-average shares: numerator definitions and rounding can produce a residual. A representative eight-tab workbook was rendered and visually inspected.

All four reference workbooks pass the saved-OOXML oracle, non-target semantic preservation, and two source/scenario counterfactual replays; all four unrepaired actor workbooks fail. Each injected fault is individually detectable when isolated. Tests reject a hardcoded reported EPS and collateral source edits. These results are **offline task-construction controls**, not Microsoft Excel for the web execution or a model score. No original-software saved/downloaded readback, GUI negative control, fresh-copy reset, or hidden final admission has occurred for these files. The Excel cell remains **0/100** admitted final tasks, and the development inventory now has four distinct workflow graphs, below the proposed ten-workflow diversity target.

Rebuild and validate locally with the bundled spreadsheet runtime:

```bash
python3 sec_excel_factory/freeze_eps_sources.py \
  --raw-dir work/sec-expansion/public-proxy \
  --source-report docs/evidence/sec-source-expansion-16-2026-09-25.json \
  --out-dir sec_excel_factory/sources/eps \
  --report docs/evidence/sec-eps-sources-2026-09-25.json
python3 sec_excel_factory/prepare_eps_cases.py \
  --source-report docs/evidence/sec-eps-sources-2026-09-25.json \
  --private-out work/sec-expansion/eps-cases.json \
  --public-out docs/evidence/sec-eps-development-inventory-2026-09-25.json
node sec_excel_factory/build_eps_workbooks.mjs \
  work/sec-expansion/eps-cases.json work/sec-expansion/eps-workbooks
python3 sec_excel_factory/audit_eps_workflows.py \
  --cases work/sec-expansion/eps-cases.json \
  --workbooks work/sec-expansion/eps-workbooks \
  --public-out docs/evidence/sec-eps-offline-four-2026-09-25.json
python3 -m unittest discover -s sec_excel_factory -p test_eps_workflow.py -v
```
