# Native Desktop bounded manifest transfer

The v16 first positive control stopped before GUI actions while downloading
the compressed guest manifest. Its probe command exited successfully, but its
byte read hit the SDK's default 60-second timeout. The failed raw receipt keeps
`cleanup_unverified`; a separate provider listing found no active guest. The
consumed intent still reserves its complete 1,200-second server lease.

The additive v17 worker intercepts only the exact compressed-manifest byte
read. It requests `format='stream'` once with an explicit 180-second SDK
request deadline, checks a monotonic 180-second bound, rejects more than 8 MiB
of compressed bytes, and owns the reader with a context manager. Success,
size overflow, clock expiration and stream errors all release the reader.
There is no wrapper HTTP, create, action or intent retry. Every other file
read and write preserves its existing arguments. The pinned E2B 2.51.0 source
provides the stream iterator, close method and context-manager protocol.

Provider `get_info` and `is_running` requests receive the same 30-second bound
for controls, the shared base and all four checkpoint slots. Model cleanup is
consumed before its first kill/status acknowledgement; a later `finally` call
returns the retained result without another HTTP operation. A longer bound
is a transport proposal; it does not establish that the previous timeout is
fixed. Sandbox leases stay at 1,200 seconds, probe command/request limits stay
at 450/480 seconds, and actors retain 90 actions and 720 seconds. The guest
probe, structural attestation, GUI executor, task packages and scorer are
unchanged. Model slots bind the identical transport recipe and source hash.

The new control entry wraps `Sandbox.create` before entering the v16 context.
The v16 attesting command wrapper therefore captures the bounded inner guest,
so its unchanged `capture_result` uses the stream wrapper. This order is
covered by a test that reaches the inherited worker's actual create and probe
entry with a fake provider, downloads once and stops before GUI setup.

The v17 source freeze requires a fresh attempt root and permit. It retains
all v16 failed-attempt files, the closed source stage, the exact external
provider reconciliation and the original full lease. Parent validation omits
only the new v17 root at this layer; v16 applies its established own-root
exclusion. Current v17 history includes the closed v16 intent. Changes to
historical metadata, source files or reconciliation bytes fail validation.
The same frozen 20 selection and 100 final candidates receive new trios;
historical controls carry no admission credit.

The verified v16 neutral identity proof remains evidence for the unchanged
probe and verifier. This source-only proposal has no fresh live neutral
transfer proof, GUI controls, model calls or official model results.

After root review and import, use the pinned native SDK Python to prepare a
new source freeze, inspect `plan`, write one permit with `review`, then run
one trio. Substitute fresh private paths at each placeholder.

```sh
python -m native_desktop_factory.selection_control_bounded_epoch_v17 prepare \
  --parent-freeze <closed-v16-freeze> --reconciliation <v16-provider-reconciliation> \
  --attempts-root <fresh-v17-attempt-root> --freeze <new-v17-private-freeze> \
  --public <new-v17-public-freeze>
python -m native_desktop_factory.selection_control_bounded_epoch_v17 plan \
  --freeze <new-v17-private-freeze>
python -m native_desktop_factory.selection_control_bounded_epoch_v17 review \
  --freeze <new-v17-private-freeze> --permit <new-v17-first-trio-permit>
python -m native_desktop_factory.selection_control_bounded_worker_v17 \
  --freeze <new-v17-private-freeze> --permit <new-v17-first-trio-permit> \
  --enable-paid-controls
```

The public-TRAIN pilot's existing prepare/review/run entry now validates this
same v17 epoch and binds the bounded transport. Its output root must remain
outside all historical accounting roots. Full study admission continues to
require all 120 completed current trios and the authentic six-cell freeze.
The TRAIN pilot is diagnostic and has no settled invoice or official result.

Offline tests cover exact file-call forwarding, success, overflow, acquisition
and iteration timeouts, stream errors, reader closure, no replay, nested
ancestral accounting, historical byte mutation, the inherited control entry,
and uniform create/read/status behavior across all five actual model slots.
