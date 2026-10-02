"""Attribute saved read-only Tinker usage to a Qwen real-GUI diagnostic.

This never contacts Tinker. Provide the raw private get_billing_usage dump and
saved official models.json pricing bytes after the provider's hourly data has
arrived. Published-rate subtotals remain distinct from an invoice or credits.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from cursibench import qwen38_real_gui_diagnostic_v1 as diagnostic
from cursibench import qwen38_real_gui_diagnostic_run_v1 as runner
from cursibench import qwen38_real_gui_diagnostic_usage_v1 as usage


ROOT = Path(__file__).resolve().parents[1]


def private_bytes(path: Path, root: Path) -> bytes:
    target = Path(path)
    diagnostic.require(target.is_file() and not target.is_symlink() and
                       target.resolve().is_relative_to((root / "work").resolve())
                       and target.stat().st_mode & 0o077 == 0,
                       "diagnostic_usage_private_input_unsafe")
    return target.read_bytes()


def write_new(path: Path, raw: bytes, *, private: bool, root: Path) -> None:
    target = Path(path).absolute()
    base = (root / "work") if private else (root / "docs/evidence")
    diagnostic.require(not target.exists() and not target.is_symlink() and
                       target.parent.resolve().is_relative_to(base.resolve()),
                       "diagnostic_usage_output_not_new_or_rooted")
    target.parent.mkdir(parents=True, exist_ok=True,
                        mode=0o700 if private else 0o755)
    if private:
        target.parent.chmod(0o700)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                 0o600 if private else 0o644)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--usage", type=Path, required=True)
    parser.add_argument("--pricing", type=Path, required=True)
    parser.add_argument("--window-start", required=True)
    parser.add_argument("--window-end", required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.repo_root.resolve()
    try:
        journal = runner.RunJournal.audit_existing(args.run_dir)
        diagnostic.require(Path(args.run_dir).resolve().is_relative_to(
            (root / "work").resolve()),
            "diagnostic_usage_run_directory_outside_work")
        plan_sha = journal.header.get("plan_sha256")
        diagnostic.require(type(plan_sha) is str and
                           diagnostic.HASH.fullmatch(plan_sha) is not None,
                           "diagnostic_usage_run_plan_missing")
        result = usage.audit(
            usage_raw=private_bytes(args.usage, root),
            pricing_raw=private_bytes(args.pricing, root),
            plan_sha256=plan_sha,
            window_start=args.window_start,
            window_end=args.window_end)
        result["run_journal_sha256"] = diagnostic.digest(
            journal.path.read_bytes())
        result["run_journal_snapshot"] = journal.snapshot()
        result["provider_invoice_usd"] = None
        private_raw = diagnostic.canonical(result)
        write_new(args.private_out, private_raw, private=True, root=root)
        public = {**result,
                  "private_audit_sha256": diagnostic.digest(private_raw)}
        write_new(args.public_out,
                  (json.dumps(public, indent=2, sort_keys=True) + "\n").encode(),
                  private=False, root=root)
        print(json.dumps({
            "status": public["status"],
            "matched_provider_event_count":
                public["matched_provider_event_count"],
            "provider_invoice_usd": None,
        }, sort_keys=True))
        return 0
    except Exception as exc:
        code = (str(exc) if isinstance(
            exc, (diagnostic.DiagnosticError, runner.RunError,
                  usage.UsageError)) else None)
        print(json.dumps({"status": "refused",
                          "reason_type": type(exc).__name__,
                          "reason_code": code}, sort_keys=True),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
