"""Mandatory full-Git integration for the unchanged shared-base paid runner.

This entry point always supplies the additive model worker. The existing
shared-base session, reservation ledger, base sampler and receipt admission
remain the sole execution protocol; its legacy default worker is never used.
"""
from __future__ import annotations
from pathlib import Path
from cursibench import full_study_shared_base_execution_v1 as execution
from . import full_git_model_workers_v1 as common


def run_gitlab_shared_base(study, usage_reconciler, *, full_git_binding_path: Path,
                           full_git_binding_file_sha256: str, cohort_freeze_path: Path,
                           sampler_factory=None):
    binding = common.validate_binding(common.private_json(full_git_binding_path, full_git_binding_file_sha256))
    cell = next(row for row in study.plan['cells'] if row['cell_id'] == 'gitlab')
    freeze = execution._verify_base_freeze(study, cell)

    def worker_factory():
        common.validate_binding(binding)
        worker = common.selection_worker(
            full_git_binding_path=full_git_binding_path,
            full_git_binding_file_sha256=full_git_binding_file_sha256,
            cohort_freeze_path=cohort_freeze_path, base_mode=True,
            expected_base_freeze_sha256=freeze['freeze_receipt_sha256'], enable_live=True)
        common.require(isinstance(worker.backend, common.FullGitBackend), 'full_git_shared_base_backend_required')
        return worker

    return execution.run_gitlab_shared_base(
        study, usage_reconciler, worker_factory=worker_factory, sampler_factory=sampler_factory)


__all__ = ['run_gitlab_shared_base']
