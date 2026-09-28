# PowerPoint for the web selection worker (v0.6.6)

`tools/office_web_ppt_selection_worker_v1.py` accepts only the exact 20-task
`CampaignSession.start_selection_attempt` roster and its trained Tinker
checkpoint. The active WDI v13 selection source has five distinct country
families and **eight calculation workflows** across 20 seven-slide briefs.
Every selection task uses the same three dependent text targets: summary,
calculation ledger and interpretation. One GUI adapter therefore covers all
eight, while the evaluator-owned WDI oracle derives the correct values and
checks the task-specific deck.

Each model sample is charged as a distinct checkpoint-bound Tinker attempt
after a current screenshot is saved. Actor and fresh-reset E2B leases are
separately charged for every task. The actor uses only v0.6.6 mouse/keyboard
actions in the original PowerPoint web editor. An evaluator with an owner
Graph identity double-downloads the exact item before the actor, after save,
and from a distinct neutral reset copy. The saved-state oracle checks all
three corrections, seven-slide content, native chart values and the embedded
workbook; any unrelated change scores zero. A missing source, unreadable
artifact, permission failure, or reset drift makes the attempt invalid rather
than a model zero.

Before paid work, the worker validates all 20 private task specifications,
frozen package identities, six-cell v0.6.6 action ratification, raw WDI source
decks, Office-normalized baselines, source-to-baseline semantic equivalence,
and evaluator-owned positive, partial and collateral scorer controls.
`prepare_private_binding` and `prepare_private_manifest` create immutable
private references; `PptSelectionBatch.run()` keeps a hash-chained task ledger
and reopens saved, verifier and reset bytes when resuming completed tasks.
An interrupted task or uncertain provider request is never replayed
automatically. Only a complete 20-row result with all per-task Tinker and E2B
paid requests can enter `record_selection_scored`.

The default live Graph admission gate **currently refuses before any paid
call**. The owner-side one-file permission controller remains train-only;
selection needs its own authenticated owner/actor account pilot and frozen
permission matrix. Offline fake tests inject a test gate only to verify the
contracts. They are not PowerPoint web acceptance, student scores, or a
published campaign. Personal OneDrive delegated invite/revoke behavior must
be proven on the intended accounts before the gate changes. The 20 selection
sources and all 100 final tasks stay evaluator-private; this worker admits no
final task.

Offline checks:

```sh
PYTHONPATH=.:src python3.14 -m unittest \
  tests.test_office_web_ppt_selection_worker_v1 \
  tests.test_office_web_ppt_selection_graph_v1 \
  tests.test_ppt_wdi_selection_oracle_v1 -v
```
