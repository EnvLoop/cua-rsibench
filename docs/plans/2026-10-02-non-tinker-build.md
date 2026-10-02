# Non-Tinker Benchmark Build Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build and verify the six real-software benchmark components and their distribution path while training is unavailable.

**Architecture:** Preserve each frozen actor, task and verifier epoch. Repair environment execution in scoped additive implementations when required, and keep qualification distinct from model results. A portable source-layout runner packages the application adapters, generators, independent verifiers and report tooling without secrets, private task state or an active training provider.

**Tech Stack:** Python, Docker, Playwright, native accessibility, original Office web, Odoo Community, GitLab CE, Magento, independent artifact/SQL/Git verifiers.

---

### Task 1: Enterprise environment execution

**Files:** Current entrypoints under `enterprise_fallback/odoo18/`, `gitlab_world/`, and Magento runtime modules; corresponding focused tests and environment documentation.

Inspect actual failed native execution receipts. Repair the next environment-only execution defect, build or validate the owned container configuration, and execute a genuine saved positive/negative/reset control where possible. Preserve prior source epochs and errors. Do not invoke Tinker or synthesize a model result.

### Task 2: Native Desktop execution

**Files:** `native_desktop_factory/native_terminal_hit_diagnostic_v38.py`, its focused tests, current native guard/launcher modules, and Desktop documentation.

Use retained native window and forward-child evidence to resolve the ownership defect. Verify a fresh owned native control and guest closure before claiming qualification. Do not accept arbitrary parent-chain exceptions or substitute file-only verification for GUI execution.

### Task 3: Lightweight Office lifecycle

**Files:** `tools/office_current_*_v4.py`, owned-folder browser bridge modules, current task factories and their focused tests.

Repair the actual upload/save/download/reset path using the existing single account. Verify the independent spreadsheet and presentation oracles and a bounded original-software lifecycle if available. Keep account state and private artifacts out of public packages.

### Task 4: Portable build and distribution

**Create:** `deployment/non-tinker-runner/Dockerfile`, `deployment/non-tinker-runner/requirements.txt`, `tools/build_non_tinker_source_bundle_v1.py`, `tools/non_tinker_runner_smoke_v1.py`, focused bundle-boundary tests and build documentation.

Stage only explicit source roots and public runtime configuration. Reject private files, links escaping the checkout and credential values. Produce a deterministic archive with file hashes, build the actual runner image, and run import, browser, artifact and verifier smoke checks inside it. Tinker access and benchmark model scores are not prerequisites for this build.

### Task 5: Integrate and report verified readiness

Reopen returned environment evidence; run tests appropriate to changed behavior. Generate English build/readiness evidence that separates source compilation, actual container execution, native qualification and unrun model outcomes. Commit and push the concrete implementation. A successful build is not a completed six-environment research result.
