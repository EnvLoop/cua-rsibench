"""Read-only, Docker-free preflight for one train-only Odoo v9 attempt.

This does not reserve the shared Docker context or authorize a live launch.
The service-cold gate must be checked immediately before a root-owned run.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import stat

from tools import odoo_v066_scale_protocol_v1 as protocol
from tools import odoo_v066_train_attachment_calibration_v9 as run


SCHEMA = "envloop-odoo-v9-one-use-offline-preflight-v1"


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def digest(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(),
            "preflight_source_missing_or_symlinked")
    return sha256(path.read_bytes()).hexdigest()


def _lease_available(lock_path: Path) -> bool:
    require(lock_path.is_file() and not lock_path.is_symlink() and
            stat.S_IMODE(lock_path.stat().st_mode) & 0o077 == 0,
            "preflight_worker_lock_unsafe")
    descriptor = os.open(lock_path, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        return True
    finally:
        os.close(descriptor)


def audit(*, worker_dir: Path, accepted_audit_path: Path,
          private_freeze_path: Path, public_freeze_path: Path,
          v8_terminal_public_path: Path) -> dict:
    worker, private, freeze, case, wrong = run._verify_freeze(
        worker_dir, accepted_audit_path, private_freeze_path,
        public_freeze_path)
    public_freeze = json.loads(Path(public_freeze_path).read_bytes())
    require(public_freeze.get("schema") == run.FREEZE_SCHEMA and
            public_freeze.get("status") == run.PUBLIC_STATUS and
            public_freeze.get("private_freeze_sha256") ==
                digest(private_freeze_path) and
            public_freeze.get("run_nonce_sha256") ==
                sha256(freeze["run_nonce"].encode()).hexdigest() and
            len(public_freeze.get("source_files_sha256", {})) ==
                len(run.SOURCE_FILES) and
            all(digest(run.ROOT / relative) == expected for
                relative, expected in
                public_freeze["source_files_sha256"].items()) and
            case.get("partition") == wrong.get("partition") == "train" and
            case["id"] != wrong["id"] and
            public_freeze.get("selection_or_hidden_values_read") is False and
            public_freeze.get("selection_or_hidden_dispatch_authorized") is False and
            public_freeze.get("model_attempts") == 0 and
            public_freeze.get("official_final_tasks_admitted") == 0,
            "preflight_train_source_or_boundary_invalid")
    run_dir = private / "v066_attachment_route_calibration" / run.RUN_NAME
    require(not run_dir.exists() and not run_dir.is_symlink(),
            "preflight_one_use_run_id_already_consumed")
    terminal_path = Path(v8_terminal_public_path)
    require(terminal_path.parent.resolve() ==
            (run.ROOT / "docs/evidence").resolve(),
            "preflight_v8_receipt_path_invalid")
    terminal = json.loads(terminal_path.read_bytes())
    failure_path = (private / "v066_attachment_route_calibration" /
                    "attachment-route-train-pilot-20260929-06" /
                    "failure.private.json")
    failure = json.loads(failure_path.read_bytes())
    require(terminal.get("schema") ==
                "envloop-odoo-train-attachment-v8-terminal-audit-v1" and
            terminal.get("status") ==
                "train_only_price_dispatch_rejected_after_generic_parse" and
            terminal.get("private_failure_sha256") == digest(failure_path) and
            terminal.get("official_final_tasks_admitted") == 0 and
            terminal.get("model_attempts") == 0 and
            failure.get("status") == "terminal_failure_no_automatic_replay" and
            failure.get("reset_exact") is True and
            failure.get("services_restored") is True and
            failure.get("official_final_tasks_admitted") == 0,
            "preflight_v8_terminal_boundary_invalid")
    lease_available = _lease_available(private / "worker-operation.lock")
    require(lease_available, "preflight_train_worker_lease_busy")
    return {
        "schema": SCHEMA,
        "status": "offline_ready_shared_runtime_cold_gate_pending",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "public_freeze_sha256": digest(public_freeze_path),
        "private_freeze_sha256": digest(private_freeze_path),
        "v8_terminal_public_sha256": digest(terminal_path),
        "v8_private_failure_sha256": digest(failure_path),
        "source_files_verified": len(run.SOURCE_FILES),
        "positive_and_wrong_train_rfqs_distinct": True,
        "source_nonce_hash_bound": True,
        "new_one_use_run_directory_absent_at_check": True,
        "train_worker_lease_available_at_check": True,
        "shared_docker_context_released_verified": False,
        "train_worker_docker_services_cold_verified": False,
        "live_dispatch_ready": False,
        "selection_or_hidden_values_read": False,
        "model_attempts": 0,
        "official_final_tasks_admitted": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker-dir", type=Path, required=True)
    parser.add_argument("--accepted-audit", type=Path, required=True)
    parser.add_argument("--private-freeze", type=Path, required=True)
    parser.add_argument("--public-freeze", type=Path, required=True)
    parser.add_argument("--v8-terminal-public", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    result = audit(
        worker_dir=args.worker_dir,
        accepted_audit_path=args.accepted_audit,
        private_freeze_path=args.private_freeze,
        public_freeze_path=args.public_freeze,
        v8_terminal_public_path=args.v8_terminal_public)
    protocol.write_new(args.public_out, result, private=False)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
