# Native forward child edges

The actual V35 diagnostic retained an owned frame and a refused-hit frame with
different native bus/object identities. Both returned empty relation sets.
Measured X11 frame extents exactly explain the owned frame's decorated box,
but do not associate the second frame. The original refusal is preserved.

V36 reads the actual owned frame's forward `get_child_at_index` edges. It checks
whether the exact refused-hit identities are reachable through those returned
edges, even when reverse `get_parent` reports another frame. Native bus/object
identity determines matches. PID, similar geometry, titles and screenshots do
not substitute for a returned edge. This diagnostic grants no actor ownership
or qualification and does not change the preserved reader.

The read is bounded to 48 nodes, 64 children per node and three edges of depth.
Large virtual collections, unknown identities, unavailable children and
exhausted budgets remain explicit partial evidence. No node names, document
text, cell values or GUI actions are read. Every returned edge is retained in
an exclusive private journal before later traversal. The whole command retains
the existing 45-second command and 55-second request bounds.

Four source tests cover exact returned paths, unreachable foreign identity,
large virtual collections without enumeration, cycles, depth/node budgets and
unavailable children. They are source checks, not native qualification.

The helper is source-pinned to the corrected V35 reader. A separately reviewed
fresh public TRAIN guest uses the same common bootstrap/source setup, then one
read-only command:

```bash
GI_TYPELIB_PATH=/tmp/envloop-atspi-v25 python3 /tmp/envloop-native-common-v31/native_child_graph_diagnostic_v36.py --filename ACTUAL_OWNED_TRAIN.xlsx --width 1280 --height 800
```

The fixed guest journal is `/tmp/envloop-native-child-v36-facts.private.jsonl`.
Native readback must verify bytes, hash and actual mode, including partial
failures. Owned cleanup remains mandatory. No guest is authorized by this file.
