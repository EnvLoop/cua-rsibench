# Desktop train-only battery preflight amendment — 2026-09-29

The [dated source receipt](native-wdi-v066-train20-battery-preflight-amendment-2026-09-29.json)
and [rebased private-plan aggregate](native-wdi-v066-train20-battery-authorized-plan-2026-09-29.json)
prepare the existing 15-SFT/5-holdout original WDI training diagnostic for
the user's battery authorization. The task assignment is unchanged: all 20
packages remain in the **training** split, and the five diagnostic holdout
IDs remain excluded from SFT collection.

The train collector still requires an explicit paid-run switch, a source-bound
plan, an unused per-ID intent, account-wide E2B active-zero, and the raw-frame
storage floor. By default it still requires AC power. A separate
`--battery-authorized` switch permits a battery-powered run, and each paid
intent records the host's power source, battery percentage, capture time, and
hash of the bounded `pmset` observation. Unknown telemetry or battery power
without that switch fails before a provider create. The independent train
auditor checks the intent/receipt power binding. This amendment changes only
the train-only worker/auditor and plan source hashes; the 35 files in the
running 100-task final-control source freeze are byte-identical.

No E2B train guest, Qwen/Tinker request, checkpoint, or model comparison was
created by this offline amendment. Train-only collection must wait until the
separate 100-task evaluator-control E2B batch is terminal and the provider is
active-zero. The preserved 15/5 split is a diagnostic design, not an official
hidden-final benchmark outcome.
