"""Offline-only Odoo v0.6.6 requalification plan and pilot proof gate."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest

from PIL import Image

# The original Odoo worker modules retain script-style sibling imports.
ODOO_SOURCE = Path(__file__).resolve().parents[1] / "enterprise_fallback/odoo18"
if str(ODOO_SOURCE) not in sys.path:
    sys.path.insert(0, str(ODOO_SOURCE))

from enterprise_fallback.odoo18 import v066_requalification_plan as plan
from enterprise_fallback.odoo18 import v066_requalification_pilot as pilot


def put(path: Path, value: object, *, private: bool = True) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700 if private else 0o755)
    raw = value if type(value) is bytes else plan.canonical(value)
    path.write_bytes(raw)
    path.chmod(0o600 if private else 0o644)
    return {"path": str(path.name), "sha256": plan.sha(raw)}


def png(color: tuple[int, int, int]) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (1440, 1000), color).save(buffer, "PNG")
    return buffer.getvalue()


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        rat_dir = self.root / "rat"
        rat_dir.mkdir(mode=0o700)
        common = {name: plan.sha((plan.ROOT / relative).read_bytes())
                  for name, relative in plan.COMMON_FILES.items()}
        adapter_sha = plan.sha((plan.ROOT / plan.ODOO_FILES[0]).read_bytes())
        cells = ("powerpoint-web", "excel-web", "desktop-native",
                 "odoo-community", "gitlab", "magento-admin")
        profiles = {cell: {"adapter_sha256": adapter_sha if cell == "odoo-community"
                            else "a" * 64, "common_source_sha256s": common}
                    for cell in cells}
        private = {"schema": "cua-six-cell-action-profile-v066-ratification-v1",
                   "status": "ratified_pre_result",
                   "action_profile": plan.PROFILE,
                   "base_and_selected_identical": True,
                   "hidden_final_model_attempts_before_ratification": 0,
                   "common_source_sha256s": common, "cell_profiles": profiles}
        self.rat_private = rat_dir / "rat.private.json"
        put(self.rat_private, private)
        self.rat_sha = plan.sha(self.rat_private.read_bytes())
        self.rat_public = self.root / "rat.public.json"
        put(self.rat_public, {
            "schema": "cua-six-cell-v066-caret-code-only-ratification-public-v1",
            "private_ratification_sha256": self.rat_sha,
            "status": "new_source_bytes_frozen_for_evaluator_controls_only",
            "qualified_final_tasks": 0, "official_final_model_results": 0,
            "cell_adapter_sha256s":
                {cell: profiles[cell]["adapter_sha256"] for cell in cells},
            "common_source_sha256s": common,
        }, private=False)
        self.workers = self.root / "workers"
        self.public_dir = self.root / "public"
        self.public_dir.mkdir()
        manifest = {"train": [], "selection": [], "official": []}
        worlds = {}
        sources = {}
        for split, (name, per_family) in plan.historical.SPLITS.items():
            cases = {}
            split_sources = {}
            for family in plan.historical.FAMILIES:
                group = []
                for index in range(per_family):
                    task_id = f"T-{split}-{family}-{index:03d}"
                    group.append({"id": task_id, "family": family,
                                  "sku": f"SKU-{task_id}",
                                  "prompt": f"Synthetic instruction {task_id}"})
                    split_sources[task_id] = plan.sha(task_id.encode())
                    manifest[name].append({"task_id": task_id,
                                           "package_sha256": plan.sha(
                                               (task_id + "pkg").encode())})
                cases[family] = group
            worlds[split] = {"split": split, "cases": cases}
            sources[split] = split_sources
        for split in plan.historical.SPLITS:
            private_dir = self.workers / split / "private"
            private_dir.mkdir(parents=True, mode=0o700)
            put(private_dir / "partition_cases.json", worlds[split])
            put(private_dir / "task_set_manifest.json", manifest)
            put(private_dir / "source_hashes.json", sources[split])
            put(private_dir / "checkpoint_receipt.json", {
                "db_sha256": plan.sha((split + "db").encode()),
                "filestore_sha256": plan.sha((split + "fs").encode())})
            put(private_dir / "baseline_snapshot.json", {})
            put(private_dir / "baseline-filestore-manifest.json", {})

    def test_new_ratification_and_140_task_plan_remain_prospective(self):
        value, public = plan.build(
            workers_root=self.workers, public_evidence_dir=self.public_dir,
            ratification_private=self.rat_private,
            ratification_public=self.rat_public,
            expected_ratification_sha256=self.rat_sha,
            historical_audit=lambda *_: ({}, {
                "historical_source_assets_and_packages_rebuilt": 140,
                "private_evidence_owner_only_permissions": True,
                "official_final_tasks_admitted": 0}))
        self.assertEqual(public["candidate_counts"],
                         {"train": 20, "selection": 20, "official_hidden": 100})
        self.assertEqual(sum(map(len, value["tasks"].values())), 140)
        self.assertEqual(value["pilot"]["split"], "train")
        self.assertEqual(public["official_final_tasks_admitted"], 0)
        self.assertFalse(public["pilot_receipt_present"])
        self.assertNotIn(value["pilot"]["task_id"], json.dumps(public))
        self.assertEqual(public["private_plan_sha256"], plan.sha(plan.canonical(value)))

    def test_changed_ratification_or_missing_privacy_rejected(self):
        with self.assertRaisesRegex(plan.RequalificationPlanError,
                                    "new_six_cell_ratification_invalid"):
            plan._ratification(self.rat_private, self.rat_public, "0" * 64)
        value = json.loads(self.rat_public.read_text())
        value["cell_adapter_sha256s"]["odoo-community"] = "f" * 64
        put(self.rat_public, value, private=False)
        with self.assertRaisesRegex(plan.RequalificationPlanError,
                                    "six_cell_adapter_roster_changed"):
            plan._ratification(self.rat_private, self.rat_public, self.rat_sha)


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workers = self.root / "workers"
        self.private = self.workers / "train" / "private"
        self.private.mkdir(parents=True, mode=0o700)
        self.attempt = self.private / "v066_requalification_runs" / "pilot-1"
        self.attempt.mkdir(parents=True, mode=0o700)
        self.task_id = "T-TRAIN-INVENTORY-001"
        self.package_sha = "b" * 64
        self.source_sha = "d" * 64
        source_files = {relative: plan.sha((plan.ROOT / relative).read_bytes())
                        for relative in plan.ODOO_FILES}
        common = {name: plan.sha((plan.ROOT / relative).read_bytes())
                  for name, relative in plan.COMMON_FILES.items()}
        db_raw, filestore_raw = b"synthetic-db", b"synthetic-filestore"
        self.checkpoint = {"db_sha256": plan.sha(db_raw),
                           "filestore_sha256": plan.sha(filestore_raw)}
        put(self.private / "baseline.pgcustom", db_raw)
        put(self.private / "baseline-filestore.tgz", filestore_raw)
        put(self.private / "checkpoint_receipt.json", self.checkpoint)
        checksum = lambda index: hashlib.sha1(str(index).encode()).hexdigest()
        attachments = [{"id": index, "checksum": checksum(index)}
                       for index in range(1, 17)]
        frozen = {f"filestore/bench/{row['checksum'][:2]}/{row['checksum']}":
                  plan.sha(str(row["id"]).encode()) for row in attachments}
        self.paths = {str(row["id"]):
                      f"{row['checksum'][:2]}/{row['checksum']}"
                      for row in attachments}
        target_rule = {"id": 1, "product_id": 3, "location_id": 4,
                       "warehouse_id": 5, "company_id": 6, "multiple": "1",
                       "trigger": "manual", "minimum": "10", "maximum": "20"}
        wrong_rule = {**target_rule, "id": 2, "product_id": 7,
                      "minimum": "5", "maximum": "9"}
        self.baseline = {"global_business_identity": {},
                         **{name: [] for name in (
                             "orders", "lines", "vendors", "products",
                             "sales_orders", "sales_lines", "crm_leads",
                             "customers", "salespeople", "crm_stages")},
                         "attachments": attachments,
                         "orderpoints": [target_rule, wrong_rule]}
        self.positive = deepcopy(self.baseline)
        self.positive["orderpoints"][0]["minimum"] = "12"
        self.positive["orderpoints"][0]["maximum"] = "24"
        self.negative = deepcopy(self.positive)
        self.negative["orderpoints"][1]["minimum"] = "6"
        baseline_ref = put(self.private / "baseline_snapshot.json", self.baseline)
        frozen_ref = put(self.private / "baseline-filestore-manifest.json", frozen)
        put(self.private / "replenishment_gold.json", {self.task_id: {
            "rule_id": 1, "expected": {"minimum": 12, "maximum": 24}}})
        self.checkpoint.update({
            "baseline_snapshot_sha256": baseline_ref["sha256"],
            "baseline_filestore_manifest_sha256": frozen_ref["sha256"]})
        case = {"id": self.task_id, "family": "inventory",
                "prompt": "Repair the replenishment rule", "sku": "SKU-1"}
        task_manifest = {"train": [{"task_id": self.task_id,
                                     "package_sha256": self.package_sha}],
                         "selection": [], "official": []}
        for index in range(19):
            task_manifest["train"].append({"task_id": f"TRAIN-FILLER-{index}",
                                           "package_sha256": plan.sha(str(index).encode())})
        for index in range(20):
            task_manifest["selection"].append({"task_id": f"SEL-FILLER-{index}",
                                               "package_sha256": plan.sha(
                                                   f"sel-{index}".encode())})
        for index in range(100):
            task_manifest["official"].append({"task_id": f"HID-FILLER-{index}",
                                              "package_sha256": plan.sha(
                                                  f"hid-{index}".encode())})
        put(self.private / "task_set_manifest.json", task_manifest)
        put(self.private / "source_hashes.json", {self.task_id: self.source_sha})
        put(self.private / "partition_cases.json", {
            "split": "train", "cases": {"inventory": [case]}})
        binding = {
            "ratification_sha256": plan.RATIFICATION_SHA256,
            "action_profile": plan.PROFILE,
            "split": "train", "task_id": self.task_id,
            "package_sha256": self.package_sha,
            "source_asset_sha256": self.source_sha,
            "visible_instruction_sha256": plan.sha(case["prompt"].encode()),
            "checkpoint": self.checkpoint,
            "odoo_adapter_sha256": source_files[plan.ODOO_FILES[0]],
        }
        self.binding_sha = plan.sha(plan.canonical(binding))
        row = {**binding,
               "task_binding_sha256": self.binding_sha,
               "source_label": "Purchase planning note for SKU-1",
               "fresh_v066_gui_proof_status": "pending",
               "family": "inventory"}
        filler = lambda item: {"task_id": item["task_id"],
                               "package_sha256": item["package_sha256"]}
        private_plan = {
            "schema": plan.PRIVATE_SCHEMA,
            "status": "planned_no_current_v066_gui_proofs",
            "ratification_sha256": plan.RATIFICATION_SHA256,
            "pilot_auditor_source_sha256": plan.sha(Path(pilot.__file__).read_bytes()),
            "odoo_source_sha256s": source_files,
            "common_action_source_sha256s": common,
            "checkpoints": {"train": self.checkpoint},
            "task_set_manifest_sha256": plan.historical.canonical_digest(task_manifest),
            "tasks": {"train": [row] + [filler(x) for x in task_manifest["train"][1:]],
                      "selection": [filler(x) for x in task_manifest["selection"]],
                      "official_hidden": [filler(x) for x in task_manifest["official"]]},
            "pilot": {"split": "train", "task_id": self.task_id,
                      "task_binding_sha256": self.binding_sha},
            "official_final_tasks_admitted": 0,
        }
        self.plan_path = self.root / "private-plan" / "plan.private.json"
        self.plan_path.parent.mkdir(mode=0o700)
        put(self.plan_path, private_plan)
        self.public_plan_path = self.root / "plan.public.json"
        put(self.public_plan_path, {
            "schema": plan.PUBLIC_SCHEMA,
            "status": "source_bound_plan_only_no_current_gui_proofs",
            "private_plan_sha256": plan.sha(plan.canonical(private_plan)),
            "new_six_cell_ratification_sha256": plan.RATIFICATION_SHA256,
            "candidate_counts": {"train": 20, "selection": 20,
                                 "official_hidden": 100},
            "task_set_manifest_sha256":
                plan.historical.canonical_digest(task_manifest),
            "pilot_auditor_source_sha256":
                plan.sha(Path(pilot.__file__).read_bytes()),
            "planner_source_sha256": plan.sha(Path(plan.__file__).read_bytes()),
        }, private=False)
        self.frozen = frozen
        self.ref = {}
        restore = {"status": "restored", "business_snapshot_equal": True,
                   "physical_filestore_equal_before_web_restart": True,
                   "db_sha256": self.checkpoint["db_sha256"],
                   "filestore_sha256": self.checkpoint["filestore_sha256"]}
        objects = {"pre_restore": restore, "post_restore": restore,
                   "baseline_sql": self.baseline,
                   "positive_sql": self.positive,
                   "negative_sql": self.negative,
                   "restored_sql": self.baseline,
                   "positive_filestore": frozen,
                   "negative_filestore": frozen,
                   "restored_filestore": frozen,
                   "positive_store_paths": self.paths,
                   "negative_store_paths": self.paths}
        for name, value in objects.items():
            self.ref[name] = put(self.attempt / f"{name}.json", value)
        colors = {"source_frame": (20, 30, 40),
                  "positive_reload_frame": (30, 40, 50),
                  "negative_reload_frame": (40, 50, 60),
                  "negative_action_frame": (60, 70, 80)}
        for name, color in colors.items():
            self.ref[name] = put(self.attempt / f"{name}.png", png(color))
        self.ref["source_review"] = put(self.attempt / "source_review.json", {
            "schema": pilot.REVIEW_SCHEMA,
            "decision": "source_visible_in_original_odoo_gui",
            "reviewer_role": "independent_visual_source_reviewer",
            "reviewer_id_sha256": "2" * 64,
            "source_frame_sha256": self.ref["source_frame"]["sha256"],
            "source_asset_sha256": self.source_sha,
            "source_label": row["source_label"],
            "reviewed_at_utc": "2026-09-28T00:00:10+00:00",
        })
        action_frames = (self.ref["source_frame"],
                         self.ref["negative_action_frame"])
        actions = []
        for step, phase in enumerate(("positive", "negative")):
            frame = action_frames[step]
            actions.append({"phase": phase, "step": step, "frame": frame,
                            "contract_receipt": {
                                "action_profile": plan.PROFILE,
                                "task_binding_sha256": self.package_sha,
                                "task_id_sha256": plan.sha(self.task_id.encode()),
                                "step": step, "frame_id_sha256": "1" * 64,
                                "screenshot": {
                                    "sha256": frame["sha256"],
                                    "width": 1440, "height": 1000},
                                "action_type": "click", "error_code": None}})
        self.ref["gui_trace"] = put(self.attempt / "gui_trace.json", {
            "schema": pilot.GUI_SCHEMA,
            "task_binding_sha256": self.binding_sha,
            "actions": actions})
        self.ref.pop("negative_action_frame")
        times = {name: f"2026-09-28T00:00:0{index + 1}+00:00"
                 for index, name in enumerate(pilot.STAGES)}
        self.receipt = {
            "schema": pilot.ATTEMPT_SCHEMA,
            "status": "completed_with_raw_evaluator_evidence",
            "plan_sha256": plan.sha(plan.canonical(private_plan)),
            "ratification_sha256": plan.RATIFICATION_SHA256,
            "split": "train", "task_id": self.task_id,
            "package_sha256": self.package_sha,
            "task_binding_sha256": self.binding_sha,
            "worker_pid": 1234, "controller_id_sha256": "3" * 64,
            "started_at_utc": "2026-09-28T00:00:00+00:00",
            "finished_at_utc": "2026-09-28T00:00:08+00:00",
            "lease_operation": pilot.LEASE_OPERATION,
            "stage_timestamps": times,
            "refs": self.ref,
        }
        lease = [
            {"event": "acquired", "operation": pilot.LEASE_OPERATION,
             "pid": 1234, "at_utc": "2026-09-27T23:59:59+00:00"},
            {"event": "released", "operation": pilot.LEASE_OPERATION,
             "pid": 1234, "at_utc": "2026-09-28T00:00:09+00:00"},
        ]
        path = self.private / "worker-lease-events.jsonl"
        put(path, ("\n".join(json.dumps(row) for row in lease) + "\n").encode())
        self.attempt_path = self.attempt / "attempt.private.json"
        put(self.attempt_path, self.receipt)

    def audit(self):
        return pilot.audit_pilot(private_plan_path=self.plan_path,
                                 public_plan_path=self.public_plan_path,
                                 workers_root=self.workers,
                                 attempt_dir=self.attempt)

    def test_derives_positive_wrong_object_and_reset_from_saved_state(self):
        result = self.audit()
        self.assertEqual(result["independent_positive_reward"], 1.0)
        self.assertEqual(result["independent_negative_reward"], 0.0)
        self.assertEqual(result["fresh_train_candidate_controls_qualified"], 1)
        self.assertEqual(result["official_final_tasks_admitted"], 0)

    def test_missing_receipt_or_changed_saved_state_fails_closed(self):
        self.attempt_path.unlink()
        with self.assertRaisesRegex(pilot.PilotEvidenceError, "pilot_attempt_missing"):
            self.audit()
        self.receipt["refs"]["negative_sql"] = put(
            self.attempt / "negative_sql.json", self.positive)
        put(self.attempt_path, self.receipt)
        with self.assertRaisesRegex(pilot.PilotEvidenceError,
                                    "pilot_independent_saved_state_or_negative_control_failed"):
            self.audit()

    def test_inexact_restore_or_unbound_gui_action_rejected(self):
        reset = json.loads((self.attempt / "post_restore.json").read_text())
        reset["physical_filestore_equal_before_web_restart"] = False
        self.receipt["refs"]["post_restore"] = put(
            self.attempt / "post_restore.json", reset)
        put(self.attempt_path, self.receipt)
        with self.assertRaisesRegex(pilot.PilotEvidenceError,
                                    "pilot_physical_reset_not_exact"):
            self.audit()
        reset["physical_filestore_equal_before_web_restart"] = True
        self.receipt["refs"]["post_restore"] = put(
            self.attempt / "post_restore.json", reset)
        trace = json.loads((self.attempt / "gui_trace.json").read_text())
        trace["actions"][0]["contract_receipt"]["task_binding_sha256"] = "0" * 64
        self.receipt["refs"]["gui_trace"] = put(
            self.attempt / "gui_trace.json", trace)
        put(self.attempt_path, self.receipt)
        with self.assertRaisesRegex(pilot.PilotEvidenceError,
                                    "pilot_v066_current_frame_action_binding_invalid"):
            self.audit()

    def test_public_plan_or_frame_tamper_fails_closed(self):
        self.public_plan_path.write_text("{}")
        with self.assertRaisesRegex(pilot.PilotEvidenceError,
                                    "pilot_public_plan_source_binding_invalid"):
            self.audit()


if __name__ == "__main__":
    unittest.main()
