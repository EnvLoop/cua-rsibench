# Magento v4 pre-configuration startup interruption

The first bounded v4 evaluator-control dispatch stopped on candidate index 0,
attempt 0, during `positive-prepare`. The captured process exited 1 with
`TimeoutError: Magento HTTP did not become ready`. The interrupted attempt is
retained. There is no prepared-pair receipt, task seed, GUI action, model call,
official admission, or completed evaluator control.

The live application and native search containers were inspected read only on
September 29. They are the exact two no-mount disposable containers created
within the original prepare intent window. The application now answers its
admin readiness probe, while cron and the embedded search process remain
stopped. Only the image's original `web/unsecure/base_url` row exists; no search
configuration or loopback repoint was written. Fourteen original SQL source
table hashes match the earlier saved baseline, both 8,156-row price indexes
match, no benchmark quote page exists, and the native sidecar contains no
index. Two independent readbacks agreed on the material state. The
[field-limited incident receipt](evidence/magento-v4-preconfig-startup-stop-2026-09-29.json)
binds the frozen v4 run, stopped journal, captured failure, original-software
source references, and proposed amendment source without exposing candidate IDs.

The frozen v4 reconciler covers a later, fully configured unreceipted pair. It
correctly rejects this earlier startup stage. The dated
[`magento_v4_preconfig_startup_amendment_20260929.py`](../tools/magento_v4_preconfig_startup_amendment_20260929.py)
is limited to this exact first case, first attempt, original journal, frozen
source and plan. Its `inspect` mode reads live containers without writing;
`prepare` and `audit` create new private receipts but perform no container
mutation. Only an explicit `cleanup --execute-cleanup` may stop and remove the
two exact audited no-mount containers. It journals the intent and each
identity-checked operation before authorizing the one same-ID whole-case
retry. Any changed SQL, search, cron, image, container identity, or task seed
blocks cleanup. No new source repair, reindex, GUI edit, or candidate swap is
part of this amendment.

After review and merge into the original checkout, execute in order from that
checkout using its pinned Python runtime:

```bash
PYTHONPATH=.:src /Users/xiaoyong/Documents/Codex/2026-09-22/ya/.venv/bin/python -m tools.magento_v4_preconfig_startup_amendment_20260929 inspect --root /Users/xiaoyong/Documents/Codex/2026-09-22/magento-observer-fix
PYTHONPATH=.:src /Users/xiaoyong/Documents/Codex/2026-09-22/ya/.venv/bin/python -m tools.magento_v4_preconfig_startup_amendment_20260929 prepare --root /Users/xiaoyong/Documents/Codex/2026-09-22/magento-observer-fix
PYTHONPATH=.:src /Users/xiaoyong/Documents/Codex/2026-09-22/ya/.venv/bin/python -m tools.magento_v4_preconfig_startup_amendment_20260929 audit --root /Users/xiaoyong/Documents/Codex/2026-09-22/magento-observer-fix
```

An operator must inspect the newly written private source freeze and audit
before running the exact cleanup command:

```bash
PYTHONPATH=.:src /Users/xiaoyong/Documents/Codex/2026-09-22/ya/.venv/bin/python -m tools.magento_v4_preconfig_startup_amendment_20260929 cleanup --root /Users/xiaoyong/Documents/Codex/2026-09-22/magento-observer-fix --execute-cleanup
PYTHONPATH=.:src /Users/xiaoyong/Documents/Codex/2026-09-22/ya/.venv/bin/python -m tools.magento_v4_preconfig_startup_amendment_20260929 verify-retired --root /Users/xiaoyong/Documents/Codex/2026-09-22/magento-observer-fix
```

After the cleanup receipt and journal are independently checked, the original
v4 controller may resume the same two-case bounded dispatch with its original
plan, source, freezes, run directory, `--resume`, and `--max-cases 2`. This
retries the **same** candidate from a fresh pair; it does not count the failed
attempt as a control or official result. No cleanup or retry had occurred when
this document was written.
