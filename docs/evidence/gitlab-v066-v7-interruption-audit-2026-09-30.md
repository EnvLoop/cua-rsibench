# GitLab v7 TRAIN interruption audit

The original v7 child has complete saved evidence for three deterministic TRAIN GUI cases with persisted-state scores 1/0/1. The original supervisor result and public outcome are absent. The original CLI therefore still reports `pending_v7_intent_no_replay`. The original supervisor exit code, watchdog outcome, and process-group termination receipt remain unavailable.

The independent read-only audit reopened the consumed intent, child result, frozen source, all three before/after/restored snapshots, the scorer, the exact controlled wrong-object delta, nine raw PNGs, their frame order and permissions, twelve raw Docker log/state files, child stdout/stderr, and reset state. All PNGs are valid and mode 0600. Each case records policy, issue-before, then issue-after; visual inspection of all nine frames confirms the priority label appears on the selected issue after reload. Recorded outbound HTTPS requests were blocked by the frozen local route guard. The three reset generations are consecutive and the last is still current. A fresh full live snapshot equals the frozen baseline. V6's child-only forensic boundary and the original thirteen terminal controls, including the failed terminal index, remain unchanged.

The public JSON contains aggregate counts, hashes, booleans, and explicit unknown supervision fields. It contains no task IDs, project names, issue IDs, labels, prompts, credentials, raw logs, or screenshots. The original v7 private tree has 43 entries and its manifest is identical before and after the audit. No GUI or task was replayed; no provider was called; no original result was reconstructed; no Docker or private evidence file was modified. Official final admission remains zero.

The frozen v7 CLI exposes `freeze`, `audit`, `child-run`, and `run-diagnostic`. It has no terminal-only finalize action. Re-entering `run-diagnostic` would violate its consumed-intent guard. Editing that frozen source would break the source binding. The prepared separate reconciliation tool is therefore the reviewable recovery path.

The tool's `audit` action only reads the original evaluator and can save a separate public audit outside it. Its optional `finalize` action verifies both reviewed hashes, takes the existing diagnostic lock without changing its bytes, reruns the full audit and live baseline check, and creates only `interruption-reconciliation.private.json` in mode 0600. It records `saved_terminal_child_reconciled_missing_original_supervision_no_replay`, unknown original exit/watchdog fields, zero dispatches, and no success claim. It never writes the original supervisor/public result, dispatches a task, launches a browser, calls a provider, resets the application, or performs a Docker mutation. This action has been tested using temporary fixtures and has not been executed against the original evidence. A separate reconciliation receipt does not change the frozen original CLI's pending status or authorize any replay or final admission.

The audit used the pinned evaluator Python runtime and the original evaluator checkout. Reopen it with:

```sh
/Users/xiaoyong/Documents/Codex/2026-09-22/ya/.venv/bin/python -B \
  /Users/xiaoyong/Documents/Codex/2026-09-30/gitlab-v7-interruption-audit/tools/reconcile_gitlab_v7_train_interruption_20260930.py audit \
  --repo /Users/xiaoyong/Documents/Codex/2026-09-25/gitlab-full-world \
  --ratification-private /Users/xiaoyong/Documents/Codex/2026-09-22/magento-observer-fix/work/full-study/v066-caret-amended-control-ratification-20260928.private.json
```

Only after review, `finalize` may be called with the same repo/ratification arguments plus the reviewed tool SHA256, the saved public audit path, the reviewed audit SHA256, and `--execute`. The tool refuses changed source, changed evidence, an active original v7 process, non-owner-only artifacts, changed reset state, a changed live baseline, a mismatched review, or any overwrite. The original supervision evidence remains explicitly missing even if separate reconciliation is performed.

Validation passed 18 focused tests: eight reconciliation refusal/namespace/lock tests and ten frozen v7 tests. The real read-only audit also passed. The preparation is isolated on `codex/gitlab-v7-interruption-audit` from mirror commit `83ebe6786c3bfe26460a6098ad787ecda6d6a3b6`.
