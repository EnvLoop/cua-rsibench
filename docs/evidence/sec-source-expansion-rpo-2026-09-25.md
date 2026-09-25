# SEC source expansion and a distinct contract-obligations workflow

The [source-expansion receipt](sec-source-expansion-16-2026-09-25.json) pins **16 additional issuer families and 16 distinct original FY2024 Form 10-K accessions**, with 589 exact public US-GAAP USD fact records in [`sec_excel_factory/sources/expansion`](../../sec_excel_factory/sources/expansion). Together with the previously pinned Apple and Microsoft snapshots, the development source inventory now covers 18 issuer families. The 16 compact excerpts are source material, not 16 GUI-admitted workbooks or hidden final items. Twelve had failed the earlier *specific seven-tag* FY2024 source screen; that rejection did not make their other SEC disclosures inauthentic, and this expansion does not reclassify them as eligible for the old workflow.

The local shell could not complete TLS to SEC hosts. A bounded read-only text proxy retrieved public [SEC companyfacts JSON](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) at no more than one request per second. The proxy was treated as untrusted transport: stripping its single extra trailing newline reproduces **byte-for-byte** the two repository snapshots previously fetched directly from SEC for Apple and Microsoft. Every one of the 16 new raw responses also matches its independently recorded direct-SEC SHA-256 in the prior pinned [`candidate_audit_fetched_2026-09-24.json`](../../sec_excel_factory/candidate_audit_fetched_2026-09-24.json). All 56 Costco and 56 Walmart records in the older pinned retail excerpt match the corresponding current raw records exactly. The compact excerpts preserve CIK, accession, filed date, form, period start/end, fiscal fields, frame, concept, unit, and reported value; each excerpt and its originating raw JSON have published hashes. The intermediary is an acquisition route, not the cited source or a claim of SEC endorsement.

Two non-proxy official filing views supply an additional cross-check. [Alphabet's 2024 10-K](https://www.sec.gov/Archives/edgar/data/1652044/000165204425000014/goog-20241231.htm) states $93.2 billion in remaining performance obligations, $6.0 billion of closing deferred revenue, and $3.9 billion recognized from the opening balance; its balance sheet reports $5.036 billion current deferred revenue. Oracle's [original 2024 10-K filing index](https://www.sec.gov/Archives/edgar/data/1341439/000095017024075605/0000950170-24-075605-index.html) binds the accession and filing date, and the SEC's [deferred-revenue disclosure table](https://www.sec.gov/Archives/edgar/data/1341439/000095017024075605/R35.htm) reports $9.313 billion current, $1.233 billion noncurrent, and $10.546 billion total. Those amounts match the frozen records. The [SEC webmaster FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions) states that public EDGAR filing content is free to access and reuse. Benchmark-authored faults and scenarios are clearly separate from SEC facts.

The [RPO offline receipt](sec-rpo-offline-four-2026-09-25.json) and [inventory](sec-rpo-development-inventory-2026-09-25.json) describe a **genuinely different eight-sheet calculation workflow** from the earlier 10-tab annual/Q4/working-capital audit. It examines contract-liability current/noncurrent classification, opening-liability revenue recognition, a liability residual explicitly *not* called billings, remaining-performance-obligation timing under editable synthetic assumptions, and balance-sheet coverage without treating RPO as cash. Real issuer disclosures differ: Alphabet lacks a separately tagged noncurrent component in this accession, while Disney lacks a separately tagged total. The workbook derives only those missing classifications from the other reported components. It never invents a filing fact.

Four public development cases use distinct original 10-K accessions from Alphabet, Oracle, NVIDIA, and Disney. The builder produced actor/reference workbooks with 43 checked formulas and nine unmarked, individually detectable faults per case. All four references passed the independent saved-OOXML oracle, non-target preservation check, and two source/scenario counterfactual replays; all four unrepaired actors failed. A representative eight-sheet workbook was rendered and visually reviewed. These are **public development controls only**: no original Excel-for-the-web saved/downloaded readback, GUI positive/negative control, fresh-copy reset, hidden final item, or official model score exists for them.

The 16 new excerpts and the four RPO tasks increase real-source and workflow diversity, but they do **not** satisfy the full-study Excel admission gate. The existing 100 proposed final workbook variants still repeat seven filing pairs, two issuers, and one template; they have **0/100** individually admitted final cases. A publication-grade hidden set needs new evaluator-held source families and workflow templates frozen before researcher access, followed by task-by-task Excel-web GUI and independent downloaded-artifact verification. These public excerpts are suitable as development or training material, not as a sealed final exam.

Rebuild the public source excerpts and the four offline cases from verified local raw snapshots:

```bash
python3 sec_excel_factory/freeze_sec_expansion.py \
  --raw-dir work/sec-expansion/public-proxy \
  --out-dir sec_excel_factory/sources/expansion \
  --report docs/evidence/sec-source-expansion-16-2026-09-25.json
python3 sec_excel_factory/prepare_rpo_cases.py \
  --source-report docs/evidence/sec-source-expansion-16-2026-09-25.json \
  --private-out work/sec-expansion/rpo-cases.json \
  --public-out docs/evidence/sec-rpo-development-inventory-2026-09-25.json
node sec_excel_factory/build_rpo_workbooks.mjs \
  work/sec-expansion/rpo-cases.json work/sec-expansion/rpo-workbooks
python3 sec_excel_factory/audit_rpo_workflows.py \
  --cases work/sec-expansion/rpo-cases.json \
  --workbooks work/sec-expansion/rpo-workbooks \
  --public-out docs/evidence/sec-rpo-offline-four-2026-09-25.json
python3 -m unittest discover -s sec_excel_factory -p test_sec_expansion_rpo.py -v
```

The full raw companyfacts snapshots remain outside Git; `fetch_public_sec_mirror.py` retrieves them only when the two known official payloads and each issuer's prior direct-SEC SHA-256 still match. If SEC updates a companyfacts response, that fetch deliberately fails until a fresh independent official-source audit produces a new pin.
