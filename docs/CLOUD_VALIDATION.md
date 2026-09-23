# Real cloud validation

## Current executable-factory studies

The original and Sol 6 / Luna 6 extension cohorts completed 13 accepted datasets and real 32-step LoRA training/sampling runs on Qwen/Qwen3.5-4B, totaling 1,636,954 scheduled training tokens. The fixed teacher is gpt-5.6-sol. Each cohort has a frozen selection and source-disjoint final instances. These are separate cohorts, with different final records and researcher-interface timing.

Current evidence is exported by `tools/audit_factory_study.py` to `factory-study.json` and `model6-study.json`. It verifies accepted data, training and checkpoint bindings, exact task results from separate saved-state verifiers, promotion, accounting, and frozen-final timing. Recorded remote executions additionally bind the trusted source/worker snapshot, task packages, runtime versions, archive and member hashes, and cleanup. See [remote evaluation](REMOTE_EVALUATION.md).

A valid failure is a model score. An infrastructure-invalid execution has no complete model score and remains visible beside its declared recovery. Provider monetary totals are unknown. These runs establish real service execution; they do not establish sustained RSI.

## Historical v0.4 integration and campaigns

The following sections record the earlier integration and single-trajectory experiment. Their totals and scores are not pooled with the executable-factory studies. Historical evidence is indexed by `outputs/evidence.json` after running `tools/summarize_evidence.py`.

1. E2B: successful creation, command execution, and destruction after credential correction.
2. Tinker: Qwen/Qwen3.5-4B, rank-8 LoRA, one real optimizer step on verified training-split demonstrations, persistent sampler checkpoint and actual checkpoint sampling. Training smoke is not capability improvement evidence.
3. Harbor 0.23: real browser oracle in E2B, separate verifier sandbox, reward 1 and no trial errors.
4. Full service chain: real checkpoint through bearer-authenticated E2B sampling proxy to Harbor's E2B browser task and separate verifier. Completed with reward **0** and no infrastructure errors. This is a valid negative task result. Proxy was destroyed.
5. Real Kanboard: native GUI execution and database readback are being calibrated on real-source public issue metadata. Infrastructure interruptions are excluded from model-success denominators and retained in the evidence index.

The stock Harbor E2B implementation requests 86400-second lifetimes. This account allows one hour. `BoundedE2B` requests 1800 seconds; the adaptation changes lifecycle only, preserving agent and verifier behavior.

Available provider receipts retain usage counts and timestamps. Some terminal teacher transport failures lack a flushed terminal receipt; unavailable usage is unknown, not zero. Monetary cost remains null unless an authoritative account price is available. Tinker checkpoints are hashed in public summaries to avoid publishing account-specific identifiers.

### Historical frozen data-research campaigns

`formal-data-astra-v2` and `formal-data-sol-v2` each executed five 16-step LoRA
attempts using the same Qwen3.5-4B base, teacher corpus and training settings.
The researchers changed only demonstration selection and optional consistent
control-reference augmentation. Training totals are 510,182 and 548,726 tokens.
Among the original candidate evaluations, seven are scored failures and three
are infrastructure-invalid. Neither researcher has an observed strict gain.

`tools/audit_data_campaigns.py` checks raw training hashes, update counts, budgets,
source disjointness, original scores, selection rules and test-start ordering.
It exports sanitized evidence without account/checkpoint identifiers. Current
completion and held-out outcomes are in `data-campaigns.json` in the release.

### Historical versioned repairs

The original observer/runtime remains frozen. `stable_observer.py` and
`kanboard_rpc_v3.py` are an explicit opt-in runtime: one batched snapshot, actual
element-object references, modal isolation, native visibility checks for closed
details, and a bounded screenshot timeout. It does not expose additional model
tools. Export with `python -m cursibench.kanboard_harbor_export_v3`.

`ReadRetryE2B` retries only two exact application-read-only commands, up to three
dispatches. It never redispatches a GUI mutation, setup or arbitrary shell command.
Recovery executions retain the original actor, checkpoint, task, observer and
verifier, and are reported separately rather than overwriting the original run.
The v3 frontier agent separately records bounded inference retries, whose unknown
usage/cost is not reported as free.

`JournalE2B` then extends recovery to GUI commands using a durable request ID and
sandbox-side command journal. Concurrent/repeated dispatches of the same logical
command reuse the stored stdout, stderr and exit status. An intent without a
completed result fails closed rather than replaying possibly completed effects.
The model still has the same GUI-only action space. Unit checks cover concurrent
duplicates, lost-result retrieval, ID collisions and incomplete intents.

Live v3 integration `native-v3-basic-03` passed a real Sol edit under Harbor/E2B
with a separate verifier (reward 1, zero infrastructure errors). Its observer
recovered once from a post-save navigation/context transition. Five real Kanboard
surfaces also matched the old nonmodal control lists; the slowest median snapshot
was 4.115 seconds before batching and 0.0092 seconds afterward. These measurements
exclude model inference and are not model-speed or training-improvement claims.
