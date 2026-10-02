"""The independent success auditor reopens every viewer-close frame."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from tools.audit_odoo_v066_train_attachment_calibration_v6 import (
    CalibrationAuditError, _viewer_guard,
)
from tests.test_odoo_v066_train_viewer_close_route_v3 import (
    SOURCE_LABEL, VIEWER, ViewerCloseRouteTests,
)


class ViewerCloseAuditTests(unittest.TestCase):
    def fixture(self):
        fixture = ViewerCloseRouteTests()
        page, adapter, observation, raw, saved = fixture.setup_adapter()
        action = adapter.parse_current_action(raw)
        applied = adapter.dispatch(action)
        directory = tempfile.TemporaryDirectory()
        root = Path(directory.name)
        root.chmod(0o700)
        frames = root / "frames"
        frames.mkdir(mode=0o700)
        observed_path = frames / "step-006.png"
        observed_path.write_bytes(VIEWER)
        observed_path.chmod(0o600)
        for index, png in enumerate(saved):
            path = frames / f"guard-{index:04d}.png"
            path.write_bytes(png)
            path.chmod(0o600)
        receipt = applied["public_contract_receipt"]
        trace_action = {
            "phase": "positive", "step": 6,
            "frame": {"path": "frames/step-006.png",
                      "sha256": sha256(VIEWER).hexdigest()},
            "contract_receipt": receipt,
        }
        intent = {
            "frame_id": observation.frame_id,
            "observed_url": page.url,
            "task_binding_sha256": observation.task_binding_sha256,
            "normalized_action": action,
        }
        result = {"contract_receipt": receipt}
        return directory, root, trace_action, intent, result, adapter.frame_guard_samples

    def test_exact_guard_and_post_close_rfq_frame(self):
        temp, root, action, intent, result, samples = self.fixture()
        with temp:
            refs, count = _viewer_guard(
                root, action, intent, result, SOURCE_LABEL, samples)
            self.assertEqual(count, 1)
            self.assertEqual(len(refs), 7)

    def test_wrong_viewer_identity_and_missing_return_fail(self):
        temp, root, action, intent, result, samples = self.fixture()
        with temp:
            changed = dict(action["contract_receipt"])
            changed["viewer_parse_guard"] = {
                **changed["viewer_parse_guard"],
                "viewer_identity": {
                    **changed["viewer_parse_guard"]["viewer_identity"],
                    "source_label": "other.pdf",
                },
            }
            with self.assertRaises(CalibrationAuditError):
                _viewer_guard(root, {**action, "contract_receipt": changed},
                              intent, result, SOURCE_LABEL, samples)
            missing = [sample for sample in samples
                       if sample["stage"] != "viewer_return"]
            with self.assertRaises(CalibrationAuditError):
                _viewer_guard(root, action, intent, result,
                              SOURCE_LABEL, missing)


if __name__ == "__main__":
    unittest.main()
