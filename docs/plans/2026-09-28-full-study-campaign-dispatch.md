# Full-study campaign dispatcher implementation plan

**Goal:** Run the preregistered 24 data-research campaigns only after six real cells, 600 final admissions, one v0.6.6 action profile, and an immutable public pre-campaign witness pass independent checks.

**Architecture:** Use the existing pre-campaign validator and dollar ledger as the source of truth. Add a private append-only campaign journal and a small transactional dispatcher that commits exact requests and worst-case resource reservations before each provider call. Keep train and selection task views separate from the evaluator-owned final inventory. On an ambiguous response or process interruption, preserve the reservation and refuse automatic replay.

**Tech stack:** Python 3.14, `unittest`, existing `cursibench` validators, AgentRouterHub Responses transport, pinned Tinker SDK and Qwen vision renderer. Native GUI teacher and selection runners remain cell-owned adapters; the dispatcher validates their task identities, costs, and saved-state receipts.

---

## Task 1: Immutable execution gate

1. Add a loader that re-runs `full_study_pre_campaign_v1.build` from the source manifest and compares its bytes with both prepared files.
2. Require a source-bound six-cell v0.6.6 ratification receipt and an immutable GitHub-commit publication witness that binds the protocol, plan, and action profile hashes.
3. Reject missing or altered data before constructing a provider client or budget ledger.
4. Test the real current tree's missing manifest refusal, synthetic six-cell fixture success, and tampered plan/action/witness failures.

## Task 2: Private resource and request journal

1. Add mode-0600, fsynced, hash-chained per-campaign journals bound to one plan and intent.
2. Enforce 16 hours and frozen call/token/candidate/selection/sandbox counters, plus the existing dollar category/global caps.
3. Record the exact request hash and reservation before dispatch; retain an interrupted or uncertain request until provider usage or no-charge evidence is reconciled.
4. Test restart, hash tampering, cap refusal, duplicate work, and one-time reconciliation with fake providers.

## Task 3: Train-only researcher and Tinker steps

1. Build researcher prompts from the frozen prompt asset, evaluator-approved train context, and selection feedback only; dispatch through the existing Responses transport with the frozen model/reasoning configuration.
2. Validate a research proposal and teacher-generated episode manifest against the train identities and package hashes, then render pinned Qwen multimodal datums.
3. Run fresh-base Qwen3.8-27B LoRA SFT through the pinned Tinker API, save and sample its checkpoint, and retain its private path and token/cost evidence.
4. Test the call flow with fake Responses/Tinker providers. A real paid smoke is allowed only on a separately admitted, nonfinal train source under a finite reservation; it is not an official campaign.

## Task 4: Selection and freeze

1. Dispatch only the 20 frozen selection identities to each cell's original-software actor/evaluator adapter.
2. Accept one complete, independently saved-state-scored 20-task result, with at most one predefined infrastructure retry. Preserve every invalid attempt and cost.
3. Promote a new checkpoint only on a strict win-count gain with zero task regressions against the incumbent. Freeze the selected checkpoint and lineage after all paid requests reconcile; never expose final tasks to this code path.
4. Test complete fake 4-by-6 campaigns, wrong task IDs, selection after timeout, retry misuse, stale resume, and checkpoint lineage drift.

## Verification and boundary

Run focused tests, then the full repository suite. Public docs explain that the dispatcher is an execution controller, not evidence of real campaigns. The current tree must still report 0/24 and reject paid dispatch because no authentic six-cell pre-campaign manifest or v0.6.6 ratification exists.
