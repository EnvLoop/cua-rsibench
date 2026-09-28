"""Publish aggregate-only proof of Odoo private-mode repair and re-audit."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import stat

from tools import harden_odoo_private_evidence_v1 as harden


SCHEMA = "envloop-odoo-private-evidence-hardening-public-v1"


def _private_json(path: Path) -> dict:
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or
            stat.S_IMODE(info.st_mode) != 0o600 or
            path.parent.is_symlink() or
            stat.S_IMODE(path.parent.stat().st_mode) & 0o077):
        raise ValueError("private_hardening_receipt_mode_invalid")
    value = json.loads(path.read_bytes())
    if type(value) is not dict:
        raise ValueError("private_hardening_receipt_invalid")
    return value


def build(*, workers_root: Path, before_path: Path, after_path: Path,
          owner_path: Path, post_audit_path: Path) -> dict:
    root = Path(workers_root).resolve()
    before = _private_json(before_path)
    after = _private_json(after_path)
    owner = _private_json(owner_path)
    post = json.loads(post_audit_path.read_bytes())
    before_sha = harden.sha256_file(before_path)
    after_sha = harden.sha256_file(after_path)
    owner_sha = harden.sha256_file(owner_path)
    post_sha = harden.sha256_file(post_audit_path)
    rows = before.get("affected_paths")
    expected = {
        "train": {"directories": 8, "files": 23},
        "selection": {"directories": 3, "files": 8},
        "official_hidden": {"directories": 4, "files": 8},
    }
    if (before.get("schema") != harden.SCHEMA or
            before.get("phase") != "snapshot_before_first_chmod" or
            before.get("three_worker_leases_held_idle") is not True or
            before.get("compose_sha256") != harden.APPROVED_COMPOSE_SHA256 or
            before.get("affected_by_split") != expected or
            type(rows) is not list or len(rows) != 54 or
            after.get("schema") != harden.SCHEMA or
            after.get("phase") != "verified_after_chmod" or
            after.get("before_journal_sha256") != before_sha or
            after.get("affected_by_split") != expected or
            after.get("affected_paths_verified_byte_identical") != 54 or
            after.get("remaining_permissive_modes") !=
            {"directories": 0, "files": 0} or
            after.get("three_worker_leases_held_idle_through_verification") is not True):
        raise ValueError("hardening_journal_inconsistent")
    types = Counter(row.get("kind") for row in rows)
    if types != {"directory": 15, "file": 39}:
        raise ValueError("hardening_path_types_inconsistent")
    for row in rows:
        relative = Path(row["relative_path"])
        if (relative.is_absolute() or ".." in relative.parts or
                not (root / relative).resolve().is_relative_to(root)):
            raise ValueError("hardening_journal_path_unsafe")
        harden._check_same(root / relative, root, row, after=True)
    if (owner.get("schema") != "envloop-odoo-owner-read-worker-preflight-v1" or
            owner.get("status") != "owner_only_and_worker_python_read_preflight_passed" or
            set(owner.get("by_split", {})) != set(harden.SPLITS) or
            not all(owner["by_split"][split]["task_manifest_official_identity_count"] == 100
                    and owner["by_split"][split]["files_owner_read"] > 0
                    for split in harden.SPLITS) or
            owner.get("docker_calls") != 0 or owner.get("provider_calls") != 0 or
            post.get("schema") != "envloop-odoo-offline-candidate-evidence-audit-v1" or
            post.get("status") != "historical_evaluator_controls_reverified_offline" or
            post.get("historical_candidate_counts") !=
            {"train": 20, "selection": 20, "official_hidden": 100} or
            post.get("historical_source_assets_and_packages_rebuilt") != 140 or
            post.get("historical_gui_positive_wrong_object_reset_receipts_reverified") != 140 or
            post.get("private_evidence_owner_only_permissions") is not True or
            post.get("permission_violations_by_category") != {} or
            post.get("pre_campaign_admission_eligible") is not False or
            post.get("official_final_tasks_admitted") != 0 or
            post.get("model_attempts") != 0):
        raise ValueError("post_hardening_audit_or_worker_preflight_inconsistent")
    code_dir = Path(__file__).resolve().parent
    return {
        "schema": SCHEMA,
        "status": "private_modes_hardened_historical_controls_reverified",
        "before_permissive_modes_by_split": expected,
        "after_permissive_modes": {"directories": 0, "files": 0},
        "affected_paths_with_preserved_size_inode_and_sha256": 54,
        "historical_candidate_controls_reverified": 140,
        "owner_worker_file_read_preflight": "passed",
        "compose_private_bind_mount": False,
        "before_private_journal_sha256": before_sha,
        "after_private_journal_sha256": after_sha,
        "owner_read_private_receipt_sha256": owner_sha,
        "post_hardening_offline_audit_sha256": post_sha,
        "post_hardening_private_per_id_report_sha256":
            post["private_per_id_report_sha256"],
        "hardening_tool_sha256": harden.sha256_file(code_dir / "harden_odoo_private_evidence_v1.py"),
        "owner_read_tool_sha256": harden.sha256_file(code_dir / "audit_odoo_owner_read_v1.py"),
        "publisher_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "live_v066_model_attempt_retested": False,
        "pre_campaign_admission_eligible": False,
        "official_final_tasks_admitted": 0,
        "researcher_campaigns": 0,
        "model_attempts": 0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers-root", type=Path, required=True)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--owner-read", type=Path, required=True)
    parser.add_argument("--post-audit", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    result = build(workers_root=args.workers_root, before_path=args.before,
                   after_path=args.after, owner_path=args.owner_read,
                   post_audit_path=args.post_audit)
    raw = (json.dumps(result, sort_keys=True, indent=2) + "\n").encode()
    fd = os.open(args.public_out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    print(json.dumps(result, sort_keys=True))
