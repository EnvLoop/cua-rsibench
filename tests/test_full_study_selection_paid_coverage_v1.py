"""20-task paid-call coverage cannot be inferred from two category labels."""

from __future__ import annotations

from hashlib import sha256
import unittest

from cursibench import full_study_selection_paid_coverage_v1 as coverage


def _hash(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def fixture(cell: str, *, per_task_environment: bool):
    tasks = [{"task_id": f"selection-{index:02d}",
              "package_sha256": _hash(f"package-{index}".encode())}
             for index in range(20)]
    digest = _hash(coverage._canonical(tasks))
    checkpoint = _hash(b"selected checkpoint")
    category = ("e2b" if cell == "desktop-native" else
                "storage_application")
    paid = []
    if per_task_environment:
        for index, task in enumerate(tasks):
            paid.append({
                "attempt_id": f"select-1-env-{index:02d}",
                "category": category, "result_present": True,
                "result_status": "active",
                "request": {
                    "selection_attempt": "select-1", "cell_id": cell,
                    "task_id": task["task_id"],
                    "package_sha256": task["package_sha256"],
                    "checkpoint_path_sha256": checkpoint,
                },
            })
    else:
        paid.append({
            "attempt_id": "select-1-env-batch", "category": category,
            "result_present": True, "result_status": "active",
            "request": {
                "selection_attempt": "select-1", "cell_id": cell,
                "selection_identities_sha256": digest,
                "selection_tasks": tasks,
            },
        })
    paid.append({
        "attempt_id": "select-1-sampler-setup", "category": "tinker",
        "result_present": True, "result_status": "ready",
        "request": {"selection_attempt": "select-1", "cell_id": cell,
                    "selection_identities_sha256": digest,
                    "checkpoint_path_sha256": checkpoint},
    })
    for index, task in enumerate(tasks):
        paid.append({
            "attempt_id": f"select-1-sample-{index:02d}",
            "category": "tinker", "result_present": True,
            "result_status": "completed",
            "request": {
                "selection_attempt": "select-1", "cell_id": cell,
                "task_id": task["task_id"],
                "package_sha256": task["package_sha256"],
                "checkpoint_path_sha256": checkpoint,
                "step": 0,
            },
        })
    args = dict(cell_id=cell, attempt_id="select-1",
                checkpoint_sha256=checkpoint, selection_tasks=tasks,
                selection_identities_sha256=digest, paid_calls=paid,
                related_paid_attempt_ids={row["attempt_id"] for row in paid})
    return args


class SelectionPaidCoverageTests(unittest.TestCase):
    def test_each_task_has_tinker_and_real_environment_coverage(self):
        for cell, per_task in (("gitlab", True),
                               ("odoo-community", False),
                               ("desktop-native", True)):
            with self.subTest(cell=cell):
                result = coverage.validate(**fixture(
                    cell, per_task_environment=per_task))
                self.assertEqual(result["task_count"], 20)
                self.assertEqual(result["sample_paid_attempt_count"], 20)
                self.assertTrue(result[
                    "all_task_ids_have_sample_and_environment"])

    def test_one_category_pair_cannot_stand_in_for_twenty_rollouts(self):
        data = fixture("gitlab", per_task_environment=True)
        data["paid_calls"] = data["paid_calls"][:1] + data["paid_calls"][-1:]
        data["related_paid_attempt_ids"] = {
            row["attempt_id"] for row in data["paid_calls"]}
        with self.assertRaisesRegex(ValueError,
                                    "selection_paid_twenty_task_coverage_missing"):
            coverage.validate(**data)

    def test_omitted_paid_call_or_changed_task_binding_fails(self):
        data = fixture("odoo-community", per_task_environment=False)
        data["paid_calls"].pop()
        with self.assertRaisesRegex(ValueError,
                                    "selection_paid_attempt_hidden_or_missing"):
            coverage.validate(**data)
        data = fixture("odoo-community", per_task_environment=False)
        data["paid_calls"][-1]["request"]["package_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError,
                                    "selection_paid_task_or_checkpoint_changed"):
            coverage.validate(**data)

    def test_batch_environment_must_name_exact_twenty_tasks(self):
        data = fixture("odoo-community", per_task_environment=False)
        data["paid_calls"][0]["request"]["selection_tasks"] = data[
            "selection_tasks"][:-1]
        with self.assertRaisesRegex(ValueError,
                                    "selection_paid_environment_batch_roster_changed"):
            coverage.validate(**data)

    def test_task_sample_with_noncompleted_paid_result_cannot_score(self):
        data = fixture("gitlab", per_task_environment=True)
        data["paid_calls"][-1]["result_status"] = "failed"
        with self.assertRaisesRegex(ValueError,
                                    "selection_paid_model_result_not_completed"):
            coverage.validate(**data)


if __name__ == "__main__":
    unittest.main()
