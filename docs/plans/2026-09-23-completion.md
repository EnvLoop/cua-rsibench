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

## Open dependency

Tinker returned billing 402 and E2B rejected supplied credentials on September 22.
Await user-side account correction; continue local implementation and verification independently.

## Claim discipline

A fixed mock score, five iterations of the same hand-written rule, or metadata-only isolation is not RSI evidence.
A zero or negative gain is a valid experimental result. Do not manufacture improvement.
