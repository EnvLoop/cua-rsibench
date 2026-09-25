"""Evidence boundary and split invariants for the two Microsoft web cells."""

import importlib.util
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "plan_office_web_admission", ROOT / "tools/plan_office_web_admission.py")
import sys
sys.path.insert(0, str(ROOT / "tools"))
plan = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(plan)


def rows(count, families, prefix):
    return [{"task_id": f"{prefix}-{number}",
             "source_group": f"source-{prefix}-{number % families}",
             "template_group": f"template-{prefix}-{number % families}",
             "entity_group": f"unresolved-{prefix}-{number % families}",
             "instance_group": f"instance-{prefix}-{number}"}
            for number in range(count)]


class OfficeAdmissionPlanTests(unittest.TestCase):
    def test_cross_split_family_or_instance_overlap_is_rejected(self):
        for field in ("source_group", "template_group", "instance_group"):
            with self.subTest(field=field):
                split = {"selection": rows(20, 2, "selection"),
                         "provisional_final": rows(100, 10, "final")}
                split["provisional_final"][0][field] = split["selection"][0][field]
                with self.assertRaisesRegex(ValueError, field):
                    plan.check_split(split, 2, 10)

    def test_repeated_task_identity_or_bad_denominator_is_rejected(self):
        split = {"selection": rows(20, 2, "selection"),
                 "provisional_final": rows(100, 10, "final")}
        split["provisional_final"][0]["task_id"] = split["selection"][0]["task_id"]
        with self.assertRaisesRegex(ValueError, "identities overlap"):
            plan.check_split(split, 2, 10)
        split["provisional_final"].pop()
        with self.assertRaisesRegex(ValueError, "20 selection and 100"):
            plan.check_split(split, 2, 10)

    def test_ppt_pin_rejects_wrong_source_before_claiming_120(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = Path(temp) / "task_registry/tasks.json"
            registry.parent.mkdir(parents=True)
            registry.write_text("{}")
            with patch.object(plan.subprocess, "run") as run:
                run.side_effect = [type("Result", (), {"stdout": plan.PPT_COMMIT + "\n"})(),
                                   type("Result", (), {"stdout": ""})()]
                with self.assertRaisesRegex(ValueError, "registry hash changed"):
                    plan.plan_ppt(Path(temp))

    def test_private_manifest_cannot_be_written_into_public_checkout(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(ValueError, "ignored work"):
                plan.produce(root, root, root, root / "docs/private.json", root / "docs/public.json")

    def test_evidence_preflight_checks_bytes_but_cannot_admit_a_task(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bindings = {}
            for name in plan.ARTIFACT_BINDINGS:
                path = root / (name + ".bin")
                path.write_bytes(name.encode())
                bindings[name] = {"path": path.name, "sha256": sha256(path.read_bytes()).hexdigest()}
            task = {"task_id": "private-case", "input_sha256": "a"*64}
            evidence = {"schema": "office-web-evaluator-task-evidence-v1",
                        "cell_id": "excel-web", "task_id": task["task_id"],
                        "source_identity_sha256": task["input_sha256"],
                        "artifacts": bindings,
                        "evaluator_checks": {name: True for name in plan.EVALUATOR_CHECKS}}
            receipt = root / "receipt.json"
            receipt.write_text(json.dumps(evidence))
            result = plan.preflight_task_evidence("excel-web", task, receipt, root)
            self.assertFalse(result["gui_admitted"])
            self.assertEqual(result["artifact_count"], len(plan.ARTIFACT_BINDINGS))
            (root / "positive_saved.bin").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                plan.preflight_task_evidence("excel-web", task, receipt, root)
            (root / "positive_saved.bin").write_bytes(b"positive_saved")
            evidence["artifacts"]["positive_saved"]["path"] = "../outside.bin"
            receipt.write_text(json.dumps(evidence))
            with self.assertRaisesRegex(ValueError, "unsafe"):
                plan.preflight_task_evidence("excel-web", task, receipt, root)

    def test_public_receipt_excludes_final_ids_and_private_output_is_separate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "docs/evidence").mkdir(parents=True)
            (root / plan.PPT_GUI_RECEIPT).write_text('{"schema":"ppt-control"}')
            (root / plan.EXCEL_GUI_RECEIPT).write_text('{"schema":"excel-control"}')
            ppt = {"cell_id": "powerpoint-web", "source": {"registry_sha256": "a"*64},
                   "sets": {"selection": rows(20, 2, "ppt-selection"),
                            "provisional_final": rows(100, 10, "SECRET-PPT-FINAL")},
                   "cluster_quality": {"entity": "unresolved"},
                   "prior_gui_control": {"status": "human selection control", "official_final_credit": 0}}
            excel = {"cell_id": "excel-web", "source": {"archive_sha256": "b"*64},
                     "sets": {"selection": rows(20, 3, "excel-selection"),
                              "provisional_final": rows(100, 15, "SECRET-EXCEL-FINAL")},
                     "cluster_quality": {"entity": "unresolved"},
                     "prior_gui_control": {"status": "authored SEC development control", "official_final_credit": 0}}
            private = root / "work/private.json"
            public = root / "docs/evidence/public.json"
            with patch.object(plan, "plan_ppt", return_value=ppt), patch.object(
                    plan, "plan_excel", return_value=excel):
                result = plan.produce(root, root, root, private, public)
            self.assertIn("SECRET-PPT-FINAL", private.read_text())
            self.assertNotIn("SECRET-PPT-FINAL", public.read_text())
            self.assertNotIn("SECRET-EXCEL-FINAL", public.read_text())
            self.assertEqual(private.stat().st_mode & 0o777, 0o600)
            self.assertEqual([cell["counts"]["official_hidden_final_tasks"] for cell in result["cells"]], [0, 0])
            self.assertEqual(json.loads(public.read_text())["contract"]["qualification_status"], "not_qualified")
            with patch.object(plan, "plan_ppt", return_value=ppt), patch.object(
                    plan, "plan_excel", return_value=excel):
                with self.assertRaisesRegex(ValueError, "must differ"):
                    plan.produce(root, root, root, public, public)


if __name__ == "__main__":
    unittest.main()
