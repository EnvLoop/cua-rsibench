# Office Terminal First Spool Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Apply each fresh model action through the existing native Office bridge before its frame expires, with the credential-bearing terminal started before capture.

**Architecture:** A CUA-side filesystem helper owns observation, exclusive request publication, bounded response waiting and native dispatch. A separately started terminal waiter validates the session and each frame, invokes the existing root-owned sampler once, and publishes a hash-bound private response. Either side poisons and stops a consumed session after timeout, uncertainty or mismatch; no request is resubmitted.

**Tech Stack:** Existing Node filesystem/crypto/path APIs, Python standard library and the unchanged Office bridge and Qwen base sampler.

---

### Task 1: Establish the private protocol

Create `tools/office_local_browser_terminal_spool_v1.mjs` and `tools/office_local_browser_terminal_waiter_v1.py`. Session metadata binds the native admission, instruction, both helper sources, maximum steps and existing actor wall-clock lease. Require private regular files with exact hashes, exclusive session/start/request/intent/output writes, fixed relative paths and no symlinks. The waiter must publish readiness before CUA observes.

### Task 2: Implement one bounded CUA frame transaction

Write `tests/test_office_local_browser_terminal_spool_v1.mjs` before implementation. Cover not-ready refusal before observation, successful repeated fresh frames, hash/nonce mismatch, late response, poison/no replay, concurrent calls and finish/stop. The helper must use only `bridge.observe`, `bridge.dispatch`, `bridge.stop` and private filesystem operations, with no process import, subprocess, provider or page-content API. Each call uses a maximum 55-second deadline within a 60-second CUA tool budget. Existing frame lifetime remains at most 150 seconds.

Run `node --test tests/test_office_local_browser_terminal_spool_v1.mjs`. First expect missing-module failure, then all protocol tests passing.

### Task 3: Implement the separate terminal waiter

Write `tests/test_office_local_browser_terminal_waiter_v1.py` before implementation. Use injected synthetic sampler functions to cover startup readiness, two distinct frames, consumed intent refusal, changed frame/context/source, uncertain provider failure, late completion and stop. Never create credentials or start a real sampler in tests. Production invocation uses the existing clean-runtime Python and shell environment; every request uses the unchanged one-frame sampler and its native admission checks.

Modify `tools/office_local_browser_qwen_base_sampler_v1.py` and its existing test to pass the previous applied context into frame admission as well as normalization. The two-frame test found that admission otherwise refused step one before inference. Preserve the admission schema, clean-runtime gate and source hashes; root must bind the updated sampler source in the next review.

Run `PYTHONPATH=.:src python3.14 -m unittest tests.test_office_local_browser_terminal_waiter_v1 -q`. First expect missing-module failure, then all waiter tests passing.

### Task 4: Review, regression and handoff

Run the new tests and existing 23 Node bridge and 11 Python bridge/sampler tests. Add English source-only documentation with terminal startup before capture, one frame per bounded CUA call, repeated-frame context and mandatory no-replay/poison/stop behavior. Record source-only status; retain the earlier native diagnostic unchanged. Commit the isolated worktree changes for root review and cherry-pick. No native UI, provider, saved-state, reset or scoring qualification is performed here.
