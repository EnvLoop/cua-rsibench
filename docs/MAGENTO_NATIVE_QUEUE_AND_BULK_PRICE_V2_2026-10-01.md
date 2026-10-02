# Native Magento queue and price-only reference V2

The actual previous TRAIN edit changed the requested price but also caused
nonprice EAV/default, line-ending and stock changes. Its original strict
verifier score0 remains unchanged. No delta was whitelisted or relabelled.

Read-only package inspection of the existing stopped pinned image confirmed
Magento Open Source2.4.6 and the native bulk path. The ordinary Products grid
**Actions → Update attributes → Price Change checkbox → Save** submits only
selected attributes. Adobe documents this [native workflow](https://experienceleague.adobe.com/en/docs/commerce-admin/catalog/product-attributes/create/bulk-product-attribute-update).
The [2.4.6 controller](https://github.com/magento/magento2/blob/2.4.6/app/code/Magento/Catalog/Controller/Adminhtml/Product/Action/Attribute/Save.php)
publishes an asynchronous operation. A queued notification cannot establish
saved price. The [native consumer](https://github.com/magento/magento2/blob/2.4.6/app/code/Magento/Catalog/Model/Attribute/Backend/Consumer.php)
uses the selected-attribute resource update and price/flat indexing. The
[MySQL queue status definitions](https://github.com/magento/magento2/blob/2.4.6/app/code/Magento/MysqlMq/Model/QueueManagement.php)
were checked directly. Context7 library/docs lookup preceded the exact
primary-source and pinned-package checks.

The existing app image has no dedicated queue consumer in its supervisor
configuration. General cron remains stopped. The new profile starts exactly
one owned native consumer for `product_action_attribute.update`, with
`--max-messages=10000 --single-thread`. Service arguments contain no task,
SKU, desired price or hidden expected answer. Teacher, controls, shared base
and four selected checkpoints all use the same profile. The actor still has
only ordinary GUI actions.

The lifecycle refuses preexisting pending/failed messages on this channel.
A one-use native supervisor pins the actual package source and launches the
native CLI once. Its owner proof retains supervisor/child PID, parent PID,
Linux start ticks, UID, executable, exact NUL-delimited command hash and owned
deadline. Detached Docker acknowledgement is insufficient; current native
process identity is reopened before actor startup and every passive native
context read. Unknown or foreign identity remains terminal.

The passive reader records internal queue states and native process proof
without changing the actor's metadata or screenshot. Final eligibility binds
the in-budget queue observation to the actual finish predispatch context.
Known pending/failed native work at actor end scores0 even if later evaluator
readback sees the price. Missing or uncertain evidence cannot become success.
The independent final grade is **original SQL/search/no-regression verdict
AND actual queue completion before actor end**. The original SQL verdict is
retained separately; its source bytes and preservation rules are unchanged.

The reference selects one exact native SKU row, proposes ordinary guarded
checkbox/menu/type/click actions, and refuses Save unless only the price field
and its Change checkbox are enabled. It confirms the displayed native grid
price; an ordinary Enter search refresh can observe asynchronous completion.
It does not mutate DOM, send requests directly or start a consumer itself.

Owned close has an exclusive request and actual supervisor stop intent,
returned native exit status/signal, child/parent absence and exact stdout/
stderr hashes. Unknown acknowledgement is not a close proof. This completes
before the original clone teardown. The original distinct reset clone also
reopens the complete channel snapshot and must equal baseline. A failed
queue-reset read cannot skip original owned cleanup. Limits remain90 actions,
720 actor seconds and1200 complete lifecycle seconds; late/unknown closure
cannot qualify a run.

New source requires fresh TRAIN positive/negative/repeated controls, native
source/queue/close/reset readback and full-split qualification. No old control
receives the new epoch's credit. Metadata preparation uses the current source
binding and remains source-only:

```bash
PYTHONPATH=.:src "$BENCH_PYTHON" -m magento_catalog_factory.native_surface_facade_v1 \
  prepare --plan-path "$PRIVATE_PLAN" --plan-sha256 "$PRIVATE_PLAN_SHA256" \
  --lane-path "$PRIVATE_LANE" --lane-sha256 "$PRIVATE_LANE_SHA256" \
  --output "$FRESH_PRIVATE_METADATA" --final-output-root "$FRESH_PRIVATE_FINAL"
```

Source tests cover native owner identity, status rederivation, unavailable
startup/close, pending and late finish, actual context binding, price-only
native form choice, original scorer/reset replay, real paid/shared selection
ledger and five final slots, plus typed SDK deadline and unknown billing.
Native app, queue and SDK inputs in these tests are synthetic. Five generated
PHP programs were parsed as PHP8.2 with zero syntax errors; no host PHP runtime
was available. This is source validation, not native startup qualification.
No new Docker resource, consumer, GUI episode or provider call was launched
for this change.

## First native schema read and correction

The first new native TRAIN startup subsequently failed before consumer launch:
its SQL selected nonexistent `queue_message.message_id`. Original owned
application/search/network cleanup completed; no startup or task credit is
inferred. The [pinned 2.4.6 MySQL queue schema](https://github.com/magento/magento2/blob/2.4.6/app/code/Magento/MysqlMq/etc/db_schema.xml)
defines message `id`, and the status table's `message_id` references that `id`.
The read now selects `id AS message_id` and joins status rows on `m.id`.
Executable schema fixtures cover all three actual SELECT queries and reject
the original invalid column. This is a source repair, not a native success;
the consumed namespace remains unchanged and fresh TRAIN is required.
