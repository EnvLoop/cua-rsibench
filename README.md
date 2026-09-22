# CUA-RSIBench — work in progress

An experimental computer-use benchmark inspired by RSIBench-Data. **The full benchmark is not implemented or validated yet.** No recursive improvement or leaderboard result is claimed.

## Current evidence

- Legacy deterministic document fixtures and integrity regression tests.
- A real Chrome runner for a synthetic expense-review application, with model-driven DOM actions, clean browser contexts, screenshot traces, reload-before-verification and exact final-state checks.
- AgentRouterHub Responses API support for `gpt-6-astra` and `gpt-5.6-sol`.
- Service-chain mocks for development only. Mock scores are null and cannot qualify for final submission.

## Run

Install the package and browser extra in a virtual environment:

```sh
pip install -e '.[browser]'
python -m unittest discover -s tests -v
python -m cursibench.browser_trial --out work/browser-run --model gpt-5.6-sol
```

The browser runner requires installed Google Chrome. Set `OPENAI_API_KEY` and `OPENAI_BASE_URL` outside the repository. Never commit keys or raw provider responses containing private configuration.

Browser actions currently use visible DOM selectors. This is a synthetic browser-use integration check, not pixel-only computer use, real enterprise-app evaluation, a held-out benchmark, or an RSI experiment.

## Remaining requirements

1. Real application task families and source-artifact/template-disjoint splits.
2. Enforced wall-time, token and monetary budgets plus complete provider accounting.
3. Model-generated, inherited harness proposals and independent acceptance evaluation.
4. Verifier/test assets isolated from editable agent code, with host-side result integrity.
5. Matched frozen/nonrecursive controls, independent seeds, confidence intervals and ablations.
6. Actual Tinker training/checkpoints, E2B lifecycle and Harbor evaluation integration.
7. A technical report and visualizations tied to auditable run artifacts.

The legacy `python -m cursibench` command is only a deterministic regression fixture. Its five iterations reuse a hand-written candidate; its score is not evidence of learning. Test assets in this repository are public and not sealed. Configuration fields do not constitute runtime enforcement. Documentation under `docs/` describes the target design, not an implemented production system.

## Browser smoke evidence

On 2026-09-23 both Astra and Sol completed one synthetic expense task through real Chrome. Persisted state was checked after reload; unrelated records were unchanged. See [traces and screenshots](docs/evidence/browser-smoke/). These are single integration trials, not comparable performance measurements or RSI results.
