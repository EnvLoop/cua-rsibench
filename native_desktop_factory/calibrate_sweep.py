"""Bounded, resumable per-ID E2B GUI calibration of private final candidates.

Known-positive/near-miss scripts operate only through the existing Desktop
mouse/keyboard shell. Trusted setup/evaluation remains in that shell. This is
NOT a model benchmark run and never promotes an official full-study score.
Existing failed or uncertain attempts are retained and never auto-replayed.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

if __package__:
    from . import admit
    from .factory import json_bytes
    from .verify import docx_content, pptx_slide_shapes, xlsx_cells
else:
    import admit
    from factory import json_bytes
    from verify import docx_content, pptx_slide_shapes, xlsx_cells


ATTEMPTS = ("positive", "near-miss", "cold-reset")
SHELL = Path(__file__).with_name("gui_control_shell.py")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _formula_for_calc(text: str) -> str:
    return text.replace("!", ".")


def actor_script(package_dir: Path, oracle: dict, attempt: str) -> str:
    if attempt == "cold-reset":
        return "stop\n"
    if attempt not in ("positive", "near-miss"):
        raise ValueError("Unknown GUI control polarity")
    workflow = oracle["workflow"]
    lines = ["wait 7", "press esc"]
    if workflow.startswith("calc-"):
        raw = next(package_dir.glob("*.xlsx")).read_bytes()
        before = xlsx_cells(raw)
        targets = list(oracle["targets"].items())
        if len(targets) != 3 or any(not addr.startswith("Decision ledger!") for addr, _ in targets):
            raise ValueError("Calc v2 must have three decision-ledger targets")
        lines += ["click 325,767"]  # Visible second sheet tab at 1280x800.
        for i, (address, rule) in enumerate(targets):
            cell = address.split("!", 1)[1]
            formula = rule["formula"]
            if attempt == "near-miss" and i == len(targets) - 1:
                formula = "=" + before["Decision ledger"][cell]["formula"].lstrip("=")
            lines += ["click 51,171", "press ctrl,a", f"write {cell}", "press enter",
                      f"write {_formula_for_calc(formula)}", "press enter"]
    elif workflow.startswith("impress-"):
        raw = next(package_dir.glob("*.pptx")).read_bytes()
        if oracle.get("target_slide") != 5:
            raise ValueError("Impress v2 expected three signals on slide 5")
        target_order = [text for text in pptx_slide_shapes(raw)[4] if text in oracle["targets"]]
        if len(target_order) != 3:
            raise ValueError("Impress target texts not found exactly three times")
        lines += ["click 81,557", "wait 2"]  # Wait for visible slide-five transition.
        for i, old in enumerate(target_order):
            replacement = oracle["targets"][old]
            if attempt == "near-miss" and i == 2:
                replacement = old
            lines += [f"double 430,{454 + i*50}", "press ctrl,a",
                      f"write {replacement}", "click 780,604"]
    elif workflow.startswith("writer-"):
        raw = next(package_dir.glob("*.docx")).read_bytes()
        old_paragraphs = docx_content(raw)["paragraphs"]
        target_order = [text for text in old_paragraphs if text in oracle["targets"]]
        if len(target_order) != 3:
            raise ValueError("Writer target paragraphs not found exactly three times")
        for i, old in enumerate(target_order):
            replacement = oracle["targets"][old]
            if attempt == "near-miss" and i == 2:
                replacement = old
            # Writer's native Find selects the full matching sentence across
            # page positions; Escape closes the bar while keeping selection.
            lines += ["press ctrl,f", f"write {old}", "press enter", "press esc",
                      f"write {replacement}"]
    else:
        raise ValueError("Unsupported final desktop workflow")
    lines += ["screen edited", "press ctrl,s", "wait 2", "click 789,519",
              "wait 3", "readback", "stop"]
    return "\n".join(lines) + "\n"


def validate_budget(*, lease_seconds: int, max_new_sandboxes: int,
                    max_estimated_usd: Decimal, usd_per_hour_upper: Decimal,
                    concurrency: int) -> Decimal:
    if not 120 <= lease_seconds <= 600:
        raise ValueError("Per-sandbox lease must be 120–600 seconds")
    if not 1 <= max_new_sandboxes <= 300 or not 1 <= concurrency <= 3:
        raise ValueError("Sandbox count/concurrency out of bound")
    if max_estimated_usd <= 0 or usd_per_hour_upper <= 0:
        raise ValueError("Positive cost ceilings required")
    if usd_per_hour_upper < Decimal("0.5328"):
        raise ValueError("USD/hour upper is below published 8-vCPU/8-GiB usage rate")
    reserve = Decimal(lease_seconds) * max_new_sandboxes / Decimal(3600) * usd_per_hour_upper
    if reserve > max_estimated_usd:
        raise ValueError("Worst-case E2B lease reserve exceeds USD ceiling")
    return reserve


def _attempt_state(path: Path, task_id: str, attempt: str, expected_sha: str) -> str:
    if not path.exists():
        return "missing"
    try:
        receipt = json.loads((path / "receipt.json").read_bytes())
        if receipt.get("task_id") != task_id or receipt.get("attempt") != attempt or receipt.get("input_sha256") != expected_sha:
            return "invalid_existing"
        if receipt.get("status") in ("control_passed", "cold_reset_observed") and receipt.get("is_running_after_kill") is False:
            return "apparently_complete"
        return "failed_or_uncertain_existing"
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return "failed_or_uncertain_existing"


def plan(candidate_root: Path, attempts_root: Path, *, max_tasks: int,
         max_new_sandboxes: int,
         only_task_ids: set[str] | None = None) -> tuple[list[dict], list[dict]]:
    inventory = json.loads((candidate_root / "candidate-inventory.json").read_bytes())
    if inventory.get("design_revision") != "v2-distinct-structures":
        raise ValueError("Expected distinct-template WDI candidate inventory")
    rows = [r for r in inventory["tasks"] if r["split"] == "final_candidate"]
    if only_task_ids is not None:
        available = {r["task_id"] for r in rows}
        if not only_task_ids or not only_task_ids <= available:
            raise ValueError("Requested task ID is absent from the private final inventory")
        rows = [r for r in rows if r["task_id"] in only_task_ids]
    rows.sort(key=lambda row: (row["source_groups"], row["workflow"]))
    selected, deferred = [], []
    reserved = 0
    for row in rows:
        if len(selected) >= max_tasks:
            deferred.append({"task_id": row["task_id"], "reason": "task_cap"})
            continue
        task_id = row["task_id"]
        try:
            _, baseline, oracle = admit._package(candidate_root, row)
            if row["workflow"] == "impress-deck" and "normalization" not in row:
                raise ValueError("final_impress_not_neutrally_normalized")
            if oracle.get("design_revision") != "v2-distinct-structures":
                raise ValueError("wrong_oracle_design_revision")
            states = {name: _attempt_state(attempts_root / task_id / name,
                                           task_id, name, digest(baseline))
                      for name in ATTEMPTS}
            if any(value in ("invalid_existing", "failed_or_uncertain_existing") for value in states.values()):
                deferred.append({"task_id": task_id, "reason": "existing_attempt_failed_or_uncertain",
                                 "attempt_states": states})
                continue
            if all(value == "apparently_complete" for value in states.values()):
                try:
                    admit.admit_one(candidate_root, attempts_root, row)
                    deferred.append({"task_id": task_id, "reason": "already_gui_calibrated"})
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    deferred.append({"task_id": task_id, "reason": "existing_complete_audit_failed",
                                     "error_type": type(exc).__name__})
                continue
            needed = [name for name in ATTEMPTS if states[name] == "missing"]
            if reserved + len(needed) > max_new_sandboxes:
                deferred.append({"task_id": task_id, "reason": "sandbox_cap"})
                continue
            selected.append({"row": row, "needed": needed})
            reserved += len(needed)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            deferred.append({"task_id": task_id, "reason": "candidate_preflight_failed",
                             "error_type": type(exc).__name__, "detail": str(exc)[:100]})
    return selected, deferred


def _run_attempt(candidate_root: Path, attempts_root: Path, row: dict,
                 attempt: str, lease_seconds: int, *, dry_run: bool,
                 expected_template_id: str | None = None) -> dict:
    task_id = row["task_id"]
    package_dir = candidate_root / "final_candidate" / task_id
    oracle = json.loads((package_dir / "oracle.json").read_bytes())
    script = actor_script(package_dir, oracle, attempt)
    destination = attempts_root / task_id / attempt
    if destination.exists():
        raise ValueError("Refusing to overwrite an existing GUI attempt")
    if dry_run:
        return {"attempt": attempt, "status": "dry_run", "script_sha256": digest(script.encode())}
    cmd = [sys.executable, str(SHELL), "--package", str(package_dir),
           "--out", str(destination), "--attempt", attempt,
           "--candidate-calibration", "--sandbox-timeout-seconds", str(lease_seconds)]
    if expected_template_id:
        cmd += ["--expected-template-id", expected_template_id]
    start = time.monotonic()
    try:
        result = subprocess.run(cmd, input=script, text=True, capture_output=True,
                                timeout=lease_seconds + 60, check=False)
        status = "passed" if result.returncode == 0 else "failed"
        receipt_path = destination / "receipt.json"
        child_receipt = json.loads(receipt_path.read_bytes()) if receipt_path.is_file() else {}
        return {"attempt": attempt, "status": status, "exit_code": result.returncode,
                "child_error_type": child_receipt.get("error_type"),
                "sandbox_id_observed": bool(child_receipt.get("sandbox_id_sha256")),
                "script_sha256": digest(script.encode()),
                "stdout_sha256": digest(result.stdout.encode()),
                "stderr_sha256": digest(result.stderr.encode()),
                "elapsed_seconds": round(time.monotonic() - start, 3),
                "receipt_exists": (destination / "receipt.json").is_file()}
    except subprocess.TimeoutExpired:
        # The E2B server-side lease still bounds this uncertain sandbox.
        return {"attempt": attempt, "status": "timeout_uncertain",
                "script_sha256": digest(script.encode()),
                "elapsed_seconds": round(time.monotonic() - start, 3),
                "receipt_exists": (destination / "receipt.json").is_file()}


def _run_task(candidate_root: Path, attempts_root: Path, item: dict,
              lease_seconds: int, *, dry_run: bool,
              expected_template_id: str | None = None) -> dict:
    row = item["row"]
    result = {"task_id": row["task_id"], "workflow": row["workflow"],
              "source_groups": row["source_groups"], "attempts": []}
    for attempt in item["needed"]:
        outcome = _run_attempt(candidate_root, attempts_root, row, attempt,
                               lease_seconds, dry_run=dry_run,
                               expected_template_id=expected_template_id)
        result["attempts"].append(outcome)
        if outcome["status"] not in ("passed", "dry_run"):
            result["status"] = "stopped_after_failed_or_uncertain_attempt"
            break
    else:
        if not dry_run:
            try:
                admit.admit_one(candidate_root, attempts_root, row)
                result["status"] = "gui_controls_passed"
            except (OSError, ValueError, KeyError, TypeError) as exc:
                result["status"] = "post_attempt_audit_failed"
                result["audit_error_type"] = type(exc).__name__
                result["audit_reason"] = str(exc)[:160]
        else:
            result["status"] = "dry_run"
    return result


def execute(candidate_root: Path, attempts_root: Path, output_dir: Path,
            *, max_tasks: int, max_new_sandboxes: int, lease_seconds: int,
            max_estimated_usd: Decimal, usd_per_hour_upper: Decimal,
            concurrency: int, max_wall_seconds: int, dry_run: bool,
            max_infrastructure_create_errors: int = 3,
            health_probe: Path | None = None,
            only_task_ids: set[str] | None = None) -> dict:
    if output_dir.exists():
        raise ValueError("Refusing to overwrite sweep run directory")
    if not 1 <= max_tasks <= 100 or not 60 <= max_wall_seconds <= 43200:
        raise ValueError("Invalid task/wall cap")
    if not 1 <= max_infrastructure_create_errors <= 10:
        raise ValueError("Invalid infrastructure circuit-breaker threshold")
    if not dry_run and not os.environ.get("E2B_API_KEY"):
        raise ValueError("E2B_API_KEY missing")
    expected_template_id = None
    health_probe_sha = None
    if health_probe is not None:
        health_raw = health_probe.read_bytes()
        health = json.loads(health_raw)
        if health.get("ready_to_resume_paid_gui_dispatch") is not True:
            raise ValueError("Provided E2B health probe is not healthy")
        expected_template_id = health["provider_sandbox_info"]["template_id"]
        health_probe_sha = digest(health_raw)
    reserve = validate_budget(lease_seconds=lease_seconds,
                              max_new_sandboxes=max_new_sandboxes,
                              max_estimated_usd=max_estimated_usd,
                              usd_per_hour_upper=usd_per_hour_upper,
                              concurrency=concurrency)
    selected, deferred = plan(candidate_root, attempts_root, max_tasks=max_tasks,
                              max_new_sandboxes=max_new_sandboxes,
                              only_task_ids=only_task_ids)
    output_dir.mkdir(parents=True)
    receipt = {"schema": "cua-native-wdi-final-gui-sweep-v1",
               "status": "started", "dry_run": dry_run,
               "candidate_inventory_sha256": digest((candidate_root / "candidate-inventory.json").read_bytes()),
               "health_probe_sha256": health_probe_sha,
               "expected_template_id": expected_template_id,
               "sdk_version": importlib.metadata.version("e2b-desktop") if not dry_run else None,
               "caps": {"max_tasks": max_tasks, "max_new_sandboxes": max_new_sandboxes,
                        "lease_seconds": lease_seconds, "max_concurrency": concurrency,
                        "max_wall_seconds": max_wall_seconds,
                        "max_infrastructure_create_errors": max_infrastructure_create_errors,
                        "max_estimated_usd": str(max_estimated_usd),
                        "usd_per_hour_upper": str(usd_per_hour_upper),
                        "full_reserved_usd_upper": str(reserve)},
               "planned_task_count": len(selected),
               "planned_new_sandboxes": sum(len(x["needed"]) for x in selected),
               "deferred": deferred, "results": []}
    journal_path = output_dir / "run-receipt.json"
    lock = threading.Lock()

    def persist() -> None:
        temporary = journal_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        temporary.replace(journal_path)

    persist()
    started = time.monotonic()
    circuit_open = False
    infrastructure_create_errors = 0
    try:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            pending = {}
            iterator = iter(selected)
            while True:
                while (not circuit_open and len(pending) < concurrency and
                       time.monotonic() - started < max_wall_seconds):
                    try:
                        item = next(iterator)
                    except StopIteration:
                        break
                    future = pool.submit(_run_task, candidate_root, attempts_root,
                                         item, lease_seconds, dry_run=dry_run,
                                         expected_template_id=expected_template_id)
                    pending[future] = item["row"]["task_id"]
                if not pending:
                    break
                completed = next(as_completed(pending))
                task_id = pending.pop(completed)
                try:
                    outcome = completed.result()
                except Exception as exc:
                    outcome = {"task_id": task_id, "status": "runner_exception",
                               "error_type": type(exc).__name__, "reason": str(exc)[:160]}
                with lock:
                    receipt["results"].append(outcome)
                    for attempt in outcome.get("attempts", []):
                        if (attempt.get("child_error_type") == "ConnectError" and
                                attempt.get("status") == "failed"):
                            infrastructure_create_errors += 1
                    if infrastructure_create_errors >= max_infrastructure_create_errors:
                        circuit_open = True
                        receipt["circuit_breaker"] = {
                            "reason": "E2B_ConnectError_threshold",
                            "infrastructure_create_error_count": infrastructure_create_errors,
                            "threshold": max_infrastructure_create_errors,
                            "no_new_tasks_dispatched": True,
                        }
                    persist()
            unstarted = list(iterator)
            receipt["unstarted_due_wall_or_completion"] = len(unstarted)
            if circuit_open:
                receipt["unstarted_due_circuit_breaker"] = len(unstarted)
        if not dry_run:
            audit = admit.audit(candidate_root, attempts_root)
            receipt["post_run_gui_audit"] = {key: audit[key] for key in
                                            ("candidate_final_count", "qualified_final_count",
                                             "missing_receipt_count", "invalid_receipt_count", "status")}
            receipt["status"] = ("infrastructure_circuit_open" if circuit_open else
                                 "finished_incomplete" if audit["status"] != "qualified" else
                                 "gui_gate_complete")
        else:
            receipt["status"] = "dry_run_complete"
    finally:
        receipt["elapsed_seconds"] = round(time.monotonic() - started, 3)
        receipt["actual_started_attempts"] = sum(len(x.get("attempts", [])) for x in receipt["results"])
        receipt["actual_reserve_usd_upper"] = str(Decimal(receipt["actual_started_attempts"])
                                                   * Decimal(lease_seconds) / Decimal(3600)
                                                   * usd_per_hour_upper)
        persist()
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--attempts-root", type=Path, required=True)
    parser.add_argument("--run-output", type=Path, required=True)
    parser.add_argument("--max-tasks", type=int, default=10)
    parser.add_argument("--max-new-sandboxes", type=int, default=30)
    parser.add_argument("--lease-seconds", type=int, default=300)
    parser.add_argument("--max-estimated-usd", type=Decimal, default=Decimal("3.00"))
    parser.add_argument("--usd-per-hour-upper", type=Decimal, default=Decimal("1.00"))
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--max-wall-seconds", type=int, default=3600)
    parser.add_argument("--max-infrastructure-create-errors", type=int, default=3)
    parser.add_argument("--execute", action="store_true", help="Dispatch bounded E2B GUI attempts")
    parser.add_argument("--health-probe", type=Path,
                        help="Bind a separately verified Desktop recovery probe and template identity")
    parser.add_argument("--task-id", action="append", default=[],
                        help="Private final task ID to calibrate; repeat to select several")
    args = parser.parse_args()
    result = execute(args.candidate_root, args.attempts_root, args.run_output,
                     max_tasks=args.max_tasks, max_new_sandboxes=args.max_new_sandboxes,
                     lease_seconds=args.lease_seconds,
                     max_estimated_usd=args.max_estimated_usd,
                     usd_per_hour_upper=args.usd_per_hour_upper,
                     concurrency=args.concurrency,
                     max_wall_seconds=args.max_wall_seconds, dry_run=not args.execute,
                     max_infrastructure_create_errors=args.max_infrastructure_create_errors,
                     health_probe=args.health_probe,
                     only_task_ids=set(args.task_id) if args.task_id else None)
    print(json.dumps({"status": result["status"],
                      "planned_tasks": result["planned_task_count"],
                      "started_attempts": result["actual_started_attempts"],
                      "gui_control_passed_tasks": sum(x.get("status") == "gui_controls_passed" for x in result["results"]),
                      "post_run_gui_audit": result.get("post_run_gui_audit")}, sort_keys=True))


if __name__ == "__main__":
    main()
