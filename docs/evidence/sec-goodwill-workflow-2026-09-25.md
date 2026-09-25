# A seventh Excel workflow: goodwill and intangible carrying values

The [source receipt](sec-goodwill-sources-2026-09-25.json) freezes 41 exact USD facts from three distinct original Form 10-K accessions: Pfizer, NVIDIA, and Meta. Each compact [`sec_excel_factory/sources/goodwill`](../../sec_excel_factory/sources/goodwill) excerpt is generated only after the full companyfacts payload matches a separately recorded direct-SEC SHA-256. It preserves the original accession, fiscal period, form, filed date, US-GAAP concept, unit, period dates, reported amount, and source record ID. Opening and closing balances come from two periods **within the same original filing**. The attributed primary feed is the [SEC companyfacts API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces).

The nine-sheet workbook examines the change in goodwill against the reported amount acquired during the year, the movement in non-goodwill intangible carrying value against amortization, and combined intangible assets as a share of total assets. The residual goodwill and intangible movements are labeled as **unexplained residuals**: they do not uniquely identify acquisition value, FX translation, disposals, or impairment. A separate synthetic goodwill write-down and extra-amortization case illustrates carrying-value sensitivity while explicitly ignoring tax and full impairment accounting. The calculation graph differs from Q4/working capital, RPO, debt maturity, EPS/shareholder returns, lease maturity, and tax provision.

The [offline receipt](sec-goodwill-offline-three-2026-09-25.json) covers three public development actor/reference pairs. Each has 45 checked formulas and nine unmarked defects. All three reference files pass an independent saved-OOXML oracle, non-target preservation, and two source/scenario perturbation replays; all three unrepaired actors fail. Every injected defect is individually detectable. Tests reject hardcoded goodwill and collateral source edits. A representative nine-tab workbook was rendered and visually inspected.

No original Microsoft Excel for the web save/download readback, GUI positive/negative control, fresh-copy reset, hidden final item, or official model score exists for these cases. Excel remains at **0/100** individually admitted final tasks. The public development inventory now contains seven distinct workflow graphs, short of the proposed ten-workflow floor; these publicly released sources and formula faults cannot later be called a sealed final exam.

Rebuild the offline controls:

```bash
python3 sec_excel_factory/freeze_goodwill_sources.py \
  --raw-dir work/sec-expansion/public-proxy \
  --source-report docs/evidence/sec-source-expansion-16-2026-09-25.json \
  --out-dir sec_excel_factory/sources/goodwill \
  --report docs/evidence/sec-goodwill-sources-2026-09-25.json
python3 sec_excel_factory/prepare_goodwill_cases.py \
  --source-report docs/evidence/sec-goodwill-sources-2026-09-25.json \
  --private-out work/sec-expansion/goodwill-cases.json \
  --public-out docs/evidence/sec-goodwill-development-inventory-2026-09-25.json
node sec_excel_factory/build_goodwill_workbooks.mjs \
  work/sec-expansion/goodwill-cases.json work/sec-expansion/goodwill-workbooks
python3 sec_excel_factory/audit_goodwill_workflows.py \
  --cases work/sec-expansion/goodwill-cases.json \
  --workbooks work/sec-expansion/goodwill-workbooks \
  --public-out docs/evidence/sec-goodwill-offline-three-2026-09-25.json
python3 -m unittest discover -s sec_excel_factory -p test_goodwill_workflow.py -v
```
