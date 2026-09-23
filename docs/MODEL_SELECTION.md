# Model identities and roles

The registered AgentRouterHub researcher IDs are `gpt-6-astra`, `gpt-6-sol`, and `gpt-6-luna`; `gpt-5.6-sol` is retained for historical research and as the fixed rollout teacher. Exact Sol6 and Luna6 Responses requests have completed and returned matching provider model IDs. A reported model ID is provider metadata, not an independent attestation of its weights.

| Alias | Exact researcher model | Evidence cohort |
|---|---|---|
| astra | gpt-6-astra | Original executable-factory study |
| sol | gpt-5.6-sol | Original executable-factory study |
| sol6 | gpt-6-sol | Separate late-addition cohort |
| luna6 | gpt-6-luna | Separate late-addition cohort |

Historical Sol5.6 results must never be relabeled Sol6. The late-addition cohort begins from fresh factory lineages, uses the same fixed Sol5.6 teacher and Qwen3.5-4B student, explicitly reuses the matched selection baseline, and has a separate sealed final source set. Its corrected turn-budget interface and initial diagnostics differ from the earliest original rounds; the two cohorts are not a matched four-way model ranking.

All researcher and teacher requests use the Responses API and the declared low reasoning effort. Dataset quality, inference validity, infrastructure failures, and monetary cost remain separate measurements. Provider dollar totals are unknown unless supplied by the account owner.

Official model references: [GPT-6 Sol](https://developers.openai.com/api/docs/models/gpt-6-sol) and [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna).
