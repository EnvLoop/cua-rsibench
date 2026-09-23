# Model roles and provider evidence

`gpt-6-astra` and `gpt-5.6-sol` are the requested AgentRouterHub model IDs. Both have completed live Responses requests. Use the former or latter for browser execution, candidate research, or review under explicit fixed settings. A returned alias is provider metadata, not independent proof of model identity. No pricing or overall superiority is asserted.

The Tinker training target is separate: the verified smoke uses `Qwen/Qwen3.5-4B`, rank 8, one optimizer step. It does not train Astra or Sol. The resulting checkpoint was actually sampled and evaluated through E2B and Harbor; it failed the task with reward 0 and no infrastructure error.

Credentials remain outside the repository. Current bounded native-app calls use low reasoning effort, 1200 requested output tokens, 180-second request timeout, one retry for designated transient errors, and a fixed GUI action budget. Earlier timeouts are preserved as infrastructure exclusions.

E2B is now usable with corrected credentials. Tinker became usable after the account was funded. Old 401/402 observations are historical diagnostics, not current blockers.
