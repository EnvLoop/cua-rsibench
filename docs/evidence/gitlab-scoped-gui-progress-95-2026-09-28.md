# GitLab scoped-GUI admission progress — 2026-09-28

The [previous aggregate control receipt](gitlab-scoped-gui-progress-85-2026-09-27.md) records the earlier GitLab CE 18.5 evaluator-private checks. This bounded serial batch used untouched candidate IDs. Prior per-ID records are unchanged in the private index, and every invalid attempt remains in the mode-0600 SHA-chained ledger. No task ID, prompt, answer, project identity, screenshot, credential, or raw action trace is published.

| Cumulative final-candidate GUI controls | Count |
| --- | ---: |
| Distinct IDs attempted | 95 / 100 |
| Distinct project source families attempted | 20 / 20 |
| Native-GUI correct / plausible wrong / repeated correct trios passed | 90 |
| Failed or infrastructure-invalid IDs | 5 |
| Unattempted IDs | 5 |
| Cold resets bound to passed IDs | 270 |
| Official final IDs admitted | **0** |

This batch attempted **10 untouched IDs** within the 20 already-attempted project source families: **9 passed** and **1 failed or infrastructure-invalid**. The [machine-readable aggregate](gitlab-scoped-gui-progress-95-2026-09-28.json) contains per-workflow counts. Every pass has independent saved-state and no-regression readback, 1/0/1 GUI scores, and three fresh cold resets. The append-only ledger has 5 verified entries; no failed ID was silently retried or converted into a model failure. The original demo was restored healthy with its pre-stop container identity.

The new infrastructure-invalid attempt had a saved first positive, then its disposable clone exited code 1 during GitLab Omnibus startup. The container log records an alertmanager log-service restart timeout; the event coincided with host thermal deep-idle sleep. The bounded readiness wait expired without a verified cold baseline. Its first attempt remains failed in the ledger. After private forensic capture, one exact cold reset restored the frozen business baseline, and the remaining untouched IDs continued in a separate bounded run.

The remaining **5** candidates lack a per-ID control. These deterministic GUI qualification checks are separate from Qwen's screenshot-only action policy. No paid training, selection feedback, researcher campaign, or official final admission is claimed. CI YAML persistence has been checked, while runner execution remains unproven. The GitLab cell remains **0/100 officially admitted** until all per-ID and global pre-campaign gates pass.
