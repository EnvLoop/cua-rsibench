# Researcher API route preflight — 2026-09-27

The [field-limited receipt](full-study-researcher-route-live-preflight-2026-09-27.json)
binds an authenticated live call to the user-approved AgentRouterHub endpoint.
The model catalog returned HTTP 200 with 26 IDs; all four preregistered
researcher IDs (`gpt-6-astra`, `gpt-5.6-sol`, `gpt-6-sol`, and `gpt-6-luna`)
were present. A bounded, non-benchmark `gpt-6-sol` Responses request returned
`completed` with provider-reported token usage. Raw catalog and response bytes
are stored mode 0600 under ignored `work/`, with SHA-256 bindings in the public
receipt. No benchmark instruction, hidden task, training call, selection
feedback or final result was sent.

An initial Python `urllib` request received Cloudflare error 1010 for this
endpoint. The installed standard `httpx` client reached the same URL normally;
the recorded HTTP 200 catalog and tiny response used that client without a
proxy, altered route, or spoofed user-agent. This difference is a client
compatibility observation, not a model failure or evidence of account balance.

The catalog establishes route visibility, not inference availability for every
listed model. Only `gpt-6-sol` received a live minimal sample. Provider model
snapshot identity, pricing/invoices, rate limits at campaign scale, and the
24-campaign six-cell freeze remain unverified. The [preflight tool](../../tools/preflight_agentrouterhub_researchers_v1.py)
refuses missing model IDs or incomplete sample usage and emits only allowlisted
public fields; reruns require a fresh private output directory.
