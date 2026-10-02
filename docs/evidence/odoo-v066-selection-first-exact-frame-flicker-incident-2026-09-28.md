# First selection control: exact-frame raster flicker

The first v0.6.6 original Odoo selection control stopped after `case_started`
and three successful source-navigation GUI actions. The fourth action, opening
the native attachment list, never acquired a durable dispatch intent and was
never sent. The controller retained `case_failed`; there is no source-open
evidence, positive saved state, wrong-object negative, independent case pass,
model attempt, or official final admission.

The three bounded pre-intent observations each failed the strict current-frame
digest check. The saved observed and current 1440×1000 PNGs differ only at two
pixels on a tab border: `(41, 419)` and `(132, 419)`, by one blue-channel level.
The images alternate A/B across successive captures. This is a renderer
flicker in the exact screenshot contract, not evidence of changed task data.
The GUI therefore failed closed before opening the attachment.

The read-only incident auditor verified the historical source blobs against
the old freeze, the hash-chained two-row journal, all three dispatched action
intents/results, all three rejected action/frame references, and the absence
of the fourth intent. Saved baseline and restored SQL match the frozen private
snapshot. The saved restored full physical filestore manifest matches the
frozen private manifest. The pre/post restore receipts report exact reset;
selection `db` and `web` are now exited with code 0, and both worker locks are
free. These are saved-state and service checks. A new live SQL/filestore
baseline query has not been performed after lease release.

The original failure and its private screenshots remain intact. A later
retry requires a new dated source freeze, private plan binding, fresh run
directory, and explicit cold-baseline preflight; the old failed journal must
not be rewritten or automatically replayed. The first hidden control should
wait because its adapter uses the same exact screenshot digest check.
See the [field-limited receipt](odoo-v066-selection-first-exact-frame-flicker-incident-2026-09-28.json).
