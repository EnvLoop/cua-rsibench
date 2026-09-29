"""Offline source, resume, and independent raw-evidence regression tests."""

from __future__ import annotations

from hashlib import sha256
import io
import json
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image
from cursibench.scale_action_output_v066 import normalize_model_action

from native_desktop_factory import qwen_v066_adapter
from native_desktop_factory import v066_train20_audit as audit
from native_desktop_factory import v066_train20_plan as plan
from native_desktop_factory import v066_train20_worker as worker
from native_desktop_factory.verify import verify


FIXTURE = (Path(__file__).resolve().parents[1] / "native_desktop_factory" /
           "dev-fixtures" / "wdi-native-mex-calc-growth")


def _write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    path.chmod(0o600)


def _ref(root: Path, path: Path, raw: bytes) -> dict:
    _write(path, raw)
    return {"private_path": str(path.relative_to(root)), "bytes": len(raw),
            "sha256": plan.digest(raw)}


class TestTrain20(unittest.TestCase):
    def test_deterministic_source_group_holdout_and_rejects_duplicates(self):
        workflows = ("calc-growth", "calc-risk", "impress-deck", "writer-brief")
        rows = [{"task_id": f"{country}-{workflow}",
                 "source_group": country, "workflow": workflow,
                 "package_sha256": sha256(f"{country}-{workflow}".encode()).hexdigest()}
                for country in ("A", "B", "C", "D", "E")
                for workflow in workflows]
        first = plan.assign_roles(rows, "a" * 64)
        self.assertEqual(first, plan.assign_roles(list(reversed(rows)), "a" * 64))
        sft, holdout, full_family = first
        self.assertEqual((len(sft), len(holdout)), (15, 5))
        self.assertEqual(sum(row["source_group"] == full_family for row in holdout), 4)
        self.assertEqual({row["workflow"] for row in holdout}, set(workflows))
        self.assertFalse({row["task_id"] for row in sft} &
                         {row["task_id"] for row in holdout})
        with self.assertRaises(ValueError):
            plan.assign_roles([*rows[:-1], rows[0]], "a" * 64)

    def test_intent_is_exclusive_and_holdout_or_battery_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "evidence"
            row = {"task_id": "train-a", "package_sha256": "a" * 64,
                   "input_sha256": "b" * 64, "action_script_sha256": "c" * 64}
            frozen = {"sft_task_ids": ["train-a"],
                      "holdout_task_ids": ["holdout-b"],
                      "planning_usd_per_hour_upper": "1.00"}
            with patch.object(worker, "ac_power_ready", return_value=False):
                with self.assertRaisesRegex(ValueError, "AC power"):
                    worker.create_intent(root=root, row=row, plan=frozen,
                                         plan_sha="d" * 64,
                                         require_provider=False)
            self.assertFalse(root.exists())
            path = worker.create_intent(root=root, row=row, plan=frozen,
                                        plan_sha="d" * 64,
                                        require_ac=False, require_provider=False)
            self.assertEqual((path / "intent.json").stat().st_mode & 0o777, 0o600)
            with self.assertRaisesRegex(ValueError, "replayed"):
                worker.create_intent(root=root, row=row, plan=frozen,
                                     plan_sha="d" * 64,
                                     require_ac=False, require_provider=False)
            row["task_id"] = "holdout-b"
            with self.assertRaisesRegex(ValueError, "Holdout"):
                worker.create_intent(root=root, row=row, plan=frozen,
                                     plan_sha="d" * 64,
                                     require_ac=False, require_provider=False)

    def test_battery_authorized_intent_keeps_power_telemetry(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "evidence"
            row = {"task_id": "train-a", "package_sha256": "a" * 64,
                   "input_sha256": "b" * 64,
                   "action_script_sha256": "c" * 64}
            frozen = {"sft_task_ids": ["train-a"],
                      "holdout_task_ids": [],
                      "planning_usd_per_hour_upper": "1.00"}
            observed = {"source": "Battery Power", "battery_percent": 71,
                        "probe_sha256": "e" * 64,
                        "captured_utc": "2026-09-29T00:00:00+00:00"}
            with patch.dict(worker.os.environ, {"E2B_API_KEY": "test"}), \
                 patch.object(worker, "active_hashes", return_value=(set(), 0)), \
                 patch.object(worker, "host_power_snapshot",
                              return_value=observed):
                with self.assertRaisesRegex(ValueError, "authorization"):
                    worker.create_intent(
                        root=root, row=row, plan=frozen,
                        plan_sha="d" * 64, require_ac=False,
                        require_provider=True)
                self.assertEqual(len(list(root.glob("*/intent.json"))), 0)
                out = worker.create_intent(
                    root=root, row=row, plan=frozen,
                    plan_sha="d" * 64, require_ac=False,
                    require_provider=True, battery_authorized=True)
            intent = json.loads((out / "intent.json").read_bytes())
            self.assertTrue(intent["battery_authorized"])
            self.assertEqual(intent["host_power_before_intent"], observed)

    def test_host_power_parser_rejects_unknown_and_keeps_percent(self):
        output = "Now drawing from 'Battery Power'\n -InternalBattery-0 71%; discharging"
        with patch.object(worker.subprocess, "run", return_value=
                          SimpleNamespace(returncode=0, stdout=output)):
            observed = worker.host_power_snapshot()
        self.assertEqual(observed["source"], "Battery Power")
        self.assertEqual(observed["battery_percent"], 71)
        with patch.object(worker.subprocess, "run", return_value=
                          SimpleNamespace(returncode=0, stdout="unknown")):
            with self.assertRaisesRegex(ValueError, "telemetry"):
                worker.host_power_snapshot()

    def _fake_evidence(self, root: Path):
        task_id = "wdi-native-mex-calc-growth"
        candidate = root / "candidates"
        package_dir = candidate / "train" / task_id
        package_dir.mkdir(parents=True)
        for name in ("package.json", "oracle.json", "actor_task.txt",
                     task_id + ".xlsx"):
            shutil.copy2(FIXTURE / name, package_dir / name)
        manifest = json.loads((package_dir / "package.json").read_bytes())
        oracle = json.loads((package_dir / "oracle.json").read_bytes())
        baseline = (package_dir / (task_id + ".xlsx")).read_bytes()
        actions = plan.actions_for_train(manifest, oracle)
        row = {"task_id": task_id, "workflow": manifest["workflow"],
               "package_sha256": manifest["package_sha256"],
               "input_sha256": plan.digest(baseline),
               "action_script_sha256": plan.digest(plan.encode(actions)),
               "relative_package_path": f"train/{task_id}"}
        evidence = root / "evidence"
        out = evidence / task_id
        out.mkdir(parents=True, mode=0o700)
        out.chmod(0o700)
        frozen = {"sft_task_ids": [task_id], "holdout_task_ids": [],
                  "guest_identity_public_sha256": "f" * 64}
        frozen_sha = "d" * 64
        intent = {"schema": worker.INTENT_SCHEMA, "split": "train",
                  "diagnostic_role": "sft_source", "task_id": task_id,
                  "plan_sha256": frozen_sha,
                  "package_sha256": row["package_sha256"],
                  "input_sha256": row["input_sha256"],
                  "action_script_sha256": row["action_script_sha256"],
                  "runner_sha256": plan.digest(Path(worker.__file__).read_bytes()),
                  "lease_seconds": 600, "automatic_replay_authorized": False,
                  "battery_authorized": False,
                  "host_power_before_intent": {
                      "source": "test_unverified", "battery_percent": None,
                      "probe_sha256": None, "captured_utc": None}}
        intent_raw = plan.encode(intent)
        _write(out / "intent.json", intent_raw)
        image = io.BytesIO()
        Image.new("RGB", (1280, 800), "white").save(image, format="PNG")
        screenshot = image.getvalue()
        steps = []
        instruction = (package_dir / "actor_task.txt").read_text()
        previous = None
        for index, action in enumerate(actions):
            frame = qwen_v066_adapter.observe(
                audit._Frame(screenshot), task_id=task_id,
                task_binding_sha256=row["package_sha256"],
                instruction=instruction, step=index,
                previous_action_result=previous,
                max_actions=worker.MAX_ACTIONS)
            payload = json.dumps(action, separators=(",", ":"))
            normalized = normalize_model_action(
                payload, frame, current_frame_id=frame.frame_id)
            steps.append({"step": index, "frame_attempt": 0,
                          "frame_id_sha256": plan.digest(frame.frame_id.encode()),
                          "observation": _ref(evidence, out / f"frame-{index:02d}-0.png", screenshot),
                          "predispatch": _ref(evidence, out / f"predispatch-{index:02d}-0.png", screenshot),
                          "normalized_action": normalized,
                          "normalized_action_sha256": plan.digest(plan.encode(normalized)),
                          "action_payload_sha256": plan.digest(payload.encode()),
                          "dispatch_type": action["type"], "status": "applied"})
            previous = {"status": "applied", "code": "ok"}
        snapshots = []
        for label in ("first", "second"):
            snapshots.append({"label": label,
                              "manifest": _ref(evidence, out / f"profile-{label}.manifest.json", b"{}"),
                              "registry": _ref(evidence, out / f"profile-{label}.registry.xml", b"<r/>"),
                              "visible_frame": _ref(evidence, out / f"profile-{label}.png", screenshot),
                              "profile_probe_script_sha256": plan.digest(
                                  audit.runtime_fingerprint_probe.PROFILE_FILE_PROBE.encode()),
                              "scoped_profile_sha256": "profile"})
        saved = (FIXTURE / "controls" / "positive.xlsx").read_bytes()
        receipt = {"schema": worker.RECEIPT_SCHEMA,
                   "purpose": "evaluator_scripted_sft_source_no_model",
                   "split": "train", "task_id": task_id,
                   "plan_sha256": frozen_sha, "intent_sha256": plan.digest(intent_raw),
                   "battery_authorized": False,
                   "host_power_before_intent": intent["host_power_before_intent"],
                   "package_sha256": row["package_sha256"],
                   "input_sha256": row["input_sha256"],
                   "action_script_sha256": row["action_script_sha256"],
                   "runner_sha256": plan.digest(Path(worker.__file__).read_bytes()),
                   "adapter_sha256": plan.digest(Path(qwen_v066_adapter.__file__).read_bytes()),
                   "guest_identity_public_sha256": "f" * 64,
                   "profile_guard_sha256": plan.digest(Path(audit.profile_guard.__file__).read_bytes()),
                   "status": "train_gui_positive_passed", "guest_content_attested": True,
                   "fresh_profile_absent": True, "kill_returned": True,
                   "is_running_after_kill": False, "official_final_admissions": 0,
                   "official_model_results": 0, "sandbox_id_sha256": "e" * 64,
                   "provider_kind": "fake_test_only", "expected_actor_action_count": len(actions),
                   "scoped_reference_sha256": "a" * 64,
                   "profile_reference_private_sha256": "a" * 64,
                   "profile_application_kind": "calc",
                   "task_profile_scoped_attested": True,
                   "task_profile_scoped_self_stable": True,
                   "task_profile_scoped_matches_public_train": True,
                   "task_profile_scoped_sha256": "profile",
                   "task_profile_scoped_snapshots": snapshots,
                   "actor_steps": steps, "physical_frame_resamples": [],
                   "saved_artifact": _ref(evidence, out / "saved.xlsx", saved),
                   "saved_sha256": plan.digest(saved),
                   "independent_saved_verifier": verify(baseline, saved, oracle)}
        _write(out / "receipt.json", plan.encode(receipt))
        return candidate, evidence, frozen, frozen_sha, row, out

    def test_independent_audit_reopens_raw_frames_and_saved_ooxml(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate, evidence, frozen, frozen_sha, row, out = self._fake_evidence(Path(temporary))
            with patch.object(audit, "validate_reference", return_value=(
                    {"applications": {"calc": "profile"}}, "a" * 64)), \
                 patch.object(audit.scope, "scoped_profile", return_value="profile"):
                result = audit.audit_one(
                    candidate_root=candidate, evidence_root=evidence,
                    plan=frozen, plan_sha=frozen_sha, row=row,
                    scoped_reference=Path("unused"), require_real_provider=False)
                self.assertEqual(result["action_count"], 12)
                with self.assertRaisesRegex(ValueError, "Fake provider"):
                    audit.audit_one(candidate_root=candidate, evidence_root=evidence,
                                    plan=frozen, plan_sha=frozen_sha, row=row,
                                    scoped_reference=Path("unused"))
                first_frame = (out / "frame-00-0.png").read_bytes()
                (out / "frame-00-0.png").write_bytes(b"tampered")
                with self.assertRaisesRegex(ValueError, "bytes changed"):
                    audit.audit_one(candidate_root=candidate, evidence_root=evidence,
                                    plan=frozen, plan_sha=frozen_sha, row=row,
                                    scoped_reference=Path("unused"),
                                    require_real_provider=False)
                _write(out / "frame-00-0.png", first_frame)
                saved = (out / "saved.xlsx").read_bytes()
                _write(out / "saved.xlsx", b"tampered")
                with self.assertRaisesRegex(ValueError, "bytes changed"):
                    audit.audit_one(candidate_root=candidate, evidence_root=evidence,
                                    plan=frozen, plan_sha=frozen_sha, row=row,
                                    scoped_reference=Path("unused"),
                                    require_real_provider=False)
                _write(out / "saved.xlsx", saved)
                receipt = json.loads((out / "receipt.json").read_bytes())
                receipt["actor_steps"][0]["normalized_action"]["target"]["x"] += 1
                _write(out / "receipt.json", plan.encode(receipt))
                with self.assertRaisesRegex(ValueError, "action envelope changed"):
                    audit.audit_one(candidate_root=candidate, evidence_root=evidence,
                                    plan=frozen, plan_sha=frozen_sha, row=row,
                                    scoped_reference=Path("unused"),
                                    require_real_provider=False)

    def test_failed_identity_cannot_be_automatically_replayed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence = root / "evidence"
            frozen = {"train_rows": [{"task_id": "train-a"}],
                      "sft_task_ids": ["train-a"], "holdout_task_ids": []}
            def intent(**_kwargs):
                (evidence / "train-a").mkdir(parents=True)
            with patch.object(worker, "validate_plan", return_value=(frozen, "a" * 64)), \
                 patch.object(worker, "create_intent", side_effect=intent), \
                 patch.object(worker, "execute_one", return_value={
                     "status": "train_gui_failed_or_infrastructure_invalid"}) as execute, \
                 patch.object(audit, "audit_one", side_effect=ValueError("failed evidence")):
                result = worker.collect(
                    repo_root=root, candidate_root=root, evidence_root=evidence,
                    plan_path=root / "plan", guest_public=root / "guest",
                    scoped_reference=root / "reference",
                    ratification=root / "ratification", max_new=1,
                    enable_paid_train20=True)
                self.assertEqual(result["status"],
                                 "stopped_after_failed_or_uncertain_id")
                with self.assertRaisesRegex(ValueError, "failed evidence"):
                    worker.collect(
                        repo_root=root, candidate_root=root, evidence_root=evidence,
                        plan_path=root / "plan", guest_public=root / "guest",
                        scoped_reference=root / "reference",
                        ratification=root / "ratification", max_new=1,
                        enable_paid_train20=True)
                self.assertEqual(execute.call_count, 1)

    def test_fake_guest_executes_current_frame_actions_and_saved_readback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate, _unused, _frozen, _sha, row, _out = self._fake_evidence(root)
            manifest = json.loads((candidate / row["relative_package_path"] /
                                   "package.json").read_bytes())
            row.update({"oracle_sha256": manifest["oracle_sha256"],
                        "instruction_sha256": manifest["actor_task_sha256"],
                        "source_group": manifest["source_groups"][0]})
            evidence = root / "new-evidence"
            frozen = {"sft_task_ids": [row["task_id"]],
                      "holdout_task_ids": [], "train_rows": [row],
                      "planning_usd_per_hour_upper": "1.00",
                      "scoped_reference_sha256": "a" * 64}
            out = worker.create_intent(root=evidence, row=row, plan=frozen,
                                       plan_sha="d" * 64,
                                       require_ac=False, require_provider=False)
            saved_positive = (FIXTURE / "controls/positive.xlsx").read_bytes()
            guest = {"provider_template_id": "desktop-test",
                     "provider_envd_version": "test-envd",
                     "provider_shape": {"vcpu": 2, "memory_mb": 4096},
                     "static_content_sha256": "f" * 64,
                     "static_content_counts": {"files": 1},
                     "kernel_identity": "test-kernel",
                     "static_content_excluded_paths": []}
            guest_path = root / "guest.json"
            guest_path.write_text(json.dumps(guest))

            class Files:
                def __init__(self):
                    self.data = {}

                def write(self, path, raw):
                    self.data[path] = raw

                def read(self, path, format="bytes"):
                    return self.data[path]

            class Commands:
                def run(self, command, **_kwargs):
                    if command.startswith("sudo -n python3"):
                        return SimpleNamespace(exit_code=0, stdout=json.dumps({
                            "content_tree_sha256": guest["static_content_sha256"],
                            "counts": guest["static_content_counts"],
                            "kernel": guest["kernel_identity"],
                            "excluded_paths": guest["static_content_excluded_paths"]}))
                    return SimpleNamespace(exit_code=0, stdout="")

            class Guest:
                sandbox_id = "fake-guest-one"

                def __init__(self):
                    self.files = Files()
                    self.commands = Commands()
                    self.remote = None
                    self.killed = False

                def get_info(self, **_kwargs):
                    return SimpleNamespace(template_id="desktop-test", cpu_count=2,
                                           memory_mb=4096, envd_version="test-envd")

                def open(self, remote):
                    self.remote = remote

                def screenshot(self):
                    return screenshot

                def press(self, keys):
                    if keys == ["ctrl", "s"]:
                        self.files.data[self.remote] = saved_positive

                def left_click(self, *_point):
                    pass

                def double_click(self, *_point):
                    pass

                def write(self, _text):
                    pass

                def kill(self):
                    self.killed = True
                    return True

                def is_running(self, **_kwargs):
                    return not self.killed

            png = io.BytesIO()
            Image.new("RGB", (1280, 800), "white").save(png, format="PNG")
            screenshot = png.getvalue()
            guest_instance = Guest()

            def attest(**kwargs):
                receipt = kwargs["receipt"]
                receipt["task_profile_scoped_attested"] = True
                kwargs["persist"]()

            with patch.object(worker, "wait_for_document_ready", return_value={"ready": True}), \
                 patch.object(worker.profile_guard, "attest", side_effect=attest), \
                 patch("time.sleep", return_value=None):
                receipt = worker.execute_one(
                    candidate_root=candidate, evidence_root=evidence,
                    row=row, plan=frozen, plan_sha="d" * 64,
                    guest_public=guest_path, scoped_reference=root / "reference.json",
                    sandbox_factory=lambda **_kwargs: guest_instance)
            self.assertEqual(receipt["status"], "train_gui_positive_passed")
            self.assertEqual(len(receipt["actor_steps"]), 12)
            self.assertTrue(all(step["status"] == "applied" for step in receipt["actor_steps"]))
            self.assertEqual((out / "saved.xlsx").read_bytes(), saved_positive)
            self.assertEqual(receipt["provider_kind"], "fake_test_only")
            self.assertFalse(receipt["is_running_after_kill"])
            with self.assertRaisesRegex(ValueError, "consumed"):
                worker.execute_one(candidate_root=candidate,
                                   evidence_root=evidence, row=row, plan=frozen,
                                   plan_sha="d" * 64, guest_public=guest_path,
                                   scoped_reference=root / "reference.json",
                                   sandbox_factory=lambda **_kwargs: guest_instance)


if __name__ == "__main__":
    unittest.main()
