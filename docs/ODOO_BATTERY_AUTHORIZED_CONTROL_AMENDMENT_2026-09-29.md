# Odoo evaluator control: dated battery-power amendment

**Status, 29 September 2026: source freeze and source-only tests; no new live gate or GUI result.** The operator explicitly authorized running with available battery power without waiting for AC. This amendment applies only to the current-candidate Odoo selection no-GUI baseline gate and one evaluator-only selection GUI control. It does not change a researcher campaign or official final-task admission.

The [v2 source freeze](evidence/odoo-v066-battery-authorized-control-source-freeze-2026-09-29.json) pins the new power sampler, gate, independent gate auditor, one-case runner, and independent batch auditor. It also binds the prior AC-only source freeze by SHA-256. The prior freeze, split plans, 25-file validator freeze, and all three failed GUI attempts are preserved byte-for-byte. The new gate writes a separate v2 receipt and SQL/full-filestore files; the new runner writes a distinct v2 batch intent in the precommitted fresh nonce directory. Neither path can promote an old result.

The sampler captures raw `pmset -g batt` output, its SHA-256, a UTC timestamp, parsed AC/Battery source and charge percentage. The independent auditor reparses and checks every saved sample. Samples are required at gate entry and exit, runner before durable intent, immediately before first GUI dispatch under the worker lease, and at runner end. A change from battery to AC, or vice versa, is recorded and permitted. No minimum charge percentage is imposed. Missing or unparseable telemetry fails closed; a failed GUI attempt retains its raw evidence and cannot be automatically replayed.

The current SQL snapshot and **every physical filestore entry** must still match the frozen baseline exactly. The gate re-audits all three terminal failures before and after its read, uses the original selection worker lease, and restores the stopped service state. The one-case runner separately binds the current six-cell candidate, unchanged selection task package, private nonce, source freeze, gate receipt, original GUI action recipe, saved positive, wrong-object negative, cold reset and independent saved-state audit. Source-frame visual review remains required after a raw passing trio. Selection and hidden plans stay isolated; no final task or model result is admitted by this amendment.

After merging this source commit into the checkout used to run the original worker, run the source check, then **only the no-GUI gate** and its independent read-only auditor:

```bash
OD_REPO=/Users/xiaoyong/Documents/Codex/2026-09-22/magento-observer-fix
OD_ORIGINAL=/Users/xiaoyong/Documents/Codex/2026-09-25/odoo-four-workflows
OD_WORKER="$OD_ORIGINAL/enterprise_fallback/odoo18/partition_workers/selection"
OD_HISTORY="$OD_ORIGINAL/work/odoo-original/v066-scale-controls-20260928"
OD_PY=/Users/xiaoyong/Documents/Codex/2026-09-22/ya/.venv/bin/python
export ENVLOOP_ODOO_WORKER_DIR="$OD_WORKER"
cd "$OD_REPO"
PYTHONPATH=enterprise_fallback/odoo18:src:. "$OD_PY" -m tools.odoo_v066_battery_authorized_source_v2
PYTHONPATH=enterprise_fallback/odoo18:src:. "$OD_PY" -m tools.odoo_v066_current_candidate_no_gui_gate_v2 \
  --worker-dir "$OD_WORKER" --historical-root "$OD_HISTORY" \
  --private-plan "$OD_WORKER/private/v066_current_candidate_epoch/selection-20260929.private.json" \
  --public-plan docs/evidence/odoo-v066-current-candidate-selection-evaluator-plan-2026-09-29.json \
  --old-private-plan "$OD_HISTORY/selection/plan-validator-v066-20260929.private.json" \
  --old-public-plan docs/evidence/odoo-v066-selection-control-plan-validator-v066-2026-09-29.json \
  --execute-baseline-check
PYTHONPATH=enterprise_fallback/odoo18:src:. "$OD_PY" -m tools.audit_odoo_v066_current_candidate_no_gui_gate_v2 \
  --worker-dir "$OD_WORKER" --historical-root "$OD_HISTORY" \
  --private-plan "$OD_WORKER/private/v066_current_candidate_epoch/selection-20260929.private.json" \
  --public-plan docs/evidence/odoo-v066-current-candidate-selection-evaluator-plan-2026-09-29.json \
  --old-private-plan "$OD_HISTORY/selection/plan-validator-v066-20260929.private.json" \
  --old-public-plan docs/evidence/odoo-v066-selection-control-plan-validator-v066-2026-09-29.json
```

The gate is a no-GUI control and admits zero tasks. Only after its receipt and live service state are independently reviewed, the separate one-case runner can be called with the same six paths and `--execute` instead of `--execute-baseline-check`:

```bash
PYTHONPATH=enterprise_fallback/odoo18:src:. "$OD_PY" -m tools.odoo_v066_current_candidate_one_selection_v2 \
  --worker-dir "$OD_WORKER" --historical-root "$OD_HISTORY" \
  --private-plan "$OD_WORKER/private/v066_current_candidate_epoch/selection-20260929.private.json" \
  --public-plan docs/evidence/odoo-v066-current-candidate-selection-evaluator-plan-2026-09-29.json \
  --old-private-plan "$OD_HISTORY/selection/plan-validator-v066-20260929.private.json" \
  --old-public-plan docs/evidence/odoo-v066-selection-control-plan-validator-v066-2026-09-29.json \
  --execute
```

The runner invokes the independent batch auditor before returning a claimed raw trio. A failure or partial run is terminal for that nonce and requires a newly dated source and private plan before any retry. The remaining 19 selection and 100 hidden per-ID GUI controls, formal admissions, 24 researcher chains, and shared base/checkpoint final evaluations are not implied by this one-case path.
