# Desktop 20-Identity GUI Evidence Implementation Plan

> For implementation: keep all task text, targets, frames, and saved files evaluator-private.

**Goal:** Prepare a resumable real E2B Desktop GUI collector for the original 20 WDI train identities and a task-disjoint 15/5 Qwen3.8 LoRA diagnostic, without treating evaluator demonstrations as model scores.

**Architecture:** A private source plan validates the complete 20/20/100 inventory and binds every train package, then deterministically assigns 15 IDs to SFT collection and five to untouched holdout. One process writes an exclusive intent before each guest, records current-frame and predispatch PNGs around bounded GUI actions, saves the actor's OOXML, and kills the guest. A separate auditor reopens raw frames and the saved OOXML, rederives the actions and independent verdict, and only then advances the cursor. Failure, missing receipt, uncertain cleanup, or changed source stops the lane; no same-ID replay is automatic.

**Constraints:** The 20 train tasks are five WDI country source families by four workflows, while the final and selection families remain separate. Four held-out IDs come from one entire country family and the fifth from another; the one mixed family is reported as such. The existing three train GUI demonstrations remain separate. The source plan and all task IDs/answers stay under ignored `work/`, mode 0600. Public evidence contains counts, hashes, limitations, and no hidden task values. A 600-second lease, one guest at a time, 20 maximum intents, exact pre-create active-zero check, and a conservative full-lease cost quote bound provider use. No create is permitted while the host is on battery.

### Task 1: Freeze the source and 15/5 assignment

Create a private plan from the original `candidates-v2-distinct-d` inventory, rehash the 140 packages, prove split group separation, bind source files and 20 exact train scripts. Reject altered or missing packages, repeated IDs, and a changed plan. Write aggregate public metadata only after private validation. Test deterministic assignment, disjointness, and tamper rejection.

### Task 2: Add one-ID GUI capture and a resumable controller

For each allowed SFT ID, create a mode-0600 exclusive intent, confirm active-zero, source binding, storage headroom, and 600-second lease budget before E2B create. Use the established v0.6.6 current-frame adapter and scoped profile guard; preserve each raw observation, predispatch frame, normalized action, and saved actor file. Kill and verify the guest in `finally`. Reopen and audit before the next ID; never retry a failed or uncertain identity automatically. Test with a fake guest and failure injection. Holdout IDs remain undispatched until the preregistered base/LoRA comparison.

### Task 3: Independently audit training evidence

Reopen source package, intent, receipt, all raw frames and profile captures, and saved OOXML. Recompute hashes and v0.6.6 action envelopes, assert action sequence/step counts and distinct guest IDs, run the independent native saved-file verifier, and classify a pass only after confirmed teardown. Test altered frame, altered action, altered saved artifact, duplicate guest, and partial intent.

### Task 4: Freeze the diagnostic protocol and validate offline

Emit the 15/5 private mapping plus an aggregate public preregistration: SFT uses only the 15 admitted train demos; the five holdouts are base/LoRA paired trials in fresh guests with equal action/observation limits. Record exact result, invalid-action, timeout, latency, token, and provider-cost fields. A pass on evaluator-scripted controls cannot count as model gain. Run focused and full tests, then commit the code and dated public plan; do not start the 20 paid guests on battery.
