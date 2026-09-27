# GitLab visible-save control calibration — 2026-09-27

The evaluator-private GitLab GUI sweep retained a cross-record issue-triage control with scores **1/0/0**. Its repeated positive displayed the requested due date while the Dates panel still showed a save spinner; immediate independent PostgreSQL readback found the baseline due date. The control remains **failed** in the private append-only ledger and in the attempted denominator. It was not retried or converted into a model result.

A separate **training-partition** issue reproduced the display timing: the date appeared while the Dates spinner was present. After the spinner cleared, a page reload retained the date and independent PostgreSQL readback matched the target. The qualification operator now waits up to 30 seconds for each Assignee, Labels, and Dates save spinner to disappear, reloads the issue, and requires the date to remain visible before taking its saved-state snapshot. The exact new helper passed a fresh training-partition GUI probe and a cold reset back to the frozen business baseline. Screenshots, issue identities, and raw receipts stay in evaluator-private storage.

This repair applies only to later untouched candidate IDs. It establishes a more reliable deterministic admission control, not Qwen solvability, an official final admission, or runner execution.
