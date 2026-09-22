# CUA-RSIBench

CUA-RSIBench is a small, runnable benchmark for recursive improvement of computer-use agent harnesses.
It copies the important RSIBench boundary: model and evaluation stay fixed while an agent may improve
the harness that plans and executes UI actions. The repository deliberately uses a deterministic document
workspace so the benchmark can be self-tested without a paid GUI service. The same task contract can later
be backed by PowerPoint Online, WPS, a desktop VM, or BrowserGym.

## What is included

- resettable task fixtures with visible state and hidden expected state;
- an independent verifier that checks intended edits and unintended mutations;
- a baseline harness and a robust candidate harness;
- a five-round RSI loop with train-side acceptance and held-out test evaluation;
- an RSIBench-Data-shaped service chain: `data-generation agent -> JSONL -> Tinker -> E2B -> Harbor -> submission`,
  with deterministic local providers for CI;
- CLI commands and tests that verify the complete loop.

## Run

```bash
python -m unittest discover -s tests -v
python -m cursibench --rounds 5
python - <<'PY'
from cursibench.service_pipeline import run_service_chain
print(run_service_chain("artifacts/local-smoke", [{"messages": [{"role": "user", "content": "edit slide"}]}]))
PY
```

The CLI prints the initial score, each accepted/rejected candidate, the final hidden score, and `PASS`
only when the final candidate improves the hidden split without regression.

## Contract for a real GUI adapter

An adapter only needs to implement `reset(task_id)`, `observe()`, `act(action)`, and `snapshot()`.
The verifier must read the saved artifact independently of the agent process. GUI screenshots are evidence,
not the authority: the authority is the parsed application state plus explicit integrity checks.

For the Tinker/E2B/Harbor-shaped format and real-provider adapter boundary, see
[`docs/RSIBENCH_DATA_FORMAT.md`](docs/RSIBENCH_DATA_FORMAT.md). The local chain is intentionally marked
`provider_mode: local-fake`; it must never be reported as a paid external run.

The complete computer-use task/reset/verifier contract is in
[`docs/COMPUTER_USE_TASK_SPEC.md`](docs/COMPUTER_USE_TASK_SPEC.md), and the Astra/Sol provider choices and
observed preflight status are in [`docs/MODEL_SELECTION.md`](docs/MODEL_SELECTION.md).

## RSI boundary

The benchmark freezes tasks, verifier, budgets, and the environment contract. The mutable object is the
harness policy. Train trajectories are available to the improvement loop; hidden test state is not.
Accepted candidates are inherited, rejected candidates are retained for audit, and the historical best is
never discarded.
