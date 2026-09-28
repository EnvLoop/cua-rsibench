"""Future-only wrapper that gates the frozen controller on cross-root spend.

No paid call occurs by importing this module. The evaluator must explicitly
enable a new full-100 run after reviewing the dated source amendment.
"""

from __future__ import annotations

from pathlib import Path

from .v066_caret_full100_preflight import preflight_fresh_full100
from .v066_final_rerun_controller import execute as frozen_execute


def execute_amended_full100(*, candidate_root: Path,
                            original_root: Path,
                            fresh_root: Path,
                            old_run_journal: Path,
                            old_ratification: Path,
                            old_reservation: Path,
                            new_ratification: Path,
                            new_reservation: Path,
                            bridge_path: Path,
                            private_map: Path,
                            profile_private: Path,
                            guest_public: Path,
                            fair_public: Path,
                            run_dir: Path,
                            concurrency: int,
                            enable_paid_control_run: bool = False) -> dict:
    if enable_paid_control_run is not True:
        raise ValueError("Amended paid full100 control run is disabled")
    preflight = preflight_fresh_full100(
        candidate_root=candidate_root,
        original_root=original_root, fresh_root=fresh_root,
        old_run_journal=old_run_journal,
        old_ratification=old_ratification,
        old_reservation=old_reservation,
        new_ratification=new_ratification,
        new_reservation=new_reservation,
        bridge_path=bridge_path,
        profile_private=profile_private,
        guest_public=guest_public,
        fair_public=fair_public)
    if preflight["combined_budget"]["combined_full_lease_intents"] != 322:
        raise ValueError("Cross-root full100 reservation changed")
    return frozen_execute(
        candidate_root=candidate_root,
        attempts_root=fresh_root,
        private_map=private_map,
        profile_private=profile_private,
        guest_public=guest_public,
        fair_public=fair_public,
        ratification=new_ratification,
        reservation=new_reservation,
        run_dir=run_dir,
        task_cap=100,
        concurrency=concurrency)
