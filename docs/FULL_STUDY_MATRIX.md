# Full computer-use study matrix (offline gate v1)

The target experiment has four researcher configurations across six original-software cells. Each cell must admit **100 distinct official task instances** and one 20-task selection set before any final-score dispatch. The common student is `Qwen/Qwen3.8-27B`; the fixed rollout teacher is `gpt-5.6-sol`. The researchers are `gpt-6-astra`, `gpt-5.6-sol`, `gpt-6-sol`, and `gpt-6-luna`. This produces 24 researcher campaigns, six shared base evaluations, and four selected-checkpoint comparison slots per cell: **600 distinct task identities and 3,000 slot-task results**. A researcher that retains an identical base checkpoint reuses its exact frozen base execution; the matrix records the evidence owner and counts unique checkpoint-task executions separately, so 3,000 is an upper bound on initial unique executions, not a guaranteed provider-call count. Reruns are separately declared and retain their original outcomes.

`src/cursibench/full_study_matrix_v1.py` is a **post-campaign final-evaluation preparation gate**, not a runner or a result. The [pre-campaign freeze](FULL_STUDY_PRE_CAMPAIGN.md) must first bind the admitted cells and 24 researcher configurations without selected checkpoints. This matrix reads one SHA-pinned `cua-full-study-matrix-v1` manifest with exactly the six declared cells and five qualified slot manifests per cell: one shared base and one selected checkpoint per researcher. It re-runs the existing `cua-final-cell-v0.6` qualification validator for each slot. That validator requires 100 task identities, saved-state GUI round trips, positive/negative independent-verifier receipts, fresh-environment reset receipts, disjoint train/selection/final source and template groups, a frozen checkpoint, and a declared all-in cost bound. The matrix gate additionally requires the same training, selection, final tasks, source/runtime/action/verifier bytes, sampling, execution settings, and qualification receipt across the five matched slots in a cell, and rejects drift from the pre-campaign freeze.

The matrix manifest has these top-level fields:

```json
{
  "schema": "cua-full-study-matrix-v1",
  "study_id": "full-computer-use-v1",
  "student_model": "Qwen/Qwen3.8-27B",
  "teacher_model": "gpt-5.6-sol",
  "researchers": {
    "astra": "gpt-6-astra",
    "sol56": "gpt-5.6-sol",
    "sol6": "gpt-6-sol",
    "luna6": "gpt-6-luna"
  },
  "pre_campaign_protocol": {"path": "pre-campaign.json", "sha256": "..."},
  "pre_campaign_plan": {"path": "pre-campaign-plan.json", "sha256": "..."},
  "configurations": {
    "student": {"path": "configs/student/config.json", "sha256": "..."},
    "teacher": {"path": "configs/teacher/config.json", "sha256": "..."},
    "researchers": {
      "astra": {"path": "configs/astra/config.json", "sha256": "..."},
      "sol56": {"path": "configs/sol56/config.json", "sha256": "..."},
      "sol6": {"path": "configs/sol6/config.json", "sha256": "..."},
      "luna6": {"path": "configs/luna6/config.json", "sha256": "..."}
    }
  },
  "cells": [
    {
      "cell_id": "powerpoint-web",
      "analysis_families": {"path": "cell/analysis-families.json", "sha256": "..."},
      "base_manifest": {"path": "cell/base.json", "sha256": "..."},
      "selected_manifests": {
        "astra": {"path": "cell/astra.json", "sha256": "..."},
        "sol56": {"path": "cell/sol56.json", "sha256": "..."},
        "sol6": {"path": "cell/sol6.json", "sha256": "..."},
        "luna6": {"path": "cell/luna6.json", "sha256": "..."}
      }
    }
  ],
  "budget": {
    "campaign_hours": 16,
    "tinker_usd_per_campaign": "500",
    "researcher_inference_usd_per_campaign": "...",
    "researcher_calls_per_campaign": 0,
    "teacher_rollout_usd_per_campaign": "...",
    "teacher_rollout_tokens_per_campaign": 0,
    "teacher_rollout_calls_per_campaign": 0,
    "e2b_sandbox_hours_per_campaign": "...",
    "e2b_usd_per_campaign": "...",
    "e2b_peak_concurrency": 0,
    "storage_application_usd_per_campaign": "...",
    "candidate_submissions_per_campaign": 0,
    "selection_evaluations_per_campaign": 0,
    "per_campaign_all_in_ceiling_usd": "...",
    "global_all_in_ceiling_usd": "...",
    "available_all_in_usd": "...",
    "spending_authorized_by_user": true
  }
}
```

The example shows only the first cell; a real manifest must include `excel-web`, `desktop-native`, `odoo-community`, `gitlab`, and `magento-admin` as well. [The dated enterprise-cell amendment](FULL_STUDY_ENTERPRISE_AMENDMENT_2026-09-25.md) selects original Odoo Community as a provisional sixth cell before any official outcomes; ServiceNow WorkArena remains a separately gated supplemental track. Ellipses and zero call limits are placeholders and **fail validation**. Every reference must point to a local file under the manifest directory and bind its exact SHA-256. Each cell's `cua-cell-analysis-families-v1` file assigns one pre-result primary source family to each official task, and that family must be among the task's declared source groups; this prevents choosing convenient bootstrap clusters after viewing scores. Each `cua-model-configuration-v1` file binds the role, provider-reported model and snapshot when available, reasoning/renderer settings, and the exact bytes of its prompt, harness, tool grammar, decoding, provider route, and student training configuration. The researcher/teacher settings must state a supported reasoning effort and standard/pro mode; temperature is omitted for these reasoning calls, following [OpenAI's Responses deployment guidance](https://developers.openai.com/api/docs/guides/deployment-checklist). A null snapshot is explicitly reported rather than silently called a weight attestation. No provider key belongs in those files. The per-campaign Tinker ceiling is $500 and the nominal 24-campaign Tinker ceiling is $12,000. Equal dollar and quantity caps for researcher inference, teacher rollout, E2B, storage/application services, candidates, and selection are required for all 24 campaigns. A campaign's all-in cap must cover those declared dollar caps plus one selected final-evaluation bound. The global upper bound reserves **24 campaign all-in caps plus six shared-base final evaluations**. Selected final evaluations are already inside campaign caps and are not counted a second time. The available balance must cover that global bound. These are declared upper bounds, not invoices or account-entitlement proof.

After all 30 qualified slot manifests exist, prepare offline with:

```bash
PYTHONPATH=src python tools/prepare_full_study_matrix_v1.py \
  --manifest work/full-study/matrix.json \
  --out work/full-study/prepared
```

The command writes hash-bound `intent.json` and `matrix-plan.json` once, checks them on resume, and makes **zero** provider, E2B, application, or model calls. It emits no score. Tests construct a synthetic *validator fixture* to exercise the full 30-slot shape; those fixture booleans are not observational evidence. The validator proves schema, byte bindings, and internal agreement only. A real cell's underlying GUI trace, evaluator implementation, reset, data rights, and hidden-set separation still need independent audit before its receipts are trusted.

**Current status:** no cell has 100 individually admitted official final tasks. Published one-task Office, GitLab, and Magento controls, offline 20/100 candidate splits, and Qwen development pilots do not satisfy this gate. The planned 4 x 6 x 100 result paper must remain unreported until real qualifying manifests, checkpoint lineages, 3,000 actual task outcomes, and complete usage/failure evidence exist. See the [implementation plan](plans/2026-09-24-full-scale-computer-use.md) and [v0.6 qualification note](qualification-v06/README.md).
