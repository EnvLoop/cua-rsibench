# GitLab Pre-Result Recovery Implementation Plan

> Implement each gate independently and retain its dated evidence before proceeding.

**Goal:** Preserve the original GitLab GUI-control failures while restoring a prospective 100-ID final candidate roster through one bounded requalification and whole-family FIFO replacement.

**Architecture:** A pure evaluator-side module commits five unseen source families from the already pinned CISA catalog without consulting outcomes. A completed first-attempt index and hash-chained ledger determine one-time requalification eligibility; any unresolved failure retires its full five-task project family. Runtime replacement and final admission remain separate gates.

**Tech Stack:** Python standard library, GitLab CE 18.5 fixture, private mode-`0600` JSON, existing PostgreSQL/Git verifier and overlayfs reset.

---

### Task 1: Freeze a prospective reserve queue

**Files:** Create `gitlab_world/pre_result_recovery.py`, `tests/test_gitlab_pre_result_recovery.py`, and `docs/evidence/gitlab-pre-result-recovery-queue-2026-09-28.json`.

1. Verify the full CISA catalog bytes against the already pinned digest.
2. Exclude all existing project CVEs/vendors, choose one unused CVE per unused vendor by seed-keyed HMAC, and group the first 20 into five complete projects.
3. Reject any source/project/asset/principal/task collision; store the ordered private queue exclusively in mode `0600` and publish only its digest and aggregate counts.
4. Run `PYTHONPATH=. python3 -m unittest tests.test_gitlab_pre_result_recovery -v`; expect the queue/disjointness/privacy tests to pass.

### Task 2: Bind first failures and one-time retries

**Files:** Modify `gitlab_world/sweep.py` and `gitlab_world/gui_workflows.py`; extend `gitlab_world/pre_result_recovery.py`, add `tools/probe_gitlab_milestone_save_train_v1.py`, and add focused tests.

1. Finish the existing untouched-ID sweep without changing it and confirm exactly 100 original active IDs in the private index.
2. Run both generic milestone and issue-triage save/reload training trios after the serial sweep ends. Freeze each v2 private summary plus all case receipts, their DB/Git baseline hashes and exact operator/probe script bytes. Freeze a first-attempt resolution from the index plus verified hash-chained ledger. Bind the original roster and first-attempt digest; require separate `{path,sha256}` references for every deterministic GUI workflow offered requalification.
3. Run `--retry-failed` only with the frozen mode-`0600` plan, on a fresh clone with the same full GUI trio and three resets; append every second failure and never erase first attempts.
4. Run the targeted recovery, sweep, and ledger tests; expect unplanned retries, third attempts, ledger drift, and incomplete denominators to fail closed.

### Task 3: Retire and replace complete project families

**Files:** Extend `gitlab_world/pre_result_recovery.py`, `bootstrap.py`, `quarantine.py`, `runtime.py`, `reset.py`, `verify.py`, and tests as needed after the terminal first-attempt audit.

1. Sort unresolved source families by first failure-ledger sequence and assign the committed queue FIFO, never by observed difficulty.
2. Bootstrap each replacement in the real GitLab application; preserve prior seed volumes and promote a new scoped-ACL baseline, one generation at a time.
3. Execute and retain all five positive/near-miss/repeated-positive GUI trios and three independent cold resets per replacement ID; retire a failed replacement as a whole and consume the next queue position, up to five total.
4. Audit a final 20-family/100-ID active roster, split/source/principal isolation, immutable originals, runtime hashes, and zero unclassified failures before a GitLab official-final freeze is considered.
