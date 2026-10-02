# Desktop train-only battery source rebase v2 — 2026-09-29

The [v2 source receipt](native-wdi-v066-train20-battery-preflight-amendment-v2-2026-09-29.json)
and [v2 15/5 plan](native-wdi-v066-train20-battery-authorized-plan-v2-2026-09-29.json)
supersede the earlier **offline-only** battery plan before any paid training
guest. The task assignment, public-training profile reference, power-policy
flag, and provider active-zero gate are unchanged. The v2 independent auditor
additionally reopens each train guest's raw UTC/local date observations and
checks the unmasked LibreOffice tip day against the dated public-training
baseline. This matches the final-control rule and prevents an SFT source from
being accepted solely on a normalized profile fingerprint.

The 15 prospective SFT examples still require real GUI collection and saved
OOXML verification. Five task-disjoint training holdouts remain excluded from
that collection. Neither version created an E2B training guest, invoked
Tinker, trained a checkpoint, or produced an official final result. The
running 100-task Desktop evaluator-control freeze remains byte-identical.
