# RSIBench-Data-shaped computer-use format

The evaluated executable-factory study adapts the Data research surface of [RSIBench-Data](https://arxiv.org/abs/2607.25886). A researcher writes a data-generation policy while the student, teacher, optimizer settings, GUI action space, task packages, and independent verifier remain controlled. Operational controller amendments are separately recorded. This does not implement the reference project's Algorithm, Harness, or Architecture roadmap surfaces, or demonstrate sustained model-level RSI.

## Executed service chain

```text
researcher-authored Python factory in an isolated E2B workspace
  -> generated native task states and independently verified teacher trajectories
  -> provenance-checked SFT messages JSONL
  -> real Tinker LoRA SFT and sampler checkpoint
  -> authenticated E2B checkpoint proxy
  -> Harbor native browser evaluation with a separate verifier
  -> scored or explicitly unscored attempt, retained selection, sealed final tests
```

The live implementation uses `factory_research` for bounded research, `factory_preflight` and `factory_corpus` for submission checks, `tinker_backend` for actual training/sampling, and `tools/run_cloud_chain.py` for the E2B/Harbor chain. `factory_campaign` records budget reservations, attempts, promotion, and frozen selection. `tools/audit_factory_study.py` reconstructs evidence independently before export.

The researcher can vary task recipes, filtering, representation, ordering, repetition, and mixtures of permitted verified examples. It cannot change the fixed training recipe or fabricate successful trajectories. Each valid candidate starts a fresh adapter from the same base student. The exact researcher model, fixed teacher, and evaluated student are different roles.

## Computer-use task mapping

Each Harbor task contains a resettable native application state, visible source facts, and a user instruction. Hidden targets and the verifier remain outside the actor environment. The trusted compiler derives expected targets. The separate verifier reads the saved application database, checks those targets, and verifies preservation of unrelated state. It does not independently solve the planning objective again. Screenshots are retained as audit artifacts and do not determine the task reward.

The current profile is Kanboard 1.2.54 with DOM-assisted browser interaction. Source IDs are separated across training, selection, and final pools, while application and task templates remain shared. Six final variants are repeated twice in fresh environments at the same sampling seed. Shared checkpoint roles reuse explicitly identified results, without adding independent observations.

More applications, template-level holdouts, independent research seeds, and equal-budget non-adaptive controls remain research extensions. Original Office and full desktop operation require separate profiles and evidence.

## Operational provenance

The remote controller is a versioned orchestration change. It preserves frozen task/checkpoint/source bindings, records the Mac-to-Linux difference, verifies archives and every member, and refuses blind redispatch after uncertain creation or execution. The original cohort's whole-suite recoveries retain all originals and are reported separately from initial final executions. See [remote evaluation](REMOTE_EVALUATION.md).

Missing results are incomplete; infrastructure-invalid results are unscored. Neither is a zero model score. Exact provider model IDs are recorded metadata, not independent weight attestations. Provider dollar totals are unknown.

## Legacy local fixtures

`cursibench.service_pipeline.run_service_chain` remains a deterministic local fixture with fake providers for development and regression checks. It is not the live training/evaluation implementation and its scores are not research evidence. Earlier `BenchmarkSpec` and `Ledger` fields describe proposed controls; metadata alone does not enforce isolation, run cloud services, or establish RSI. The historical v0.4 pilot is also a separate experiment and is not pooled with the executable-factory cohorts.
