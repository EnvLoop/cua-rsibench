"""Offline contracts for the task-free GitLab boot probe."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from gitlab_world import v066_boot_only_probe_v5 as probe


class BootOnlyProbeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "docs/evidence").mkdir(parents=True)
        self.private_root = self.root / "private"
        self.private_root.mkdir(mode=0o700)
        self.probe_dir = self.private_root / "probe"
        self.probe_dir.mkdir(mode=0o700)
        self.public_freeze = self.root / "docs/evidence/source.json"
        self.ratification = self.private_root / "ratification.private.json"
        self.ratification.write_text("{}")
        self.ratification.chmod(0o600)
        self.patches = [
            patch.object(probe, "ROOT", self.root),
            patch.object(probe.one, "ROOT", self.root),
            patch.object(probe.one, "PRIVATE_ROOT", self.private_root),
            patch.object(probe, "PRIVATE_ROOT", self.private_root),
            patch.object(probe, "PROBE", self.probe_dir),
            patch.object(probe, "CLONES", self.probe_dir / "clones"),
            patch.object(probe, "PRIVATE_FREEZE", self.probe_dir / "source.private.json"),
            patch.object(probe, "PUBLIC_FREEZE", self.public_freeze),
            patch.object(probe, "INTENT", self.probe_dir / "intent.private.json"),
            patch.object(probe, "CHILD_RESULT", self.probe_dir / "child.private.json"),
            patch.object(probe, "SUPERVISOR_RESULT", self.probe_dir / "supervisor.private.json"),
            patch.object(probe, "PUBLIC_RESULT", self.root / "docs/evidence/result.json"),
        ]
        for item in self.patches:
            item.start()
        self.addCleanup(lambda: [item.stop() for item in reversed(self.patches)])

    def _freeze_offline(self):
        with patch.object(probe, "_parent_bindings", return_value=(
                 {"status": "source_plan_auditable_only_in_original_evaluator_worktree"},
                 {"epoch_sha256": "a" * 64})), \
             patch.object(probe, "_source_sha256s", return_value={"source.py": "b" * 64}), \
             patch.object(probe.secrets, "token_hex", return_value="ab" * 32), \
             patch.object(probe, "PARENT_PUBLIC", self.ratification), \
             patch.object(probe, "SCOPE", self.ratification):
            public = probe.freeze(self.ratification)
            audited = probe.audit(self.ratification)
        return public, audited

    def test_freeze_and_audit_are_offline_and_hide_nonce(self):
        with patch.object(probe.reset, "reset") as reset_run, \
             patch.object(probe.lane, "assert_live_world") as world_read:
            public, audited = self._freeze_offline()
        self.assertEqual(public, audited)
        self.assertEqual(public["maximum_boot_clones"], 3)
        self.assertNotIn("ab" * 32, json.dumps(public))
        self.assertEqual(public["selection_or_final_tasks_dispatched"], 0)
        self.assertEqual((self.probe_dir / "source.private.json").stat().st_mode & 0o077,
                         0)
        reset_run.assert_not_called()
        world_read.assert_not_called()

    def test_freeze_source_drift_is_rejected_before_runtime(self):
        self._freeze_offline()
        with patch.object(probe, "_parent_bindings", return_value=(
                 {"status": "source_plan_auditable_only_in_original_evaluator_worktree"},
                 {"epoch_sha256": "a" * 64})), \
             patch.object(probe, "_source_sha256s", return_value={"source.py": "c" * 64}), \
             patch.object(probe, "PARENT_PUBLIC", self.ratification), \
             patch.object(probe, "SCOPE", self.ratification):
            with self.assertRaisesRegex(probe.ProbeError,
                                        "boot_probe_frozen_source_or_parent_changed"):
                probe.validate_freeze(self.ratification)

    def test_forensics_save_raw_logs_and_state_without_config(self):
        folder = self.probe_dir / "clones" / "00"
        folder.mkdir(mode=0o700, parents=True)
        state = b'{"Status":"exited","ExitCode":1,"OOMKilled":false}\n'
        with patch.object(probe, "_docker_forensic", side_effect=[
            (b"raw startup stdout\n", b"raw startup stderr\n", 0, None),
            (state, b"", 0, None),
        ]) as docker:
            result = probe.capture_startup_forensics(folder)
        self.assertTrue(result["raw_startup_logs_saved"])
        self.assertTrue(result["state_only_inspect_saved"])
        self.assertEqual(result["state_exit_code"], 1)
        self.assertFalse(result["state_oom_killed"])
        self.assertEqual((folder / "docker-logs.stdout.private.log").read_bytes(),
                         b"raw startup stdout\n")
        self.assertEqual((folder / "docker-logs.stderr.private.log").read_bytes(),
                         b"raw startup stderr\n")
        self.assertTrue(all(path.stat().st_mode & 0o077 == 0
                            for path in folder.iterdir()))
        self.assertEqual(docker.call_args_list[0].args[0][:2],
                         ["logs", "--timestamps"])
        self.assertEqual(docker.call_args_list[1].args[0],
                         ["inspect", "--format", "{{json .State}}", probe.runtime.WORLD])
        self.assertNotIn("Config", str(docker.call_args_list))

    def test_failed_log_capture_is_saved_as_unverified(self):
        folder = self.probe_dir / "clones" / "00"
        folder.mkdir(mode=0o700, parents=True)
        with patch.object(probe, "_docker_forensic", side_effect=[
            (b"", b"Docker error", 1, None),
            (b"[]", b"", 0, None),
        ]):
            result = probe.capture_startup_forensics(folder)
        self.assertFalse(result["raw_startup_logs_saved"])
        self.assertFalse(result["state_only_inspect_saved"])
        self.assertEqual(result["docker_inspect_state_error_type"],
                         "StateJsonNotObject")
        self.assertEqual((folder / "docker-logs.stderr.private.log").read_bytes(),
                         b"Docker error")

    def test_existing_intent_blocks_second_dispatch_without_docker(self):
        self.public_freeze.write_text("{}")
        (self.probe_dir / "intent.private.json").write_text("{}")
        reviewed = probe.one.sha(self.public_freeze.read_bytes())
        with patch.object(probe, "validate_freeze", return_value=(
                 {"intent_nonce": "ab" * 32}, "a" * 64)), \
             patch.object(probe.lane, "assert_live_world") as world_read, \
             patch.object(probe.one, "supervise_child") as supervise:
            with self.assertRaisesRegex(probe.ProbeError,
                                        "boot_probe_intent_already_dispatched_no_replay"):
                probe.run_probe(self.ratification, reviewed)
        world_read.assert_not_called()
        supervise.assert_not_called()

    def test_supervisor_captures_after_child_failure_before_cleanup(self):
        self.public_freeze.write_text("{}")
        reviewed = probe.one.sha(self.public_freeze.read_bytes())
        nonce = "ab" * 32
        private = {"intent_nonce": nonce,
                   "intent_nonce_sha256": probe.one.sha(nonce.encode())}
        child = {"child_terminated": True,
                 "process_group_terminated": True,
                 "timed_out": True, "exit_code": 1}
        forensic = {"raw_startup_logs_saved": True,
                    "state_only_inspect_saved": True,
                    "raw_file_sha256s": {"docker_logs_stdout": "d" * 64}}
        order = []

        def capture(folder):
            order.append("capture")
            self.assertEqual(folder.name, "supervisor-fallback")
            return forensic

        def cleanup():
            order.append("cleanup")
            return {"cold_reset_exact": True}

        with patch.object(probe, "validate_freeze", return_value=(private, "a" * 64)), \
             patch.object(probe.terminal, "validate_freeze", return_value=(
                 {}, {"old": {}}, {})), \
             patch.object(probe.lane, "assert_live_world", return_value={}), \
             patch.object(probe.one, "supervise_child", return_value=child), \
             patch.object(probe.recovery, "_confirm_child_process_group",
                          side_effect=lambda row: row), \
             patch.object(probe, "capture_startup_forensics", side_effect=capture), \
             patch.object(probe.one, "exact_cold_reset", side_effect=cleanup):
            result = probe.run_probe(self.ratification, reviewed)
        self.assertEqual(order, ["capture", "cleanup"])
        self.assertEqual(result["status"],
                         "terminal_probe_failure_exactly_reset_no_replay")
        self.assertTrue(result["supervisor_fallback_log_capture_succeeded"])
        self.assertTrue(result["raw_startup_logs_saved_before_cleanup"])
        self.assertTrue(result["raw_logs_private"])
        self.assertEqual(result["task_intents"], 0)

    def _child_case(self, *, fail_first_reset: bool):
        self.public_freeze.write_text("{}")
        reviewed = probe.one.sha(self.public_freeze.read_bytes())
        nonce = "ab" * 32
        freeze_sha = "a" * 64
        intent = {
            "schema": probe.INTENT_SCHEMA,
            "intent_nonce": nonce,
            "source_freeze_sha256": freeze_sha,
            "maximum_boot_clones": 3,
            "task_intents": 0,
            "selection_or_final_tasks_dispatched": 0,
            "same_failed_id_replay_authorized": False,
        }
        probe.one.write_new(probe.INTENT, intent)
        private = {"intent_nonce": nonce,
                   "intent_nonce_sha256": probe.one.sha(nonce.encode())}
        forensic = {"raw_startup_logs_saved": True,
                    "state_only_inspect_saved": True,
                    "raw_file_sha256s": {"docker_logs_stdout": "d" * 64}}
        with patch.object(probe, "validate_freeze", return_value=(private, freeze_sha)), \
             patch.object(probe.terminal, "validate_freeze", return_value=(
                 {}, {"old": {}}, {})), \
             patch.object(probe.lane, "assert_live_world", return_value={}), \
             patch.object(probe, "capture_startup_forensics", return_value=forensic), \
             patch.object(probe.reset, "reset", side_effect=(
                 RuntimeError("boot failed") if fail_first_reset else None),
                 return_value={"cold_reset": True}) as reset_run:
            result = probe._child_run(self.ratification, reviewed)
        return result, reset_run.call_count

    def test_child_runs_three_task_free_boots(self):
        result, reset_count = self._child_case(fail_first_reset=False)
        self.assertEqual(result["status"],
                         "three_boot_only_clones_exact_baseline")
        self.assertEqual(reset_count, 3)
        child, _ = probe.one.private_json(probe.CHILD_RESULT)
        self.assertEqual(child["completed_boot_clones"], 3)
        self.assertEqual(child["task_intents"], 0)
        self.assertEqual(child["selection_or_final_tasks_dispatched"], 0)

    def test_child_failure_stops_after_one_boot_and_keeps_logs_receipt(self):
        result, reset_count = self._child_case(fail_first_reset=True)
        self.assertEqual(result["status"],
                         "boot_only_clone_failed_or_forensics_incomplete")
        self.assertEqual(reset_count, 1)
        receipt, _ = probe.one.private_json(
            probe.CLONES / "00" / "boot-receipt.private.json")
        self.assertEqual(receipt["error_type"], "RuntimeError")
        self.assertEqual(receipt["boot_index"], 0)
        self.assertFalse((probe.CLONES / "01").exists())

    def test_audit_reopens_raw_forensics_and_rejects_tampering(self):
        self._freeze_offline()
        frozen, freeze_sha = probe.one.private_json(probe.PRIVATE_FREEZE)
        nonce = frozen["intent_nonce"]
        intent = {
            "schema": probe.INTENT_SCHEMA,
            "intent_nonce": nonce,
            "source_freeze_sha256": freeze_sha,
            "maximum_boot_clones": 3,
            "task_intents": 0,
            "selection_or_final_tasks_dispatched": 0,
            "same_failed_id_replay_authorized": False,
        }
        intent_sha = probe.one.write_new(probe.INTENT, intent)
        probe.CLONES.mkdir(mode=0o700)
        folder = probe.CLONES / "00"
        folder.mkdir(mode=0o700)
        with patch.object(probe, "_docker_forensic", side_effect=[
            (b"startup raw\n", b"", 0, None),
            (b'{"Status":"exited","ExitCode":1,"OOMKilled":false}', b"", 0, None),
        ]):
            forensic = probe.capture_startup_forensics(folder)
        receipt_sha = probe.one.write_new(
            folder / "boot-receipt.private.json",
            {"boot_index": 0, "forensics": forensic})
        child_sha = probe.one.write_new(probe.CHILD_RESULT, {
            "schema": probe.CHILD_SCHEMA,
            "intent_sha256": intent_sha,
            "task_intents": 0,
            "selection_or_final_tasks_dispatched": 0,
            "model_calls": 0, "official_final_admitted": 0,
            "completed_boot_clones": 1,
            "boot_receipt_sha256s": [receipt_sha],
        })
        supervisor = {
            "schema": probe.SUPERVISOR_SCHEMA,
            "status": "terminal_probe_failure_exactly_reset_no_replay",
            "intent_sha256": intent_sha,
            "source_freeze_sha256": freeze_sha,
            "intent_nonce_sha256": frozen["intent_nonce_sha256"],
            "child_result_sha256": child_sha,
            "completed_boot_clones": 1,
            "raw_log_sha256s": [forensic["raw_file_sha256s"]["docker_logs_stdout"]],
            "private_forensic_tree_manifest": probe._forensic_tree_manifest(),
            "fallback_forensics": None,
            "fallback_log_capture_succeeded": False,
            "raw_startup_logs_saved_before_cleanup": True,
            "post_failure_exact_reset": True,
            "cleanup": {"cold_reset_exact": True},
            "child_process_group_terminated": True,
            "same_failed_id_replay_authorized": False,
            "task_intents": 0,
            "selection_or_final_tasks_dispatched": 0,
            "model_calls": 0, "official_final_admitted": 0,
        }
        supervisor_sha = probe.one.write_new(probe.SUPERVISOR_RESULT,
                                              supervisor)
        probe.one.write_new(probe.PUBLIC_RESULT,
                            probe._public_result(supervisor, supervisor_sha),
                            0o644)
        with patch.object(probe, "_parent_bindings", return_value=(
                 {"status": "source_plan_auditable_only_in_original_evaluator_worktree"},
                 {"epoch_sha256": "a" * 64})), \
             patch.object(probe, "_source_sha256s", return_value={"source.py": "b" * 64}), \
             patch.object(probe, "PARENT_PUBLIC", self.ratification), \
             patch.object(probe, "SCOPE", self.ratification):
            self.assertEqual(probe.audit(self.ratification)["completed_boot_clones"], 1)
            (folder / "docker-logs.stdout.private.log").write_bytes(b"changed")
            with self.assertRaisesRegex(
                    probe.ProbeError,
                    "boot_probe_raw_startup_forensic_bytes_changed"):
                probe.audit(self.ratification)


if __name__ == "__main__":
    unittest.main()
