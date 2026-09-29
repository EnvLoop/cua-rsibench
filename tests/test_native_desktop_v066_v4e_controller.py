"""Offline mutation checks for the source-only Desktop five-root continuation."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from native_desktop_factory import v066_day_rollover_controller_v4e as controller
from native_desktop_factory import v066_day_rollover_durable_child_v4e as child
from native_desktop_factory import v066_day_rollover_five_root_v4e as budget
from native_desktop_factory import v066_day_rollover_independent_audit_v4e as auditor


def _write(path: Path, value: dict) -> bytes:
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    path.chmod(0o600)
    return raw


class FiveRootBudgetTests(unittest.TestCase):
    def test_existing_old56_plus_new267_is_323(self):
        with TemporaryDirectory() as directory:
            roots = [Path(directory) / f"root-{i}" for i in range(5)]
            with patch.object(budget, "four_root_budget", return_value={
                "historical_counts": [22, 2, 2],
                "fresh_existing_intents": 30,
                "combined_full_lease_intents": 56,
            }), patch.object(budget, "intent_budget", return_value={
                "existing_intents": 0,
            }):
                observed = budget.five_root_budget(
                    original_root=roots[0], failed_root=roots[1],
                    failed_scoped_root=roots[2],
                    date_amended_root=roots[3], new_root=roots[4],
                    proposed_new_intents=267)
                self.assertEqual(observed["combined_full_lease_intents"], 323)
                self.assertEqual(observed["historical_four_root_intents"], 56)
                with self.assertRaisesRegex(ValueError, "lease ledger"):
                    budget.five_root_budget(
                        original_root=roots[0], failed_root=roots[1],
                        failed_scoped_root=roots[2],
                        date_amended_root=roots[3], new_root=roots[4],
                        proposed_new_intents=268)

    def test_nested_fifth_root_refused(self):
        with TemporaryDirectory() as directory:
            roots = [Path(directory) / f"root-{i}" for i in range(4)]
            with patch.object(budget, "four_root_budget", return_value={
                "historical_counts": [22, 2, 2],
                "fresh_existing_intents": 30,
                "combined_full_lease_intents": 56,
            }):
                with self.assertRaisesRegex(ValueError, "isolation"):
                    budget.five_root_budget(
                        original_root=roots[0], failed_root=roots[1],
                        failed_scoped_root=roots[2],
                        date_amended_root=roots[3],
                        new_root=roots[3] / "nested")


class SortedRosterTests(unittest.TestCase):
    def test_untouched_starts_after_old_precreate_and_clone_is_separate(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "candidate"
            candidate.mkdir()
            rows = [{"task_id": f"sorted-{i:03d}"} for i in range(100)]
            raw = b"shuffled-raw-inventory"
            frozen = {
                "candidate_inventory_sha256": sha256(raw).hexdigest(),
                "sorted_final_roster_sha256": sha256(
                    (json.dumps([row["task_id"] for row in rows],
                                separators=(",", ":")) + "\n").encode()).hexdigest(),
            }
            with patch.object(child, "_final_rows", return_value=(raw, rows)):
                child._verify_roster(
                    frozen=frozen,
                    run={"mode": "untouched", "selected_private_task_ids":
                         [rows[12]["task_id"]]},
                    root=root / "attempts", candidate_root=candidate)
                child._verify_roster(
                    frozen=frozen,
                    run={"mode": "clone", "selected_private_task_ids":
                         [rows[11]["task_id"]]},
                    root=root / "attempts", candidate_root=candidate)
                with self.assertRaisesRegex(ValueError, "skipped or reused"):
                    child._verify_roster(
                        frozen=frozen,
                        run={"mode": "untouched", "selected_private_task_ids":
                             [rows[11]["task_id"]]},
                        root=root / "attempts", candidate_root=candidate)
                with self.assertRaisesRegex(ValueError, "absent or unsafe"):
                    child._verify_roster(
                        frozen=frozen,
                        run={"mode": "untouched", "selected_private_task_ids":
                             [rows[13]["task_id"]]},
                        root=root / "attempts", candidate_root=candidate)


class ReviewPermitTests(unittest.TestCase):
    def test_review_writes_exact_one_batch_permit_without_child(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            freeze_path = root / "freeze.json"
            _write(freeze_path, {
                "new_attempts_root": str(root / "new-root"),
                "source_sha256s": {"source": "a" * 64},
            })
            rows = [{"task_id": f"private-{i:03d}"} for i in range(100)]
            current = {"untouched_complete_prefix": 0,
                       "clone_complete": False,
                       "official_final_admissions": 0}
            with patch.object(auditor, "audit", return_value=current), \
                    patch.object(auditor, "_old_paths", return_value={
                        "candidate_root": root / "candidate"}), \
                    patch.object(auditor, "_final_rows", return_value=(b"raw", rows)):
                result = auditor.review_one_batch(
                    freeze=freeze_path, mode="untouched", max_new_ids=1,
                    review_out=root / "review.json",
                    permit_out=root / "permit.json",
                    active_probe=lambda: (set(), 0))
            self.assertEqual(result["status"],
                             "one_batch_permit_written_without_provider_create")
            self.assertFalse((root / "new-root").exists())
            self.assertEqual(json.loads((root / "permit.json").read_bytes())[
                "selected_private_task_ids_sha256"],
                sha256(b'["private-012"]\n').hexdigest())

    def test_exact_review_and_one_batch_binding(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            freeze = root / "freeze.json"
            freeze_raw = _write(freeze, {"schema": "source"})
            frozen = {
                "source_sha256s": {"source": "a" * 64},
                "new_attempts_root": str(root / "fresh"),
            }
            selected = [{"task_id": "private-12"}]
            selected_sha = sha256(b'["private-12"]\n').hexdigest()
            review_path = root / "review.json"
            review_raw = _write(review_path, {
                "schema":
                    "cua-native-wdi-v066-v4e-independent-preflight-review-private-v1",
                "status": "accepted_for_exact_one_batch",
                "freeze_sha256": sha256(freeze_raw).hexdigest(),
                "source_sha256s": frozen["source_sha256s"],
                "mode": "untouched", "batch_number": 1,
                "maximum_new_ids": 1,
                "selected_private_task_ids_sha256": selected_sha,
                "provider_active_at_review": 0,
                "current_independent_audit": {"official_final_admissions": 0},
            })
            permit_path = root / "permit.json"
            _write(permit_path, {
                "schema": controller.PERMIT_SCHEMA,
                "status": "independently_reviewed_one_batch",
                "dispatch_authorized": True,
                "freeze_sha256": sha256(freeze_raw).hexdigest(),
                "source_sha256s": frozen["source_sha256s"],
                "mode": "untouched", "batch_number": 1,
                "maximum_new_ids": 1,
                "selected_private_task_ids_sha256": selected_sha,
                "same_intent_replay_authorized": False,
                "new_attempts_root": frozen["new_attempts_root"],
                "independent_review_path": str(review_path),
                "independent_review_sha256": sha256(review_raw).hexdigest(),
            })
            controller._checked_permit(
                freeze=freeze, frozen=frozen, permit_path=permit_path,
                mode="untouched", selected=selected, batch_number=1)
            with self.assertRaisesRegex(ValueError, "review permit absent"):
                controller._checked_permit(
                    freeze=freeze, frozen=frozen, permit_path=permit_path,
                    mode="clone", selected=selected, batch_number=1)
            changed = json.loads(review_raw)
            changed["provider_active_at_review"] = 1
            _write(review_path, changed)
            with self.assertRaisesRegex(ValueError, "review permit absent"):
                controller._checked_permit(
                    freeze=freeze, frozen=frozen, permit_path=permit_path,
                    mode="untouched", selected=selected, batch_number=1)


class DurableAttemptAuditTests(unittest.TestCase):
    def test_raw_stderr_and_full_lease_total_are_independently_bound(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            attempt_dir = root / "private-12" / "positive"
            attempt_dir.mkdir(parents=True)
            attempt_dir.chmod(0o700)
            row = {"task_id": "private-12", "package_sha256": "b" * 64}
            frozen = {"source_sha256s": {
                auditor.CHILD_SOURCE: "c" * 64,
                "native_desktop_factory/qwen_v066_adapter_v4_strict.py":
                    "d" * 64,
            }}
            _write(attempt_dir / "child.stdout", {"note": "raw output"})
            stderr_path = attempt_dir / "child.stderr"
            stderr_path.write_bytes(b"safe-stderr\n")
            stderr_path.chmod(0o600)
            budget_value = {
                "schema": "cua-native-wdi-v066-precreate-budget-private-v3",
                "status": "fsynced_before_provider_create",
                "task_id": row["task_id"], "attempt": "positive",
                "five_root_budget": {
                    "schema": "cua-native-wdi-v066-five-root-lease-budget-v4e",
                    "historical_four_root_intents": 56,
                    "new_root_existing_intents": 0,
                    "new_root_proposed_intents": 1,
                    "combined_full_lease_intents": 57,
                    "combined_conservative_reserved_usd": "9.5",
                },
                "fresh_lane_budget": {"combined_intents": 1},
                "provider_active_before_intent": 0,
                "storage_dispatch_ready": True,
                "credential_present": True,
                "power": {"source": "Battery Power"},
            }
            budget_raw = _write(attempt_dir / "budget.json", budget_value)
            _write(attempt_dir / "intent.json", {
                "schema": "cua-native-wdi-v066-final-control-intent-v1",
                "status": "recorded_before_provider_create",
                "task_id": row["task_id"], "attempt": "positive",
                "package_sha256": row["package_sha256"],
                "lease_seconds": auditor.LEASE_SECONDS,
                "precreate_budget_sha256": sha256(budget_raw).hexdigest(),
                "durable_child_wrapper_sha256": "c" * 64,
                "v4e_freeze_sha256": "e" * 64,
                "same_intent_replay_authorized": False,
            })
            _write(attempt_dir / "child-output.json", {
                "schema": "cua-native-wdi-v066-v4d-private-child-output-v1",
                "status": "terminal_output_fsynced_before_classification",
                "exit_code": 0, "timed_out": False,
                "stdout_sha256": sha256(
                    (attempt_dir / "child.stdout").read_bytes()).hexdigest(),
                "stderr_sha256": sha256(stderr_path.read_bytes()).hexdigest(),
            })
            _write(attempt_dir / "receipt.json", {
                "native_adapter_sha256": "d" * 64,
                "is_running_after_kill": False,
            })
            seen = set()
            auditor._checked_attempt(
                root=root, row=row, attempt="positive", frozen=frozen,
                freeze_sha="e" * 64, seen_budget_totals=seen)
            self.assertEqual(seen, {57})
            stderr_path.write_bytes(b"tampered stderr\n")
            with self.assertRaisesRegex(ValueError, "durable attempt"):
                auditor._checked_attempt(
                    root=root, row=row, attempt="positive", frozen=frozen,
                    freeze_sha="e" * 64, seen_budget_totals=set())
            stderr_path.write_bytes(b"safe-stderr\n")
            budget_value["five_root_budget"]["combined_full_lease_intents"] = 56
            _write(attempt_dir / "budget.json", budget_value)
            with self.assertRaisesRegex(ValueError, "durable attempt"):
                auditor._checked_attempt(
                    root=root, row=row, attempt="positive", frozen=frozen,
                    freeze_sha="e" * 64, seen_budget_totals=set())


if __name__ == "__main__":
    unittest.main()
