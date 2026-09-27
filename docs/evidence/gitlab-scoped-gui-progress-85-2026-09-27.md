# GitLab scoped-GUI admission progress — 2026-09-27

The [previous aggregate control receipt](gitlab-scoped-gui-progress-75-2026-09-27.md) records the earlier GitLab CE 18.5 evaluator-private checks. This bounded serial batch used untouched candidate IDs. Prior per-ID records are unchanged in the private index, and every invalid attempt remains in the mode-0600 SHA-chained ledger. No task ID, prompt, answer, project identity, screenshot, credential, or raw action trace is published.

| Cumulative final-candidate GUI controls | Count |
| --- | ---: |
| Distinct IDs attempted | 85 / 100 |
| Distinct project source families attempted | 20 / 20 |
| Native-GUI correct / plausible wrong / repeated correct trios passed | 81 |
| Failed or infrastructure-invalid IDs | 4 |
| Unattempted IDs | 15 |
| Cold resets bound to passed IDs | 243 |
| Official final IDs admitted | **0** |

This batch attempted **10 untouched IDs** within the 20 already-attempted project source families: **10 passed** and **0 failed or infrastructure-invalid**. The [machine-readable aggregate](gitlab-scoped-gui-progress-85-2026-09-27.json) contains per-workflow counts. Every pass has independent saved-state and no-regression readback, 1/0/1 GUI scores, and three fresh cold resets. The append-only ledger has 4 verified entries; no failed ID was silently retried or converted into a model failure. The original demo was restored healthy with its pre-stop container identity.

The remaining **15** candidates lack a per-ID control. These deterministic GUI qualification checks are separate from Qwen's screenshot-only action policy. No paid training, selection feedback, researcher campaign, or official final admission is claimed. CI YAML persistence has been checked, while runner execution remains unproven. The GitLab cell remains **0/100 officially admitted** until all per-ID and global pre-campaign gates pass.
