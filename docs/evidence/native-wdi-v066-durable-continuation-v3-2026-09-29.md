# Durable Desktop continuation amendment — 2026-09-29

The v2 bounded continuation correctly retained seven independently audited
positive/near-miss/reset trios, quarantined two interrupted task IDs, and
selected only the remaining 91 never-intended IDs. An injected pre-dispatch
failure exposed a durability gap: the frozen controller wrote a create intent
without `fsync`, and the frozen paid child wrote its receipt without `fsync`
before `Sandbox.create`. The v2 source and public freeze remain preserved as
the historical proposal; v2 is superseded for new paid dispatch by this v3
amendment.

The additive v3 controller leaves the original 35-file evaluator, actor
scripts, saved-artifact scorer, and seven accepted trios byte-identical. For
each new attempt it checks the dedicated Python/SDK versions, credential
presence, host power source, provider active-zero, four-root full-lease budget,
and raw-frame storage readiness. It writes and synchronizes a private budget
receipt and create intent, including their directory entries, before starting
the child. The new child adapter invokes the original paid evaluator while
synchronizing every `receipt.json` update before the evaluator advances. The
precreate intent binds the adapter source hash. A separate read-only audit
reopens each new budget, intent, and receipt in source order; the existing
independent audit still reopens saved Office artifacts, raw frames, profile
captures, near misses, and resets.

Only one or two untouched task IDs may run per root-owned batch. The child
runs in its own process group; timeout or a catchable root interruption
terminates that group. An uncertain attempt leaves its full ten-minute lease
charged and stops the batch. A missing terminal journal, active provider guest,
or incomplete task directory blocks any automatic continuation. The two
quarantined task IDs still require a separately frozen sidecar protocol and
are not authorized here. No model run, official final admission, or actual
provider bill is inferred from evaluator controls.

The unchanged planning arithmetic is 26 historical leases plus 24 current
first-attempt leases plus 273 prospective leases for 91 untouched trios:
323 full ten-minute leases, or $53.83333333333333 at the conservative
$1/hour rate. The conditional six-lease sidecar for the two quarantined task
IDs would bring the count to 329 and $54.83333333333333; it is not part of
this dispatch authority.

Before any paid launch, create a private v3 source freeze and its English
field-limited public counterpart from the root checkout. The root process
must retain its live terminal handle; an observation timeout is not a reason
to start another batch. The private credential must be injected without
printing it, and the pinned Python must provide `e2b-desktop==2.2.0`,
`e2b==2.51.0`, and `Pillow==11.3.0`.

```bash
PYTHONPATH=.:src python -m native_desktop_factory.v066_day_rollover_continuation_v3 prepare \
  --base-freeze work/native-desktop/v066-day-rollover-final-20260929/bounded-continuation-freeze-v2-20260929.private.json \
  --freeze work/native-desktop/v066-day-rollover-final-20260929/bounded-continuation-freeze-v3-20260929.private.json \
  --public docs/evidence/native-wdi-v066-bounded-continuation-freeze-v3-2026-09-29.json

PYTHONPATH=.:src python -m native_desktop_factory.v066_day_rollover_continuation_v3 plan \
  --freeze work/native-desktop/v066-day-rollover-final-20260929/bounded-continuation-freeze-v3-20260929.private.json \
  --max-new-ids 1

PYTHONPATH=.:src python -m native_desktop_factory.v066_day_rollover_continuation_v3 run \
  --freeze work/native-desktop/v066-day-rollover-final-20260929/bounded-continuation-freeze-v3-20260929.private.json \
  --run-dir "$PWD/work/native-desktop/v066-day-rollover-final-20260929/v066-durable-continuation-runs/batch-0001" \
  --max-new-ids 1 --execute
```

The v3 source freeze and paid run are separate events. Source preparation
queries provider active state but creates no sandbox. The `plan` command is
offline and creates no sandbox. The `run --execute` command is the sole paid
entry point. The run directory must be absolute: the frozen controller compares
it to the absolute parent of the private attempts root. The first root-owned
invocation with the earlier relative path stopped at this path check before
creating a batch directory or any E2B intent; no provider work was replayed.
