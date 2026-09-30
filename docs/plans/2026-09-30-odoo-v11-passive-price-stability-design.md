# Odoo v11 TRAIN passive price stabilization

The v10 positive route passed and saved its repair; the wrong-object negative
route remained ready but failed before intent because its already documented
four-pixel corner pair changed between the base and first final PNG. The
historical v10 failure remains terminal and its raw artifacts stay unchanged.

V11 uses the same original TRAIN task, wrong-object control, source PDF,
checkpoint, editor-owning-row identity, route token, action grammar, 720-second
wall budget and maximum action count. It has a fresh nonce and separate run
directory. No selection or final environment is involved, and no model is called.

The narrowly changed price parse guard performs at most six passive rounds.
Each round takes three full PNGs. Every PNG must be the observation or the exact
existing v5 four-pixel RGB alternate. Any third/material frame or change in
RFQ, editor, price, target bounds, focus, modal state, task/frame binding, or
URL fails immediately. Between unstable rounds the page waits 40 ms without
input. A successful round requires its base and both final PNGs to be
byte-identical. This adds at most 18 saved parse PNGs and 200 ms of passive wait
per observation, within the existing wall budget and pre-intent observation cap.

The route journal writes the successful token and action intent only after
that parse succeeds. The post-intent dispatch guard is the unchanged v5
implementation. It never waits through an instability or retries a dispatch.
An unstable post-intent frame remains terminal. Successful parse membership
does not authorize a different frame, editor, route or action at dispatch.

The v11 auditor reopens every passive PNG, reconstructs all member labels and
round outcomes, verifies that only the final round is stable, and then applies
the original independent v10 price checker to the identical final triple and
unchanged dispatch receipt. Original action/result bytes are checked before
this in-memory chronology adaptation. Historical source modules remain unchanged.

Source freeze includes the executable v11 runner, router, independent auditor,
original dependencies, this protocol and the v10 terminal audit. Offline
preparation is permitted; the actual Docker run requires a separate root
source/freeze review and exclusive shared-environment availability. A failed
v11 run is terminal under the same one-use rule.

The scoped tests cover both TRAIN phases, unstable-then-stable evidence,
permanent alternation, material pixels, identity changes during passive waiting,
forged or missing raw samples, and post-intent failure without replay. No live
v11 control, model attempt or final-task admission is claimed by source preparation.

## Offline preparation and reviewed execution

```bash
PYTHONPATH=.:src:enterprise_fallback/odoo18 "$PYTHON" \
  -m tools.odoo_v066_train_attachment_calibration_v11 prepare \
  --worker-dir "$TRAIN_WORKER" \
  --accepted-audit docs/evidence/odoo-v066-second-train-pilot-2026-09-28.json \
  --private-freeze "$TRAIN_PRIVATE/v066-attachment-train-source-freeze-v11-20260930.private.json" \
  --public-freeze "$NEW_PUBLIC_V11_FREEZE"
```

After root review and Docker-context release, the same source and freeze paths
may be supplied to `run --execute`. The fresh private run directory is
`v066_attachment_route_calibration/attachment-route-train-pilot-20260930-09`.
Existing v10 or v11 intents are never resumed or reused.
