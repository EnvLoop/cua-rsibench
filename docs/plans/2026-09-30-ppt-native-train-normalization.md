# PPT native TRAIN normalization implementation plan

**Goal:** Prepare and test an offline proposal for one frozen failed native collection, preserving its original strict score and all eligibility boundaries.

**Architecture:** A separate evaluator module binds the exact collection, baseline, observed saved artifact, reset, task, source, and unchanged verifier. It first validates the observed metadata and workbook rename, then guards every candidate against the frozen native profile before canonicalizing a temporary copy for the unchanged scorer. A separate explicit folder-scope auditor accepts truthful account evidence and retains strict saved-state scoring.

**Tech stack:** Python standard library, existing OOXML package guard and independent PPT verifier; no cloud or browser execution.

1. Inspect exact XML differences and distinguish target text, editing flags, revision metadata, derived thumbnail, and byte-identical embedded workbook rename. Fail on any material style/body/cache/binary change.
2. Implement a one-case private calibration with exact hashes, strict metadata/schema validation, bijective workbook/relationship/content-type checks, and temporary-copy normalization.
3. Mutate saved artifacts to test wrong targets, source/collateral/style/layout/cache/workbook/relationship changes, aliases, unknown parts/nodes/attributes/XML payloads, and strict reset behavior. Verify unchanged core scorer hash and historical failure.
4. Add an explicit development-only existing-account/disposable-folder evidence scope. Preserve false dedicated-account assertion and zero model/selection/final credit. Do not register the current failed artifact.
5. Record portable English counts/hashes, commit isolated source, and send replay evidence for independent review. Then implement a separately confined offline local-browser action bridge with focused validation.
