"""Train exporters pin helper, complete envelope, PNGs, and saved OOXML."""

from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from cursibench.scale_action_contract import ContractLimits, make_observation
from cursibench.scale_action_output_v066 import normalize_model_action
from native_desktop_factory import v066_scoped_calc_writer_train_demo as demo
from tools import export_desktop_v066_calc_train_sft_v1 as calc
from tools import export_desktop_v066_writer_train_sft_v1 as writer
from tools import export_desktop_v066_calc_writer_train_sft_common_v1 as common


class CalcWriterExporterTests(unittest.TestCase):
    def test_public_offline_render_receipts_bind_exact_exporter_sources(self):
        root = Path(__file__).resolve().parents[1]
        helper_sha = common.digest(Path(common.__file__).read_bytes())
        for kind, module, count in (("calc", calc, 12),
                                     ("writer", writer, 8)):
            path = (root / "docs/evidence" /
                f"native-wdi-v066-{kind}-train-sft-render-2026-09-28.json")
            public = json.loads(path.read_bytes())
            self.assertEqual(public["status"],
                             "evaluator_scripted_public_train_gui_rendered_offline")
            self.assertEqual(public["real_gui_train_turns"], count)
            self.assertEqual(public["exporter_source_sha256"],
                             common.digest(Path(module.__file__).read_bytes()))
            self.assertEqual(public["shared_helper_source_sha256"], helper_sha)
            self.assertEqual(module.HELPER_SHA256, helper_sha)
            self.assertEqual(public["provider_calls"], 0)
            self.assertIsNone(public["benchmark_score"])
            self.assertEqual(public["official_final_admissions"], 0)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        work = Path(self.temp.name) / "work/native-desktop"
        self.root = (work / "gui-diagnostics" /
                     "v066-scoped-calc-writer-train-demo-20260928-001")
        self.root.mkdir(parents=True, mode=0o700)
        self.root.chmod(0o700)
        for name in ("v066-scoped-profile-reference-20260928.private.json",
                     "v066-scoped-calc-writer-train-demo-reservation-20260928.private.json"):
            (work / name).write_text("{}")
        output = io.BytesIO()
        Image.new("RGB", (1280, 800), "white").save(output, format="PNG")
        self.frame = output.getvalue()
        self.receipt_raw = {}
        for kind in demo.KINDS:
            self.create_episode(kind)
        self.run_raw = b'{"schema":"fake-run"}\n'
        self.write_private(self.root / "run-receipt.json", self.run_raw)
        audit_record = {
            "schema": "cua-native-wdi-v066-calc-writer-train-demo-audit-v2-private-v1",
            "status": "two_distinct_train_gui_positives_passed",
            "run_journal_sha256": common.digest(self.run_raw),
            "provider_active_zero_after": True,
            "official_final_admissions": 0,
            "raw_private_file_sha256s": {},
        }
        audit_raw = json.dumps(audit_record).encode()
        self.write_private(self.root / "audit-v2.private.json", audit_raw)
        public = {
            "schema": "cua-native-wdi-v066-calc-writer-train-demo-public-v1",
            "status": "two_public_train_gui_positives_independently_verified_not_registered_sft",
            "private_v2_independent_audit_sha256": common.digest(audit_raw),
            "private_run_journal_sha256": common.digest(self.run_raw),
            "demo_runner_source_sha256": common.digest(Path(demo.__file__).read_bytes()),
            "historical_bound_v1_auditor_source_sha256": common.digest(
                Path(common.historical_audit.__file__).read_bytes()),
            "corrected_read_only_v2_auditor_source_sha256": common.digest(
                Path(common.independent_audit.__file__).read_bytes()),
            "official_final_admissions": 0,
            "source_bound_sft_exporters_completed": False,
        }
        for kind in demo.KINDS:
            public[f"private_{kind}_receipt_sha256"] = common.digest(
                self.receipt_raw[kind])
        self.public = Path(self.temp.name) / "public.json"
        self.public.write_text(json.dumps(public))

    @staticmethod
    def write_private(path, raw):
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.parent.chmod(0o700)
        path.write_bytes(raw)
        path.chmod(0o600)

    def bound(self, path, raw):
        self.write_private(path, raw)
        return {"private_path": str(path.relative_to(self.root)),
                "sha256": common.digest(raw), "bytes": len(raw)}

    def create_episode(self, kind):
        package, oracle, baseline, instruction, _filename = demo._source(kind)
        path = self.root / kind
        path.mkdir(mode=0o700)
        actions = []
        for index, minimal in enumerate(demo.actor_actions(kind, oracle)):
            observation = make_observation(
                task_id=package["task_id"],
                task_binding_sha256=package["package_sha256"],
                instruction=instruction, step=index,
                screenshot_bytes=self.frame,
                a11y_text="", dom_text="", controls=(),
                previous_action_result=(None if index == 0 else
                                        {"status": "applied", "code": "ok"}),
                memory="", limits=ContractLimits(max_step=demo.MAX_ACTIONS))
            raw_action = json.dumps(minimal, separators=(",", ":"))
            normalized = normalize_model_action(
                raw_action, observation,
                current_frame_id=observation.frame_id)
            actions.append({
                "step": index,
                "status": "applied",
                "normalized_action": normalized,
                "normalized_action_sha256": common.digest(json.dumps(
                    normalized, sort_keys=True,
                    separators=(",", ":")).encode()),
                "frame_id_sha256": common.digest(observation.frame_id.encode()),
                "observation": self.bound(
                    path / f"frame-{index:02d}.png", self.frame),
                "predispatch": self.bound(
                    path / f"predispatch-{index:02d}.png", self.frame),
            })
        saved = b"changed " + kind.encode()
        ext = ".xlsx" if kind == "calc" else ".docx"
        receipt = {
            "kind": kind, "split": "train",
            "package_sha256": package["package_sha256"],
            "input_sha256": common.digest(baseline),
            "status": "train_gui_positive_passed",
            "actor_gui_actions": len(actions),
            "official_final_model_attempts": 0,
            "normalized_actor_actions": actions,
            "saved_artifact": self.bound(path / ("saved" + ext), saved),
        }
        raw = json.dumps(receipt).encode()
        self.receipt_raw[kind] = raw
        self.write_private(path / "receipt.json", raw)
        self.write_private(path / "intent.json", b"{}")
        path.chmod(0o700)

    def patched(self):
        return (patch.object(common, "PUBLIC_EVIDENCE", self.public),
                patch.object(common.independent_audit, "audit_both",
                             return_value=(
                                 {"status": "two_distinct_train_gui_positives_passed",
                                  "run_journal_sha256": common.digest(self.run_raw)},
                                 {"current_frame_actions_total": 20})))

    def test_both_exporters_preserve_recorded_frame_ids(self):
        public_patch, audit_patch = self.patched()
        with public_patch, audit_patch:
            for kind, module in (("calc", calc), ("writer", writer)):
                source, turns = module.source_bound_steps(self.root / kind)
                self.assertEqual(len(turns), 12 if kind == "calc" else 8)
                self.assertTrue(all(
                    turn["observation"].frame_id ==
                    turn["recorded_normalized_action"]["frame_id"]
                    for turn in turns))
                self.assertEqual(len(source["source_frames"]), len(turns))

    def test_helper_pin_frame_and_saved_tamper_are_rejected(self):
        with patch.object(calc, "HELPER_SHA256", "0" * 64):
            with self.assertRaisesRegex(ValueError, "shared source changed"):
                calc.source_bound_steps(self.root / "calc")
        public_patch, audit_patch = self.patched()
        with public_patch, audit_patch:
            frame = self.root / "calc/frame-00.png"
            frame.write_bytes(b"tampered")
            with self.assertRaises(ValueError):
                calc.source_bound_steps(self.root / "calc")

    def test_recorded_frame_id_tamper_is_rejected_even_with_new_action_hash(self):
        path = self.root / "writer/receipt.json"
        receipt = json.loads(path.read_bytes())
        step = receipt["normalized_actor_actions"][0]
        step["normalized_action"]["frame_id"] = "forged-current-frame"
        step["normalized_action_sha256"] = common.digest(json.dumps(
            step["normalized_action"], sort_keys=True,
            separators=(",", ":")).encode())
        raw = json.dumps(receipt).encode()
        self.write_private(path, raw)
        public = json.loads(self.public.read_bytes())
        public["private_writer_receipt_sha256"] = common.digest(raw)
        self.public.write_text(json.dumps(public))
        public_patch, audit_patch = self.patched()
        with public_patch, audit_patch:
            with self.assertRaisesRegex(ValueError, "current-frame ID changed"):
                writer.source_bound_steps(self.root / "writer")
