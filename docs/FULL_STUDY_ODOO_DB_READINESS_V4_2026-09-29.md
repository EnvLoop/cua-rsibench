# Odoo no-GUI database-readiness amendment (2026-09-29)

The first v3 no-GUI gate reached the original selection worker's exclusive
lease, started PostgreSQL, and exited before writing any gate, SQL, or
filestore result. The lease acquired/released pair is complete. A local
read-only audit matched the three retained incident hashes to the unchanged
selection plan. The root operator observed both original worker services
stopped and PostgreSQL logging readiness immediately before a fast shutdown.
The [limited incident receipt](evidence/odoo-v066-v3-no-gui-db-readiness-incident-2026-09-29.json)
separates those observations from the inference of a readiness race; the
exact psql error text is unavailable. This is not a GUI task failure.

The additive v4 gate retains the same candidate plan, prior incidents, and
frozen v3 source bytes. Under the original worker lease it starts only the
database, polls the native PostgreSQL `pg_isready` health probe and a
read-only `SELECT 1` as `bench_verify`, then invokes the already-frozen
SELECT-only full business snapshot and scans every physical filestore file.
It permits at most 30 probe cycles within a 60-second window, with a
five-second timeout per command. Any unexpected running service, timeout,
readback difference, or failed restore rejects the gate; the `finally` path
still stops the database. The v4 gate refuses to proceed if any v3 gate/SQL/
filestore receipt appears. The [v4 source freeze](evidence/odoo-v066-db-readiness-control-source-freeze-2026-09-29.json)
binds the gate, independent auditor, one-case runner, batch auditor, and
previous v3 epoch. It creates only new v4-named receipts.

The original stopped selection worker, current-candidate private/public
selection plans, and pinned validator-v0.6.6 old plans are required. After
installing the source commit in the chosen checkout, use the original paths
and the pinned project Python. The exact no-GUI dispatch command is:

```bash
ENVLOOP_ODOO_WORKER_DIR="$WORKER_DIR" \
PYTHONPATH=enterprise_fallback/odoo18:src:. \
"$PYTHON" -m tools.odoo_v066_current_candidate_no_gui_gate_v4 \
  --worker-dir "$WORKER_DIR" \
  --historical-root "$HISTORICAL_ROOT" \
  --private-plan "$WORKER_DIR/private/v066_current_candidate_epoch/selection-20260929.private.json" \
  --public-plan docs/evidence/odoo-v066-current-candidate-selection-evaluator-plan-2026-09-29.json \
  --old-private-plan "$HISTORICAL_ROOT/selection/plan-validator-v066-20260929.private.json" \
  --old-public-plan docs/evidence/odoo-v066-selection-control-plan-validator-v066-2026-09-29.json \
  --execute-baseline-check
```

The independent v4 auditor takes the same six path arguments without
`--execute-baseline-check`, plus `--write-public-audit` only after its
read-only checks pass. The v4 one-case GUI runner is a separate explicit
command and remains forbidden until the new gate passes independent audit.
No v3 run is replayed. Source freezing, synthetic tests, and an eventual
passing no-GUI gate are not task admissions or model results; official counts
remain zero.
