"""Prove Odoo v0.6.5 official entry refuses absent six-cell freeze."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Refusing to overwrite official guard audit")
    hidden_gui_path = ROOT / "docs/evidence/odoo-official-hidden-100-gui-audit-2026-09-25.json"
    hidden_boundary_path = ROOT / "docs/evidence/odoo-hidden-final-boundary-2026-09-25.json"
    train_smoke_path = ROOT / "docs/evidence/odoo-qwen-v065-native-train-2026-09-27.json"
    gui = json.loads(hidden_gui_path.read_bytes())
    boundary = json.loads(hidden_boundary_path.read_bytes())
    train = json.loads(train_smoke_path.read_bytes())
    if (gui.get("candidate_cases") != 100 or gui.get("cases_with_all_per_id_controls") != 100
            or gui.get("official_final_tasks_admitted") != 0 or gui.get("model_attempts") != 0
            or boundary.get("candidate_counts") != {
                "train": 20, "selection": 20, "official_hidden": 100}
            or boundary.get("official_final_tasks_admitted") != 0
            or train.get("official_model_result_count") != 0
            or train.get("applied_gui_action_types") != ["click", "click"]):
        raise ValueError("Odoo candidate or train-only evidence changed")
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        missing = root / "missing-six-cell-freeze.json"
        output = root / "official-never-created"
        command = [sys.executable, "-m", "official_runner_v065",
                   "--freeze", str(missing), "--worker-dir", str(root / "not-a-worker"),
                   "--task-id", "synthetic-nonfinal", "--out-dir", str(output),
                   "--execute"]
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src") + ":" + str(ROOT / "enterprise_fallback/odoo18")
        result = subprocess.run(command, capture_output=True, text=True,
                                cwd=ROOT, env=env, timeout=30)
        try:
            blocked = json.loads(result.stdout)
        except (ValueError, TypeError):
            raise ValueError("Official guard did not return safe JSON") from None
        if (result.returncode != 2 or output.exists()
                or blocked != {
                    "status": "blocked_before_provider_or_model_dispatch",
                    "reason_code": "six_cell_freeze_missing", "provider_calls": 0,
                    "hidden_task_model_observations": 0,
                }):
            raise ValueError("Official guard did not fail before hidden/provider use")
    report = {
        "schema": "envloop-odoo-v065-official-dispatch-guard-public-v1",
        "checked_date": "2026-09-27",
        "scope": "Explicit --execute with an absent six-cell freeze, synthetic nonfinal task ID, nonexistent worker and output path; no hidden task, provider call, browser or official result.",
        "hidden_candidate_counts": boundary["candidate_counts"],
        "hidden_candidate_gui_controls_passed": gui["cases_with_all_per_id_controls"],
        "train_only_v065_applied_gui_actions": len(train["applied_gui_action_types"]),
        "official_entry_status": blocked["status"],
        "official_entry_reason_code": blocked["reason_code"],
        "provider_calls": 0,
        "hidden_task_model_observations": 0,
        "output_directory_created": False,
        "official_final_tasks_admitted": 0,
        "official_model_results": 0,
        "runner_sha256": digest((ROOT / "enterprise_fallback/odoo18/official_runner_v065.py").read_bytes()),
        "source_evidence_sha256s": {
            "hidden_gui": digest(hidden_gui_path.read_bytes()),
            "hidden_boundary": digest(hidden_boundary_path.read_bytes()),
            "train_v065_smoke": digest(train_smoke_path.read_bytes()),
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in (
        "official_entry_status", "official_entry_reason_code", "provider_calls",
        "official_model_results")}, sort_keys=True))


if __name__ == "__main__":
    main()
