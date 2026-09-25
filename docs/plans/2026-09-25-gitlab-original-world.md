# GitLab Original World Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Produce a realistic, resettable GitLab CE 18.5 development world and a fail-closed path from 20/20/100 candidate identities to individual GUI admission.

**Architecture:** A pinned CC0 CISA KEV excerpt supplies real advisory facts; an explicitly synthetic internal operations layer supplies projects, employees, ownership, source documents, issues, merge requests, and access roles. A disposable GitLab CE container hosts the world. Bootstrap uses the application API; candidate actions use only the visible browser. The independent oracle reads PostgreSQL and persisted Git objects and compares the intended change with a frozen unrelated-state baseline. No candidate becomes an official final task from offline generation alone.

**Tech Stack:** Python standard library, GitLab CE 18.5, Docker/Colima, PostgreSQL, Playwright, GitLab REST API for fixture setup only.

---

### Task 1: Pin the real source and construct split-disjoint candidate identities

**Files:** `gitlab_world/data/kev_excerpt.json`, `gitlab_world/factory.py`, `tests/test_gitlab_original_world_factory.py`

1. Freeze the CISA `cisagov/kev-data` commit and full-file digest, then extract 120 distinct vendor records into a small CC0 excerpt with provenance.
2. Write tests for 5 train, 5 selection, and 20 final project families; distinct CVE/vendor/project/principal/template sets; exactly 20/20/100 unsealed tasks; and independent task identity hashes.
3. Implement deterministic private-seed generation of code/repository files, noisy issues, release policy, role map, MR branches, prompts, and evaluator-only targets.
4. Run the focused tests and commit the source pin/factory.

### Task 2: Bootstrap an isolated, real GitLab world

**Files:** `gitlab_world/runtime.py`, `gitlab_world/bootstrap.py`, `gitlab_world/README.md`, `tests/test_gitlab_original_world_runtime.py`

1. Prove and record the pre-existing GitLab demo container ID, image, mounts, ports, and health.
2. Stop that demo without deleting it; start a fresh-volume disposable CE 18.5 container on a distinct loopback port with a generated private credential.
3. Create users, groups, projects, repository files, issues, labels, and two plausible MRs per project from the private manifest; no outbound invitations.
4. Verify actual GUI render, source asset counts, and restricted access on the real instance.

### Task 3: Independent oracle and cold reset

**Files:** `gitlab_world/verify.py`, `gitlab_world/reset.py`, `tests/test_gitlab_original_world_verify.py`

1. Snapshot monitored business columns across the split namespace in PostgreSQL and exact selected Git refs/file content from storage.
2. Compare post-action state to target conditions and reject all unrelated changes, wrong objects, overprivileged grants, stale source branches, and partial edits.
3. Freeze the entire stopped-state data/config/log volumes and restore an isolated clone for each GUI attempt. Fail on untracked state or mismatched baseline digest.
4. Test a correct and plausible incorrect action, checking score 1/0 and restoration of the same baseline.

### Task 4: GUI admission sweeper and evidence

**Files:** `gitlab_world/gui_controls.py`, `gitlab_world/sweep.py`, `docs/evidence/gitlab-original-world-development-2026-09-25.{md,json}`

1. Complete representative positive and near-miss GUI controls using fresh browser sessions and saved-state readback.
2. For every final candidate ID, run the same per-ID positive, near-miss, and cold-reset control. Mark unattempted/failed cases pending or rejected, never admitted by inventory.
3. Publish only field-limited, English pre-result evidence, source/license facts, exact attempted/qualified/admitted counts, and unresolved blockers. Keep private manifests, gold, credentials, and raw network recordings ignored.
4. Remove the disposable world and verify the original demo returns healthy with unchanged identity, image, mounts, and ports.

This plan defines work still to execute. It does not constitute a frozen 100-task cell or a measured researcher campaign.
