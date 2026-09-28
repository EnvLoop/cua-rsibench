# First original Odoo v0.6.6 train pilot: preserved failure audit

The first current-source train GUI pilot failed and remains preserved. The
independent offline receipt uses schema
`envloop-odoo-v066-failed-train-pilot-source-bound-audit-v1` and status
`source_bound_failed_train_pilot_pre_intent`. It admits zero official final
tasks and records zero model attempts. No SFT candidate file exists in this
attempt.

The audit binds the old public code freeze, the old private train-only plan and
pilot binding, and the attempt's start and failure receipts by SHA-256. It
loads the recorder, verifier, and pilot-auditor bytes from the fixed Git commit
`0f31866c72eb2c36a61313c27531983f636f438f`, then checks all source hashes
in the frozen plan. Its public JSON contains only aggregate results and hashes;
it contains no private task value, target state, secret, or local source location.

The saved trace has 16 matched action intents and dispatch results: 12 in the
positive phase and four in the negative phase. Each is linked to the saved
assistant action, rendered instruction, visible text, screenshot bytes, frame
ID hash, contract receipt, and trace row. A seventeenth screenshot and
assistant action are saved, with no corresponding intent or result. The frozen
recorder writes those files before parsing the action and writes the durable
intent only after parse succeeds. This supports a failure before the final
action intent or GUI dispatch. The failure receipt says `ContractError` at
`negative_gui`; it records no specific error code or message. The exact
contract subtype, including any reported stale-frame explanation, is therefore
unverified by the preserved receipt.

The positive SQL snapshot scores 1.0 when rerun through the pure purchase
evaluator functions extracted from the frozen verifier source. All 16
protected source attachments match the frozen filestore manifest, and their
saved storage locations match the baseline. The saved post-reset SQL equals
the frozen baseline, protected source files still match, and the reset receipt
reports exact restoration. The failure receipt reports that the original
service state was restored. Live service state is not independently observed
by this offline audit. No negative saved-state snapshot exists, so this failed
attempt is not a complete positive/negative pilot qualification.

The auditor prints the public JSON receipt to stdout and performs no write to
the train worker. Its integration tests run against the preserved bytes when
the three private evidence locations are supplied in environment variables;
they reject a changed frozen recorder source and a tampered dispatch result.
