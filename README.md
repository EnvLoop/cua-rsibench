# CUA-RSIBench

**EnvLoop's controlled pilot of data-centric research for verifiable computer use.**

A real Kanboard application, public-source issue metadata, actual Tinker LoRA training, an E2B sampling proxy, Harbor task execution, and an independent saved-state verifier. Inspired by [RSIBench-Data](https://github.com/evolvent-ai/RSIBench-Data).

- [English technical report](docs/site/CUA-RSIBench-Technical-Report.pdf)
- [Interactive evidence explorer](https://envloop.github.io/cua-rsibench/site/)
- [Report, figures and offline bundle](https://github.com/EnvLoop/cua-rsibench/releases/tag/v0.5.0-executable-factories)
- [Original-cohort audit](docs/site/factory-study.json) and [Sol 6 / Luna 6 audit](docs/site/model6-study.json)

## v0.6 real-software qualification note

The [English qualification PDF](docs/qualification-v06/EnvLoop-Computer-Use-Qualification-Report.pdf), [interactive six-application explorer](https://envloop.github.io/cua-rsibench/qualification-v06/), and [source-hashed evidence data](docs/evidence/v0.6-qualification-report-data.json) document the next benchmark's environment and verifier work. This is a **separate methods release**, not a new full-scale score: the planned Qwen3.8-27B study has zero completed researcher campaigns, zero official final task instances, and no application with 100 admitted tasks. Human GUI controls, one-task model pilots, published source inventories, and provisional splits are labeled separately. The v0.5 Qwen3.5-4B Kanboard results below remain unchanged.

The [v0.6.1 English addendum](docs/qualification-v061/EnvLoop-Real-Software-Qualification-Addendum.pdf) and [vector control diagram](docs/qualification-v061/figures/control-transitions.svg) report three additional saved-state development controls in real Excel web, PowerPoint web, and Magento admin. Their task-specific scores are not pooled or promoted into the planned 24-campaign study. The [Magento 100-candidate backlog](docs/evidence/magento-100-candidate-admission-2026-09-24.md) is an audited preparation queue with zero officially admitted final identities.

For the intended publication-scale study, the [English pre-result protocol](docs/FULL_STUDY_PREREGISTRATION.md) fixes the comparisons, leakage boundary, budgets, failure handling, and family-level analysis. The [offline full-matrix gate](docs/FULL_STUDY_MATRIX.md) revalidates all 30 base/selected slot manifests and refuses to dispatch unless six original-software cells each have 100 individually qualified final tasks. Current [Office](docs/evidence/office-web-100-provisional-screen-2026-09-25.md), [SaaS](docs/evidence/saas-100-candidate-admission-2026-09-25.md), and [native desktop](docs/evidence/osworld-native-office-admission-2026-09-25.md) 20/100 inventories are **provisional only**. The [dated enterprise-cell amendment](docs/FULL_STUDY_ENTERPRISE_AMENDMENT_2026-09-25.md) selects original Odoo Community as a provisional sixth cell; [ServiceNow WorkArena access](docs/evidence/servicenow-workarena-pdi-gate-2026-09-25.md) remains a separately gated supplemental track. Neither has 100 admitted final tasks, and no 4 x 6 result paper is claimed.

A separate [Qwen3.8-27B base-model Magento price-task pilot](docs/evidence/magento-price777-qwen-base-pilot-2026-09-24.md) records one runner failure and one 40-sample budget-censored retry. Neither completed a product save or entered an official final-task denominator; both attempts' monitored SQL and search state were restored. This protocol-development evidence is not a checkpoint or training-gain result.

The later [v3 scored development diagnostic](docs/evidence/magento-price777-qwen-scored-v3-2026-09-25.md) completed one valid model-driven GUI attempt on the same public task. Qwen saved one of five target prices, then chose `finish`; the unchanged evaluator and independent saved-state check scored the full task **0.0**. Two intervening v2 attempts remain unscored infrastructure/protocol failures. Monitored SQL and all 181 search documents were restored after every attempt. This public task adds no hidden final identity or researcher campaign.

## Executable data-research studies

Researchers write Python data factories in isolated E2B workspaces, generate native task states, request verified GUI demonstrations, and revise their training mixtures from selection feedback. Each accepted dataset trains a fresh Qwen3.5-4B LoRA adapter. The fixed teacher is **gpt-5.6-sol**; the researcher model and the evaluated student are different roles.

| Cohort | Researcher | Research rounds | Trained candidates | Scheduled training tokens | Retained selection |
|---|---|---:|---:|---:|---|
| Original | gpt-6-astra | 5 | 3 | 371,887 | Round 1, 1/3 |
| Original | gpt-5.6-sol | 5 | 4 | 460,768 | Round 5, 1/3 |
| Separate extension | gpt-6-sol | 5 | 5 | 664,132 | Round 2, 1/3 |
| Separate extension | gpt-6-luna | 5 | 1 | 140,167 | Base, 0/3 |

All four searches, prescribed final evaluations, and declared operational recoveries are complete. In the Sol 6 / Luna 6 extension, the student selected by Sol 6 scores **2/12 (16.7%)** across two six-task repetitions; the base scores **0/12**. Luna 6 retains that same base checkpoint and shares its execution evidence. All 24 extension final trials are valid, without infrastructure errors. These are separate cohorts, not a matched four-model ranking: final source records and researcher-facing interface timing differ. Original Sol5.6 results are never relabeled Sol6. The extension explicitly reuses the selection baseline and starts fresh researcher lineages.

The [historical v0.4 release](https://github.com/EnvLoop/cua-rsibench/releases/tag/v0.4.0-research-pilot) used selection/augmentation from one teacher trace. Its published artifacts remain unchanged and are not pooled with executable-factory results. See [the factory contract](docs/DATA_FACTORY.md) and [alignment with RSIBench-Data](docs/RSIBENCH_ALIGNMENT.md).

The original cohort retains its infrastructure-invalid original comparisons. In its separate recovery view, base scores 0/12 and the Sol 5.6-selected student scores 2/12; valid Astra originals score 3/12. Astra originals use the Mac controller and replays use Linux, so that view is not a platform-matched estimate of training-data effects.

No sustained RSI, broad desktop generalization, or mature leaderboard is claimed. Rejected submissions receive no training score. Infrastructure failures remain unscored, and declared recoveries retain the original evidence.

## Install and validate

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e '.[browser,cloud,harbor,report]'
source .venv/bin/activate
PYTHONPATH=src python -m unittest discover -s tests -v
```

Configure `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `TINKER_API_KEY`, and `E2B_API_KEY` outside the repository. AgentRouterHub uses the Responses API with the requested researcher identifiers. No keys belong in the source or report.

## Run an executable-factory study

Build the native application and proxy templates using the configured E2B account:

```sh
python tools/build_kanboard_template.py
python tools/build_proxy_template.py
```

The fresh-study launcher implements the original gpt-6-astra / gpt-5.6-sol researcher protocol. Preparation exports and seals the task packages without model calls; full execution consumes the configured provider accounts.

```sh
PYTHONPATH=src python tools/run_factory_study.py \
  --out work/new-study-preview --prepare-only
PYTHONPATH=src python tools/run_factory_study.py --out work/new-study
```

For a separate Sol 6 / Luna 6 cohort, prepare new factory lineages from the verified original study. This explicitly reuses its selection baseline and creates disjoint final instances; it does not relabel or inherit its researcher programs.

```sh
PYTHONPATH=src python tools/prepare_model6_extension.py \
  --original work/new-study --out work/new-model6-study
```

Use `tools/run_factory_round.py` for the bounded rounds, then `tools/prepare_factory_comparison.py` to freeze both selections after the declared stop. The [factory guide](docs/DATA_FACTORY.md) describes generation, training, feedback and budget enforcement. The [remote evaluation guide](docs/REMOTE_EVALUATION.md) covers the trusted Linux controller, exact prepared payloads, collection, and reviewed final admission. Local and remote controller paths are separately versioned and must not be silently mixed.

The local preparation path and individual cloud components have been validated. The convenience launcher has not been rerun as an additional full paid study. Exact replication also depends on current provider availability and the declared software versions. Historical single-trajectory `data_campaign` examples and their report builders belong to the [v0.4 release](https://github.com/EnvLoop/cua-rsibench/tree/v0.4.0-research-pilot).

## Scope and evidence boundaries

The environment is unmodified Kanboard 1.2.54. Thirty-seven issue metadata records have source URLs, timestamps, and a content hash. Twelve source IDs each are assigned to training, selection, and final-test packs. Policies, staff, planning inputs, and archive distractors are explicitly constructed. Source IDs are disjoint; the workflow template is shared.

This is DOM-assisted browser use, not pixel-only grounding, full Windows/macOS operation, or original Microsoft Office evaluation. Screenshots are audit artifacts; actual saved database state determines task success. Infrastructure interruptions and model task failures are different outcomes.

The earlier deterministic workbench remains a regression fixture. Its historical `+0.1429` delta is not an RSI result. See [reference alignment and remaining work](docs/RSIBENCH_ALIGNMENT.md), [realism](docs/REALISM.md), [cloud evidence](docs/CLOUD_VALIDATION.md), and the [completion plan](docs/plans/2026-09-23-completion.md).

## Rebuild the English report and explorer

The release contains separate sanitized cohort inputs, program snapshots, and the native application screenshot. These suffice for offline report/figure rebuilding without private checkpoints or provider credentials:

```sh
mkdir -p outputs
cp docs/site/factory-study.json docs/site/model6-study.json \
   docs/site/kanboard-real-ui.png outputs/
cp -R docs/site/factory-programs outputs/
python tools/build_factory_figures.py
python tools/build_factory_report.py
python tools/build_factory_visualization.py
python tools/package_factory_release.py
```

Figures are exported as PNG, SVG, and PDF; the manuscript is also emitted as Markdown. The builders check completion, model identities, cohort separation, dataset composition, and original/recovery boundaries. Regenerating an independent study audit requires its raw local execution artifacts; rebuilding from released evidence does not.
