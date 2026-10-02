# Witnessed runtime policy v22

This is an additive pre-result policy implementation. It preserves the frozen historical USD500 protocol and its episode bytes. The new policy follows the direct human authorization for no dollar ceiling. It does not assume funding availability or publish a benchmark result.

The same new policy covers six cells, 24 campaigns, 600 distinct official task identities and 3000 initial slot-task results. Every campaign retains its 16-hour limit and existing compute/count caps. All five student slots declare 90 actions, 720 actor seconds and 1200-second leases. Actor time excludes setup, native cold boots, independent save/readback/reset and provider shutdown; those measured lifecycle times remain separate.

Original Office cloud-account/browser leases are explicitly classified as storage/application operations in v22. They must not fabricate E2B transactions. Desktop remains an actual E2B environment. The environment policy is source-bound in the new amendment and witness for all five slots. Original environment declarations remain historical evidence.

A completed sample response, an applied GUI action, independently scored saved state and authentic billing are separate facts. A consumed last request may remain uncertain after the exact actor deadline. Its performance is admitted only after the saved artifact, independent verifier, fresh distinct reset, owned cleanup, no late GUI and provider-close acknowledgement are reopened. Missing responses stay missing; unknown tokens, invoices and actual charges stay null. Known late responses are retained separately and withheld from GUI. Earlier provider faults remain infrastructure-invalid, and an invalid attempt with unknown billing cannot be retried.

`full_study_runtime_v2` preserves the actual campaign resource checks, paid request/result hash chains, training checkpoint lineage, 20-task coverage, no-regression promotion and incumbent computation. It removes the old dollar comparison and separates billing completeness from checked performance. Its fresh final gate rebuilds 600 admissions, the matched matrix, all 24 private campaign chains and an immutable final witness. An old campaign header is rejected under the new policy. `full_study_final_performance_v2` retains the original reset, saved-state verifier, screenshot/action trace, timing and source/worker checks while accepting nullable authentic cost. A nominal estimate is not accepted as an observed charge.

`policy_execution_v22.run_selection` requires the additive `current_episode_paid_id_v22` actual paid-ID hook and uses the current actor/scorer/reset engine and a fresh clean sampler per task, identically for base and all four checkpoints. A poisoned sampler is acknowledged/closed before performance admission and before the next task. The paid wrappers preserve exact typed deadline proof, write the consumed uncertain request, and permit only one owned reset before admission. They never repeat the request or apply a late response.

The real v21 TRAIN diagnostic is retained as historical evidence: 22 completed responses, 22 applied clicks, one retained error result, 720 actor seconds, independently saved score 0, exact fresh reset and provider-close acknowledgement. Its 23rd normal response and invoice remain unknown. Reopening those artifacts under the new adapter does not register or reclassify that old episode. New formal receipts require RPCs bound to the fresh policy hash.

Native qualification remains separate. The reviewed Odoo supplemental final/shared-base source is registered as a source dependency; its legacy total-time accounting cannot be relabeled as actor time. The new Odoo clock/deadline verifier and actual paid-ID hook must be imported before the new source freeze. The Odoo runtime must be qualified in a fresh epoch before activation. The legacy Desktop teacher uses 600-second leases, 1350-second episode timing and an older byteguard; it is not qualified under this policy. A new teacher factory should reuse the current `_episode` engine with real teacher callbacks and real 1200-second actor/reset leases. No claim that all seven actor paths or all six native runtimes are qualified is made.

## Preparation and commands

Run from a reviewed checkout with its existing pinned clean Python runtime. Place all private paths under that checkout's `work` directory. These commands do not dispatch providers:

```bash
PYTHONPATH=.:src "$TASK_PYTHON" -m cursibench.full_study_runtime_v2 prepare \
  --repo-root "$TASK_REPO" --output "$TASK_POLICY_DIR" \
  --parent-manifest "$TASK_PARENT_MANIFEST" --parent-prepared "$TASK_PARENT_PREPARED" \
  --ratification "$TASK_RATIFICATION" --parent-public-commit "$TASK_PARENT_COMMIT" \
  --parent-witness "$TASK_PARENT_WITNESS" --amendment "$TASK_AMENDMENT"
```

Publish only the generated safe pre-result witness at `docs/evidence/full-study-pre-result-policy-witness-v2.json` in an immutable commit before new paid study work. The historical parent witness and new policy witness are checked separately. Source changes require a new namespace and witness.

The new CLI keeps the original required campaign arguments and real commands:

```bash
PYTHONPATH=.:src "$TASK_PYTHON" tools/full_study_campaign_dispatch_v2.py \
  --policy-dir "$TASK_POLICY_DIR" --parent-witness "$TASK_PARENT_WITNESS" \
  --policy-public-commit "$TASK_POLICY_COMMIT" --repo-root "$TASK_REPO" \
  --manifest "$TASK_PARENT_MANIFEST" --prepared-dir "$TASK_PARENT_PREPARED" \
  --ratification "$TASK_RATIFICATION" --public-commit "$TASK_PARENT_COMMIT" check
```

The same prefix supports `base-admit`, `start`, `base-selection`, `researcher-call`, `selection-start`, `selection-score`, `selection-invalid`, `selection-freeze` and `reconcile`. Only the inherited researcher command invokes a paid request through the normal gates. SFT, native workers and actual teacher callbacks retain their existing programmatic entrypoints under `runtime_context(study)`.

The concrete current Desktop selection/base entrypoint is:

```python
from native_desktop_factory.policy_execution_v22 import run_selection, admit_shared_base
result = run_selection(worker=qualified_worker, session=session, started=started,
                       checkpoint_path=actual_checkpoint_path,
                       output_dir=fresh_private_output, base=is_base)
# Base admission reopens every native saved/reset artifact and actual paid call.
if is_base:
    admit_shared_base(study=study, worker=qualified_worker, session=session,
                     native_result=result, usage_reconciler=authentic_usage_reader)
# A checkpoint result is registered by the actual campaign promotion method.
else:
    session.record_selection_scored(attempt_id=started['attempt_id'],
                                   result=result['result'],
                                   paid_attempt_ids=result['paid_attempt_ids'])
```

Use `prepare_matrix(study, actual_matrix_manifest, fresh_output)` for the v22 matched matrix. Construct the new `FinalGate` with the actual 24-chain completion index and new immutable policy/final witnesses; missing chains refuse before workers. Then construct `full_study_final_performance_v2.FinalController` with six source-qualified workers and actual sampler bindings. No final task body is opened during policy preparation or gate construction.

The source manifest includes the policy modules, current v21 closure, checked legacy counterparts and current public native source files. Root must freeze it again after importing the remaining native clock/teacher counterparts. Tests use synthetic native/provider surfaces and are not native qualification or paid benchmark outcomes.
