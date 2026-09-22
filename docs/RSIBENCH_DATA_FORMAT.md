# RSIBench-Data-shaped computer-use format

The benchmark has two separable tracks:

1. **Harness RSI** changes the computer-use harness while the foundation model is frozen.
2. **Data RSI** changes `train_messages.jsonl` and bounded training configuration while the target
   model, serving path, sandbox and evaluator stay fixed.

For a defensible computer-use result, the protocol also needs task-template/application split isolation,
`avg@3` repeats, non-recursive controls, append-only lineage and cost accounting. The local
`BenchmarkSpec` and `Ledger` currently describe those fields only. They do not enforce isolation, execute controls, provide append-only storage, or measure costs.

The second track follows this fixed chain:

```text
data-generation agent
  -> Tinker SFT messages JSONL
  -> Tinker LoRA SFT
  -> Tinker sampler checkpoint
  -> E2B tool-call proxy sandbox
  -> Harbor benchmark evaluation
  -> scored attempt and final submission
```

The repository's `service_pipeline.run_service_chain` runs this shape locally with deterministic fake
providers. It writes `data_generation_agent.json`, `train_messages.jsonl`, `scored_attempt.json`,
`final_submission.json`, `result.json`, the provider mode, the checkpoint URI, the E2B proxy sandbox
identity, the Harbor result, and the frozen sampling/evaluation configuration.

## Real adapter boundary

Real integrations must implement the three provider protocols in `cursibench.service_pipeline`:

- `TinkerBackend`: LoRA training and checkpoint sampling;
- `E2BBackend`: create the fixed proxy template and execute the sandbox;
- `HarborBackend`: run the selected dataset and return task results plus infrastructure errors.

The adapter must not modify tasks, hidden expected state, verifier code, or evaluation hyperparameters.
Missing keys must fail before a paid run. A local-fake result is useful for CI but is not evidence of
an external Tinker/E2B/Harbor evaluation.

## Computer-use dataset mapping

Each Harbor task should mount a resettable application state, visible inputs and the user instruction.
The hidden verifier reads the final artifact independently. For a document task this means checking the
parsed application state, intended object changes, untouched objects, and artifact integrity; screenshots
remain evidence for visual quality rather than the sole authority.
