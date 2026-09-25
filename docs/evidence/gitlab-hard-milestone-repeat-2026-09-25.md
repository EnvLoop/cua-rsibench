# Hard GitLab milestone mutation: fresh-clone development control

Pinned WebArena-Verified GitLab task **590** belongs to the published hard subset. It was repeated on a fresh disposable GitLab CE 18.5 container made from image `sha256:f7e992491db0c80a9a3f066c2c26e69b444307b5a8834e1bdde7929c4a74e97e`. The task and evaluator came from commit `6473f72db5dcefc97b5725b59e734504edc28a21`, dataset SHA-256 `d65275660814663375028e9017e1f929e3c38321041b125795e2713b52243d30`. This was a deterministic GUI control with no model or paid-provider calls.

| Fresh browser attempt | Unchanged official score | Independent PostgreSQL target readback | Monitored reset |
| --- | ---: | --- | --- |
| Correct milestone | 1.0 | Persisted requested values | Passed |
| Plausible wrong due date | 0.0 | Persisted the wrong date on the intended milestone | Passed |
| Correct milestone again | 1.0 | Persisted requested values | Passed |

Raw and field-limited HARs reproduced the same score in every case. The independent oracle checked the project milestone row and monitored project events, issues, and milestone sequence. Each GUI attempt was followed by a reset to the identical baseline; the final monitored state matched the pre-run state. The disposable mutation clone was removed. The pre-existing GitLab demo was paused to provide memory, then restarted healthy with the same container identity, image digest, ports, and volume destinations. The [field-limited machine receipt](gitlab-hard-milestone-repeat-2026-09-25.json) includes hashes and scores without source answer values, credentials, or raw HAR.

The local project was a **minimal synthetic fixture**, not the original populated WebArena GitLab database. Its source task refers to historical dates. This repeat qualifies one hard GUI/evaluator/SQL/reset development workflow, not a realistic hidden final instance or a 100-task GitLab cell. Official final admitted count remains **zero**.
