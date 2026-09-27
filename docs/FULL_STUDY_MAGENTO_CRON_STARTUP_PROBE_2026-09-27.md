# Training-only Magento cron startup probe — 2026-09-27

The [second frozen-index mismatch](evidence/magento-original-cellwide-index-drift-stop-2026-09-27.md)
stopped the original Magento cell before any final task was seeded. The
original preparation code remains available as the historical runtime. This
dated proposal adds an **opt-in, train-only** variation to the pinned-image
clone preparation: stop its `cron` supervisor immediately after the app
container starts and before any Magento configuration, cache or search-index
operation. The original GUI sweep does not pass this option.

The [probe program](../tools/probe_magento_cron_frozen_start_v1.py) starts one
new pinned app/native-search pair with no task, actor or model. It reads the
live and replica price-index hashes immediately after cron stop, after
configuration/cache cleanup, and after the same `catalogsearch_fulltext`
reindex used by the historical control. Each stage must retain 8,156 matching
price rows and zero derived-price differences, and the sidecar must expose
exactly 181 documents with the historical frozen-source digest. Any mismatch
fails closed and preserves the private failure receipt and disposable pair for
diagnosis. A passing startup probe is still **not** a qualified environment:
it needs a bounded idle check and train-only positive/negative GUI controls
under the same cron policy before a cell-wide runtime revision can be frozen.

If the revised runtime is adopted, the earlier 35 candidate GUI controls
must be rerun in fresh clones before they can be pooled with the remaining
65. No per-case retry of the stopped ordinal is authorized. The model,
researcher campaign and official final counts remain zero. The conservative
provider bill and final runtime fingerprint remain unknown until live
execution and reconciliation.

## First probe failure and narrower startup revision

The [first train-only probe](evidence/magento-cron-startup-probe-v1-failure-2026-09-27.json)
failed before it could stop cron: the app container was running but its
supervisor control socket was not ready at the immediate stop call. It seeded
no task, called no model and left an exact pinned, no-mount disposable pair.
The pair was read-only audited and must be retired by the
[exact training-pair controller](../tools/reconcile_magento_cron_probe_v1.py)
before another probe. This is a setup-timing failure, not evidence that a
cron-free environment passes the source-index gate.

The separately versioned [v2 train probe](../tools/probe_magento_cron_never_autostart_v2.py)
sets `autostart=false` in the disposable container's pinned supervisor cron
configuration **before** the original entrypoint starts supervisord. It
verifies that cron never entered RUNNING, retains the same pinned application
and native-search image IDs with zero host mounts, and reads the price-index
shape after HTTP readiness, after configuration/cache work, after frozen
search reindex, and after a 60-second idle period. Every stage must keep zero
derived-price differences against the source replica; both search checks
must match the frozen 181-document digest. It remains training-only and
does not change historical or active final-candidate sweep commands. A
successful v2 startup still needs separate train GUI positive/negative and
reset controls before a cell-wide runtime amendment can be adopted.
