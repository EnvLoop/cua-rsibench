# Desktop evaluator interruption and bounded continuation — 2026-09-29

**Dispatch amendment:** The [v3 durable continuation](native-wdi-v066-durable-continuation-v3-2026-09-29.md)
supersedes this v2 launch procedure for any new paid E2B create. The v2
source and freeze remain retained as pre-result historical evidence.

The published date-amended 100-task E2B controller stopped without a terminal
journal marker. The [field-limited interruption receipt](native-wdi-v066-orphan-interruption-2026-09-29.json)
binds the private evidence. Its last durable journal remains `started` after seven
completed task trios. There are 24 full-lease create intents and 24 receipts:
seven positive/near-miss/cold-reset trios have verified teardown, one further
positive control has verified teardown, and two in-flight GUI receipts lack
teardown confirmation. The two interrupted leases are retained as
infrastructure-invalid first attempts. One had a partial near-miss edit; the
other had saved a scripted positive artifact and fair verdict but never
completed teardown. Neither is counted as a valid control or a model result.

The provider initially listed two active sandboxes matching the two pending
receipt hashes. At the evaluator-owned teardown check both ten-minute leases
had expired; the account listed zero active sandboxes, so no kill call was
made. A separate private teardown intent and reconciliation receipt were
fsynced. The original attempt bytes remain unchanged, and a read-only ledger
audit reopened all 1,435 raw evidence rows. The [seven-trio independent
audit](native-wdi-v066-day-rollover-seven-completed-audit-2026-09-29.json)
accepted seven positive artifacts, seven target-failing near misses, and seven
fresh resets from 21 distinct guests. The process exit code is unavailable.
No September 29 Python crash report or PID-specific unified-log entry was
found. The journal progressed after the subagent's earlier turn ended, so
immediate turn-end teardown is excluded; a later session cleanup, host kill,
or uncaught process failure cannot be distinguished from the retained data.

The [current additive continuation freeze](native-wdi-v066-bounded-continuation-freeze-v2-2026-09-29.json)
retains all 24 charged leases and the two invalid attempts. It authorizes
only the 91 **never-intended** task IDs, in source order, with at most two new
IDs per root-owned invocation. Before a create, it reopens the original
run/teardown receipts, verifies the first nine task directories, all saved
artifacts and raw frames, the 35-file frozen paid child, account active-zero,
and the four-root budget. Each completed trio is independently audited before
another ID. The v2 controller checks the dedicated E2B SDK versions and
credential before recording a new intent; the earlier offline v1 source
freeze is preserved as a superseded proposal and authorizes no paid launch.
An uncertain attempt stops the lane; no automatic replay or
same-ID retry is authorized here. The 91 IDs project 273 new leases; with the
original 50 across all roots, this is 323 full leases or $53.83333333333333
at the conservative $1/hour planning rate. Actual provider billing is unknown.

A [dated conditional eligibility receipt](native-wdi-v066-conditional-retry-eligibility-2026-09-29.json)
was frozen at provider active-zero before any retry create. A one-time,
fresh-clone retry of the two quarantined logical task IDs is
**conditionally defensible as evaluator-only pre-result recovery**: no model
sample or researcher checkpoint was produced, the task/score source would
remain frozen, both first attempts stay invalid and charged, and the scripted
positive verdict stays evaluator-private. It is not authorized by this
continuation freeze. A separate dated sidecar-root bridge, explicit one-time
retry intents, source freeze, and cross-root independent audit must be
published before either retry create. Six additional full leases would bring
the all-root projection to 329 leases or $54.83333333333333, below the existing
$60 planning cap. No final task admission or model outcome is claimed.

After this source and public freeze are published and independently checked on
the root checkout, a root-owned process can make a short bounded run. `python`
below must be the dedicated environment with `e2b-desktop==2.2.0`,
`e2b==2.51.0`, and `Pillow==11.3.0`, with the private E2B credential supplied
through the host environment:

```bash
PYTHONPATH=.:src python -m native_desktop_factory.v066_day_rollover_continuation_v2 plan \
  --freeze work/native-desktop/v066-day-rollover-final-20260929/bounded-continuation-freeze-v2-20260929.private.json \
  --max-new-ids 1

PYTHONPATH=.:src python -m native_desktop_factory.v066_day_rollover_continuation_v2 run \
  --freeze work/native-desktop/v066-day-rollover-final-20260929/bounded-continuation-freeze-v2-20260929.private.json \
  --run-dir work/native-desktop/v066-day-rollover-final-20260929/v066-continuation-runs/batch-0001 \
  --max-new-ids 1 --execute
```

No paid continuation create has occurred at publication of this protocol.
