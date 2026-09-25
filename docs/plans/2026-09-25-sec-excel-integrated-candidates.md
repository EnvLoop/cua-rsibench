# Filing-pinned integrated Excel candidates

This design advances the original Microsoft Excel for the web cell. It does not
admit a final task or replace an Excel-web save/download/readback test.

## Source and split

Use the two hash-pinned SEC companyfacts snapshots already in the repository.
Enumerate only original annual 10-K and corresponding third-quarter 10-Q
accessions with unambiguous US-GAAP USD facts. Copy the actual filing accession,
form, filed date, period start/end, concept, unit, value, and source record ID
into each workbook. Keep comparative entries from those same filings as authentic
period-selection distractors. No generated fault or scenario input is described
as an SEC fact. Bound every candidate to an explicit accession pair. Split by
accession pair and fiscal year before assignment; reject accession overlap
across train, selection, and final candidate pools. The same issuer can recur
across pools, so this is not an entity-disjoint or sealed hidden exam.

## Workbooks and actor task

The final-candidate template has ten functional tabs: Review, FY Selection,
Q3 Selection, Q4 Bridge, Working Capital, Scenario, Audit, Annual 10-K,
Q3 10-Q, and Source Map. The first seven form a dependency graph from raw facts
through quarter reconstruction, working-capital metrics, and a modeled stress.
The final three retain filing provenance and authentic distractors. Train and
selection use narrower, visibly different calculation graphs. Each candidate
contains several interacting formula faults, including wrong filing period,
quarter versus year-to-date, sign, and source reference errors. The actor must
repair the saved workbook using the real Excel GUI, without being given the
reference solution. Scenario amounts are synthetic and labeled as such.

## Oracle and gate

An independent OOXML verifier reads the downloaded saved workbook, recomputes
numeric targets from frozen source records and scenario values, checks the
non-target semantic cells and structural invariants, and replays source and
scenario perturbations to reject hardcodes and equal-value wrong links. The
per-task positive, negative, no-regression, reset, and downloaded readback
receipts must be recorded before a candidate is admitted. Public counts must
remain candidate counts until those controls and a sealed, non-exposed source
corpus exist. Source snapshot refresh is a separate, rate-limited operation.

The initial pool is limited by only two local full companyfacts snapshots.
Attempts to refresh the other audited issuers were unsuccessful because the
SEC host could not complete TLS from this environment. Thus this pool must
not be described as 100 independent filing families or a publishable hidden
exam, even if 100 candidate workbook variants are generated.
