# A third Excel calculation workflow: debt maturity and cash capacity

The [offline audit receipt](sec-debt-offline-five-2026-09-25.json) covers five public development workbooks from distinct original 10-K accessions: Pfizer, Costco, Walmart, Alphabet, and Salesforce. Their exact source records come from the 16 [hash-verified SEC filing excerpts](sec-source-expansion-rpo-2026-09-25.md). Each workbook has eight functional tabs, 33 checked formula targets, and eight unmarked defects. All five reference workbooks pass independent saved-OOXML scoring, non-target preservation, and two evaluator-side source/scenario perturbation replays. All five unsolved actor workbooks fail. Every injected defect is detectable when isolated. One full eight-tab reference was rendered and visually inspected.

This is a **different calculation graph** from the annual/Q4/working-capital and contract-liability/RPO workflows. It selects the reported current and noncurrent portions of long-term debt, cash, operating cash flow, capital expenditure, current assets, and current liabilities. It then calculates historical cash generation and coverage of the current long-term-debt portion. A separate synthetic scenario models the fraction refinanced, incremental annual rate, cash due, and illustrative post-maturity capacity. The two long-term-debt tags form a **tracked subset**, not total corporate debt: other short-term borrowings, leases, and untagged obligations may exist. Historical cash flow is a scenario capacity proxy, not a repayment forecast. The scenario inputs and inserted faults are benchmark-authored, not SEC disclosures or guidance.

The five authentic source families include different sectors and fiscal calendars. The original filing accessions and all source record IDs, concept names, period starts/ends, form, filed date, frame, and units are held in each workbook's `Source 10-K` and `Filing Map` sheets. The pinned excerpt files and [public candidate inventory](sec-debt-development-inventory-2026-09-25.json) provide the offline reproduction path. The [SEC companyfacts API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) is the attributed origin; the prior direct-SEC raw SHA-256 is rechecked by the independent oracle for every case.

These five examples are **public development controls only**. None has an observed Microsoft Excel for the web saved/downloaded readback, GUI positive/negative control, fresh-copy reset, hidden exam identity, or official model score. The workbook and verifier source is public. The Excel cell still has **0/100** individually admitted final items. There are now three distinct *development* workflow graphs, short of the proposed ten-workflow diversity target, and no public development case should be reclassified into a sealed final set.

Rebuild and verify locally with the bundled spreadsheet runtime:

```bash
python3 sec_excel_factory/prepare_debt_cases.py \
  --source-report docs/evidence/sec-source-expansion-16-2026-09-25.json \
  --private-out work/sec-expansion/debt-cases.json \
  --public-out docs/evidence/sec-debt-development-inventory-2026-09-25.json
node sec_excel_factory/build_debt_workbooks.mjs \
  work/sec-expansion/debt-cases.json work/sec-expansion/debt-workbooks
python3 sec_excel_factory/audit_debt_workflows.py \
  --cases work/sec-expansion/debt-cases.json \
  --workbooks work/sec-expansion/debt-workbooks \
  --public-out docs/evidence/sec-debt-offline-five-2026-09-25.json
python3 -m unittest discover -s sec_excel_factory -p test_debt_workflow.py -v
```
