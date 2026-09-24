# Fiscal-year review repair

Open `task.xlsx` in Microsoft Excel for the web. Fill the 84 pale-yellow, empty formula cells across `FY Selection`, `Drivers`, `Forecast`, and `Committee View`. Save the workbook. Keep the `Raw SEC` table and every non-yellow cell unchanged.

The `Raw SEC` sheet contains public SEC companyfacts records. It deliberately mixes issuer fiscal calendars, 10-K and 10-Q facts, later comparative filings, annual and quarterly durations, and USD, USD/share, and share units. For each issuer, FY2023 and FY2024, select the **USD** fact from that issuer's **FY2024 Form 10-K**, with the exact fiscal period end shown on `FY Selection`. Apple’s accession is `0000320193-24-000123`; Microsoft’s is `0000950170-24-087843`. Annual revenue, operating income, operating cash flow, and capital expenditures must cover a full fiscal year; assets, liabilities, and equity are end-date balances. Put selected values in **USD millions**. The balance check is assets minus liabilities minus equity.

In `Drivers`, calculate FY2025 revenue growth as FY2024 revenue divided by FY2023 revenue minus one. Use FY2024 operating cash flow divided by revenue and FY2024 capital expenditures divided by revenue. Set FY2026 revenue growth to half the FY2025 rate. Keep the existing capex scenario multipliers unchanged; they are illustrative assumptions rather than SEC facts.

In `Forecast`, use prior-year revenue and the matching issuer's growth driver to calculate FY2025 and FY2026 revenue. Apply the cash-flow and capex ratios to each forecast year's revenue, and apply the scenario multiplier to capex. Free cash flow is operating cash flow minus capex. Hold operating margin at FY2024 actuals. Calculate free-cash-flow margin from each forecast year.

In `Committee View`, link FY2024 revenue, free cash flow, revenue growth and operating margin, plus FY2026 revenue, free cash flow and free-cash-flow margin. Bring across the FY2024 balance check. Use formulas so every result responds if a source fact or scenario input changes.
