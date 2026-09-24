# Blind fiscal-year model audit

Open `task.xlsx` in Microsoft Excel for the web. A board analyst has received a six-sheet FY2024 actuals and FY2025–2026 scenario model. Some formulas are wrong, but the affected cells and number of errors are not disclosed. Audit the full model, repair the causal formulas, and save it. Preserve all filing records, assumptions, labels, tables, and formulas that were already correct.

The `Raw SEC` sheet contains authentic, frozen SEC companyfacts records. Treat each issuer's fiscal year separately. The FY2023 and FY2024 annual facts in `Historical` must come from the issuer's original FY2024 Form 10-K, using USD values, the exact year-end shown, and a full-year period for flow metrics. Balance-sheet facts are point-in-time. Convert USD to USD millions. Apple uses accession `0000320193-24-000123`; Microsoft uses `0000950170-24-087843`.

In `Q4 Bridge`, the nine-month year-to-date facts must come from each issuer's original FY2024 third-quarter Form 10-Q, not the three-month quarter or a later comparative. Apple's nine-month period is 2023-10-01 through 2024-06-29, accession `0000320193-24-000081`; Microsoft's is 2023-07-01 through 2024-03-31, accession `0000950170-24-048288`. The implied fourth quarter is the full fiscal year minus the first nine months. Free cash flow is operating cash flow minus capital expenditures.

`Drivers`, `Forecast`, and `Board Review` should update when underlying facts or the capex scenario multiplier change. FY2025 revenue growth repeats FY2024 growth; FY2026 growth is half that rate. Hold FY2024 cash-flow, capex, and operating-income ratios constant in the forecast. The capex multiplier is a modeled assumption, not an SEC fact. Treat FY2025–2026 outputs as an illustrative scenario, not company guidance.

There are same-value later comparative filings, different fiscal calendars, year-to-date and quarter-only observations, mixed units, and interdependent forecast formulas. A visually plausible number may still link to the wrong filing. No code, hidden fault list, reference workbook, or evaluation perturbations are supplied to the actor.
