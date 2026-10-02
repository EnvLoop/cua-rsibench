# Excel Web 20-task selection worker plan

**Goal:** Execute the frozen 20-task Excel-for-the-web selection roster with one Qwen v0.6.6 paid sample per screenshot, original GUI actions, independent SEC saved-workbook scoring, fresh-copy reset, and exact per-task cost coverage.

**Architecture:** Accept only the exact `CampaignSession.start_selection_attempt` value and hash-bound private selection manifest. Bind the selected Tinker sampler path to the start checkpoint hash and source-frozen v0.6.6 renderer. For each SEC integrated selection workbook, create an E2B desktop through a selection-only manual-login bridge and a separately reviewed one-file ACL; sample the Qwen model only from current screenshots, recording each sample through `session.dispatch_paid`. After GUI finish, an owner Graph client double-downloads the exact `.xlsx` and a separate SEC evaluator process checks formulas, numeric dependencies under two source/scenario perturbations, and non-target state. A new desktop and distinct neutral cloud copy provide per-task reset evidence. Keep all task, permission and provider receipts private; return the 20-row selection result plus complete paid attempt IDs to `record_selection_scored`.

**Steps**

1. Add selection-only source/ACL/URL admission files; never relabel the existing train bridge or grant access to final items.
2. Add a 20-task worker that validates IDs, package hashes, checkpoint, runtime/source hashes, E2B cost caps, and one SEC `selection_candidate` case per item before provider dispatch.
3. Add a one-shot sampler setup and one Tinker reservation per current screenshot, with status/token bounds, no automatic replay, and exact paid request identity for `full_study_selection_paid_coverage_v1`.
4. Drive only v0.6.6 screenshot-bound E2B mouse/keyboard actions; persist frame and action traces, saved `.xlsx` bytes, independent 0/1 scorer receipt and fresh reset before emitting a task row.
5. Test a fake 20-task end-to-end attempt and refusals for wrong split/package/checkpoint, missing sample or E2B payment, stale frame, cloud download divergence, formula/non-target regression, reset drift, and ambiguous provider outcome. Run the full suite; keep live model/Office/Graph/E2B disabled until account ACL and manual login evidence exist.

This first worker covers the SEC integrated workflow only. Other private Excel selection workflow families remain unsupported and fail closed; a full 20-task run is impossible unless all frozen selection identities match this supported source or additional source-specific scorers are added before campaigns.
