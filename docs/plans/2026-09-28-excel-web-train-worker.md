# Excel Web SEC train teacher worker plan

**Goal:** Feed one original Excel-for-the-web SEC training episode into the frozen v0.6.6 teacher collector, using evaluator-owned formula/numeric/no-regression scoring and a distinct fresh reset copy.

**Architecture:** Reuse the proven E2B Desktop/manual-login/single-file ACL lifecycle from the PowerPoint teacher worker. Pin an Excel-specific cloud item and private SEC integrated train case before any provider call. The actor receives screenshots and GUI actions only. An owner-side Graph client double-downloads the exact `.xlsx` after a save, while a separate SEC evaluator process checks formulas, numeric dependencies under two perturbations, and non-target workbook state. Both actor and reset grants are revoked by exact permission ID before the next file is shared.

**Tasks**

1. Add an Excel Graph owner reader with the same stable item/eTag/two-download and identity-bound revocation checks, but exact `.xlsx` MIME and name.
2. Add a private, one-case SEC integrated train oracle. Its seed must fail; its original filing-backed reference must pass at least 20 formula targets and both counterfactual profiles. Score saved Excel bytes in a separate evaluator process; compare a fresh reset to the seed semantically across every cell and workbook structure.
3. Add a private binding preparer and `ExcelWebTeacherWorker`. Require a frozen real campaign, six-cell v0.6.6 ratification, source/module hashes, an original train-only actor package, a distinct neutral reset item, and separately reviewed one-file ACL receipts. Use two paid E2B leases and ledgered owner readbacks; no direct actor workbook/API access.
4. Test Graph response variation, train/final isolation, missing ACL, stale frame, formula failure, non-target mutation, divergent downloads, exact permission revocation, fresh reset drift, cleanup, and the shared `_verify_episode` receipt contract with fake providers. Run the full suite; preserve current 0/24 official campaigns.

The Mac Office UI is locked and no delegated Graph write scope or verified owner token is available. This task does not dispatch a live cloud, model, or payment request. Owner-side invitation/revocation automation is feasible per Microsoft Graph v1.0 but remains a separate account acceptance gate; the current E2B actor login remains manual.
