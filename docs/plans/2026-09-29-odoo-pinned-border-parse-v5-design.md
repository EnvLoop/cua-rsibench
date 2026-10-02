# Odoo pinned-border parse amendment v5

## Observed failure and boundary

The original current-candidate selection attempt is terminal. Its independent
[failure audit](../evidence/odoo-v066-current-candidate-first-gui-terminal-failure-audit-2026-09-29.json)
binds the raw journal, three preceding GUI actions, three pre-intent rejections,
18 physical guard samples, exact SQL and full-filestore reset, stopped services,
and released worker lease. At the source-document attachment click, each of
three model observations alternated against the same physical image. The two
images differ only at RFQ tab-border pixels `(41,419)` and `(132,419)`. The
click target was outside those pixels. Each observation saw six stable samples
of the other image, so exact screenshot equality in `parse_current_action`
failed before a step-3 intent or dispatch. The existing pinned-border exception
applies only at dispatch. It was never reached. This is a frame-equivalence
liveness failure, not a demonstrated task repair or a model outcome.

## Decision

Add a **new adapter subclass** and dated source epoch; leave the frozen v4
adapter, evaluator, failed run, and evidence untouched. A longer exact-return
wait can still fail whenever the alternate remains stable. Globally masking
pixels would silently relax every action and route. The new exception is
limited to a purchase RFQ `click` on a visible control outside the two border
pixels, with no third image and no business-state mutation before intent.

The v5 parse path first runs the inherited exact-return check. If that fails,
it accepts only six consecutive samples with one identical alternate PNG,
each independently differing from the observed PNG at exactly the two pinned
pixels with the pinned RGB transition. It verifies the task binding, frame ID,
current URL, purchase RFQ route, and action shape. It normalizes the action
against the original observation and checks that the click point resolves to
one enabled visible control in the observation's control list. Two current DOM
reads must agree on the control's ref, role, label, bounds, and purchase-RFQ
view marker; neither bounds nor click point may touch the border pixels. A
final physical PNG and URL check must still match the six-sample alternate.
Any failed check raises `stale_frame` before an intent is written. The parse
receipt records private hashes and bounded control geometry for independent
audit; it does not enter model-visible content.

The original dispatch guard still runs after the durable action intent. It
rechecks the physical screenshot, URL, target control, and pinned-border
equivalence immediately before the click. No action is replayed after intent,
even if this second check fails. The v5 journal and auditor must bind the
parse receipt to the observed screenshot, action, physical samples, and
eventual dispatch result. They must reject a parse exception without a
matching dispatch guard or a dispatch without a parse exception.

## Epoch, execution, and acceptance

Create a new source-only freeze covering the v5 adapter, runner, plan builder,
and independent auditor. The new private/public evaluator plans bind that
freeze, the passed v4 no-GUI baseline gate, the terminal failure receipt,
and a fresh random run nonce. The same underlying selection task may be
chosen for a **new candidate attempt** because the failed one had no step-3
intent or dispatch; the old run directory, nonce, and attempt remain immutable.
The new run uses a distinct directory and durable pre-service intent. The
current candidate remains evaluator-only: no SFT row, campaign, or official
final admission follows from source freezing or a single GUI control.

Offline tests must cover exact-frame behavior, the allowed two-pixel
alternate, a third pixel, changed URL or task binding, changed target-control
identity or geometry, target overlap with the border, and a changed final
physical PNG. Run the independent source/failure/gate audits and publish the
limited freeze **before** the next GUI attempt. Once `cua-scale` is free, one
supervised same-task new-candidate attempt must show source-document GUI
readback, baseline reward `0`, positive `1`, wrong-object negative `0`, and
exact cold reset. Preserve and audit any failure without automatic replay.

The existing v4 gate and terminal failure audits remain independently
re-runnable. A successful v5 one-case control is still review-pending until
its source image and saved artifact are checked; it does not amend historical
results or authorize the 100-case final cohort.
