# Original GitLab CE 18.5 development world

This directory builds an **original, unsealed development world** for the proposed GitLab cell of EnvLoop's computer-use study. It runs in the real `gitlab/gitlab-ce:18.5.0-ce.0` application. The fixture is not the original WebArena GitLab database, and its generated tasks do not inherit WebArena-Verified task IDs, evaluators, difficulty labels, or results.

The pinned [CISA Known Exploited Vulnerabilities mirror](https://github.com/cisagov/kev-data/tree/203fa4633af39c6944608e30984996f04ccc4541) supplies real CVE, vendor, product, advisory, and required-action facts. Its [license](https://github.com/cisagov/kev-data/blob/203fa4633af39c6944608e30984996f04ccc4541/LICENSE) is CC0 1.0; the source does not authorize use of CISA or DHS branding or imply endorsement. The 120-row excerpt in `data/kev_excerpt.json` is checked against the full catalog file SHA-256 `39099ffcf82c3f183fa6f7326900a6d82731517b2edb5cecde06dee6e04289d1`, catalog version `2026.09.24`. Internal asset IDs, users, groups, role assignments, deadlines, issue text around the advisory facts, project repositories, and merge-request scenarios are **synthetic** and identified as such in each GitLab README. No claim is made that those organizations operate the affected vendor products.

A private seed permutes the 120 advisory records into 30 four-record portfolios. Five projects produce 20 training candidates, five different projects produce 20 selection candidates, and 20 different projects produce 100 final candidates. Their project, CVE, vendor, asset, principal, and workflow-template identity sets are disjoint across all three partitions. Each project contains a source register, release policy, response runbook, security note, CI file, six deliberately similar issues, two competing merge requests, three direct members with different ACLs, and an incoming responder without baseline access. Five final task families require cross-record triage, coordinated milestones and issue linkage, selective MR merge, least-privilege access handoff, or paired CI/runbook edits. Some final actions have several GUI steps and plausible wrong-object paths. The exact private seed, task prompts, project-to-advisory assignment, and oracle targets remain under ignored `work/gitlab-full-world/` with mode `0600`.

Bootstrap uses the local GitLab API strictly to prepare fixture state. Task action controls use a fresh Playwright browser context and the original application's visible UI. The independent verifier reads PostgreSQL business columns and Git refs/blobs from the GitLab container, including all 30 projects for no-regression checks. It rejects partial target changes, wrong issues or MRs, overprivileged access, unrelated repository changes, and missing saved state. A stopped seeded volume set forms read-only overlayfs lowerdirs. Each cold-reset attempt receives a fresh overlay upperdir and a new CE container, then must reproduce the same monitored business-state digest before the next task starts. This is copy-on-write reset of application state, not a cleanup routine that relies on deleting only named task objects.

The separate pre-existing `cua-v06-gitlab-demo` container is stopped while the disposable world uses its dedicated Colima VM. Its ID, image, mounts, ports, and health are recorded before the stop and checked after restart. The disposable instance binds only `127.0.0.1:8014`. The generated credential, API token, raw traces, and task gold are never committed.

Run locally with an available Colima `cua-gitlab` profile and the pinned GitLab image:

```bash
PYTHONPATH=. python3 -m gitlab_world.runtime start
PYTHONPATH=. python3 -m gitlab_world.bootstrap --max-projects 30
PYTHONPATH=. python3 -m gitlab_world.verify save-baseline
PYTHONPATH=. python3 -m gitlab_world.reset freeze
PYTHONPATH=. /path/to/python-with-playwright -m gitlab_world.gui_controls --task-id <private-id>
PYTHONPATH=. python3 -m gitlab_world.reset restore-demo
```

The first command requires a healthy preserved demo and writes private credentials automatically. The actual experiment needs a sealed identity/gold manifest, source-family preregistration, 100 individual positive/negative/cold-reset admissions, matched model harness, and all campaign/evaluation records before a GitLab result can be reported. **An offline 100-task inventory, one GUI trio, or a passing synthetic oracle test has zero official final admissions.**

GitLab fixture setup follows the official [projects](https://docs.gitlab.com/api/projects/), [issues](https://docs.gitlab.com/api/issues/), [milestones](https://docs.gitlab.com/api/milestones/), [members](https://docs.gitlab.com/api/project_members/), [repository commits](https://docs.gitlab.com/api/commits/), and [merge requests](https://docs.gitlab.com/api/merge_requests/) API documentation. Context7 documentation lookup reached its monthly quota during development; these primary docs and the running 18.5 instance were used for API verification.
