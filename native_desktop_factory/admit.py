"""Fail-closed, per-ID native-desktop task admission (no provider dispatch).

Input is a private 140-package inventory and private E2B receipts for each
final candidate.  Only real GUI positive, near-miss, saved-file readback and
fresh sandbox reset can admit a task.  A candidate count never becomes an
admitted count by manifest declaration alone.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

if __package__:
    from .factory import EXPECTED_COUNTS, json_bytes
    from .source import EXPECTED_SHA256
    from .verify import verify
else:
    from factory import EXPECTED_COUNTS, json_bytes
    from source import EXPECTED_SHA256
    from verify import verify


ATTEMPTS = ("positive", "near-miss", "cold-reset")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _package(candidate_root: Path, row: dict) -> tuple[Path, bytes, dict]:
    task_id = row["task_id"]
    directory = candidate_root / row["split"] / task_id
    manifest = json.loads((directory / "package.json").read_bytes())
    if manifest != row:
        raise ValueError("Candidate package receipt differs from inventory")
    without_digest = {key: value for key, value in row.items() if key != "package_sha256"}
    if digest(json_bytes(without_digest)) != row["package_sha256"]:
        raise ValueError("Candidate package digest changed")
    oracle_raw = (directory / "oracle.json").read_bytes()
    if digest(oracle_raw) != row["oracle_sha256"]:
        raise ValueError("Candidate oracle digest changed")
    oracle = json.loads(oracle_raw)
    files = list(directory.glob("*.xlsx")) + list(directory.glob("*.pptx")) + list(directory.glob("*.docx"))
    if len(files) != 1:
        raise ValueError("Expected one OOXML input")
    raw = files[0].read_bytes()
    if digest(raw) != row["input_sha256"] or digest(raw) != oracle["input_sha256"]:
        raise ValueError("Candidate input digest changed")
    if digest((directory / "actor_task.txt").read_bytes()) != row["actor_task_sha256"]:
        raise ValueError("Candidate actor instruction digest changed")
    if oracle["task_id"] != task_id or oracle["split"] != row["split"]:
        raise ValueError("Oracle identity mismatch")
    return directory, raw, oracle


def _receipt(root: Path, task_id: str, attempt: str, baseline_sha: str) -> tuple[dict, str]:
    path = root / task_id / attempt / "receipt.json"
    receipt_raw = path.read_bytes()
    receipt = json.loads(receipt_raw)
    if receipt.get("schema") != "cua-native-wdi-gui-development-attempt-v1" or receipt.get("task_id") != task_id:
        raise ValueError("GUI receipt schema/identity mismatch")
    if receipt.get("attempt") != attempt or receipt.get("input_sha256") != baseline_sha:
        raise ValueError("GUI receipt attempt/input mismatch")
    if receipt.get("kill_returned") is not True or receipt.get("is_running_after_kill") is not False:
        raise ValueError("GUI sandbox termination unverified")
    if not receipt.get("sandbox_id_sha256") or not receipt.get("runtime_probe"):
        raise ValueError("GUI sandbox/runtime identity missing")
    screens = receipt.get("screenshots", {})
    if not isinstance(screens, dict) or not screens:
        raise ValueError("No screenshot observation")
    for label, record in screens.items():
        screenshot = root / task_id / attempt / f"{label}.png"
        if not screenshot.is_file() or digest(screenshot.read_bytes()) != record.get("sha256"):
            raise ValueError("Screenshot bytes missing or changed")
    return receipt, digest(receipt_raw)


def admit_one(candidate_root: Path, attempts_root: Path, row: dict) -> dict:
    directory, baseline, oracle = _package(candidate_root, row)
    receipts = {name: _receipt(attempts_root, row["task_id"], name, digest(baseline)) for name in ATTEMPTS}
    records = {name: result[0] for name, result in receipts.items()}
    if len({records[name]["sandbox_id_sha256"] for name in ATTEMPTS}) != 3:
        raise ValueError("GUI attempts reused a sandbox")
    if len({records[name]["runtime_probe"] for name in ATTEMPTS}) != 1:
        raise ValueError("GUI attempts had different software versions")
    for attempt, expected in (("positive", True), ("near-miss", False)):
        receipt = records[attempt]
        saved_files = list((attempts_root / row["task_id"] / attempt).glob("saved.*"))
        if len(saved_files) != 1 or saved_files[0].suffix not in (".xlsx", ".pptx", ".docx"):
            raise ValueError("Saved actor artifact missing")
        raw = saved_files[0].read_bytes()
        if digest(raw) != receipt.get("saved_sha256") or digest(raw) == digest(baseline):
            raise ValueError("GUI edit was not saved before evaluation")
        result = verify(baseline, raw, oracle)
        if result != receipt.get("verifier") or result["passed"] is not expected:
            raise ValueError("Independent verifier disagrees with GUI receipt")
        if receipt["status"] != "control_passed":
            raise ValueError("GUI control did not pass its expected polarity")
        if not receipt.get("actor_actions"):
            raise ValueError("No visible actor actions recorded")
        if attempt == "near-miss":
            errors = result.get("errors", [])
            if not errors or not all(error.startswith("target_") for error in errors):
                raise ValueError("Near-miss changed collateral state or did not test target")
    cold = records["cold-reset"]
    if cold["status"] != "cold_reset_observed" or cold.get("restored_state_sha256") != digest(baseline):
        raise ValueError("Fresh desktop did not restore original artifact bytes")
    return {"task_id": row["task_id"], "package_sha256": row["package_sha256"],
            "source_groups": row["source_groups"], "runtime_probe": cold["runtime_probe"],
            "attempt_receipt_sha256": {key: receipts[key][1] for key in ATTEMPTS},
            "status": "development_controls_passed"}


def audit(candidate_root: Path, attempts_root: Path) -> dict:
    raw = (candidate_root / "candidate-inventory.json").read_bytes()
    inventory = json.loads(raw)
    if inventory.get("schema") != "cua-native-wdi-candidate-inventory-v1" or inventory.get("counts") != EXPECTED_COUNTS or inventory.get("source_sha256") != EXPECTED_SHA256:
        raise ValueError("Candidate inventory does not match frozen source/counts")
    rows = inventory["tasks"]
    if len(rows) != 140 or len({r["task_id"] for r in rows}) != 140:
        raise ValueError("Candidate task identity inventory changed")
    groups = {}
    for row in rows:
        for group in [("source", x) for x in row["source_groups"]] + [
            ("template", row["template_group"]), ("instance", row["instance_group"])
        ]:
            owner = groups.setdefault(group, row["split"])
            if owner != row["split"]:
                raise ValueError(f"{group[0]} group leaked across splits: {group[1]}")
    final = [row for row in rows if row["split"] == "final_candidate"]
    if len(final) != 100 or len({tuple(row["source_groups"]) for row in final}) != 25:
        raise ValueError("Final task/source-family shape changed")
    admitted, missing, invalid = [], [], []
    sandbox_ids = set()
    for row in final:
        directory = attempts_root / row["task_id"]
        if not directory.exists():
            missing.append(row["task_id"])
            continue
        try:
            evidence = admit_one(candidate_root, attempts_root, row)
            for attempt in ATTEMPTS:
                r, _ = _receipt(attempts_root, row["task_id"], attempt, row["input_sha256"])
                sid = r["sandbox_id_sha256"]
                if sid in sandbox_ids:
                    raise ValueError("Sandbox reused across final tasks")
                sandbox_ids.add(sid)
            admitted.append(evidence)
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            invalid.append({"task_id": row["task_id"], "error_type": type(exc).__name__,
                            "reason": str(exc)[:160]})
    return {"schema": "cua-native-wdi-admission-audit-v1",
            "candidate_inventory_sha256": digest(raw),
            "candidate_final_count": 100, "qualified_final_count": len(admitted),
            "missing_receipt_count": len(missing), "invalid_receipt_count": len(invalid),
            "status": "qualified" if len(admitted) == 100 else "incomplete",
            "admitted": admitted, "missing_task_ids": missing, "invalid": invalid}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--attempts-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    result = audit(args.candidate_root, args.attempts_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("candidate_final_count", "qualified_final_count", "missing_receipt_count", "invalid_receipt_count", "status")}, sort_keys=True))
    if args.require_complete and result["status"] != "qualified":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
