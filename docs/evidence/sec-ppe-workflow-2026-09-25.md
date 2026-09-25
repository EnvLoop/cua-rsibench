# A tenth Excel workflow: property, plant and equipment carrying values

The [source receipt](sec-ppe-sources-2026-09-25.json) freezes 72 exact USD facts from Costco, Netflix, Pfizer, Boeing, and Caterpillar, each from a distinct **original** 10-K accession. Each compact [`sec_excel_factory/sources/ppe`](../../sec_excel_factory/sources/ppe) excerpt is extracted after the full companyfacts payload matches a separately recorded direct-SEC SHA-256. The two-period source facts cover reported gross PPE, accumulated depreciation, net PPE, total assets, capital expenditures, and depreciation/depletion/amortization. Every row retains its exact concept, period, accession, filing date, fiscal label, unit, and value. The source is the [SEC companyfacts API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces).

The nine-sheet task recomputes gross less accumulated PPE, compares it to separately reported net PPE, tracks year-over-year changes, and contrasts net PPE movement with current capex less reported D&A. Any difference stays an **unexplained residual**. Reported D&A may include non-PPE assets, so the residual is not attributed to disposals, acquisitions, foreign exchange, or impairment. A separate synthetic write-down and maintenance-capex increase shows sensitivity; it is neither booked by the issuer nor an SEC forecast. This dependency graph differs from the nine earlier public development workflows.

The [offline audit](sec-ppe-offline-five-2026-09-25.json) covers five public development actor/reference pairs with 55 checked formula targets and nine unmarked defects per case. All five references pass independent saved-OOXML numeric and no-regression scoring with two source/scenario counterfactual replays; all five unrepaired actors fail. Every injected defect is individually detectable. Tests reject a hardcoded filing value and an unrelated source edit. The nine tabs of a representative case were rendered and visually checked.

These are **public development controls**. No Microsoft Excel for the web saved/downloaded readback, GUI positive/negative case, fresh-copy reset, hidden final task, or official model score exists for them. Excel remains **0/100** individually admitted final items. The ten public workflow graphs establish development diversity only. A future evaluator-held 20/20/100 split must still isolate issuer and semantic-template families from all these public examples; none can be relabeled as hidden final after public release.

Rebuild and audit locally:

```bash
python3 sec_excel_factory/freeze_ppe_sources.py \
  --raw-dir work/sec-expansion/public-proxy \
  --source-report docs/evidence/sec-source-expansion-16-2026-09-25.json \
  --out-dir sec_excel_factory/sources/ppe \
  --report docs/evidence/sec-ppe-sources-2026-09-25.json
python3 sec_excel_factory/prepare_ppe_cases.py \
  --source-report docs/evidence/sec-ppe-sources-2026-09-25.json \
  --private-out work/sec-expansion/ppe-cases.json \
  --public-out docs/evidence/sec-ppe-development-inventory-2026-09-25.json
node sec_excel_factory/build_ppe_workbooks.mjs \
  work/sec-expansion/ppe-cases.json work/sec-expansion/ppe-workbooks
python3 sec_excel_factory/audit_ppe_workflows.py \
  --cases work/sec-expansion/ppe-cases.json \
  --workbooks work/sec-expansion/ppe-workbooks \
  --public-out docs/evidence/sec-ppe-offline-five-2026-09-25.json
python3 -m unittest discover -s sec_excel_factory -p test_ppe_workflow.py -v
```
