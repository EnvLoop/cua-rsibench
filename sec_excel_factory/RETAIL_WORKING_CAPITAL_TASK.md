# Retail inventory and payables audit

You are reviewing a retailer working-capital workbook before an investment committee uses it. The `Raw SEC` sheet contains genuine SEC companyfacts observations for Costco and Walmart, including original and later filings, quarterly observations, different fiscal calendars, and issuer-specific US-GAAP cost-of-sales tags.

Find and repair formula errors in `History`, `Year Delta`, `Scenario`, and `Review`. The workbook does not mark the faulty cells. Keep all source observations, scenario inputs, labels, sheet structure, and already-correct formulas unchanged.

Use the original FY2024 Form 10-K for FY2023 and FY2024 revenue, cost of sales, closing inventory, and closing trade payables. Use the original FY2023 Form 10-K comparative figures for FY2022 opening inventory and payables. A filing with the same numeric value but the wrong accession is still the wrong source link. Match issuer, metric/concept, USD unit, period, form, and accession.

`DIO` is average inventory divided by fiscal-year cost of sales times the actual inclusive fiscal-year day count. `DPO` uses average trade payables in the numerator. The modeled stress changes FY2024 **ending** inventory and ending payables; recompute the averages and downstream outputs. Positive incremental cash tied equals stressed ending inventory less stressed ending payables minus the unstressed difference. `DPO` here is a trade-payables proxy, not a published issuer KPI or a full cash-conversion-cycle measure.

Finish by saving the workbook. The evaluator reads back the saved `.xlsx`, checks the intended formulas and outputs under additional undisclosed source and scenario changes, and rejects unrelated workbook modifications.
