# Real cloud validation

Evidence is indexed by `outputs/evidence.json` after running `tools/summarize_evidence.py`.

1. E2B: successful creation, command execution, and destruction after credential correction.
2. Tinker: Qwen/Qwen3.5-4B, rank-8 LoRA, one real optimizer step on verified training-split demonstrations, persistent sampler checkpoint and actual checkpoint sampling. Training smoke is not capability improvement evidence.
3. Harbor 0.23: real browser oracle in E2B, separate verifier sandbox, reward 1 and no trial errors.
4. Full service chain: real checkpoint through bearer-authenticated E2B sampling proxy to Harbor's E2B browser task and separate verifier. Completed with reward **0** and no infrastructure errors. This is a valid negative task result. Proxy was destroyed.
5. Real Kanboard: native GUI execution and database readback are being calibrated on real-source public issue metadata. Infrastructure interruptions are excluded from model-success denominators and retained in the evidence index.

The stock Harbor E2B implementation requests 86400-second lifetimes. This account allows one hour. `BoundedE2B` requests 1800 seconds; the adaptation changes lifecycle only, preserving agent and verifier behavior.

All provider receipts retain usage counts and timestamps. Monetary cost remains null unless an authoritative account price is available; null is not zero. Tinker checkpoints are hashed in public summaries to avoid publishing account-specific identifiers.
