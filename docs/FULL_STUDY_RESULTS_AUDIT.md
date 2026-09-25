# Full-study result audit and report input (offline v1)

The [pre-campaign freeze](FULL_STUDY_PRE_CAMPAIGN.md) binds six qualified cells and 24 researcher intents before training; the [post-campaign matrix](FULL_STUDY_MATRIX.md) binds their selected checkpoints before final evaluation. `src/cursibench/full_study_results_v1.py` is the third gate. It accepts **only a complete execution index** linked to the rebuilt final matrix, then produces the paired statistics that a future English paper and visualization may consume. It does not run a researcher, train Qwen, operate an application, or create a score from a candidate inventory.

The private index schema is `cua-full-study-execution-index-v1`. It contains `study_id`, `matrix_plan_sha256`, exactly 24 `campaigns`, and one `final_executions` reference per **unique checkpoint** in the matrix. Every reference is a local `{ "path": "...", "sha256": "..." }` pair under the index directory. Each campaign references a selection-freeze receipt and a usage/failure receipt. The freeze binds the base and selected checkpoint hashes, training-lineage and selection-result hashes, candidate/selection counts, and start/freeze/finish timestamps within the 16-hour cap. Usage is broken out by Tinker, researcher inference, teacher rollout, E2B, storage/application services, and selected final evaluation, with dollars, calls, tokens, sandbox hours, candidate counts, provider invoice availability, and failure counts. Every declared cap is checked.

A final execution receipt names its evidence-owner slot, checkpoint, timestamps, cost basis, and **exactly 100** frozen task-package results. Each task has one scored, binary 0/1 attempt or one infrastructure-invalid attempt followed by a scored recovery. Invalid provider, transport, environment, and verifier attempts remain counted separately and can never become a model zero. Saved state, independent verifier, reset, action trace, and observation trace hashes are required for each scored result. The final execution must begin after all four selections in its cell were frozen. If selected slots reuse an identical checkpoint, they reuse the exact evidence owner and may not claim extra task executions or charge their campaign for a duplicate final run.

Only after all six cells, 24 campaigns, and 3,000 slot-task outcomes pass does the audit compute 24 paired base-to-selected comparisons with the preregistered source-family clustering and fixed bootstrap seed. It records all cost bases and leaves `provider_invoice_complete` false unless every campaign and final execution has provider-billed cost evidence. The result of a synthetic 30-slot validator fixture is **not** a benchmark result. Hashes and JSON schemas prove internal consistency, not that an application-specific GUI trace or SQL/OOXML readback is truthful; independent cell audits must still inspect those raw receipts before publication.

After the real matrix and execution index exist, run:

```bash
PYTHONPATH=src python tools/audit_full_study_results_v1.py \
  --matrix-manifest work/full-study/matrix.json \
  --execution-index work/full-study/execution-index.json \
  --out work/full-study/audited-results.json
```

The command revalidates every qualification and checkpoint reference from the source matrix before reading final receipts. It writes its private summary once and refuses an incomplete index. The eventual public PDF/figures must be derived from a separately privacy-reviewed projection of that summary, and the released assets must be downloaded back and visually inspected. **Current real status:** zero official final tasks, zero completed 24-campaign records, and no full-study result index or result paper.
