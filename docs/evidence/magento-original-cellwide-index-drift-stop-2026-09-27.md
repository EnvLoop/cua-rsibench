# Original Magento GUI cell stopped on repeated pre-seed index drift

The [field-limited receipt](magento-original-cellwide-index-drift-stop-2026-09-27.json)
binds the second pre-seed search-index mismatch to the unchanged evaluator
plan. The preceding bounded ordinal-31 retry had passed both GUI polarities
and reset, and the resumed serial queue reached 35 distinct candidate GUI
controls. The next fresh clone stopped during `positive-prepare`, **before**
its task quote was seeded or any actor/model action occurred. Its 181 search
documents had the same unexpected digest as the earlier failed clone, not the
frozen source digest. A read-only SQL scan again found 2,776 of 8,156 live
price-index rows differing from the unchanged price-index replica, with the
same three derived price fields affected. The original journal, process error,
SQL scan and search response are preserved privately and hash-bound here.

The [cell-halt reconciliation controller](../../tools/reconcile_magento_cellwide_halt_v1.py)
can retire only this exact pinned, no-mount, unseeded pair after a second
read-only identity and source-state audit. That cleanup merely frees the
dedicated container names for the training-only startup probe; it does not
authorize another per-case retry or change this stopped result.

The [pre-seed drift rule](../FULL_STUDY_MAGENTO_PRESEED_INDEX_DRIFT_RULE_2026-09-27.md)
allows one complete retry of its first exact ordinal and explicitly stops the
cell on a second source-hash mismatch. Therefore **no further per-case retry
is allowed** for this second interruption. The running disposable pair is
retained, unseeded, for read-only diagnosis. The application image starts a
cron supervisor, and an indexer cron job overlapped the earlier mismatch;
that is a plausible cause, not a proven causal attribution. A training-only
startup probe must compare the live and replica price-index hashes at each
setup stage and test a deterministic cron policy. Any changed startup recipe
must be declared as a cell-wide environment revision and used to requalify
the prior 35 GUI controls as well as the remaining candidates before the
100-task final cell can be admitted. Old passes remain historical evidence,
not silently mixed with a revised runtime.

This is infrastructure and evaluator qualification work. Magento official
final admissions, researcher campaigns, and model outcomes remain zero.
