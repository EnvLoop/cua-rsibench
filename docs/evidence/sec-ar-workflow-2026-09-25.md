# An eighth Excel workflow: receivables and doubtful-account allowance

The [source receipt](sec-ar-sources-2026-09-25.json) freezes 37 exact USD facts from Pfizer, Oracle, and Amazon, each from a distinct **original** 10-K accession. Every compact [`sec_excel_factory/sources/ar`](../../sec_excel_factory/sources/ar) excerpt is extracted only after its complete companyfacts payload matches a separately recorded direct-SEC SHA-256. It preserves net receivables, separately reported doubtful-account allowance, selected annual revenue, operating cash flow, and current assets across two filing periods, with exact record concepts, dates, form, accession, fiscal label, unit, and amount. Issuers use their reported revenue tags; these are not silently standardized to a different concept. The origin is the [SEC companyfacts API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces).

The nine-sheet workbook infers **gross receivables = reported net receivables + reported allowance**, evaluates allowance rates and average-balance receivable days, and shows operating-cash-flow context. Cash flow is explicitly **not** treated as an actual customer-collections ledger. A separately marked synthetic reserve-rate and cash-realization scenario changes modeled net receivables and a cash-shortfall **proxy**, not the reported facts or an SEC credit-loss forecast. This calculation graph is distinct from the inventory/working-capital, RPO, debt maturity, EPS, lease maturity, tax-provision, and goodwill development workflows.

The [offline audit](sec-ar-offline-three-2026-09-25.json) covers three public development actor/reference workbooks with 49 checked formula targets and nine unmarked defects each. All references pass independent saved-OOXML numeric and no-regression scoring with two source/scenario perturbation replays; all unrepaired actors fail. Every defect is detectable in isolation. Tests reject a hardcoded receivable value and an unrelated source edit. A representative nine-tab workbook was rendered and visually checked.

These are **public development controls**. No Microsoft Excel for the web saved/downloaded readback, GUI positive/negative case, fresh-copy reset, hidden exam task, or official model score exists for them. Excel remains **0/100** individually admitted final items. The public development inventory has eight distinct workflow graphs; ten was the proposed floor before designing a new evaluator-held, issuer/template-isolated 20/20/100 split. Nothing public here can be retroactively counted as a sealed final task.

Rebuild and audit locally:

```bash
python3 sec_excel_factory/freeze_ar_sources.py \
  --raw-dir work/sec-expansion/public-proxy \
  --source-report docs/evidence/sec-source-expansion-16-2026-09-25.json \
  --out-dir sec_excel_factory/sources/ar \
  --report docs/evidence/sec-ar-sources-2026-09-25.json
python3 sec_excel_factory/prepare_ar_cases.py \
  --source-report docs/evidence/sec-ar-sources-2026-09-25.json \
  --private-out work/sec-expansion/ar-cases.json \
  --public-out docs/evidence/sec-ar-development-inventory-2026-09-25.json
node sec_excel_factory/build_ar_workbooks.mjs \
  work/sec-expansion/ar-cases.json work/sec-expansion/ar-workbooks
python3 sec_excel_factory/audit_ar_workflows.py \
  --cases work/sec-expansion/ar-cases.json \
  --workbooks work/sec-expansion/ar-workbooks \
  --public-out docs/evidence/sec-ar-offline-three-2026-09-25.json
python3 -m unittest discover -s sec_excel_factory -p test_ar_workflow.py -v
```
