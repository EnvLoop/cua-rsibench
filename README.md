# CUA-RSIBench

A computer-use benchmark under active development, inspired by [RSIBench-Data](https://github.com/evolvent-ai/RSIBench-Data). The primary environment is **real Kanboard 1.2.54**, deployed in disposable E2B sandboxes. Tasks use public issue metadata with explicit provenance; policies and staff assignments are marked synthetic.

## Evidence, not a simulated score

- **Real Tinker**: LoRA update, persistent checkpoint and checkpoint sampling verified on Qwen/Qwen3.5-4B.
- **Real E2B + Harbor**: browser oracle and a separate verifier executed successfully.
- **Full service chain**: Tinker checkpoint → E2B sampling proxy → Harbor E2B browser task → separate verifier. One completed trial, no infrastructure errors, reward **0**. This negative result proves execution, not capability improvement.
- **Real Kanboard GUI**: AgentRouterHub Sol completed a native form edit; independent SQLite readback confirmed intended changes and preserved other tasks.
- **Real-source data**: 37 public issue metadata records; source URLs, timestamps and content hash retained. No authors or issue bodies copied.
- **Difficulty calibration in progress**: original handwritten tasks saturated and were excluded from formal RSI claims. Astra/Sol are being evaluated on native workflows with distributed information and real metadata.

No sustained recursive improvement, unseen-application transfer or mature leaderboard is claimed. The old deterministic fixture remains a unit regression check only. Mock providers return no score and cannot qualify for final submission.

## Reproduce

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e '.[browser,cloud,harbor]'
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

Configure `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `TINKER_API_KEY`, and `E2B_API_KEY` outside the repository. Never commit credentials. AgentRouterHub uses the Responses API with `gpt-6-astra` and `gpt-5.6-sol`; fees remain unknown unless account prices are supplied.

Local browser fixtures require installed Google Chrome. The real-app path uses the E2B Kanboard template. See [realism](docs/REALISM.md), [cloud validation](docs/CLOUD_VALIDATION.md), and the [completion plan](docs/plans/2026-09-23-completion.md).

```sh
python -m cursibench.kanboard_runner --kind public --model gpt-5.6-sol --out work/native-trial
python -m cursibench.kanboard_harbor_export --kind public --out work/harbor-native
harbor run -p work/harbor-native -a cursibench.kanboard_harbor:KanboardAgent \
  -m gpt-5.6-sol --env cursibench.cloud_env:BoundedE2B -n 1
```

The E2B template builder currently requires the pinned source archive and the recorded browser base template; cloud setup is account-specific and is not yet a one-command public installation. Exported Harbor tasks have Dockerfiles for independent rebuilds.

## Boundaries

The actor receives native visible DOM text and controls and can click, fill, select, press limited keys, go back or finish. It cannot access shell, SQL, application APIs or host files. Screenshots are recorded for audit; this is **DOM-assisted browser use**, not pixel-only computer use or a full Windows/macOS benchmark.

Task success is based on actual saved database state. Infrastructure errors, invalid model actions and task failures are different outcomes. The evaluator normalizes only known semantically equivalent application fields; source records, comments and unrelated objects are preserved.

The implementation contains separate harness-adaptation and data-training paths. Metadata flags are not treated as isolation or promotion enforcement. Formal experiments require discriminative tasks, source-disjoint splits, matched controls, repeated final evaluation, and complete evidence.

## Publication

- [Interactive evidence explorer](https://nanobanana123.github.io/cua-rsibench/site/)
- [Pilot technical report and offline bundle](https://github.com/nanobanana123/cua-rsibench/releases/tag/v0.3.0-pilot)
- [PDF in this repository](docs/site/CUA-RSIBench-Technical-Report.pdf)

The 9-page report was rendered, visually inspected, published, fetched back and checked byte-for-byte. The live visualization's filters and PDF link were tested. It reports real data provenance, real cloud execution, native GUI calibration results, infrastructure exclusions and limitations. The historical toy `+0.1429` fixture delta is not an RSI result. Multi-round data-research campaigns are still running; the goal is not yet marked complete.
