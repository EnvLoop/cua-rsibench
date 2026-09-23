# CUA-RSIBench: Executable Data Research for Verifiable Computer Use

[Code, evidence, and released artifacts: github.com/EnvLoop/cua-rsibench](https://github.com/EnvLoop/cua-rsibench)

## Abstract

Can a researcher agent turn evidence of browser-agent failures into better training data? We study this question in a bounded, real-application setting. Two researchers, gpt-6-astra and gpt-5.6-sol, write and execute Python data factories, construct native Kanboard task states from public issue metadata, request independently verified GUI demonstrations from a fixed teacher, and revise their datasets using student evaluation feedback. Each valid dataset trains a fresh Qwen3.5-4B LoRA adapter through Tinker. Harbor evaluates the student in E2B environments with a separate saved-state verifier. Across {{ROUND_COUNT}} completed research rounds, {{TRAINED_COUNT}} candidates complete training and consume {{TOTAL_TOKENS}} scheduled training tokens. {{SELECTION_SENTENCE}} Final evaluation covers six source-disjoint task instances with two same-seed environment repetitions. {{FINAL_SENTENCE}} We release the implementation, evidence audit, English report, and visualizations while distinguishing failed submissions and infrastructure errors from scored model failures. This is a small data-research pilot, not evidence of sustained recursive self-improvement or broad computer-use generalization.

## 1. Research question

A computer-use agent can issue valid clicks while repeatedly reopening the wrong task, leave changes unsaved, miss a planning constraint, or stop after editing only one required record. Useful training experience must therefore teach state-dependent behavior that survives interaction with real software. A successful data-generation program or a completed training job alone does not establish that improvement.

The benchmark separates three roles. A frontier researcher changes the training-data policy; a fixed teacher produces GUI experience for permitted training tasks; a separate student is trained and evaluated. Astra and Sol are researcher identifiers, not the identities of the trained browser agents. Their direct frontier-actor calibration in the earlier release is a separate experiment.

Our contribution is an executable data-research boundary around a native application, including source permissions, bounded code execution, verified trajectory provenance, fixed training and evaluation, checkpoint preservation, and traceable experiment records. The empirical outcome is reported without requiring it to be positive.

---PAGEBREAK---

## 2. Protocol and reference alignment

RSIBench-Data isolates training-data research while fixing the surrounding post-training services [1]. Its Appendix B describes a flexible action space including executable task states, trajectories, validation, filtering, representations, mixtures, and feedback-driven revisions. We implement a constrained computer-use instance of this idea. Our prior v0.4 release selected demonstrations from one trajectory; the present study adds researcher-authored executable factories and newly verified native episodes.

![Figure 1. Executable data research under a fixed service boundary. The researcher controls its generator and data mixture. The controller owns permissions, training, execution, and scoring. Only permitted selection feedback returns to the researcher.](figures/factory-pipeline.png)

For researcher r and round t, a policy produces dataset D(r,t) from permitted training sources and previous selection feedback. Every valid candidate starts from the same base student: M(r,t) = Train(M0, D(r,t); c). The preceding adapter is not continued. The fixed configuration c, actor interface, evaluator, and task set are held constant; data generation and organization vary.

The researcher writes and runs Python, constructs task recipes, requests teacher rollouts, reads permitted results, and submits messages JSONL. It can preserve earlier verified examples, change source order and workflow constraints, select decision-only or full-history records, deduplicate, repeat, order, and mix them. Positive examples must match controller-reconstructed, independently verified traces. The current interface does not admit arbitrary invented observations, unexecuted repair demonstrations, or new optimizer implementations.

Selection uses three fixed task instances. A candidate must strictly improve the mean and regress on none of the incumbent's task outcomes to be promoted. Equal scores retain the earlier candidate, including the base. This controller-enforced rule is an explicit restriction relative to free researcher checkpoint choice. Both searches close before any final execution starts; final results never become further training feedback.

---PAGEBREAK---

## 3. Application, source data, and tasks

The execution environment runs Kanboard 1.2.54 with its original PHP controllers, forms, projects, comments, and SQLite persistence [2]. Each episode receives a fresh application instance and task state. Setup API operations initialize the fixture before the actor begins and receive no agent credit. The tested profile is DOM-assisted browser use; screenshots are audit artifacts rather than model inputs.

![Figure 2. Native Kanboard interface recorded in E2B. The benchmark uses the original application and persistent database; project content and workflow constraints are constructed fixtures.](kanboard-real-ui.png)

The source snapshot contains 37 authentic public issue metadata records with source URLs, issue numbers, capped titles, states, timestamps, labels, and comment counts. Twelve IDs each are assigned to training, selection, and final sources; one is unused. The three source pools do not overlap. Issue bodies, authors, and email addresses are excluded. Staff, planning values, costs, capacities, dependencies, archive distractors, and project names are explicitly synthetic.

| Task family | Required behavior | Common valid failure |
| Direct updates | Find specified source records; set assignee, priority, and complexity; save | Edit another record or choose the wrong value |
| Conditional ranking | Apply source-fact predicates, sort with a tie-break, then update every selected task | Stop after one target or confuse source status with local status |
| Constrained allocation | Maximize value under cost, time, dependency and exclusion rules; minimize cost on ties | Choose a feasible but suboptimal set |

**Table 1.** The three task families. Final instances vary insertion order, target attributes, ranking direction, and planning alternatives. These combined variations probe robustness but do not isolate any single shortcut causally.

---PAGEBREAK---

## 4. Verification and isolation

The trusted controller derives expected targets from validated task recipes and source facts. It exports actor-visible application state without hidden targets. After execution, a separate Harbor verifier compares the initial and final database snapshots against the allowed changes. Strict success requires every intended update and preservation of unrelated records and business tables. A completion message or plausible screenshot cannot replace saved-state verification.

Narrow normalization handles application-maintained timestamps, null versus zero time fields, and native newline conversion. Missing records, wrong targets, altered comments, unauthorized edits, and extra changes fail. The tests include these negative cases. Partial target completion and valid action syntax remain diagnostics; they cannot promote a candidate.

The research workspace is a separate E2B sandbox. A root-owned supervisor executes generated programs as a dedicated non-root user in an empty network namespace, with no-new-privileges and process, CPU, memory, file-size, and time bounds. Training inputs are read-only; service journals are inaccessible. Provider credentials, host project files, final tasks, and verifier answers are not mounted into this workspace. A live probe verified the non-root identity, absent provider credentials and host canary, blocked outbound networking, protected inputs and service results, and sandbox cleanup.

The teacher and student receive visible page text, control references, working memory, and the previous action outcome. Their actions are click, fill, select, limited keypress, back, and finish. They have no shell, SQL, application API, file editor, or arbitrary navigation tool. The same versioned prompt constructor is used for training demonstrations and student evaluation.

Provenance checks reconstruct each admitted record from the executed trace and independently recheck the saved state. Exact token preflight prevents oversized contexts, targets longer than the student's output budget, and schedules that omit submitted rows. Rejected submissions remain unscored. Training reservations precede new execution; uncertain paid failures remain charged conservatively. Rounds 1 and 2 were imported historically because their execution preceded the reservation guard, a distinction preserved in the audit.

---PAGEBREAK---

## 5. Experimental setup

Both researchers use AgentRouterHub's Responses interface under the same controller. Model names are requested provider identifiers, not independent attestations of the hosted weights. The fixed rollout teacher is gpt-5.6-sol. The student is Qwen/Qwen3.5-4B. Tinker performs actual LoRA updates and checkpoint sampling; an authenticated E2B proxy serves the checkpoint; Harbor runs the task and separate verification environments [3-5].

| Component | Declared setting |
| Research budget | 5 rounds and 1,048,576 scheduled training tokens per researcher |
| Per-round generation | 20 researcher turns; up to 40 charged calls with retries; 12 program runs; 3 new rollouts; 100 teacher calls |
| Training | 32 updates; batch 2; LoRA rank 8; learning rate 0.0001; seed 23 |
| Data exposure | At most 64 records for full coverage in 32 updates; 16,384 tokens per sequence; 262,144 scheduled tokens per candidate |
| Student sampling | Temperature 0; seed 23; at most 512 output tokens |
| Evaluation | 90 actions per task; 1,500-second agent timeout; 3 tasks per bounded execution chunk |
| Selection / final | 3 fixed selection instances; 6 source-disjoint final instances, each evaluated twice |
| Software | Kanboard 1.2.54; Harbor 0.23.0; Tinker 0.30.0; E2B 2.51.0 |

**Table 2.** Shared settings. Token counts include masked input tokens and do not estimate dollars. Wall-time limits apply to individual services and round control; the study does not claim the reference paper's monetary or whole-campaign wall-time budget.

The initial three-task launch exposed a serving defect: a 256-entry cache could not cover three 90-action trials. The controller derived a 270-entry capacity from task count and reran the paired baseline and initial candidates without changing their weights, data, task packages, observer, or verifier. Original infrastructure-invalid executions are preserved. All subsequent study comparisons use the repaired serving path.

Final packages were sealed before round 2 evaluation. The final runner verifies the selected training manifest, checkpoint identity, all task case hashes, canonical application and verifier files, runtime hashes, and timing after selection. Two repetitions use the same sampling seed in fresh environments. If two comparison roles select the identical checkpoint, they share explicitly identified execution evidence rather than being presented as independent samples.

---PAGEBREAK---

## 6. Selection trajectories and resource use

{{CAMPAIGN_TABLE}}

**Table 3.** Research outcomes. Rejected submissions and rounds without a submission are attempts at research but are not training jobs or zero-score evaluations. The selected candidate follows the declared no-regression rule.

![Figure 3. Candidate selection scores and the retained incumbent across the five research rounds. A cross in the unscored band denotes an invalid submission or absent candidate, not zero task success. Scores are over three fixed selection instances.](figures/factory-trajectories.png)

{{TRAJECTORY_ANALYSIS}}

Astra's first candidate solved the direct selection instance while its ranking and allocation executions stopped early. Its second candidate added verified multi-target lessons but lost the solved direct task. Sol's first two datasets did not improve on the base. The third Astra round exhausted its turn budget without submitting; the third Sol dataset was rejected because one full-history record exceeded the sequence limit by 101 tokens. Those artifacts were retained, and feedback was returned without editing either researcher's data by hand. Astra's fourth round also ended without submission. The researcher prompt exposed retry-call reservations but did not explicitly state the remaining logical turns; round five added this deadline for both systems. This interface repair is a study limitation, not retrospective evidence that the earlier data policies failed after training.

These records distinguish useful experience generation from student capability gains. Successful teacher episodes and longer datasets do not imply a better trained policy. The first positive selection result may also reflect shared layouts or workflow templates; final variations test a narrower form of robustness, not generalization across software.

---PAGEBREAK---

## 7. Final evaluation

{{FINAL_TABLE}}

**Table 4.** Six final tasks in each fresh-environment repetition. A complete mean exists only when every prescribed trial is valid. Shared base executions are identified explicitly; two repetitions do not create twelve independent task instances.

![Figure 4. Per-task final outcomes for the base and selected models. Cells show strict saved-state success. Infrastructure-invalid outcomes use a separate unscored representation.](figures/factory-final-matrix.png)

{{FINAL_ANALYSIS}}

Final evidence is not used to select a different checkpoint or generate another candidate. The study therefore preserves its chosen result even when a selected checkpoint fails on these instances. Selection success and final performance are separate outcomes.

---PAGEBREAK---

## 8. Interpretation and limitations

This study demonstrates an executable research loop with agent-authored Python, new native task states, verified GUI trajectories, real weight updates, fixed evaluation, and immutable selection. It does not establish sustained recursive self-improvement: a separate frontier researcher improves a fixed smaller student, and improved students do not become the next researchers.

The evaluation is small: one application, three shared task families, one research seed per system, three selection tasks, and six final tasks. Source IDs are disjoint, but templates, UI structure, and some workflow conventions are shared. Public metadata may already occur in pretraining data. No unseen-application, pixel-grounding, original Microsoft Office, Windows, or macOS capability is measured.

A larger final suite, repeated research seeds, and an equal-budget non-adaptive search control are required before attributing improvement to feedback-driven research or ranking the researchers. The current final repeats test environment stability at a fixed seed. They cannot support confidence intervals over a broad task distribution. The controller-enforced checkpoint rule also measures a narrower research interface than unrestricted strategy and stopping decisions.

Task difficulty should distinguish meaningful errors without placing every model at a floor. Direct frontier calibration from v0.4 establishes solvability for related native workflows, but does not prove student calibration on every new instance. Broader studies should predeclare multiple difficulty tiers and independent solvability evidence before freezing their evaluation sets.

## 9. Reproducibility and release boundary

The release includes the implementation, sanitized evidence JSON, report source, standalone PNG/SVG/PDF figures, and a portable explorer. The evidence audit reconstructs trusted corpora, matches training-data hashes and update counts, re-reads evaluator outcomes, checks resource accounting and promotion, and binds final executions to frozen plans. Raw credentials, private checkpoint identifiers, provider envelopes, and host paths are excluded.

The v0.4 selection-only pilot remains a separate historical release. Its scores and transport recoveries are not pooled with this executable-factory study. Unknown provider dollar costs are reported as unknown. The report describes observed behavior and preserves negative outcomes; successful infrastructure operation is not counted as successful agent work.

## References

[1] Meng et al. RSIBench-Data: Benchmarking Data-Centric Research for Recursive Self-Improvement. 2026. [Paper](https://arxiv.org/abs/2607.25886), [code](https://github.com/evolvent-ai/RSIBench-Data).

[2] Kanboard. [Original application and source](https://github.com/kanboard/kanboard).

[3] Thinking Machines Lab. [Tinker](https://github.com/thinking-machines-lab/tinker).

[4] E2B. [Sandbox infrastructure](https://github.com/e2b-dev/E2B).

[5] Harbor. [Evaluation framework](https://github.com/laude-institute/harbor).
