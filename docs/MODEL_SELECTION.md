# Model/provider selection

The researcher/controller model is separate from the computer-use task model. It should inspect train
trajectories, propose a bounded harness/data change, and write a structured rationale; it must never see
hidden test tasks or verifier internals.

The repository supports the two requested AgentRouterHub model IDs:

- `gpt-6-astra`: recommended for the meta-researcher, failure diagnosis, causal review, and candidate
  proposal. Its higher reasoning budget is useful when the trajectory evidence is long and mixed.
- `gpt-5.6-sol`: recommended as a lower-cost independent reviewer, control proposer, or repeated rollout
  worker. It is also useful for checking whether Astra's proposed change is supported by the evidence.

Both were live-probed through `https://sub2api.agentrouterhub.com/v1/responses` and returned the expected
sentinel response during this release. The probe does not establish benchmark performance.

Example shell configuration, with secrets kept outside the repository:

```bash
export OPENAI_BASE_URL=https://sub2api.agentrouterhub.com
export OPENAI_API_KEY=...                 # user-owned secret, never commit
```

The `cursibench.agentrouter` module uses only the Responses API, validates the model allowlist, adds a
stable user-agent, and fails closed when the key is missing or the provider returns an error.

## Provider status observed for this release

- AgentRouterHub: reachable; Astra and Sol sentinel calls passed.
- Tinker: SDK import passed, but a real service capability call returned HTTP 402 because the account's
  billing status blocks access. No paid training attempt was started.
- E2B: SDK import passed, but sandbox creation returned HTTP 401 because the supplied key was rejected as
  malformed and the service requires the `e2b_` key format. No sandbox task was run.

The local fake chain remains useful for protocol/CI checks, but it is not external evaluation evidence.
