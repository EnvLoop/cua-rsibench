# Third selection control: validator-version mismatch before dispatch

The third same-ID original Odoo selection control passed its separate
current-SQL/full-filestore gate, opened the native supplier PDF, and completed
eight GUI actions. Two pre-intent stale-frame observations at the source
attachment step were recorded and recovered. The next intended action was a
double-click in the purchase-line quantity editor. Its intent was durably
saved, but no step-8 dispatch-guard sample, mouse result, positive saved-state
readback, or negative phase exists.

The [independent read-only audit](odoo-v066-selection-third-validator-mismatch-2026-09-29.json)
reconstructed the saved step-8 model-visible observation: 79 controls, a
unique matching visible/enabled input control, matching frame ID, and a target
point inside its saved bounds. The frozen actor source imported the **base
v0.6 action validator** before dispatch. Offline replay of the saved action
returns `invalid_action` from that validator, while the intended v0.6.6
extension accepts the same `double_click`. The failure is an actor validator
import error, not a rejection by the independent saved-state auditor or a
changed target. It occurred before the physical dispatch exception could run.

The auditor reopened the source freeze against the actual run commit (24/24
source hashes), 20 selection task bindings, cold-baseline gate, 8 action
intent/result pairs, the failed intent, journal chain, worker lease, and
saved reset. Baseline and restored SQL match across 13 business snapshot
sections. The saved current and restored full physical filestore manifests
match the 888-entry frozen manifest. Both selection services are exited with
code 0 and worker locks are free. A live post-exit Docker-volume rescan was
not performed.

All three failed attempts remain terminal and unmodified. This third
journal's two rows contain the batch-intent SHA-256, unlike the first two
journals, so the records here distinguish this batch. The batch identifier is
content-addressed; it is **not** a random run nonce and cannot guarantee
uniqueness if identical batch-intent bytes are reused. The failure row does
not directly include the failure-receipt hash, so the attempt directory and
its private receipt remain necessary context.

A dated source correction should use the v0.6.6 validator before dispatch and
prove the frozen GUI action-type sequence through a fake adapter boundary.
Any later same-ID attempt would require a new source freeze, fresh private
plan and run directory, and a separate current-SQL/full-filestore authority.
No further GUI attempt or official/model result is claimed. Live work is
paused while the host is on battery power.
