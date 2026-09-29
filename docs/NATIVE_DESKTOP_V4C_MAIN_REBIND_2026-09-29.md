# Desktop v4c main-checkout source rebind

This is a source-only integration procedure. The original v4c public freeze
records a prelaunch freeze made in an isolated worktree. Its private record
names that worktree's public path, so copying the original v4c private record
into the main checkout would leave the execution binding wrong. Keep both
original records unchanged. The additive main-checkout freeze below binds the
same v4c source bytes and historical raw evidence to a new private record and
public path. No E2B guest, researcher model, or official final task is created
by this procedure.

The main checkout must contain the two source commits in order: the
cross-observation caret guard, then the bounded untouched-ID continuation.
The evaluator-private directory `work/native-desktop/caret-v4-20260929/` must
contain these exact byte-preserved, mode-0600 files, restored from private
storage:

| File | SHA-256 |
| --- | --- |
| `caret-liveness-audit.private.json` | `c90787fcfd2841005cc8176d7d1727ddff7b02a855b3ed1ad2d1bf13322e4d81` |
| `caret-liveness-source-freeze.private.json` | `5d3f0ad7ce4ee33e9270f98934d3aa4aa98f44f92c808cba3d1d2aa5cb39f67a` |

The private caret records contain no absolute checkout path. The public caret
audit and source freeze from the first source commit bind those two hashes.
The stopped v3 batch, v3 freeze, 35 historical source files, and first eleven
task trees stay in their original locations and are reopened during `prepare`.
The independent raw-frame audit must be rerun in memory on the main source
before preparing the new freeze; compare its private payload excluding only
`recorded_utc`, and compare the public payload excluding its hash of the
timestamped private file. The original raw receipt hashes must remain:
`d3bb43c2b2b73d7e7c038742f639bc9ce88e2c48677c0f9db286ff8294093395`
for stopped batch 2, and
`adf65dcafad13e2c895fe8f3fc0752d9ec13ecc9b3b13d6284010972d2ca101c`
for the failed near-miss receipt. This is a read-only source and evidence
check, not a fresh result.

Run from the main repository root with `PYTHONPATH=src:.` and a Python
environment containing the repository dependencies. `prepare` performs a
read-only E2B active-sandbox check, so the pinned Desktop SDK and a securely
injected `E2B_API_KEY` must be present; never print the credential. An initial
invocation without that key stopped before writing either freeze or creating a
guest. After the byte checks,
write exactly one new main-checkout freeze:

```sh
python -m native_desktop_factory.v066_day_rollover_continuation_v4 prepare \
  --v3-freeze work/native-desktop/v066-day-rollover-final-20260929/bounded-continuation-freeze-v3-20260929.private.json \
  --caret-freeze work/native-desktop/caret-v4-20260929/caret-liveness-source-freeze.private.json \
  --batch-one work/native-desktop/v066-day-rollover-final-20260929/v066-durable-continuation-runs/batch-0001/run-receipt.json \
  --stopped-batch-two work/native-desktop/v066-day-rollover-final-20260929/v066-durable-continuation-runs/batch-0002/run-receipt.json \
  --freeze work/native-desktop/caret-v4-20260929/v4c-main-rebind-untouched-continuation-freeze.private.json \
  --public docs/evidence/native-wdi-v066-untouched-continuation-freeze-v4c-main-rebind-2026-09-29.json
```

The new private freeze must contain absolute paths beneath the main checkout
for `caret_freeze_path` and `public_path`; its `v3_freeze_sha256`,
`v3_batch_one_sha256`, `v3_stopped_batch_two_sha256`,
`caret_freeze_sha256`, and `candidate_inventory_sha256` must match the retained
source evidence. The private freeze remains ignored and mode 0600. Commit and
publish the new public freeze and this correction before any paid dispatch.
The original isolated-path public freeze remains in Git for audit history.

Validate the exact main binding and next untouched selection without a
provider create:

```sh
python -m native_desktop_factory.v066_day_rollover_continuation_v4 plan \
  --freeze work/native-desktop/caret-v4-20260929/v4c-main-rebind-untouched-continuation-freeze.private.json \
  --max-new-ids 1
```

The expected prelaunch readout is eight independently accepted complete
evaluator-control trios, one next untouched ID selected, 58 projected
four-root full-lease intents, and zero official final admissions. A root-owned
paid run, only after the published main freeze and independent source review,
must use the first new run directory
`work/native-desktop/v066-day-rollover-final-20260929/v066-v4-untouched-runs/batch-0001`
and `run --execute --max-new-ids 1`. An uncertain create or failed audit stops
the batch; it must not be restarted automatically. A completed control trio is
still not an official final admission or model result.
