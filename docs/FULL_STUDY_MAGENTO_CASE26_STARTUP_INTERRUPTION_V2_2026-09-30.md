# Magento case-26 recovery v2 before cleanup

The original 834-row, 335,420-byte journal, 26 completed controls, v4 evaluator source, earlier case-0 amendment, and application source remain unchanged. Case 26 still ends at its first positive-prepare intent. The v1 private freeze (`a5470097ad2490ab4d92d6b3216118162e81e24fb2c2da75e4aed17efaad65f3`), v1 public freeze, and original pre-intent audit (`984be8ced69c6909379afebd733a309266cca33a40124336b354514898eba2dd`) remain historical evidence. No task seed, GUI action, retry, or official admission is authorized by source supersession.

V2 closes two reviewed gaps. The saved validator now checks schemas, statuses, case/attempt/task/package/plan/v4/amendment identities, positive pair, per-ID/study caps, and zero-work fields throughout the audit, cleanup intent, retirement receipt, and journal lineage. The generic completed-prefix auditor performs its common identity/hash/zero-work checks before delegating case 26. Saved container hashes must be valid and distinct; creation times must fall after the original prepare intent and before the saved observation. The full source SQL hashes, both unchanged 8,156-row price indexes, stopped cron/embedded search, empty search sidecar, and no quote pages remain required. HTTP readiness remains a diagnostic.

V2 uses new source freeze paths:

- `work/magento-original/clean-v4-100-20260929/case26-startup-interruption-v2-freeze-20260930.private.json`
- `docs/evidence/magento-v4-case26-startup-interruption-v2-freeze-2026-09-30.json`

After merging the reviewed source into the original evaluator checkout, `prepare` writes only those new freeze files and leaves the canonical v1 audit intact. The explicit `audit` action performs pre-intent audit supersession under the original evaluator lock. It requires the unchanged original journal, no cleanup intent/receipt, no original worker, and two unchanged source-state readbacks. It stages a complete v2 audit and preserves the original audit's exact bytes as `reconciliation-audit.v1-preintent-20260930.private.json`, mode 0600, before activating the v2 audit at the canonical `reconciliation-audit.private.json` path. A separate supersession intent binds both audit hashes, their paths, the v1/v2 freezes, task identity, and original journal; a separate completion receipt records that the original bytes were preserved. Staged, archived, and activated records are reopened on reentry. An interrupted activation is resumed without losing or silently rewriting the original audit. The journal remains unchanged throughout this supersession. Files are never superseded once cleanup intent exists.

Explicit `cleanup --execute-cleanup` requires the complete v2 audit supersession lineage and rechecks original-worker absence on every entry. If the cleanup intent file was saved before its journal event, the unchanged original journal and two fresh source reads allow that event to be appended. Each stop/remove uses the frozen exact-ID/image/no-mount helper. Completed effects are not dispatched again. Four ordered exact-ID stop/remove intents are required; existing finish events must be unique, ordered, follow their matching intent, and retain valid stdout/stderr hashes. A command result missing after an interruption remains unrecorded. Only full exact-pair absence permits retirement with such missing results. The private receipt lists the actions with unrecorded results and explicitly states that original command results were not reconstructed. No synthetic exit code, stdout, stderr, or finish event is created.

`verify-retired` must pass before the original v4 controller resumes its single same-ID whole-case retry. The generic auditor later reopens the complete archival/supersession/cleanup lineage. No earlier positive is reused, no retry cap changes, and final admission remains zero. The original v4 terminal auditor's older classification allowlist remains immutable; an eventual terminal report still requires the separately source-bound completed-prefix auditor rather than a claim that the old terminal auditor accepts the additive classification.

Commands must run using the loaded original evaluator checkout and its original worker lock, after root review and merge:

```sh
PYTHONPATH=src:. python -B \
  -m tools.magento_v4_case26_startup_interruption_20260930 prepare \
  --root /ABS/PATH/TO/ORIGINAL_EVALUATOR

PYTHONPATH=src:. python -B \
  -m tools.magento_v4_case26_startup_interruption_20260930 audit \
  --root /ABS/PATH/TO/ORIGINAL_EVALUATOR
```

Root must review the newly saved v2 freeze, original-audit archive, supersession intent/receipt, and canonical v2 audit before explicit cleanup. This source-only change has not created or superseded original private evidence and has not stopped or removed any actual container. Protocol tests run only against temporary files and an in-memory Docker pair.
