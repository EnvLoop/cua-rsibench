# GitLab CE supervised one-ID final control, source-only

The original prospective 100-ID evaluator controller records a 7,200-second
per-task limit but tests it only after the task returns. The
[source-backed correction](evidence/gitlab-v066-prospective-wall-cap-clarification-2026-09-28.json)
keeps its frozen plan and code intact. A separate supervisor now wraps **one
unchanged controller invocation per child process**, always with
`--max-tasks 1`. It starts a new process group, writes private child stdout
and stderr, and applies a real 7,200-second child deadline. If the deadline
expires it sends TERM to the group, waits up to 30 seconds, then sends KILL
and waits for termination. Cleanup and independent auditing happen afterward
and have their own wall time; 200 hours is still not a hard end-to-end bound
for all 100 IDs.

The supervisor writes a private source-bound intent before launching each
child. After a clean child exit, it reopens the original hash-chained journal,
all completed raw GUI receipts, the saved PostgreSQL/Git baseline, and the
healthy disposable GitLab image. A passing ID is recorded only after those
checks. Following a timeout or nonpassing exit, it terminates a pending or
unstarted journal ID as failed without replay. Once the child is confirmed
dead, it cold-resets the disposable world and independently compares the
result with the immutable seed baseline. If the child died after removing the
container, the supervisor clears/rebuilds its overlay from the immutable
lowerdirs and updates the clone generation **only after** a passing readback.
An unreadable journal, a child process group that cannot be confirmed dead,
or an inexact reset stops the lane for manual review. Prior completed IDs
must have a passing private supervisor receipt before the next invocation.

Five offline tests cover process-group timeout termination, an exact normal
reset, fail-closed bad readback, recovery from a missing container with
state-file commit only after exact readback, and no-replay journal
terminalization. The existing seven prospective-controller tests also pass.
The [separate source freeze](evidence/gitlab-v066-prospective-supervised-one-plan-2026-09-28.json)
binds these files to the original 100-ID plan. **No supervised live ID, model
call, researcher campaign, or official final admission has run.** The first
live step should be one supervised ID on stable power, followed by a separate
raw receipt review and runtime measurement before the remaining IDs.
