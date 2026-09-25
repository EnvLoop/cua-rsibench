# SEC Excel task prototype

This directory contains runnable **development prototypes**, not an admitted 100-task Microsoft Excel for the web benchmark. The checked-in five-sheet fixture uses authentic public SEC XBRL facts; its ready-to-open actor package is in `fixtures/actor/`. Two additional development task shapes are described below. The harness retains SEC snapshots, generated reference solutions, and independent verifier code outside the actor workspace.

The newer [filing-close integrated candidate pool](../docs/evidence/sec-integrated-offline-140-2026-09-25.md) builds 20/20/100 **offline** train/selection/proposed-final workbook pairs from these same pinned Apple/Microsoft SEC snapshots. Its final template has ten tabs and 48 independent numeric targets; the 100 final files still repeat seven source filing pairs, two issuer entities, and one calculation template. Every reference passes the local OOXML/counterfactual oracle and every unsolved seed fails, but **zero of the 100 is a hidden or Excel-web GUI-admitted final task**. `prepare_integrated_cases.py`, `build_integrated_workbooks.mjs`, `verify_integrated_candidate.py`, and `audit_integrated_cases.py` provide the reproducible development pipeline. Keep generated actor/reference files and private case manifests in ignored `work/`.

A separate [source expansion and contract-obligations workflow](../docs/evidence/sec-source-expansion-rpo-2026-09-25.md) freezes compact public original 10-K filing excerpts with report periods ending in calendar 2024 for 16 more issuers, each byte-bound to the prior direct-SEC source audit. Home Depot's source is fiscal **2023** ending January 28, 2024; fiscal labels are preserved as reported. Four eight-sheet RPO/deferred-revenue development cases use Alphabet, Oracle, NVIDIA, and Disney filings and a different dependency graph. They pass local independent OOXML and perturbation controls, but also have **zero Excel-web GUI admissions**. The public excerpts are development material; a future hidden final set needs evaluator-held, non-exposed source and template families.

The checked-in fixture is a transparent development example. Its source records and verifier logic are public, so this exact task must never be counted as a hidden official final instance. Future final tasks need distinct source families and evaluator-only perturbations that are frozen outside the actor and public release.

## What is real and what is modeled

- `sources/raw/apple-companyfacts.json.gz` and `sources/raw/microsoft-companyfacts.json.gz` are frozen compressed copies of JSON downloaded on 2026-09-24 from the [Apple companyfacts API](https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json) and [Microsoft companyfacts API](https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json). Decompressed SHA-256 values are `73a86c6aedc31f77cac2ea4df5f80f0b3bd7e6eb58bb4e01444fbedf3afb9c43` and `f8aae2965b20ad0df44bdf7ccbedf797d275b6b8dc030154a7a311361bb7246f`. The extraction script checks them before doing any work.
- The fixture draws from [Apple’s FY2024 10-K](https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm) and [Microsoft’s FY2024 10-K](https://www.sec.gov/Archives/edgar/data/789019/000095017024087843/msft-20240630.htm), plus authentic 10-Q and comparative records in the same API responses. It has 132 source rows, two issuers with different fiscal year ends, FY2023/FY2024 actuals, two future modeled years, mixed units, and 84 missing formulas. Each source row keeps CIK, concept, period start/end, form, accession, filed date, fiscal year/period, frame, unit, and reported value.
- The FY2025–2026 model is a deliberately simplified **illustrative forecast**; it is not a company filing, investment valuation, or financial advice. The editable capex multiplier is synthetic. The holdout task changes that multiplier while preserving SEC facts.

The selection policy is exact and deterministic: match issuer, concept, USD unit, the issuer-specific FY2023/FY2024 end date, annual duration for flow facts (instant for balance-sheet facts), 10-K form, and the issuer’s FY2024 accession. This avoids silently choosing the newest comparative or a quarterly/YTD amount. `extract_sec.py` preserves conflicting candidate periods and different unit types as real distractors; it does not invent restatements.

## Build and verify

Use the bundled Node runtime and `@oai/artifact-tool` package found by Codex `load_workspace_dependencies`. Create a local `node_modules` symlink to that runtime in this directory. A standard `node` installation also works if `@oai/artifact-tool` is available.

```bash
python3 extract_sec.py
node build_workbooks.mjs output base
python3 verify_ooxml.py output/private/positive.xlsx output/actor/task.xlsx
python3 -m unittest discover -s . -p 'test_*.py' -v
```

`node build_workbooks.mjs output holdout` creates a second, independently scored task with a changed scenario input. Only give an actor that variant's `output/actor` directory. Do not give it `output/private`, `sources/raw`, `sources/excerpt.json`, or verifier code. A real benchmark runner should create per-attempt isolated copies, reset from the actor seed, and keep its acceptance split/configuration on the evaluator side.

The verifier parses saved `.xlsx` OOXML independently of the authoring tool. It checks all 84 target formulas against numbers recomputed from the frozen SEC JSON, cached values when present, unchanged non-target cell contents, sheet order, table identity/range, and sheet validation/structure. Its evaluator-side tests perturb one real-source reference by $1 billion and one scenario input by 0.05 to catch hardcodes and equal-value references to the wrong filing. These development perturbations are in public code, not sealed final tests. The supplied tests show a positive base and holdout, source tampering rejection, hardcode rejection, and rejection of an equal-value wrong-filing reference.

## Rights and boundaries

The [SEC EDGAR API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) says companyfacts data are public and require no API key. The [SEC webmaster FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions) says government-created content and public EDGAR filing content are free to access and reuse. Automated refreshes must respect the SEC’s [rate-control and fair-access guidance](https://www.sec.gov/filergroup/announcements-old/new-rate-control-limits); this prototype makes no runtime SEC requests after the source files are frozen. Those statements do not imply the SEC endorses this benchmark. Preserve attribution and recheck the live sources for any production reuse.

The OOXML evaluator supports direct A1 references, arithmetic, and parentheses. It does not yet accept valid but more elaborate Excel formulas such as `SUMIFS` or `XLOOKUP`, or check chart/drawing fidelity. Its no-regression comparison normalizes Excel's equivalent shared-string encodings and numeric spellings that decode to the same IEEE-754 value; substantive source edits still fail.

## Blind Q4 bridge audit prototype

[`build_bridge_audit.py`](build_bridge_audit.py) creates a separate six-sheet development task from the same pinned source snapshots. It has 177 authentic filing records, 114 initially populated formulas, and nine fault locations undisclosed to the actor. The actor must diagnose causal mistakes across annual fact selection, nine-month-to-full-year Q4 reconciliation, forecast drivers, and a board view. The independent [`verify_bridge_audit.py`](verify_bridge_audit.py) scores the saved OOXML workbook against freshly recomputed SEC values, rejects edits outside the faulted formulas, and runs two public-code evaluator-side replays that perturb all 36 canonical filing facts plus two scenario inputs. It reports isolated partial credit in ninths while preserving a strict full-pass check. It is a harder task *shape*, but not a new issuer source family or a hidden final case because its generator is public.

```bash
python3 build_bridge_audit.py output/bridge_audit
python3 verify_bridge_audit.py output/bridge_audit/private/reference.xlsx output/bridge_audit/actor/task.xlsx output/bridge_audit/private/reference.xlsx
python3 -m unittest discover -s . -p 'test_bridge_audit.py' -v
```

The full evidence and admission limits are in [`docs/evidence/sec-bridge-audit-prototype-2026-09-24.md`](../docs/evidence/sec-bridge-audit-prototype-2026-09-24.md). Generated workbooks are intentionally ignored. A complete human positive control later passed in visible Excel web; that does not establish a student score or clean reset.

## Retail working-capital audit prototype

[`extract_retail_sec.py`](extract_retail_sec.py) freezes a small authentic Costco/Walmart excerpt from hash-pinned full SEC downloads. The full responses stay in ignored `work/`; the [public excerpt](sources/retail_excerpt.json) preserves the 112 annual and quarterly records used in the task and source provenance. [`build_retail_working_capital.py`](build_retail_working_capital.py) constructs a five-sheet audit with 92 populated formulas and nine unmarked defects. It tests original-filing provenance, different retail cost-of-sales concepts, a 53-week Costco fiscal year, opening/closing inventory and payables, average-balance days metrics, and a modeled ending-balance stress. It is a genuinely different workflow and issuer cohort from the Apple/Microsoft forecast audit, but still only one public development case.

The separate [`verify_retail_working_capital.py`](verify_retail_working_capital.py) reads saved OOXML, recomputes all targets from the hash-pinned excerpt, rejects unrelated changes, and runs two public-code evaluator-side source/scenario replays. Eight targeted tests cover a full positive, unsolved negative, one-repair partial credit, same-number wrong filing, hardcode, source tampering, regression, deterministic build, and source-hash provenance. See the [task brief](RETAIL_WORKING_CAPITAL_TASK.md) and [evidence note](../docs/evidence/sec-retail-working-capital-prototype-2026-09-24.md). The real Excel-web GUI has now produced partial, full, and manual reset controls on one cloud file; a fresh independent model attempt and automated reset remain unverified.

## Original five-sheet fixture: Excel web smoke

On 2026-09-24, a copy of the original five-sheet fixture was uploaded into a dedicated test account in actual Microsoft Excel for the web. All five sheets opened in editing mode. One cross-sheet target formula was entered through the GUI, saved, reloaded, and downloaded. Independent OOXML readback found that target correct and no non-target semantic cell changes, and an evaluator-side source perturbation changed its computed result. This qualifies the single edit and readback path only: **83 target formulas remain blank**, the full task is unscored, and per-attempt cloud reset is untested. The redacted receipt is [`docs/evidence/v0.6-sec-excel-web-smoke.json`](../docs/evidence/v0.6-sec-excel-web-smoke.json). No Office account, credentials, paid data provider, or tenant data are included here.
