# A ninth Excel workflow: cash-flow quality and reinvestment

The [source receipt](sec-cashquality-sources-2026-09-25.json) freezes 90 exact USD facts from Meta, Salesforce, Costco, Coca-Cola, and Netflix, each from a distinct **original** 10-K accession. Each compact [`sec_excel_factory/sources/cashquality`](../../sec_excel_factory/sources/cashquality) excerpt is extracted after its full companyfacts payload matches a separately recorded direct-SEC SHA-256. The selected current and comparative annual facts are net income, operating cash flow, depreciation and amortization, share-based compensation, capital expenditures, and common-stock repurchases. Every row preserves its concept, original period, accession, filing date, fiscal label, unit, and value. The source is the [SEC companyfacts API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces).

This nine-sheet workbook compares net income to operating cash flow, makes the two selected noncash adjustments explicit, and leaves their difference as an **unexplained residual**. That residual is not labeled as a single reported adjustment. It also computes free cash flow, capital intensity, repurchase coverage, year-over-year changes, and a separate synthetic capex and working-capital cash stress. The stress is neither a filing fact nor an SEC forecast. This calculation graph differs from the previous receivables, goodwill, tax, lease, EPS, debt, RPO, and integrated-close development workflows.

The [offline audit](sec-cashquality-offline-five-2026-09-25.json) covers five public development actor/reference pairs with 48 checked formula targets and nine unmarked defects per case. All five references pass independent saved-OOXML numeric and no-regression scoring with two source/scenario counterfactual replays; all five unrepaired actors fail. Every injected defect is individually detectable. Tests reject a hardcoded filing value and an unrelated source edit. The nine tabs of a representative case were rendered and visually checked.

These are **public development controls**, with zero Microsoft Excel for the web saved/downloaded readbacks, GUI positive/negative cases, fresh-copy resets, hidden final tasks, or model scores. Excel remains **0/100** individually admitted final items. The public development inventory has nine distinct workflow graphs. The planned evaluator-held 20/20/100 split must be built from source-issuer and semantic-template families isolated from all public development examples; these five cases cannot be retroactively counted as hidden finals.

Rebuild and audit locally:

```bash
python3 sec_excel_factory/freeze_cashquality_sources.py \
  --raw-dir work/sec-expansion/public-proxy \
  --source-report docs/evidence/sec-source-expansion-16-2026-09-25.json \
  --out-dir sec_excel_factory/sources/cashquality \
  --report docs/evidence/sec-cashquality-sources-2026-09-25.json
python3 sec_excel_factory/prepare_cashquality_cases.py \
  --source-report docs/evidence/sec-cashquality-sources-2026-09-25.json \
  --private-out work/sec-expansion/cashquality-cases.json \
  --public-out docs/evidence/sec-cashquality-development-inventory-2026-09-25.json
node sec_excel_factory/build_cashquality_workbooks.mjs \
  work/sec-expansion/cashquality-cases.json work/sec-expansion/cashquality-workbooks
python3 sec_excel_factory/audit_cashquality_workflows.py \
  --cases work/sec-expansion/cashquality-cases.json \
  --workbooks work/sec-expansion/cashquality-workbooks \
  --public-out docs/evidence/sec-cashquality-offline-five-2026-09-25.json
python3 -m unittest discover -s sec_excel_factory -p test_cashquality_workflow.py -v
```
