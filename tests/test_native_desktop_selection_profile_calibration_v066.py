"""No-model fake-provider gates for future 20-ID profile measurements."""

from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from native_desktop_factory import selection_profile_calibration_v066 as profiles
from native_desktop_factory.selection_worker_v066 import SelectionPackage
from native_desktop_factory.v066_final_freeze import digest


ROOT = Path(__file__).resolve().parents[1]
GUEST_PATH = ROOT / "docs/evidence/native-wdi-guest-content-identity-2026-09-27.json"
GUEST = json.loads(GUEST_PATH.read_bytes())
SOURCE = (ROOT / "native_desktop_factory/dev-fixtures/"
          "wdi-native-mex-calc-growth/wdi-native-mex-calc-growth.xlsx").read_bytes()
ORACLE = json.loads((ROOT / "native_desktop_factory/dev-fixtures/"
                     "wdi-native-mex-calc-growth/oracle.json").read_bytes())


def frame() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (1280, 800), "white").save(output, "PNG")
    return output.getvalue()


class FakeGuest:
    def __init__(self, task_id):
        self.sandbox_id = "fake-profile-" + task_id
        self.sandbox = object()
        self.neutral_input = None
        self.profile_sha256 = None
        self.guest_content_sha256 = None
        self.provider_shape_attested = False
        self.fresh_profile_absent = False
        self.raw_input_sha256 = None
        self.killed = False

    def prepare(self, *, source, filename, oracle, guest_identity):
        assert filename.endswith(".xlsx")
        self.neutral_input = source
        self.profile_sha256 = "a" * 64
        self.guest_content_sha256 = guest_identity["static_content_sha256"]
        self.provider_shape_attested = True
        self.fresh_profile_absent = True
        self.raw_input_sha256 = digest(source)

    def _screenshot(self):
        return frame()

    def close(self):
        self.killed = True
        return True


class FakeBackend:
    is_fake = True

    def __init__(self):
        self.creates = []

    def create(self, phase, lease_seconds, package):
        self.creates.append((phase, lease_seconds,
                             package.identity["task_id"]))
        return FakeGuest(package.identity["task_id"])


class ProfileCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="desktop-profile-fake-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.receipts_root = self.root / "receipts"
        self.packages = []
        for ordinal in range(1, 21):
            identity = {"task_id": f"synthetic-profile-{ordinal:03d}",
                        "package_sha256": f"{ordinal:064x}"}
            self.packages.append(SelectionPackage(
                identity=identity, source=SOURCE,
                oracle={**ORACLE, "split": "selection",
                        "task_id": identity["task_id"]},
                filename=identity["task_id"] + ".xlsx",
                instruction="Use the current GUI.",
                source_inventory_sha256="d" * 64))

    def test_offline_plan_counts_twenty_without_provider(self):
        backend = FakeBackend()
        with patch.object(profiles, "_packages",
                          return_value=self.packages):
            selected, plan = profiles.plan(
                candidate_root=self.root, private_map=self.root,
                expected_inventory_sha256="d" * 64,
                receipts_root=self.receipts_root)
        self.assertEqual(len(selected), 20)
        self.assertEqual(plan["fresh_selection_profiles_needed"], 20)
        self.assertEqual(plan["new_e2b_leases_planned"], 20)
        self.assertEqual(plan["new_full_lease_reserve_usd"],
                         "3.333333340")
        self.assertEqual(backend.creates, [])

    def test_existing_uncertain_intent_is_not_replayed(self):
        path = self.receipts_root / self.packages[0].identity["task_id"]
        path.mkdir(parents=True)
        (path / "intent.json").write_text("{}")
        with patch.object(profiles, "_packages",
                          return_value=self.packages):
            with self.assertRaisesRegex(ValueError,
                                        "existing_intent_or_receipt_uncertain"):
                profiles.plan(candidate_root=self.root,
                              private_map=self.root,
                              expected_inventory_sha256="d" * 64,
                              receipts_root=self.receipts_root)

    def test_fake_neutral_open_preserves_private_receipt_but_cannot_publish_manifest(self):
        backend = FakeBackend()
        package = self.packages[0]
        path = self.receipts_root / package.identity["task_id"]
        self.receipts_root.mkdir(mode=0o700)
        with patch.object(profiles, "_canonical_profile",
                          return_value="a" * 64), \
             patch.object(profiles.time, "sleep"):
            receipt = profiles.run_one(
                package=package, out_dir=path,
                guest_reference=GUEST, backend=backend)
        self.assertEqual(receipt["status"], "profile_baseline_passed")
        self.assertEqual(receipt["provider_kind"], "fake_offline")
        self.assertEqual(backend.creates,
                         [("selection-profile", 600,
                           package.identity["task_id"])])
        self.assertTrue((path / "neutral-open.png").is_file())
        self.assertTrue((path / "neutral-baseline.xlsx").is_file())
        with patch.object(profiles, "_packages",
                          return_value=[package]):
            with self.assertRaisesRegex(ValueError,
                                        "receipt_not_independently_accepted"):
                profiles.audit_manifest(
                    candidate_root=self.root, private_map=self.root,
                    expected_inventory_sha256="d" * 64,
                    receipts_root=self.receipts_root,
                    guest_reference_public=GUEST_PATH,
                    manifest_out=self.root / "profiles.private.json")

    def test_execute_refuses_while_live_final_sweep_is_not_terminal(self):
        with self.assertRaisesRegex(ValueError,
                                    "live_dispatch_not_authorized"):
            profiles.execute(
                candidate_root=self.root, private_map=self.root,
                expected_inventory_sha256="d" * 64,
                guest_reference_public=GUEST_PATH,
                receipts_root=self.receipts_root,
                manifest_out=self.root / "profiles.private.json",
                run_dir=self.root / "run",
                lane_reservation=self.root / "missing-lane.json",
                final_sweep_terminal=self.root / "missing-terminal.json")
        self.assertFalse(self.receipts_root.exists())

    def test_separate_four_dollar_lane_requires_terminal_final_journal(self):
        terminal = self.root / "final-terminal.private.json"
        terminal.write_bytes(profiles._canonical({
            "schema": "cua-native-wdi-v066-final-rerun-private-v1",
            "status": "started",
            "completed_utc": None,
        }))
        terminal.chmod(0o600)
        lane = self.root / "profile-lane.private.json"
        with self.assertRaisesRegex(ValueError,
                                    "still_live_or_unreconciled"):
            profiles.prepare_lane(
                path=lane, final_sweep_terminal=terminal,
                expected_inventory_sha256="d" * 64,
                guest_reference_sha256=digest(GUEST_PATH.read_bytes()))
        self.assertFalse(lane.exists())
        terminal.write_bytes(profiles._canonical({
            "schema": "cua-native-wdi-v066-final-rerun-private-v1",
            "status": "all_selected_trios_provisional",
            "completed_utc": "2026-09-28T00:00:00+00:00",
        }))
        receipt = profiles.prepare_lane(
            path=lane, final_sweep_terminal=terminal,
            expected_inventory_sha256="d" * 64,
            guest_reference_sha256=digest(GUEST_PATH.read_bytes()))
        self.assertEqual(receipt["initial_full_lease_reserve_usd"],
                         "3.333333340")
        self.assertEqual(receipt["lane_cap_usd"], "4.000000000")
        self.assertEqual(lane.stat().st_mode & 0o777, 0o600)
        profiles._validate_lane(
            lane, final_sweep_terminal=terminal,
            expected_inventory_sha256="d" * 64,
            guest_reference_sha256=digest(GUEST_PATH.read_bytes()))


if __name__ == "__main__":
    unittest.main()
