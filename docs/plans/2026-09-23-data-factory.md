# Executable Data Factory Implementation Plan

**Goal:** Let a researcher write and revise executable training-data generation code and submit newly grounded, verified browser experiences through fixed services.

**Architecture:** A controller owns source partitions, budgets, rollout verification, training, and evaluation. A disposable E2B workspace runs researcher-written Python without provider credentials, host mounts, or internet access. Researcher actions can edit/run code and request bounded training rollouts; only controller-verified artifacts can become positive demonstrations.

**Tech Stack:** Python, E2B, the existing native Kanboard v3 observer, durable command journal, AgentRouterHub, Tinker, Harbor.

## Decisions

Extend the research interface to executable code rather than adding more fixed selectors. Keep the first application contract explicit: native Kanboard task states, source-grounded selection/planning policies, and persisted field updates. This boundary is a task profile, not a claim that every computer-use domain is implemented. New application profiles will use the same researcher/service contract.

Do not open algorithm, harness, or architecture mutation during a Data study. Keep v0.4 evidence and reports frozen. All public material remains English.

## Task 1 - Source registry and grounded task compiler

Create `src/cursibench/factory_cases.py` and `tests/test_factory_cases.py`.
- Controller-only source partition validation, with a train-only export.
- Compile researcher-produced case specifications into original Kanboard scenarios and host-only targets.
- Support direct action lessons, conditional/ranked selection, and constrained allocation from authentic records and explicitly synthetic planning inputs.
- Reject unknown/evaluation sources, duplicates, malformed predicates, impossible goals, and excess sizes.
- Tests must include forbidden-source access, falsified source facts, no-op cases, and independently computed targets.

## Task 2 - Isolated executable workspace and accounting

Create `factory_workspace.py`, `factory_budget.py`, and focused tests.
- E2B workspace, no internet or provider credentials; no host project/evaluation files uploaded.
- Constrained artifact paths and byte limits; bounded Python execution with durable command IDs.
- Controller-owned append-only budget accounting. Uncertain executions consume reservations and cannot bypass limits through retries.
- Live isolation probe and researcher-authored program execution.

## Task 3 - Canonical GUI contract and verified rollout service

Create `factory_rollout.py` and reuse the v3 observer and command journal.
- One prompt constructor for teacher records and student evaluation.
- Fresh real Kanboard state for every generated case; all teacher edits go through the GUI.
- Independent final-state verification, per-action trace and failure retention.
- Positive examples are reconstructed from trusted trace evidence; submitted claims alone cannot establish success.

## Task 4 - Researcher tool loop

Create `factory_research.py` with read/write/run/rollout/submit actions.
- Astra/Sol may write and revise Python, generate case specifications, inspect permitted rollout evidence, and change data mixtures/representations.
- The controller validates each boundary and exposes no arbitrary host shell/file tool.
- Preserve source code revisions, hypotheses, receipts, budget events, rejected submissions, and final artifacts.
- Execute a real bounded researcher session and verify at least one newly generated native rollout.

## Task 5 - Training/evaluation integration and next study

Connect validated submissions to fixed Tinker training and Harbor evaluation. Calibrate multiple task instances with the student before another multi-round search. Add fresh evaluation partitions and non-recursive/repeated-seed controls before stronger attribution claims. Record missing evidence explicitly; do not mark the overall goal complete after a workspace smoke test.

## Verification

Run focused boundary tests and the existing suite. For cloud checks, inspect actual process results, code/data hashes, native saved state, and sandbox cleanup. Mock tests prove boundary behavior only; they never supply capability scores. Keep development runs bounded rather than adopting the reference paper's monetary budget.

## Execution update

- Source compiler and protected-source checks implemented.
- Live workspace isolation passed after adding a per-program network namespace.
- Astra and Sol each generated two independently verified native episodes and valid datasets.
- Controller interruption recovery retained Sol's completed rollouts and completed submission without rerunning them.
- Both datasets trained for 32 real optimizer steps under one configuration; all rows were covered.
- A multi-task proxy capacity bug was reproduced at exactly 256 samples, fixed, and retained as a separately versioned repair.
- The repaired initial comparison is scored: base 0/3, Astra-data checkpoint 1/3, Sol-data checkpoint 0/3. Feedback-driven factory revisions are now running.
- Add counterbalanced layouts/target values to the next calibration to distinguish workflow learning from positional shortcuts. Do not retrofit the frozen three-case comparison.
