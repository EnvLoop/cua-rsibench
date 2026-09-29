"""No-provider review, permit, and cold-reset mutation checks."""

from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PIL import Image

from native_desktop_factory import v066_post_enter_train_calibration_v1 as control
from native_desktop_factory import v066_post_enter_train_calibration_audit_v1 as audit


def _png() -> bytes:
    image = Image.new("RGB", (1280, 800), "white")
    output = BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


class ReviewTests(unittest.TestCase):
    def test_review_is_private_exact_and_never_creates_guest(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            freeze = root / "freeze.json"
            control._write_new(freeze, {"schema": "test"})
            value = {"work_root": str(root),
                     "output_root": str(root / "gui-diagnostics" / "episode"),
                     "source_sha256s": {"source": "a" * 64}}
            budget = {"past_attempt_or_batch_count": 0,
                      "past_conservative_reserved_usd": "0",
                      "proposed_reserved_usd": "0.5",
                      "combined_reserved_usd": "0.5",
                      "within_cap": True}
            storage = {"dispatch_storage_ready": True}
            review_path = root / "review.json"
            permit_path = root / "permit.json"
            with patch.object(audit, "validate_source", return_value=value), \
                    patch.object(audit, "_budget_summary", return_value=budget), \
                    patch.object(audit, "storage_audit", return_value=storage):
                result = audit.review(
                    freeze_path=freeze, review_path=review_path,
                    permit_path=permit_path, active_probe=lambda: (set(), 0))
                self.assertEqual(result["status"],
                                 "private_train_permit_written_without_provider_create")
                self.assertFalse(Path(value["output_root"]).exists())
                audit.checked_permit(
                    freeze_path=freeze, permit_path=permit_path, value=value)
                modified = json.loads(review_path.read_bytes())
                modified["provider_active_at_review"] = 1
                review_path.write_text(json.dumps(modified))
                with self.assertRaisesRegex(ValueError, "permit changed"):
                    audit.checked_permit(
                        freeze_path=freeze, permit_path=permit_path, value=value)

    def test_run_has_no_implicit_paid_entry(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "explicit enablement"):
                control.run(freeze_path=root / "freeze.json",
                            permit_path=root / "permit.json")
            self.assertEqual(list(root.iterdir()), [])

    def test_root_owned_run_uses_exact_two_instrumented_train_guests(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            (work / "gui-diagnostics").mkdir(parents=True)
            output = work / "gui-diagnostics" / "episode"
            freeze = root / "freeze.json"
            permit = root / "permit.json"
            control._write_new(freeze, {"schema": "test"})
            control._write_new(permit, {"schema": "test"})
            value = {"output_root": str(output), "work_root": str(work),
                     "guest_public": str(root / "guest.json"),
                     "scoped_reference": str(root / "reference.json"),
                     "reservation_path": str(root / "reservation.json")}
            seen = []
            from e2b_desktop import Sandbox
            def fake_create(**_kwargs):
                guest = object()
                seen.append(guest)
                return guest
            def fake_demos(*, output_root, **_kwargs):
                output_root.mkdir()
                (output_root / "calc").mkdir()
                (output_root / "writer").mkdir()
                self.assertIsInstance(Sandbox.create(), control.PostEnterProbeProxy)
                self.assertIs(Sandbox.create(), seen[-1])
                return {"status": "two_public_train_gui_positives_pending_audit"}
            with patch.object(control, "validate_source", return_value=value), \
                    patch.object(control, "_checked_permit"), \
                    patch.object(control, "_runtime_preflight"), \
                    patch.object(Sandbox, "create", side_effect=fake_create), \
                    patch.object(control.demo, "run_both", side_effect=fake_demos), \
                    patch.object(control.demo_audit, "audit_both"), \
                    patch.object(control, "_cold_reset", return_value={
                        "status": "cold_reset_observed"}), \
                    patch.object(audit, "audit", return_value={"status": "audited"}):
                result = control.run(
                    freeze_path=freeze, permit_path=permit,
                    enable_paid_train_calibration=True)
            self.assertEqual(result["status"],
                             "three_train_guests_independently_audited")
            self.assertEqual(len(seen), 2)
            self.assertTrue((work / "gui-diagnostics" /
                             "episode.calibration-run.private.json").is_file())


class FakeColdGuest:
    sandbox_id = "distinct-fake-cold-guest"

    def __init__(self, guest, baseline):
        self.guest = guest
        self.baseline = baseline
        self.memory = {}
        self.files = self
        self.commands = self
        self.killed = False

    def get_info(self, **_kwargs):
        class Info:
            pass
        info = Info()
        info.template_id = self.guest["provider_template_id"]
        info.envd_version = self.guest["provider_envd_version"]
        info.cpu_count = self.guest["provider_shape"]["vcpu"]
        info.memory_mb = self.guest["provider_shape"]["memory_mb"]
        return info

    def write(self, name, raw):
        self.memory[name] = raw

    def read(self, name, **_kwargs):
        return self.memory[name]

    def run(self, command, **_kwargs):
        class Result:
            pass
        result = Result()
        result.exit_code = 0
        result.stdout = json.dumps({
            "content_tree_sha256": self.guest["static_content_sha256"],
            "counts": self.guest["static_content_counts"],
            "kernel": self.guest["kernel_identity"],
            "excluded_paths": self.guest["static_content_excluded_paths"],
        })
        return result

    def open(self, _filename):
        pass

    def press(self, _key):
        pass

    def screenshot(self):
        return _png()

    def kill(self):
        self.killed = True
        return True

    def is_running(self, **_kwargs):
        return False


class ColdResetTests(unittest.TestCase):
    def test_fresh_guest_restores_original_train_bytes_and_kills(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "gui-diagnostics" / "episode"
            output.mkdir(parents=True)
            package, _oracle, baseline, _instruction, _filename = control.demo._source("calc")
            guest = {
                "provider_template_id": "desktop",
                "provider_envd_version": "pinned",
                "provider_shape": {"vcpu": 2, "memory_mb": 2048},
                "static_content_sha256": "a" * 64,
                "static_content_counts": {},
                "kernel_identity": "test",
                "static_content_excluded_paths": [],
            }
            guest_path = root / "guest.json"
            guest_path.write_text(json.dumps(guest))
            freeze = root / "freeze.json"
            permit = root / "permit.json"
            control._write_new(freeze, {"schema": "test"})
            control._write_new(permit, {"schema": "test"})
            value = {"output_root": str(output), "work_root": str(root),
                     "guest_public": str(guest_path),
                     "scoped_reference": str(root / "reference.json")}
            fake = FakeColdGuest(guest, baseline)
            def attest(*, receipt, persist, **_kwargs):
                receipt["task_profile_scoped_attested"] = True
                receipt["task_profile_scoped_snapshots"] = []
                persist()
            with patch.object(control, "active_hashes", return_value=(set(), 0)), \
                    patch.object(control, "budget_audit", return_value={
                        "within_cap": True}), \
                    patch.object(control, "validate_reference", return_value=(
                        {"applications": {"calc": {}}}, "a" * 64)), \
                    patch.object(control, "wait_for_document_ready", return_value={
                        "ready_after_seconds": 0}), \
                    patch.object(control.profile_guard, "attest", side_effect=attest), \
                    patch.object(control.time, "sleep"):
                result = control._cold_reset(
                    value=value, freeze_path=freeze,
                    permit_path=permit,
                    sandbox_factory=lambda **_kwargs: fake)
            self.assertEqual(result["status"], "cold_reset_observed")
            self.assertTrue(fake.killed)
            self.assertEqual(result["restored_state_sha256"], control.digest(baseline))
            self.assertTrue((output / "cold-reset/intent.json").is_file())
            self.assertTrue((output / "cold-reset/cold-neutral-open.png").is_file())
            self.assertEqual((output / "cold-reset/restored-original.xlsx").read_bytes(),
                             baseline)
            (output / "cold-reset/restored-original.xlsx").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "frame changed"):
                audit._bound(output, result["restored_artifact"])


if __name__ == "__main__":
    unittest.main()
