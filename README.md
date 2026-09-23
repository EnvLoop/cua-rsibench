# CUA-RSIBench

**EnvLoop's controlled pilot of data-centric research for verifiable computer use.**

A real Kanboard application, public-source issue metadata, actual Tinker LoRA training, an E2B sampling proxy, Harbor task execution, and an independent saved-state verifier. Inspired by [RSIBench-Data](https://github.com/evolvent-ai/RSIBench-Data).

- [English technical report](docs/site/CUA-RSIBench-Technical-Report.pdf)
- [Interactive evidence explorer](https://envloop.github.io/cua-rsibench/site/)
- [Report, figures and offline bundle](https://github.com/EnvLoop/cua-rsibench/releases/tag/v0.4.0-research-pilot)
- [Campaign audit](docs/site/data-campaigns.json) and [recovery evidence](docs/site/journal-recovery.json)

## Executable data-research studies

Researchers write Python data factories in isolated E2B workspaces, generate native task states, request verified GUI demonstrations, and revise their training mixtures from selection feedback. Each accepted dataset trains a fresh Qwen3.5-4B LoRA adapter. The fixed teacher is **gpt-5.6-sol**; the researcher model and the evaluated student are different roles.

| Cohort | Researcher | Research rounds | Trained candidates | Scheduled training tokens | Retained selection |
|---|---|---:|---:|---:|---|
| Original | gpt-6-astra | 5 | 3 | 371,887 | Round 1, 1/3 |
| Original | gpt-5.6-sol | 5 | 4 | 460,768 | Round 5, 1/3 |
| Separate extension | gpt-6-sol | 5 | 5 | 664,132 | Round 2, 1/3 |
| Separate extension | gpt-6-luna | 5 | 1 | 140,167 | Base, 0/3 |

Selections are frozen after the declared search limit. Final tests and operational recoveries are being completed before the new report is released. These are separate cohorts, not a matched four-model ranking: final source records and researcher-facing interface timing differ. Original Sol5.6 results are never relabeled Sol6. The extension explicitly reuses the selection baseline and starts fresh researcher lineages.

The [historical v0.4 release](https://github.com/EnvLoop/cua-rsibench/releases/tag/v0.4.0-research-pilot) used selection/augmentation from one teacher trace. Its published artifacts remain unchanged and are not pooled with executable-factory results. See [the factory contract](docs/DATA_FACTORY.md) and [alignment with RSIBench-Data](docs/RSIBENCH_ALIGNMENT.md).

No sustained RSI, broad desktop generalization, or mature leaderboard is claimed. Rejected submissions receive no training score. Infrastructure failures remain unscored, and declared recoveries retain the original evidence.

## Install and validate

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e '.[browser,cloud,harbor,report]'
source .venv/bin/activate
PYTHONPATH=src python -m unittest discover -s tests -v
```

Configure `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `TINKER_API_KEY`, and `E2B_API_KEY` outside the repository. AgentRouterHub uses the Responses API with the requested researcher identifiers. No keys belong in the source or report.

## Run on your provider accounts

Build the application and proxy templates from pinned public dependencies:

```sh
python tools/build_kanboard_template.py
python tools/build_proxy_template.py
```

Collect a verified training trajectory, then launch an explicit data campaign:

```sh
python -m cursibench.kanboard_runner --kind public --seed 51 \
  --model gpt-5.6-sol --out work/teacher
python -m cursibench.data_campaign --teacher work/teacher/result.json \
  --researcher gpt-6-astra --out work/research-astra
```

The teacher must pass saved-state verification before it can supply training data. Baseline sampling no longer depends on a training manifest from the author's private workspace. Cloud runs use the configured provider accounts and record unknown prices as unknown.

The original experiment is frozen at commit `62b99b9`. To use the repaired observer explicitly:

```sh
python -m cursibench.kanboard_harbor_export_v3 --kind basic --out work/native-v3
harbor run -p work/native-v3 \
  -a cursibench.kanboard_harbor_v3:ResilientKanboardAgent \
  -m gpt-5.6-sol --env cursibench.journal_env:JournalE2B -n 1
```

To sample the base student through the complete service chain, with no prior training artifact:

```sh
python tools/run_cloud_chain.py --out work/base-check --native --base \
  --model Qwen/Qwen3.5-4B --task work/native-v3 --environment journal
```

Journaled transport reuses the result of the same logical command after response loss. It refuses to replay an incomplete intent whose effects are uncertain. The model retains its GUI-only action space.

## Scope and evidence boundaries

The environment is unmodified Kanboard 1.2.54. Thirty-seven issue metadata records have source URLs, timestamps, and a content hash. Twelve source IDs each are assigned to training, selection, and final-test packs. Policies, staff, planning inputs, and archive distractors are explicitly constructed. Source IDs are disjoint; the workflow template is shared.

This is DOM-assisted browser use, not pixel-only grounding, full Windows/macOS operation, or original Microsoft Office evaluation. Screenshots are audit artifacts; actual saved database state determines task success. Infrastructure interruptions and model task failures are different outcomes.

The earlier deterministic workbench remains a regression fixture. Its historical `+0.1429` delta is not an RSI result. See [reference alignment and remaining work](docs/RSIBENCH_ALIGNMENT.md), [realism](docs/REALISM.md), [cloud evidence](docs/CLOUD_VALIDATION.md), and the [completion plan](docs/plans/2026-09-23-completion.md).

## Build the English report

The released `docs/site/` directory contains the sanitized inputs and application screenshot. Copy them to `outputs/`, then run:

```sh
mkdir -p outputs
cp docs/site/evidence.json docs/site/data-campaigns.json \
   docs/site/journal-recovery.json docs/site/kanboard-real-ui.png outputs/
python tools/build_figures.py
python tools/build_report.py
python tools/build_visualization.py
```

Figures are exported as PNG, SVG, and PDF. The manuscript is also emitted as Markdown. Generating a fresh campaign audit requires the original local execution artifacts; rebuilding the report from the released evidence does not.
