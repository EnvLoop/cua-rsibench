# Native Desktop Save readiness

The closed v19 positive attempt applied 21 GUI actions, then rejected the
observation for step 21 as material drift. Its preceding input was the frozen
generic Save tail's `Control+S`; the pending action was a 2,000 ms wait. Their
payload hashes match the retained receipt and caret-probe record. The pending
wait did not dispatch. The failed receipt, successful teardown and complete
1,200-second lease remain unchanged.

Both retained frames were visually reopened. Each shows the same Confirm File
Format dialog. Pixel readback found 556 changed pixels with an aggregate box
from (138, 59) to (1269, 480), spread over widget glyphs and the checkbox rather
than one contiguous caret. The most common changes increment gray channels by
one. The original caret classifier correctly returns false. A Save-dialog
paint or focus transition is an inference from these two frames; the native
modal ID was not captured for this comparison. No tooltip, text or geometry
change was visible. This evidence does not justify accepting either stale
frame or masking any region.

The thin v20 adapter adds `Control+S` to the existing passive readiness trigger
predicate. It reuses the original v18 capture, settled-suffix and audit bodies.
Seven full native PNGs, the same delay sequence, the same visible-window
identity checks, four final exact or original narrow-caret frames, and the
existing 60-second component limit remain mandatory. The final full PNG is
returned unchanged. Exact current-frame parsing and material rejection remain
unchanged. A new Save input or action retry is never used to settle the UI.

Controls and all five model slots bind this identical trigger recipe and
source hash. V19 Enter capture retains its existing 60-second bound. Actors
retain 90 actions and 720 seconds, and server leases remain 1,200 seconds.
The transfer, cleanup, guest probe, TLS state, native profile, SDK pins, task
packages, control script and saved-state scorer are unchanged.

A fresh v20 source epoch preserves all 130 closed v19 attempt files, its source
stage, failed probe and exact receipt. Historical accounting retains the full
lease. Parent validation excludes only the fresh root at this layer. The same
20 selection and 100 final candidates require new trios, with no historical
control credit and no consumed-intent replay. The existing v16 neutral runtime
identity proof remains attached to the unchanged probe and verifier.

Offline tests show that the original direct parser rejects a material Save
transition. After one Save input, the shared adapter captures seven full frames
and returns the stable final frame for a new exact parse in all five actual
model guest paths. Unstable suffixes, native identity changes and material
changes after the observation still fail. Tests also reach the actual
inherited control create entry once through a fake provider. Source-only
validation against the real parent and a newly appended intent passed. No
provider, model or native call was made; new live success remains unverified.

After root review and import, use the pinned native Python with fresh paths.

```sh
python -m native_desktop_factory.selection_control_save_epoch_v20 prepare \
  --parent-freeze <closed-v19-private-freeze> --attempts-root <fresh-v20-attempt-root> \
  --freeze <new-v20-private-freeze> --public <new-v20-public-freeze>
python -m native_desktop_factory.selection_control_save_epoch_v20 plan \
  --freeze <new-v20-private-freeze>
python -m native_desktop_factory.selection_control_save_epoch_v20 review \
  --freeze <new-v20-private-freeze> --permit <new-v20-first-trio-permit>
python -m native_desktop_factory.selection_control_save_worker_v20 \
  --freeze <new-v20-private-freeze> --permit <new-v20-first-trio-permit> \
  --enable-paid-controls
```

The existing public TRAIN pilot then prepares one fresh diagnostic against
this same v20 control freeze after the trio is terminal. Its separate permit
and output root remain outside every historical accounting root. It receives
actual model responses and contributes zero official model results.
