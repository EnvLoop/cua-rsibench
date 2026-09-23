# Alignment with RSIBench-Data

Reviewed against the [research surfaces](https://rsibench.co/#surfaces), the [Data release](https://rsibench.co/data/), and [paper Sections 3-6 and Appendix B](https://arxiv.org/html/2607.25886v1).

The website's released surface is Data. Algorithm, Agent/Harness, and Architecture are roadmap surfaces. An integration of Tinker, E2B, and Harbor does not itself instantiate all four.

## What the paper evaluates

The researcher constructs a reusable training-data policy under fixed training, serving, evaluation, and budget boundaries. Executable states, verified trajectories, filtering, representation, curricula, mixtures, feedback-driven revision, and checkpoint preservation are part of its available research space. Appendix B gives representative actions rather than a mandatory internal stage sequence.

The main experiment improves a separate target model. It must not be described as demonstrated sustained model-level RSI. The paper also explicitly states that selection and official evaluation reuse task subsets: fresh task environments alone do not establish statistically held-out generalization.

## Implementation mapping

| Protocol element | CUA-RSIBench implementation | Evidence boundary |
|---|---|---|
| Executable data policy | Researcher-authored Python in an isolated E2B workspace | Restricted native Kanboard profile, not arbitrary desktop tasks |
| New training experience | Generated direct, ranked, and allocation task states | Source facts are authentic; workflow rules and planning inputs are synthetic |
| Fixed rollout service | Same Sol teacher for both researchers, using native GUI actions | Teacher success does not establish student improvement |
| Data validation | Controller reconstructs exact examples from independently verified traces | Failed traces support diagnosis; invented successful traces are rejected |
| Representation and mixture | Decision or full-history records, filtering, ordering, repetition and inherited mixtures | No arbitrary rewriting of observed states |
| Fixed learning stack | Fresh Qwen3.5-4B LoRA adapter per valid candidate, same 32-step recipe | Smaller student and budget than the reference experiment |
| Fixed evaluation | Harbor/E2B native task execution and separate saved-state verification | DOM-assisted browser use; no pixel-only or full desktop claim |
| Feedback-driven search | Prior factory and controlled selection diagnostics available each round | One research seed per researcher; no causal attribution to feedback |
| Checkpoint preservation | Strict improvement with no per-task regression; ties retain the incumbent | A controller rule, narrower than unrestricted researcher checkpoint choice |
| Final evaluation | Source-disjoint sealed instances, frozen checkpoint, exact runtime/task binding | Shared templates/application; same-seed repetitions test execution stability |

The v0.4 published experiment selected and augmented records from one teacher trace. It remains a separate historical release. The executable-factory study uses a new versioned protocol, datasets, and final instances; its results must not be pooled with v0.4.

## Remaining research limitations

A broader benchmark needs more applications and task instances, predeclared difficulty tiers, repeated research seeds, and an equal-budget non-adaptive search control before stronger claims about researcher rankings or the benefit of feedback. Original Microsoft Office, pixel grounding, Windows, and macOS need separate execution profiles and evidence. None is implied by Kanboard results.

Source-ID separation prevents the benchmark controller from reusing protected source records for training. It does not rule out public-data pretraining exposure or establish unseen-template transfer. Unknown dollar costs remain unknown.

## Operational repairs are visible

The study retains the initial multi-task proxy-cache failure and its clean paired reruns. Submission preflight returns exact token violations without rewriting agent datasets. Round five explicitly exposes the remaining logical turns after earlier runs reached their cap without submitting. These interface repairs are recorded; they do not retroactively convert failed or absent candidates into valid scores.
