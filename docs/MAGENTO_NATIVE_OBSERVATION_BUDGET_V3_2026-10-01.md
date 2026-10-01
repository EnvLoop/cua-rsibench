# Magento observation readiness budget V3

The saved V5 TRAIN positive control applied seven native actions: product
navigation, search, opening the product, filling its price, and clicking Save.
Independent saved-only review reopened every original native envelope, PNG,
decision, exclusive intent, nonce and returned driver receipt. The seventh
pointer hit the currently observed Save button. Its next observation retained
two loading-mask frames and then failed in the V2 metadata read's six-second
`asyncio.wait_for`. No subsequent observation or saved-state score was produced.
A returned Save pointer does not prove that the product was saved.

The Docker journal's full hash chain was reopened. Its five exact absence
results show both dedicated app/search pairs and their network were removed.
New read-only inspections also confirmed these five resources absent, and the
old supervisor and worker were absent. The failure path did not persist the
structured material-reset receipt; cleanup confirmation does not grant reset
qualification. The private saved-only review has SHA-256
`67fa6691f4e4fecbe130ab303366e4e6a5a576fec33342fc013fd82e90f54bcb`;
the original positive Docker journal has SHA-256
`ed528e2fa979baf4168d6d12f7d983b6899c0c10ecb03abd33b824a171e0eb4e`.

V3 uses one absolute 30-second observation deadline covering readiness waits,
metadata, screenshots, lease checks and ownership reads. The deadline is
clipped to the existing absolute actor deadline. A single metadata request may
settle after six seconds; every read shares the same observation deadline.
Only the two previously recognized destroyed-context errors allow another
read before action intent. Timeout or another error remains terminal. Each
read has a durable intent and returned/unavailable result; timeout discards
the observation and prevents a nonce or model request. A typed actor expiry
remains a budget outcome. A readiness timeout remains an unqualified
infrastructure failure with saved score Unknown.

V1 and V2 adapter bytes, native target checks, predispatch reads, keyboard-focus
reads, scorer and reset code remain unchanged. Teacher, trusted controls,
shared base and all four selected checkpoints use the same V3 actor import and
source manifest. Limits remain 90 actions, 720 actor seconds and 1200 lifecycle
seconds. The new source needs fresh TRAIN and full-split qualification; prior
V5 actions receive no V3 or formal benchmark credit.

Verification ran 36 tests over the production adapter, native guard, actor,
pipeline, selection/final gates, deadline accounting and Docker journal. The
new tests cover a metadata read that settles after six seconds, one shared
deadline across busy reads, durable timeout refusal, typed actor expiry,
read-only destroyed-context recovery, one-call predispatch failure and
post-pointer keyboard uncertainty. Native page and transport inputs in these
tests are synthetic; no new native application, Docker resource or provider
call was launched for this repair.

```bash
PYTHONPATH=.:src "$BENCH_PYTHON" -m unittest \
  tests.test_magento_native_surface_adapter_v3 \
  tests.test_magento_native_surface_adapter_v2 \
  tests.test_magento_native_surface_guard_v1 \
  tests.test_magento_native_surface_pipeline_v1 \
  tests.test_magento_native_surface_selection_v1 \
  tests.test_magento_native_surface_final_v1 \
  tests.test_magento_native_surface_budget_v1 \
  tests.test_magento_native_command_journal_v2
```

After importing this source into the current common study tree, prepare a
fresh private namespace using the existing metadata-only facade; its binding
must be recomputed in that tree. `prepare` does not run or qualify a control.
The original consumed V5 namespace must remain unchanged.

```bash
PYTHONPATH=.:src "$BENCH_PYTHON" -m magento_catalog_factory.native_surface_facade_v1 \
  prepare --plan-path "$PRIVATE_PLAN" --plan-sha256 "$PRIVATE_PLAN_SHA256" \
  --lane-path "$PRIVATE_LANE" --lane-sha256 "$PRIVATE_LANE_SHA256" \
  --output "$FRESH_PRIVATE_METADATA" --final-output-root "$FRESH_PRIVATE_FINAL"
```
