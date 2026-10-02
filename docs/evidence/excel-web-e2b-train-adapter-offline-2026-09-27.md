# Excel-web screenshot actor: offline train adapter

The train-only E2B adapter now sends the shared Qwen/Qwen3.8-27B student a
current screenshot and the train actor instruction, normalizes one action
through the shared v0.6.5 contract, rechecks the pixels after sampling, and
dispatches only a validated coordinate GUI action. It records private screen
frames and append-only intent/results, and terminates the bounded sandbox even
on invalid actions or provider errors. A hidden-final package path or oracle
field fails preflight before any provider connection.

Ten fake-provider acceptance tests passed. One actual evaluator-private train
actor workbook passed a package-only, no-provider preflight; the
[aggregate receipt](excel-web-e2b-train-adapter-offline-2026-09-27.json)
contains its hash commitment and no task identity or answer. No E2B connection,
Tinker call, Microsoft upload, Excel-web save, or cloud download was made in
this check. The adapter deliberately reports any injected workbook package
readback as unscored, because package validity alone cannot bind an Excel cloud
item or establish the task oracle. Original-software and official-final
admissions remain **0**.

The next live train pilot requires an account scope that cannot reach sealed
final items, manual login, a source-bound cloud upload, and an independently
audited saved `.xlsx` download. The [design boundary](../plans/2026-09-27-excel-web-e2b-train-adapter.md)
records the transport and evidence limits.
