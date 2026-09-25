# Researcher model route preflight: connectivity only

Checked 2026-09-25 against the configured OpenAI-compatible Responses route through AgentRouterHub, using the repository's [`agentrouter.py`](../../src/cursibench/agentrouter.py). Each request contained only the same short public marker prompt, a 128-output-token ceiling, and the adapter's current low-reasoning setting. No benchmark task, account data, private document, source code, screenshot, or gold was sent. All four responses completed, returned the exact marker, and reported the requested model ID:

| Researcher configuration | Gateway-reported model | Input tokens | Cached input tokens | Output tokens | Elapsed seconds |
| --- | --- | ---: | ---: | ---: | ---: |
| Astra | `gpt-6-astra` | 4,128 | 3,968 | 9 | 6.093 |
| Sol 5.6 | `gpt-5.6-sol` | 4,394 | 4,224 | 9 | 5.374 |
| Sol 6 | `gpt-6-sol` | 4,394 | 4,224 | 9 | 2.660 |
| Luna 6 | `gpt-6-luna` | 4,394 | 3,840 | 9 | 1.987 |

The provider usage envelopes include router-side instruction and cache accounting, so these token counts are much larger than the visible marker prompt and differ by route. This one request per model does **not** establish sustained throughput, equal latency, account rate limits, dollar prices, model weight identity, or performance on computer-use tasks. The final study must freeze the actual researcher prompts/reasoning settings and measure all 24 campaigns under matched per-campaign caps. Response IDs and full attribution details are retained only in a private hash-bound receipt; the [field-limited JSON](full-study-researcher-route-preflight-2026-09-25.json) contains no credential or private request body.

**Study status from this probe:** 4/4 routes reachable, **0/24 researcher campaigns completed**, and **0 official final results**.
