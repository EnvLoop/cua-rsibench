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
                      self.physical) for i in range(14)]
        final = guard[6]
        dispatch = guard[13]
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
            "frame_id": "synthetic-frame", "frame_ref": frame,
            "frame_sha256": frame["sha256"],
            "pre_intent_stale_resamples": 0,
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
            "pre_intent_rejections": [],
            "actions": [{"step": 0, "phase": "positive", "frame": frame,
                         "contract_receipt": self.contract}],
            "exact_return_guard_samples": [
                {"step": 0, "stage": "parse", "sample": index,
                 "classification":
                     "one_recurring_micro_raster_alternate",
                 "observed_frame_sha256": frame["sha256"],
                 "observed_frame_id_sha256": digest(b"synthetic-frame"),
                 "sampled_frame_ref": reference}
                for index, reference in enumerate(guard[:6])] + [
                    {"step": 0, "stage": "parse_final", "sample": 6,
                     "classification": audit.PARSE_ALT,
                     "observed_frame_sha256": frame["sha256"],
                     "observed_frame_id_sha256":
                         digest(b"synthetic-frame"),
                     "sampled_frame_ref": final}] + [
                    {"step": 0, "stage": "dispatch", "sample": index,
                     "classification":
                         ("one_recurring_micro_raster_alternate"
                          if index < 6 else audit.PINNED),
                     "observed_frame_sha256": frame["sha256"],
                     "observed_frame_id_sha256":
                         digest(b"synthetic-frame"),
                     "sampled_frame_ref": reference}
                    for index, reference in enumerate(guard[7:])],
        }
        self.write_intent_result()

    def write_intent_result(self) -> None:
        prefix = ("step-000" if
                  self.intent["pre_intent_stale_resamples"] == 0 else
                  f"step-000-resample-"
                  f"{self.intent['pre_intent_stale_resamples']:02d}")
        for pattern in ("step-000*-intent.private.json",
                        "step-000*-result.private.json"):
            for old in (self.root / "actions").glob(pattern):
                old.unlink()
        raw = json.dumps(self.intent, sort_keys=True).encode()
        save(self.root, f"actions/{prefix}-intent.private.json", raw)
        result = {"step": 0, "intent_sha256": digest(raw),
                  "contract_receipt": self.contract,
                  "applied_action": self.intent["normalized_action"]}
        save(self.root, f"actions/{prefix}-result.private.json",
             json.dumps(result, sort_keys=True).encode())

    def prepend_valid_stale_rejection(self) -> None:
        samples = self.trace["exact_return_guard_samples"]
        old_raw = [(self.root / sample["sampled_frame_ref"]["path"])
                   .read_bytes() for sample in samples]
        for index, (sample, raw) in enumerate(zip(samples, old_raw)):
            sample["sampled_frame_ref"] = save(
                self.root, f"frames/guard-{index + 1:04d}.png", raw)
        self.contract["parse_guard"]["physical_frame_ref"] = \
            samples[6]["sampled_frame_ref"]
        self.contract["physical_dispatch_guard"]["physical_frame_ref"] = \
            samples[13]["sampled_frame_ref"]
        frame = save(self.root, "frames/step-000-rejected.png", self.observed)
        current = save(self.root, "frames/step-000-rejected-current.png",
                       self.physical)
        assistant = save(self.root, "actions/step-000-assistant.json", b"{}")
        rejection = {
            "schema": "envloop-odoo-v066-pre-intent-frame-rejection-v1",
            "phase": "positive", "step": 0, "observation_attempt": 0,
            "error_code": "stale_frame",
            "frame_id_sha256": digest(b"prior-stale-frame"),
            "observed_frame_ref": frame,
            "assistant_action_ref": assistant,
            "current_frame_ref": current,
            "pre_dispatch_intent_created": False,
            "gui_action_dispatched": False,
        }
        reference = save(
            self.root, "actions/step-000-rejection.private.json",
            json.dumps(rejection, sort_keys=True).encode())
        self.trace["pre_intent_rejections"].append(reference)
        samples.insert(0, {
            "step": 0, "stage": "parse", "sample": 0,
            "classification": "one_recurring_micro_raster_alternate",
            "observed_frame_sha256": digest(self.observed),
            "observed_frame_id_sha256": digest(b"prior-stale-frame"),
            "sampled_frame_ref": save(
                self.root, "frames/guard-0000.png", self.physical),
        })
        self.intent["pre_intent_stale_resamples"] = 1
        self.write_intent_result()

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
        self.contract["parse_guard"]["physical_frame_ref"] = {
            "path": "frames/guard-0006.png", "sha256": digest(self.physical)}
        self.contract["parse_guard"]["physical_url"] = \
            "http://127.0.0.1:8069/odoo/sales/123"
        self.write_intent_result()
        with self.assertRaises(audit.ParseAuditError):
            audit.audit_trace(self.root, self.trace, self.row)

    def test_missing_intent_rejected(self) -> None:
        (self.root / "actions/step-000-intent.private.json").unlink()
        with self.assertRaises(audit.ParseAuditError):
            audit.audit_trace(self.root, self.trace, self.row)

    def test_material_third_dispatch_sample_rejected(self) -> None:
        third = Image.open(BytesIO(self.physical)).copy()
        third.putpixel((800, 800), (0, 0, 0))
        reference = save(self.root, "frames/guard-0014.png", png(third))
        self.trace["exact_return_guard_samples"].append({
            "step": 0, "stage": "dispatch", "sample": 7,
            "classification": "third_or_material_frame_rejected",
            "observed_frame_sha256": digest(self.observed),
            "observed_frame_id_sha256": digest(b"synthetic-frame"),
            "sampled_frame_ref": reference,
        })
        with self.assertRaises(audit.ParseAuditError):
            audit.audit_trace(self.root, self.trace, self.row)

    def test_parse_final_before_six_parse_samples_rejected(self) -> None:
        samples = self.trace["exact_return_guard_samples"]
        samples.insert(0, samples.pop(6))
        for index, sample in enumerate(samples):
            sample["sampled_frame_ref"] = {
                "path": f"frames/guard-{index:04d}.png",
                "sha256": digest(self.physical),
            }
        self.contract["parse_guard"]["physical_frame_ref"] = \
            samples[0]["sampled_frame_ref"]
        self.write_intent_result()
        with self.assertRaises(audit.ParseAuditError):
            audit.audit_trace(self.root, self.trace, self.row)

    def test_parse_final_indexed_sink_collision_rejected(self) -> None:
        samples = self.trace["exact_return_guard_samples"]
        samples[6]["sampled_frame_ref"] = samples[5]["sampled_frame_ref"]
        self.contract["parse_guard"]["physical_frame_ref"] = \
            samples[5]["sampled_frame_ref"]
        self.write_intent_result()
        with self.assertRaises(audit.ParseAuditError):
            audit.audit_trace(self.root, self.trace, self.row)

    def test_bound_pre_intent_stale_rejection_passes(self) -> None:
        self.prepend_valid_stale_rejection()
        result = audit.audit_trace(self.root, self.trace, self.row)
        self.assertEqual(result["pinned_border_parse_exceptions"], 1)

    def test_unbound_rejected_frame_sample_fails(self) -> None:
        self.prepend_valid_stale_rejection()
        self.trace["pre_intent_rejections"].clear()
        self.intent["pre_intent_stale_resamples"] = 0
        self.write_intent_result()
        with self.assertRaises(audit.ParseAuditError):
            audit.audit_trace(self.root, self.trace, self.row)


if __name__ == "__main__":
    unittest.main()
