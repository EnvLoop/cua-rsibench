# Completion plan — CUA-RSIBench

Reference: evolvent-ai/RSIBench-Data, commit 4c807610243e7b481d382c5ed360c71c79a22f61.

## Required end state

- Real computer-use task execution with reset, persistent state, negative fixtures and host verification.
- Agent-proposed persistent improvements; frozen action space, evaluator, data partitions and budgets.
- Distinct harness adaptation and data/weight adaptation tracks; never conflate their results.
- Five-round campaign, explicit acceptance/rejection lineage, a frozen baseline, held-out final reporting.
- All model calls via user-selected AgentRouterHub Astra/Sol; no secrets in artifacts.
- Actual Tinker/E2B/Harbor path where account access permits; provider blocks do not remove this requirement.
- Published PDF with methods, exact results, limitations and references; visualizations and auditable artifacts.

## Implementation order

1. Build a persistent workbench with task families, visible provenance and dirty records.
2. Implement safe model API accounting, action boundaries and host-only ground truth.
3. Freeze campaign spec/split hashes before evaluation; preserve every attempt and failed call.
4. Test positive/negative/mutation/reset cases, then run model-driven campaigns.
5. Add Harbor task format export and validate it against the actual upstream schema; integrate cloud adapters.
6. Render and inspect PDF, build result visualization, publish and fetch back release assets.

## Current evidence and remaining work

The September 22 credential/billing blocks are resolved. Real Tinker training,
checkpoint sampling, E2B execution and Harbor separate verification have run.
The public pilot PDF/site were published and fetched back. Kanboard public-source
planning calibrated differently for Astra and Sol in one matched pair; this is
discrimination evidence for that task, not a general model ranking.

Both frozen v2 data campaigns completed all five real training attempts. They
used 510,182 and 548,726 scheduled training tokens. No scored candidate improved
on the baseline. The original final trials and all bounded transport-recovery executions have
finished. Three original final trials were invalid; three shared journaled final
checks completed with zero reward and no infrastructure error. Invalid originals
remain undefined, rather than being converted to zero.

Remaining release gates:

- [x] Finish and audit original held-out trials plus separately labeled recovery runs.
- [x] Verify the opt-in v3 observer in real Kanboard, including a saved native edit.
- [x] Publish the English research PDF/site under EnvLoop and verify fetched artifacts.
- [x] Remove historical-manifest dependencies from fresh-clone campaign bootstrapping.
- Broaden the single-trajectory selection track into new data synthesis, add task
  and application coverage, and establish non-recursive controls before stronger
  RSIBench-equivalence or RSI-effect claims. These remain research gaps.

## Claim discipline

A fixed mock score, five iterations of the same hand-written rule, or metadata-only isolation is not RSI evidence.
A zero or negative gain is a valid experimental result. Do not manufacture improvement.

See [RSIBench alignment](../RSIBENCH_ALIGNMENT.md) for the source-reviewed next-stage requirements.
