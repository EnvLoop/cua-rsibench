# Alignment with RSIBench

Reviewed against the [research surfaces](https://rsibench.co/#surfaces), the [Data release](https://rsibench.co/data/), and [paper sections 3-6 and Appendix B](https://arxiv.org/html/2607.25886v1).

## Released work versus roadmap

The website marks Data as open. Algorithm, Agent/Harness, and Architecture are roadmap surfaces. Each study is intended to vary one declared component while keeping the surrounding service contract fixed.

| Surface | CUA-RSIBench status |
|---|---|
| Data | Real training and evaluation executed; research restricted to selection and one augmentation |
| Algorithm | No comparative algorithm-research experiment |
| Agent/Harness | Development code and runtime repairs; no completed comparable harness-research study |
| Architecture | No model, kernel, or inference-system research study |

An implementation of Tinker, E2B, and Harbor is the execution substrate. It does not by itself implement all four research surfaces.

## The central gap

The paper's data researcher can construct and validate new training experiences. Appendix B discusses executable states, trajectories, filtering, representation, curricula, and search. Our current researcher only chooses records from one existing trajectory. The published report identifies this restriction; it must not be relabeled as open-ended synthesis.

## Required changes for the next computer-use study

1. **A writable, isolated data-research workspace.** Let the researcher implement a reusable data factory, inspect permitted source material, and revise generation code. Evaluation tasks, answers, grader code, credentials, and budget state must remain outside that workspace. JSON flags alone are not isolation.
2. **New executable training tasks and states.** Generate fresh app fixtures from allowlisted, provenance-tracked training sources. Construct workflow constraints explicitly. Do not convert selection or final-test records into supervision. Keep a registry of protected source IDs and refresh final tasks between studies.
3. **Real rollout and validation.** Execute generated tasks through the same GUI contract used at evaluation. Use one fixed external rollout model for both researchers. Retain failed attempts for diagnosis; admit positive demonstrations only after independent state verification. Recovery examples must actually execute the recovery.
4. **Behavior-aligned representations.** Support complete trajectories, selected decisions, verified endings, and repaired continuations. Preserve observations and tool pairing. Unify training and evaluation instruction headers. Label truncation, compression, and synthetic reference transformations.
5. **Researcher-controlled filtering and curriculum.** Permit auditable deduplication, mixtures, difficulty schedules, and training exposure within a frozen whitelist and budget. Require a concrete hypothesis for each revision; do not prescribe every internal data-factory stage.
6. **A discriminative evaluation distribution.** Calibrate multiple instances and difficulty tiers with both the student and frontier actors. A task solvable by Sol can still produce a floor for the 4B student. Keep protocol smoke tasks distinct from research targets; never create difficulty through broken infrastructure or impossible budgets.
7. **Meaningful comparisons.** Record the unadapted base, first valid candidate, historical best, last attempted candidate, selected checkpoint, and final evaluation. Add repeated research seeds and an equal-budget non-recursive control before attributing gains to feedback-driven search.
8. **A reusable component contract.** Declare inputs, outputs, allowed configuration, artifacts, resource accounting, and scoring for the active surface. Enforce immutable evaluator and budget state in the service, and retain a replayable lineage of candidates.

## Interpretation constraints

The current pilot supports a real executable chain, native-app solvability, and a negative data-selection result. Its three journaled final executions are repeated stability checks of one base model, not three independent tasks. Source IDs are disjoint while the template is shared.

The reference paper also cautions that its original selection and official evaluations share task subsets. Its official reruns do not establish statistically held-out generalization. Our source separation addresses a different boundary and does not establish unseen-template or unseen-application transfer.

The next implementation must change the data-research interface and evaluation coverage before spending another five-round budget. The v0.4 report and original records remain frozen; subsequent studies receive new versions and fresh final-test partitions.
