# Office-web authenticated fork isolation: train-only design

**Status: unqualified proposal. No E2B request, Microsoft login, owner share,
model call, official final admission, or score was produced by this work.**
This design targets the original Microsoft PowerPoint and Excel web applications.
It builds on the existing [one-file actor-scope gate](2026-09-27-office-web-actor-isolation.md)
and [manual-login E2B bridge](2026-09-27-office-web-e2b-login-design.md).
Neither a valid OneDrive editor URL nor a fresh VM alone proves the actor cannot
see other benchmark files.

## Decision and evidence boundary

The preferred *experiment* is a dedicated Microsoft actor account whose
authenticated E2B Desktop has **no benchmark file access or task data** at the
moment it becomes a parent. A trusted evaluator signs in to that parent once,
records a clean owner-side permission inventory and browser/cloud-history
baseline, and keeps the parent idle. For each task attempt, E2B forks a fresh
child from that clean parent. Only **after the fork** does the evaluator grant
that actor one specific-person edit permission on one fresh input copy. A
central lease permits at most one active task grant per actor principal. The
student sees the child desktop, one task instruction, and current screenshots;
it never receives the owner session, hidden final inventory, verifier, or gold.

The pinned local `e2b==2.51.0` implementation documents `Sandbox.fork()` as
checkpointing a running sandbox in place with its **full memory state**, then
creating independent children while the original retains its ID and expiry.
It returns a list containing either a child or an exception for each requested
fork. This makes an authenticated parent plausible, but it also copies the
actor login capability into every child. It does **not** create a distinct
Microsoft identity or erase account-level server history. [E2B SDK source](https://github.com/e2b-dev/E2B/blob/main/packages/python-sdk/e2b/sandbox_sync/main.py),
[E2B runtime overview](https://github.com/e2b-dev/runtime/blob/main/README.md).

An [offline mocked fork probe](../evidence/office-e2b-fork-wrapper-offline-2026-09-28.json)
of pinned `e2b-desktop==2.2.0` and `e2b==2.51.0` returned a Desktop subclass
without `_display` or its host-side VNC wrapper. The subclass inherits the
base SDK fork implementation but initializes those attributes only in its
`create()` path. The probe made **zero provider requests**. Existing screenshot
and action methods may still work because the child VM should inherit its X
process and environment, but that is an inference, not a live result. A pinned
child attachment adapter and a real train-only fork must qualify screenshot,
click, typing, save, stream teardown, and exact VM identity before this route
can run a model. Do not create a new Desktop via `Sandbox.create(snapshot_id)`
and assume it preserves the inherited GUI: that path also starts an X server
in Desktop 2.2.0. [Desktop SDK source](https://github.com/e2b-dev/E2B/blob/main/packages/desktop-python/e2b_desktop/main.py).

## Required lifecycle for each train pilot

1. **Freeze a clean parent.** A dedicated actor account has no owner role,
   benchmark folder grant, file grant, or hidden item access. The evaluator
   reads the complete benchmark item inventory through an independently
   authenticated owner path. An operator verifies the parent browser's local
   history and the actor account's OneDrive Recent/Shared views contain no
   benchmark item. Parent screenshots, inventory responses, actor identity,
   session hash, SDK/template versions, and lease times stay in ignored
   mode-0600 evaluator files. The parent receives no task URL or data.
   The current login bridge starts a password-protected VNC stream for manual
   sign-in and is **not** a reusable-parent builder. Before any authenticated
   fork, trusted setup must stop the stream, remove its password file inside
   the parent VM, verify no VNC/noVNC service is still exposed, and then pin
   a new stream-free parent receipt. A full-memory fork would otherwise copy
   the stream service and its access material into every child. Child GUI
   screenshots/actions must work without a stream, or a separately secured
   child-only stream must be created after the fork and destroyed at teardown.
2. **Fork before sharing.** Fork one child from the still-clean parent. Reject
   partial fork errors, a reused child ID, expired parent/child leases, or a
   child whose GUI cannot be independently controlled. Refresh the parent and
   child Recent/Shared views, inspect the child local browser history, and
   probe a non-final sentinel denial before granting anything. If a prior
   benchmark item is listed, this actor lane is contaminated even when its
   permission was revoked. A new VM does not cure server-side history.
3. **Acquire one actor-wide lease and grant one file.** The evaluator's
   scheduler must atomically exclude every other active grant for that actor
   across all workers, then create one fresh task copy, bind its owner item ID
   and original-format saved bytes to the intended seed, and grant exactly
   one specific-person `write` permission on that file. The parent folder
   remains private. Read owner-side permissions for both assigned file and
   parent and sweep the pinned benchmark inventory for *all* other grants to
   this actor. The existing actor-scope gate checks the file/parent snapshot;
   `tools/office_web_fork_scope_gate_v1.py` adds parent/child, time-order,
   inventory, and history-evidence bindings. Its acceptance means
   **operator-attested train evidence only**: offline code cannot authenticate
   Microsoft responses or interpret screenshots.
4. **Run only the bounded GUI actor.** Supply the selected task instruction
   and screenshot/action contract to the child. Do not pass owner credentials,
   Graph tokens, raw private inventory, hidden final URLs, or expected edits.
   Journal provider timeouts and uncertain calls separately from task scores.
5. **Read back, revoke, and reset.** The owner downloads the *same item ID*
   twice after saving, verifies byte-stable original-format output, applies the
   independent task oracle and collateral checks, removes the exact grant,
   confirms owner-side permissions are empty, and probes actor denial again.
   Kill the child and confirm termination before releasing the actor lease.
   Refresh the parent's and actor's Recent/Shared views before any later fork.
   Any failed download, revoke, denial, kill, or clean-history check is an
   infrastructure failure with preserved evidence, never a task score of zero.
   [Microsoft sharing](https://support.microsoft.com/en-us/onedrive/share-files-and-folders-in-microsoft-onedrive),
   [Graph list permissions](https://learn.microsoft.com/en-us/graph/api/driveitem-list-permissions?view=graph-rest-1.0),
   [Graph download](https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0),
   [Graph delete permission](https://learn.microsoft.com/en-us/graph/api/permission-delete?view=graph-rest-1.0).

No task should be dispatched concurrently on the same actor account. VM forks
are isolated at the E2B layer, but simultaneous specific-person grants on a
single Microsoft principal would let every child reach every concurrently
shared item through that same account. A local file lock is inadequate for a
distributed 24-campaign controller; the grant lease must be global, durable,
and owner-verified. Revocation may remove content access without removing a
name from server-side Recent/Shared. If a train pilot observes such persistence,
the reused-identity route fails this benchmark's cross-task-history rule;
operator assertions or an empty *local* browser history cannot repair it.

## Scale and cost implication

The 3,000 matched slot-task outcomes include **1,000 Office slot-task
outcomes**: two Office cells × five checkpoint slots × 100 tasks. This is up
to 1,000 unique executions before identical-checkpoint reuse and retries. If
every unique attempt occupied ten minutes, the child runtime would be
`1,000 × 600 / 3,600 = 166.7` sandbox-hours and one actor identity with one
active grant would spend 166.7 hours in serial actor runtime before setup and
teardown. The current train-only
runner caps actually differ: PowerPoint allows 600 seconds and Excel allows
1,800 seconds. If all 500 attempts in each cell used those entire caps, the
child runtime envelope would be `(500 × 600 + 500 × 1,800) / 3,600 = 333.3`
sandbox-hours, and one serial actor lane could occupy 333.3 hours.
Twenty independently qualified actor lanes would reduce those conditional
runtime makespans to ideal 8.3 or 16.7 hours, respectively, plus upload,
grant, verification, revocation, fork, model-provider latency, and retries.
Each live lane requires
at least one parent and one child sandbox, so 20 lanes require at least 40
concurrent E2B sandboxes. Account provisioning, concurrent Microsoft sessions,
rate limits, and actual E2B entitlement are unverified. E2B currently lists
one-hour Hobby sessions with 20 concurrent sandboxes and up to 24-hour Pro
sessions with 100 concurrent sandboxes; these are published plan limits, not
proof of this account's entitlement. [E2B plans](https://e2b.dev/).

Reserve actual cost from measured parent and child active seconds, fork and
snapshot charges if billed, storage, account/application costs, provider
errors, and retries. If `P` parent sandboxes remain live for `T` hours and
task children run for `t_i` seconds, the billable runtime envelope is
`P × T + Σ(t_i / 3,600)` sandbox-hours, before any provider-specific
minimums or extra charges. Do not call the fork route cheaper until an invoice
or billing API reconciles the private attempt ledger. The 16-hour researcher
campaign limit is distinct from final-evaluation throughput and must remain
unchanged for all four researchers.

## Separately labeled signed-out fallback

A fresh signed-out Desktop (or clean unauthenticated template) can open a
different one-file **anonymous edit link** in every child. This avoids a
shared Microsoft actor identity, hence avoids its account-level Recent/Shared
history and removes the parent-login bottleneck. It remains the original
Microsoft web application. It is a lower-assurance *bearer-link* protocol:
anyone holding the URL may be able to edit until the owner revokes or expires
it, and the URL itself must stay out of public logs, prompts, screenshots
released with the dataset, and cross-task browser profiles. The evaluator
must still prove a clean child, only one live file link, source-bound owner
readback, exact permission removal, no folder access, and independent scoring.
Whether Microsoft personal OneDrive permits anonymous PowerPoint/Excel web
editing without sign-in, whether those saves persist in the original item,
and whether link revocation closes all access are **unknown** here. It must
pass a separate train-only pilot and a pre-result protocol amendment before
any official use. Anonymous-link outcomes must never be pooled silently with
identity-bound outcomes. [Microsoft OneDrive sharing](https://support.microsoft.com/en-us/onedrive/share-files-and-folders-in-microsoft-onedrive).

| Route | Authentication work | Isolation condition | Main unresolved risk |
| --- | --- | --- | --- |
| One dedicated actor account with forks | One manual sign-in per live parent lease | One global active grant; zero local **and server-side** prior-item history | Microsoft Recent/Shared may persist; one lane is serial. |
| Pool of distinct dedicated actor accounts | One sign-in per account/parent lease | One global grant per identity plus clean-history audit for each reuse | Account scale, license/entitlement and session behavior unproved. |
| Signed-out child plus one anonymous link | No Microsoft actor login | Clean child and one short-lived bearer link | Link leakage and anonymous editing/revocation behavior unproved. |

## Verification and admission

The offline fork guard checks strict mode-0600 private inputs under `work/`,
parent/child and actor identities, frozen inventory hash/count, complete
owner-sweep entries with exactly one assigned actor grant, time ordering,
private screenshot hashes, and operator review. Six synthetic negative-control
tests cover extra grants, omitted inventory, wrong child/scope, stale/order
errors, prior Recent entries, and tampering. These tests made no provider
request and leave `official_final_admitted = 0`. The guard is **not wired into
the train runner** yet; its return value is not a dispatch authorization.

The first live acceptance test must use a disposable *train-only* PowerPoint
file and workbook, never a sealed final item: one clean parent, two sequential
child forks, a non-final sentinel, source-bound owner byte readback, a complete
owner permission sweep, revoke/denial, and an explicit check that the second
child sees no first-task name in either browser or Microsoft Recent/Shared.
Then test two separate actor lanes concurrently. Qualification needs recorded
SDK/VM versions, GUI behavior, actual billable seconds, provider failures,
and independent verifiers. Until these pass, neither the authenticated fork
route nor the anonymous-link fallback supports a 100-task Office cell or any
formal model result. Context7 CLI returned a monthly-quota error during this
design; the SDK conclusion above comes from the SHA-pinned local package
sources and linked E2B primary sources.
