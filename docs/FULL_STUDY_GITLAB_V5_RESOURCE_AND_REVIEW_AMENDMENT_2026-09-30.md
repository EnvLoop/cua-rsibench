# GitLab v5: pre-result resource and independent-review amendment

The original dedicated `cua-gitlab` VM has 3 CPUs, 6 GiB configured memory and
24 GiB disk. A read-only live snapshot on September 30 observed the original
GitLab using 3.767 GiB of the Docker VM's 5.773 GiB limit. Starting a second full
GitLab alongside it in that VM is not approved by this review.

The lowest-maintenance resource proposal keeps the same context and read-only
seed transport, raises the dedicated VM to **12 GiB**, and retains 3 CPUs and
24 GiB disk. Root-owned maintenance must first confirm that no old evaluator
worker is live and record source/private-baseline/terminal hashes and original
runtime identity. Its transient VM/application restart must be retained in a
separate pre-result maintenance receipt. Do not claim the old application never
stopped across maintenance. The cloned bootstrap itself continues to forbid
stopping or mutating the original application, volumes, files or markers.

After maintenance, restore the original runtime, confirm healthy pinned image
identity, and re-open its exact 31-project PostgreSQL/Git baseline and original
source/private/terminal hashes. No old task intent is replayed. Preserve before
and after resource metadata, identity, source/baseline hashes and timestamps.
This review performs no VM resize or application mutation.

The [read-only resource interface](../gitlab_world/v066_prospective_resource_preflight_v5.py)
requires at least **10 GiB Docker VM memory**, at least 3 CPUs, and measured free
disk greater than the immutable config/log/data copy size plus an 8 GiB floor.
It reads Docker info, `df`/`du`, healthy original image/identity and the exact
31-project business snapshot. Bootstrap repeats this preflight **before**
creating its epoch root or durable bootstrap intent. An undersized VM leaves
no new bootstrap intent, volumes or container.

```bash
cd "$GITLAB_EVALUATOR_ROOT"
PYTHONPATH=src:. "$GITLAB_PYTHON" \
  -m gitlab_world.v066_prospective_resource_preflight_v5 \
  --freeze "$NEW_REVIEWED_COHORT_FREEZE" \
  --private-out "$NEW_PRIVATE_RESOURCE_PROOF"
```

The independent code review also corrected three proof gaps. Native ACL
acceptance now re-opens all three fresh browser cases, checks their scoped
principal hashes and 3 own/6 cross-partition responses, and rehashes all nine
owner-only PNGs. A new exclusive, fsynced child-start marker consumes each
supervisor intent before any GUI/database operation; a second child invocation
is refused even after receipt loss. Prefix audit binds that marker and re-opens
the saved stdout/stderr against the supervisor hashes. A refused journal
transition no longer appends an invalid event to the existing valid journal.
The 32-project plan also binds invariant cold-seed metadata to the three new
named volumes and exact baseline; generation counters may advance under the
frozen reset rule, while switching back to an original volume is refused.

All original source modules, 30/31-project validators, private world, seeds and
terminal history remain unchanged. The clone-scoped 32-project adapter still
restores module globals on exit. No historical pass enters the new denominator.
The prior unlaunched v5 source proposal is retained as method history; these
amended source bytes require an exclusive new source freeze and root review
before bootstrap. There is no bootstrap/control permission in this amendment.
Native 32-project bootstrap, all 100 new controls, model calls and official
final admissions remain **zero**.
