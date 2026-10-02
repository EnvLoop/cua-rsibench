"""Offline regression for Desktop v4c inventory-order failure and v4d output."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from native_desktop_factory import v066_day_rollover_durable_child_v4 as v4c
from native_desktop_factory import v066_day_rollover_durable_child_v4d as v4d
from native_desktop_factory import v066_day_rollover_durable_output_v4d as output
from native_desktop_factory import v066_day_rollover_precreate_freeze_v4d as freeze
from native_desktop_factory.v066_scoped_profile_final_controller import _final_rows


class SortedFrozenRosterTests(unittest.TestCase):
    def test_shuffled_raw_inventory_uses_controller_sorted_roster(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "candidate"
            candidate.mkdir()
            workflows = ("calc-growth", "calc-risk", "impress-deck",
                         "writer-brief")
            rows = [
                {"task_id": f"id-{group:02d}-{workflow}",
                 "split": "final_candidate", "source_groups": [f"g{group:02d}"],
                 "workflow": workflow}
                for group in range(25) for workflow in workflows
            ]
            # This is intentionally far from the controller's canonical order.
            raw = json.dumps({"design_revision": "v2-distinct-structures",
                              "tasks": list(reversed(rows))},
                             separators=(",", ":")).encode()
            (candidate / "candidate-inventory.json").write_bytes(raw)
            with patch("native_desktop_factory.v066_scoped_profile_final_controller.admit._package"):
                observed, sorted_rows = _final_rows(candidate)
                self.assertEqual(observed, raw)
                sorted_ids = [row["task_id"] for row in sorted_rows]
                self.assertNotEqual(sorted_ids[11],
                                    [row["task_id"] for row in reversed(rows)][11])
                frozen = {
                    "candidate_inventory_sha256": sha256(raw).hexdigest(),
                    "sorted_final_roster_sha256": sha256(
                        (json.dumps(sorted_ids, separators=(",", ":")) +
                         "\n").encode()).hexdigest(),
                }
                run = {"selected_private_task_ids": [sorted_ids[11]]}
                v4d._verify_untouched_roster(
                    frozen=frozen, run=run, root=root / "attempts",
                    candidate_root=candidate)
                with self.assertRaisesRegex(ValueError, "skipped an incomplete"):
                    v4c._verify_untouched_roster(
                        frozen=frozen, run=run, root=root / "attempts",
                        candidate_root=candidate)
                with self.assertRaisesRegex(ValueError, "sorted final roster changed"):
                    v4d._verify_untouched_roster(
                        frozen={**frozen, "sorted_final_roster_sha256": "0" * 64},
                        run=run, root=root / "attempts",
                        candidate_root=candidate)


class DurableChildOutputTests(unittest.TestCase):
    def test_stderr_is_private_and_fsynced_before_return(self):
        with TemporaryDirectory() as directory:
            attempt = Path(directory) / "id-11" / "positive"
            attempt.mkdir(parents=True)
            attempt.chmod(0o700)
            command = [sys.executable, "-c",
                       "import sys; print('out'); print('precreate gate', file=sys.stderr); sys.exit(7)"]
            code, stdout, stderr, timed_out = output._invoke_to_files(
                command, attempt, timeout_seconds=5)
            self.assertEqual((code, stdout, stderr, timed_out),
                             (7, "out\n", "precreate gate\n", False))
            record = json.loads((attempt / "child-output.json").read_bytes())
            self.assertEqual(record["status"],
                             "terminal_output_fsynced_before_classification")
            self.assertEqual(record["stderr_sha256"],
                             sha256((attempt / "child.stderr").read_bytes()).hexdigest())
            for name in ("child.stdout", "child.stderr", "child-output.json"):
                self.assertEqual((attempt / name).stat().st_mode & 0o077, 0)
            with self.assertRaisesRegex(ValueError, "replay refused"):
                output._invoke_to_files(command, attempt, timeout_seconds=5)

    def test_dispatch_helper_rejects_unbound_command(self):
        with self.assertRaisesRegex(ValueError, "source-bound v4d child"):
            output._attempt_dir([sys.executable, "-c", "pass"])


class NoCreateProofTests(unittest.TestCase):
    def test_stderr_hash_match_is_required_before_clone_eligibility(self):
        repo = Path(__file__).resolve().parents[1]
        wrapper_sha = sha256((repo / freeze.V4C_SOURCE_NAMES[3]).read_bytes()).hexdigest()
        stderr = (b'  File "frozen-child.py", line 115, in '
                  b'_verify_untouched_roster\n'
                  b'ValueError: v4 child skipped an incomplete earlier ID\n')
        budget = {"status": "fsynced_before_provider_create",
                  "four_root_budget": {"combined_full_lease_intents": 56},
                  "fresh_lane_budget": {"combined_intents": 30}}
        intent = {"status": "recorded_before_provider_create",
                  "durable_child_wrapper_sha256": wrapper_sha}
        budget_raw = json.dumps(budget).encode()
        intent_raw = json.dumps(intent).encode()
        attempt = {
            "attempt": "positive", "exit_code": 1,
            "status": "missing_or_invalid_receipt",
            "receipt_sha256": None, "sandbox_id_observed": False,
            "child_process_exited": True,
            "stdout_sha256": sha256(b"").hexdigest(),
            "stderr_sha256": sha256(stderr).hexdigest(),
            "budget_sha256": sha256(budget_raw).hexdigest(),
            "intent_sha256": sha256(intent_raw).hexdigest(),
        }
        terminal = {
            "status": "stopped_for_reconciliation",
            "existing_complete_trios_before": 8,
            "official_final_admissions": 0,
            "official_final_model_attempts": 0,
            "selected_private_task_ids": ["synthetic-11"],
            "task_outcomes": [{
                "private_task_id": "synthetic-11",
                "status": "stopped_after_invalid_or_uncertain_attempt",
                "attempts": [attempt],
            }],
        }
        public = {
            "child_stderr_sha256": sha256(stderr).hexdigest(),
            "child_stderr_reproduced_sha256_match": True,
            "new_attempt_receipt_present": False,
            "new_sandbox_id_observed": False,
        }
        old = {"source_sha256s": {freeze.V4C_SOURCE_NAMES[3]: wrapper_sha}}
        freeze._prove_precreate(v4c=old, terminal=terminal, stderr=stderr,
                                budget_raw=budget_raw, intent_raw=intent_raw,
                                public_audit=public, repo=repo)
        with self.assertRaisesRegex(ValueError, "no-create proof absent"):
            freeze._prove_precreate(
                v4c=old, terminal=terminal, stderr=stderr + b"changed",
                budget_raw=budget_raw, intent_raw=intent_raw,
                public_audit=public, repo=repo)


if __name__ == "__main__":
    unittest.main()
