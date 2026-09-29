# Original Odoo train attachment-route calibration

This is a **train-only evaluator control** for the shared Odoo Community 18
Purchase attachment route. The preserved selection failures are diagnostic
evidence about the route, not inputs to the controller's task choice, action
sequence, source filename, or expected business state. The control uses a
previously frozen train Purchase case and the original train worker; it never
opens a selection or hidden-final task package. It produces no model attempt,
campaign result, selection admission, or official-final admission.

The existing accepted train pilot proves that the native PDF viewer, one
known-answer price repair, a distinct wrong-RFQ mutation, saved SQL verifier,
physical source files, and cold reset can work together. The new calibration
must repeat those phases in one fresh immutable train attempt while checking
the attachment-link dispatch more precisely. Its actor action is still a
coordinate click from a 1440×1000 current screenshot. At observation time the
evaluator records the **visible exact PDF filename, unique hit-tested element,
bounding box, parent RFQ URL and task/frame binding**. The tray item has no
independently observed resource URL in the retained failure trace; the native
PDF frame, source asset and physical attachment bytes are checked separately.
At parse and again immediately
before click, it accepts an exact observed PNG or only the previously frozen
two-pixel noninteractive border alternate after bounded samples. Two final
physical PNGs must agree; the target element, filename, bounds, URL, task and
frame must remain identical. An absent or ambiguous link, altered PDF label,
third pixel state, changed hit target, or uncertain post-intent dispatch fails
closed. This rule is written for the route and visible filename, never for a
selection identity or business answer.

Before any Docker call, freeze the adapter, runner, independent auditor,
existing source/checkpoint digests, original worker `.env` and Compose file,
train task package and output nonce. The runner writes a durable train-only
intent and waits for native PostgreSQL health plus verifier `SELECT 1`
before its first business snapshot. It then uses the original Odoo GUI to
open the attachment tray and PDF, save a positive business repair, mutate a
separate RFQ, and cold-restore. A separate read-only audit reopens every
frame/action/guard reference; independently derives baseline 0, positive 1,
wrong-object 0 and exact reset from SELECT-only SQL, full physical filestore,
protected attachment store paths and the frozen source asset. The full
post-web physical filestore manifest must also match the frozen manifest
exactly; any extra file fails this calibration. A distinct
visual reviewer inspects the saved native PDF frame. The run is terminal on
any post-intent failure; no automatic retry or selection continuation occurs.
The new auditor re-derives the PDF-link guard and every action/frame/intent
binding. For other RFQ actions it retains and reopens v5/v6 guard images and
results, but does not re-derive every non-link guard classification. This
calibration is a route check, not a blanket v5/v6 certification.

Two other paths were considered: broadening v6 for selection now would fit a
failed evaluator identity, while using the old exact-only train adapter would
not test the recurring border alternate. This isolated train calibration
keeps the selection cohort sealed until a source-neutral rule has real native
evidence.

The [public pre-Docker source freeze](../evidence/odoo-v066-attachment-train-source-freeze-v3-2026-09-29.json)
binds the runner, route guard, independent auditor, original task/checkpoint
dependencies and a mode-0600 private train binding. The corresponding private
freeze is stored in the original train worker and is mode-0600. The offline
freeze check passed. The live command remains gated on release of the shared
`colima-cua-scale` Docker context.

The earlier [v2 offline source freeze](../evidence/odoo-v066-attachment-train-source-freeze-v2-2026-09-29.json)
is retained as source-only history. It was superseded before any Docker or GUI
action because its adapter did not preserve v6 border handling for non-link
RFQ actions. Only the v3 freeze below is eligible for a live train control.

Set `ENVLOOP_ODOO_WORKER_DIR` to the original train worker and run with the
repository Python and `PYTHONPATH=enterprise_fallback/odoo18:.:src`:

```bash
export ENVLOOP_ODOO_WORKER_DIR=/path/to/original-odoo/partition_workers/train
python -m tools.odoo_v066_train_attachment_calibration_v1 run \
  --worker-dir "$ENVLOOP_ODOO_WORKER_DIR" \
  --accepted-audit docs/evidence/odoo-v066-second-train-pilot-2026-09-28.json \
  --private-freeze "$ENVLOOP_ODOO_WORKER_DIR/private/v066-attachment-train-source-freeze-v3-20260929.private.json" \
  --public-freeze docs/evidence/odoo-v066-attachment-train-source-freeze-v3-2026-09-29.json \
  --execute
```

Only a fresh raw run with one link dispatch, positive save, wrong-object
negative and exact reset can proceed to a distinct visual source review and
the read-only `audit_odoo_v066_train_attachment_calibration_v1` gate. The
source freeze, unit tests and offline train package checks alone do not admit
selection candidates or validate the link in a live browser.
