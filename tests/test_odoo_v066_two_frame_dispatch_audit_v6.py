"""Offline mutation tests for every saved Odoo v6 dispatch guard frame."""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from tools import audit_odoo_v066_two_frame_dispatch_v6 as audit


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def png(image: Image.Image) -> bytes:
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def save(root: Path, name: str, raw: bytes) -> dict:
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    return {"path": name, "sha256": digest(raw)}


class TwoFrameAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        observed = Image.new("RGB", (1440, 1000), (255, 255, 255))
        for xy in audit.PIXELS:
            observed.putpixel(xy, (235, 237, 240))
        alternate = observed.copy()
        for xy in audit.PIXELS:
            alternate.putpixel(xy, (235, 237, 239))
        self.observed = png(observed)
        self.alternate = png(alternate)
        self.frame = save(self.root, "frames/step-000.png", self.observed)
        self.guards = [save(self.root, f"frames/guard-{i:04d}.png",
                            self.observed if i in (0, 7, 8)
                            else self.alternate) for i in range(9)]
        self.url = "http://127.0.0.1:8069/odoo/purchase/123"
        self.row = {"task_id": "synthetic-id", "package_sha256": "a" * 64,
                    "task_binding_sha256": "b" * 64}
        self.control = {
            "ref": "c100", "role": "button", "label": "Attach Files",
            "visible": True, "enabled": True, "purchase_rfq_view": True,
            "bounds": [1280, 850, 1335, 885],
        }
        self.action = {"type": "click", "target": {"x": 1307, "y": 868},
                       "task_id": self.row["task_id"],
                       "task_binding_sha256": self.row["package_sha256"],
                       "frame_id": "synthetic-frame"}
        controls = [{key: self.control[key] for key in
                     ("ref", "role", "label", "visible", "enabled")}]
        visible = save(self.root, "actions/step-000-visible.txt",
                       json.dumps({"controls": controls,
                                   "screenshot": {
                                       "sha256": self.frame["sha256"]}},
                                  sort_keys=True).encode())
        self.intent = {
            "step": 0, "task_id": self.row["task_id"],
            "task_binding_sha256": self.row["package_sha256"],
            "frame_id": "synthetic-frame", "frame_ref": self.frame,
            "frame_sha256": self.frame["sha256"],
            "pre_intent_stale_resamples": 0,
            "normalized_action": self.action,
            "dispatch_state": "intent_durable_before_gui_action",
            "observed_url": self.url,
            "observed_target_control": self.control,
            "observation_controls": controls,
            "visible_text_ref": visible,
        }
        self.contract = {
            "screenshot": {"sha256": self.frame["sha256"]},
            "control_count": 1,
            "task_binding_sha256": self.row["package_sha256"],
            "task_id_sha256": digest(self.row["task_id"].encode()),
            "frame_id_sha256": digest(b"synthetic-frame"),
            "parse_guard": {
                "profile": audit.PARSE_PROFILE,
                "classification": audit.PARSE_EXACT,
                "observed_frame_sha256": self.frame["sha256"],
                "observed_frame_id_sha256": digest(b"synthetic-frame"),
                "physical_frame_ref": self.guards[0],
                "observed_url": self.url, "physical_url": self.url,
                "sample_count": 1,
                "target_point": self.action["target"],
                "target_control_before": None,
                "target_control_after": self.control,
            },
            "physical_dispatch_guard": {
                "profile": audit.V6_PROFILE,
                "classification": audit.TWO_OBSERVED,
                "observed_frame_sha256": self.frame["sha256"],
                "observed_frame_id_sha256": digest(b"synthetic-frame"),
                "observed_url": self.url, "physical_url": self.url,
                "target_point": self.action["target"],
                "target_control_before": self.control,
                "target_control_after": self.control,
                "target_control": self.control,
                "base_dispatch_samples": 6,
                "first_final_frame_ref": self.guards[7],
                "second_final_frame_ref": self.guards[8],
                "physical_frame_ref": self.guards[8],
                "pinned_pixel_coordinates": [[41, 419], [132, 419]],
            },
        }
        self.trace = {
            "task_binding_sha256": self.row["task_binding_sha256"],
            "sft_examples_written": 0, "pre_intent_rejections": [],
            "actions": [{"step": 0, "phase": "positive",
                         "frame": self.frame,
                         "contract_receipt": self.contract}],
            "exact_return_guard_samples": [
                {"step": 0, "stage": ("parse" if index == 0 else
                                       "dispatch" if index <= 6 else
                                       "dispatch_final"),
                 "sample": (0 if index == 0 else index - 1),
                 "classification": (
                     "exact_return" if index == 0 else
                     "one_recurring_micro_raster_alternate"
                     if index <= 6 else
                     "two_frame_candidate_observed" if index == 7 else
                     audit.TWO_OBSERVED),
                 "observed_frame_sha256": self.frame["sha256"],
                 "observed_frame_id_sha256": digest(b"synthetic-frame"),
                 "sampled_frame_ref": ref}
                for index, ref in enumerate(self.guards)],
        }
        self.write_result()

    def write_result(self) -> None:
        raw = json.dumps(self.intent, sort_keys=True).encode()
        save(self.root, "actions/step-000-intent.private.json", raw)
        result = {"step": 0, "intent_sha256": digest(raw),
                  "contract_receipt": self.contract,
                  "applied_action": self.action}
        save(self.root, "actions/step-000-result.private.json",
             json.dumps(result, sort_keys=True).encode())

    def test_observed_return_audits_every_indexed_frame(self) -> None:
        result = audit.audit_trace(self.root, self.trace, self.row)
        self.assertEqual(result["actions"], 1)

    def test_alternate_confirmation_audits_two_pixel_set(self) -> None:
        for index in (7, 8):
            ref = save(self.root, f"frames/guard-{index:04d}.png",
                       self.alternate)
            self.trace["exact_return_guard_samples"][index][
                "sampled_frame_ref"] = ref
        self.trace["exact_return_guard_samples"][7]["classification"] = \
            "two_frame_candidate_alternate"
        self.trace["exact_return_guard_samples"][8]["classification"] = \
            audit.TWO_ALTERNATE
        receipt = self.contract["physical_dispatch_guard"]
        receipt["classification"] = audit.TWO_ALTERNATE
        receipt["first_final_frame_ref"] = \
            self.trace["exact_return_guard_samples"][7]["sampled_frame_ref"]
        receipt["second_final_frame_ref"] = \
            self.trace["exact_return_guard_samples"][8]["sampled_frame_ref"]
        receipt["physical_frame_ref"] = receipt["second_final_frame_ref"]
        self.write_result()
        self.assertEqual(audit.audit_trace(self.root, self.trace, self.row)
                         ["actions"], 1)

    def test_third_or_unbound_frame_rejected(self) -> None:
        third = Image.open(BytesIO(self.observed)).copy()
        third.putpixel((800, 800), (0, 0, 0))
        ref = save(self.root, "frames/guard-0008.png", png(third))
        self.trace["exact_return_guard_samples"][8]["sampled_frame_ref"] = ref
        self.contract["physical_dispatch_guard"]["second_final_frame_ref"] = ref
        self.contract["physical_dispatch_guard"]["physical_frame_ref"] = ref
        self.write_result()
        with self.assertRaises(audit.ParseAuditError):
            audit.audit_trace(self.root, self.trace, self.row)
        self.trace["exact_return_guard_samples"][8]["sampled_frame_ref"] = \
            self.guards[8]
        self.contract["physical_dispatch_guard"]["second_final_frame_ref"] = \
            self.guards[8]
        self.contract["physical_dispatch_guard"]["physical_frame_ref"] = \
            self.guards[8]
        self.trace["exact_return_guard_samples"].append(
            self.trace["exact_return_guard_samples"][8].copy())
        self.write_result()
        with self.assertRaises(audit.ParseAuditError):
            audit.audit_trace(self.root, self.trace, self.row)

    def test_target_control_or_url_mutation_rejected(self) -> None:
        self.contract["physical_dispatch_guard"]["target_control_after"] = {
            **self.control, "label": "Changed"}
        self.write_result()
        with self.assertRaises(audit.ParseAuditError):
            audit.audit_trace(self.root, self.trace, self.row)
        self.contract["physical_dispatch_guard"]["target_control_after"] = \
            self.control
        self.contract["physical_dispatch_guard"]["physical_url"] = \
            "http://127.0.0.1:8069/odoo/sales/123"
        self.write_result()
        with self.assertRaises(audit.ParseAuditError):
            audit.audit_trace(self.root, self.trace, self.row)


if __name__ == "__main__":
    unittest.main()
