# Executable computer-use data factories

This work extends the v0.4 selection pilot. Researchers now write and run Python to construct new native application tasks, obtain verified GUI experience, and emit training data. The original published v0.4 results remain unchanged.

## Implemented boundary

- A dedicated E2B workspace receives only approved training sources and the public task contract.
- A root-owned supervisor runs generated programs as a separate Unix user, in a separate network namespace, with no-new-privileges and CPU, memory, process, file-size and wall limits.
- The controller owns source partitions, budgets, teacher rollouts, expected targets, verification, and the positive-example registry. No provider credentials or host project/evaluation files are mounted in the research workspace.
- Generated task recipes are compiled into the real Kanboard application. Source facts are inserted from the controller registry; workflow rules and planning fields are explicitly synthetic.
- Supported initial task families are direct field updates, conditional/ranked selection, and constrained allocation. This is an application profile, not unrestricted desktop task coverage.
- Dataset submissions must match independently verified training traces. Researcher-authored success flags, fabricated observations, protected source IDs, and altered provenance are rejected.
- A shared GUI prompt constructor is used for generated demonstrations and student evaluation.

## Researcher interface

The agent can read/write workspace files, execute bounded Python, request a training rollout, and submit JSONL. It may generate task variants, inspect failures, select decision-only or full-history representations, deduplicate, order and mix verified examples. It can inherit its previous factory and training experience with controlled selection feedback for a subsequent round.

Inputs live under `/inputs`; generated files live under `/workspace`. Service journals are inaccessible to generated programs. The controller records program edits, execution receipts, hypotheses, rejected actions, data hashes and budget reservations. Complete bounded workspace snapshots are retained on normal exit. Interrupted controllers can reconnect to a live workspace without rerunning completed GUI episodes.

## Executed integration evidence

Two real researcher sessions used the same approved source pool and the same Sol teacher:

| Researcher | Generated verified episodes | Native teacher actions | Accepted examples |
|---|---:|---:|---:|
| gpt-6-astra | 2 | 11 + 18 | 26 |
| gpt-5.6-sol | 2 | 11 + 24 | 35 |

Astra wrote a source-dependent factory using state, labels and source timestamps. Sol wrote its own generator and revised its exporter after inspecting the actual record schema. Sol's controller was interrupted after both GUI episodes had passed, then resumed from the existing workspace. Completed rollouts were not repeated.

These figures establish executable generation and verified data production. They are not researcher rankings or proof of sustained RSI.

## Training and multi-task calibration

Both datasets have completed real 32-step Tinker LoRA training on Qwen3.5-4B under the same settings. The schedule covers every submitted row. Scheduled training tokens are 116,177 for Astra and 128,738 for Sol. Target responses fit the student's 512-token response budget.

A three-family selection suite was frozen before student runs. The initial multi-task evaluation exposed a proxy-cache capacity defect: 256 entries did not cover three 90-action trials. Those interrupted results are retained as unscored. The repaired proxy derives its bounded capacity from the task count and keeps retry idempotency. Paired reruns use unchanged datasets, weights, tasks, observer and verifier.

The repaired initial selection comparison completed without infrastructure errors: base student 0/3, Astra-data checkpoint 1/3, and Sol-data checkpoint 0/3. These are three-task calibration results. No final-task or generalization claim follows. The original small suite also needs counterbalanced source order, changed target attributes, and additional instances to test positional shortcuts.

## Run

```sh
python -m cursibench.factory_research --researcher gpt-6-astra --out work/my-factory
python -m cursibench.factory_research --out work/my-factory --resume
```

The resume option requires an incomplete run and preserves its budget reservations. A later feedback round can use `--parent` and `--feedback`; feedback must come from the fixed selection service, not final-test results.

```sh
python -m cursibench.factory_research --researcher gpt-6-astra \
  --parent work/my-factory --feedback work/selection-feedback.json \
  --out work/my-factory-round-2
python -m cursibench.tinker_backend --profile factory-v1 --steps 32 \
  --data work/my-factory-round-2/train_messages.jsonl --out work/trained-round-2
```

Training still enforces the fixed sequence and scheduled-token bounds. In the factory profile, insufficient exposure is rejected instead of silently ignoring the end of a dataset.

## Remaining gates

Complete a feedback-driven research trajectory through the fixed trainer and evaluator; preserve the historical best before final testing; calibrate a larger, counterbalanced task suite; run independent final cases and appropriate controls; then update the English report and visualization from the resulting evidence. The data-factory integration alone does not complete these gates.
