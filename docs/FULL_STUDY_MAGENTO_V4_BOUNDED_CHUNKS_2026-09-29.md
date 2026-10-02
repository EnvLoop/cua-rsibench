# Magento v4 bounded 100-case GUI control amendment

**Pre-result source amendment; no v4 candidate has been run or admitted.** The
v3 freeze remains immutable. V4 must bind its exact private hash and public
receipt, the same 100 ordered candidate package identities, the original
Magento and native-search images, the pinned Python and Playwright runtime,
the train-only release-notification guard pilot, and unchanged v3 per-case GUI
actor and saved-state scorer bytes. V4 starts from case index zero in a new
private run directory. Historical v2 partial controls and any v3 controls
contribute zero to its denominator. A v3 campaign directory already present
blocks the v4 freeze rather than allowing ambiguous reuse.

Each invocation of `run` explicitly declares `--max-cases` from 1 through 5.
The cap counts **new complete cases in that invocation**, not raw attempts.
Each complete case still requires fresh positive and wrong-variant Magento plus
native-search pairs, saved-state scores 1 and 0, four exact pre-edit readbacks,
independent material cold reset, and verified removal of both disposable
pairs. Only then can the controller append `case_completed` and stop. The
partial `chunk_completed` journal receipt binds the v4 freeze, v3 parent,
ordered completed identities, calibration receipt hashes, exact preceding
journal prefix, retry count, and next ordinal. This is a private engineering
receipt, **not an official final-task admission**.

`--resume` holds the same exclusive Magento lock, revalidates the v4 and v3
freezes, exact plan and source, complete journal hash chain, ordered event
sequence, every prior completed saved-state receipt, and the entire attempt
directory inventory before starting another case. A completed task is never
rerun. An open dispatch resumes under its original case cap; a crash just
after a completed case but before `chunk_completed` closes that exact boundary
without replay. A partially executed case must pass the original explicit
read-only interruption audit and exact cleanup before its one permitted
whole-case infrastructure retry. Missing or extra attempt directories,
changed receipts, a different cap for an open dispatch, and any unexplained
material state fail closed. The 20 study-wide and one per-case retry limits
remain unchanged. The v3 and v2 source, journals, and failure evidence are
retained.

For the first live chunk, commit the generated v4 public freeze before
dispatch. From the project root, using the pinned interpreter:

```bash
env PYTHONPATH=.:src /Users/xiaoyong/Documents/Codex/2026-09-22/ya/.venv/bin/python -m tools.magento_clean_100_v4 freeze \
  --plan work/magento-original/candidate-plan-v2.private.json \
  --plan-sha256 1df41f027b5f284c7ff7ed162f42f075259960242a295e0a430bff1c8b479ae1 \
  --source work/webarena-source \
  --parent-freeze work/magento-original/cron-freeze-20260928.private.json \
  --freeze-v4 work/magento-original/clean-v4-freeze-20260929.private.json \
  --public-out docs/evidence/magento-clean-100-v4-freeze-2026-09-29.json

env PYTHONPATH=.:src /Users/xiaoyong/Documents/Codex/2026-09-22/ya/.venv/bin/python -m tools.magento_clean_100_v4 run \
  --plan work/magento-original/candidate-plan-v2.private.json \
  --plan-sha256 1df41f027b5f284c7ff7ed162f42f075259960242a295e0a430bff1c8b479ae1 \
  --source work/webarena-source \
  --parent-freeze work/magento-original/cron-freeze-20260928.private.json \
  --freeze-v4 work/magento-original/clean-v4-freeze-20260929.private.json \
  --run-dir work/magento-original/clean-v4-100-20260929 \
  --max-cases 2
```

The historic observed pace was about 17 minutes per complete case, so this
first two-case chunk might take roughly 34 minutes plus startup and audits;
that is an estimate, not a timeout or completeness claim. Later calls use the
same paths with `--resume --max-cases 2` (or another cap after a closed chunk).
An open dispatch requires its original cap. No new dispatch should be started
while an existing process or disposable pair is live. Once all 100 controls
finish, `audit` independently reopens every completed case and writes a
separate public aggregate; that still does not admit official final tasks or
produce a model result.
