# GitLab member expiry date-only application repair

GitLab CE 18.5.0's member-invite frontend passed the datepicker's JavaScript `Date` directly into JSON. In an Asia/Shanghai browser, a selected October 22, 2026 local midnight became `2026-10-21T16:00:00.000Z`. The backend's date column consequently persisted October 21. Both normal text entry and selecting calendar day 22 produced this mismatch.

The repaired application build formats the selected local year, month and day as `YYYY-MM-DD` before transport. It changes neither the selected date, browser timezone, task specification, scoring nor reset data. The original build and failing outcomes remain separate provenance.

## Build

Requires Docker with the original CE 18.5.0 image available. The builder pins the base image digest and checks the exact original and repaired frontend asset hashes. It includes plain and gzip assets with the original readable `0644` permissions.

```sh
python tools/build_gitlab_member_date_only_image.py \
  --docker-context colima-cua-gitlab \
  --image envloop/gitlab-ce-date-only:18.5.0-fix2 \
  --output work/gitlab-date-only/application-build.json
```

The output records the actual image ID. Verify the HTTP-served asset for plain and compressed requests before a live qualification. The adapter additionally checks asset readability as `gitlab-www` and the exact image/asset identity on each owned reset cycle.

## Use in a native run

Wrap the existing backend's `open` call, including both reset cycles, in the new application scope:

```python
import json
from gitlab_world.member_date_application_epoch import application_epoch_scope

with open("work/gitlab-date-only/application-build.json") as stream:
    application_epoch = json.load(stream)

with application_epoch_scope(application_epoch):
    with backend.open(original_task_identity) as active:
        # Run the existing guarded GUI recipe, finish, then mandatory saved read.
        run_original_recipe(active)
        saved = active.read_saved_state()
```

Keep the existing native lease, guard, action/key contract, actor and reset budgets. Record the application-build receipt next to results. This scope changes only owned clone images; original-before and resumed-original checks keep their original image contract. No model or provider call is required.

## Verified result

The same original member/calendar task and unchanged verifier passed a real native whole trio: baseline 0, Reporter positive 1, Guest wrong-variant 0. Positive and wrong-variant SQL both persisted the policy date `2026-10-22`. Each case restored the original identity, SQL, all 33 Git repositories and protected seed over two owned reset cycles. Six distinct clones and 594 raw Git references were independently checked.

The scalar evidence is in `docs/evidence/gitlab-member-date-only-repair.json`. This qualifies the repaired application for that whole trio; it does not claim a completed selection20 or model improvement. Private task bodies, accounts, SQL snapshots, screenshots and application assets are excluded from this publication.
