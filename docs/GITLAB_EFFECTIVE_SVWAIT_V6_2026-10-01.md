# GitLab effective startup wait V6 / common task epoch V14

The V13/V18 full100 reference run stopped after two completed control trios.
Saved-only review rederived eight completed cases, 92 native dispatch receipts
and 6,391 retained files. The repeated positive in ordinal2 also has a saved
SQL/full-Git verdict1 and four returned native receipts, but its second fresh
cold-reset clone failed during reconfigure. It receives no completed-control
or formal credit. The exact reset logger command timed out after30 seconds;
the fresh container exited1 without OOM. Both owned cycles and their parent
were removed. Independent saved readback and current read-only inspection
verified exact original identity, all33 project Git trees, SQL, protected
source/seed and healthy original services. No owned cleanup remains for
this failed attempt. No restart was performed by this review.

The terminal independent review SHA-256 is
`cf6a4c002955fbce50ba33489f0a57a80477b56ac4f3717f45f22c88e7f48ea5`.
The earlier timestamped live-prefix review SHA-256 is
`bb82141cb3385dcd214702c4b852cadff4d80f7f1ec8895534ec0001b905bdb9`.
The terminal supervisor receipt SHA-256 is
`114afe45f5c784136429dfcd8752ae8bab6a82acee2125bd33fa1cf375ef9d13`.
Observed guard spans were12–39 seconds. Completed-case filesystem lifecycle
spans were447–477 seconds, mean464.8; these filesystem timings are not formal
actor or budget receipts. Native setup/reset dominates observed throughput.

The current container environment already declares `SVWAIT=60`. Read-only
inspection of the pinned package established that `/opt/gitlab/bin/gitlab-ctl`
unconditionally exports30 before starting Omnibus. Its SHA-256 is
`65e32e7af21742b5748c2244cff835702fea65410de2b723fd9fbf7bea2d669b`.
The unchanged runit helper SHA-256 is
`3e0d99fe6537db18c0627158a6f076f8249b7421d8f984ab2c4de2d68ed7f575`.
This explains why Docker environment verification alone missed the effective
startup wait. The [runit manual](https://smarden.org/runit/sv.8) documents both
SVWAIT and explicit `-w`, with the explicit option taking precedence. The
[18.5 helper](https://gitlab.com/gitlab-org/omnibus-gitlab/-/raw/18.5.0%2Bce.0/files/gitlab-cookbooks/runit/libraries/helpers.rb)
uses the resource timeout to build that option, including logger restarts.
The [18.5 resource](https://gitlab.com/gitlab-org/omnibus-gitlab/-/raw/18.5.0%2Bce.0/files/gitlab-cookbooks/runit/libraries/resource_runit_service.rb)
exposes `sv_timeout`. Context7 GitLab library resolution and current docs were
consulted before these exact primary-source and pinned-package checks.

V6 appends a fixed Ruby block only to each freshly owned clone config upper.
It sets the Chef process's `ENV['SVWAIT']='60'` after the wrapper export and
makes unset runit resource waits explicit with `-w60`. An unexpected nginx
resource wait override is rejected; other explicit service waits retain their
original values. The original image, package helpers, immutable
lower, account, task bodies, scorer and original installation remain frozen.

The profile writes a bounded private native journal from the actual Chef
process and helper invocation: configuration provenance, intent before the
nginx logger command, and returned exit status. The reader requires pinned
package hashes, fresh post-container-start timestamps, root/private ownership,
explicit-w60 command, effective process environment60 and returned status0.
A config literal, unavailable command, nonzero result or incomplete intent
cannot qualify startup. The journal is read back after the single native boot;
there is no failed-startup rerun.

Common task epoch V14 uses this same backend for teacher, trusted controls,
shared base and all four selected checkpoints. The V13 native safety policy
and 90-action/720-second actor limits remain unchanged. Each native owned task
has one actual1200-second deadline from backend construction through verified
restoration. Command/readiness waits are clipped to remaining time. Known
owned rollback still runs after deadline; late restoration is recorded and
refuses qualification. The neutral three-cycle setup retains its separate
existing7200-second batch bound and has no actor/model/task credit.

**Fresh V6 neutral three-cycle qualification is mandatory before V14 TRAIN.**
The old V5 neutral proof and old two V13 trios cannot qualify the new profile.
Then run fresh V14 TRAIN, independent saved reset/process review, and fresh
full-split controls. Model/paper admission remains behind the existing full
study gates. No new native or provider job was launched for this source change.

These commands prepare metadata only. Use the original evaluator checkout
with exact current common source files; never reuse a consumed namespace.

```bash
PYTHONPATH=.:src "$BENCH_PYTHON" -m gitlab_world.v066_neutral_telemetry_coldboot_v6 \
  prepare --freeze "$PRIVATE_ORIGINAL_SOURCE_FREEZE" \
  --upstream-bindings "$PRIVATE_PINNED_UPSTREAM_BINDINGS" \
  --out "$FRESH_PRIVATE_NEUTRAL_V6" --port 8026

# Only after actual V6 three-cycle success and independent raw audit:
PYTHONPATH=.:src "$BENCH_PYTHON" -m gitlab_world.v066_uniform_task_runtime_v14 \
  prepare --neutral-plan "$FRESH_PRIVATE_NEUTRAL_V6/plan.private.json" \
  --neutral-permit "$PRIVATE_NEUTRAL_V6_PERMIT" --out "$FRESH_PRIVATE_TASK_V14"

PYTHONPATH=.:src "$BENCH_PYTHON" -m gitlab_world.v066_uniform_model_workers_v14 \
  freeze-source --out "$FRESH_PRIVATE_TASK_V14/uniform-whole-source.private.json"
```
