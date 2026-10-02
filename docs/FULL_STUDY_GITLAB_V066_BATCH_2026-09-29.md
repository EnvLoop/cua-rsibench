# GitLab CE v0.6.6: source-bound one-ID batch controller

This dated batch layer starts **after three independently audited current-profile evaluator controls**. It leaves the 100-ID plan, frozen original GUI controller, one-ID supervisor, prior journal, all raw case receipts, and six historical first-attempt failures unchanged. The three current controls establish an immutable prefix, not three official final admissions.

`gitlab_world.v066_supervised_final_batch_v1` adds a private source plan and an append-only hash-chained batch journal. Every invocation requires an explicit positive `--max-new-ids`; it dispatches one next ID through the existing `v066_supervised_final_one_v1.run_one` supervisor, then independently reopens the original saved GUI, PostgreSQL/Git, score, unrelated-change, and reset receipts. It checks the GitLab CE image, healthy container and exact frozen business baseline before another ID. The existing one-ID supervisor retains its 7,200-second child watchdog, process-group termination, terminal journal entry on failure, and exact cold-reset recovery. The batch layer never makes model calls and never retries an ID.

Each batch has a private `batch_start`, per-ID pre-dispatch `id_intent`, independently verified `id_completed` or `id_failed`, and `batch_end` event. Completed batches have immutable mode-0600 private and field-limited public receipts. If the process stops after an ID intent, the next invocation requires `--resume-pending` with the same frozen batch budget. It can only reconcile an already-existing one-ID result. A missing, uncertain or unauditable result stops without replay. If the batch journal closes before its receipt is written, the next invocation reconstructs only that immutable receipt. A failed ID blocks future batches pending a separately sourced amendment and explicit review.

First freeze in the original GitLab worktree, with its preserved evaluator-private world and the original six-cell ratification path:

```bash
PYTHONPATH=src:. python -m gitlab_world.v066_supervised_final_batch_v1 freeze \
  --ratification-private /ABS/PATH/TO/v066-caret-amended-control-ratification-20260928.private.json
```

The freeze reopens the first three raw controls and compares the computed private/public audit to the preserved read-only three-ID aggregate. It binds the original and supervisor plans, prior journal prefix, first three one-ID result bytes, this module, its tests, and this note. After reviewing the private/public plan, a bounded live batch is:

```bash
PYTHONPATH=src:. python -m gitlab_world.v066_supervised_final_batch_v1 run-batch \
  --ratification-private /ABS/PATH/TO/v066-caret-amended-control-ratification-20260928.private.json \
  --max-new-ids 3 --execute
```

For a pending batch, use the same command with `--resume-pending`. `audit` is read-only and reports the number of source-bound current controls, whether a batch/ID remains pending, and whether a terminal failure occurred. The batch must run from the original GitLab worktree because its evaluator-private runtime and baseline live there. Do not invoke two batch controllers concurrently or call the one-ID supervisor separately during a batch.

These are evaluator-operated solvability and reset controls. Per-ID final proof issuance, six-cell admission, 24 researcher training chains, Qwen/Qwen3.8-27B checkpoint selection, matched final model evaluation and the full English result paper remain separate gates. The batch receipts always state `official_final_admitted: 0`.
