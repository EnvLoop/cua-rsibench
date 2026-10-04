# Magento Reference Continuation Implementation Plan

**Goal:** Prepare a reviewed continuation of the interrupted original selection20 reference controls, with no model or Tinker calls and no cohort launch during preparation.

**Architecture:** An additive controller preserves the frozen Native10 actor, sampler, scorer, guard, and reset. It reopens only the first eleven completed whole trios from their original paths, runs nine fresh whole trios in original ordinal order after a new one-use review, and independently verifies the complete ordered twenty-task aggregate. A separate durable host supervisor owns one worker and records its PID, exit and private logs without restarting it.

**Tech Stack:** Existing Native10 modules and Python standard library; offline unittest fixtures and mocks.

## Evidence boundaries

- Original ordinals 0 through 10 may supply thirty-three accepted modes only after fresh saved audits.
- Ordinal 11 must run all three modes in a new namespace. Its original completed baseline and interrupted positive mode remain failure-cost evidence, with no aggregate credit.
- Ordinals 12 through 19 run in their original order with their original identities.
- The aggregate contains exactly sixty reference modes and their original or fresh provenance. Every mode must pass the existing Native10 auditor, fixed 0/1/0 expected score, reference-only sample checks, and exact source/path/identity checks.
- A missing mode, changed source, changed prerequisite, unknown process result or failed reset stops progress. No authority replay or automatic restart is admitted.
- Resource cleanup is separately journaled and never recreates a formal reset receipt for the interrupted mode.

## Tasks

1. Complete the separately approved exact owned-resource cleanup and hash every preserved original artifact after it.
2. Add `magento_catalog_factory/native_selection_reference_continuation_v1.py`. Review and saved-audit entry points reopen private evidence without loading new task bodies or opening runtime.
3. Add `tests/test_magento_selection_reference_continuation_v1.py` with refusals for identity/order/path/source/sample changes, partial promotion, failed audits, consumed authority reuse and failed-run continuation.
4. Add `magento_catalog_factory/native_reference_host_supervisor_v1.py` and offline tests. The supervisor launches at most one independently detached worker only after explicit exact review; it records one-use authority, PID, private output and terminal status, and never retries a launch or restarts the worker.
5. Run scoped offline tests and prepare the exact private continuation contract. Hash source and tests, obtain independent source review and root review before any cohort execution.

## Validation

Run the continuation and host supervisor unittest files with `PYTHONPATH=.:src:tests` using the workspace virtual environment. No tests launch Magento, Docker, a model, Tinker, or a real supervisor process. Reopen the prepared contract under runtime and task-loader traps and verify that the frozen original binding is unchanged. The original output is never appended to or rewritten.

## Execution boundary

This plan authorizes preparation only. A root-reviewed exact continuation contract and a separate exact durable-launch review are required before the new cohort can run. The existing 90-turn, 720-second actor and 1200-second lifecycle bounds remain unchanged.
