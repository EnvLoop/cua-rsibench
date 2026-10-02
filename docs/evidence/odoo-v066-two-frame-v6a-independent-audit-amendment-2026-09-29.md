# Odoo v6 independent trace audit amendment

The frozen v6 actor requires two byte-identical final physical PNG reads for
one purchase-RFQ click. Its original read-only auditor reopens every indexed
trace sample, but an offline mutation check found that it accepted a paired
intent/result edit to the normalized action's task ID, task binding, or frame
ID. It also accepted an extra guard PNG with no trace entry. These are
evidence-completeness gaps in the independent auditor, not observed live v6
dispatches.

The [additive v6a source freeze](odoo-v066-two-frame-v6a-audit-source-freeze-2026-09-29.json)
binds a second read-only audit to the unchanged v6 source freeze. The new
audit first reruns the frozen v6 PNG/target/URL checks, then verifies each
normalized action's task, binding, step, and frame against its durable intent.
It also requires the physical `frames/guard-*` file set to equal the exact
indexed trace set, with no orphan, missing, or symlinked guard file. Offline
mutation tests cover the four action-identity fields and an extra guard PNG.

A v6 raw GUI control may be reviewed only after both the original saved-state
case/batch audit and this supplemental trace audit pass. The supplemental
audit does not itself prove application success, source visual quality, or
official task admission. Any v6 failure remains terminal under its original
run nonce and must be preserved; another attempt requires a fresh candidate
nonce and plan. Official final tasks admitted and model attempts remain zero.
