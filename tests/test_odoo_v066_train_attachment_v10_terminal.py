"""Retained TRAIN rejection evidence must prove the exact corner-only cause."""
from __future__ import annotations
import copy
from pathlib import Path
import tempfile
import unittest

from tests.test_odoo_v066_train_price_corner_route_v5 import OBSERVED, ALTERNATE, THIRD
from tools import record_odoo_v066_train_gui_v1 as recorder
from tools.audit_odoo_v066_train_attachment_calibration_v10 import CalibrationAuditError
from tools.audit_odoo_v066_train_attachment_v10_terminal import _negative_rejections


class NegativeTerminalTests(unittest.TestCase):
    def fixture(self):
        temp = tempfile.TemporaryDirectory()
        out = Path(temp.name) / "attempt"
        out.mkdir(mode=0o700)
        rejects, samples = [], []

        def save(name, value):
            path = out / name
            path.parent.mkdir(mode=0o700, exist_ok=True)
            ref = recorder._artifact(path.parent, path.name, value)
            ref["path"] = name
            return ref

        for i in range(3):
            observed, current = (OBSERVED, ALTERNATE) if i % 2 == 0 else (ALTERNATE, OBSERVED)
            prefix = "step-016" + (f"-resample-{i:02d}" if i else "")
            observed_ref = save(f"frames/{prefix}.png", observed)
            current_ref = save(f"frames/{prefix}-rejected-current.png", current)
            fid = f"{i + 1:064x}"
            probe = save(f"routes/probe-{i}.json", {
                "schema": "envloop-odoo-train-price-route-probe-v2", "status": "ready", "reason_code": "ready",
                "visible_price_input_count": 1, "strict_price_identity_present": True,
                "price_phase": "negative", "step": 16, "observation_serial": 18 + i,
                "task_binding_sha256": "a" * 64, "frame_sha256": observed_ref["sha256"], "frame_id_sha256": fid})
            decision = save(f"routes/decision-{i}.json", {
                "schema": "envloop-odoo-train-action-route-decision-v1", "status": "nonclaim",
                "reason_code": "physical_or_identity_guard_rejected", "route_kind": "price_editor",
                "route_token": None, "route_token_sha256": None, "probe_ref": probe,
                "frame_sha256": observed_ref["sha256"], "frame_id_sha256": fid})
            assistant = save(f"actions/{prefix}-assistant.json", {"type": "double_click", "target": {"x": 809, "y": 479}})
            rejects.append(save(f"actions/{prefix}-rejection.private.json", {
                "schema": "envloop-odoo-v066-route-pre-intent-rejection-v1", "phase": "negative", "step": 16,
                "observation_attempt": i, "error_code": "stale_frame", "pre_dispatch_intent_created": False,
                "gui_action_dispatched": False, "assistant_action_ref": assistant,
                "observed_frame_ref": observed_ref, "current_frame_ref": current_ref,
                "frame_id_sha256": fid, "route_probe_ref": probe, "route_decision_ref": decision}))
            for n, raw in enumerate((observed, current)):
                samples.append({"step": 16, "stage": "parse" if n == 0 else "parse_price_final", "sample": n,
                                "classification": "one_observed" if n == 0 else "unstable_first_final_rejected",
                                "observed_frame_sha256": observed_ref["sha256"], "observed_frame_id_sha256": fid,
                                "sampled_frame_ref": save(f"frames/guard-{2 * i + n:04d}.png", raw)})
        return temp, out, rejects, samples

    def test_exact_negative_cause_is_rederived(self):
        temp, out, refs, samples = self.fixture()
        with temp:
            routes, pair = _negative_rejections(out, refs, samples, "a" * 64)
            self.assertEqual(len(routes), 6)
            self.assertEqual(len(pair), 2)

    def test_completed_intent_cannot_be_reclassified_pre_intent(self):
        temp, out, refs, samples = self.fixture()
        with temp:
            recorder._artifact(out / "actions", "step-016-intent.private.json", {})
            with self.assertRaises(CalibrationAuditError):
                _negative_rejections(out, refs, samples, "a" * 64)

    def test_guard_sample_omission_or_classification_forgery_rejected(self):
        temp, out, refs, samples = self.fixture()
        with temp:
            for forged in (samples[:-1], [{**samples[0], "classification": "confirmed"}] + samples[1:]):
                with self.assertRaises(CalibrationAuditError):
                    _negative_rejections(out, refs, forged, "a" * 64)

    def test_third_material_sample_even_with_correct_hash_rejected(self):
        temp, out, refs, samples = self.fixture()
        with temp:
            path = out / "frames/material.png"
            ref = recorder._artifact(path.parent, path.name, THIRD)
            ref["path"] = "frames/material.png"
            forged = copy.deepcopy(samples)
            forged[1]["sampled_frame_ref"] = ref
            with self.assertRaises(CalibrationAuditError):
                _negative_rejections(out, refs, forged, "a" * 64)

    def test_other_task_binding_rejected(self):
        temp, out, refs, samples = self.fixture()
        with temp:
            with self.assertRaises(CalibrationAuditError):
                _negative_rejections(out, refs, samples, "b" * 64)


if __name__ == "__main__":
    unittest.main()
