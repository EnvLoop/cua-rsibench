# v0.6.6 validator correction after third selection failure

The third same-ID selection attempt remains a terminal failed control. Its
[independent incident audit](odoo-v066-selection-third-validator-mismatch-2026-09-29.json)
reopened the saved step-8 observation and proved that the base v0.6 action
validator rejects the intended `double_click` as `invalid_action`, while the
v0.6.6 extension accepts it. The import was corrected only in the new
Odoo pinned-border adapter's pre-dispatch validation path. The actor's
physical-frame rule, model-visible contract, and earlier attempts were not
rewritten.

The regression replays the entire frozen selection action-type sequence
through a fake adapter dispatch boundary: `type`, `key`, five `click`
actions, `wait`, and the failed `double_click`; a separate `finish` branch is
also checked. The test asserts that this adapter imports the exact v0.6.6
validator. No Docker, GUI, provider, or model call is made by the test.

A possible later attempt uses a new source freeze and split-local private
plan. Its separate no-GUI preflight must independently re-audit all three
retained failures, query the **current** SQL and full physical filestore under
the original selection worker lease, require exact frozen-baseline equality,
and restore the prior stopped service state. Only then may it create a fresh
immutable private gate. The previous gates and three failed run directories
are never reused or overwritten. The new batch intent includes a random
128-bit run nonce; its SHA binds each journal row. A failed journal row also
binds its private failure-receipt SHA, when that receipt exists.

The [dated source freeze](odoo-v066-scale-validator-v066-source-freeze-2026-09-29.json)
and field-limited [selection](odoo-v066-selection-control-plan-validator-v066-2026-09-29.json)
and [hidden](odoo-v066-official_hidden-control-plan-validator-v066-2026-09-29.json)
plans prepare the source-only lane. The earlier pinned-border and RFQ-view
freezes are preserved as pre-dispatch revisions. No fourth GUI attempt,
hidden task, model call, or official final admission is claimed. Live work
remains paused until AC power is verified.
