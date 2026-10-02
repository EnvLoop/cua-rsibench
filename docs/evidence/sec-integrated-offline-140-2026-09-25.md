# SEC filing-close Excel candidate pool: offline 20/20/100 audit

The [machine-readable receipt](sec-integrated-offline-140-2026-09-25.json) records an **offline candidate build**, not an admitted or hidden Microsoft Excel for the web benchmark. The builder produced 20 training candidates, 20 selection candidates, and 100 proposed final candidates as individual actor/reference `.xlsx` pairs in ignored evaluator-owned `work/`. All 140 reference workbooks passed the independent OOXML numeric and no-regression oracle with two source/scenario counterfactual replays. All 140 unfixed actor workbooks were rejected. Each contains 6–9 unmarked, isolated-detectable formula faults. The final candidate workbooks have ten functional worksheets, 48 checked formula targets, 28–29 authentic annual-source rows and 32–33 authentic third-quarter-source rows, plus synthetic stress assumptions labeled as such. A sample final workbook was rendered and visually inspected across all ten sheets.

The facts come from the repository's SHA-256-pinned Apple and Microsoft [SEC companyfacts API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) snapshots. Each source row retains its CIK, US-GAAP concept, unit, reported value, period start/end, filing form, accession, fiscal year/period, frame, and filed date. The train workbook exposes the original 10-K rows; the selection and final workbooks also expose the corresponding Q3 10-Q rows. Annual/YTD canonical selection is strict; comparatives and quarter-only disclosures from those same filings remain authentic distractors. The train, selection, and final candidate splits have **zero accession overlap**. That does not imply entity or fact-value isolation: Apple and Microsoft recur in every split, and comparative values can be re-reported in another filing. The SEC says public EDGAR filing content is [free to access and reuse](https://www.sec.gov/about/webmaster-frequently-asked-questions); the stress values and inserted errors are authored for this benchmark and carry no SEC endorsement.

| Candidate split | Workbooks | Filing pairs | Issuers | Calculation templates | Distinct fault sets | Target formulas each |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Train | 20 | 4 | 2 | 1 | 20 | 25 |
| Selection | 20 | 4 | 2 | 1 | 20 | 33 |
| Proposed final | 100 | 7 | 2 | 1 | 39 | 48 |

The three splits have different sheet sets and dependency graphs, but only **one authored template within the proposed final set**. The 100 final files therefore represent scenario/fault variants of seven filing pairs, not 100 independent source or task-template families. The source snapshots and related 2024 formula-repair prototypes are public; this set is not a sealed hidden exam. The candidate identity and artifact commitments in the receipts establish integrity only. They are not secrecy claims. **Individually GUI-admitted final: 0/100; official final attempts: 0.** No Excel-web cloud copy, saved/downloaded readback, positive/negative GUI control, or fresh-copy reset was performed for this pool. The prior narrow SEC Excel-web controls involved other development workbooks and cannot be transferred to these cases.

The initial offline source expansion attempted the 18 previously audited issuer API endpoints at no more than 1.33 requests per second using a public organization contact in the SEC User-Agent. All attempts produced `URLError`; a single `curl` check failed during TLS negotiation with the SEC host. That initial build accepted no new snapshot. The existing two frozen source snapshots remained sufficient to test the factory but not to support a publication-grade 100-case final exam.

Later [hash-verified SEC source expansion](sec-source-expansion-rpo-2026-09-25.md) froze 16 new public filing excerpts and built a separate contract-obligations development workflow. It does not change this integrated pool's seven final filing pairs, two issuers, one final template, or zero GUI-admitted finals.

For a discriminating official Excel cell, freeze a **new private** source corpus before model training. A concrete minimum design is 20 final issuer/filing families with at most five cases per family, plus four issuer families each for the 20 training and 20 selection tasks, with zero issuer and accession overlap across the three sets. This requires at least 28 distinct issuers under the five-case cap. Author at least ten structurally different final workflows—e.g. quarter reconstruction, working-capital stress, debt maturity, deferred-revenue rollforward, segment margin, capex-to-cash, allowance reconciliation, FX translation, inventory reserve, and covenant sensitivity—with at most ten final cases per workflow. Train and selection should have their own nonidentical workflow-template families. These thresholds are a proposed preregistration rule to avoid pseudoreplication, not an empirically validated sufficiency theorem. An independent reviewer should inspect source/template similarity and case difficulty before the final set is frozen.

Each of those 100 replacement final items must then pass the real Excel-web admission gate on an isolated fresh document: untouched open/save/reload/download baseline, task-specific known-positive GUI repair, a partial or wrong-answer negative, a collateral-edit negative, independent downloaded OOXML scoring, scenario/source perturbation, same-file reset, and fresh-copy reset. The evaluator must keep source variants, task identities, gold workbooks, and score feedback outside the actor and public release. A saved formula, offline oracle pass, or local renderer preview is not proof of Excel-web execution.

Rebuild and re-audit the development pool locally with the bundled `@oai/artifact-tool` runtime:

```bash
python3 sec_excel_factory/prepare_integrated_cases.py \
  --private-out work/sec-integrated/cases.json \
  --public-out docs/evidence/sec-integrated-candidate-inventory-2026-09-25.json
node sec_excel_factory/build_integrated_workbooks.mjs \
  work/sec-integrated/cases.json work/sec-integrated/workbooks 140
python3 sec_excel_factory/audit_integrated_cases.py \
  --cases work/sec-integrated/cases.json \
  --workbooks work/sec-integrated/workbooks \
  --public-out docs/evidence/sec-integrated-offline-140-2026-09-25.json
python3 -m unittest discover -s sec_excel_factory -p test_integrated_candidates.py -v
```

The exact generated `.xlsx` bytes can vary with exporter ZIP metadata; the public commitment uses normalized saved-OOXML semantics and stable private-oracle/task text. Freeze and separately record the exact actor baseline bytes for each later Excel-web admission attempt. The publicly committed generator and oracle are development methods, not a hidden acceptance key.
