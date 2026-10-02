# Neutral Odoo native material qualification

This change is additive source preparation. It provides one fresh TRAIN control,
then complete 20-task selection and 100-task official_hidden GUI controls. No
new native control, model/provider call, source-frame visual review, campaign
ratification, or official task admission is established by the source/fake tests.
Historical v13 TRAIN success receives zero positive credit here.

## Prepare from existing metadata

Use the existing full private plan with schema
`envloop-odoo-v066-prospective-gui-requalification-plan-v1`. The projector takes
`tasks[split]` and `checkpoints[split]`, preserving exactly these row fields:
`task_id`, `family`, `package_sha256`, `task_binding_sha256`,
`source_asset_sha256`, `visible_instruction_sha256`, `source_label`.
Checkpoint fields are `db_sha256`, `filestore_sha256`,
`baseline_snapshot_sha256`, and `baseline_filestore_manifest_sha256`.
Their source construction is in `v066_requalification_plan.py` lines 156–186.
The preparation command does not open a partition world, prompt, source asset,
gold file, credential file, database checkpoint, Odoo service, or provider.

An existing split plan with schema
`envloop-odoo-v066-split-gui-control-plan-v1` is also supported when its roster
contains exactly 20 or 100 rows. The remaining-TRAIN plan has 19 rows and fails.
`task_set_manifest.json` alone lacks the required bindings and fails. The
projector never recovers missing fields from task bodies.

From this checkout, after creating an owner-only output directory, substitute
the root's existing frozen full metadata plan path for `FULL_METADATA_PLAN`:

```bash
PYTHONPATH=.:src:enterprise_fallback/odoo18 \
  python3.14 \
  -m tools.odoo_v066_native_material_qualification_v1 prepare \
  --legacy-metadata-plan FULL_METADATA_PLAN --split train \
  --private-plan OWNER_ONLY_OUTPUT/train-plan.private.json \
  --native-binding OWNER_ONLY_OUTPUT/native-binding.private.json \
  --public-plan OWNER_ONLY_OUTPUT/train-plan.public.json
```

`--metadata-plan-sha256` can additionally pin the exact input metadata bytes.
Dedicated projected metadata uses `--roster-metadata` instead. Each preparation
generates a new nonce and whole source binding. Selection/official_hidden use
the same command with their split and distinct output files. Public plans expose
counts and hashes, with native control/model/admission counts all zero.

## First TRAIN control and independent visual review

Live execution is a distinct later action. Set `ENVLOOP_ODOO_WORKER_DIR` to the
original `train` worker and use its private run path
`WORKER/private/v066_native_material_controls/FRESH_RUN_DIRECTORY_NAME`, where
the directory name is copied from the prepared private plan:

```bash
PYTHONPATH=.:src:enterprise_fallback/odoo18 \
  python3.14 \
  -m tools.odoo_v066_native_material_qualification_v1 run \
  --plan OWNER_ONLY_OUTPUT/train-plan.private.json --worker-dir ORIGINAL_TRAIN_WORKER \
  --run-dir EXACT_FRESH_RUN_DIRECTORY --execute
```

This chooses one purchase TRAIN row, or an explicit `--train-task-id`, and runs
the original source GUI, positive repair, wrong-object negative, reload, SQL
readback, physical filestore readback, and exact restore through the common
neutral adapter. It retains the existing split lease and independent saved-state
verifier. The recorder makes one parse attempt per action; no stale resample,
action retry, resume, or failed-attempt replay is available.

All three isolated startup paths retain the accepted v13 database readiness
sequence. They stop web if present, start db, run the original bounded
`_wait_db_ready` health plus `bench_verify` `SELECT 1` gate, then start web and
perform the original restore. Bounds stay 60 seconds total, 5 seconds per probe,
30 probes, and 1 second polling. A startup failure restores the original service
set using service operations only; it cannot run SQL restore before readiness.
The helper retains a success/failure receipt. Control audits hash and verify the
attempt's `db-readiness.private.json`; teacher episodes retain it under
`artifacts/`, and Qwen batches at their output root. The accepted v13 helper
source and the additive readiness helper are both in the whole source binding.

The result remains `fresh_native_material_train_flow_pending_independent_source_review`.
It writes `train-control-candidate.private.json`, never an accepted TRAIN proof.
A separate owner-only source-frame review must use schema
`envloop-odoo-v066-native-material-source-frame-review-v1`, status
`independent_native_source_frame_review_verified`, and contain exactly:

- `task_id`, `package_sha256`, `source_asset_sha256` from the selected plan row.
- `source_frame_sha256` from the exact attempt's `refs.source_frame`.
- `attempt_sha256`, `audit_sha256` from the pending candidate.
- `native_worker_binding_sha256`, `native_adapter_binding_sha256`,
  `run_nonce_sha256` from the fresh plan.
- `reviewer_independent_of_actor`, `source_attachment_readable`, and
  `source_matches_package`, each explicitly true after independent inspection.
- `reviewed_at_utc`, a timezone-bearing timestamp after that attempt finishes.
- The schema and status stated above.

After actual independent raw frame inspection, finalize from saved evidence:

```bash
PYTHONPATH=.:src:enterprise_fallback/odoo18 \
  python3.14 \
  -m tools.odoo_v066_native_material_qualification_v1 finalize-train-control \
  --plan OWNER_ONLY_OUTPUT/train-plan.private.json --worker-dir ORIGINAL_TRAIN_WORKER \
  --run-dir EXACT_FRESH_RUN_DIRECTORY --source-review EXACT_NEW_REVIEW_RECEIPT \
  --source-review-sha256 EXACT_REVIEW_FILE_SHA256
```

Finalization reopens the fresh source PNG and re-derives the entire saved SQL,
filestore, action, guard, and lease audit. Only the new bound visual review can
produce `train-control.private.json` with `fresh_native_material_train_flow_verified`.
An old v13 review, a pending candidate, a mutated source PNG, or a mismatched
nonce/source binding cannot satisfy selection, official_hidden, or model gates.

## Full selection and official_hidden controls

Use the prepared split plan with `run --execute --train-control` and
`--train-control-sha256` pointing to the exact accepted new neutral TRAIN proof.
The TRAIN and split nonces must differ. These modes execute all 20 or all 100
metadata identities under a fresh immutable run directory. Every case requires
positive=1, baseline=0, wrong-object=0, exact checkpoint/reset/protected source
bytes, source GUI presentation, and both neutral guards re-derived from six
retained PNGs per action. A failure preserves the attempt and blocks replay.
Successful control semantics still leave per-case visual review pending and
`official_final_tasks_admitted=0`.

## Teacher and Qwen integration

`native_material_workers_v1.train_worker()` preserves the existing `run_episode`
API. `selection_worker()` preserves `run_selection`, including explicit Qwen
base mode and hash-bound selected Tinker checkpoint mode. All paths use the
exact `OdooV066NativeMaterialAdapter` class. Adapter arguments are only the
current page, task identity/package binding, visible instruction, and limits.

The wrappers compile checked isolated copies of the existing source files.
They install raw guard PNG sinks and parse the action before dispatch. Qwen
retains its normalized private action and native contract. Teacher preserves
the official sampled action trace exactly and stores native contracts separately
under `artifacts/native-contracts/`; wrapper auditing checks them against the
unchanged official action and frame. Existing module globals/files are unchanged.

Both model factories require the owner-only whole native source binding and its
file hash, the hash-bound accepted new TRAIN proof, explicit `enable_live=True`,
the existing expected runtime/verifier bindings, and a separately supplied real
`campaign_ratification_path`/`campaign_ratification_sha256`. The existing
`validate_ratification` must admit the unchanged two-field Odoo profile binding
the shared action source hashes and the neutral adapter source SHA. The separate
scoped binding additionally checks `native_adapter_binding_sha256` and the
whole worker source closure; it cannot substitute for six-cell campaign
ratification. Until that real neutral campaign profile is admitted, live model
execution remains blocked.
Existing paid dispatch, local cost authority, Qwen renderer/checkpoint, task
budgets, SQL/filestore, and worker lease machinery remain in force.

Verification uses the pinned Python and `unittest` source/fake fixtures. Coverage
includes complete fake 20/100 orchestration, pending/finalized TRAIN boundaries,
whole binding drift, official teacher trace equality, the real copied Qwen loop
with a fake page/sampler, saved raw guard re-derivation, single parse/no replay,
and the separate campaign prerequisite. These fixtures establish code behavior
only; they establish no current native control or paid attempt.
