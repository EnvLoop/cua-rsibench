# PowerPoint calibration source-boundary rebase implementation plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Freeze a new, dated evaluator-private WDI source boundary that can be reopened and checked against every known PowerPoint source partition without recreating the unavailable historical 80-case manifest.

**Architecture:** Keep the September 27 aggregate receipt immutable and label its private provenance unavailable. Generate a distinct September 29 private seed, eight official-country source package commitments, and an 80-spec *unbuilt* calibration plan. Independently reopen the original 35-country snapshot, exact v13 20/20/100 plan, future reserve queue, all 12 historical final-plan files, and both new training-transfer CSV packages before accepting the eight source families. Publish only counts, hashes, status, and zero-overlap results. The Office transfer gate may accept the newly frozen boundary for source disjointness; this does not turn the old 80 cases or the new unbuilt specs into admitted training cases.

**Tech Stack:** Python standard library, pinned repository WDI/PPT source and verifier modules, `unittest`, ignored owner-only evaluator storage.

---

### Task 1: Source-boundary audit

**Files:** Create `tools/ppt_wdi_calibration_rebase_20260929.py`; test `tests/test_ppt_wdi_calibration_rebase_20260929.py`.

1. Add synthetic tests for eight unique official packages, exact active v13/queue hashes, 12 complete historical final plans, and zero overlap against each source category. Confirm source collisions and changed package bytes fail closed.
2. Implement read-only source reopening and private manifest construction. Bind the old public receipt's published private-manifest SHA as a historical claim, never as a fabricated replacement.
3. Generate 80 private task **specifications** with a fresh seed and a new calibration role; leave their saved decks and GUI admissions at zero.
4. Add private/public replay validation that recomputes source and plan hashes. Never serialize ISO3 codes, task IDs, gold, exact values, or credentials in the public receipt.

### Task 2: Freeze real official sources

**Files:** Ignored `work/ppt-calibration-rebase-20260929/` only; public `docs/evidence/ppt-wdi-calibration-source-rebase-2026-09-29.json`.

1. Commit a private priority order before checking any model outcome. Accept the first eight source-disjoint country ZIPs with all 30 required 2019–2024 WDI observations; retain rejected candidates and reasons privately.
2. Create a fresh 32-byte private seed, source-family manifest, 80-spec plan, and field-limited public receipt.
3. Reopen the private inputs and verify every public field and commitment. No 80-deck CPU build or Office browser/provider call occurs in this step.

### Task 3: Connect the transfer-source gate

**Files:** Modify `tools/office_transfer_source_gate_v1.py`, `tests/test_office_transfer_source_gate_v1.py`.

1. Keep the original published 80-case manifest SHA immutable. Add a separately named, pinned September 29 source boundary accepted only after its private SHA and source-role checks pass.
2. Recheck transfer-country non-overlap against the new eight-source manifest, active v13, reserve queue, and historical final plans. A missing or altered new boundary must block source-plan generation.
3. Emit distinct historical and rebased provenance fields so a source-only gate pass cannot imply that the historical 80 cases have been reopened.

### Task 4: Publish provenance status and validate

**Files:** Modify `docs/evidence/ppt-wdi-train-calibration-80-2026-09-27.md` and `docs/FULL_STUDY_OFFICE_TRANSFER_SOURCE_AMENDMENT_2026-09-29.md`; add `docs/evidence/ppt-wdi-calibration-source-rebase-2026-09-29.md`.

1. State the old aggregate receipt is historical and its current private backing is unavailable. Link the new source boundary without relabeling old tasks.
2. Run focused synthetic tests, actual private/public replay, and a public-file scan for country/task leakage. A one- or two-case direct-file smoke is optional and remains separate from 80-case claims.
3. Commit only source, tests, and field-limited public documents. Keep seed, ISO3 manifest, source ZIPs, task specifications, and future control artifacts ignored and mode `0600`/`0700`.
