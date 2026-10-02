# GitLab complete Git proof for model workers

This additive source path captures the target project's raw before tree, after tree, changed-path diff and all six monitored blobs while the original native backend lease is still open. The backend captures before its cold-reset finalizer. Post-reset audits reopen the retained bytes and evaluator-private context; they never reconstruct a formal positive from six historical blob hashes or trust a captured verdict boolean.

The original TRAIN and selection grader function code and verdict values are retained. A normal negative caused by an unrelated Git edit remains the original zero verdict. Unsupported positive path or mode scopes fail closed. Final readback calls `audit_formal_saved_task`, retains the original final verdict, and mechanically maps its fields for the unchanged selection actor loop. The model receives its original screenshot/instruction/GUI action interface. Git readers, SQL, task oracles and the private proof context are evaluator operations only.

The completed source work has **12 focused offline tests and 53 existing regression tests passing**. The focused tests exercise all 13 original workflow families, positive and protected-field negative verdicts, unrelated Git negatives, raw capture before reset, post-reset reopening without live lookup, terminal capture without model credit, teacher/selection actor loops, the concrete final loop, source-dependency drift, five-slot identity, checkpoint deduplication, dispatched reservations and one-shot intents. Native execution, official admissions and model scores remain unverified and zero.

## Source preparation

From the repository root, create an owned directory with mode 0700 and freeze the supplemental binding. The CLI reads repository source and fixed source assets only; it does not read hidden task bodies or start an application/provider.

```bash
mkdir -m 700 "$GITLAB_MODEL_SOURCE_DIR"
PYTHONPATH=.:src python -m gitlab_world.full_git_model_workers_v1 freeze-source \
  --out "$GITLAB_MODEL_SOURCE_DIR/binding.private.json"

PYTHONPATH=.:src python -m gitlab_world.full_git_model_workers_v1 check-source \
  --binding "$GITLAB_MODEL_SOURCE_DIR/binding.private.json" \
  --binding-file-sha256 "$BINDING_FILE_SHA256"
```

`freeze-source` prints both the canonical binding digest and the exact file digest. Its 97-file source closure includes lazy in-repository Python imports, explicit dynamic runtime roots, fixed data sources, budget/admission helpers and the original action/model stack. Freeze the same binding together with the original six-cell ratification and all five matching matrix slots before using this model path. The supplemental binding does not extend historical control or admission evidence.

## Trusted APIs

The factories below require the explicit immutable cohort source. The owned source file is pinned at construction and checked again before each application open; its digest is retained with the saved proof. Use the same cohort and source binding for teacher, base, selection and all final slots.

```python
from gitlab_world import full_git_model_workers_v1 as full_git
from gitlab_world.full_git_shared_base_execution_v1 import run_gitlab_shared_base
from gitlab_world.full_git_final_worker_v1 import final_worker_factory

common = dict(
    full_git_binding_path=binding_path,
    full_git_binding_file_sha256=binding_file_sha256,
    cohort_freeze_path=cohort_freeze_path,
)

teacher = full_git.train_worker(
    **common,
    private_output_root=train_output_root,
    ratification_path=ratification_path,
    ratification_sha256=ratification_sha256,
    expected_runtime_sha256=full_git.teacher.runtime_sha256(),
    expected_verifier_sha256=full_git.teacher.verifier_sha256(),
    enable_live=False,
)
selected = full_git.selection_worker(**common, enable_live=False)
```

The teacher keeps the original `run_episode(task, out_dir, sample_teacher, dispatch_e2b)` API. Selection keeps the original `run_attempt(session, started, out_dir, sampler_provider)` API, including its exact 20-identity view and existing campaign reservations. Live execution remains disabled unless explicitly enabled and all original frozen gates pass.

For shared-base selection, invoke the additive entry point instead of the legacy default. It always passes the full-Git worker to the existing paid runner and retains the original base checkpoint freeze, base sampler, usage reconciliation and admission logic.

```python
result = run_gitlab_shared_base(study, usage_reconciler, **common)
```

For final scoring, use the existing validated `FinalGate` and six-cell `FinalController`. The factory constructs one concrete worker for the sealed 100-identity metadata view. That one worker uses the same supplemental source/cohort binding across the shared base and four selected slots. Existing checkpoint deduplication still chooses the execution owner. Hidden task bodies are opened only inside the already dispatched paid application operation.

```python
from cursibench.full_study_final_dispatch_v1 import FinalController

gitlab_final = final_worker_factory(
    gate=gate,
    **common,
    final_output_root=final_output_root,
    enable_live=False,
)
workers["gitlab"] = gitlab_final
controller = FinalController(
    gate,
    workers=workers,
    sampler_bindings_path=sampler_bindings_path,
    output_dir=final_output_root,
)
```

The existing gate still requires the full matrix, completed campaign freezes, ratification, matching runtime/action/verifier sources, qualified initial state, sampler/checkpoint identity and the exact dispatched dollar reservation. The factories do not create a gate, grant admission, change budgets/action limits, or authorize replay. Original control, teacher, selection, verifier and shared-base source bytes remain unchanged. The original uncommitted WIP sources were preserved before completion.
