"""Preview, preregister, inspect or run the separate Qwen real-GUI diagnostic.

Only `run` can contact Tinker. It requires three task-disjoint public-train
workflows, a source-bound exact private plan, an immutable public freeze and
the dedicated root-owned runtime. No command can open selection/final tasks.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys

from cursibench import qwen38_real_gui_diagnostic_v1 as diagnostic
from cursibench import qwen38_real_gui_diagnostic_run_v1 as paid
from cursibench import full_study_qwen_runtime_gate_v1 as runtime_gate
from cursibench.full_study_teacher_adapter_v1 import _load_renderer


ROOT = Path(__file__).resolve().parents[1]


def write_new(path: Path, raw: bytes, *, private: bool) -> None:
    target = Path(path).absolute()
    base = (ROOT / "work") if private else (ROOT / "docs/evidence")
    diagnostic.require(
        not target.exists() and not target.is_symlink() and
        target.parent.resolve().is_relative_to(base.resolve()) and
        not base.is_symlink(),
        "diagnostic_new_output_path_required")
    target.parent.mkdir(parents=True, mode=0o700 if private else 0o755,
                        exist_ok=True)
    if private:
        target.parent.chmod(0o700)
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                         0o600 if private else 0o644)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("preview", "prepare", "run"):
        command = sub.add_parser(name)
        command.add_argument("--sources", type=Path, required=True)
        command.add_argument("--ratification", type=Path, required=True)
        if name == "prepare":
            command.add_argument("--private-plan-out", type=Path,
                                 required=True)
            command.add_argument("--public-proposal-out", type=Path,
                                 required=True)
        elif name == "run":
            command.add_argument("--private-plan", type=Path, required=True)
            command.add_argument("--public-freeze-commit", required=True)
            command.add_argument("--run-dir", type=Path, required=True)
    status = sub.add_parser("status")
    status.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()
    try:
        if args.command == "status":
            result = paid.RunJournal.audit_existing(
                args.run_dir).snapshot()
        elif args.command == "preview":
            prereg, prereg_sha = diagnostic.load_prereg(root)
            episodes, manifest_sha, rat_sha = diagnostic.load_sources(
                root, args.sources, args.ratification)
            workflows = dict(sorted(Counter(
                row["workflow"] for row in episodes).items()))
            try:
                train, holdout = diagnostic.split_tasks(episodes, prereg)
                ready = True
                reason = None
            except diagnostic.DiagnosticError as exc:
                train, holdout, ready, reason = [], [], False, str(exc)
            result = {
                "status": "ready_for_offline_exact_plan" if ready else
                          "blocked_before_any_paid_call",
                "prereg_sha256": prereg_sha,
                "sources_manifest_sha256": manifest_sha,
                "ratification_sha256": rat_sha,
                "validated_train_source_tasks": len(episodes),
                "workflow_counts": workflows,
                "candidate_train_tasks": len(train),
                "candidate_holdout_tasks": len(holdout),
                "reason_code": reason,
                "provider_calls": 0,
                "benchmark_score": None,
            }
        elif args.command == "prepare":
            runtime_gate.assert_active_worker(root)
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            plan, proposal = diagnostic.prepare_plan(
                root, args.sources, args.ratification, _load_renderer)
            write_new(args.private_plan_out, diagnostic.canonical(plan),
                      private=True)
            write_new(args.public_proposal_out,
                      (json.dumps(proposal, indent=2, sort_keys=True) +
                       "\n").encode(), private=False)
            result = {"status": proposal["status"],
                      "plan_sha256": proposal["plan_sha256"],
                      "train_task_count": proposal["train_task_count"],
                      "holdout_task_count": proposal["holdout_task_count"],
                      "provider_calls": 0,
                      "benchmark_score": None}
        else:
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            result = paid.run(
                repo_root=root, manifest_path=args.sources,
                ratification_path=args.ratification,
                plan_path=args.private_plan,
                public_commit=args.public_freeze_commit,
                run_dir=args.run_dir,
                renderer_loader=_load_renderer)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:
        code = (str(exc) if isinstance(
            exc, (diagnostic.DiagnosticError, paid.RunError,
                  runtime_gate.RuntimeGateError)) else None)
        print(json.dumps({"status": "refused",
                          "reason_type": type(exc).__name__,
                          "reason_code": code},
                         sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
