# Full-study pre-campaign freeze (offline gate v1)

The [post-campaign matrix](FULL_STUDY_MATRIX.md) binds four selected checkpoints per cell, so it cannot exist before the 24 researchers train. This separate `cua-full-study-pre-campaign-v1` gate freezes what researchers must share **before** any campaign can use selection feedback: six qualified original-software cells, 20 selection and 100 individually admitted final task identities per cell, disjoint training sources, the common Qwen student and Sol rollout teacher, four researcher configurations, source-family assignments, action/observation/runtime/verifier bytes, sampling, and matched per-campaign resource caps. It contains **no selected checkpoint and no result**.

The manifest has the same `study_id`, `student_model`, `teacher_model`, `researchers`, `configurations`, and `budget` fields as the final matrix, but its schema is `cua-full-study-pre-campaign-v1` and each of its six `cells` contains only `cell_id`, `analysis_families`, and `base_manifest`. Every reference is a local `{ "path": "...", "sha256": "..." }` pair. The base manifest is the evaluator-owned `cua-final-cell-v0.6` manifest: it must already prove application access, a fixed Qwen screenshot/action interface, 100 per-task native GUI positive/negative and saved-state/reset receipts, legal source use, and source/template/instance separation. The code revalidates every referenced byte and refuses duplicate official IDs across cells.

The all-in reserve is **six shared-base final-evaluation bounds plus 24 campaign caps**. Each campaign cap must at least cover its $500 Tinker ceiling, its declared researcher-inference ceiling, and one selected final-evaluation bound. Teacher, E2B, storage, and application services must fit within the remaining cap. The global ceiling and declared available balance must cover the full reserve; those declared figures are not invoices or proof of provider entitlement. Actual calls, charges, quota hits, and uncertain responses remain separate runtime evidence.

After all six cells qualify, prepare without remote or paid calls:

```bash
PYTHONPATH=src python tools/prepare_full_study_pre_campaign_v1.py \
  --manifest work/full-study/pre-campaign.json \
  --out work/full-study/prepared-campaigns
```

This writes a hash-bound `intent.json` and 24 immutable `campaign_intents` in `campaign-plan.json`, refusing a changed resume. The private plan includes task identity hashes, but no final-task instructions or gold should be shown to a researcher. Publish the plan digest and protocol revision **before the first campaign**; a local hash alone cannot prove when it was frozen. The later final matrix **must reference both this pre-campaign manifest and its exact plan**; it re-runs the pre-campaign validation and refuses changes to base checkpoint, tasks, family map, model configuration, environment, or budget. It then adds selected checkpoints and final-evaluation chunk plans. A separate paid dispatcher and result ledger are still needed; neither offline gate sends a provider request.

**Current status:** no real cell has 100 individually admitted final tasks, so no authentic pre-campaign manifest can pass. The test suite constructs a synthetic 600-task validator fixture to exercise the shape and tamper detection; its boolean receipts are not application evidence. Actual campaigns remain **0/24**.
