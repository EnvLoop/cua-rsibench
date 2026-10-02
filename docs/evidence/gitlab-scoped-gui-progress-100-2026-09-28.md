# GitLab scoped-GUI admission progress — 2026-09-28

The [previous aggregate control receipt](gitlab-scoped-gui-progress-95-2026-09-28.md) records the earlier GitLab CE 18.5 evaluator-private checks. This bounded serial batch used untouched candidate IDs. Prior per-ID records are unchanged in the private index, and every invalid attempt remains in the mode-0600 SHA-chained ledger. No task ID, prompt, answer, project identity, screenshot, credential, or raw action trace is published.

| Cumulative final-candidate GUI controls | Count |
| --- | ---: |
| Distinct IDs attempted | 100 / 100 |
| Distinct project source families attempted | 20 / 20 |
| Native-GUI correct / plausible wrong / repeated correct trios passed | 94 |
| Failed or infrastructure-invalid IDs | 6 |
| Unattempted IDs | 0 |
| Cold resets bound to passed IDs | 282 |
| Official final IDs admitted | **0** |

This batch attempted **5 untouched IDs** within the 20 already-attempted project source families: **4 passed** and **1 failed or infrastructure-invalid**. The [machine-readable aggregate](gitlab-scoped-gui-progress-100-2026-09-28.json) contains per-workflow counts. Every pass has independent saved-state and no-regression readback, 1/0/1 GUI scores, and three fresh cold resets. The append-only ledger has 6 verified entries; no failed ID was silently retried or converted into a model failure. The original demo was restored healthy with its pre-stop container identity.

The new failure is a deterministic **0/0/1** GUI trio. Its first positive displayed the intended milestone while the Milestone section save spinner was active, but independent PostgreSQL readback found one required issue link still at baseline. The wrong-date control failed as intended and the repeated positive passed; all three cold resets were verified. This first attempt stays failed. Across the 100 attempted IDs, four failures are infrastructure-invalid and two are deterministic GUI-control failures.

All **100** candidates have an attempted per-ID control, but **6** failed or infrastructure-invalid IDs have not passed qualification. These deterministic GUI qualification checks are separate from Qwen's screenshot-only action policy. No paid training, selection feedback, researcher campaign, or official final admission is claimed. CI YAML persistence has been checked, while runner execution remains unproven. The GitLab cell remains **0/100 officially admitted** until all per-ID and global pre-campaign gates pass.
