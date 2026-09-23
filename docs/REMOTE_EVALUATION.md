# Remote evaluation and evidence admission

The remote controller runs the frozen browser evaluator on a separate Linux E2B instance. It is a trusted orchestration service. Researcher-generated code and student actions cannot access it. The execution path remains Tinker checkpoint sampling, an E2B proxy, Harbor, the native Kanboard application, and a separate saved-state verifier.

The public source snapshot in `docs/evidence/remote-controller-sources-v1.json` pins the 20 supplied runtime files and the remote dispatcher. The payload also binds each task package, checkpoint, sampling settings, installed package versions, and selected package source files. Changing these inputs requires a new versioned protocol; it must not silently replace an existing run.

## Prepare a controller

Use the declared Python 3.12 Harbor environment and configure provider credentials outside the repository. Preparation is offline; building consumes the configured E2B account.

```sh
PYTHONPATH=src python tools/build_remote_orchestrator_template.py \
  --out work/my-remote-controller
PYTHONPATH=src python tools/build_remote_orchestrator_template.py \
  --out work/my-remote-controller --execute
```

An existing alias alone does not prove that a template build is READY. Preserve the preparation and provider build evidence. Do not launch evaluation until readiness is independently established.

## Initial frozen finals

These commands require a completed local study with both campaign registries, training artifacts, sealed packages, and a frozen `final-comparison.json`. Private sampler checkpoints and raw execution directories are not included in the public release. The sanitized release supports report rebuilding; new cloud experiments use newly generated local artifacts.

```sh
PYTHONPATH=src python tools/prepare_remote_factory_final.py prepare \
  --study work/my-study --template-directory work/my-remote-controller
```

Preparation creates one slot per distinct checkpoint and prescribed repetition. Each slot contains two three-task chunks. Its `plan.json` equals the frozen final plan; `operational-plan.json` binds the comparison, checkpoint, both selection freeze times, and child payload hashes. Identical selected/base checkpoints share the same explicitly declared executions. These are initial finals, with no invented recovery history.

For one prepared chunk, set `CUA_FINAL_CHUNK` to its directory and `CUA_CONTROLLER_TEMPLATE` to the READY template name recorded by controller preparation:

```sh
PYTHONPATH=src python tools/run_cloud_chain_remote.py launch \
  --out "$CUA_FINAL_CHUNK" --template "$CUA_CONTROLLER_TEMPLATE"
PYTHONPATH=src python tools/run_cloud_chain_remote.py status \
  --out "$CUA_FINAL_CHUNK"
PYTHONPATH=src python tools/run_cloud_chain_remote.py collect \
  --out "$CUA_FINAL_CHUNK"
```

Use the same directory and job identity after a lost acknowledgement. A durable creation intent precedes allocation, and a remote execution intent precedes inference. An uncertain creation or dispatch is reconciled before further work; changing the output directory is not a recovery method. Completed evidence is collected without repeating inference.

After both chunks are collected and cleanup is verified, use the slot label from `final-comparison.json`:

```sh
PYTHONPATH=src python tools/prepare_remote_factory_final.py finalize \
  --study work/my-study --label "$CUA_FINAL_LABEL"
```

This verifies evidence without registering a result. Independent review checks the archive and every extracted member, trusted source inventory, model/task bindings, successful dispatcher completion, separate verifier results, freeze-before-test timing, and cleanup. The same command with `--admit` then records the recomputed six-task outcome once. Repeating admission verifies the existing result and refuses differences.

## Original-study recovery

`prepare_remote_final_recovery.py` is restricted to four recorded infrastructure-invalid slots of the original study. It is not a generic score retry. Its amendment preserves all original outcomes and the two valid Astra-selected slots, supersedes incomplete bootstrap-only recovery paths with explicit markers, and prescribes one fresh six-task suite per eligible logical slot.

The recovered view never combines successful original rows with new rows. It is not an additional research seed or repetition. In the original cohort, retained Astra executions use the Mac controller and replayed base/Sol executions use Linux; the resulting comparison is descriptive and cannot isolate a training-data effect from controller or observation variation.

## Export and publish

`audit_factory_study.py` reconstructs each study's data provenance, training accounting, selection history, final results, and operational amendments from local evidence. Report, figure, explorer, and release builders require completed audits for both cohorts. Missing results remain incomplete; infrastructure-invalid scores remain undefined. A result PDF is rendered and visually inspected before release.
