# A fifth Excel workflow: operating-lease maturity audit

The [source receipt](sec-lease-sources-2026-09-25.json) pins 87 exact SEC facts in **USD** and dimensionless discount-rate units from four distinct original 10-K accessions: Coca-Cola, Alphabet, Walmart, and Oracle. Each compact [`sec_excel_factory/sources/lease`](../../sec_excel_factory/sources/lease) excerpt is extracted only after the full companyfacts payload matches a separately recorded direct-SEC SHA-256. It keeps the original filing accession, form, filed date, fiscal label, period start/end, frame, unit, value, and source hash. The source is the [SEC companyfacts API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces), not a benchmark-authored number.

This workflow uses a **six-bucket operating-lease payment schedule**: next twelve months, years two through five, and after year five. Its nine-sheet workbook selects the reported cash payments, lease cost, current/noncurrent lease liabilities, right-of-use asset, weighted-average discount rate, and operating cash flow. It reconciles the six buckets to the reported undiscounted total, calculates the reported liability subtotal, and compares next-year obligations with historical cash activity. The difference between undiscounted payments and reported lease liability is labeled as an **arithmetic gap**, not an independently reported imputed-interest fact. A separate synthetic payment-reduction and escalation stress illustrates a scenario while leaving the contractual source disclosures unchanged; it is not a lease renegotiation or SEC guidance. This calculation graph is structurally different from Q4/working-capital, RPO, debt maturity, and EPS/shareholder-return workflows.

The [offline audit](sec-lease-offline-four-2026-09-25.json) covers four public development actor/reference workbook pairs. Each has 52 independently checked formula targets and nine unmarked defects. All four reference workbooks pass the saved-OOXML oracle, non-target preservation check, and two source/scenario counterfactual replays; all four unrepaired seeds fail. Every defect is individually detectable when isolated. Tests reject a hardcoded next-year payment and a collateral source edit. A representative nine-sheet workbook was rendered and visually inspected.

These are **public development controls**. None has a Microsoft Excel for the web saved/downloaded readback, GUI positive/negative control, fresh-copy reset, hidden exam identity, or official model score. The Excel cell remains **0/100** final items admitted. Five distinct development workflow graphs now exist, below the proposed ten-workflow diversity target; these public source families and formulas cannot themselves constitute a sealed hidden final set.

Rebuild and check with the bundled spreadsheet runtime:

```bash
python3 sec_excel_factory/freeze_lease_sources.py \
  --raw-dir work/sec-expansion/public-proxy \
  --source-report docs/evidence/sec-source-expansion-16-2026-09-25.json \
  --out-dir sec_excel_factory/sources/lease \
  --report docs/evidence/sec-lease-sources-2026-09-25.json
python3 sec_excel_factory/prepare_lease_cases.py \
  --source-report docs/evidence/sec-lease-sources-2026-09-25.json \
  --private-out work/sec-expansion/lease-cases.json \
  --public-out docs/evidence/sec-lease-development-inventory-2026-09-25.json
node sec_excel_factory/build_lease_workbooks.mjs \
  work/sec-expansion/lease-cases.json work/sec-expansion/lease-workbooks
python3 sec_excel_factory/audit_lease_workflows.py \
  --cases work/sec-expansion/lease-cases.json \
  --workbooks work/sec-expansion/lease-workbooks \
  --public-out docs/evidence/sec-lease-offline-four-2026-09-25.json
python3 -m unittest discover -s sec_excel_factory -p test_lease_workflow.py -v
```
