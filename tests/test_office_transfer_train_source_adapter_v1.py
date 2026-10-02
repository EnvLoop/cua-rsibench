"""Source-profile and namespace refusals; no Office or provider access."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from tools import office_single_account_train_pilot_v1 as pilot
from tests import test_office_single_account_train_pilot_v1 as fixtures


def task(split="train_policy_development"):
    return {
        "schema": "ppt-wdi-original-candidates-v1",
        "split": split, "task_id": "ppt-wdi-transfer-" + "a" * 16,
        "actor_task": "Repair the four TRAIN fields.",
        "official_final_credit": 0,
        "development_source_split": "train",
        "analogue_role": "additional_train_only_after_private_control_admission",
        "source_scope": "private_wdi_country_csv_reserve_v1",
        "rights_tier": "wdi_cc_by_4_0_facts_plus_authored_simulation",
        "workflow": "chart_caption_reconciliation",
        "template_group": "ppt-transfer-brief-v1:chart_caption_reconciliation",
        "presentation_template": "ppt_wdi_factory/build_train_transfer_deck.mjs",
        "target_keys": ["summary", "chart_caption", "ledger", "interpretation"],
    }


class TransferSourceAdapterTests(unittest.TestCase):
    def transfer_evidence_fixture(self):
        fixture = fixtures.SingleAccountTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        spec_path, evidence_path, output, spec, evidence = fixture.fixture("powerpoint-web")
        old, _ = pilot._ref(spec["task_ref"], fixture.work_root)
        new = old.parent.parent.parent / "train_policy_development" / old.parent.name
        new.parent.mkdir()
        shutil.move(old.parent, new)
        task_path = new / "task.private.json"
        row = json.loads(task_path.read_bytes())
        row["split"] = "train_policy_development"
        fixtures.write_private(task_path, pilot._canonical(row))
        spec["task_ref"] = fixtures.ref(task_path, fixture.work_root)
        spec["source_ref"] = fixtures.ref(new / "source.pptx", fixture.work_root)
        fixtures.write_private(spec_path, pilot._canonical(spec))
        evidence["spec_sha256"] = pilot._sha(spec_path.read_bytes())
        fixtures.write_private(evidence_path, pilot._canonical(evidence))
        return fixture, spec_path, evidence_path, output, evidence

    def test_explicit_four_target_transfer_profile(self):
        row = task()
        self.assertEqual(pilot._ppt_train_profile(row, row["task_id"]),
                         "transfer_wdi_four_target_train")

    def test_legacy_single_target_profile_unchanged(self):
        row = task("train")
        row["task_id"] = "ppt-wdi-" + "b" * 16
        row["target_keys"] = ["summary"]
        self.assertEqual(pilot._ppt_train_profile(row, row["task_id"]),
                         "original_wdi_single_target_train")

    def test_wrong_split_or_transfer_contract_is_refused(self):
        mutations = [
            ("split", "selection"), ("split", "final_candidate"),
            ("development_source_split", "final"),
            ("analogue_role", "calibration_only"),
            ("source_scope", "private_wdi_reserve_v1"),
            ("rights_tier", "unknown"),
            ("presentation_template", "ppt_wdi_factory/build_deck.mjs"),
            ("template_group", "ppt-transfer-brief-v1:wrong"),
            ("target_keys", ["summary"]),
            ("target_keys", ["summary", "ledger", "interpretation", "decision"]),
            ("task_id", "ppt-wdi-" + "a" * 16),
            ("official_final_credit", 1), ("workflow", "unsupported"),
        ]
        for key, value in mutations:
            with self.subTest(key=key, value=value):
                row = task()
                row[key] = value
                with self.assertRaisesRegex(pilot.SingleAccountPilotError,
                                            "ppt_task_not_train_source"):
                    pilot._ppt_train_profile(row, row["task_id"])

    def test_task_identity_must_match_spec(self):
        with self.assertRaisesRegex(pilot.SingleAccountPilotError,
                                    "ppt_task_not_train_source"):
            pilot._ppt_train_profile(task(), "ppt-wdi-transfer-" + "c" * 16)

    def test_transfer_identity_cannot_be_relabelled_single_target_train(self):
        row = task("train")
        row["target_keys"] = ["summary"]
        with self.assertRaisesRegex(pilot.SingleAccountPilotError,
                                    "ppt_task_not_train_source"):
            pilot._ppt_train_profile(row, row["task_id"])

    def test_malformed_profile_is_refused_with_field_limited_error(self):
        for value in (None, [], {"source": "private contents"}):
            row = task()
            row["workflow"] = value
            with self.assertRaisesRegex(pilot.SingleAccountPilotError,
                                        "ppt_task_not_train_source"):
                pilot._ppt_train_profile(row, row["task_id"])

    def test_only_exact_nearest_train_package_namespace_is_allowed(self):
        def path(parts):
            return Path("work/private") / parts / "case" / "task.private.json"
        self.assertTrue(pilot._train_package_path(
            path("packages/train"), "powerpoint-web"))
        self.assertTrue(pilot._train_package_path(
            path("packages/train_policy_development"), "powerpoint-web"))
        self.assertFalse(pilot._train_package_path(
            path("packages/train_policy_development"), "excel-web"))
        for value in ("packages/selection", "packages/final_candidate",
                      "packages/train/final_candidate", "packages/train/nested"):
            with self.subTest(value=value):
                self.assertFalse(pilot._train_package_path(path(value), "powerpoint-web"))

    def test_source_profile_does_not_skip_independent_raw_freeze(self):
        row = task()
        with patch.object(pilot.json, "loads", return_value=deepcopy(row)), \
                patch.object(pilot.ppt_verify, "freeze", side_effect=ValueError("bad source")) as frozen:
            with self.assertRaisesRegex(pilot.SingleAccountPilotError,
                                        "source_not_wdi"):
                pilot.OfficeTrainScorer(
                    {"cell_id": "powerpoint-web", "task_id": row["task_id"]},
                    {"task": unittest.mock.Mock(), "source": Path("source.pptx")})
        frozen.assert_called_once()

    def test_transfer_namespace_keeps_fake_receipts_labelled_fake(self):
        fixture, spec, evidence, output, _ = self.transfer_evidence_fixture()
        result = pilot.audit(spec, evidence, output, work_root=fixture.work_root,
                             scorer_factory=fixtures.FakeScorer)
        self.assertEqual(result["status"], "fake_test_control_only")
        self.assertFalse(result["independent_scorer_executed"])
        self.assertFalse(result["selection_or_final_admitted"])

    def test_transfer_namespace_still_requires_actor_only_folder(self):
        fixture, spec, evidence_path, output, evidence = self.transfer_evidence_fixture()
        ref = evidence["phases"]["saved"]["inventory_ref"]
        inventory_path, _ = pilot._ref(ref, fixture.work_root)
        inventory = json.loads(inventory_path.read_bytes())
        inventory["items"].append({"file_name": "EL-PPT-Train-Extra.pptx",
                                  "edit_url_sha256": "e" * 64,
                                  "sourcedoc_sha256": "f" * 64})
        fixtures.write_private(inventory_path, pilot._canonical(inventory))
        evidence["phases"]["saved"]["inventory_ref"] = fixtures.ref(
            inventory_path, fixture.work_root)
        fixtures.write_private(evidence_path, pilot._canonical(evidence))
        with self.assertRaisesRegex(pilot.SingleAccountPilotError,
                                    "inventory_not_one_current_item"):
            pilot.audit(spec, evidence_path, output, work_root=fixture.work_root,
                        scorer_factory=fixtures.FakeScorer)
        self.assertFalse(output.exists())

    def context_fixture(self, directory):
        source_dir = directory / "evaluator"
        source_dir.mkdir()
        source = source_dir / "source.pptx"
        source.write_bytes(b"source")
        candidate = directory / "downloads" / "before.pptx"
        candidate.parent.mkdir()
        candidate.write_bytes(b"saved native candidate")
        scorer = pilot.OfficeTrainScorer.__new__(pilot.OfficeTrainScorer)
        scorer.source_profile = "transfer_wdi_four_target_train"
        scorer.paths = {"source": source}
        scorer.case = {}
        for name, key in [("source-snapshot.private.json", "source_snapshot_sha256"),
                          ("source-provenance.private.json", "source_provenance_sha256"),
                          ("source-country.private.zip", "source_zip_sha256")]:
            raw = ("fixture:" + name).encode()
            (source_dir / name).write_bytes(raw)
            scorer.case[key] = pilot._sha(raw)
        return scorer, candidate, source_dir

    def test_baseline_source_context_is_evaluator_only_and_candidate_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            scorer, candidate, source_dir = self.context_fixture(Path(temporary))
            original = candidate.read_bytes()
            copied_dirs = []
            def freeze(path, row, *, office_web_normalized):
                self.assertNotEqual(path, candidate)
                self.assertEqual(path.read_bytes(), original)
                self.assertEqual(path.parent.parent, source_dir)
                self.assertTrue(office_web_normalized)
                copied_dirs.append(path.parent)
                self.assertTrue((path.parent / "source-country.private.zip").is_file())
                return {"source_sha256": pilot._sha(path.read_bytes())}
            with patch.object(pilot.ppt_verify, "freeze", side_effect=freeze):
                result = scorer._freeze_ppt_baseline(candidate)
            self.assertEqual(result["source_sha256"], pilot._sha(original))
            self.assertEqual(candidate.read_bytes(), original)
            self.assertFalse(any(path.exists() for path in copied_dirs))
            self.assertEqual(list(candidate.parent.iterdir()), [candidate])

    def test_changed_or_symlink_source_context_is_rejected_before_freeze(self):
        for symlink in (False, True):
            with self.subTest(symlink=symlink), tempfile.TemporaryDirectory() as temporary:
                scorer, candidate, source_dir = self.context_fixture(Path(temporary))
                context = source_dir / "source-country.private.zip"
                if symlink:
                    other = source_dir / "other.zip"
                    context.rename(other)
                    context.symlink_to(other)
                else:
                    context.write_bytes(b"changed")
                with patch.object(pilot.ppt_verify, "freeze") as frozen:
                    with self.assertRaisesRegex(pilot.SingleAccountPilotError,
                                                "source_context_(changed|invalid)"):
                        scorer._freeze_ppt_baseline(candidate)
                frozen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
