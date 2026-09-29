"""Independent audit reopens the exact price-editor corner pair."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from tools.audit_odoo_v066_train_attachment_calibration_v8 import (
    CalibrationAuditError, _price_guard,
)
from tests.test_odoo_v066_train_price_corner_route_v5 import (
    OBSERVED, NEG_PRICE, NEG_SKU, PRICE, SKU, PriceCornerRouteTests,
)


CASE = {"id": "ELPO-TRN-0001", "lines": [{"sku": SKU,
                   "initial": {"price": float(PRICE)},
                   "expected": {"price": 172.77}}]}
WRONG = {"id": "ELPO-TRN-0002", "lines": [{"sku": NEG_SKU,
         "initial": {"price": float(NEG_PRICE)},
         "expected": {"price": float(NEG_PRICE)}}]}
BASELINE = {"orders": [{"id": 123, "name": CASE["id"]},
                       {"id": 124, "name": WRONG["id"]}]}


class PriceCornerAuditTests(unittest.TestCase):
    def fixture(self, phase="positive"):
        fixture = PriceCornerRouteTests()
        page, adapter, observation, raw, saved = fixture.setup_adapter(phase)
        action = adapter.parse_current_action(raw)
        applied = adapter.dispatch(action)
        temp = tempfile.TemporaryDirectory()
        out = Path(temp.name)
        out.chmod(0o700)
        frames = out / "frames"
        frames.mkdir(mode=0o700)
        frame = frames / "step-008.png"
        frame.write_bytes(OBSERVED)
        frame.chmod(0o600)
        for index, raw in enumerate(saved):
            path = frames / f"guard-{index:04d}.png"
            path.write_bytes(raw)
            path.chmod(0o600)
        receipt = applied["public_contract_receipt"]
        trace_action = {
            "phase": phase, "step": 8,
            "frame": {"path": "frames/step-008.png",
                      "sha256": sha256(OBSERVED).hexdigest()},
            "contract_receipt": receipt,
        }
        intent = {
            "frame_id": observation.frame_id,
            "observed_url": page.url,
            "normalized_action": action,
        }
        result = {"contract_receipt": receipt}
        return temp, out, trace_action, intent, result, adapter.frame_guard_samples

    def test_exact_pair_and_six_physical_frames(self):
        for phase in ("positive", "negative"):
            with self.subTest(phase=phase):
                temp, out, action, intent, result, samples = self.fixture(phase)
                with temp:
                    refs, count = _price_guard(
                        out, action, intent, result,
                        CASE, WRONG, BASELINE, samples)
                    self.assertEqual(count, 1)
                    self.assertEqual(len(refs), 6)

    def test_target_change_or_unstable_final_fails(self):
        temp, out, action, intent, result, samples = self.fixture()
        with temp:
            wrong = dict(action["contract_receipt"])
            wrong["price_parse_guard"] = {
                **wrong["price_parse_guard"],
                "target_identity": {
                    **wrong["price_parse_guard"]["target_identity"],
                    "sku": "EL-TRN-OTHER-001",
                },
            }
            with self.assertRaises(CalibrationAuditError):
                _price_guard(out, {**action, "contract_receipt": wrong},
                             intent, result, CASE, WRONG, BASELINE, samples)
            damaged = out / "frames/guard-0002.png"
            damaged.write_bytes(OBSERVED)
            damaged.chmod(0o600)
            with self.assertRaises(CalibrationAuditError):
                _price_guard(out, action, intent, result,
                             CASE, WRONG, BASELINE, samples)

    def test_wrong_phase_or_order_route_fails(self):
        temp, out, action, intent, result, samples = self.fixture("negative")
        with temp:
            with self.assertRaises(CalibrationAuditError):
                _price_guard(out, {**action, "phase": "positive"},
                             intent, result, CASE, WRONG, BASELINE, samples)
            with self.assertRaises(CalibrationAuditError):
                _price_guard(out, action,
                             {**intent, "observed_url":
                              "http://127.0.0.1:8069/odoo/purchase/999"},
                             result, CASE, WRONG, BASELINE, samples)


if __name__ == "__main__":
    unittest.main()
