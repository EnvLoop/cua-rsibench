# SEC Excel source-family expansion audit (2026-09-24)

## Measured result

The new [`candidate_issuers.json`](../../sec_excel_factory/candidate_issuers.json) contains **18 candidate issuers** spanning proposed retail, software, manufacturing, consumer, healthcare, media, and energy task shapes. Ticker, CIK, and SEC-conformed name came from the SEC's public [`company_tickers.json`](https://www.sec.gov/files/company_tickers.json), checked on 2026-09-24. These labels are *research hypotheses* for later workbook design; the ticker list does not prove that any candidate has the required facts or that a workbook is hard.

An offline audit of the **two already frozen** companyfacts snapshots found **2 eligible sources out of 2 inspected**: Apple and Microsoft. The other **16 candidates are pending snapshots**, not rejected. No additional companyfacts API request or Excel workbook was made in this pass. Both eligible snapshots are already used in the single existing five-sheet prototype, so the observed **new distinct workbook-family count is zero**. Even treating the original prototype as a family, this audit does not increase its family count beyond one.

| Issuer | FY2024 10-K accession | FY2023 / FY2024 end dates | Raw JSON SHA-256 | Same-end facts from other accessions | 2023–24 10-Q facts in required tags |
|---|---|---|---|---:|---:|
| Apple, CIK 320193 | `0000320193-24-000123` | 2023-09-30 / 2024-09-28 | `73a86c6aedc31f77cac2ea4df5f80f0b3bd7e6eb58bb4e01444fbedf3afb9c43` | 43 | 120 |
| Microsoft, CIK 789019 | `0000950170-24-087843` | 2023-06-30 / 2024-06-30 | `f8aae2965b20ad0df44bdf7ccbedf797d275b6b8dc030154a7a311361bb7246f` | 56 | 122 |

The exact record-level selected facts, source URLs, frozen-file SHA-256, and pending statuses are in [`candidate_audit.json`](../../sec_excel_factory/candidate_audit.json). The candidate-list SHA-256 in that audit is `6fe7bd4c582414d8006306d18e5113cc9f7b0138d4950c3e404421b523c41383`. The counts above are computed over SEC response records, including repeated comparative and quarterly contexts; they are indicators of source-selection difficulty, **not** a count of independent tasks or workbook families.

## Qualification rule and provenance

The [`qualify_candidates.py`](../../sec_excel_factory/qualify_candidates.py) script imports the prototype's seven exact US-GAAP concept IDs from `extract_sec.py`: revenue, operating income, operating cash flow, property/plant/equipment payments, assets, liabilities, and stockholders' equity. It requires all 14 USD values for FY2023 and FY2024 from **one original FY2024 Form 10-K accession**. Revenue and the other flows need 330–380-day durations and a common period start within each year; balance-sheet items must be instants at the exact corresponding fiscal year end. Form, accession, `fy`, `fp`, filed date, CIK, unit, and end date are checked. It rejects conflicting duplicate facts and a balance-sheet identity gap over USD 1.5 million. The cutoff for identifying a FY2024 original 10-K is a filing date no later than 2025-06-30. A candidate with a different revenue tag or nonstandard fiscal-year context remains outside this exact seven-tag prototype until a separately verified mapping is designed.

The SEC [documents companyfacts](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) as all standard XBRL company concepts in one JSON response and says the API needs no API key. The API covers entity-wide, non-custom taxonomy facts, which is useful for this bounded source gate but omits custom and segment-specific facts needed for richer company models. The SEC [fair-access guidance](https://www.sec.gov/about/developer-resources) limits automated access to at most 10 requests per second in aggregate and asks scripts to download only what is needed; its [FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions) asks for a declared User-Agent with a contact. The optional fetch mode therefore requires an explicitly configured organization/contact `SEC_USER_AGENT`, caps each run at 20 issuers, and waits at least 0.5 seconds between requests. There was no verified contact to use in this pass, so fetching was deliberately not run. For larger collection, the SEC recommends the nightly [companyfacts bulk ZIP](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) as the efficient route.

## Reproduce and extend

From the repository root, with no network:

```bash
python3 sec_excel_factory/qualify_candidates.py --output sec_excel_factory/candidate_audit.json
python3 -m unittest discover -s sec_excel_factory -p 'test_qualify_candidates.py' -v
```

The offline run returned `18` candidates, `2` audited, `2` eligible, `0` rejected, and `16` pending. Seven mutation tests passed on frozen SEC snapshots, including missing concept/unit, wrong CIK, omitted or conflicting accession fact, inconsistent annual start, and a broken accounting identity. That validates the filter's behavior on these inputs; it does not establish a high acceptance rate among uninspected issuers.

After a project owner supplies a genuine organization/contact User-Agent, a bounded online pass can be run with `SEC_USER_AGENT` set privately in the shell and `--fetch --max-fetch 16 --delay 1`. The script caches each raw response as gzip and records both decompressed JSON and snapshot-file hashes. If SEC denies access or throttles, stop or honor the response; do not interpret missing data as a financial-data rejection. For more than a few dozen issuers, use the SEC bulk archive and build a separate batch importer instead of repeated per-company requests.

## What remains for 100 distinct workbook families

1. Audit a materially larger, stratified set of issuers and filings. The current 18 are only a bounded candidate cohort and 16 have no source audit. Freeze each accepted source with CIK, accession, dates, URL, raw hash, and a reason-coded rejection log. The yield is unknown, so the needed candidate count cannot yet be inferred from 2/2.
2. Define and implement genuinely different workbook authoring specs using company-specific real disclosures: segments, inventory, debt maturities, deferred revenue, capex, acquisitions, or other relevant schedules. The seven common facts alone do not make 100 different business workflows. Record source-filing lineage and a structural family ID; multiple task perturbations of one base workbook count as one family.
3. Build an independent oracle and hidden perturbations for each spec, then admit every workbook through an untouched Microsoft Excel for the web round trip, a visible-UI solution, saved-artifact readback, no-regression checks, and clean per-attempt reset. None of those per-family gates was run here. Keep final-set source families isolated from training and public fixture solutions.

The current status is **a tested data-source qualifier plus two already-used eligible sources**, not a 100-family dataset or a 100-case Excel benchmark.
