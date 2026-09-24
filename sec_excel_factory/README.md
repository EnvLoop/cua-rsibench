# SEC Excel task prototype

This is one runnable **prototype**, not a validated Microsoft Excel for the web benchmark. It uses authentic public SEC XBRL facts to make a five-sheet financial review repair task. A ready-to-open actor package is in `fixtures/actor/`. The harness retains the SEC snapshots, the generated reference solution, and `verify_ooxml.py` outside the actor workspace.

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

The verifier parses saved `.xlsx` OOXML independently of the authoring tool. It checks all 84 target formulas against numbers recomputed from the frozen SEC JSON, cached values when present, unchanged non-target cell contents, sheet order, table identity/range, and sheet validation/structure. It then privately perturbs one real-source reference by $1 billion and one scenario input by 0.05 in its own evaluator to catch hardcodes and equal-value references to the wrong filing. The supplied tests show a positive base and holdout, source tampering rejection, hardcode rejection, and rejection of an equal-value wrong-filing reference.

## Rights and boundaries

The [SEC EDGAR API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) says companyfacts data are public and require no API key. The [SEC webmaster FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions) says government-created content and public EDGAR filing content are free to access and reuse. Automated refreshes must respect the SEC’s [rate-control and fair-access guidance](https://www.sec.gov/filergroup/announcements-old/new-rate-control-limits); this prototype makes no runtime SEC requests after the source files are frozen. Those statements do not imply the SEC endorses this benchmark. Preserve attribution and recheck the live sources for any production reuse.

The OOXML evaluator supports direct A1 references, arithmetic, and parentheses. It does not yet accept valid but more elaborate Excel formulas such as `SUMIFS` or `XLOOKUP`, or check chart/drawing fidelity. Its no-regression comparison normalizes Excel's equivalent shared-string encodings and numeric spellings that decode to the same IEEE-754 value; substantive source edits still fail.

## Blind Q4 bridge audit prototype

[`build_bridge_audit.py`](build_bridge_audit.py) creates a separate six-sheet development task from the same pinned source snapshots. It has 177 authentic filing records, 114 initially populated formulas, and nine undisclosed injected faults. The actor must diagnose causal mistakes across annual fact selection, nine-month-to-full-year Q4 reconciliation, forecast drivers, and a board view. The independent [`verify_bridge_audit.py`](verify_bridge_audit.py) scores the saved OOXML workbook against freshly recomputed SEC values, rejects edits outside the faulted formulas, and runs two private replays that perturb all 36 canonical filing facts plus two scenario inputs. It reports isolated partial credit in ninths while preserving a strict full-pass check. It is a harder task *shape*, but not a new issuer source family or a hidden final case because its generator is public.

```bash
python3 build_bridge_audit.py output/bridge_audit
python3 verify_bridge_audit.py output/bridge_audit/private/reference.xlsx output/bridge_audit/actor/task.xlsx output/bridge_audit/private/reference.xlsx
python3 -m unittest discover -s . -p 'test_bridge_audit.py' -v
```

The full evidence and admission limits are in [`docs/evidence/sec-bridge-audit-prototype-2026-09-24.md`](../docs/evidence/sec-bridge-audit-prototype-2026-09-24.md). Generated workbooks are intentionally ignored. The full task has not been solved or qualified in a visible Excel-web GUI.

On 2026-09-24, a copy was uploaded into a dedicated test account in actual Microsoft Excel for the web. All five sheets opened in editing mode. One cross-sheet target formula was entered through the GUI, saved, reloaded, and downloaded. Independent OOXML readback found that target correct and no non-target semantic cell changes, and a private source perturbation changed its computed result. This qualifies the single edit and readback path only: **83 target formulas remain blank**, the full task is unscored, and per-attempt cloud reset is untested. The redacted receipt is [`docs/evidence/v0.6-sec-excel-web-smoke.json`](../docs/evidence/v0.6-sec-excel-web-smoke.json). No Office account, credentials, paid data provider, or tenant data are included here.
