# A sixth Excel workflow: tax provision, cash taxes, and deferred assets

The [source receipt](sec-tax-sources-2026-09-25.json) freezes 51 exact USD tax records from three issuer-distinct original 10-K accessions: Alphabet, Salesforce, and Meta. Each compact [`sec_excel_factory/sources/tax`](../../sec_excel_factory/sources/tax) excerpt is bound to a prior direct-SEC companyfacts SHA-256 and preserves the filing accession, form, fiscal label, period, US-GAAP concept, unit, reported value, and source record identity. Current and prior-year facts come from the **same pinned original filing**, with later comparative filings excluded. The attributed primary feed is the [SEC companyfacts API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces).

The nine-sheet development workbook examines **current plus deferred tax expense** against reported total tax provision, accrual expense against cash taxes paid, and the change in net deferred-tax assets across two balance-sheet dates. It calculates reported and prior effective tax rates without assuming that cash taxes, current accrual expense, and deferred-asset movement share one accounting basis. Its separate synthetic pre-tax-income and effective-rate stress is an illustrative model, not a filing prediction, SEC guidance, or tax advice. This source and calculation graph differs from annual/Q4/working-capital, RPO, debt maturity, EPS/shareholder returns, and lease maturity workflows.

The [offline audit](sec-tax-offline-three-2026-09-25.json) covers three **public development** actor/reference workbooks, each with 46 checked formula targets and nine unmarked defects. All three references pass the independent saved-OOXML oracle, non-target semantic preservation, and two source/scenario counterfactual replays. All three unrepaired seeds fail. Every defect is detectable when isolated; tests reject a hardcoded tax amount and collateral source edit. A representative nine-tab workbook was rendered and visually inspected.

No original Microsoft Excel for the web saved/downloaded readback, GUI positive/negative control, fresh-copy reset, hidden exam item, or official model score exists for these cases. The Excel cell remains **0/100** final items admitted. The public development inventory now has six distinct workflow graphs, below the proposed ten-workflow floor. Its published source facts and builder cannot be retroactively sealed as a hidden final exam.

Reproduce the offline development controls:

```bash
python3 sec_excel_factory/freeze_tax_sources.py \
  --raw-dir work/sec-expansion/public-proxy \
  --source-report docs/evidence/sec-source-expansion-16-2026-09-25.json \
  --out-dir sec_excel_factory/sources/tax \
  --report docs/evidence/sec-tax-sources-2026-09-25.json
python3 sec_excel_factory/prepare_tax_cases.py \
  --source-report docs/evidence/sec-tax-sources-2026-09-25.json \
  --private-out work/sec-expansion/tax-cases.json \
  --public-out docs/evidence/sec-tax-development-inventory-2026-09-25.json
node sec_excel_factory/build_tax_workbooks.mjs \
  work/sec-expansion/tax-cases.json work/sec-expansion/tax-workbooks
python3 sec_excel_factory/audit_tax_workflows.py \
  --cases work/sec-expansion/tax-cases.json \
  --workbooks work/sec-expansion/tax-workbooks \
  --public-out docs/evidence/sec-tax-offline-three-2026-09-25.json
python3 -m unittest discover -s sec_excel_factory -p test_tax_workflow.py -v
```
