"""Fake-only safety tests for the dated Magento modal supplement."""

from __future__ import annotations

from contextlib import nullcontext
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools import audit_magento_v2_modal_supplement_v1 as final
from tools import magento_v2_modal_supplement_v1 as wrapper


class MagentoModalSupplementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.run_dir = self.root / "run"
        self.run_dir.mkdir()
        self.base = wrapper.v2.attempt_dir(self.run_dir, 14, 0)
        self.pair = self.base / "case-014" / "positive"
        (self.pair / "neutral").mkdir(parents=True)
        self.stderr = (b"Locator.click: Timeout 60000ms exceeded.\n"
                       b"line 50, in read_quote_in_gui\n"
                       b"admin__form-loading-mask\n"
                       b"modal-popup confirm _show\n"
                       b"intercepts pointer events\n")
        (self.pair / "positive-neutral-stderr.private.bin").write_bytes(self.stderr)
        process = {"exit_code": 1, "stderr_sha256": wrapper.sha(self.stderr)}
        self.process_path = self.pair / "positive-neutral-process.private.json"
        self.process_path.write_text(json.dumps(process, sort_keys=True) + "\n")
        self.scoped = [
            {"event": "case_attempt_started", "index": 14, "attempt": 0},
            {"event": "step_intent", "step": "positive-prepare"},
            {"event": "step_finished", "step": "positive-prepare", "exit_code": 0},
            {"event": "step_intent", "step": "positive-seed"},
            {"event": "step_finished", "step": "positive-seed", "exit_code": 0},
            {"event": "step_intent", "step": "positive-neutral"},
            {"event": "step_finished", "step": "positive-neutral",
             "exit_code": 1, "stderr_sha256": wrapper.sha(self.stderr)},
            {"event": "attempt_stopped", "index": 14, "attempt": 0},
        ]
        self.ctx = {"run_dir": self.run_dir,
                    "stop": {"stderr_sha256": wrapper.sha(self.stderr),
                             "process_sha256": wrapper.sha(self.process_path.read_bytes()),
                             "journal_sha256": "j" * 64}}
        self.freeze = {"original_stopped_journal_sha256": "j" * 64}

    def test_one_case_classifier_extension_is_explicit_and_byte_bound(self) -> None:
        classify = wrapper._supplemental_classifier(
            self.ctx, self.freeze, lambda *_args: None)
        self.assertEqual(classify(self.base, 14, self.scoped), wrapper.COMPAT_CLASS)
        self.assertIsNone(classify(self.base, 13, self.scoped))
        self.assertIsNone(classify(self.run_dir / "other", 14, self.scoped))
        changed = list(self.scoped) + [{"event": "step_intent", "step": "positive-gui"}]
        self.assertIsNone(classify(self.base, 14, changed))
        (self.pair / "positive-neutral-stderr.private.bin").write_bytes(b"different timeout")
        with self.assertRaisesRegex(ValueError, "modal_bytes"):
            classify(self.base, 14, self.scoped)

    def test_runtime_compatibility_override_is_scoped_and_restored(self) -> None:
        original = wrapper.v2._known_neutral_timeout
        with wrapper.explicit_source_bound_v2_classifier(self.ctx, self.freeze):
            self.assertIsNot(wrapper.v2._known_neutral_timeout, original)
            self.assertEqual(wrapper.v2._known_neutral_timeout(
                self.base, 14, self.scoped), wrapper.COMPAT_CLASS)
        self.assertIs(wrapper.v2._known_neutral_timeout, original)

    def test_source_receipt_rejects_unbound_wrapper_or_stop_audit(self) -> None:
        stop = {"freeze_v2_sha256": "f" * 64,
                "cleanup_authorized": False, "retry_authorized": False}
        stop_path = self.root / "stop-public.json"
        stop_path.write_text(json.dumps(stop))
        auditor_path = Path(final.__file__)
        public = {
            "schema": wrapper.PUBLIC_SCHEMA,
            "status": "proposed_before_cleanup_retry_or_model_result",
            "supplemental_classification": wrapper.SUPPLEMENT_CLASS,
            "v2_internal_compatibility_classification": wrapper.COMPAT_CLASS,
            "original_v2_class_did_not_match_stopped_stderr": True,
            "scope_case_ordinal": 15,
            "source_sha256": wrapper.sha(Path(wrapper.__file__).read_bytes()),
            "independent_auditor_sha256": wrapper.sha(auditor_path.read_bytes()),
            "modal_stop_public_sha256": wrapper.sha(stop_path.read_bytes()),
            "frozen_v2_private_sha256": "f" * 64,
            "frozen_v2_code_sha256s": {
                name: wrapper.sha((wrapper.ROOT / name).read_bytes())
                for name in wrapper.v2.CODE_FILES},
            "modal_stop_private_sha256": "m" * 64,
            "original_stopped_journal_sha256": "j" * 64,
            "post_stop_ui_observation_sha256s": {},
            "first_controls_retained": 14,
            "cleanup_authorized": False, "retry_authorized": False,
            "model_calls": 0, "official_final_admitted": 0,
        }
        stop.update({"private_audit_sha256": "m" * 64,
                     "journal_sha256": "j" * 64})
        stop_path.write_text(json.dumps(stop))
        public["modal_stop_public_sha256"] = wrapper.sha(stop_path.read_bytes())
        public_path = self.root / "supplement-public.json"
        public_path.write_text(json.dumps(public))
        with (patch.object(wrapper, "SOURCE_PUBLIC", public_path),
              patch.object(wrapper, "STOP_PUBLIC", stop_path),
              patch.object(wrapper, "AUDITOR_SOURCE", auditor_path)):
            self.assertEqual(wrapper.source_receipt()["source_public"], public)
            public["source_sha256"] = "0" * 64
            public_path.write_text(json.dumps(public))
            with self.assertRaisesRegex(ValueError, "source_or_stop_evidence_changed"):
                wrapper.source_receipt()

    def test_prepare_freeze_preserves_first_fourteen_and_original_stop(self) -> None:
        journal = self.run_dir / "journal.private.jsonl"
        journal.write_bytes(b"frozen original stopped journal\n")
        for dirname, screenshot, clicked in (
                ("modal-ui-readonly-20260928", "dashboard.private.png", False),
                ("modal-ui-click-readonly-20260928", "after.private.png", True)):
            folder = self.run_dir / dirname
            folder.mkdir()
            (folder / screenshot).write_bytes(b"retained UI-only pixels")
            receipt = {"business_edits": 0,
                       "screenshot_sha256": wrapper.sha(b"retained UI-only pixels")}
            if clicked:
                receipt.update({"menu_clicked": True, "error_type": None})
            (folder / "receipt.private.json").write_text(json.dumps(receipt))
        ui_hashes = wrapper._post_stop_ui_evidence(self.run_dir)
        self.ctx.update({
            "journal": journal,
            "events": ([{"event": "case_completed", "index": i, "attempt": 0}
                        for i in range(14)] +
                       self.scoped),
            "stop": {**self.ctx["stop"],
                     "journal_sha256": wrapper.sha(journal.read_bytes())},
            "cases": [{"task_id": f"private-{i}",
                       "package_sha256": f"{i + 1:064x}"} for i in range(100)],
            "source_public_sha256": "p" * 64,
            "source_public": {
                "post_stop_ui_observation_sha256s": ui_hashes,
                "original_stopped_journal_sha256": wrapper.sha(journal.read_bytes())},
            "freeze_sha256": "f" * 64,
            "frozen": {"code_sha256": {"frozen-source": "1" * 64}},
            "stop_sha256": "s" * 64,
            "stop_public_sha256": "u" * 64,
        })
        with patch.object(wrapper, "_first_fourteen_receipts", return_value="r" * 64):
            value = wrapper.prepare_freeze(self.ctx)
        self.assertEqual(value["first_fourteen_calibration_sha256"], "r" * 64)
        self.assertEqual(value["original_stopped_journal_sha256"],
                         wrapper.sha(journal.read_bytes()))
        self.assertEqual(value["case_index"], 14)
        self.assertEqual(value["model_calls"], 0)

    def test_cleanup_refuses_changed_live_material_before_any_v2_action(self) -> None:
        self.ctx["stop"]["material_witness"] = {"material_equal_exact": True}
        paths = wrapper._paths(self.ctx)
        paths["fresh"].write_text(json.dumps({
            "supplement_freeze_sha256": "f" * 64,
            "material_witness": self.ctx["stop"]["material_witness"],
            "fresh_material_witness_sha256": "a" * 64}))
        paths["v2_audit"].write_text(json.dumps({
            "classification": wrapper.COMPAT_CLASS, "case_index": 14}))
        with (patch.object(wrapper, "validate_supplement_freeze",
                           return_value=({}, "f" * 64)),
              patch.object(wrapper, "fresh_modal_witness",
                           side_effect=ValueError("new live business drift")),
              patch.object(wrapper.v2, "reconcile_attempt") as reconcile):
            with self.assertRaisesRegex(ValueError, "business drift"):
                wrapper.cleanup(self.ctx)
            reconcile.assert_not_called()
        self.assertFalse(paths["intent"].exists())

    def test_resume_refuses_absent_supplemental_cleanup_lineage(self) -> None:
        with (patch.object(wrapper, "require_cleanup_lineage",
                           side_effect=ValueError("cleanup lineage absent")),
              patch.object(wrapper.v2, "run_campaign") as runner):
            with self.assertRaisesRegex(ValueError, "cleanup lineage absent"):
                wrapper.resume(self.ctx)
            runner.assert_not_called()

    def test_independent_final_gate_rejects_extra_retry_or_missing_100(self) -> None:
        self.ctx.update({"freeze_sha256": "f" * 64,
                         "stop": {"journal_sha256": "j" * 64}})
        frozen = {"first_fourteen_calibration_sha256": "1" * 64,
                  "original_stopped_journal_sha256": "j" * 64}
        lineage = {"supplement_cleanup_receipt_sha256": "2" * 64,
                   "wrapper_source_sha256": "3" * 64}
        original = {"distinct_candidate_controls": 100,
                    "positive_saved_state_pass": 100,
                    "wrong_variant_saved_state_rejected": 100,
                    "fresh_clone_material_reset_pass": 100,
                    "bounded_invalid_infrastructure_retries": 1,
                    "invalid_attempts_by_classification": {wrapper.COMPAT_CLASS: 1},
                    "historical_controls_reused": 0,
                    "model_calls": 0, "official_final_admitted": 0,
                    "journal_sha256": "4" * 64}
        calls = {"plan": Path("p"), "plan_sha256": "x",
                 "source": Path("s"), "parent_freeze": Path("o"),
                 "freeze_v2": Path("v"), "run_dir": self.run_dir}
        with (patch.object(final.supplement, "context", return_value=self.ctx),
              patch.object(final.supplement, "validate_supplement_freeze",
                           return_value=(frozen, "5" * 64)),
              patch.object(final.supplement, "require_cleanup_lineage",
                           return_value=lineage),
              patch.object(final, "_independent_raw_modal_check",
                           return_value={"stderr_sha256": "6" * 64}),
              patch.object(final.supplement, "_first_fourteen_receipts",
                           return_value="1" * 64),
              patch.object(final.supplement,
                           "explicit_source_bound_v2_classifier",
                           return_value=nullcontext()),
              patch.object(final.v2, "audit_campaign", return_value=original)):
            private, public = final.audit(**calls)
            self.assertEqual(public["distinct_evaluator_controls"], 100)
            self.assertEqual(public["supplemental_classification"],
                             wrapper.SUPPLEMENT_CLASS)
            self.assertEqual(private["official_final_admitted"], 0)
            original["bounded_invalid_infrastructure_retries"] = 2
            with self.assertRaisesRegex(ValueError, "not_exactly_100"):
                final.audit(**calls)


if __name__ == "__main__":
    unittest.main()
