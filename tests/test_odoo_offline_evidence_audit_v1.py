"""Synthetic, read-only 140-ID Odoo historical evidence audit tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest

ODDO_DIR = Path(__file__).resolve().parents[1] / "enterprise_fallback/odoo18"
sys.path.insert(0, str(ODDO_DIR))
import offline_evidence_audit_v1 as offline  # noqa: E402


def encode(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def put(path: Path, value: object, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encode(value) if not isinstance(value, bytes) else value)
    path.chmod(mode)


def asset(case: dict, _world: dict) -> bytes:
    return ("synthetic-source:" + case["id"]).encode()


class OdooOfflineEvidenceAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.workers = root / "workers"
        self.public = root / "public"
        self.public.mkdir()
        self.manifest = {"train": [], "selection": [], "official": []}
        self.worlds = {}
        self.sources = {}
        for split, (name, per_family) in offline.SPLITS.items():
            cases = {}
            sources = {}
            for family in offline.FAMILIES:
                rows = []
                for index in range(per_family):
                    case_id = f"T-{split}-{family}-{index:03}"
                    case = {"id": case_id, "family": family, "partition": split,
                            "template_group": f"template-{split}-{family}",
                            "instance_group": f"instance-{split}-{family}-{index}"}
                    source_sha = sha256(asset(case, {})).hexdigest()
                    package_sha = sha256(json.dumps(case, sort_keys=True).encode() +
                                         b"\n" + asset(case, {})).hexdigest()
                    self.manifest[name].append({
                        "task_id": case_id, "package_sha256": package_sha,
                        "source_groups": ["odoo-source-" + source_sha],
                        "template_group": case["template_group"],
                        "instance_group": case["instance_group"]})
                    rows.append(case)
                    sources[case_id] = source_sha
                cases[family] = rows
            self.worlds[split] = {"split": split, "cases": cases}
            self.sources[split] = sources
        self.manifest_sha = offline.canonical_digest(self.manifest)
        self.pinned_code = {name: offline.file_digest(offline.CODE_DIR / name)
                            for name in ("bootstrap.py", "create_partition_worlds.py",
                                         "partition_factory.py", "verify.py", "reset.py",
                                         "gui_controls.py", "sweep_partition.py",
                                         "worker_lease.py", "audit_partition_receipts.py",
                                         "record_train_trace.py", "hidden_factory.py",
                                         "compose.yaml")}
        boundary_private = {
            "task_set_manifest_sha256": self.manifest_sha,
            "pinned_code_and_runtime_sha256": self.pinned_code,
            "official_final_tasks_admitted": 0,
        }
        final_private = self.workers / "official_hidden" / "private"
        final_private.mkdir(parents=True, mode=0o700)
        put(final_private / "hidden_boundary_audit.json", boundary_private)
        public_boundary = {
            "schema": "envloop-odoo-hidden-boundary-public-v1",
            "official_final_tasks_admitted": 0,
            "source_entity_instance_overlap_with_any_compared_pool": 0,
            "causal_template_overlap_with_exposed_development": 0,
            "qa_prompts_gold_and_sources_researcher_exposed": False,
            "task_set_manifest_sha256": self.manifest_sha,
            "private_boundary_audit_sha256":
                offline.file_digest(final_private / "hidden_boundary_audit.json"),
        }
        put(self.public / offline.BOUNDARY_FILE, public_boundary)
        self.gui_audits = {}
        for split, (name, per_family) in offline.SPLITS.items():
            p = self.workers / split / "private"
            p.mkdir(parents=True, exist_ok=True)
            p.chmod(0o700)
            for directory in (p / "admission_runs", p / "admission_runs" / "runA"):
                directory.mkdir(mode=0o700)
            world = self.worlds[split]
            sources = self.sources[split]
            db = b"db:" + split.encode()
            filestore = b"filestore:" + split.encode()
            snapshot = b"{}"
            put(p / "baseline.pgcustom", db)
            put(p / "baseline-filestore.tgz", filestore)
            put(p / "baseline_snapshot.json", snapshot)
            checkpoint = {"db_sha256": sha256(db).hexdigest(),
                          "filestore_sha256": sha256(filestore).hexdigest()}
            put(p / "checkpoint_receipt.json", checkpoint)
            put(p / "partition_cases.json", world)
            put(p / "source_hashes.json", sources)
            put(p / "task_set_manifest.json", self.manifest)
            receipt = {
                "partition": split, "official_final_tasks_admitted": 0,
                "case_manifest_sha256": offline.canonical_digest(world),
                "source_hash_manifest_sha256": offline.canonical_digest(sources),
                "task_set_manifest_sha256": self.manifest_sha,
                "pinned_code_and_runtime_sha256": self.pinned_code,
            }
            put(p / "partition_receipt.json", receipt)
            all_cases = [case for family in offline.FAMILIES
                         for case in world["cases"][family]]
            packages = {row["task_id"]: row for row in self.manifest[name]}
            started = datetime(2026, 9, 25, tzinfo=timezone.utc)
            rows = []
            for index, case in enumerate(all_cases):
                row = {
                    "case_id": case["id"], "family": case["family"],
                    "task_package_sha256": packages[case["id"]]["package_sha256"],
                    "baseline_snapshot_sha256": sha256(snapshot).hexdigest(),
                    "status": "candidate_environment_gui_qualified",
                    "official_final_task": False,
                    "exclusive_worker_lease_held": True,
                    "cold_reset_before": True, "cold_reset_after": True,
                    "source_visible_in_native_gui": True,
                    "baseline_reward": 0.0, "gui_oracle_reward": 1.0,
                    "positive_difference_codes": [],
                    "wrong_object_reward": 0.0,
                    "wrong_object_difference_codes":
                        [offline.NEGATIVE_CODES[case["family"]]],
                    "after_reset_reward": 0.0,
                    "protected_source_files_checked": 3 * per_family + 1,
                    "worker_pid": 4321,
                    "started_at_utc": (started + timedelta(seconds=2 * index)).isoformat(),
                    "finished_at_utc":
                        (started + timedelta(seconds=2 * index + 1)).isoformat(),
                }
                rows.append(row)
                put(p / "admission_runs" / "runA" / f"{case['id']}.json", row)
            put(p / "admission_runs" / "runA" / "summary.json", {
                "run_id": "runA", "partition": split,
                "attempted_this_run": len(rows), "qualified_this_run": len(rows),
                "official_final_tasks_admitted": 0, "cases": rows,
            })
            events = [
                {"event": "acquired", "operation": "sweep_partition", "pid": 4321,
                 "at_utc": (started - timedelta(seconds=1)).isoformat()},
                {"event": "released", "operation": "sweep_partition", "pid": 4321,
                 "at_utc": (started + timedelta(seconds=2 * len(rows))).isoformat()},
            ]
            put(p / "worker-lease-events.jsonl",
                ("\n".join(json.dumps(row) for row in events) + "\n").encode())
            audit = {
                "partition": split, "schema": "envloop-odoo-partition-candidate-gui-audit-v1",
                "status": "candidate_environment_qualified",
                "official_final_tasks_admitted": 0, "model_attempts": 0,
                "world_case_manifest_sha256": receipt["case_manifest_sha256"],
                "world_source_hash_manifest_sha256": receipt["source_hash_manifest_sha256"],
                "task_set_manifest_sha256": self.manifest_sha,
                "pinned_code_and_runtime_sha256": self.pinned_code,
                "db_checkpoint_sha256": checkpoint["db_sha256"],
                "filestore_checkpoint_sha256": checkpoint["filestore_sha256"],
                "run_id": "runA", "candidate_cases": len(rows),
                "cases_with_all_per_id_controls": len(rows),
                "all_sources_visible_in_native_gui": True,
                "final_database_and_physical_filestore_reset_exact": True,
                "actor_role_scoped_no_admin_group": True,
                "evaluator_select_only_on_scored_tables": True,
                "exclusive_worker_lease_interval_verified": True,
                "protected_attachment_files_per_attempt": 3 * per_family + 1,
                "per_family_qualified": {family: per_family for family in offline.FAMILIES},
            }
            self.gui_audits[split] = audit
            put(self.public / offline.AUDIT_FILES[split], audit)
        aggregate = {
            "schema": "envloop-odoo-hidden-study-environment-aggregate-v1",
            "candidate_counts": {"train": 20, "selection": 20,
                                 "official_hidden": 100},
            "official_final_tasks_admitted": 0,
            "completed_official_model_attempts": 0,
            "common_task_set_manifest_sha256": self.manifest_sha,
            "source_entity_instance_overlap_with_exposed_development": 0,
            "causal_template_overlap_with_exposed_development": 0,
            "evidence_sha256": {
                **{("hidden_gui" if split == "official_hidden" else
                    f"{split}_gui"): offline.file_digest(
                        self.public / offline.AUDIT_FILES[split])
                   for split in offline.SPLITS},
                "hidden_boundary": offline.file_digest(
                    self.public / offline.BOUNDARY_FILE),
            },
        }
        put(self.public / offline.AGGREGATE_FILE, aggregate)

    def run_audit(self):
        return offline.audit(self.workers, self.public, asset_builder=asset)

    def test_rebuilds_all_140_and_keeps_official_closed(self):
        private, public = self.run_audit()
        self.assertEqual(public["historical_source_assets_and_packages_rebuilt"], 140)
        self.assertEqual(public["historical_gui_positive_wrong_object_reset_receipts_reverified"], 140)
        self.assertEqual(len(private["per_id"]["official_hidden"]), 100)
        self.assertTrue(public["private_evidence_owner_only_permissions"])
        self.assertFalse(public["pre_campaign_admission_eligible"])
        self.assertEqual(public["official_final_tasks_admitted"], 0)
        self.assertNotIn("per_id", public)

    def test_permissive_private_directory_fails_closed(self):
        (self.workers / "official_hidden" / "private").chmod(0o755)
        _, public = self.run_audit()
        self.assertEqual(public["status"],
                         "historical_evaluator_controls_reverified_privacy_hardening_pending")
        self.assertFalse(public["private_evidence_owner_only_permissions"])
        self.assertFalse(public["pre_campaign_admission_eligible"])
        self.assertEqual(public["permission_violations_by_category"]["directories"], 1)

    def test_changed_per_id_gui_receipt_rejected(self):
        path = next((self.workers / "official_hidden" / "private" /
                     "admission_runs" / "runA").glob("T-*.json"))
        row = json.loads(path.read_text())
        row["wrong_object_reward"] = 1.0
        put(path, row)
        with self.assertRaisesRegex(offline.EvidenceError,
                                    "per_id_gui_control_invalid"):
            self.run_audit()

    def test_public_receipt_hash_or_worker_overlap_rejected(self):
        public_audit = self.public / offline.AUDIT_FILES["train"]
        original = public_audit.read_bytes()
        put(public_audit, {**self.gui_audits["train"], "model_attempts": 1})
        with self.assertRaisesRegex(offline.EvidenceError,
                                    "public_gui_receipt_hash_changed"):
            self.run_audit()
        put(public_audit, original)
        lease = (self.workers / "official_hidden" / "private" /
                 "worker-lease-events.jsonl")
        events = [json.loads(line) for line in lease.read_text().splitlines()]
        events.insert(1, {"event": "acquired", "operation": "other_worker",
                          "pid": 9999,
                          "at_utc": "2026-09-25T00:00:01+00:00"})
        put(lease, ("\n".join(json.dumps(row) for row in events) + "\n").encode())
        with self.assertRaisesRegex(offline.EvidenceError,
                                    "exclusive_gui_lease_missing_or_overlap"):
            self.run_audit()

    def test_boolean_reward_does_not_count_as_numeric_control(self):
        path = next((self.workers / "train" / "private" /
                     "admission_runs" / "runA").glob("T-*.json"))
        row = json.loads(path.read_text())
        row["gui_oracle_reward"] = True
        put(path, row)
        with self.assertRaisesRegex(offline.EvidenceError,
                                    "per_id_gui_control_invalid"):
            self.run_audit()

    def test_changed_source_asset_or_archive_rejected(self):
        with self.assertRaisesRegex(offline.EvidenceError,
                                    "source_asset_or_package_changed"):
            offline.audit(self.workers, self.public,
                          asset_builder=lambda case, world: b"tampered")
        archive = self.workers / "train" / "private" / "baseline.pgcustom"
        put(archive, b"changed")
        with self.assertRaisesRegex(offline.EvidenceError,
                                    "checkpoint_archive_hash_changed"):
            self.run_audit()


if __name__ == "__main__":
    unittest.main()
