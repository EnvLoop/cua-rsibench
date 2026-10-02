# Train-only task-difficulty screen for the full computer-use study

**Status: pre-result method, not a passed screen or a benchmark result.** The
current repo has real-application positive/negative/reset controls and bounded
Qwen interface smokes, but it has **no paired, independently saved-state-scored
Qwen versus Astra/Sol episodes** on representative training tasks for all six
cells. This document and its offline auditor make that missing evidence
explicit. They do not admit any of the 600 official final identities or
authorize a model campaign.

## Why two gates are needed

An evaluator-owned GUI positive and plausible negative establish that a task
is solvable, that the intended saved state can be measured, and that unrelated
state is protected. They do **not** show whether a model can solve the task or
whether different model capabilities separate. Conversely, a low model score
without a trustworthy GUI positive can be an interface, persistence, or oracle
failure. The study therefore keeps **application qualification** and
**train-only model difficulty** as separate gates.

Three design choices were considered. Counting GUI positives alone would
confuse solvability with difficulty. Counting one base-model failure would
confuse a hard task with invalid actions, timeouts, or a broken renderer. The
adopted screen pairs the fixed Qwen base student with a separately configured
`gpt-6-astra` or `gpt-6-sol` reference actor on the **same train-only tasks**,
uses the same frozen observation/action budget, and reads saved state with an
evaluator-side verifier. “Stronger reference” names a proposed diagnostic
role; model superiority on these tasks remains to be measured.

## Predeclared input and evidence boundary

`src/cursibench/train_difficulty_gate_v1.py` reads an ignored private
`cua-train-difficulty-input-v1` JSON manifest. Its partition must be `train`.
Each task has opaque SHA-256 identities for task, source family, workflow, and
verifier, plus a train-only GUI control receipt and a four-part complexity
vector: target fields, causal steps, distractor objects, and screen
transitions. The manifest declares minimum complexity **before** model probes;
tasks below it cannot certify the intended final difficulty. No selection or
final task, prompt, answer, gold file, application account with final access,
or final score may enter the manifest or a model request.

Both actor configurations bind a model ID, provider route, prompt, and exact
configuration hash. A Qwen attempt and a reference attempt use the same task,
action profile, maximum GUI actions, and wall-clock envelope. Each scored
attempt must retain the actual saved-state bytes, a separately emitted
evaluator receipt, observation/action trace hashes, a verified fresh reset,
and a valid binary score. The auditor opens the saved bytes and verifier
receipt and checks their hashes and score agreement. This is a **generic
cross-cell integrity check**, not a substitute for a cell auditor reopening
the real `.pptx`, `.xlsx`, database snapshot, or native document and rerunning
its semantic verifier. Model-visible input is limited to the task and current
GUI observation; the verifier receipt declares `model_visible=false`.

The public output contains only aggregate counts, unnamed workflow/family
indices, configuration/input/gate-source hashes, and screening decisions. Private task
identities, model text, screenshots, saved artifacts, and oracle details stay
under ignored evaluator storage. A public aggregate must be privacy-reviewed
before commit. The CLI refuses to overwrite a prior aggregate:

```bash
PYTHONPATH=src python tools/audit_train_difficulty_v1.py \
  --input work/train-difficulty/powerpoint-web/input.json \
  --out work/train-difficulty/powerpoint-web/aggregate.json
```

## Screening rules, fixed in source

These are **descriptive pre-freeze exclusion heuristics**, not confidence
intervals, p-values, official benchmark results, or evidence of training gain.
All 8 paired tasks for a workflow must come from at least two train source
families with at least two pairs each. A source-family report remains visible
so one easy source cannot be hidden by a hard aggregate.

| Condition on a workflow | Decision before final freeze |
| --- | --- |
| Any known-positive/near-miss/cold-reset control fails | Exclude the affected source family; the workflow cannot pass while that failure remains in the proposed pool. Preserve the failed receipt. |
| A pilot task is below the predeclared train complexity minimum | Hold as nonrepresentative; create a separate train-source challenge analogue. Do not inspect final answers to repair the pilot. |
| Fewer than 8 paired scored tasks or fewer than 2 source families with 2 pairs each | Insufficient train evidence; no difficulty claim. |
| Infrastructure-invalid fraction >10%, either actor's valid-action fraction <85%, or reference wall-limit fraction >25% | Hold the interface or budget; do not turn these into model zeros or task-floor evidence. |
| Qwen and reference each solve at least 7/8 (87.5%) | Exclude the workflow/template as a ceiling for this study before freeze. |
| Reference solves at most 1/8 (12.5%) after the preceding controls pass | Exclude the workflow/template as a floor under this fixed actor/budget protocol; this is not a claim of human impossibility. |
| Qwen solves 12.5–75%, reference at least 50%, and reference exceeds Qwen by at least 12.5 points | Record a discriminative **train** screen, still subject to cell-specific saved-state audit. |
| Other paired pattern | Hold as ambiguous separation; retain all attempts. |

The aggregate can report `all_observed_train_workflows_discriminative` only
when every workflow **represented in this train manifest** passes. It cannot
certify unrepresented final workflow types or a full cell, and it never changes
official admission or result counts. A failed model attempt can end at the action or wall limit
and score zero **only if** the saved state and independent verifier were
successfully read afterward. Provider, transport, environment, or verifier
failures are `infrastructure_invalid`, never score zero. The input permits at
most one append-only infrastructure retry per task/actor; an unresolved pair
reduces evidence rather than disappearing. Partial target completion is
reported separately and cannot silently change the binary endpoint.

The 8-task cutoffs are deliberately coarse and should not be read as
statistical significance. A publication should retain family-stratified
counts and uncertainty from the actual 100 frozen final tasks, as specified
in the [full study preregistration](FULL_STUDY_PREREGISTRATION.md). No task or
family may be removed **after** official final outcomes are observed because
its score was inconvenient. Any later substantive task, model, budget, or
verifier change requires a dated new protocol and preserves old outcomes.

## Current gap and bounded next experiment

The [native Desktop Qwen train smoke](evidence/native-wdi-qwen-v064-nonfinal-smoke-2026-09-27.md)
applied two GUI clicks and stopped before a saved edit; the
[Odoo train smoke](evidence/odoo-qwen-v065-native-train-2026-09-27.md) also
reached a two-action cap with reward zero. The
[Magento price-777 pilot](evidence/magento-price777-qwen-scored-v3-2026-09-25.json)
contains one completed, independently inspected base attempt on a published
development task, not a paired reference sample of original final-like work.
The four researcher-route smokes sent no benchmark task. None can be imported
as a completed difficulty pair. The [PowerPoint split-shape audit](evidence/ppt-wdi-split-difficulty-shape-2026-09-27.json)
records one target field per train task versus four on distinct final slides;
those train smokes cannot establish final-like difficulty. Ten declared final
PowerPoint workflow types would require **at least 80 representative train
challenge tasks** for this per-workflow screen, distributed across train-only
source families. This is additional pilot work, not a reason to expose final
families to a model.

The next paid pilot should begin with **two** qualified, representative
train-source tasks in one cell: same frozen v0.6.6 action profile, identical
action/wall envelopes, one Qwen base and one Astra/Sol reference saved-state
episode per task, independent verifier and reset on each. Reserve a stated
worst-case provider/E2B cost before dispatch, preserve all failures, then
expand toward the 8-pair workflow threshold only if the source-bound runner
and per-cell verifier pass. No live pilot was dispatched with this gate:
Office account isolation and cloud readback are unresolved, Desktop's bounded
development lease is nearly exhausted, and the existing Magento/GitLab/Odoo
workers are carrying other evaluator-owned operations. These are interface
and budget boundaries, **not** observed model difficulty.
