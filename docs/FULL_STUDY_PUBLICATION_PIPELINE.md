# English full-study paper gate

This pipeline prepares a PDF and vector figures **only after** the complete
real 4 x 6 benchmark is audited. It does not produce a full-result paper from
offline candidates, development GUI controls, a partial campaign, or a
synthetic test fixture. At the time this gate was added, official final
outcomes and the 24-campaign index were absent.

Run the existing [result audit](FULL_STUDY_RESULTS_AUDIT.md) first. Then supply
all six independent inputs to `tools/build_full_study_report_v1.py`:

1. the original matrix manifest and complete final execution index;
2. the exact audited summary from `tools/audit_full_study_results_v1.py`;
3. a hash-bound final-attempt telemetry index; and
4. a hash-bound 24-campaign candidate/selection trajectory index; and
5. a hash-bound six-cell independent release-review index.

The builder rebuilds the matrix from its referenced qualification receipts,
re-runs the 24-campaign / 600-identity / 3,000-slot result audit with the
preregistered 10,000-draw, seed-23 paired bootstrap, compares the supplied
summary with the recomputed result, and rejects any other study ID. It then
checks every telemetry row, campaign trajectory, and review reference. A failure leaves no report
directory. The CLI has no synthetic or partial-result option.

## Per-attempt telemetry contract

The historical v1 final receipts are unchanged. The separate
`cua-full-study-final-attempt-telemetry-index-v1` object has `study_id`,
`matrix_plan_sha256`, `execution_index_sha256`, and `executions`. There is one
entry for **every unique checkpoint execution** in the result index, not one
entry for each reused comparison slot:

```json
{
  "schema": "cua-full-study-final-attempt-telemetry-index-v1",
  "study_id": "full-computer-use-v1",
  "matrix_plan_sha256": "<64 lowercase hex characters>",
  "execution_index_sha256": "<64 lowercase hex characters>",
  "executions": [
    {
      "cell_id": "powerpoint-web",
      "owner_slot": "shared-base",
      "receipt": {"path": "telemetry/ppt-base.json", "sha256": "<64 lowercase hex characters>"}
    }
  ]
}
```

Each referenced `cua-full-study-execution-telemetry-v1` receipt binds the
original final-execution receipt SHA-256, its `cell_id` and `owner_slot`, and
exactly 100 tasks. Every task contains exactly the attempt IDs from that
execution receipt. Each attempt requires:

```json
{
  "attempt_id": "initial",
  "attempt_receipt_sha256": "<original attempt receipt SHA-256>",
  "timeout_subtype": "none",
  "action_count": 37,
  "wall_time_ms": 72842,
  "provider_latency_ms": 52210,
  "telemetry_trace_sha256": "<raw timing/action event trace SHA-256>",
  "retry_provenance": null
}
```

Permitted timeout subtypes are `none`, `provider`, `transport`,
`environment`, `verifier`, `actor_action_budget`, and `actor_wall_budget`.
Infrastructure timeout subtypes must match an invalid first attempt's failure
type. Actor-budget timeout subtypes require a valid scored zero, so the report
never folds them into infrastructure invalids. A second attempt must bind the
first attempt ID and receipt hash plus a frozen `retry_rule_sha256`:

```json
{
  "prior_attempt_id": "initial",
  "prior_attempt_receipt_sha256": "<original first-attempt SHA-256>",
  "retry_rule_sha256": "<frozen rule SHA-256>"
}
```

`wall_time_ms` is bounded by the original coarse timestamp interval.
`provider_latency_ms` is cumulative provider wait within the attempt. These
fields must be measured from actual execution telemetry; zeros cannot stand
in for missing observations. A real zero is permitted when the separately
hashed raw trace proves there were no provider calls or actions. The validator
checks field coverage and source binding, not the physical truth of the
counters.

## Candidate and selection trajectory contract

The `cua-full-study-campaign-trajectory-index-v1` has the same study, matrix,
and execution-index hashes as the audited summary and exactly 24 campaign
entries of `{cell_id, researcher_id, receipt}`. Each referenced
`cua-full-study-campaign-trajectory-v1` receipt binds the original selection
freeze and usage receipt SHA-256 values, the frozen training-lineage and
selection-results-bundle SHA-256 values, a 20-task base selection win count
and base-selection receipt hash, and an ordered `rounds` array. Rounds have
sequential `round_index` values and timestamps entirely within the 16-hour
campaign and before the selection freeze.

Each round records `candidate_submitted`, `hypothesis_sha256`,
`training_data_sha256`, `training_receipt_sha256`, `checkpoint_sha256`,
`training_base_checkpoint_sha256`,
`selection_attempts`, `regressions_vs_incumbent`, `promotion_decision`,
`incumbent_after_checkpoint_sha256`, `cost_usd`, `cost_basis`, and
`failure_type`. A submitted candidate must bind training-data bytes; a trained
checkpoint also binds a training receipt, and every submitted candidate binds
the same frozen base checkpoint rather than a previous adapter. There may be
at most two selection
attempts for a candidate: an invalid first attempt followed by one
rule-bound retry. Each attempt records an ID, status, 20-task score when
valid, result-receipt SHA-256, failure type when invalid, timestamps, and the
retry-rule SHA-256 if it is the second attempt. Exactly one valid selection
score at most is allowed per round. An unscored round names a failure class
instead of being mapped to zero.

A promoted checkpoint must strictly beat the prior incumbent's selection
wins and have zero regressed selection tasks; otherwise the incumbent stays
unchanged. The final incumbent checkpoint must equal the frozen selected
checkpoint. Submitted candidates and selection-attempt totals must equal the
campaign freeze and usage receipt counts; summed round costs cannot exceed
the campaign subtotal excluding selected final evaluation. The renderer
reports every campaign's first, best, and last valid selection scores,
first-to-best improvement, post-peak regression, scored/unscored rounds,
selection retries, and selected incumbent separately. A best observed score
is never described as recursive improvement by itself. The raw 20-task
selection results remain separately hashed and reviewer-owned; the schema
checks lineage and summary consistency, not their physical truth.

## Independent application review

The `cua-full-study-independent-release-audit-v1` index binds the same study,
matrix, and execution index and contains exactly six `{cell_id, receipt}`
references. Each `cua-full-study-independent-cell-review-v1` receipt binds
those same hashes, names a reviewer and UTC review timestamp, cites a raw
evidence-bundle SHA-256 and method notes, and records `passed: true` only after
checking all 100 final tasks for source rights, hidden split, GUI trace plus
saved-state readback, negative/reset controls, and actor/evaluator separation.
The five boolean field names are `source_rights_checked`,
`hidden_split_checked`, `gui_trace_and_saved_state_readback_checked`,
`reset_and_negative_controls_checked`, and
`evaluator_independent_of_actor`. A signed-off receipt is an auditable human
claim, not a mathematical proof that the application behaved as recorded.

## Outputs and publication boundary

The builder writes a fresh private review directory containing an English
PDF, four vector SVG figures, ordinal-pseudonymized source-family effects for
all 24 comparisons, a 24-campaign search summary, and a source/output hash
manifest. It includes cost basis,
per-attempt latency/actions/wall time, timeout subtypes, invalid attempt
counts, and family-cluster intervals. It does not expose task instructions,
private source-family names, account state, credentials, or gold. Independently
render every PDF page, inspect figures and tables, scan all output bytes for
private data, then download and hash-check the eventual public release before
calling it published. The builder itself never uploads or publishes.

The unwatermarked renderer accepts only the in-process object returned by the
complete publication audit. A plain aggregate dictionary cannot be passed to
`build_report` to bypass the audit. Within this repository, output is restricted
to `work/` or `tmp/`; publishable paths under `docs/` are refused before any
file is written. The test-only synthetic route watermarks every PDF page and
every SVG and labels both JSON supplements and the output manifest as synthetic.
These controls reduce accidental release of a test fixture. They do not replace
the independent input audit, privacy review, or visual inspection of all pages.
