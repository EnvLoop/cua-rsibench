# Two SaaS cells: source-pinned admission queues, not final results

The pinned [WebArena-Verified source](https://github.com/ServiceNow/webarena-verified/tree/6473f72db5dcefc97b5725b59e734504edc28a21) contains 182 Magento-admin single-site task IDs in 41 intent-template families and 180 GitLab single-site IDs in 41 families. The dataset and hard-subset SHA-256 values are respectively `d65275660814663375028e9017e1f929e3c38321041b125795e2713b52243d30` and `3b0a4df231bb5a0c642215e521c3fa97701a384f52a734dc2db8f617ad0591a7`. The planners reject byte drift. They write **private candidate metadata only**, never instructions or evaluator answers.

The [cross-cell builder](../../tools/build_saas_admission_matrix_v06.py) combines the [existing Magento planner](../../tools/plan_magento_final_candidates_v06.py) with the new [GitLab planner](../../tools/plan_gitlab_final_candidates_v06.py). It emits a per-task pending-gate matrix. Its output is stored under ignored `work/`, with no public task-identity manifest.

| Offline property | Magento admin | GitLab |
| --- | ---: | ---: |
| Published single-site IDs | 182 | 180 |
| Published hard-subset IDs | 55 | 57 |
| Selection candidates | 20 | 20 |
| Provisional final candidates | 100 | 100 |
| Selection / final template families | 5 / 32 | 4 / 30 |
| Hard-subset IDs in provisional final | 44 | 36 |
| Successful mutation / retrieval / navigation in provisional final | 58 / 37 / 5 | 77 / 16 / 7 |
| Explicit selection-entity overlaps excluded before final selection | 8 | 37 |
| Official sealed final identities admitted | **0** | **0** |

All 200 provisional final records have the published expected status `SUCCESS`. Entire selection template families are withheld from final, and no selected task ID recurs in final. The GitLab planner also rejects explicit cross-split project, principal, issue, and merge-request hints from source fields and literal project URLs. The Magento planner excludes its own explicit entity hints. These are limited source checks: a common seeded database object can still be reached through different names or workflows. The public upstream source contains task instructions and evaluator answers, so withholding the generated queue does **not** create a hidden final exam.

The Magento queue preserves its [prior status and evaluator audit](magento-100-candidate-admission-2026-09-24.md). It excludes two policy-denial records from the successful-mutation cohort, one inconsistent product-save assertion, and an unqualified price-template family. Task 538 is now assigned to a **train-only visible-GUI demonstration**. Its entire five-task template family and any exact source-entity-hint match are excluded from both candidate splits; the latter removed zero additional source records in this pinned revision. The prior task-538 address-edit receipt remains a narrow real-GUI, independent SQL, wrong-order, and monitored-reset development control, not final-test evidence. The five removed mutation candidates were deterministically refilled by other published successful tasks, leaving 58 mutation and 37 retrieval candidates. The GitLab queue excludes the five published non-success outcomes and source/evaluator mismatch at task 102. A new [GitLab task-258 GUI probe](gitlab-public-projects-gui-probe-2026-09-25.md) found the visible destination but an official 0.0 because the current GitLab CE request omitted a required evaluator query option; task 258 is now also quarantined. The earlier task-590 milestone control used a synthetic fixture rather than the populated WebArena seed. None of these controls admits 100 final tasks.

Each provisional task in the private matrix remains pending an authentic fresh seed, native GUI positive and plausible negative attempts, an independent oracle for saved state or browsing/destination, unrelated-state preservation, exact reset, the fixed student observation/action contract, and an evaluator-owned unpublished variant with sealed answers. Tasks with stale 2023 dates or clone-specific behavior need replacement or revalidation before any frozen final set. The source queue is useful for qualification and calibration; it is **not** a scored full-scale study or a Tinker training result.

Rebuild the ignored private artifacts from the pinned checkout:

```bash
python3 tools/build_saas_admission_matrix_v06.py \
  --source work/scale-v06/sources/webarena-verified/assets/dataset/webarena-verified.json \
  --hard-ids work/scale-v06/sources/webarena-verified/assets/dataset/subsets/webarena-verified-hard.json \
  --out-dir work/scale-v06/saas-admission
python3 -m unittest -v \
  tests.test_plan_magento_final_candidates_v06 \
  tests.test_plan_gitlab_final_candidates_v06 \
  tests.test_build_saas_admission_matrix_v06
```
