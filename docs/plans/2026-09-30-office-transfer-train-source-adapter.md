# Office transfer TRAIN source adapter Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let the existing lightweight single-account manual auditor recognize the explicitly declared four-target PowerPoint transfer TRAIN source profile.

**Architecture:** Add a narrow source-profile classifier and exact package-path rule to the existing manual auditor. Keep the PowerPoint saved-artifact verifier and every existing GUI provenance, actor/reset identity, private screenshot, folder inventory and exact double-download condition unchanged. This enables a future complete manual evidence collection; it cannot convert the present aggregate controls into missing observations or authorize a model/selection/final run.

**Tech Stack:** Python standard library, existing WDI source and OOXML verifier, unittest.

---

### Task 1: Specify source and namespace refusals

- Modify `tests/test_office_single_account_train_pilot_v1.py` with focused classifier/path tests for legacy TRAIN, transfer TRAIN, wrong split, wrong target contract, wrong source/template/rights declaration and misleading nested paths.
- Run the focused new tests and confirm the classifier/path helper is absent.

### Task 2: Add the narrow adapter

- Modify `tools/office_single_account_train_pilot_v1.py` to classify only the original one-target TRAIN profile and the explicit source-disjoint four-target transfer declaration.
- Accept the transfer package directory only for PowerPoint, with its exact private task directory and logical manual `split=train` preserved.
- Retain independent source freeze, native baseline/positive/reset scoring and all phase evidence checks.
- Bind the admission adapter and source-profile definition in verifier source commitments.

### Task 3: Verify real artifacts and preserved evidence gates

- Run the focused unit tests and existing single-account/candidate/staging suites once.
- Replay the real private transfer source, native baseline, saved positive and fresh reset through `OfficeTrainScorer` without constructing a missing inventory or writing a passing manual receipt.
- Record the remaining live collection and automated worker gates in portable English documentation; publish counts and hashes only.
- Commit only code, tests, plans and redacted documentation in the isolated checkout.
