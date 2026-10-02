# Magento pre-seed search-index drift rule — 2026-09-27

**Pre-result infrastructure amendment.** In the serial original-Magento GUI
admission sweep, the fresh application/search pair for ordinal 31 stopped during
`positive-prepare`, before the task quote was seeded, before any actor GUI action,
and before a model call. The sidecar exposed all 181 search documents, but their
canonical digest differed from the frozen source digest. The existing preparation
gate refused the pair. This is an evaluator infrastructure failure, not a zero
score or a substitute source baseline.

The [field-limited failure receipt](evidence/magento-original-preseed-index-drift-2026-09-27.md)
records the original stopped journal and diagnostic hashes. Read-only comparison
with the immediately preceding successful frozen-source control found the
unchanged pinned images, zero mounts, zero benchmark quote pages, matching
catalog entity/EAV/stock and non-CMS business table hashes, and an unchanged
price-index replica. The live price index differed in derived price fields;
2,776 of 8,156 rows differed from the replica. The search index differed as a
result or in the same preparation interval. A concurrent indexer/cron operation
is plausible, but its exact causal step has not been proven. The failed pair
remains retained until exact-identity reconciliation.

The [reconciliation controller](../tools/reconcile_magento_unseeded_search_drift_v1.py)
is scoped to this one stopped journal and ordinal. Its audit mode verifies the
original process/stderr hashes, absence of seed and quote, frozen-source
reference hashes, pinned image/network/loopback/no-mount state, container
creation inside the failed prepare interval, 181-document observed mismatch,
and the specific derived-price SQL difference. It writes a mode-0600 private
audit with hashed container identities. Cleanup mode requires that exact saved
audit, repeats the live read-only audit, records cleanup intent, and stops and
removes only the two still-matching disposable containers. It never calls an
indexer, edits a product, seeds a task, or repairs the drifted search index.

After identity-bound cleanup, the unchanged sweep controller may dispatch
**one** complete fresh-clone retry of this same ordinal and private plan. The
retry reruns both positive and negative pairs, the original GUI controller,
independent verifier, and cold-reset control. Its output is not an official
final admission by itself. The original failure remains in the append-only
private journal and public failure count. A second source-hash mismatch or
another failed retry stops the Magento cell; it does not permit further
replacement attempts. At that point, a separately registered cell-wide
deterministic startup change, such as a controlled cron freeze, must be probed
on training material and earlier GUI controls requalified before comparable
candidate results can be claimed.

This rule was recorded before the case-31 cleanup or retry. No final task,
researcher campaign, or model outcome is credited by this amendment.
