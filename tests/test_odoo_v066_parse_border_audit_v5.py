"""Offline forged-evidence rejection for the v5 independent parse auditor."""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from tools import audit_odoo_v066_parse_border_v5 as audit


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def png(image: Image.Image) -> bytes:
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def save(root: Path, path: str, raw: bytes) -> dict:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    return {"path": path, "sha256": digest(raw)}


class ParseAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        first = Image.new("RGB", (1440, 1000), (255, 255, 255))
        for point in audit.PIXELS:
            first.putpixel(point, (235, 237, 239))
        second = first.copy()
        for point in audit.PIXELS:
            second.putpixel(point, (235, 237, 240))
        self.observed = png(first)
        self.physical = png(second)
        frame = save(self.root, "frames/step-000.png", self.observed)
        guard = [save(self.root, f"frames/guard-{i:04d}.png",
                      self.physical) for i in range(6)]
        final = save(self.root, "frames/parse-final.png", self.physical)
        dispatch = save(self.root, "frames/dispatch.png", self.physical)
        self.url = "http://127.0.0.1:8069/odoo/purchase/123"
        self.row = {"task_id": "synthetic-id", "package_sha256": "a" * 64,
                    "task_binding_sha256": "b" * 64}
        target = {"x": 1307, "y": 868}
        control = {"ref": "c100", "role": "button",
                   "label": "Attach Files", "visible": True,
                   "enabled": True, "purchase_rfq_view": True,
                   "bounds": [1280, 850, 1335, 885]}
        action = {"type": "click", "target": target,
                  "task_id": self.row["task_id"],
                  "task_binding_sha256": self.row["package_sha256"],
                  "frame_id": "synthetic-frame"}
        self.intent = {
            "step": 0, "task_id": self.row["task_id"],
            "task_binding_sha256": self.row["package_sha256"],
            "frame_sha256": frame["sha256"],
            "normalized_action": action,
            "dispatch_state": "intent_durable_before_gui_action",
            "observed_url": self.url,
            "observation_controls": [{key: control[key] for key in
                                      ("ref", "role", "label", "visible",
                                       "enabled")}],
            "observed_target_control": control,
        }
        self.contract = {
            "screenshot": {"sha256": frame["sha256"]},
            "task_binding_sha256": self.row["package_sha256"],
            "task_id_sha256": digest(self.row["task_id"].encode()),
            "frame_id_sha256": digest(b"synthetic-frame"),
            "parse_guard": {
                "profile": audit.PARSE_PROFILE,
                "classification": audit.PARSE_ALT,
                "observed_frame_sha256": frame["sha256"],
                "observed_frame_id_sha256": digest(b"synthetic-frame"),
                "physical_frame_ref": final,
                "observed_url": self.url, "physical_url": self.url,
                "sample_count": 6, "target_point": target,
                "target_control_before": control,
                "target_control_after": control,
                "pinned_pixel_coordinates": [[41, 419], [132, 419]],
            },
            "physical_dispatch_guard": {
                "classification": audit.PINNED,
                "observed_frame_sha256": frame["sha256"],
                "observed_frame_id_sha256": digest(b"synthetic-frame"),
                "physical_frame_ref": dispatch,
                "observed_url": self.url, "physical_url": self.url,
                "target_point": target, "target_control": control,
                "pinned_pixel_coordinates": [[41, 419], [132, 419]],
            },
        }
        self.trace = {
            "task_binding_sha256": self.row["task_binding_sha256"],
            "sft_examples_written": 0,
            "actions": [{"step": 0, "phase": "positive", "frame": frame,
                         "contract_receipt": self.contract}],
            "exact_return_guard_samples": [
                {"step": 0, "stage": "parse", "sample": index,
                 "classification":
                     "one_recurring_micro_raster_alternate",
                 "observed_frame_sha256": frame["sha256"],
                 "observed_frame_id_sha256": digest(b"synthetic-frame"),
                 "sampled_frame_ref": reference}
                for index, reference in enumerate(guard)] + [
                    {"step": 0, "stage": "parse_final", "sample": 6,
                     "classification": audit.PARSE_ALT,
                     "observed_frame_sha256": frame["sha256"],
                     "observed_frame_id_sha256":
                         digest(b"synthetic-frame"),
                     "sampled_frame_ref": final}],
        }
        self.write_intent_result()

    def write_intent_result(self) -> None:
        raw = json.dumps(self.intent, sort_keys=True).encode()
        save(self.root, "actions/step-000-intent.private.json", raw)
        result = {"step": 0, "intent_sha256": digest(raw),
                  "contract_receipt": self.contract,
                  "applied_action": self.intent["normalized_action"]}
        save(self.root, "actions/step-000-result.private.json",
             json.dumps(result, sort_keys=True).encode())

    def test_frozen_two_pixel_parse_and_dispatch_pass(self) -> None:
        result = audit.audit_trace(self.root, self.trace, self.row)
        self.assertEqual(result["pinned_border_parse_exceptions"], 1)

    def test_changed_control_rejected(self) -> None:
        self.contract["parse_guard"]["target_control_after"] = {
            **self.contract["parse_guard"]["target_control_after"],
            "label": "Other"}
        self.write_intent_result()
        with self.assertRaises(audit.ParseAuditError):
            audit.audit_trace(self.root, self.trace, self.row)

    def test_changed_physical_png_and_url_rejected(self) -> None:
        third = Image.open(BytesIO(self.physical)).copy()
        third.putpixel((800, 800), (0, 0, 0))
        self.contract["parse_guard"]["physical_frame_ref"] = save(
            self.root, "frames/forged-final.png", png(third))
        self.write_intent_result()
        with self.assertRaises(audit.ParseAuditError):
            audit.audit_trace(self.root, self.trace, self.row)
        self.contract["parse_guard"]["physical_frame_ref"] = save(
            self.root, "frames/parse-final.png", self.physical)
        self.contract["parse_guard"]["physical_url"] = \
            "http://127.0.0.1:8069/odoo/sales/123"
        self.write_intent_result()
        with self.assertRaises(audit.ParseAuditError):
            audit.audit_trace(self.root, self.trace, self.row)

    def test_missing_intent_rejected(self) -> None:
        (self.root / "actions/step-000-intent.private.json").unlink()
        with self.assertRaises(audit.ParseAuditError):
            audit.audit_trace(self.root, self.trace, self.row)


if __name__ == "__main__":
    unittest.main()
