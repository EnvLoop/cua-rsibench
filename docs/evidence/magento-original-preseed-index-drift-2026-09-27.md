# Magento search-index drift before task seeding

The [aggregate receipt](magento-original-preseed-index-drift-2026-09-27.json)
binds one stopped evaluator preparation attempt. The pinned, mount-free Magento
clone and native search sidecar were created, but the frozen 181-document
search-index digest check failed. The attempt stopped before task seeding,
visible GUI control, model inference, or official admission. The original
process stderr and append-only journal remain private and hash-bound.

A read-only comparison to the preceding successful frozen-source clone found
that eight stable catalog table digests, including the price-index replica,
and five non-CMS business table digests still matched. The live price index
had 2,776 changed derived-price rows among 8,156 rows; no price row key or
non-derived field differed. Cron and price/fulltext indexer updates overlapped
the preparation window. That timing supports an infrastructure-drift
hypothesis, but it does not identify the precise operation that caused it.

The exact failed containers remain in place. The [dated one-case recovery
rule](../FULL_STUDY_MAGENTO_PRESEED_INDEX_DRIFT_RULE_2026-09-27.md) requires a
second private, identity-bound read-only audit before retiring them and permits
at most one complete fresh-clone retry of the unchanged candidate. This
receipt grants no GUI qualification and no benchmark outcome.
