# Research evidence update

Continue the authorized PDF and visualization using the existing design. Preserve
the frozen v2 engine and report completed, failed, and pending evaluations separately.

The report adds the actual data-search protocol, candidate trajectories, final
selection, held-out execution results, and a failure audit. The explorer adds one
section with researcher and metric selectors, per-attempt training counts, and
clickable hypotheses. A missing score is never plotted as zero.

Alternative designs considered: a flat table is easy to audit but hides the gap
between valid actions and task success; a separate dashboard adds navigation with
little benefit. Extend the existing page with both a small plot and source table.

Validate against raw training manifests and Harbor results, check selection
precedence and source disjointness, inspect rendered PDF pages, test interactive
controls on desktop/mobile, then publish and verify fetched artifacts. Report the
observer repair separately because the original campaigns use a frozen runtime.
