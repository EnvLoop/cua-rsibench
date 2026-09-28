# Prospective source-bound GitLab final controls

**Status:** implementation design before any new GitLab or model run. The
historical 100 GUI trios and six first-attempt failures remain unchanged. A
new run must be a separate evaluator-only qualification lane; its results
cannot retrospectively bind the older GUI-controller source.

The lane freezes an immutable private plan for exactly the existing 100
candidate IDs and 20 complete project source families. It binds the private
candidate-preflight ledger, world and baseline snapshots, application image,
bootstrap identities, the amended six-cell v0.6.6 source-only ratification,
and exact bytes for the GUI actor, reset, independent verifier, and controller.
The prior ratification remains historical; the amended one is required for
this prospective run. Its public copy contains no IDs or gold.

For every ID, the controller appends and fsyncs a hash-chained `intent` before
the first browser action. It then runs one positive, one plausible negative,
and one repeated positive in fresh original GitLab CE clones. Each case saves
its raw GUI receipt, post-action PostgreSQL/Git snapshot, post-reset snapshot,
screenshots, and source-bound case-completion receipt. An unrelated-state
perturbation probes whether the independent verifier rejects a regression.
Only then may the controller append a terminal success. A terminal failure or
unresolved intent stops the lane. Continuation skips only complete successes;
it never replays a failed or uncertain ID. Any recovery needs a separate
pre-result amendment and retains the failed attempt.
The plan fixes a 7,200-second acceptance cap per ID; the journal records
each ID's elapsed time. Browser and container calls retain their own bounded
timeouts. A host interruption leaves an unresolved intent for explicit
reconciliation. The live CLI requires an explicit `--execute` flag,
the same checkout that owns the private GitLab world, an active v3 clone with
the exact CE image, and an independently read business state equal to the
frozen baseline before every new intent. The default live batch is one ID.

A read-only auditor reopens every intent, source hash, screenshot, persisted
state, reset readback, positive/negative result, and unrelated-change probe.
It can report partial evaluator-control progress without granting a final
admission. Only a complete 100/100 run can yield the supporting raw evidence
for future `cua-task-reset-proof-v0.6` and
`cua-task-verifier-proof-v0.6` receipts. Those exact-schema receipts must be
paired with a separate source-bound envelope that names the raw case and
probe hashes; a later admission verifier must reopen that envelope rather
than relying on bare `passed: true` fields. Live v0.6.6 student sampling,
application entitlement/runtime, all-in balance, hidden-set freeze, and the
six-cell pre-campaign witness remain separate gates.

The conversion is exact. The v0.6 reset receipt's task ID and package hash
come from the frozen private candidate identity; `initial_state_sha256` is
the recomputed baseline business digest, `mutated_state_sha256` is the first
positive case's saved post-action PostgreSQL/Git digest, and
`restored_state_sha256` is that case's separately saved post-reset digest.
The fresh-environment flag requires a changed container identity and the
next cold-reset generation. The v0.6 verifier receipt's correct/incorrect
flags come from both positive saved-state readbacks and the plausible wrong
case. Its unrelated-change flag comes from a separate persisted-state
perturbation replayed through the independent evaluator, with score zero and
no-regression false. The source-bound envelope retains the plan, exact trio,
all three case-completion, and unrelated-probe hashes plus the hashes of the
two exact-schema receipts. A later admission verifier must rederive both
receipts from the envelope's original files and compare all bytes. A task
without this complete chain cannot be promoted by writing a JSON boolean.

The current Magento control lane owns Docker resources. This implementation
is restricted to source code and fake-backend tests until the GitLab lane can
be scheduled with the original GitLab worktree and its mode-0700 private data.
