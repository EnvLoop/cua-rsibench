"""V2 train auditor validates the complete v0.6.6 action envelope."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from cursibench.scale_action_contract import VERSION
from native_desktop_factory import (
    v066_scoped_calc_writer_train_demo as demo,
    v066_scoped_calc_writer_train_demo_audit as old_audit,
    v066_scoped_calc_writer_train_demo_audit_v2 as audit,
)
from native_desktop_factory.v066_final_freeze import digest


class ScopedDemoAuditV2Tests(unittest.TestCase):
    def test_public_real_demo_aggregate_binds_v2_source_before_sft(self):
        root = Path(__file__).resolve().parents[1]
        public = json.loads((root / "docs/evidence" /
            "native-wdi-v066-calc-writer-train-demo-2026-09-28.json"
            ).read_bytes())
        self.assertEqual(public["corrected_read_only_v2_auditor_source_sha256"],
                         digest(Path(audit.__file__).read_bytes()))
        self.assertEqual(public["historical_bound_v1_auditor_source_sha256"],
                         digest(Path(old_audit.__file__).read_bytes()))
        self.assertFalse(public["source_bound_sft_exporters_completed"])
        self.assertEqual(public["official_final_admissions"], 0)

    def test_full_envelope_matches_then_rejects_task_frame_step_or_extra_key(self):
        package, oracle, _raw, _instruction, _filename = demo._source("calc")
        expected = demo.actor_actions("calc", oracle)[0]
        action = {**expected, "version": VERSION,
                  "task_id": package["task_id"],
                  "task_binding_sha256": package["package_sha256"],
                  "frame_id": "synthetic-current-frame", "step": 0,
                  "memory": ""}

        def row(value):
            return {"frame_id_sha256": digest(
                        "synthetic-current-frame".encode()),
                    "normalized_action_sha256": digest(json.dumps(
                        value, sort_keys=True,
                        separators=(",", ":")).encode())}

        self.assertTrue(audit._action_envelope_matches(
            step=row(action), normalized=action,
            expected=expected, package=package, index=0))
        for field, replacement in (("task_id", "other-task"),
                                   ("task_binding_sha256", "0" * 64),
                                   ("frame_id", "other-frame"),
                                   ("step", 1),
                                   ("memory", "unexpected memory"),
                                   ("extra", "shell")):
            with self.subTest(field=field):
                changed = {**action, field: replacement}
                self.assertFalse(audit._action_envelope_matches(
                    step=row(changed), normalized=changed,
                    expected=expected, package=package, index=0))

    def test_historical_bound_auditor_bytes_are_preserved(self):
        self.assertEqual(digest(Path(old_audit.__file__).read_bytes()),
                         "b0f0201c3deb4b08903be8171772f9fe23ea57d81bf1defe40da38ac4230104b")
