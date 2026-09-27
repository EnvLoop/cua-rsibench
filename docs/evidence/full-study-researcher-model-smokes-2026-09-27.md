# Four researcher routes: live tiny-sample evidence — 2026-09-27

The [first route receipt](full-study-researcher-route-live-preflight-2026-09-27.json)
binds the live model catalog and a completed minimal `gpt-6-sol` response.
The [additional smoke receipt](full-study-researcher-model-smokes-2026-09-27.json)
records one completed, non-benchmark Responses request for each of
`gpt-6-astra`, `gpt-5.6-sol`, and `gpt-6-luna`. All four planned researcher
models therefore returned a completed tiny request through the approved
AgentRouterHub endpoint. Provider-reported tokens, request hashes and response
hashes are public; raw responses are mode 0600 under ignored `work/`.
The [offline auditor](../../tools/audit_agentrouterhub_model_smokes_v1.py)
rebuilds the three additional public rows from those private bytes.

These probes sent no benchmark task, hidden source, training data, selection
query or final evaluation. They show current route and model availability for
minimal calls only. They do not establish sustained rate limits, researcher
reasoning configuration, account balance, invoices, model snapshot identity,
or the six-cell campaign freeze. Official task admissions and campaigns remain
zero.
