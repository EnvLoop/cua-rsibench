# Odoo selection lease-prefix amendment (2026-09-29)

This additive v3 source epoch repairs an evaluator-only audit blocker. The
second retained selection incident signed the then-complete worker lease
journal. The third incident and later controls appended legitimate leases to
that same file. Re-running the historical v1 incident auditors changed only
their `worker_lease_events_sha256` output because they hashed the entire
current journal. Their published incident records, saved attempts, and older
source freezes remain unchanged.

The v3 adapter checks the published SHA against an **exact newline-bound
prefix** of the current journal. It requires that prefix to end with the
original attempt's uniquely matched acquire/release pair, whose timestamps
enclose the saved intent and failure. It parses every row in the complete
current journal with duplicate-key rejection, checks the original canonical
JSON encoding, and requires all later rows to form ordered, complete
same-operation/same-PID lease pairs. Only after these checks does it replace
the one mutable whole-journal digest in each historical auditor's derived
dictionary with its published prefix digest and compare every other field
byte-for-byte with the published incident JSON. A changed prefix, malformed
or unpaired suffix, changed saved attempt, or changed public incident fails
closed.

On the retained local selection evidence before any v3 live gate, the second
signed prefix was 1,636 bytes and 14 rows; the third was 2,120 bytes and 18
rows. The current 18-row journal included two complete later leases after
the second incident. The v3 re-audit reopened all three historical incident
auditors with service-state reads stubbed for this **offline source check**.
This does not establish the live service-state gate. The new six-file source
freeze is
`docs/evidence/odoo-v066-lease-prefix-control-source-freeze-2026-09-29.json`.
The current selection evaluator plan audit passed read-only with the original
selection worker and its pinned validator-v0.6.6 historical plan. No v2 or
v3 no-GUI SQL, filestore, or gate receipt existed at this review point.

The v3 no-GUI gate must run on the original stopped selection worker. It
rechecks the retained incidents before and after its exclusive lease, reads
the current SQL snapshot and every physical filestore entry under that
lease, verifies both against the frozen baseline, stops the database, and
writes three new v3-only private receipts. The independent v3 auditor
reopens those receipts and the retained lease prefixes. Only then may the
single v3 evaluator GUI control run. The original v2 output paths are never
reused. There is no automatic replay of any previous failed control.
After a passing gate, run the independent auditor with the same six path
arguments and `--write-public-audit`. It writes the fixed, new public path
`docs/evidence/odoo-v066-current-candidate-selection-no-gui-lease-prefix-gate-audit-2026-09-29.json`
only after its checks pass. The command refuses to overwrite an existing
public receipt.

The following is a command template after the v3 source commit is installed
in the chosen checkout; the worker and historical root are local private
paths and must be supplied by the operator:

```bash
ENVLOOP_ODOO_WORKER_DIR="$WORKER_DIR" \
PYTHONPATH=enterprise_fallback/odoo18:src:. \
"$PYTHON" -m tools.odoo_v066_current_candidate_no_gui_gate_v3 \
  --worker-dir "$WORKER_DIR" \
  --historical-root "$HISTORICAL_ROOT" \
  --private-plan "$WORKER_DIR/private/v066_current_candidate_epoch/selection-20260929.private.json" \
  --public-plan docs/evidence/odoo-v066-current-candidate-selection-evaluator-plan-2026-09-29.json \
  --old-private-plan "$HISTORICAL_ROOT/selection/plan-validator-v066-20260929.private.json" \
  --old-public-plan docs/evidence/odoo-v066-selection-control-plan-validator-v066-2026-09-29.json \
  --execute-baseline-check
```

Before dispatch, verify the exact historical old-plan filename against the
current candidate plan audit's pinned inputs. A passing no-GUI gate is not a
GUI qualification, official final task, model attempt, or researcher
campaign. At this source-only stage the counts remain zero.
