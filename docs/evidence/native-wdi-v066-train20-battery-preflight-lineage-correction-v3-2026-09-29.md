# Desktop train-only public lineage correction v3 — 2026-09-29

The [additive v3 receipt](native-wdi-v066-train20-battery-preflight-lineage-correction-v3-2026-09-29.json)
binds the current public [v1 battery preflight](native-wdi-v066-train20-battery-preflight-amendment-2026-09-29.json)
at SHA-256 `f48c303e091003a825122777a692ceef89f1a688d9509a34f5da884a580161f8`.
After v2 was prepared, a field name in v1 was changed to avoid a false
credential-pattern match. The [published v2 receipt](native-wdi-v066-train20-battery-preflight-amendment-v2-2026-09-29.json)
still contains the earlier v1 byte hash. V3 preserves that stale value as
historical evidence and explicitly supersedes v2 SHA-256
`f7e74496cac85d55f369bf06bd90bd1548888c56db9bbb3cb409cc4494f4a84f`.
Neither older receipt is silently rewritten.

The new [read-only validator](../../native_desktop_factory/v066_train20_public_lineage_v3.py)
reopens v1, v2, the v2 15/5 plan, and all 35 files in the frozen full100
evaluator source. It rejects a changed public byte, a stale v3 pointer,
changed plan denominator, or changed evaluator source. The 15-SFT/5-holdout
assignment and running full100 source are unchanged. This corrects document
lineage only: zero train E2B creates, zero Tinker calls, zero official final
admissions, and zero model results.
