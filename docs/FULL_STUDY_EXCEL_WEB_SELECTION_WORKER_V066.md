# Excel for the web selection worker (v0.6.6)

`tools/office_web_excel_selection_worker_v1.py` executes the exact 20-task
`CampaignSession.start_selection_attempt` view for the **original Microsoft
Excel for the web** SEC integrated workbook workflow. It accepts neither a
guessed task ID nor a local candidate workbook as a model result. The student
acts through current screenshots and the frozen v0.6.6 GUI action contract.
Each screenshot sample is a separate paid, checkpoint-bound Tinker request;
each task has paid actor and fresh-reset E2B leases. The evaluator separately
double-downloads the exact owner OneDrive `.xlsx` item and scores its saved
formulas, 33 targets, two counterfactual numeric profiles, and non-target
preservation. A distinct neutral cloud copy and sandbox must pass the reset
check before a task contributes a 0/1 row.

The private preparation API is `prepare_private_binding` for each frozen
selection identity, then `prepare_private_manifest` for the ordered 20-task
roster. `ExcelSelectionBatch.run()` validates **all 20** source bindings and
positive/negative SEC calibrations before any paid call. Its hash-chained
`tasks.private.jsonl` preserves task starts, completed receipt hashes,
sampler setup, and scoring. On restart, completed task receipts reopen the
saved pair, verifier and reset files. An interrupted task is not automatically
replayed; an uncertain paid call is recorded as an invalid selection attempt
and requires the campaign's explicit reconciliation/retry rule.

The default live admission gate currently refuses before Tinker, E2B, Graph,
or Office dispatch. The existing evaluator Graph one-file lease controller
permits **train only**; no independent selection/final permission matrix,
distinct actor-account pilot, or source-bound authenticated Graph lease proof
has been admitted. The selection-only scope file is required in addition to
manual actor login, exact file permission, owner/inherited permission review,
and sentinel denial. A fake gate is injected only by offline tests. No
selection score, model comparison, or Office account acceptance is implied by
those tests. Personal OneDrive delegated Graph invite/revoke semantics still
require an authenticated account pilot before publication-scale use.

This worker supports the SEC **integrated** workbook family only. Other
selection workflow keys fail closed. A real 20-task Excel campaign needs all
20 frozen identities to match this workflow or additional source-specific
workers and independent scorers before provider dispatch. It does not inspect
or admit hidden final packages.

Offline checks:

```sh
PYTHONPATH=.:src python3.14 -m unittest \
  tests.test_office_web_excel_selection_worker_v1 \
  tests.test_office_web_excel_selection_boundary_v1 \
  tests.test_sec_excel_web_selection_oracle_v1 -v
```
