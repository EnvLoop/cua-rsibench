# Native Desktop passive-readiness bound

The v17 first positive attempt downloaded and retained the complete compressed
guest manifest and passed the unchanged structural identity check. It then
applied seven GUI actions and stopped during passive capture before the next
observation. Its failed receipt and successful teardown remain unchanged.
The complete 1,200-second intent remains charged to historical lease accounting.

Independent readback verified all six retained PNGs against their full and
application hashes. All six are byte-identical; their last four samples have
no material or caret difference. Native window identities are unchanged.
Elapsed capture times were 4.636, 9.664, 15.917, 22.059, 26.892 and 31.169 seconds.
The sixth sample crossed v12's 30-second component limit. No seventh PNG was
captured, and no stable seven-frame readiness result was returned.

The v18 readiness source copies v12 byte for byte except for
`MAX_WALL_MS = 60_000`. It preserves seven samples, the original delay sequence,
exact window checks, the final four-frame material/caret test, the raw final
PNG and exact current-frame dispatch. It adds no action, retry or pixel mask.
A 60-second component bound is supported by measured capture latency; a fresh
live run is still needed to establish success. Actors retain 90 actions and
720 seconds, and each server lease remains 1,200 seconds. The v17 stream
transfer and one-shot cleanup, v16 guest probe, TLS state, tasks, scorer and
SDK pins are unchanged.

The new source epoch requires a fresh attempt root and one-use permit. It
reopens all closed v17 files, its six PNGs, source stage and teardown. Parent
validation excludes only the fresh v18 root at this layer; each ancestor keeps
its established own-root exclusion. Current history includes the closed v17
full lease and its raw failed result. The same 20 selection and 100 final
candidates require fresh control trios. Historical failures receive no control
credit. The actual v16 neutral identity proof is retained for the unchanged
probe and verifier.

Controls and all five model slots bind the same v18 readiness recipe and
source hash. Model actor time includes passive readiness. The public TRAIN
pilot uses this same transport after the control trio is terminal; its result
remains diagnostic with zero official model results.

Offline tests replay the exact six measured capture durations. The old bound
rejects after six samples. The new bound accepts only with a synthetic seventh
stable frame and still rejects missing frames, material drift, native identity
changes, bad clocks and durations over 60 seconds. Tests also reach the real
inherited control create entry once through a fake provider and verify full
frame observations for all five model slots. This source proposal performs no
provider, model or native call and proves no new live control success.

After root import and review, use the pinned native Python for these entries.
Each placeholder denotes a fresh path except the closed parent freeze.

```sh
python -m native_desktop_factory.selection_control_readiness_epoch_v18 prepare \
  --parent-freeze <closed-v17-private-freeze> --attempts-root <fresh-v18-attempt-root> \
  --freeze <new-v18-private-freeze> --public <new-v18-public-freeze>
python -m native_desktop_factory.selection_control_readiness_epoch_v18 plan \
  --freeze <new-v18-private-freeze>
python -m native_desktop_factory.selection_control_readiness_epoch_v18 review \
  --freeze <new-v18-private-freeze> --permit <new-v18-first-trio-permit>
python -m native_desktop_factory.selection_control_readiness_worker_v18 \
  --freeze <new-v18-private-freeze> --permit <new-v18-first-trio-permit> \
  --enable-paid-controls
```
