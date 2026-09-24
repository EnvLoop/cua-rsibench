# Magento admin: a 100-task admission backlog, not a final benchmark

## Measured source and offline result

The pinned [WebArena Verified](https://github.com/ServiceNow/webarena-verified/tree/6473f72db5dcefc97b5725b59e734504edc28a21) dataset has **182** Magento-admin single-site task IDs from **41** intent templates. Its dataset SHA-256 is `d65275660814663375028e9017e1f929e3c38321041b125795e2713b52243d30`; the published hard-subset JSON SHA-256 is `3b0a4df231bb5a0c642215e521c3fa97701a384f52a734dc2db8f617ad0591a7`. Only **55** of the 182 admin IDs are in that published hard subset. Neither the full count nor the hard label establishes that a task is GUI-solvable, difficult for our student, or independently scorable. A [source and evaluator audit](magento-100-candidate-audit-2026-09-24.md) found three task-specific exceptions that are excluded from the corrected backlog.

[`plan_magento_final_candidates_v06.py`](../../tools/plan_magento_final_candidates_v06.py) creates a deterministic, private task-identity backlog from those pinned bytes. It reserves entire intent-template families for a 20-task selection set, including a family from each of retrieval, navigation, and mutation, then prioritizes published hard IDs and persistent mutations among the remaining families for a 100-task **provisional final candidate** set. Task packages and hidden answers are not produced. The queue is not a frozen official set.

| Offline property | Count |
| --- | ---: |
| Source Magento-admin task IDs / intent templates | 182 / 41 |
| Published hard-subset admin IDs | 55 |
| Selection candidates / template families | 20 / 5 |
| Provisional final candidates / template families | 100 / 33 |
| Final candidates from published hard subset | 44 |
| Final task types | 63 successful mutate, 32 retrieve, 5 navigate |
| Source-entity-hint overlaps excluded from final | 8 task IDs |
| Clone-sensitive price template held from both sets | 6 task IDs |
| Additional individual source tasks excluded | 3 task IDs |
| Provisional candidates admitted to a sealed official final set | **0** |

The clone-sensitive price template is 742. In one isolated Magento 2.4.6 clone, [task 777](magento-variant-price-rejection-2026-09-24.md) received 1.0 from the unchanged network evaluator after five product-save POSTs, yet the GUI reported a save error and all five prices remained unchanged in SQL. After repairing that clone's search service and URL, a [separate task-777 GUI run](magento-variant-price-qualified-2026-09-24.md) persisted the five target prices, rejected a wrong-color edit, and restored monitored SQL plus search-index state. This proves **one task in one repaired clone**, not every variation of template 742. Holding the six template IDs from the provisional final backlog remains a conservative qualification quarantine, not a claim that the template always fails. A separate [order-address task](magento-order-address-mutation-2026-09-24.md), which lies in this provisional final queue, also passed GUI positive/wrong-order negative, SQL readback, and reset. It is still a public development task; one local task receipt does not make the provisional set a hidden official final benchmark.

Two published records labeled `mutate` actually expect `ACTION_NOT_ALLOWED_ERROR` and no saved change (IDs 491 and 790); they belong in a separately scored policy-denial cohort, not this successful-mutation queue. Task 423 has a product-save assertion containing unrelated report-filter POST fields, so it is held until a native GUI, HAR, SQL-state, and reset check resolves the mismatch. The corrected 100 identities are a deterministic refill from the same pinned source. They all have published `SUCCESS` status, but none is admitted merely by replacement. The private manifest now records expected status and distinguishes saved-mutation oracles from no-state-change oracles.

The selection/final sets are disjoint by `intent_template_id`. They also exclude eight final candidates with an obvious entity hint shared with a selection-family task. These hints inspect a few explicit `order_id`, product, config, brand, and phone fields. They cannot discover every implicit shared order, customer, product, review, or database row. **Full source-entity isolation remains unverified.** Public task instructions and evaluator answers are discoverable in the upstream repository, so a genuinely hidden final exam will additionally need new evaluator-owned variants or source entities; simply withholding this JSON does not make the published tasks hidden.

The queue's mutation priority is a proposed work order, not a score of difficulty. Every provisional final task still requires: a fresh seeded environment, bounded visible-GUI positive and plausible wrong-object negative, independent database or artifact readback, no-regression checks, reset-to-baseline proof, fixed Qwen3.8-27B observation/action compatibility, and a verified cost bound. A retrieval case also needs trusted browsing/answer provenance because upstream retrieval evaluators may only grade the final text. The manifest records which task type needs which extra oracle, but it does not assert those oracles have run.

Rebuild the ignored private queue after obtaining the pinned upstream checkout:

```bash
python3 tools/plan_magento_final_candidates_v06.py \
  --source work/scale-v06/sources/webarena-verified/assets/dataset/webarena-verified.json \
  --hard-ids work/scale-v06/sources/webarena-verified/assets/dataset/subsets/webarena-verified-hard.json \
  --out work/scale-v06/magento-100-admission-plan.json
python3 -m unittest tests.test_plan_magento_final_candidates_v06 -v
```

The generated JSON is ignored under `work/`; it contains upstream task identities, record hashes, template groups, and triage flags. This public summary reports reproducible counts without republishing benchmark task text or answers.
