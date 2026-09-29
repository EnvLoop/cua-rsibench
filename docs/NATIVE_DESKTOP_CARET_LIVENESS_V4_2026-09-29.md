# Prospective Desktop caret-liveness control, v4

The preserved v3 continuation batch stopped during a near-miss evaluator
control after 15 applied GUI actions. Its positive control had passed, but the
near-miss has no saved artifact and no cold-reset control exists for that
logical task. The next selected task was never started. This episode cannot
count as a completed trio or an official final admission.

The [read-only raw-frame audit](evidence/native-wdi-v066-caret-cross-observation-audit-2026-09-29.json)
reopened all 16 receipt-bound drift pairs from the failed attempt. At the
failed action, five independent observation/predispatch pairs had exactly the
same two application images. Their only application difference was a one-pixel
column, 18 pixels high. A later 151-pixel change was entirely in excluded
window chrome. The old adapter sampled for 1.25 seconds within each parse but
never saw the application image return *inside that call*, so its fail-closed
stop was correct under the v3 rule. The five separate observations did show
the original application state again before the identical narrow alternate.

The proposed v4 adapter uses that additional liveness evidence. It first runs
the unchanged v3 bounded exact-return probe. If that fails on a narrow
alternate, the next independent observation must reproduce the original
application pixels exactly, and its direct predispatch screenshot may be only
the same alternate. The action text and step must also be unchanged. This
A→B→A→B sequence proves a live two-state transition without accepting a
persistent one-pixel edit. A third state, changed action, material screen
change, or missing return is rejected. The rule does not branch on task ID or
read the document, oracle, or hidden result.

Five public-train GUI traces independently supply 28 receipt-hash-verified
drift pairs: nine have the narrow-caret shape, while 19 material or other
pairs are rejected. Two separate public-train action steps show a repeated
two-state pair followed by an applied action. Offline unit tests cover the
cross-observation acceptance and persistent-edit, third-state, changed-action,
and material-change rejection. This is training-side corroboration of the
mechanism, not a live v4 success rate.

The [v4 source freeze](evidence/native-wdi-v066-caret-cross-observation-freeze-2026-09-29.json)
reopens the unchanged 35-file historical runtime bundle and hashes the new
adapter, audit, freeze writer, and tests. A private one-use eligibility record
binds the old failed receipt and permits at most one *proposed* fresh complete
trio for that logical ID. It does not authorize a create. The old positive and
partial near-miss remain retained and charged; no old result is rewritten.

Before any paid retry, the v4 adapter must be wired into a new, source-bound
controller and child. That controller must save the A/B/A/B witness and
predispatch frame, use a separate fresh trio root and budget intent, and stop
on any uncertain create. An independent auditor must re-open every raw frame,
recalculate the positive saved-OOXML result, verify the near-miss target-only
failure and no-regression fields, and prove a fresh untouched cold reset.
The six-cell source ratification must then be updated before researcher
campaigns. These steps have not run: v4 paid creates, v4 completed trios,
official final admissions, and model results are all zero.
