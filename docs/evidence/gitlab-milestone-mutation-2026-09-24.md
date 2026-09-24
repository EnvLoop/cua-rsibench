# GitLab milestone mutation qualification (2026-09-24)

One [WebArena-Verified GitLab task](https://github.com/ServiceNow/webarena-verified/tree/6473f72db5dcefc97b5725b59e734504edc28a21) was exercised through the visible UI of a disposable, locally hosted GitLab CE 18.5 instance. Task **590** asks for a `product launch` milestone in `primer/design` with a January 16, 2023 start date and January 30, 2023 due date. Its pinned upstream evaluator checks the successful response and the exact title and both dates in a real POST to the project milestone endpoint.

The actual GUI runs scored **1.0 / 0.0 / 1.0** for correct dates, a wrong due date of February 1, and correct dates again. The independent PostgreSQL readback found the exact persisted milestone values after each submission. Each case then removed the milestone and its activity event, reset the milestone sequence, and recovered the same monitored baseline for project milestones, events, and issues. The two positive cases had matching business-state hashes. The task was performed by a deterministic qualification script, **not by an AI model**.

| Case | Official score | Persisted start | Persisted due | Monitored reset |
|---|---:|---|---|---|
| Correct #1 | 1.0 | 2023-01-16 | 2023-01-30 | Passed |
| Wrong due date | 0.0 | 2023-01-16 | 2023-02-01 | Passed |
| Correct #2 | 1.0 | 2023-01-16 | 2023-01-30 | Passed |

The local project was created with [this minimal fixture](../../tools/qualify_gitlab_milestone_seed_v1.rb) in a **separate** `colima-cua-gitlab-mutation` VM. It is not the original populated WebArena GitLab database. The source dataset SHA-256 is `d65275660814663375028e9017e1f929e3c38321041b125795e2713b52243d30`, at commit `6473f72db5dcefc97b5725b59e734504edc28a21`; the real GitLab CE image digest is `sha256:f7e992491db0c80a9a3f066c2c26e69b444307b5a8834e1bdde7929c4a74e97e`. A fresh browser context with no cookies was used for each case. It navigated from the project through **Plan → Milestones → New milestone**, filled the visible form, submitted it, and inspected the resulting page. The form's date picker needed focus to leave each input before the next date was entered; a bounded, visible-UI retry resolved intermittent focus behavior.

The [machine-readable receipt](gitlab-milestone-mutation-2026-09-24.json) includes the actual sanitized milestone POST from each private HAR, its source and container hashes, independent DB readback, and reset hashes. Each extracted one-event trace was rescored by the pinned evaluator and reproduced its full-trace score. Private raw HARs, login state, and the local test password were not retained in the public evidence. Seven external Gravatar image requests per case were blocked; they did not affect the local milestone workflow. The [correct screenshot](gitlab-milestone-positive-2026-09-24.png) and [wrong-date screenshot](gitlab-milestone-wrong-due-2026-09-24.png) were visually checked against the persisted dates.

This qualifies **one** published mutation workflow and its reset on a synthetic fixture. The past 2023 dates make task 590 an infrastructure probe in September 2026, not a realistic final task. It does not qualify 100 independent GitLab final tasks, the original WebArena seed, training, or model performance.

Run the focused checks with the pinned WebArena environment:

```bash
work/scale-v06/webarena-venv/bin/python -m unittest -v tests.test_gitlab_milestone_mutation_v1
```
