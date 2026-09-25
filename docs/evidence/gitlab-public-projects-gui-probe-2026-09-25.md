# GitLab public-projects navigation: visible GUI and evaluator disagree

An isolated, locally hosted GitLab CE 18.5 demo was used to probe one published [WebArena-Verified task](https://github.com/ServiceNow/webarena-verified/tree/6473f72db5dcefc97b5725b59e734504edc28a21), task 258. The source dataset was pinned to SHA-256 `d65275660814663375028e9017e1f929e3c38321041b125795e2713b52243d30`; its evaluator and task record were not edited. This was a deterministic, read-only GUI control with **zero model and paid-provider calls**, not a benchmark model attempt. The demo contains no original populated WebArena GitLab seed.

| Fresh-browser case | Visible destination | Published response evaluator | Published network evaluator | Whole-task score |
| --- | --- | ---: | ---: | ---: |
| Requested public-projects page | `Explore projects` | 1.0 | 0.0 | **0.0** |
| Plausible wrong destination | `Milestones` | 1.0 | 0.0 | **0.0** |

The requested page opened through GitLab's visible search/context menu and returned HTTP 200. Its observed navigation request omitted a query option required by the pinned network assertion. Raw and credential-stripped HARs gave the same official scores. A read-only PostgreSQL fingerprint of `todos`, `projects`, `issues`, and `merge_requests` was identical before the positive case, after it, and after the wrong-route case. Only local GitLab requests were allowed during the task context; external image requests were blocked. The [field-limited receipt](gitlab-public-projects-gui-probe-2026-09-25.json) publishes hashes and scores without source answer fields, login state, or raw HAR.

**Admission decision:** quarantine task 258 for this GitLab CE 18.5 environment. The current evaluator cannot distinguish the visible correct destination from the wrong route in this probe. This does not show that the published task is invalid on its original software version, nor does an unseeded demo qualify source-data-dependent tasks. Re-admission requires a version-matched populated seed or a separately reviewed evaluator-owned variant, plus a new positive/negative GUI run and exact state reset. No official final task was admitted.
